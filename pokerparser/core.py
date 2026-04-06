import os
import json
import sys
import discord
from typing import Optional
from .logger import log

def load_config():
    """Load configuration from config.json file"""
    possible_paths = [
        "config.json",  
        os.path.join(os.path.dirname(__file__), "..", "config.json"),  
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "config.json"),  
    ]
    for config_path in possible_paths:
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading config from {config_path}: {e}")
                continue
    print("ERROR: config.json not found!")
    sys.exit(1)

config = load_config()
TIMEZONE = config.get("timezone", "Europe/Budapest")

LOCALE = config.get("locale", "hu")


def load_translations(locale="hu"):
    paths = [
        os.path.join(os.path.dirname(__file__), "..", "locales", f"{locale}.json"),
        os.path.join(os.getcwd(), "locales", f"{locale}.json")
    ]
    for p in paths:
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading {p}: {e}")
    print(f"Warning: Locale file for '{locale}' not found.")
    return {}

TRANSLATIONS = load_translations(LOCALE)

def t(key, **kwargs):
    text = TRANSLATIONS.get(key, key)
    if kwargs:
        try:
            return text.format(**kwargs)
        except Exception:
            return text
    return text

async def send_discord_message(target, content: str = None, embed: discord.Embed = None, file: discord.File = None, view: discord.ui.View = None):
    """Send message to Discord or print to console based on DRY_RUN env variable"""
    dry_run = os.environ.get('DRY_RUN', '')
    
    if dry_run:  # Non-empty string means DRY_RUN mode
        msg = f"[DRY_RUN] Message to {target}: {content if content else ''}"
        if embed:
            msg += f" [Embed: {embed.title}]"
        if file:
            msg += f" [File: {file.filename}]"
        if view:
            msg += f" [View: {view.__class__.__name__}]"
        log.info(msg)
    else:
        if file:
            await target.send(content=content, embed=embed, file=file, view=view)
        else:
            await target.send(content=content, embed=embed, view=view)
