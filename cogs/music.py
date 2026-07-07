import asyncio
import functools

import discord
from discord import app_commands
from discord.ext import commands
import yt_dlp as youtube_dl

YTDL_OPTS = {
    "format": "bestaudio/best",
    "noplaylist": True,
    "quiet": True,
    "default_search": "ytsearch",
    "source_address": "0.0.0.0",
}

FFMPEG_OPTS = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options": "-vn",
}

ytdl = youtube_dl.YoutubeDL(YTDL_OPTS)


class GuildMusicState:
    def __init__(self):
        self.queue = []
        self.current = None
        self.voice_client: discord.VoiceClient = None


class Music(commands.Cog):
    """Play music in voice channels from YouTube search/links."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.states = {}

    def get_state(self, guild_id) -> GuildMusicState:
        if guild_id not in self.states:
            self.states[guild_id] = GuildMusicState()
        return self.states[guild_id]

    async def _extract(self, query):
        loop = asyncio.get_event_loop()
        func = functools.partial(ytdl.extract_info, query, download=False)
        data = await loop.run_in_executor(None, func)
        if "entries" in data:
            data = data["entries"][0]
        return data

    def _play_next(self, guild_id):
        state = self.get_state(guild_id)
        if not state.queue:
            state.current = None
            return
        next_track = state.queue.pop(0)
        state.current = next_track
        source = discord.FFmpegPCMAudio(next_track["url"], **FFMPEG_OPTS)
        state.voice_client.play(
            source, after=lambda e: self._play_next(guild_id)
        )

    @app_commands.command(name="play", description="Play a song from YouTube (link or search terms)")
    @app_commands.describe(query="YouTube link or search terms")
    async def play(self, interaction: discord.Interaction, query: str):
        if interaction.user.voice is None or interaction.user.voice.channel is None:
            await interaction.response.send_message("❌ You need to be in a voice channel first.", ephemeral=True)
            return

        await interaction.response.defer()
        state = self.get_state(interaction.guild_id)

        if state.voice_client is None or not state.voice_client.is_connected():
            state.voice_client = await interaction.user.voice.channel.connect()

        try:
            data = await self._extract(query)
        except Exception as e:
            await interaction.followup.send(f"❌ Couldn't find/play that: {e}")
            return

        track = {"title": data.get("title", "Unknown title"), "url": data["url"], "webpage_url": data.get("webpage_url", "")}
        state.queue.append(track)

        if not state.voice_client.is_playing() and state.current is None:
            self._play_next(interaction.guild_id)
            await interaction.followup.send(f"▶️ Now playing: **{track['title']}**")
        else:
            await interaction.followup.send(f"➕ Added to queue: **{track['title']}**")

    @app_commands.command(name="skip", description="Skip the current song")
    async def skip(self, interaction: discord.Interaction):
        state = self.get_state(interaction.guild_id)
        if state.voice_client and state.voice_client.is_playing():
            state.voice_client.stop()
            await interaction.response.send_message("⏭️ Skipped.")
        else:
            await interaction.response.send_message("❌ Nothing is playing.", ephemeral=True)

    @app_commands.command(name="pause", description="Pause the current song")
    async def pause(self, interaction: discord.Interaction):
        state = self.get_state(interaction.guild_id)
        if state.voice_client and state.voice_client.is_playing():
            state.voice_client.pause()
            await interaction.response.send_message("⏸️ Paused.")
        else:
            await interaction.response.send_message("❌ Nothing is playing.", ephemeral=True)

    @app_commands.command(name="resume", description="Resume the paused song")
    async def resume(self, interaction: discord.Interaction):
        state = self.get_state(interaction.guild_id)
        if state.voice_client and state.voice_client.is_paused():
            state.voice_client.resume()
            await interaction.response.send_message("▶️ Resumed.")
        else:
            await interaction.response.send_message("❌ Nothing is paused.", ephemeral=True)

    @app_commands.command(name="stop", description="Stop music and clear the queue")
    async def stop(self, interaction: discord.Interaction):
        state = self.get_state(interaction.guild_id)
        state.queue.clear()
        if state.voice_client:
            state.voice_client.stop()
            await state.voice_client.disconnect()
            state.voice_client = None
        await interaction.response.send_message("⏹️ Stopped and disconnected.")

    @app_commands.command(name="queue", description="View the current music queue")
    async def queue_cmd(self, interaction: discord.Interaction):
        state = self.get_state(interaction.guild_id)
        if not state.current and not state.queue:
            await interaction.response.send_message("The queue is empty.", ephemeral=True)
            return
        lines = []
        if state.current:
            lines.append(f"**Now Playing:** {state.current['title']}")
        for i, t in enumerate(state.queue, start=1):
            lines.append(f"{i}. {t['title']}")
        await interaction.response.send_message("\n".join(lines))


async def setup(bot: commands.Bot):
    await bot.add_cog(Music(bot))
