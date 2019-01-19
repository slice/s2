from random import choice

from lifesaver.config import Config
from lifesaver.bot import Cog


class HouseConfig:
    slice_user_id: int = None
    house_guild_id: int = None
    emojis_channel_id: int = None


@Cog.with_config(HouseConfig)
class House(Cog):
    @property
    def slice(self):
        return self.bot.get_user(self.config.slice_user_id)

    @property
    def house(self):
        return self.bot.get_guild(self.config.house_guild_id)

    async def update_emoji_listing(self):
        channel = self.house.get_channel(self.config.emojis_channel_id)

        emojis = sorted(self.house.emojis, key=lambda emoji: emoji.name)
        descriptions = '\n'.join([
            f'{emoji}: `:{emoji.name}:`' for emoji in emojis
        ])
        messages = await channel.history(limit=1).flatten()

        if messages:
            # edit existing message
            await messages[0].edit(content=descriptions)
        else:
            await channel.send(descriptions)

        await channel.edit(topic=str(choice(self.house.emojis)))

    async def on_guild_update(self, before, after):
        if before != self.house or before.emojis == after.emojis:
            return

        await self.update_emoji_listing()

    async def on_member_update(self, before, after):
        if before != self.slice or before.avatar == after.avatar:
            return

        avatar_url = after.avatar_url_as(format='png', size=256)
        async with self.session.get(avatar_url) as resp:
            avatar_bytes = await resp.read()
            await self.house.edit(avatar=avatar_bytes, reason="slice changed his avatar")
