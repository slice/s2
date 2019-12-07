__all__ = ["S2Help"]

import itertools

from discord.ext import commands


class S2Help(commands.DefaultHelpCommand):
    async def send_bot_help(self, mapping):
        # this implementation is copied directly from the library source code,
        # but slightly modified in order to remove category headers and stuff
        # every command into the same category for aesthetic purposes.

        ctx = self.context
        bot = ctx.bot

        if bot.description:
            # <description> portion
            self.paginator.add_line(bot.description, empty=True)

        no_category = "\u200b{0.no_category}:".format(self)

        def get_category(command, *, no_category=no_category):
            return no_category

        filtered = await self.filter_commands(bot.commands, sort=True, key=get_category)
        max_size = self.get_max_size(filtered)
        to_iterate = itertools.groupby(filtered, key=get_category)

        # Now we can add the commands to the page.
        for category, commands in to_iterate:
            commands = (
                sorted(commands, key=lambda c: c.name)
                if self.sort_commands
                else list(commands)
            )
            self.add_indented_commands(commands, heading=category, max_size=max_size)

        note = self.get_ending_note()
        if note:
            self.paginator.add_line()
            self.paginator.add_line(note)

        await self.send_pages()

    def get_ending_note(self) -> str:
        ending_note = super().get_ending_note()
        return ending_note.splitlines()[0]
