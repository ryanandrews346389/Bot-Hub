# Discord Bot Hub 2

A feature-rich Python Discord bot built with `discord.py`.

## Features
- **Moderation:** kick, ban, timeout, purge, warn/warnings
- **Leveling/XP:** chat XP + voice channel XP, `/rank`, level-up announcements
- **Music:** play/pause/resume/skip/stop/queue from YouTube
- **Tickets:** button-based complaint/support tickets with private channels
- **Economy:** daily/weekly, pay, deposit/withdraw, coinflip, slots, shop
- **Giveaways:** button entry, automatic winner picking, reroll
- **Fighting game:** challenge + accept, power tied to level, coin wagers
- **Confessions:** anonymous posts to a configured channel
- **Birthday tracker:** auto-announcements on the day
- **Marriage/relationship:** propose, accept/decline, divorce
- **Leaderboards:** XP, richest, top fighters
- **Suggestion box:** button-based approve/deny + reactions
- **Ownership transfer prank:** `$ownership_transfer` — countdown gag command with a DM reveal
- **Arrest/jail (basic):** `/arrest`, `/release` — groundwork only; the full interactive panel will be added once you share the panel spec

## Setup

1. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```
   You'll also need `ffmpeg` installed on your system for the music cog to work
   (e.g. `apt install ffmpeg` on Linux, or download a build for Windows/Mac).

2. **Create your bot & get a token**
   - Go to https://discord.com/developers/applications
   - Create an application → Bot → copy the token
   - Under "Privileged Gateway Intents", enable **Server Members Intent** and **Message Content Intent**

3. **Configure your token**
   - Copy `.env.example` to `.env`
   - Paste your token into `DISCORD_TOKEN=`

4. **Invite the bot to your server**
   - In the Developer Portal, go to OAuth2 → URL Generator
   - Select scopes: `bot`, `applications.commands`
   - Select permissions: Administrator (simplest), or pick individual permissions matching the features above
   - Open the generated URL and invite the bot

5. **Run the bot**
   ```bash
   python bot.py
   ```

## First-time server configuration

Once the bot is in your server, an admin should run these slash commands to wire up channels/roles:

- `/setup channel feature:confessions channel:#confessions`
- `/setup channel feature:suggestions channel:#suggestions`
- `/setup channel feature:birthdays channel:#general`
- `/setup channel feature:giveaways channel:#giveaways`
- `/setup channel feature:level_up_announcements channel:#level-ups`
- `/setup channel feature:jail channel:#jail`
- `/setup role role_type:admin_role role:@Admin` (needed for `$ownership_transfer` and to control `/arrest`)
- `/setup role role_type:jail_role role:@Jailed`
- `/setup role role_type:mod_role role:@Moderator` (used by tickets so staff can see them)

You can check current config anytime with `/setup view`.

## Notes
- The economy is purely a virtual, in-bot currency for fun — it has no real-world value.
- The database is a single `bot.db` SQLite file created automatically on first run, storing data per-server so the bot works across multiple servers.
- The `$ownership_transfer` prank command is a text command (uses the `$` prefix), while most other commands are slash commands. Make sure it's clear to your server this is just a joke — the bot's DM reveal already does that.
- The `/arrest` and `/release` commands are basic groundwork (adds/removes a jail role). Send over your panel spec whenever you're ready and I'll build the full interactive version on top of this.
