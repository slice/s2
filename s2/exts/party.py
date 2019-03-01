import asyncio
from random import choice

import discord
from discord import Permissions
from discord.ext.commands import BucketType, cooldown
from discord.http import Route
from lifesaver.bot import Cog, Context, group

PARTY_PERMISSIONS = {
    "add_reactions",
    "read_messages",
    "send_messages",
    "embed_links",
    "attach_files",
    "external_emojis",
    "connect",
    "speak",
    "use_voice_activation",
    "change_nickname",
    "read_message_history",
}

ADJECTIVES = [
    "awesome",
    "sweet",
    "fabulous",
    "crazy",
    "extraordinary",
    "unusual",
    "remarkable",
    "significant",
    "tiny",
    "hollow",
    "spherical",
    "shiny",
    "bouncy",
    "electrified",
]


class Party:
    def __init__(
        self, bot, creator: discord.User, guild: discord.Guild, duration: int = 5 * 60
    ):
        self.bot = bot
        self.creator = creator
        self.guild = guild
        self.duration = duration

        # linked message in source guild
        self.link = None

        self.ended = False

        self.creator_role = None
        self.partygoer_role = None

    @property
    def general(self):
        return self.guild.text_channels[0]

    async def setup(self):
        # --- step 0.  set sane message notifications
        await self.bot.http.request(
            Route("PATCH", "/guilds/{guild_id}", guild_id=self.guild.id),
            json={"default_message_notifications": 1},
        )

        # --- step 1.  tweak base permissions
        perms = discord.Permissions()
        for sane_perm in PARTY_PERMISSIONS:
            setattr(perms, sane_perm, True)
        await self.guild.default_role.edit(permissions=perms)

        # --- step 2.  we need to be first
        await self.general.send("welcome to the party! \N{PARTY POPPER}")

        # --- step 3.  create party role for the creator
        self.creator_role = creator = await self.guild.create_role(
            name="party creator",
            color=discord.Color(0xff6666),
            hoist=True,
            mentionable=True,
            permissions=Permissions.all(),
        )

        # --- step 4.  partygoers need a role
        self.partygoer_role = partygoer = await self.guild.create_role(
            name="partygoer", color=discord.Color(0x66ccff), hoist=True
        )

        # --- step 5.  move roles
        await creator.edit(position=2)
        await partygoer.edit(position=1)

        # --- step 6.  add listeners
        self.bot.add_listener(self.handle_join, "on_member_join")

    async def end(self):
        self.bot.remove_listener(self.handle_join, "on_member_join")
        await self.guild.delete()
        await self.link.edit(content="party's over :(")
        self.ended = True

    async def handle_join(self, member: discord.Member):
        if member.guild != self.guild:
            return

        try:
            if member == self.creator:
                await member.add_roles(self.creator_role)
                await self.general.send(
                    f"welcome to your party, {member.mention}! you have admin btw"
                )
            else:
                await member.add_roles(self.partygoer_role)
        except discord.HTTPException:
            pass

    async def timer(self):
        await asyncio.sleep(self.duration - 10)
        await self.general.send("\N{ALARM CLOCK} 10 seconds left in this party @here")
        await asyncio.sleep(10)

    @classmethod
    async def create(cls, *, creator: discord.User, bot, session, duration):
        async with session.get(creator.avatar_url_as(format="png")) as avatar:
            avatar = await avatar.read()

        guild = await bot.create_guild(
            name=f"{creator.name}'s {choice(ADJECTIVES)} party", icon=avatar
        )

        await asyncio.sleep(2)

        # refresh from cache
        guild = bot.get_guild(guild.id)

        return cls(bot, creator, guild, duration)


class PartyCog(Cog):
    def __init__(self, bot):
        super().__init__(bot)
        self.parties = set()

    @group(invoke_without_command=True, enabled=False)
    @cooldown(1, 60, BucketType.guild)
    async def party(self, ctx: Context, dur_seconds: int = 5 * 60):
        """Creates a party."""
        if ctx.guild in map(lambda p: p.guild, self.parties):
            await ctx.send("parties can't be nested wtf")
            return

        if any(p.creator == ctx.author for p in self.parties):
            await ctx.send("you are already managing a party")
            return

        if dur_seconds < 20:
            await ctx.send("duration too short (min 20)")
            return

        progress = await ctx.send("creating a party...")

        try:
            party = await Party.create(
                creator=ctx.author,
                bot=self.bot,
                session=self.session,
                duration=dur_seconds,
            )
            party.link = progress

            self.parties.add(party)
        except discord.HTTPException:
            await progress.edit(content="can't throw party...")
            return

        try:
            await progress.edit(content="setting up...")
            await party.setup()

            invite = await party.general.create_invite()
            await progress.edit(content=f"let's have some fun!\n\n{invite}")

            await party.timer()
        finally:
            if not party.ended:
                await party.end()
                self.parties.remove(party)

    @party.command(name="end")
    async def party_end(self, ctx: Context):
        """Ends your party."""
        party = discord.utils.find(lambda p: p.creator == ctx.author, self.parties)
        if not party:
            await ctx.send("u don't have a party atm")
            return
        await party.end()
        self.parties.remove(party)
        await ctx.send("rip party...")


def setup(bot):
    bot.add_cog(PartyCog(bot))
