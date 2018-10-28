import asyncio
import functools
from io import BytesIO

import discord
from lifesaver.utils.timing import Timer


def image_renderer(func):
    loop = asyncio.get_event_loop()

    @functools.wraps(func)
    async def wrapper(ctx, *args, **kwargs):
        image = await loop.run_in_executor(None, functools.partial(func, *args, **kwargs))

        def render():
            buffer = BytesIO()
            image.save(fp=buffer, format='png')
            buffer.seek(0)
            return buffer

        with Timer() as timer:
            buffer = await loop.run_in_executor(None, render)

        image.close()

        await ctx.send(
            f'Rendered in {timer}. ({image.width} \U000000d7 {image.height})',
            file=discord.File(buffer, 'image.png')
        )

    return wrapper


# http://jesselegg.com/archives/2009/09/5/simple-word-wrap-algorithm-pythons-pil/
def draw_word_wrap(draw, font, text, xpos=0, ypos=0, *, max_width, fill=(0, 0, 0)):
    """
    Draws text that automatically word wraps.

    Parameters
    ----------
    draw : PIL.ImageDraw.Draw
        The `ImageDraw.Draw` instance to draw with.
    font : PIL.ImageFont
    text
        The font to draw with.
    xpos : int
        The X position to start at.
    ypos : int
        The Y position to start at.
    max_width : int
        The maximum width allotted to draw text at before wrapping.
    fill : Tuple[int, int, int]
        The fill color.
    """
    text_size_x, text_size_y = draw.textsize(text, font=font)
    remaining = max_width
    output_text = []
    for word in text:
        letter_width, letter_height = draw.textsize(word, font=font)
        if letter_width > remaining:
            output_text.append(word)
            remaining = max_width - letter_width
        else:
            if not output_text:
                output_text.append(word)
            else:
                output = output_text.pop()
                output += word
                output_text.append(output)
            remaining -= letter_width
    for text in output_text:
        draw.text((xpos, ypos), text, font=font, fill=fill)
        ypos += text_size_y
