import datetime
import discord
from discord.ext import commands

import pylast
import lifesaver
from lifesaver.utils.formatting import human_delta

LASTFM_COLOR = discord.Color(0xB90000)


class LastFMConfig(lifesaver.config.Config):
    name: str
    api_key: str
    api_secret: str
    registered_to: str


class LastFMUser(commands.Converter):
    async def convert(self, ctx, argument):
        cog = ctx.command.cog

        info = await ctx.bot.loop.run_in_executor(None, cog.get_info, argument)
        if not info:
            raise commands.BadArgument("User not found.")

        return info


@lifesaver.Cog.with_config(LastFMConfig)
class LastFM(lifesaver.Cog, name="Last.fm"):
    def __init__(self, bot, *args, **kwargs):
        super().__init__(bot, *args, **kwargs)

        self.last_fm = pylast.LastFMNetwork(
            api_key=self.config.api_key, api_secret=self.config.api_secret,
        )

    def get_info(self, username):
        user = self.last_fm.get_user(username)

        if not user:
            return None

        tracks = user.get_recent_tracks()
        playcount = user.get_playcount()
        now_playing = user.get_now_playing()
        top_tracks = user.get_top_tracks(limit=5)

        return {
            "user": user,
            "tracks": tracks,
            "playcount": playcount,
            "now_playing": now_playing,
            "top_tracks": top_tracks,
        }

    @lifesaver.group(
        name="last_fm",
        aliases=["lfm", "last.fm"],
        typing=True,
        invoke_without_command=True,
    )
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def last_fm_command(self, ctx, user: LastFMUser):
        """Shows last.fm info."""

        def format_played_track(played_track):
            timestamp = datetime.datetime.utcfromtimestamp(int(played_track.timestamp))
            delta = human_delta(timestamp) + " ago"
            track = played_track.track
            return format_track(track) + f" ({delta})"

        def format_track(track):
            return discord.utils.escape_markdown(
                f"{track.artist} \N{em dash} {track.title}"
            )

        tracks = "\n".join(format_played_track(track) for track in user["tracks"][:5])

        embed = discord.Embed(
            title=f'@{user["user"].get_name()}',
            url=user["user"].get_url(),
            color=LASTFM_COLOR,
            description=f'Listened to {user["playcount"]:,} tracks in total.',
        )

        if user["now_playing"]:
            embed.add_field(
                name="Currently Listening To",
                value=format_track(user["now_playing"]),
                inline=False,
            )

        embed.add_field(
            name="Recently Played Tracks", value=tracks or "No tracks scrobbled."
        )
        await ctx.send(embed=embed)

    @last_fm_command.command(aliases=["fav", "favs"], typing=True)
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def favorites(self, ctx, user: LastFMUser):
        """Shows a user's favorite tracks."""

        def format_item(item):
            track = item.item
            track_description = discord.utils.escape_markdown(
                f"{track.artist} \N{em dash} {track.title}"
            )
            return f"{track_description} ({item.weight} plays)"

        favs = "\n".join(format_item(fav) for fav in user["top_tracks"])

        embed = discord.Embed(
            title=f'@{user["user"].get_name()}',
            url=user["user"].get_url(),
            color=LASTFM_COLOR,
        )
        embed.add_field(
            name="Most Played Tracks of All Time", value=favs,
        )
        await ctx.send(embed=embed)


def setup(bot):
    bot.add_cog(LastFM(bot))
