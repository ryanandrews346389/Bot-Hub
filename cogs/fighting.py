import random
import asyncio

import discord
from discord import app_commands
from discord.ext import commands

import database


class FightChallengeView(discord.ui.View):
    def __init__(self, challenger: discord.Member, opponent: discord.Member, wager: int):
        super().__init__(timeout=60)
        self.challenger = challenger
        self.opponent = opponent
        self.wager = wager
        self.responded = False

    @discord.ui.button(label="Accept Fight", style=discord.ButtonStyle.success)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.opponent.id:
            await interaction.response.send_message("This challenge isn't for you.", ephemeral=True)
            return
        self.responded = True
        self.stop()
        await interaction.response.defer()
        await run_fight(interaction, self.challenger, self.opponent, self.wager)

    @discord.ui.button(label="Decline", style=discord.ButtonStyle.danger)
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.opponent.id:
            await interaction.response.send_message("This challenge isn't for you.", ephemeral=True)
            return
        self.responded = True
        self.stop()
        await interaction.response.send_message(f"{self.opponent.mention} declined the fight. 🚪")


async def run_fight(interaction: discord.Interaction, challenger: discord.Member, opponent: discord.Member, wager: int):
    guild_id = interaction.guild_id

    c_level_row = database.ensure_level_row(guild_id, challenger.id)
    o_level_row = database.ensure_level_row(guild_id, opponent.id)
    c_econ_row = database.ensure_economy_row(guild_id, challenger.id)
    o_econ_row = database.ensure_economy_row(guild_id, opponent.id)

    if wager > 0:
        if c_econ_row["balance"] < wager or o_econ_row["balance"] < wager:
            await interaction.followup.send("❌ One of the fighters doesn't have enough coins to cover the wager.")
            return

    # Combat power derived from level (strength stat) with some randomness
    c_power = 50 + (c_level_row["level"] * 5) + random.randint(0, 40)
    o_power = 50 + (o_level_row["level"] * 5) + random.randint(0, 40)

    rounds = []
    c_hp, o_hp = 100, 100
    round_num = 1
    while c_hp > 0 and o_hp > 0 and round_num <= 10:
        c_dmg = max(5, int(c_power * random.uniform(0.15, 0.35)))
        o_dmg = max(5, int(o_power * random.uniform(0.15, 0.35)))
        o_hp -= c_dmg
        c_hp -= o_dmg
        rounds.append(f"Round {round_num}: {challenger.display_name} hits for {c_dmg} | {opponent.display_name} hits for {o_dmg}")
        round_num += 1

    winner, loser = (challenger, opponent) if o_hp <= c_hp else (opponent, challenger)
    if o_hp <= 0 and c_hp <= 0:
        winner, loser = random.choice([(challenger, opponent), (opponent, challenger)])

    if wager > 0:
        database.execute(
            "UPDATE economy SET balance = balance - ? WHERE guild_id = ? AND user_id = ?",
            (wager, guild_id, loser.id),
        )
        database.execute(
            "UPDATE economy SET balance = balance + ? WHERE guild_id = ? AND user_id = ?",
            (wager, guild_id, winner.id),
        )
    database.execute(
        "UPDATE economy SET wins = wins + 1 WHERE guild_id = ? AND user_id = ?", (guild_id, winner.id)
    )
    database.execute(
        "UPDATE economy SET losses = losses + 1 WHERE guild_id = ? AND user_id = ?", (guild_id, loser.id)
    )

    embed = discord.Embed(
        title="⚔️ Fight Result",
        description="\n".join(rounds[-5:]),
        color=discord.Color.red(),
    )
    embed.add_field(name="Winner", value=f"🏆 {winner.mention}")
    if wager > 0:
        embed.add_field(name="Wager", value=f"{wager} coins transferred from {loser.mention} to {winner.mention}")
    await interaction.followup.send(embed=embed)


class Fighting(commands.Cog):
    """A currency + XP-based fighting/battle game between members."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="fight", description="Challenge another member to a fight, optionally wagering coins")
    @app_commands.describe(opponent="Who to challenge", wager="Coins to wager (optional, default 0)")
    async def fight(self, interaction: discord.Interaction, opponent: discord.Member, wager: app_commands.Range[int, 0, None] = 0):
        if opponent.bot:
            await interaction.response.send_message("❌ You can't fight a bot.", ephemeral=True)
            return
        if opponent.id == interaction.user.id:
            await interaction.response.send_message("❌ You can't fight yourself.", ephemeral=True)
            return

        if wager > 0:
            challenger_econ = database.ensure_economy_row(interaction.guild_id, interaction.user.id)
            if challenger_econ["balance"] < wager:
                await interaction.response.send_message("❌ You don't have enough coins for that wager.", ephemeral=True)
                return

        view = FightChallengeView(interaction.user, opponent, wager)
        wager_text = f" wagering **{wager} coins**" if wager > 0 else ""
        await interaction.response.send_message(
            f"⚔️ {opponent.mention}, {interaction.user.mention} has challenged you to a fight{wager_text}! Do you accept?",
            view=view,
        )

    @app_commands.command(name="fight_stats", description="View your (or someone else's) fight record")
    async def fight_stats(self, interaction: discord.Interaction, member: discord.Member = None):
        member = member or interaction.user
        row = database.ensure_economy_row(interaction.guild_id, member.id)
        embed = discord.Embed(title=f"⚔️ {member.display_name}'s Fight Record", color=discord.Color.dark_red())
        embed.add_field(name="Wins", value=str(row["wins"]))
        embed.add_field(name="Losses", value=str(row["losses"]))
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Fighting(bot))
