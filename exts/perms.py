import discord
from lifesaver.bot import Cog, command, Context


class Perms(Cog):
    @command()
    async def perms(self, ctx: Context, target: discord.Member = None):
        """Shows permissions for a user."""
        target = target or ctx.author
        perms = target.guild_permissions
        embed = discord.Embed()
        allowed = []
        denied = []

        for perm in dir(perms):
            if "__" in perm:
                continue
            value = getattr(perms, perm, None)
            if not isinstance(value, bool):
                continue
            title = perm.replace("_", " ").title()
            if value:
                allowed.append(title)
            else:
                denied.append(title)

        embed.add_field(name="Allowed", value="\n".join(allowed) or "<none>")
        embed.add_field(name="Denied", value="\n".join(denied) or "<none>")

        await ctx.send(embed=embed)


def setup(bot):
    bot.add_cog(Perms(bot))
