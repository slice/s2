import itertools
import io

import discord
import lifesaver
from PIL import Image, ImageDraw, ImageFont
from discord.ext import commands

from .converters import TierList
from .utils import image_renderer, draw_word_wrap

standard_cooldown = commands.cooldown(1, 3, commands.BucketType.user)

brain_heights = [
    155,
    181,
    188,
    165,
    179,
    190,
    210,
    194,
]

tier_colors = [
    (255, 127, 127),
    (255, 191, 127),
    (255, 223, 127),
    (255, 255, 127),
    (191, 255, 127),
    (127, 255, 127),
    (127, 255, 255),
    (127, 191, 255),
    (127, 127, 255),
    (255, 127, 255),
]

@image_renderer
def render_spark_joy(bad, good):
    image = Image.open('assets/spark_joy.jpg')
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype('assets/Arial_Regular.ttf', 32)

    draw_word_wrap(draw, font, bad, 500, 26, max_width=472)
    draw_word_wrap(draw, font, good, 500, 510, max_width=472)

    del draw
    return image


@image_renderer
def render_tier_list(groups, avatars):
    border = 2
    avatar_size = 64
    row_height = border + avatar_size
    image_height = len(groups) * row_height
    name_padding = 20

    font = ImageFont.truetype('assets/Arial_Regular.ttf', 16)
    image = Image.new('RGB', (10, image_height), (49, 52, 58))
    draw = ImageDraw.Draw(image)

    # calculate the true width of the image based on the longest name provided
    longest_name = max(groups, key=lambda group: len(group['name']))['name']
    longest_users = len(max(groups, key=lambda group: len(group['users']))['users'])
    longest_name_size = draw.textsize(longest_name, font)
    names_width = longest_name_size[0] + (name_padding * 2) + border
    image_width = names_width + max(avatar_size * 8, longest_users * (avatar_size - 5) + 5)
    image = image.resize((image_width, image_height))

    # make a new imagedraw for the new image
    del draw
    draw = ImageDraw.Draw(image)

    for index, group in enumerate(list(groups)):
        print(f'index: {index}, group: {group}')
        y = row_height * index

        # draw group fill
        draw.rectangle(
            [(0, y), (names_width - border, y + row_height - border)],
            fill=tier_colors[index % len(tier_colors)],
        )

        # draw group name
        draw.text(
            (name_padding, y + (row_height / 2) - (longest_name_size[1] / 2)),
            group['name'], (0, 0, 0), font
        )

        # draw bottom border
        bottom_border_y = y + row_height - border
        draw.line(
            [(0, bottom_border_y), (image_width, bottom_border_y)],
            fill=(0, 0, 0), width=border,
        )

        # draw chat background border
        draw.line(
            [(names_width, bottom_border_y), (image_width, bottom_border_y)],
            fill=(42, 45, 50), width=border,
        )

        for user_index, user in enumerate(group['users']):
            avatar = Image.open(fp=io.BytesIO(avatars[user.id]))\
                .convert('RGBA')\
                .resize((avatar_size - 10, avatar_size - 10), resample=Image.BICUBIC)

            avatar_offset = user_index * (avatar_size - 5)
            avatar_x = names_width + avatar_offset + 5
            avatar_y = y + 5

            with avatar:
                image.paste(avatar, (avatar_x, avatar_y), avatar,)

    # draw border between names and users
    draw.line(
        [(names_width - border, 0), (names_width - border, image_height)],
        fill=(0, 0, 0), width=border,
    )

    del draw
    return image


@image_renderer
def render_brain_meme(stages):
    font = ImageFont.truetype('assets/Arial_Regular.ttf', 32)
    base = Image.open('assets/brain_meme.png')

    # resize the image to fit the number of stages
    image_height = sum(brain_heights[:len(stages)])
    base = base.crop((0, 0, 599, image_height))

    draw = ImageDraw.Draw(base)
    margin = 10

    for index, stage in enumerate(stages):
        x_pos = margin
        y_pos = sum(brain_heights[:index]) + margin
        draw_word_wrap(draw, font, stage, x_pos, y_pos, max_width=300 - margin * 2)

    del draw
    return base


@image_renderer
def render_discord_logo(text: str):
    font = ImageFont.truetype('assets/Uni_Sans_Heavy.otf', 125)
    base = Image.open('assets/discord_logo.png')
    draw = ImageDraw.Draw(base)

    text_size = draw.textsize(text, font)

    if 323 + text_size[0] > base.width:
        new_base = Image.new(base.mode, (323 + text_size[0], base.height))
        new_base.paste(base, None, base)

        base.close()

        del draw
        draw = ImageDraw.Draw(new_base)
        draw.text((323, 90), text, (255, 255, 255), font=font)
        return new_base
    else:
        draw.text((323, 90), text, (255, 255, 255), font=font)
        del draw
        return base


class ImgMod(lifesaver.Cog, name='Image manipulations'):
    @lifesaver.command(typing=True, hidden=True, enabled=False)
    @standard_cooldown
    async def discordlogo(self, ctx, *, text):
        """Generates a Discord logo"""
        if not text:
            await ctx.send('put something')
            return
        await render_discord_logo(ctx, text)

    @lifesaver.command(typing=True)
    @standard_cooldown
    async def joy(self, ctx, bad, *, good):
        """This one sparks joy."""
        await render_spark_joy(ctx, bad, good)

    @lifesaver.command(typing=True, hidden=True)
    @commands.guild_only()
    @standard_cooldown
    async def tierlist(self, ctx, *groups: TierList):
        """Generates a tier list of your friends"""
        if not groups:
            await ctx.send("can't make a tier list outta nothing bud")
            return

        users = itertools.chain.from_iterable([group['users'] for group in groups])
        avatars = {}
        for user in set(users):
            avatar = user.avatar_url_as(format='png', static_format='png', size=64)
            async with self.session.get(str(avatar)) as resp:
                avatars[user.id] = await resp.read()

        await render_tier_list(ctx, groups, avatars)

    @lifesaver.command(typing=True)
    @standard_cooldown
    async def brainmeme(self, ctx, *stages):
        """Generates a brain meme"""
        if not stages:
            await ctx.send('put something')
            return
        if len(stages) > 8:
            await ctx.send('too many stages')
            return
        await render_brain_meme(ctx, stages)


def setup(bot):
    bot.add_cog(ImgMod(bot))
