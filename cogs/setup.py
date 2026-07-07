import discord
from discord import app_commands
from discord.ext import commands

import database


class Setup(commands.Cog):
    """Admin commands for configuring the bot's channels and roles per server."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    setup_group = app_commands.Group(name="setup", description="Configure Discord Bot Hub 2 for this server")

    @setup_group.command(name="channel", description="Set a designated channel for a bot feature")
    @app_commands.describe(feature="Which feature to set the channel for", channel="The channel to use")
    @app_commands.choices(feature=[
        app_commands.Choice(name="confessions", value="confessions_channel_id"),
        app_commands.Choice(name="suggestions", value="suggestions_channel_id"),
        app_commands.Choice(name="birthdays", value="birthday_channel_id"),
        app_commands.Choice(name="giveaways", value="giveaway_channel_id"),
        app_commands.Choice(name="level_up_announcements", value="level_up_channel_id"),
        app_commands.Choice(name="jail", value="jail_channel_id"),
    ])
    @app_commands.checks.has_permissions(administrator=True)
    async def set_channel(self, interaction: discord.Interaction, feature: app_commands.Choice[str], channel: discord.TextChannel):
        database.set_guild_config_field(interaction.guild_id, feature.value, channel.id)
        await interaction.response.send_message(
            f"✅ Set **{feature.name}** channel to {channel.mention}.", ephemeral=True
        )

    @setup_group.command(name="role", description="Set a role used by the bot (mod, admin, or jail role)")
    @app_commands.describe(role_type="Which role to configure", role="The role to use")
    @app_commands.choices(role_type=[
        app_commands.Choice(name="mod_role", value="mod_role_id"),
        app_commands.Choice(name="admin_role", value="admin_role_id"),
        app_commands.Choice(name="jail_role", value="jail_role_id"),
    ])
    @app_commands.checks.has_permissions(administrator=True)
    async def set_role(self, interaction: discord.Interaction, role_type: app_commands.Choice[str], role: discord.Role):
        database.set_guild_config_field(interaction.guild_id, role_type.value, role.id)
        await interaction.response.send_message(
            f"✅ Set **{role_type.name}** to {role.mention}.", ephemeral=True
        )

    @setup_group.command(name="view", description="View the current bot configuration for this server")
    @app_commands.checks.has_permissions(administrator=True)
    async def view_config(self, interaction: discord.Interaction):
        row = database.get_guild_config(interaction.guild_id)
        embed = discord.Embed(title="⚙️ Server Configuration", color=discord.Color.blurple())
        fields = [
            ("Confessions channel", row["confessions_channel_id"]),
            ("Suggestions channel", row["suggestions_channel_id"]),
            ("Birthday channel", row["birthday_channel_id"]),
            ("Giveaway channel", row["giveaway_channel_id"]),
            ("Level-up channel", row["level_up_channel_id"]),
            ("Jail channel", row["jail_channel_id"]),
            ("Jail role", row["jail_role_id"]),
            ("Mod role", row["mod_role_id"]),
            ("Admin role", row["admin_role_id"]),
        ]
        for name, value in fields:
            display = f"<#{value}>" if value and "channel" in name.lower() else (f"<@&{value}>" if value else "Not set")
            embed.add_field(name=name, value=display, inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Setup(bot))
