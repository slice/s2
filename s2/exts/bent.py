import typing

import discord
from lifesaver.bot import Cog


def ban_channel_for(guild: discord.Guild) -> typing.Optional[discord.TextChannel]:
    """Return the ban echoing channel for a :class:`discord.Guild`."""
    return discord.utils.find(
        lambda channel: channel.topic is not None and '[s2:bent]' in channel.topic,
        guild.text_channels,
    )


class Bent(Cog):
    async def on_member_ban(self, guild, user):
        channel = ban_channel_for(guild)
        if not channel:
            return
        await channel.send(f'***{user} got bent***')

    async def on_member_unban(self, guild, user):
        channel = ban_channel_for(guild)
        if not channel:
            return
        await channel.send(f'***{user} got unbent***')


def setup(bot):
    bot.add_cog(Bent(bot))
