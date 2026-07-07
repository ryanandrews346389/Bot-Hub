import time
import random
import math

import discord
from discord import app_commands
from discord.ext import commands, tasks

import database

XP_PER_MESSAGE_MIN = 15
XP_PER_MESSAGE_MAX = 25
MESSAGE_COOLDOWN_SECONDS = 60
XP_PER_VOICE_MINUTE = 5


def xp_for_level(level: int) -> int:
    """XP required to reach a given level (simple quadratic curve)."""
    return 5 * (level ** 2) + 50 * level + 100


class Leveling(commands.Cog):
    """Chat + voice based XP and leveling system."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.voice_xp_task.start()
        self._voice_join_times = {}

    def cog_unload(self):
        self.voice_xp_task.cancel()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        row = database.ensure_level_row(message.guild.id, message.author.id)
        now = time.time()
        if now - (row["last_message_ts"] or 0) < MESSAGE_COOLDOWN_SECONDS:
            return

        gained = random.randint(XP_PER_MESSAGE_MIN, XP_PER_MESSAGE_MAX)
        new_xp = row["xp"] + gained
        new_level = row["level"]
        leveled_up = False
        while new_xp >= xp_for_level(new_level):
            new_xp -= xp_for_level(new_level)
            new_level += 1
            leveled_up = True

        database.execute(
            "UPDATE levels SET xp = ?, level = ?, last_message_ts = ? WHERE guild_id = ? AND user_id = ?",
            (new_xp, new_level, now, message.guild.id, message.author.id),
        )

        if leveled_up:
            await self._announce_level_up(message.guild, message.author, new_level, message.channel)

    async def _announce_level_up(self, guild, member, new_level, fallback_channel):
        config = database.get_guild_config(guild.id)
        channel = None
        if config["level_up_channel_id"]:
            channel = guild.get_channel(config["level_up_channel_id"])
        if channel is None:
            channel = fallback_channel
        try:
            await channel.send(f"🎉 {member.mention} just leveled up to **Level {new_level}**!")
        except discord.HTTPException:
            pass

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        key = (member.guild.id, member.id)
        if before.channel is None and after.channel is not None:
            self._voice_join_times[key] = time.time()
        elif before.channel is not None and after.channel is None:
            self._voice_join_times.pop(key, None)

    @tasks.loop(minutes=1)
    async def voice_xp_task(self):
        for guild in self.bot.guilds:
            for vc in guild.voice_channels:
                members = [m for m in vc.members if not m.bot]
                if len(members) < 2:
                    continue  # require at least 2 humans to earn voice XP (avoid AFK farming)
                for member in members:
                    row = database.ensure_level_row(guild.id, member.id)
                    new_xp = row["xp"] + XP_PER_VOICE_MINUTE
                    new_level = row["level"]
                    leveled_up = False
                    while new_xp >= xp_for_level(new_level):
                        new_xp -= xp_for_level(new_level)
                        new_level += 1
                        leveled_up = True
                    voice_seconds = row["voice_seconds"] + 60
                    database.execute(
                        "UPDATE levels SET xp = ?, level = ?, voice_seconds = ? WHERE guild_id = ? AND user_id = ?",
                        (new_xp, new_level, voice_seconds, guild.id, member.id),
                    )
                    if leveled_up:
                        text_channels = guild.text_channels
                        if text_channels:
                            await self._announce_level_up(guild, member, new_level, text_channels[0])

    @voice_xp_task.before_loop
    async def before_voice_xp_task(self):
        await self.bot.wait_until_ready()

    @app_commands.command(name="rank", description="Check your (or someone else's) level and XP")
    async def rank(self, interaction: discord.Interaction, member: discord.Member = None):
        member = member or interaction.user
        row = database.ensure_level_row(interaction.guild_id, member.id)
        needed = xp_for_level(row["level"])
        embed = discord.Embed(title=f"{member.display_name}'s Rank", color=discord.Color.green())
        embed.add_field(name="Level", value=str(row["level"]))
        embed.add_field(name="XP", value=f"{row['xp']} / {needed}")
        embed.add_field(name="Voice Time", value=f"{row['voice_seconds'] // 60} minutes")
        embed.set_thumbnail(url=member.display_avatar.url)
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Leveling(bot))
