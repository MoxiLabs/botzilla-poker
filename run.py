#!/usr/bin/env python3
"""Standalone runner for the poker parser Discord bot"""

import sys
import os

# Add the pokerparser directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import and run the bot
from pokerparser.discordbot import bot, TOKEN, log

if __name__ == "__main__":
    try:
        log.info("Starting Discord bot...")
        bot.run(TOKEN)
    except KeyboardInterrupt:
        log.info("Bot stopped by user.")
        sys.exit(0)
    except Exception as e:
        log.error(f"Error starting bot: {e}")
        sys.exit(1)
