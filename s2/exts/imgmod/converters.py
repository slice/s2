import itertools

import discord
from discord.ext import commands


class TierList(commands.Converter):
    async def convert(self, ctx, argument):
        parts = argument.split(':')

        if len(parts) != 2:
            raise commands.BadArgument('invalid tier group: invalid separation?')

        name, people_desc = parts

        people = people_desc.split(',')

        if people == '':
            raise commands.BadArgument('invalid tier group: no users?')

        async def resolve_user(desc):
            if desc == '$everyone':
                return ctx.guild.members
            if desc.startswith('&'):
                role = discord.utils.get(ctx.guild.roles, name=desc[1:])
                if role:
                    return role.members
            return [await commands.MemberConverter().convert(ctx, desc)]

        users = list(itertools.chain.from_iterable([
            await resolve_user(desc)
            for desc in people
        ]))

        if len(users) > 50:
            raise commands.BadArgument(
                f'invalid tier group: max of 50 users (there are {len(users)})'
            )

        return {
            'name': name,
            'users': users,
        }
