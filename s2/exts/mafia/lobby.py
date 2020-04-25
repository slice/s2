__all__ = ["LobbyMenu"]

from typing import cast, TYPE_CHECKING

import discord
import lifesaver
from discord.ext import menus
from lifesaver.utils import pluralize

from .formatting import user_listing

if TYPE_CHECKING:
    from .game import MafiaGame


class LobbyMenu(menus.Menu):
    JOIN_EMOJI = "\N{RAISED HAND}"

    def __init__(self, game: "MafiaGame", minimum_players: int = 4, **kwargs) -> None:
        super().__init__(timeout=None, **kwargs)
        self.game = game
        self.minimum_players = minimum_players
        self.was_cancelled = False

    def _still_needed(self) -> int:
        return self.minimum_players - len(self.game.participants)

    def _embed(self) -> discord.Embed:
        players_listing = user_listing(self.game.participants)
        embed = discord.Embed(
            title="Mafia Lobby", description=players_listing, color=discord.Color.red()
        )
        embed.set_author(
            name=str(self.game.creator), icon_url=self.game.creator.avatar_url
        )

        if (still_needed := self._still_needed()) > 0:
            players = pluralize(player=still_needed, with_indicative=True)
            embed.set_footer(text=f"{players} still needed")

        return embed

    async def _update_embed(self) -> None:
        await self.message.edit(embed=self._embed())

    async def send_initial_message(self, ctx, channel) -> None:
        content = (
            f"React with {self.JOIN_EMOJI} to join!\n"
            "If you don't know how to play Mafia, type "
            f"`{ctx.prefix}help mafia` to have me DM you a tutorial! \N{HOCHO}"
        )

        return await channel.send(content, embed=self._embed())

    @menus.button(JOIN_EMOJI)
    async def on_player_movement(self, payload: discord.RawReactionActionEvent) -> None:
        ctx = cast(lifesaver.Context, self.ctx)
        guild = cast(discord.Guild, ctx.guild)
        member = cast(discord.Member, guild.get_member(payload.user_id))

        if payload.event_type == "REACTION_REMOVE":
            if member == self.game.creator:
                # creator can't leave the lobby
                return

            try:
                self.game.participants.remove(member)
            except KeyError:
                pass
            else:
                await self._update_embed()
            return

        self.game.participants.add(member)

        await self._update_embed()

        if self._still_needed() < 1:
            # add the start button
            await self.add_button(
                menus.Button("\N{WHITE HEAVY CHECK MARK}", action=self.on_start),
                react=True,
            )

    @menus.button("\N{CROSS MARK}")
    async def on_cancel(self, payload: discord.RawReactionActionEvent) -> None:
        if payload.user_id != self.game.creator.id:
            return
        self.was_cancelled = True
        self.stop()

    async def on_start(self, payload: discord.RawReactionActionEvent) -> None:
        self.stop()

    def reaction_check(self, payload: discord.RawReactionActionEvent) -> bool:
        if (member := payload.member) is not None and member.bot:
            return False
        return payload.message_id == self.message.id and payload.emoji in self.buttons
