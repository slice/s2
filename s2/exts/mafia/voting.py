__all__ = ["Votes", "Voting", "trial_and_judgement_loop", "Spotlight"]

import asyncio
import enum
import collections
import math
from typing import (
    Any,
    Dict,
    Callable,
    Awaitable,
    Generic,
    DefaultDict,
    Tuple,
    List,
    Optional,
    TYPE_CHECKING,
    TypeVar,
)

import discord
from lifesaver.utils.formatting import pluralize

from . import messages
from .utils import basic_command, select_player
from .formatting import Message, msg, user_listing

if TYPE_CHECKING:
    from .player import Player
    from .game import MafiaGame
    from .roster import Roster

VT = TypeVar("VT")
VR = TypeVar("VR")


class Judgement(enum.Enum):
    GUILTY = enum.auto()
    INNOCENT = enum.auto()
    ABSTAINED = enum.auto()

    def __str__(self) -> str:
        if self is self.GUILTY:  # type: ignore
            return "guilty"
        elif self is self.INNOCENT:  # type: ignore
            return "innocent"
        elif self is self.ABSTAINED:  # type: ignore
            return "abstained"
        return "...?"


class Votes(Generic[VR, VT]):
    def __init__(self) -> None:
        self.votes: DefaultDict[VT, List[VR]] = collections.defaultdict(list)

    def tallied(self) -> Dict[VT, int]:
        """Return the votes, but tallied up instead of lists of voters."""
        return {target: len(votes) for target, votes in self.votes.items()}

    def sorted_tallies(
        self, descending: bool = True
    ) -> "collections.OrderedDict[VT, int]":
        """Return the tallied votes, defaulting to descending order."""
        sorted_tallies = sorted(
            self.tallied().items(), key=lambda item: item[1], reverse=descending
        )
        return collections.OrderedDict(sorted_tallies)

    def sorted(
        self, *, descending: bool = True
    ) -> "collections.OrderedDict[VT, List[VR]]":
        """Return the votes as an ordered dictionary. """
        sorted_items = sorted(
            self.votes.items(), key=lambda item: len(item[1]), reverse=descending
        )
        return collections.OrderedDict(sorted_items)

    def get_vote(self, voter: VR) -> Optional[VT]:
        """Return who a voter voted for.

        The the voter hasn't voted for someone yet, ``None`` is returned.
        """
        if (
            vote := discord.utils.find(
                lambda item: voter in item[1], self.votes.items()
            )
        ) is not None:
            return vote[0]
        return None

    def add_vote(self, voter: VR, target: VT) -> None:
        """Add a voter's vote for someone.

        Raises if the voter has already voted.
        """
        if self.get_vote(voter) is not None:
            raise ValueError(f"{voter!r} has already voted")
        self.votes[target].append(voter)

    def cancel_vote(self, voter: VR) -> None:
        """Remove a voter's vote for someone.

        Raises if the voter hasn't voted yet.
        """
        if (vote := self.get_vote(voter)) is None:
            raise KeyError(repr(voter))

        self.votes[vote].remove(voter)


class Spotlight:
    def __init__(self, game: "MafiaGame", player: "Player"):
        self.game = game
        self.player = player

    async def __aenter__(self) -> None:
        assert self.game.all_chat is not None
        await self.game.all_chat.set_permissions(self.player.member, send_messages=True)
        await self.game._lock()

    async def __aexit__(self, *args: Any) -> None:
        assert self.game.all_chat is not None
        await self.game.all_chat.set_permissions(self.player.member, overwrite=None)
        await self.game._unlock()


class Voting:
    def __init__(self, game: "MafiaGame"):
        self.game = game

        self.trial_voting_time = 30
        self.defense_time = 20
        self.judgement_voting_time = 20
        self.last_words_time = 5

        self.trial_votes = Votes["Player", "Player"]()
        self.judgement_votes: Dict["Player", Judgement] = {}

    # properties {{{

    @property
    def all_chat(self) -> discord.TextChannel:
        assert (all_chat := self.game.all_chat) is not None
        return all_chat

    @property
    def roster(self) -> "Roster":
        assert (roster := self.game.roster) is not None
        return roster

    # }}}

    # messages & formatting {{{

    def _msg_trial_time(self) -> str:
        return msg(
            messages.VOTING_TIME_ANNOUNCEMENT,
            seconds=self.trial_voting_time,
            votes=pluralize(vote=self.trial_votes_required()),
            players=user_listing(self.roster.alive),
        )

    def _msg_already_voted(self, voter: "Player", target: "Player") -> str:
        return msg(messages.ALREADY_VOTED_FOR, voter=voter.mention, target=target)

    def _msg_trial_time_remaining(self, seconds: int) -> str:
        return msg(messages.VOTING_TIME_REMAINING, seconds=seconds)

    def _msg_voted_for(self, voter: "Player", target: "Player") -> str:
        return msg(messages.VOTED_FOR, voter=voter, target=target)

    def _format_sorted_tallies(self, votes: Votes["Player", "Player"]) -> str:
        sorted_tallies = votes.sorted_tallies()
        highest_tally = max(sorted_tallies.values())

        def format_item(item: Tuple["Player", int]) -> str:
            target, votes = item
            formatted = msg(messages.VOTES_ENTRY, votes=votes, mention=target.mention)
            if votes == highest_tally:
                formatted = f"**{formatted}**"
            return formatted

        return "\n".join(map(format_item, sorted_tallies.items()))

    # }}}

    # shared handling {{{

    async def run_task(
        self,
        awaitable: Awaitable[None],
        *,
        duration: int,
        time_remaining_message: "Message",
    ) -> None:
        """Run a task for a duration, while warning players when it ends soon."""
        if duration < 10:
            raise ValueError("needs to run for at least 10 seconds")
        task = self.game.bot.loop.create_task(awaitable)

        await asyncio.sleep(duration - 10)
        await self.all_chat.send(msg(time_remaining_message, seconds=10))
        await asyncio.sleep(5)
        await self.all_chat.send(msg(time_remaining_message, seconds=5))
        await asyncio.sleep(5)

        task.cancel()

    async def handle_messages(
        self,
        *,
        private: bool = False,
        handler: Callable[[discord.Message, "Player"], Awaitable[None]],
    ) -> None:
        """Handle incoming messages from alive players."""

        def _check(msg: discord.Message) -> bool:
            if (player := self.roster.get_player(msg.author)) is None:
                return False
            if player.dead:
                return False
            return (
                (msg.guild is None or msg.channel == player.channel)
                if private
                else msg.channel == self.all_chat
            )

        async def _wrapper_handler(msg: discord.Message) -> None:
            player = self.roster.get_player(msg.author)
            assert player is not None
            await handler(msg, player)

        while True:
            msg = await self.game.bot.wait_for("message", check=_check)
            self.game.bot.loop.create_task(_wrapper_handler(msg))

    # }}}

    # trial {{{

    def trial_votes_required(self) -> int:
        return max(math.floor(len(self.roster.alive) / 3), 2)

    async def _process_trial_vote(self, msg: discord.Message, player: "Player") -> None:
        selector = basic_command("!vote", msg.content)
        if selector is None:
            return

        target = select_player(selector, self.roster.alive)

        if not target or target.member == msg.author:
            await msg.add_reaction(self.game.bot.emoji("generic.no"))
            return

        if (previous_target := self.trial_votes.get_vote(player)) is not None:
            if previous_target == target:
                # voter has already voted for this person
                await self.all_chat.send(self._msg_already_voted(player, target))
                return
            self.trial_votes.cancel_vote(player)

        self.trial_votes.add_vote(player, target)

        update_content = (
            self._msg_voted_for(player, target)
            + "\n\n"
            + self._format_sorted_tallies(self.trial_votes)
        )
        await self.all_chat.send(update_content)

    async def trial_voting(self) -> Optional["Player"]:
        """Go through voting time to put someone on trial."""
        await self.all_chat.send(self._msg_trial_time())

        # gather messages
        await self.run_task(
            self.handle_messages(handler=self._process_trial_vote),
            duration=self.trial_voting_time,
            time_remaining_message=messages.VOTING_TIME_REMAINING,
        )

        sorted_tallies = self.trial_votes.sorted_tallies()

        if not sorted_tallies:
            # no votes happened?
            return None

        st_items = list(sorted_tallies.items())
        highest_target, highest_votes = st_items[0]

        if list(sorted_tallies.values()).count(highest_votes) > 1:
            # tie
            return None

        if highest_votes < self.trial_votes_required():
            # not enough votes
            return None

        return highest_target

    # }}}

    # judgement {{{

    async def _process_judgement_vote(
        self, message: discord.Message, player: "Player"
    ) -> None:
        if player not in self.judgement_votes:
            # wasn't placed in the original voting map; ignore
            return

        if message.content in {"!innocent", "!inno", "!i"}:
            vote = Judgement.INNOCENT
        elif message.content in {"!guilty", "!g"}:
            vote = Judgement.GUILTY
        else:
            return

        public_message = (
            messages.JUDGEMENT_VOTE_PUBLIC
            if self.judgement_votes[player] is Judgement.ABSTAINED
            else messages.JUDGEMENT_VOTE_PUBLIC_CHANGE
        )

        self.judgement_votes[player] = vote

        await self.all_chat.send(msg(public_message, player=player))
        await message.channel.send(msg(messages.JUDGEMENT_VOTE, judgement=vote))

    def tally_judgement_votes(self, judgement: Judgement) -> int:
        return sum(1 for vote in self.judgement_votes.values() if vote is judgement)

    async def judge(self, suspect: "Player") -> Tuple[int, int]:
        async with Spotlight(self.game, suspect):
            await self.all_chat.send(msg(messages.PUT_ON_TRIAL, player=suspect.mention))
            await asyncio.sleep(self.defense_time)

        voters = self.roster.alive - {suspect}
        self.judgement_votes = {player: Judgement.ABSTAINED for player in voters}

        mentions = ", ".join(player.mention for player in voters)
        await self.all_chat.send(
            f"{mentions}: " + msg(messages.JUDGEMENT_PROMPT, player=suspect)
        )

        # collect !innocent, !guilty votes
        await self.run_task(
            self.handle_messages(private=True, handler=self._process_judgement_vote),
            duration=self.judgement_voting_time,
            time_remaining_message=messages.VOTING_TIME_REMAINING,
        )

        guilty_votes = self.tally_judgement_votes(Judgement.GUILTY)
        innocent_votes = self.tally_judgement_votes(Judgement.INNOCENT)

        def _format_judgement_vote(item: Tuple["Player", Judgement]) -> str:
            player, judgement = item
            emoji = {
                Judgement.ABSTAINED: "\N{MEDIUM WHITE CIRCLE}",
                Judgement.GUILTY: "\N{LARGE RED CIRCLE}",
                Judgement.INNOCENT: "\N{LARGE GREEN CIRCLE}",
            }[judgement]

            line = (
                f"{player} **abstained**."
                if judgement is Judgement.ABSTAINED
                else f"{player} voted **{judgement}**."
            )

            return f"{emoji} {line}"

        vote_summary = (
            "\n".join(map(_format_judgement_vote, self.judgement_votes.items()))
            + "\n\n"
            + f"Guilty: {guilty_votes}\nInnocent: {innocent_votes}"
        )
        await self.all_chat.send(vote_summary)

        return guilty_votes, innocent_votes

    # }}}

    async def lynch(self, player: "Player") -> None:
        async with Spotlight(self.game, player):
            await self.all_chat.send(
                msg(messages.LYNCH_LAST_WORDS_PROMPT, player=player)
            )
            await asyncio.sleep(self.last_words_time)
            await player.kill()
            await self.game._display_will(player)
        await self.all_chat.send(msg(messages.REST_IN_PEACE, player=player))
        await asyncio.sleep(3)
        await self.all_chat.send(embed=self.game._role_reveal(player))
        await self.game._update_role_listing()
        await asyncio.sleep(5)

    async def trial_and_judgement_loop(self) -> None:
        assert self.game.all_chat is not None

        trials = 0

        # only perform three trials at most
        while trials < 3:
            suspect = await self.trial_voting()

            if not suspect:
                # no suspect could be determined
                await self.all_chat.send(msg(messages.VOTING_TIME_STALEMATE))
                return

            # now we have a suspect, give them their defense and see poll the
            # town for their judgement.
            guilty_votes, innocent_votes = await self.judge(suspect)

            if guilty_votes > innocent_votes:
                # voted guilty; time to lynch
                await self.lynch(suspect)
                return
            else:
                if guilty_votes == innocent_votes:
                    await self.all_chat.send(
                        msg(messages.JUDGEMENT_TIE, player=suspect)
                    )
                elif innocent_votes > guilty_votes:
                    await self.all_chat.send(
                        msg(messages.JUDGEMENT_INNOCENT, player=suspect)
                    )
                await asyncio.sleep(5)

            self.trial_votes = Votes()
            self.judgement_votes = {}

            trials += 1

        await self.all_chat.send(msg(messages.VOTING_TIME_TOO_MANY_TRIALS))


async def trial_and_judgement_loop(game: "MafiaGame") -> None:
    await Voting(game).trial_and_judgement_loop()
