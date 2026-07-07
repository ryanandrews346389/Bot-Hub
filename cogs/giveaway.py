import time
import random
import re

import discord
from discord import app_commands
from discord.ext import commands, tasks

import database


def parse_duration(duration_str: str) -> int:
    """Parse a string like '1h', '30m', '2d' into seconds."""
    match = re.match(r"^(\d+)([smhd])$", duration_str.strip().lower())
    if not match:
        raise ValueError("Duration must look like 30s, 10m, 2h, or 1d.")
    amount, unit = int(match.group(1)), match.group(2)
    multiplier = {"s": 1, "m": 60, "h": 3600, "d": 86400}[unit]
    return amount * multiplier


class GiveawayView(discord.ui.View):
    def __init__(self, giveaway_id: int):
        super().__init__(timeout=None)
        self.giveaway_id = giveaway_id
        self.enter_button.custom_id = f"giveaway_enter_{giveaway_id}"

    @discord.ui.button(label="🎉 Enter Giveaway", style=discord.ButtonStyle.success)
    async def enter_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        existing = database.execute(
            "SELECT * FROM giveaway_entries WHERE giveaway_id = ? AND user_id = ?",
            (self.giveaway_id, interaction.user.id),
            fetch="one",
        )
        if existing:
            await interaction.response.send_message("You've already entered this giveaway!", ephemeral=True)
            return
        database.execute(
            "INSERT INTO giveaway_entries (giveaway_id, user_id) VALUES (?, ?)",
            (self.giveaway_id, interaction.user.id),
        )
        await interaction.response.send_message("✅ You're entered! Good luck!", ephemeral=True)


class Giveaway(commands.Cog):
    """Giveaway system with button entry and automatic winner selection."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.check_giveaways.start()

    def cog_unload(self):
        self.check_giveaways.cancel()

    @app_commands.command(name="giveaway_start", description="Start a giveaway")
    @app_commands.describe(prize="What is being given away", duration="e.g. 30s, 10m, 2h, 1d", winners="Number of winners")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def giveaway_start(self, interaction: discord.Interaction, prize: str, duration: str, winners: app_commands.Range[int, 1, 20] = 1):
        try:
            seconds = parse_duration(duration)
        except ValueError as e:
            await interaction.response.send_message(f"❌ {e}", ephemeral=True)
            return

        end_time = time.time() + seconds
        config = database.get_guild_config(interaction.guild_id)
        channel = interaction.channel
        if config["giveaway_channel_id"]:
            configured = interaction.guild.get_channel(config["giveaway_channel_id"])
            if configured:
                channel = configured

        embed = discord.Embed(
            title="🎉 GIVEAWAY 🎉",
            description=f"**Prize:** {prize}\n**Winners:** {winners}\n**Ends:** <t:{int(end_time)}:R>\n\nClick the button below to enter!",
            color=discord.Color.magenta(),
        )
        embed.set_footer(text=f"Hosted by {interaction.user.display_name}")

        giveaway_id = database.execute(
            "INSERT INTO giveaways (guild_id, channel_id, message_id, prize, winners_count, end_time, host_id) VALUES (?, ?, 0, ?, ?, ?, ?)",
            (interaction.guild_id, channel.id, prize, winners, end_time, interaction.user.id),
        )
        row = database.execute(
            "SELECT giveaway_id FROM giveaways WHERE guild_id = ? ORDER BY giveaway_id DESC LIMIT 1",
            (interaction.guild_id,),
            fetch="one",
        )
        giveaway_id = row["giveaway_id"]

        view = GiveawayView(giveaway_id)
        message = await channel.send(embed=embed, view=view)
        database.execute(
            "UPDATE giveaways SET message_id = ? WHERE giveaway_id = ?", (message.id, giveaway_id)
        )

        if channel.id != interaction.channel.id:
            await interaction.response.send_message(f"✅ Giveaway started in {channel.mention}!", ephemeral=True)
        else:
            await interaction.response.send_message("✅ Giveaway started!", ephemeral=True)

    async def _end_giveaway(self, row):
        guild = self.bot.get_guild(row["guild_id"])
        if guild is None:
            return
        channel = guild.get_channel(row["channel_id"])
        entries = database.execute(
            "SELECT user_id FROM giveaway_entries WHERE giveaway_id = ?",
            (row["giveaway_id"],),
            fetch="all",
        )
        entrant_ids = [e["user_id"] for e in entries]
        database.execute("UPDATE giveaways SET ended = 1 WHERE giveaway_id = ?", (row["giveaway_id"],))

        if not entrant_ids:
            if channel:
                await channel.send(f"😢 No one entered the giveaway for **{row['prize']}**. No winners this time.")
            return

        winners_count = min(row["winners_count"], len(entrant_ids))
        winner_ids = random.sample(entrant_ids, winners_count)
        mentions = ", ".join(f"<@{uid}>" for uid in winner_ids)

        if channel:
            await channel.send(f"🎉 Congratulations {mentions}! You won **{row['prize']}**!")

    @tasks.loop(seconds=15)
    async def check_giveaways(self):
        due = database.execute(
            "SELECT * FROM giveaways WHERE ended = 0 AND end_time <= ?",
            (time.time(),),
            fetch="all",
        )
        for row in due:
            await self._end_giveaway(row)

    @check_giveaways.before_loop
    async def before_check_giveaways(self):
        await self.bot.wait_until_ready()

    @app_commands.command(name="giveaway_reroll", description="Reroll winners for the most recent giveaway in this channel")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def giveaway_reroll(self, interaction: discord.Interaction):
        row = database.execute(
            "SELECT * FROM giveaways WHERE channel_id = ? AND ended = 1 ORDER BY giveaway_id DESC LIMIT 1",
            (interaction.channel.id,),
            fetch="one",
        )
        if row is None:
            await interaction.response.send_message("No ended giveaway found in this channel.", ephemeral=True)
            return
        await interaction.response.send_message("🔁 Rerolling...")
        await self._end_giveaway(row)


async def setup(bot: commands.Bot):
    await bot.add_cog(Giveaway(bot))
