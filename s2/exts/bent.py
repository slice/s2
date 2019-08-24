import typing as T

import discord
import lifesaver


def ban_channel_for(guild: discord.Guild) -> T.Optional[discord.TextChannel]:
    """Return the ban echoing channel for a :class:`discord.Guild`."""
    return discord.utils.find(
        lambda channel: channel.topic is not None and "[s2:bent]" in channel.topic,
        guild.text_channels,
    )


class Bent(lifesaver.Cog):
    async def _report_bending(
        self, guild: discord.Guild, user: discord.abc.User, *, type: str
    ):
        channel = ban_channel_for(guild)
        if not channel:
            return
        await channel.send(f"***{user} got {type}***")

    @lifesaver.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, user: discord.abc.User):
        await self._report_bending(guild, user, type="bent")

    @lifesaver.Cog.listener()
    async def on_member_unban(self, guild: discord.Guild, user: discord.abc.User):
        await self._report_bending(guild, user, type="unbent")


def setup(bot):
    bot.add_cog(Bent(bot))
