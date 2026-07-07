import discord
from discord import app_commands
from discord.ext import commands

import database


class Leaderboard(commands.Cog):
    """Leaderboards for XP/level, richest members, and fight wins."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _build_embed(self, interaction, title, rows, value_fn):
        embed = discord.Embed(title=title, color=discord.Color.teal())
        if not rows:
            embed.description = "No data yet."
            return embed
        lines = []
        medals = ["🥇", "🥈", "🥉"]
        for i, row in enumerate(rows):
            member = interaction.guild.get_member(row["user_id"])
            name = member.display_name if member else f"User {row['user_id']}"
            prefix = medals[i] if i < 3 else f"{i + 1}."
            lines.append(f"{prefix} **{name}** — {value_fn(row)}")
        embed.description = "\n".join(lines)
        return embed

    @app_commands.command(name="leaderboard_xp", description="Top members by level/XP")
    async def leaderboard_xp(self, interaction: discord.Interaction):
        rows = database.execute(
            "SELECT * FROM levels WHERE guild_id = ? ORDER BY level DESC, xp DESC LIMIT 10",
            (interaction.guild_id,),
            fetch="all",
        )
        embed = await self._build_embed(
            interaction, "🏆 XP Leaderboard", rows, lambda r: f"Level {r['level']} ({r['xp']} XP)"
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="leaderboard_richest", description="Top richest members")
    async def leaderboard_richest(self, interaction: discord.Interaction):
        rows = database.execute(
            "SELECT *, (balance + bank) as total FROM economy WHERE guild_id = ? ORDER BY total DESC LIMIT 10",
            (interaction.guild_id,),
            fetch="all",
        )
        embed = await self._build_embed(
            interaction, "💰 Richest Members", rows, lambda r: f"{r['total']} coins"
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="leaderboard_fights", description="Top members by fight wins")
    async def leaderboard_fights(self, interaction: discord.Interaction):
        rows = database.execute(
            "SELECT * FROM economy WHERE guild_id = ? ORDER BY wins DESC LIMIT 10",
            (interaction.guild_id,),
            fetch="all",
        )
        embed = await self._build_embed(
            interaction, "⚔️ Top Fighters", rows, lambda r: f"{r['wins']} wins / {r['losses']} losses"
        )
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Leaderboard(bot))
