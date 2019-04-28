from io import BytesIO
from random import choice

import discord
import lifesaver
from discord.ext import commands
from jishaku.functools import executor_function
from PIL import Image


class HouseConfig(lifesaver.config.Config):
    slice_user_id: int = None
    house_guild_id: int = None
    emojis_channel_id: int = None


@executor_function
def flip_avatar(buffer):
    with Image.open(buffer) as image:
        image = image.transpose(Image.FLIP_TOP_BOTTOM)
        image.save(buffer, 'png')

    buffer.seek(0)


@lifesaver.Cog.with_config(HouseConfig)
class House(lifesaver.Cog):
    @property
    def slice(self):
        return self.bot.get_user(self.config.slice_user_id)

    @property
    def house(self):
        return self.bot.get_guild(self.config.house_guild_id)

    @lifesaver.command()
    @commands.is_owner()
    async def update_listing(self, ctx: lifesaver.Context):
        """Manually updates the emoji listing"""
        await self.update_emoji_listing()
        await ctx.ok()

    @lifesaver.command()
    @commands.is_owner()
    async def update_icon(self, ctx: lifesaver.Context):
        """Manually updates the guild icon"""
        await self.update_guild_icon(ctx.author)
        await ctx.ok()

    @lifesaver.command(name='disguise')
    @commands.is_owner()
    async def disguise_command(self, ctx: lifesaver.Context, target: discord.Member = None):
        """Steal someone's avatar"""
        target = target or ctx.author
        await self.steal_avatar(target)
        await ctx.ok()

    async def steal_avatar(self, member):
        avatar = member.avatar_url_as(format='png', size=256)
        with BytesIO() as buffer:
            await avatar.save(buffer, seek_begin=True)
            flipped_bytes = await flip_avatar(buffer)
            await self.bot.user.edit(avatar=flipped_bytes.getvalue())

    async def update_emoji_listing(self):
        """Update the emoji listing in the #emojis channel."""
        channel = self.house.get_channel(self.config.emojis_channel_id)

        emojis = sorted(self.house.emojis, key=lambda emoji: emoji.name)
        descriptions = '\n'.join([
            f'{emoji} `:{emoji.name}:`' for emoji in emojis
        ])
        messages = await channel.history(limit=1).flatten()

        if messages:
            # edit existing message
            await messages[0].edit(content=descriptions)
        else:
            await channel.send(descriptions)

        await channel.edit(topic=str(choice(self.house.emojis)))

    async def update_guild_icon(self, slice):
        """Update the guild icon to slice's avatar."""
        avatar_url = slice.avatar_url_as(format='png', size=256)

        async with self.session.get(str(avatar_url)) as resp:
            avatar_bytes = await resp.read()
            await self.house.edit(icon=avatar_bytes, reason='slice changed his avatar')

    @lifesaver.Cog.listener()
    async def on_guild_emojis_update(self, guild, before, after):
        self.log.debug('processing guild emoji update %d', guild.id)

        if guild != self.house:
            return

        self.log.debug('automatically updating emoji listing')
        await self.update_emoji_listing()

    @lifesaver.Cog.listener()
    async def on_user_update(self, before, after):
        if before != self.slice or before.avatar == after.avatar:
            return

        self.log.debug('automatically updating guild icon')
        await self.update_guild_icon(after)

        self.log.debug('automatically stealing avatar')
        await self.steal_avatar(after)


def setup(bot):
    bot.add_cog(House(bot))
