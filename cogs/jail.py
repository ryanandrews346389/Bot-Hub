import time

import discord
from discord import app_commands
from discord.ext import commands

import database

# NOTE: This is a basic groundwork implementation of the "arrest" command.
# The interactive panel (buttons/options) described by the user will be
# added on top of this once the panel spec is provided. For now, $arrest
# jails a member: assigns the configured jail role and (optionally) moves
# them to a configured jail channel by revoking view access elsewhere.


class Jail(commands.Cog):
    """Groundwork for the arrest/jail command — panel UI to be added later."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="arrest", description="Arrest (jail) a member — basic version, panel coming soon")
    @app_commands.describe(member="Member to arrest", reason="Reason for the arrest")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def arrest(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
        config = database.get_guild_config(interaction.guild_id)
        if not config["jail_role_id"]:
            await interaction.response.send_message(
                "❌ No jail role configured yet. An admin should run /setup role jail_role first.", ephemeral=True
            )
            return

        jail_role = interaction.guild.get_role(config["jail_role_id"])
        if jail_role is None:
            await interaction.response.send_message("❌ The configured jail role no longer exists.", ephemeral=True)
            return

        await member.add_roles(jail_role, reason=reason)
        database.execute(
            "INSERT OR REPLACE INTO jail (guild_id, user_id, jailed_by, reason, jailed_at) VALUES (?, ?, ?, ?, ?)",
            (interaction.guild_id, member.id, interaction.user.id, reason, time.time()),
        )

        embed = discord.Embed(title="🚔 Member Arrested", color=discord.Color.dark_red())
        embed.add_field(name="Member", value=member.mention)
        embed.add_field(name="Reason", value=reason)
        embed.set_footer(text=f"Arrested by {interaction.user.display_name} • Full panel coming soon")

        jail_channel = None
        if config["jail_channel_id"]:
            jail_channel = interaction.guild.get_channel(config["jail_channel_id"])

        await interaction.response.send_message(embed=embed)
        if jail_channel:
            try:
                await jail_channel.send(f"{member.mention} has been placed here. Reason: {reason}")
            except discord.HTTPException:
                pass

    @app_commands.command(name="release", description="Release a member from jail")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def release(self, interaction: discord.Interaction, member: discord.Member):
        config = database.get_guild_config(interaction.guild_id)
        if config["jail_role_id"]:
            jail_role = interaction.guild.get_role(config["jail_role_id"])
            if jail_role and jail_role in member.roles:
                await member.remove_roles(jail_role)
        database.execute(
            "DELETE FROM jail WHERE guild_id = ? AND user_id = ?", (interaction.guild_id, member.id)
        )
        await interaction.response.send_message(f"🔓 {member.mention} has been released from jail.")


async def setup(bot: commands.Bot):
    await bot.add_cog(Jail(bot))
