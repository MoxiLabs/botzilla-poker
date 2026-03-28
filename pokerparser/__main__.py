"""Main entry point for the poker parser - runs the Discord bot"""

import sys
from .discordbot import bot, TOKEN, log


def main():
    """Main function to start the Discord bot"""
    try:
        log.info("Starting Discord bot...")
        bot.run(TOKEN)
    except Exception as e:
        log.error(f"Error starting bot: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
