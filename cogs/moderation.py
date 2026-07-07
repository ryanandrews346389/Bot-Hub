import time

import discord
from discord import app_commands
from discord.ext import commands

import database


class Moderation(commands.Cog):
    """Kick, ban, timeout, purge, and warn commands."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="kick", description="Kick a member from the server")
    @app_commands.describe(member="Member to kick", reason="Reason for the kick")
    @app_commands.checks.has_permissions(kick_members=True)
    async def kick(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
        await member.kick(reason=reason)
        embed = discord.Embed(title="👢 Member Kicked", color=discord.Color.orange())
        embed.add_field(name="Member", value=member.mention)
        embed.add_field(name="Reason", value=reason)
        embed.set_footer(text=f"Kicked by {interaction.user}")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="ban", description="Ban a member from the server")
    @app_commands.describe(member="Member to ban", reason="Reason for the ban")
    @app_commands.checks.has_permissions(ban_members=True)
    async def ban(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
        await member.ban(reason=reason)
        embed = discord.Embed(title="🔨 Member Banned", color=discord.Color.red())
        embed.add_field(name="Member", value=member.mention)
        embed.add_field(name="Reason", value=reason)
        embed.set_footer(text=f"Banned by {interaction.user}")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="timeout", description="Timeout (mute) a member for a number of minutes")
    @app_commands.describe(member="Member to timeout", minutes="Duration in minutes", reason="Reason for the timeout")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def timeout(self, interaction: discord.Interaction, member: discord.Member, minutes: int, reason: str = "No reason provided"):
        duration = discord.utils.utcnow() + discord.utils.timedelta(minutes=minutes)
        await member.timeout(duration, reason=reason)
        embed = discord.Embed(title="🔇 Member Timed Out", color=discord.Color.dark_orange())
        embed.add_field(name="Member", value=member.mention)
        embed.add_field(name="Duration", value=f"{minutes} minute(s)")
        embed.add_field(name="Reason", value=reason)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="untimeout", description="Remove a member's timeout")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def untimeout(self, interaction: discord.Interaction, member: discord.Member):
        await member.timeout(None)
        await interaction.response.send_message(f"✅ Removed timeout for {member.mention}.")

    @app_commands.command(name="purge", description="Delete a number of recent messages in this channel")
    @app_commands.describe(amount="Number of messages to delete (max 100)")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def purge(self, interaction: discord.Interaction, amount: app_commands.Range[int, 1, 100]):
        await interaction.response.defer(ephemeral=True)
        deleted = await interaction.channel.purge(limit=amount)
        await interaction.followup.send(f"🧹 Deleted {len(deleted)} messages.", ephemeral=True)

    @app_commands.command(name="warn", description="Warn a member")
    @app_commands.describe(member="Member to warn", reason="Reason for the warning")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def warn(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
        database.execute(
            "INSERT INTO warnings (guild_id, user_id, moderator_id, reason, created_at) VALUES (?, ?, ?, ?, ?)",
            (interaction.guild_id, member.id, interaction.user.id, reason, time.time()),
        )
        count = database.execute(
            "SELECT COUNT(*) as c FROM warnings WHERE guild_id = ? AND user_id = ?",
            (interaction.guild_id, member.id),
            fetch="one",
        )["c"]
        embed = discord.Embed(title="⚠️ Member Warned", color=discord.Color.yellow())
        embed.add_field(name="Member", value=member.mention)
        embed.add_field(name="Reason", value=reason)
        embed.add_field(name="Total Warnings", value=str(count))
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="warnings", description="View a member's warnings")
    async def warnings(self, interaction: discord.Interaction, member: discord.Member):
        rows = database.execute(
            "SELECT * FROM warnings WHERE guild_id = ? AND user_id = ? ORDER BY created_at DESC LIMIT 10",
            (interaction.guild_id, member.id),
            fetch="all",
        )
        if not rows:
            await interaction.response.send_message(f"{member.mention} has no warnings.", ephemeral=True)
            return
        embed = discord.Embed(title=f"Warnings for {member.display_name}", color=discord.Color.yellow())
        for row in rows:
            embed.add_field(
                name=f"Warning #{row['warning_id']}",
                value=f"Reason: {row['reason']}\nBy: <@{row['moderator_id']}>",
                inline=False,
            )
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Moderation(bot))
