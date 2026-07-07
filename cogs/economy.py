import time
import random

import discord
from discord import app_commands
from discord.ext import commands

import database

DAILY_AMOUNT = 200
WEEKLY_AMOUNT = 1000
DAILY_COOLDOWN = 24 * 60 * 60
WEEKLY_COOLDOWN = 7 * 24 * 60 * 60

SHOP_ITEMS = {
    "vip_color": {"name": "VIP Name Color", "price": 5000, "description": "Bragging rights item (cosmetic)."},
    "lucky_charm": {"name": "Lucky Charm", "price": 2500, "description": "Cosmetic flex item."},
    "trophy": {"name": "Golden Trophy", "price": 10000, "description": "Show off your wealth."},
}


class Economy(commands.Cog):
    """Virtual currency economy: daily/weekly, shop, gambling, pay."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="balance", description="Check your (or someone else's) balance")
    async def balance(self, interaction: discord.Interaction, member: discord.Member = None):
        member = member or interaction.user
        row = database.ensure_economy_row(interaction.guild_id, member.id)
        embed = discord.Embed(title=f"💰 {member.display_name}'s Wallet", color=discord.Color.gold())
        embed.add_field(name="Balance", value=f"{row['balance']} coins")
        embed.add_field(name="Bank", value=f"{row['bank']} coins")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="daily", description="Claim your daily coins")
    async def daily(self, interaction: discord.Interaction):
        row = database.ensure_economy_row(interaction.guild_id, interaction.user.id)
        now = time.time()
        remaining = DAILY_COOLDOWN - (now - (row["last_daily"] or 0))
        if remaining > 0:
            hrs = int(remaining // 3600)
            mins = int((remaining % 3600) // 60)
            await interaction.response.send_message(f"⏳ You already claimed your daily. Try again in {hrs}h {mins}m.", ephemeral=True)
            return
        database.execute(
            "UPDATE economy SET balance = balance + ?, last_daily = ? WHERE guild_id = ? AND user_id = ?",
            (DAILY_AMOUNT, now, interaction.guild_id, interaction.user.id),
        )
        await interaction.response.send_message(f"✅ You claimed your daily **{DAILY_AMOUNT} coins**!")

    @app_commands.command(name="weekly", description="Claim your weekly coins")
    async def weekly(self, interaction: discord.Interaction):
        row = database.ensure_economy_row(interaction.guild_id, interaction.user.id)
        now = time.time()
        remaining = WEEKLY_COOLDOWN - (now - (row["last_weekly"] or 0))
        if remaining > 0:
            days = int(remaining // 86400)
            hrs = int((remaining % 86400) // 3600)
            await interaction.response.send_message(f"⏳ You already claimed your weekly. Try again in {days}d {hrs}h.", ephemeral=True)
            return
        database.execute(
            "UPDATE economy SET balance = balance + ?, last_weekly = ? WHERE guild_id = ? AND user_id = ?",
            (WEEKLY_AMOUNT, now, interaction.guild_id, interaction.user.id),
        )
        await interaction.response.send_message(f"✅ You claimed your weekly **{WEEKLY_AMOUNT} coins**!")

    @app_commands.command(name="pay", description="Give coins to another member")
    @app_commands.describe(member="Member to pay", amount="Amount of coins to send")
    async def pay(self, interaction: discord.Interaction, member: discord.Member, amount: app_commands.Range[int, 1, None]):
        if member.id == interaction.user.id:
            await interaction.response.send_message("❌ You can't pay yourself.", ephemeral=True)
            return
        sender = database.ensure_economy_row(interaction.guild_id, interaction.user.id)
        if sender["balance"] < amount:
            await interaction.response.send_message("❌ You don't have enough coins.", ephemeral=True)
            return
        database.ensure_economy_row(interaction.guild_id, member.id)
        database.execute(
            "UPDATE economy SET balance = balance - ? WHERE guild_id = ? AND user_id = ?",
            (amount, interaction.guild_id, interaction.user.id),
        )
        database.execute(
            "UPDATE economy SET balance = balance + ? WHERE guild_id = ? AND user_id = ?",
            (amount, interaction.guild_id, member.id),
        )
        await interaction.response.send_message(f"✅ {interaction.user.mention} paid {member.mention} **{amount} coins**.")

    @app_commands.command(name="deposit", description="Deposit coins into your bank (safe from gambling losses)")
    async def deposit(self, interaction: discord.Interaction, amount: app_commands.Range[int, 1, None]):
        row = database.ensure_economy_row(interaction.guild_id, interaction.user.id)
        if row["balance"] < amount:
            await interaction.response.send_message("❌ You don't have that much in your wallet.", ephemeral=True)
            return
        database.execute(
            "UPDATE economy SET balance = balance - ?, bank = bank + ? WHERE guild_id = ? AND user_id = ?",
            (amount, amount, interaction.guild_id, interaction.user.id),
        )
        await interaction.response.send_message(f"🏦 Deposited **{amount} coins** into your bank.")

    @app_commands.command(name="withdraw", description="Withdraw coins from your bank")
    async def withdraw(self, interaction: discord.Interaction, amount: app_commands.Range[int, 1, None]):
        row = database.ensure_economy_row(interaction.guild_id, interaction.user.id)
        if row["bank"] < amount:
            await interaction.response.send_message("❌ You don't have that much in your bank.", ephemeral=True)
            return
        database.execute(
            "UPDATE economy SET balance = balance + ?, bank = bank - ? WHERE guild_id = ? AND user_id = ?",
            (amount, amount, interaction.guild_id, interaction.user.id),
        )
        await interaction.response.send_message(f"💵 Withdrew **{amount} coins** from your bank.")

    @app_commands.command(name="coinflip", description="Bet coins on a coin flip (50/50)")
    async def coinflip(self, interaction: discord.Interaction, amount: app_commands.Range[int, 1, None], choice: str):
        choice = choice.lower()
        if choice not in ("heads", "tails"):
            await interaction.response.send_message("❌ Choose 'heads' or 'tails'.", ephemeral=True)
            return
        row = database.ensure_economy_row(interaction.guild_id, interaction.user.id)
        if row["balance"] < amount:
            await interaction.response.send_message("❌ You don't have enough coins.", ephemeral=True)
            return
        result = random.choice(["heads", "tails"])
        won = result == choice
        delta = amount if won else -amount
        database.execute(
            "UPDATE economy SET balance = balance + ? WHERE guild_id = ? AND user_id = ?",
            (delta, interaction.guild_id, interaction.user.id),
        )
        outcome = "🎉 You won!" if won else "💸 You lost."
        await interaction.response.send_message(f"The coin landed on **{result}**. {outcome} ({'+' if won else ''}{delta} coins)")

    @app_commands.command(name="slots", description="Try your luck on the slot machine")
    async def slots(self, interaction: discord.Interaction, amount: app_commands.Range[int, 1, None]):
        row = database.ensure_economy_row(interaction.guild_id, interaction.user.id)
        if row["balance"] < amount:
            await interaction.response.send_message("❌ You don't have enough coins.", ephemeral=True)
            return
        symbols = ["🍒", "🍋", "🔔", "⭐", "💎"]
        spin = [random.choice(symbols) for _ in range(3)]
        if spin[0] == spin[1] == spin[2]:
            multiplier = 5
        elif len(set(spin)) == 2:
            multiplier = 1.5
        else:
            multiplier = 0
        delta = int(amount * multiplier) - amount
        database.execute(
            "UPDATE economy SET balance = balance + ? WHERE guild_id = ? AND user_id = ?",
            (delta, interaction.guild_id, interaction.user.id),
        )
        await interaction.response.send_message(f"🎰 {' | '.join(spin)}\n{'You won' if delta > 0 else 'You lost'} {abs(delta)} coins.")

    @app_commands.command(name="shop", description="View the coin shop")
    async def shop(self, interaction: discord.Interaction):
        embed = discord.Embed(title="🛒 Shop", color=discord.Color.purple())
        for key, item in SHOP_ITEMS.items():
            embed.add_field(name=f"{item['name']} — {item['price']} coins", value=item["description"], inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="buy", description="Buy an item from the shop")
    @app_commands.choices(item=[app_commands.Choice(name=v["name"], value=k) for k, v in SHOP_ITEMS.items()])
    async def buy(self, interaction: discord.Interaction, item: app_commands.Choice[str]):
        price = SHOP_ITEMS[item.value]["price"]
        row = database.ensure_economy_row(interaction.guild_id, interaction.user.id)
        if row["balance"] < price:
            await interaction.response.send_message("❌ You can't afford that.", ephemeral=True)
            return
        database.execute(
            "UPDATE economy SET balance = balance - ? WHERE guild_id = ? AND user_id = ?",
            (price, interaction.guild_id, interaction.user.id),
        )
        await interaction.response.send_message(f"✅ You bought **{item.name}**!")


async def setup(bot: commands.Bot):
    await bot.add_cog(Economy(bot))
