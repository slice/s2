import discord
from discord.ext import commands
from lifesaver.bot import Cog, Context, command

from s2.uploader import upload


def humanize_perm(perm: str) -> str:
    return perm.replace("_", " ").title().replace("Tts", "TTS")


class Perms(Cog):
    @command(typing=True)
    @commands.has_permissions(manage_roles=True)
    @commands.guild_only()
    @commands.cooldown(1, 5, type=commands.BucketType.guild)
    async def role_lint(self, ctx: Context):
        """Shows roles with unnecessary permissions."""
        reports = []

        for role in ctx.guild.roles:
            if role == ctx.guild.default_role:
                continue

            for (perm, value) in role.permissions:
                default_perm = getattr(ctx.guild.default_role.permissions, perm)
                if default_perm and value:
                    reports.append({
                        'type': 'warning',
                        'message': f'"{role.name}" doesn\'t need {humanize_perm(perm)}.'
                    })

        output = ''
        for report in reports:
            output += '[{}] {}\n'.format(report['type'].upper(), report['message'])

        link = await upload(output)
        await ctx.send(f'linted: {len(reports)} report(s). {link}')

    @command()
    @commands.guild_only()
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
            title = humanize_perm(perm)
            if value:
                allowed.append(title)
            else:
                denied.append(title)

        embed.add_field(name="allowed", value="\n".join(allowed) or "<none>")
        embed.add_field(name="denied", value="\n".join(denied) or "<none>")

        await ctx.send(embed=embed)


def setup(bot):
    bot.add_cog(Perms(bot))
