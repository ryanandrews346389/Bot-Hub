import time

import discord
from discord import app_commands
from discord.ext import commands

import database


class SuggestionModerationView(discord.ui.View):
    def __init__(self, suggestion_id: int):
        super().__init__(timeout=None)
        self.suggestion_id = suggestion_id

    @discord.ui.button(label="✅ Approve", style=discord.ButtonStyle.success, custom_id="suggestion_approve")
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._update_status(interaction, "approved", discord.Color.green())

    @discord.ui.button(label="❌ Deny", style=discord.ButtonStyle.danger, custom_id="suggestion_deny")
    async def deny(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._update_status(interaction, "denied", discord.Color.red())

    async def _update_status(self, interaction: discord.Interaction, status: str, color: discord.Color):
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message("You don't have permission to moderate suggestions.", ephemeral=True)
            return
        database.execute(
            "UPDATE suggestions SET status = ? WHERE suggestion_id = ?", (status, self.suggestion_id)
        )
        embed = interaction.message.embeds[0]
        embed.color = color
        embed.set_footer(text=f"Status: {status.capitalize()} by {interaction.user.display_name}")
        await interaction.response.edit_message(embed=embed, view=None)


class Suggestions(commands.Cog):
    """Suggestion box with upvote/downvote reactions and staff approval."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        bot.add_view(SuggestionModerationView(0))  # register persistent view pattern (ids handled per-message via custom_id lookups)

    @app_commands.command(name="suggest", description="Submit a suggestion for the server")
    @app_commands.describe(suggestion="Your suggestion")
    async def suggest(self, interaction: discord.Interaction, suggestion: str):
        config = database.get_guild_config(interaction.guild_id)
        channel = interaction.channel
        if config["suggestions_channel_id"]:
            configured = interaction.guild.get_channel(config["suggestions_channel_id"])
            if configured:
                channel = configured

        embed = discord.Embed(
            title="💡 New Suggestion",
            description=suggestion,
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow(),
        )
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        embed.set_footer(text="Status: Pending")

        suggestion_row_id = database.execute(
            "INSERT INTO suggestions (guild_id, user_id, message_id, content, created_at) VALUES (?, ?, 0, ?, ?)",
            (interaction.guild_id, interaction.user.id, suggestion, time.time()),
        )
        row = database.execute(
            "SELECT suggestion_id FROM suggestions WHERE guild_id = ? ORDER BY suggestion_id DESC LIMIT 1",
            (interaction.guild_id,),
            fetch="one",
        )
        suggestion_id = row["suggestion_id"]

        view = SuggestionModerationView(suggestion_id)
        message = await channel.send(embed=embed, view=view)
        await message.add_reaction("👍")
        await message.add_reaction("👎")

        database.execute(
            "UPDATE suggestions SET message_id = ? WHERE suggestion_id = ?", (message.id, suggestion_id)
        )

        if channel.id != interaction.channel.id:
            await interaction.response.send_message(f"✅ Suggestion submitted to {channel.mention}!", ephemeral=True)
        else:
            await interaction.response.send_message("✅ Suggestion submitted!", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Suggestions(bot))
