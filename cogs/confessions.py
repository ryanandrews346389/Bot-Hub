import time

import discord
from discord import app_commands
from discord.ext import commands

import database


class Confessions(commands.Cog):
    """Anonymous confessions posted to a designated channel."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._confession_counter = {}

    @app_commands.command(name="confess", description="Send an anonymous confession to this server (works via DM too)")
    @app_commands.describe(server_id="If using this in DMs, the ID of the server to send your confession to", message="Your anonymous confession")
    async def confess(self, interaction: discord.Interaction, message: str, server_id: str = None):
        guild = interaction.guild
        if guild is None:
            if not server_id:
                await interaction.response.send_message(
                    "Please provide the server_id of the server you want to send your confession to.", ephemeral=True
                )
                return
            guild = self.bot.get_guild(int(server_id))
            if guild is None:
                await interaction.response.send_message("I couldn't find that server.", ephemeral=True)
                return

        config = database.get_guild_config(guild.id)
        if not config["confessions_channel_id"]:
            await interaction.response.send_message(
                "This server hasn't set up a confessions channel yet. Ask an admin to run /setup channel.", ephemeral=True
            )
            return

        channel = guild.get_channel(config["confessions_channel_id"])
        if channel is None:
            await interaction.response.send_message("The configured confessions channel no longer exists.", ephemeral=True)
            return

        count = self._confession_counter.get(guild.id, 0) + 1
        self._confession_counter[guild.id] = count

        embed = discord.Embed(
            title=f"🤫 Anonymous Confession #{count}",
            description=message,
            color=discord.Color.dark_grey(),
            timestamp=discord.utils.utcnow(),
        )
        await channel.send(embed=embed)

        # Log sender internally for staff moderation purposes only (not shown publicly)
        print(f"[CONFESSION LOG] Guild {guild.id} | Confession #{count} | Sender: {interaction.user} ({interaction.user.id})")

        await interaction.response.send_message("✅ Your confession has been posted anonymously.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Confessions(bot))
