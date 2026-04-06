import discord
from discord.ext import commands
import os
import sys
import asyncio
from dotenv import load_dotenv

from .core import config
from .logger import log, setup_logger, setup_discord_logging, logging
from .database import init_db

# Load environment variables
load_dotenv()

# Configuration
TOKEN = os.environ.get("DISCORD_TOKEN")
CHANNEL_ID = config.get("channel_id")
ALLOWED_CHANNEL_IDS = config.get("allowed_channel_ids", [])

if not TOKEN:
    print("ERROR: DISCORD_TOKEN not found in environment or .env file")
    sys.exit(1)

if not ALLOWED_CHANNEL_IDS:
    # Default to the main channel if not specified
    ALLOWED_CHANNEL_IDS = [CHANNEL_ID] if CHANNEL_ID else []

# Logging Setup
log_cfg = config.get("logging", {})
log_level = getattr(logging, log_cfg.get("level", "INFO").upper(), logging.INFO)
log_file = log_cfg.get("file", "botzilla.log")
log_max_bytes = log_cfg.get("max_mb", 5) * 1024 * 1024
log_backup_count = log_cfg.get("backup_count", 3)

setup_logger(log_file=log_file, max_bytes=log_max_bytes, level=log_level, backup_count=log_backup_count)
setup_discord_logging(log_file=log_file, max_bytes=log_max_bytes, backup_count=log_backup_count)

# Bot instance
COMMAND_PREFIX = config.get("command_prefix", "!")
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix=COMMAND_PREFIX, intents=intents, help_command=None)

@bot.check
async def globally_block_dms_and_channels(ctx):
    """Restrict bot to allowed channels only"""
    return ctx.channel.id in ALLOWED_CHANNEL_IDS

@bot.event
async def on_ready():
    log.info(f"Botzilla Poker Bot online: {bot.user}")
    await init_db()
    
    # Load Cogs
    try:
        await bot.load_extension("pokerparser.cogs.admin")
        await bot.load_extension("pokerparser.cogs.commands")
        await bot.load_extension("pokerparser.cogs.tasks")
        log.info("Cogs loaded successfully")
    except Exception as e:
        log.error(f"Error loading cogs: {e}")

if __name__ == "__main__":
    bot.run(TOKEN)
