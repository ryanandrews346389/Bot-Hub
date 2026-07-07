import asyncio

import discord
from discord.ext import commands

import database

PASSWORD = "$XSupreme"
PRANK_ROLE_NAME = None  # optionally set a specific role name here, or configure via /setup role admin_role


class Prank(commands.Cog):
    """The (fake) ownership transfer prank command."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _has_permission(self, ctx: commands.Context) -> bool:
        config = database.get_guild_config(ctx.guild.id)
        admin_role_id = config["admin_role_id"]
        if admin_role_id:
            role = ctx.guild.get_role(admin_role_id)
            if role and role in ctx.author.roles:
                return True
        # Fallback: real administrator permission can also run it
        return ctx.author.guild_permissions.administrator

    @commands.command(name="ownership_transfer")
    async def ownership_transfer(self, ctx: commands.Context):
        if not self._has_permission(ctx):
            await ctx.send("❌ You don't have permission to use this command.")
            return

        await ctx.send("🔑 Who do you want to transfer ownership to? Please mention them.")

        def check_mention(m: discord.Message):
            return m.author.id == ctx.author.id and m.channel.id == ctx.channel.id and len(m.mentions) > 0

        try:
            mention_msg = await self.bot.wait_for("message", check=check_mention, timeout=60)
        except asyncio.TimeoutError:
            await ctx.send("⌛ Timed out waiting for a mention. Cancelled.")
            return

        target = mention_msg.mentions[0]

        await ctx.send(f"🔐 Please enter the terminal password to authorize transferring ownership to {target.mention}.")

        def check_password(m: discord.Message):
            return m.author.id == ctx.author.id and m.channel.id == ctx.channel.id

        try:
            pw_msg = await self.bot.wait_for("message", check=check_password, timeout=60)
        except asyncio.TimeoutError:
            await ctx.send("⌛ Timed out waiting for the password. Cancelled.")
            return

        if pw_msg.content.strip() != PASSWORD:
            await ctx.send("❌ Incorrect password. Ownership transfer cancelled.")
            return

        countdown_msg = await ctx.send(f"✅ Password accepted. Beginning ownership transfer to {target.mention} in **10**...")
        for i in range(9, 0, -1):
            await asyncio.sleep(1)
            try:
                await countdown_msg.edit(content=f"✅ Password accepted. Beginning ownership transfer to {target.mention} in **{i}**...")
            except discord.HTTPException:
                pass

        await asyncio.sleep(1)
        await countdown_msg.edit(content=f"📨 {target.mention}, check your DMs for confirmation!")

        try:
            await target.send(
                "😂 **You thought you were getting ownership?!** Gotcha! This was just a prank, "
                "you're still just a regular member. No hard feelings — go about your day! 🎉"
            )
        except discord.Forbidden:
            await ctx.send(
                f"⚠️ Couldn't DM {target.mention} (they may have DMs disabled), so here's the reveal instead: "
                f"{target.mention}, that ownership transfer was just a prank — you're still a regular member! 😂"
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(Prank(bot))
