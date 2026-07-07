import datetime

import discord
from discord import app_commands
from discord.ext import commands, tasks

import database


class Birthday(commands.Cog):
    """Users can set their birthday; bot announces it automatically."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.check_birthdays.start()

    def cog_unload(self):
        self.check_birthdays.cancel()

    @app_commands.command(name="set_birthday", description="Set your birthday so the server can celebrate it")
    @app_commands.describe(month="Month (1-12)", day="Day of the month", year="Year (optional)")
    async def set_birthday(self, interaction: discord.Interaction, month: app_commands.Range[int, 1, 12], day: app_commands.Range[int, 1, 31], year: app_commands.Range[int, 1900, 2025] = None):
        try:
            datetime.date(year or 2000, month, day)
        except ValueError:
            await interaction.response.send_message("❌ That's not a valid date.", ephemeral=True)
            return

        database.execute(
            """
            INSERT INTO birthdays (guild_id, user_id, month, day, year)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(guild_id, user_id) DO UPDATE SET month=excluded.month, day=excluded.day, year=excluded.year
            """,
            (interaction.guild_id, interaction.user.id, month, day, year),
        )
        await interaction.response.send_message(f"🎂 Your birthday has been set to {month}/{day}" + (f"/{year}" if year else "") + "!", ephemeral=True)

    @app_commands.command(name="birthday", description="Check a member's birthday")
    async def birthday(self, interaction: discord.Interaction, member: discord.Member = None):
        member = member or interaction.user
        row = database.execute(
            "SELECT * FROM birthdays WHERE guild_id = ? AND user_id = ?",
            (interaction.guild_id, member.id),
            fetch="one",
        )
        if row is None:
            await interaction.response.send_message(f"{member.display_name} hasn't set their birthday yet.", ephemeral=True)
            return
        date_str = f"{row['month']}/{row['day']}" + (f"/{row['year']}" if row["year"] else "")
        await interaction.response.send_message(f"🎂 {member.display_name}'s birthday is {date_str}.")

    @tasks.loop(hours=24)
    async def check_birthdays(self):
        today = datetime.date.today()
        rows = database.execute(
            "SELECT * FROM birthdays WHERE month = ? AND day = ?",
            (today.month, today.day),
            fetch="all",
        )
        for row in rows:
            if row["last_announced_year"] == today.year:
                continue
            guild = self.bot.get_guild(row["guild_id"])
            if guild is None:
                continue
            config = database.get_guild_config(guild.id)
            channel = guild.get_channel(config["birthday_channel_id"]) if config["birthday_channel_id"] else None
            if channel is None and guild.text_channels:
                channel = guild.text_channels[0]
            if channel:
                age_text = ""
                if row["year"]:
                    age = today.year - row["year"]
                    age_text = f" (turning {age})"
                try:
                    await channel.send(f"🎉🎂 Happy Birthday <@{row['user_id']}>{age_text}! Hope you have an amazing day!")
                except discord.HTTPException:
                    pass
            database.execute(
                "UPDATE birthdays SET last_announced_year = ? WHERE guild_id = ? AND user_id = ?",
                (today.year, row["guild_id"], row["user_id"]),
            )

    @check_birthdays.before_loop
    async def before_check_birthdays(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(Birthday(bot))
