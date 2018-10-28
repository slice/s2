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


def wrap_single_word(draw, font, word, *, max_width):
    chunks = []
    current_chunk = ''
    current_width = 0

    for letter in word:
        current_width += draw.textsize(letter, font=font)[0]
        current_chunk += letter

        if current_width > max_width:
            chunks.append(current_chunk)
            current_chunk = ''
            current_width = 0

    if current_chunk:
        chunks.append(current_chunk)

    return chunks


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
    total_width, line_height = draw.textsize(text, font=font)
    lines = []
    space_width = draw.textsize(' ', font=font)[0]
    remaining = max_width

    for word in text.split():
        word_width = draw.textsize(word, font=font)[0]

        if space_width + word_width > remaining:
            if word_width > max_width:
                # this word would wrap by itself. find the point where we can break the word itself
                lines += wrap_single_word(draw, font, word, max_width=max_width)
            else:
                # this word can't fit, start a new line
                lines.append(word)
            remaining = max_width - word_width
        else:
            if not lines:
                lines.append(word)
            else:
                # add this word to the last line
                new_line = lines.pop()
                new_line += ' ' + word
                lines.append(new_line)
            remaining -= word_width + space_width

    for text in lines:
        draw.text((xpos, ypos), text, font=font, fill=fill)
        ypos += line_height
