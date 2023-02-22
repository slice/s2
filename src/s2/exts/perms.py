import collections

import discord
import lifesaver
from discord.ext import commands
from lifesaver.utils import pluralize
from jishaku.paginators import PaginatorInterface

from s2.uploader import upload


def humanize_perm(perm: str) -> str:
    return perm.replace("_", " ").title().replace("Tts", "TTS")


def diff_markers(marker, iterable):
    return [f"{marker} {value}" for value in iterable]


def names_of_perms(perms: discord.Permissions, *, is_granted: bool = True):
    return {humanize_perm(name) for (name, value) in perms if value is is_granted}


def diff_perms(before: discord.Permissions, after: discord.Permissions) -> str:
    before_n = names_of_perms(before)
    after_n = names_of_perms(after)

    changes = (
        diff_markers("+", after_n - before_n)
        + diff_markers("-", before_n - after_n)
        + diff_markers(" ", before_n & after_n)
    )

    return changes


class Perms(lifesaver.Cog, name="Permissions"):
    @lifesaver.command(aliases=["flatten_roles"])
    @commands.has_permissions(manage_roles=True)
    @commands.guild_only()
    async def flatten_role(self, ctx: lifesaver.Context, *roles: discord.Role):
        """Makes a role purely cosmetic"""
        for role in roles:
            try:
                await role.edit(permissions=discord.Permissions.none())
                ctx += f"\N{MEMO} flattened {role.name}"
            except discord.HTTPException as err:
                ctx += f"\N{LOCK WITH INK PEN} unable to flatten {role.name}: {err}"
        await ctx.send_pages()

    @lifesaver.command()
    @commands.bot_has_permissions(manage_roles=True)
    @commands.has_permissions(manage_roles=True)
    @commands.guild_only()
    async def clean_roles(self, ctx: lifesaver.Context):
        """Removes useless permissions from roles"""
        everyone = ctx.guild.default_role

        pages = commands.Paginator(prefix="```diff", max_size=1000)
        interface = PaginatorInterface(ctx.bot, pages, owner=ctx.author)

        pages.add_line(
            "Removing unnecessary permission bits from all roles.", empty=True
        )
        await interface.send_to(ctx)

        def needs_cleaning(role):
            if role == everyone:
                return False

            has_duplicates = role.permissions.value & everyone.permissions.value != 0
            can_edit = role.position < ctx.guild.me.top_role.position

            return has_duplicates and can_edit

        cleanable_roles = [role for role in ctx.guild.roles if needs_cleaning(role)]

        if not cleanable_roles:
            await interface.add_line("No roles need tidying up!", empty=True)

        for role in cleanable_roles:
            perms = role.permissions

            # remove all permissions that are already inherited from the default
            # role
            cleaned = discord.Permissions(perms.value)
            cleaned.update(
                **{
                    name: False
                    for (name, value) in everyone.permissions
                    if getattr(perms, name) == value
                }
            )

            await interface.add_line(f"@@ {role.name}")
            await interface.add_line(
                f"--- {hex(perms.value)} \N{RIGHTWARDS ARROW} {hex(cleaned.value)}"
            )
            for change in diff_perms(perms, cleaned):
                await interface.add_line(change)
            await interface.add_line()

            try:
                await role.edit(permissions=cleaned)
                await interface.add_line("+ Successfully cleaned up role.", empty=True)
            except discord.HTTPException:
                await interface.add_line(
                    "- Failed to clean up role. (Likely a hierarchy problem.)",
                    empty=True,
                )

        await interface.add_line("Done!")

    @lifesaver.command(typing=True)
    @commands.has_permissions(manage_roles=True)
    @commands.guild_only()
    @commands.cooldown(1, 5, type=commands.BucketType.guild)
    async def lint_roles(self, ctx: lifesaver.Context):
        """Shows roles with useless permissions"""
        indent = " " * 2
        lint_results = collections.defaultdict(list)

        for role in ctx.guild.roles:
            if role == ctx.guild.default_role:
                continue

            if not role.members:
                lint_results[role.name].append("Nobody has this role.")

            for (perm, value) in role.permissions:
                default_perm = getattr(ctx.guild.default_role.permissions, perm)
                if default_perm and value:
                    description = f"{humanize_perm(perm)} is unnecessary."
                    lint_results[role.name].append(description)

        if not lint_results:
            await ctx.send("this server is flawless!")
            return

        output = ""
        for role_name, descriptions in lint_results.items():
            output += f"{role_name}\n"
            output += "\n".join(
                f"{indent} - {description}" for description in descriptions
            )
            output += "\n\n"

        link = await upload(output)
        roles = pluralize(role=len(lint_results))
        await ctx.send(f"{roles} are :( - {link}")

    @lifesaver.command()
    @commands.guild_only()
    async def perms(self, ctx: lifesaver.Context, target: discord.Member = None):
        """Shows a user's permissions"""
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


async def setup(bot):
    await bot.add_cog(Perms(bot))
