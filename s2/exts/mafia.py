import asyncio
import collections
import enum
import logging
import math
import random
import typing

import discord
import lifesaver
from discord.ext import commands
from lifesaver.utils import pluralize


def generate_name(name: str) -> str:
    id = random.randint(100, 1000)
    return f'dogbot-mafiagame-{name}-{id}'


class MafiaGameState(enum.Enum):
    WAITING = enum.auto()
    STARTED = enum.auto()


class Roster:
    """A class that deals with the sets of players currently in the game."""

    def __init__(self, game, *, creator):
        self.game = game

        #: The set of all alive members of the mafia.
        self.mafia = set()

        #: The set of all players who have joined the game.
        self.all = {creator}

        #: The set of all alive players.
        self.players = {creator}

    @property
    def townies(self):
        """All players who aren't in the mafia."""
        return {player for player in self.players if player not in self.mafia}

    def all_townies_dead(self):
        """Return whether all townies are dead."""
        return self.players - self.mafia == set()

    def pick_mafia(self, *, portion: int = 3, max: int = 2):
        """Randomly determine the members of the mafia."""
        n_mafia = min(math.ceil(len(self.all) / portion), max)
        mafia = self.mafia = set(random.sample(self.all, n_mafia))
        return mafia

    def is_alive(self, user):
        return user in self.players

    def kill(self, user):
        """Effectively "kill" a user, removing them from the list of alive players.

        The user will still remain in the "all" set.
        """
        self.players.remove(user)

    def add(self, user):
        """Add a user to the list of players."""
        self.all.add(user)
        self.players.add(user)


class MafiaGame:
    """A class representing a game of mafia."""

    def __init__(self, bot, *, creator: discord.Member, channel: discord.TextChannel):
        self.bot = bot
        self.log = logging.getLogger(__name__)

        #: The game roster, a class that stores full lists of players and
        #: handles mafia selection.
        self.roster = Roster(self, creator=creator)

        #: The user who created the game.
        self.creator = creator

        #: The channel that the lobby was created in.
        self.channel = channel

        #: The main "game channel" where both mafia and townies can speak.
        self.game_channel: typing.Optional[discord.TextChannel] = None

        #: The guild where the game is taking place.
        self.guild: discord.Guild = channel.guild

        #: The text channel reserved for mafia members.
        self.mafia_chat: typing.Optional[discord.TextChannel] = None

        #: The current state of the game.
        self.state = MafiaGameState.WAITING

        #: The current day.
        self.day = 1

        #: The current time of day.
        self.daytime = True

        #: A mapping of hanging votes during the daytime.
        #: The key is the user ID of the person to hang, while the value is the
        #: list of users who voted for that person to be hanged.
        self.hanging_votes = collections.defaultdict(list)

        #: The victim that will be killed tonight, decided by mafia.
        self.victim_tonight: typing.Optional[discord.Member] = None

    #: The number of players required before the game can automatically started.
    REQUIRED_PLAYERS = 8

    #: Debugging mode. Shortens some wait times.
    DEBUG = False

    async def gather_players(self):
        """Interactively gather game participants."""
        self.log.debug('gathering players for game')

        def format_participants():
            required = self.REQUIRED_PLAYERS - len(self.roster.all)
            formatted = '\n'.join(str(user) for user in self.roster.all)

            required = pluralize(player=required, with_indicative=True)
            embed = discord.Embed(title='Players', description=formatted)
            embed.set_footer(text=f'{required} still needed')
            return embed

        join_emoji = '\N{LARGE RED CIRCLE}'
        force_start_emoji = '\N{LARGE BLUE CIRCLE}'
        abort_emoji = '\N{MEDIUM WHITE CIRCLE}'

        prompt = await self.channel.send(
            f'{self.creator} made a mafia lobby. Join by reacting with {join_emoji}!',
            embed=format_participants(),
        )
        await prompt.add_reaction(join_emoji)

        def reaction_check(reaction, user):
            return reaction.message.id == prompt.id and not user.bot

        while True:
            reaction, user = await self.bot.wait_for('reaction_add', check=reaction_check)

            if reaction.emoji not in (join_emoji, force_start_emoji, abort_emoji):
                continue

            overriding = reaction.emoji == force_start_emoji and user == self.creator
            is_aborting = reaction.emoji == abort_emoji and user == self.creator

            if is_aborting:
                self.log.debug('aborting game')
                await prompt.delete()
                return False

            if reaction.emoji == join_emoji:
                self.log.debug('%r is joining the game', user)
                self.roster.add(user)

            if len(self.roster.players) == self.REQUIRED_PLAYERS or overriding:
                if len(self.roster.players) < 3:
                    await self.channel.send(
                        f"{self.creator.mention}: Can't force start. At least 3 players are required.")
                    continue

                await prompt.edit(content='Game starting. Good luck!', embed=None)

                try:
                    await prompt.clear_reactions()
                except discord.HTTPException:
                    pass

                break
            else:
                await prompt.edit(embed=format_participants())

        self.log.debug('we have enough players, creating game channel')

        # disallow @everyone and allow self
        overwrites = {
            self.guild.default_role: discord.PermissionOverwrite(read_messages=False),
            self.guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        }

        # grant every player access to the channel
        overwrites.update({
            player: discord.PermissionOverwrite(read_messages=True)
            for player in self.roster.all
        })

        self.log.debug('game channel overwrites: %r', overwrites)

        self.game_channel = await self.guild.create_text_channel(
            generate_name('town'), overwrites=overwrites)

        self.log.debug('created game channel: %r', self.game_channel)

    async def pick_mafia(self):
        """Set up the mafia members for this game and creates the chat channel."""
        mafia = self.roster.pick_mafia()
        self.log.debug('picked mafia: %r', mafia)

        block = discord.PermissionOverwrite(read_messages=False)
        allow = discord.PermissionOverwrite(read_messages=True, send_messages=True)

        overwrites = {
            self.guild.default_role: block,
            self.guild.me: allow,
        }
        overwrites.update({
            mafia_member: allow
            for mafia_member in self.roster.mafia
        })

        self.mafia_chat = await self.guild.create_text_channel(
            generate_name('mafia'), overwrites=overwrites)

        flavor = random.choice([
            'Say hello!',
            'Greet each other, mafia!',
        ])

        mentions = ', '.join(member.mention for member in self.roster.mafia)

        await self.mafia_chat.send(
            f'{mentions}: {flavor} In this channel you can secretly talk with your evil partner.',
        )

    async def notify_roles(self):
        for player in self.roster.townies:
            await player.send(
                f'**You are innocent!** Your goal is to hang the mafia. '
                f'The game will take place in {self.game_channel.mention}.'
            )

    async def pick_victim(self):
        def check(message):
            return message.channel == self.mafia_chat and message.author in self.roster.mafia

        while True:
            message = await self.bot.wait_for('message', check=check)

            if message.content.startswith('!kill '):
                target_name = message.content[len('!kill '):]
                target = discord.utils.find(
                    lambda player: player.name.lower() == target_name.lower() or player.mention == target_name,
                    self.roster.townies,
                )

                if not target:
                    await message.add_reaction(self.bot.emoji('generic.no'))
                    continue

                self.victim_tonight = target
                await self.mafia_chat.send(f'**{target}** will be killed tonight.')

    async def alltalk(self):
        """Allow all game participants to speak in the main game channel."""
        self.log.debug('commencing alltalk!')
        for member in self.roster.all:
            self.log.debug('alltalk: allowing %r to speak in %r', member, self.game_channel)
            await self.game_channel.set_permissions(member, read_messages=True, send_messages=True)

    async def gather_hanging_votes(self):
        def check(message):
            return message.channel == self.game_channel and self.roster.is_alive(message.author)

        # TODO: these are bad
        def has_voted(voter):
            for target_id, voter_ids in self.hanging_votes.items():
                if voter.id in voter_ids:
                    return True
            return False

        def get_vote(voter):
            for target_id, voter_ids in self.hanging_votes.items():
                if voter.id in voter_ids:
                    return target_id

        while True:
            message = await self.bot.wait_for('message', check=check)

            if not message.content.startswith('!vote '):
                continue

            try:
                target_name = message.content[len('!vote '):]

                target = discord.utils.find(
                    lambda player: player.name.lower() == target_name.lower() or player.mention == target_name,
                    self.roster.players
                )

                if not target or target == message.author:
                    await message.add_reaction(self.bot.emoji('generic.no'))
                    continue

                self.log.debug('%r is voting to hang %r', message.author, target)

                if has_voted(message.author):
                    previous_target = get_vote(message.author)

                    if previous_target == target.id:
                        # voter has already voted for this person
                        await self.game_channel.send(
                            f'{message.author.mention}: You have already voted for {target}.')
                        continue

                    # remove the vote for the other person (switching votes!)
                    self.hanging_votes[previous_target].remove(message.author.id)

                self.hanging_votes[target.id].append(message.author.id)

                await self.game_channel.send(
                    f'**{message.author}** has voted for **{target}** to be hanged.\n\n' +
                    '\n'.join(f'<@{key}>: {len(value)} vote(s)' for key, value in self.hanging_votes.items() if not value)
                )
            except Exception:
                self.log.exception('something went wrong while processing votes:')

    async def lock(self):
        """Prevent anyone from sending messages in the game channel."""
        await self.game_channel.set_permissions(
            self.guild.default_role, read_messages=False, send_messages=False)

    async def unlock(self):
        """Undo a lock."""
        await self.game_channel.set_permissions(
            self.guild.default_role, read_messages=False, send_messages=None)

    async def game_over(self, *, mafia_won: bool):

        def format_listing(users):
            return ', '.join(user.mention for user in users)

        if mafia_won:
            await self.game_channel.send(
                f'**Currently Alive Mafia:**\n\n{format_listing(self.roster.mafia)}')
        else:
            await self.game_channel.send(
                f'**Currently Alive Town:**\n\n{format_listing(self.roster.townies)}')

        await asyncio.sleep(2.0)
        await self.alltalk()
        await asyncio.sleep(8.0)

    async def game_loop(self):
        mentions = ', '.join(player.mention for player in self.roster.players)
        await self.game_channel.send(f'{mentions}: The main game will be conducted here! Make sure to have fun!')
        await asyncio.sleep(5.0)

        while True:
            # send current day/daytime state to players
            emoji = '\N{BLACK SUN WITH RAYS}' if self.daytime else '\N{NIGHT WITH STARS}'
            await self.game_channel.send(f'{emoji} **{"Day" if self.daytime else "Night"} {self.day}** {emoji}')
            self.log.info('>> Time progression. Day %d, %s.', self.day, 'day' if self.daytime else 'night')

            # if we are on D1, send some directions and just move onto N1.
            if self.daytime and self.day == 1:
                self.log.info('Tutorial section, this will take a bit.')
                await self.game_channel.send(
                    '**Welcome to the game!**\n\n'
                    f'There are {len(self.roster.mafia)} mafia hiding within a town of innocents. '
                    'If you are an innocent, your goal is to lynch the mafia. '
                    'If you are a mafia, your goal is to work with your partner to wipe out the innocents before '
                    'they find out about you!'
                )
                await asyncio.sleep(3 if self.DEBUG else 15)
                self.daytime = False
                continue

            if self.daytime:
                if self.victim_tonight:
                    self.roster.kill(self.victim_tonight)
                    await self.game_channel.set_permissions(self.victim_tonight, read_messages=True, send_messages=False)
                    await self.game_channel.send(
                        f'**{self.victim_tonight}** was unfortunately found dead in their home last night.'
                    )
                    await asyncio.sleep(3.0)
                    await self.game_channel.send('They were **innocent.**')
                    await asyncio.sleep(5.0)
                    self.victim_tonight = None

                    if self.roster.all_townies_dead():
                        await self.game_channel.send('\U0001f52a **Mafia win!** \U0001f52a')
                        await self.game_over(mafia_won=True)
                        break

                votes_required = math.floor(len(self.roster.players) / 3)
                self.log.info('It is now discussion time. (%d votes required for hanging.)', votes_required)
                await self.game_channel.send(
                    'Discussion time! Alive town members can now vote who to hang. To vote, type `!vote <username>` in '
                    f'chat. You have 30 seconds, and {votes_required} vote(s) are required to hang someone.'

                    '\n\n**Alive Players:**\n' +
                    '\n'.join(f'- {user.name}' for user in self.roster.players)
                )

                # gather hanging votes.
                task = self.bot.loop.create_task(self.gather_hanging_votes())
                await asyncio.sleep(50.0)
                await self.game_channel.send('**10 seconds of voting remaining!**')
                await asyncio.sleep(5.0)
                await self.game_channel.send('**5 seconds of voting remaining!**')
                await asyncio.sleep(5.0)
                task.cancel()

                self.hanging_votes = {target_id: len(votes) for target_id, votes in self.hanging_votes.items()}
                self.log.info('Hanging votes (postprocessed): %s', self.hanging_votes)
                sorted_votes = sorted(list(self.hanging_votes.items()), key=lambda e: e[1], reverse=True)
                vote_board = list(filter(
                    lambda e: e[1] >= votes_required, sorted_votes
                ))
                self.log.info('Final voting board: %s', vote_board)
                if not vote_board:
                    await self.game_channel.send('A verdict was not reached in time. Oh well!')
                else:
                    hanged = discord.utils.get(self.roster.players, id=vote_board[0][0])
                    await self.lock()
                    await self.game_channel.set_permissions(hanged, read_messages=True, send_messages=True)
                    await self.game_channel.send(
                        f'\N{SKULL} {hanged.mention}, you have been voted to be hanged. Do you have any last words '
                        'before your death? You have 15 seconds.'
                    )
                    await asyncio.sleep(3.0 if self.DEBUG else 15.0)
                    await self.game_channel.set_permissions(hanged, read_messages=True, send_messages=False)
                    await self.unlock()
                    await self.game_channel.send(f'\N{SKULL} **Rest in peace, {hanged}. You will be missed.** \N{SKULL}')
                    self.roster.kill(hanged)
                    await asyncio.sleep(3)
                    was_mafia = hanged in self.roster.mafia
                    if was_mafia:
                        self.roster.mafia.remove(hanged)
                        await self.mafia_chat.set_permissions(hanged, read_messages=True, send_messages=False)
                    await self.game_channel.send(f'{hanged} was **{"mafia" if was_mafia else "innocent"}.**')
                    await asyncio.sleep(5)

                # reset hanging votes
                self.hanging_votes = collections.defaultdict(list)
            else:
                await self.game_channel.send(
                    "Night time! Sleep tight, and don't let the bed bugs bite!"
                )
                await self.lock()
                alive_mafia = ', '.join(mafia.mention for mafia in self.roster.mafia)
                await self.mafia_chat.send(
                    f"{alive_mafia}: It's time to kill! \N{HOCHO} Discuss someone to kill, then type "
                    "`!kill <username>` in chat when you have decided on someone to stab. You have 30 seconds! "
                    "Alternatively, you can do nothing to stay low. "
                    "Once you choose someone to kill, you can't go back to killing nobody!\n\n" +
                    '\n'.join(f'- {player.name}' for player in self.roster.townies)
                )
                task = self.bot.loop.create_task(self.pick_victim())
                await asyncio.sleep(2.0 if self.DEBUG else 30.0)
                task.cancel()
                await self.unlock()

            if not self.roster.mafia:
                await self.game_channel.send('\U0001f64f **Innocents win!** \U0001f64f')
                await self.game_over(mafia_won=False)
                break
            elif self.roster.all_townies_dead():
                await self.game_channel.send('\U0001f52a **Mafia win!** \U0001f52a')
                await self.game_over(mafia_won=True)
                break

            if not self.daytime:
                # it's night, so move onto next
                self.day += 1
                self.daytime = True
            else:
                # it's day, so move onto night
                self.daytime = False

    async def start(self):
        self.log.debug('game started! gathering players (%d needed).', self.REQUIRED_PLAYERS)
        success = await self.gather_players()
        if success is False:
            self.log.debug('hmm. game was aborted!')
            return
        await self.pick_mafia()
        await self.notify_roles()
        await asyncio.sleep(5.0)
        self.state = MafiaGameState.STARTED
        await self.game_loop()

        await self.game_channel.send('Game over! This channel will self destruct in 10 seconds.')
        await asyncio.sleep(10.0)

        await self.mafia_chat.delete()
        await self.game_channel.delete()


class Mafia(lifesaver.Cog):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.sessions = set()

    @lifesaver.command(hidden=True, enabled=False)
    @commands.guild_only()
    async def mafia(self, ctx: lifesaver.Context):
        """Starts a game of mafia."""
        if ctx.channel.id in self.sessions:
            await ctx.send('A game has already been started here.')
            return

        self.sessions.add(ctx.channel.id)
        game = MafiaGame(ctx.bot, creator=ctx.author, channel=ctx.channel)
        await game.start()
        self.sessions.remove(ctx.channel.id)


def setup(bot):
    bot.add_cog(Mafia(bot))
