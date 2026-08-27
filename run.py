#!/usr/bin/env python3
"""Standalone runner for the Botzilla poker parser Discord bot."""

import sys
import os

# Add root directory to python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pokerparser.bot.client import run_bot

if __name__ == "__main__":
    run_bot()
