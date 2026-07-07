import time

import discord
from discord import app_commands
from discord.ext import commands

import database


class CloseTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.danger, custom_id="close_ticket_button")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        row = database.execute(
            "SELECT * FROM tickets WHERE channel_id = ? AND status = 'open'",
            (interaction.channel.id,),
            fetch="one",
        )
        if row is None:
            await interaction.response.send_message("This isn't an active ticket channel.", ephemeral=True)
            return
        database.execute(
            "UPDATE tickets SET status = 'closed', closed_at = ? WHERE ticket_id = ?",
            (time.time(), row["ticket_id"]),
        )
        await interaction.response.send_message("🔒 Closing this ticket in 5 seconds...")
        await interaction.channel.edit(name=f"closed-{row['ticket_id']}")
        await interaction.channel.set_permissions(interaction.guild.get_member(row["user_id"]), view_channel=False)


class OpenTicketView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(label="📩 Open a Complaint Ticket", style=discord.ButtonStyle.primary, custom_id="open_ticket_button")
    async def open_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.create_ticket(interaction)


class Tickets(commands.Cog):
    """Ticket/support system for member complaints."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        bot.add_view(OpenTicketView(self))
        bot.add_view(CloseTicketView())

    async def create_ticket(self, interaction: discord.Interaction):
        guild = interaction.guild
        existing = database.execute(
            "SELECT * FROM tickets WHERE guild_id = ? AND user_id = ? AND status = 'open'",
            (guild.id, interaction.user.id),
            fetch="one",
        )
        if existing:
            channel = guild.get_channel(existing["channel_id"])
            await interaction.response.send_message(
                f"You already have an open ticket: {channel.mention if channel else '#unknown'}", ephemeral=True
            )
            return

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True),
        }
        config = database.get_guild_config(guild.id)
        if config["mod_role_id"]:
            mod_role = guild.get_role(config["mod_role_id"])
            if mod_role:
                overwrites[mod_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True)

        category = discord.utils.get(guild.categories, name="Tickets")
        if category is None:
            category = await guild.create_category("Tickets")

        channel = await guild.create_text_channel(
            f"ticket-{interaction.user.name}", overwrites=overwrites, category=category
        )

        database.execute(
            "INSERT INTO tickets (guild_id, user_id, channel_id, status, created_at) VALUES (?, ?, ?, 'open', ?)",
            (guild.id, interaction.user.id, channel.id, time.time()),
        )

        embed = discord.Embed(
            title="📩 New Complaint Ticket",
            description=f"Hey {interaction.user.mention}, describe your issue and staff will help shortly.",
            color=discord.Color.blue(),
        )
        await channel.send(embed=embed, view=CloseTicketView())
        await interaction.response.send_message(f"✅ Ticket created: {channel.mention}", ephemeral=True)

    @app_commands.command(name="ticket_panel", description="Post the ticket-opening panel in this channel")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def ticket_panel(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🎫 Support Tickets",
            description="Click the button below to open a private ticket for complaints or support.",
            color=discord.Color.blue(),
        )
        await interaction.channel.send(embed=embed, view=OpenTicketView(self))
        await interaction.response.send_message("✅ Ticket panel posted.", ephemeral=True)

    @app_commands.command(name="close_ticket", description="Close the current ticket")
    async def close_ticket_cmd(self, interaction: discord.Interaction):
        row = database.execute(
            "SELECT * FROM tickets WHERE channel_id = ? AND status = 'open'",
            (interaction.channel.id,),
            fetch="one",
        )
        if row is None:
            await interaction.response.send_message("This isn't an active ticket channel.", ephemeral=True)
            return
        database.execute(
            "UPDATE tickets SET status = 'closed', closed_at = ? WHERE ticket_id = ?",
            (time.time(), row["ticket_id"]),
        )
        await interaction.response.send_message("🔒 Ticket closed.")
        await interaction.channel.edit(name=f"closed-{row['ticket_id']}")


async def setup(bot: commands.Bot):
    await bot.add_cog(Tickets(bot))
