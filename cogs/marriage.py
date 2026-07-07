import time

import discord
from discord import app_commands
from discord.ext import commands

import database

MARRIAGE_COST = 500
DIVORCE_FEE = 250


class ProposalView(discord.ui.View):
    def __init__(self, proposer: discord.Member, target: discord.Member):
        super().__init__(timeout=60)
        self.proposer = proposer
        self.target = target

    @discord.ui.button(label="💍 Accept", style=discord.ButtonStyle.success)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.target.id:
            await interaction.response.send_message("This proposal isn't for you.", ephemeral=True)
            return

        guild_id = interaction.guild_id
        database.execute(
            "INSERT OR REPLACE INTO marriages (guild_id, user_id, partner_id, married_at) VALUES (?, ?, ?, ?)",
            (guild_id, self.proposer.id, self.target.id, time.time()),
        )
        database.execute(
            "INSERT OR REPLACE INTO marriages (guild_id, user_id, partner_id, married_at) VALUES (?, ?, ?, ?)",
            (guild_id, self.target.id, self.proposer.id, time.time()),
        )
        self.stop()
        await interaction.response.send_message(
            f"💒 {self.proposer.mention} and {self.target.mention} are now married! Congratulations! 🎉"
        )

    @discord.ui.button(label="Decline", style=discord.ButtonStyle.danger)
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.target.id:
            await interaction.response.send_message("This proposal isn't for you.", ephemeral=True)
            return
        self.stop()
        await interaction.response.send_message(f"💔 {self.target.mention} declined the proposal.")


class Marriage(commands.Cog):
    """Marriage/relationship commands tied to the economy system."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _get_marriage(self, guild_id, user_id):
        return database.execute(
            "SELECT * FROM marriages WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id),
            fetch="one",
        )

    @app_commands.command(name="marry", description=f"Propose marriage to another member (costs {MARRIAGE_COST} coins)")
    async def marry(self, interaction: discord.Interaction, member: discord.Member):
        if member.id == interaction.user.id:
            await interaction.response.send_message("❌ You can't marry yourself.", ephemeral=True)
            return
        if member.bot:
            await interaction.response.send_message("❌ You can't marry a bot.", ephemeral=True)
            return

        if self._get_marriage(interaction.guild_id, interaction.user.id):
            await interaction.response.send_message("❌ You're already married! Divorce first with /divorce.", ephemeral=True)
            return
        if self._get_marriage(interaction.guild_id, member.id):
            await interaction.response.send_message(f"❌ {member.display_name} is already married.", ephemeral=True)
            return

        econ = database.ensure_economy_row(interaction.guild_id, interaction.user.id)
        if econ["balance"] < MARRIAGE_COST:
            await interaction.response.send_message(f"❌ You need {MARRIAGE_COST} coins to propose.", ephemeral=True)
            return

        database.execute(
            "UPDATE economy SET balance = balance - ? WHERE guild_id = ? AND user_id = ?",
            (MARRIAGE_COST, interaction.guild_id, interaction.user.id),
        )

        view = ProposalView(interaction.user, member)
        await interaction.response.send_message(
            f"💍 {member.mention}, {interaction.user.mention} has proposed to you! Do you accept?", view=view
        )

    @app_commands.command(name="divorce", description=f"Divorce your partner (costs {DIVORCE_FEE} coins)")
    async def divorce(self, interaction: discord.Interaction):
        row = self._get_marriage(interaction.guild_id, interaction.user.id)
        if row is None:
            await interaction.response.send_message("❌ You're not married.", ephemeral=True)
            return

        partner_id = row["partner_id"]
        econ = database.ensure_economy_row(interaction.guild_id, interaction.user.id)
        fee = min(DIVORCE_FEE, econ["balance"])
        database.execute(
            "UPDATE economy SET balance = balance - ? WHERE guild_id = ? AND user_id = ?",
            (fee, interaction.guild_id, interaction.user.id),
        )
        database.execute("DELETE FROM marriages WHERE guild_id = ? AND user_id = ?", (interaction.guild_id, interaction.user.id))
        database.execute("DELETE FROM marriages WHERE guild_id = ? AND user_id = ?", (interaction.guild_id, partner_id))

        await interaction.response.send_message(f"💔 {interaction.user.mention} has divorced <@{partner_id}>. That'll be {fee} coins.")

    @app_commands.command(name="spouse", description="Check who a member is married to")
    async def spouse(self, interaction: discord.Interaction, member: discord.Member = None):
        member = member or interaction.user
        row = self._get_marriage(interaction.guild_id, member.id)
        if row is None:
            await interaction.response.send_message(f"{member.display_name} isn't married.", ephemeral=True)
            return
        await interaction.response.send_message(f"💑 {member.mention} is married to <@{row['partner_id']}>.")


async def setup(bot: commands.Bot):
    await bot.add_cog(Marriage(bot))
