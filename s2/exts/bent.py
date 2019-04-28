import typing

import discord
import lifesaver


def ban_channel_for(guild: discord.Guild) -> typing.Optional[discord.TextChannel]:
    """Return the ban echoing channel for a :class:`discord.Guild`."""
    return discord.utils.find(
        lambda channel: channel.topic is not None and '[s2:bent]' in channel.topic,
        guild.text_channels,
    )


class Bent(lifesaver.Cog):
    @lifesaver.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, user: typing.Union[discord.User, discord.Member]):
        channel = ban_channel_for(guild)
        if not channel:
            return
        await channel.send(f'***{user} got bent***')

    @lifesaver.Cog.listener()
    async def on_member_unban(self, guild: discord.Guild, user: typing.Union[discord.User, discord.Member]):
        channel = ban_channel_for(guild)
        if not channel:
            return
        await channel.send(f'***{user} got unbent***')


def setup(bot):
    bot.add_cog(Bent(bot))
