from PIL import Image, ImageDraw, ImageFont
from discord.ext import commands
from lifesaver.bot import Cog, command

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


class ImgMod(Cog):
    @command(typing=True)
    @standard_cooldown
    async def discordlogo(self, ctx, *, text):
        """Generates a Discord logo"""
        if not text:
            await ctx.send('put something')
            return
        await render_discord_logo(ctx, text)

    @command(typing=True)
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
