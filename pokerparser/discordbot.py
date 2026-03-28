import discord
import asyncio
import requests
import re
import json
import os
import sys
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, timezone
from itertools import cycle
from typing import List, cast, Union
from .freerollpass import FreerollParser
from .freeroll_password import FreeRollPasswordParser
from .models import TournamentEvent
from dotenv import load_dotenv
from .logger import log, setup_logger, setup_discord_logging, logging

# Load environment variables from .env file
load_dotenv()

# ------------------------------------------------------
# CONFIG LOADING
# ------------------------------------------------------
def load_config():
    """Load configuration from config.json file"""
    # Try to find config.json in multiple locations
    possible_paths = [
        "config.json",  # Current directory
        os.path.join(os.path.dirname(__file__), "..", "config.json"),  # Parent directory
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "config.json"),  # Absolute parent
    ]
    
    for config_path in possible_paths:
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                # We don't have logger initialized yet, so use print
                print(f"Error loading config from {config_path}: {e}")
                continue
    
    # If no config file found, show error and exit
    print("ERROR: config.json not found!")
    print("Please create a config.json file based on config.example.json")
    print("Expected locations:")
    for path in possible_paths:
        print(f"  - {os.path.abspath(path)}")
    sys.exit(1)

# Load configuration
config = load_config()

# ------------------------------------------------------
# LOGGING SETUP
# ------------------------------------------------------
log_cfg = config.get("logging", {})
log_level_name = log_cfg.get("level", "INFO").upper()
log_level = getattr(logging, log_level_name, logging.INFO)
log_file = log_cfg.get("file", "botzilla.log")
log_max_mb = log_cfg.get("max_mb", 5)
log_backup_count = log_cfg.get("backup_count", 3)

# Convert MB to Bytes for the rotating handler
log_max_bytes = log_max_mb * 1024 * 1024

# Initialize bot and discord library loggers
setup_logger(
    log_file=log_file, 
    max_bytes=log_max_bytes, 
    level=log_level, 
    backup_count=log_backup_count
)
setup_discord_logging(
    log_file=log_file, 
    max_bytes=log_max_bytes, 
    backup_count=log_backup_count
)

# Discord token from environment variable
TOKEN = os.environ.get("DISCORD_TOKEN")

# Target channel for automatic notifications
CHANNEL_ID = config.get("channel_id")

# Channels allowed for command interaction
ALLOWED_CHANNEL_IDS = config.get("allowed_channel_ids", [])

if not TOKEN:
    log.error("DISCORD_TOKEN not found in environment or .env file")
    sys.exit(1)

if not CHANNEL_ID:
    log.error("channel_id not found in config.json")
    sys.exit(1)

if not ALLOWED_CHANNEL_IDS:
    log.warning("allowed_channel_ids not found or empty in config.json")
    # Default to the main channel if not specified
    ALLOWED_CHANNEL_IDS = [CHANNEL_ID]

LAST_EVENT_FILE = config.get("last_event_file", "last_event.json")

intents = discord.Intents.default()
intents.message_content = True
bot = discord.Client(intents=intents)

URL_PASSWORD = config.get("url_password", "https://freeroll-password.com/")
URL_PASS = config.get("url_pass", "https://freerollpass.com/")

# Command settings
COMMAND_PREFIX = config.get("command_prefix", "!")
COMMAND_SUFFIX = config.get("command_suffix", "")

# ------------------------------------------------------
# DISCORD WRAPPER FOR DRY RUN
# ------------------------------------------------------
async def send_discord_message(target, content: str):
    """Send message to Discord or print to console based on DRY_RUN env variable"""
    dry_run = os.environ.get('DRY_RUN', '')
    
    if dry_run:  # Non-empty string means DRY_RUN mode
        log.info(f"[DRY_RUN] Message to {target}: {content}")
    else:
        await target.send(content)

# ------------------------------------------------------
# SCRAPER – freeroll-password.com
# ------------------------------------------------------
def fetch_freerolls_password() -> List[TournamentEvent]:
    """Fetch freerolls from freeroll-password.com"""
    try:
        parser = FreeRollPasswordParser(url=URL_PASSWORD)
        tournaments = parser.get_tournaments()
        return tournaments if tournaments else []
    except:
        return []


# ------------------------------------------------------
# SCRAPER – freerollpass.com
# ------------------------------------------------------
def fetch_freerolls_pass() -> List[TournamentEvent]:
    """Fetch freerolls from freerollpass.com"""
    try:
        parser = FreerollParser(url=URL_PASS)
        tournaments = parser.get_tournaments()
        return tournaments if tournaments else []
    except:
        return []


# ------------------------------------------------------
# COMBINED SCRAPER
# ------------------------------------------------------
def get_event_datetime(event: TournamentEvent) -> datetime:
    """Get datetime from event (date + time fields)"""
    if event['is_all_day'] or event['time'] is None:
        # For all-day events, use midnight
        return datetime.combine(event['date'], datetime.min.time())
    return datetime.combine(event['date'], event['time'])

def fetch_freerolls() -> List[TournamentEvent]:
    """Fetch freerolls from all sources and combine them"""
    events: List[TournamentEvent] = []    # Fetch from both sources
    events.extend(fetch_freerolls_password())
    events.extend(fetch_freerolls_pass())
    
    # Sort by date and time
    events.sort(key=lambda x: get_event_datetime(x))
    return events

# ------------------------------------------------------
# EVENT STORAGE HELPERS
# ------------------------------------------------------
def event_to_dict(event: TournamentEvent) -> dict:
    """Convert TournamentEvent to dictionary for comparison/storage"""
    return {
        "date": event["date"].isoformat(),
        "time": event["time"].isoformat() if event["time"] else None,
        "is_all_day": event["is_all_day"],
        "room": event["room"],
        "name": event["name"],
        "prize": event["prize"],
        "password": event["password"],
        "source": event.get("source", "n/a")
    }

def load_sent_events() -> List[dict]:
    """Load all sent events from file"""
    if not os.path.exists(LAST_EVENT_FILE):
        return []
    try:
        with open(LAST_EVENT_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # Handle old format (single event) and new format (list of events)
            if isinstance(data, dict):
                return [data]  # Convert old single event to list
            return data if isinstance(data, list) else []
    except:
        return []

def save_sent_events(events: List[dict]) -> None:
    """Save all sent events to file"""
    try:
        with open(LAST_EVENT_FILE, 'w', encoding='utf-8') as f:
            json.dump(events, f, ensure_ascii=False, indent=2)
    except Exception as e:
        log.error(f"Error saving sent events: {e}")

def event_already_sent(event: TournamentEvent, sent_events: List[dict]) -> bool:
    """Check if event was already sent (deep compare all fields)"""
    event_data = event_to_dict(event)
    for sent_event in sent_events:
        if event_data == sent_event:
            return True
    return False

def add_sent_event(event: TournamentEvent) -> None:
    """Add event to sent events list"""
    sent_events = load_sent_events()
    event_data = event_to_dict(event)
    
    # Only add if not already in list
    if not event_already_sent(event, sent_events):
        sent_events.append(event_data)
        save_sent_events(sent_events)

def cleanup_old_events() -> None:
    """Remove events older than today from sent events list"""
    sent_events = load_sent_events()
    today = datetime.now().date()
    
    # Keep only today's events
    cleaned_events = []
    for event_data in sent_events:
        try:
            event_date = datetime.fromisoformat(event_data["date"]).date()
            if event_date >= today:
                cleaned_events.append(event_data)
        except:
            # If can't parse date, skip this event
            continue
    
    save_sent_events(cleaned_events)

# ------------------------------------------------------
# FORMATTER
# ------------------------------------------------------
def fmt(e: TournamentEvent) -> str:
    source_emoji = "🌐" if e.get('source') == "freeroll-password.com" else "🎯"
    
    # Format time display
    if e['is_all_day'] or e['time'] is None:
        time_display = f"**{e['date'].strftime('%d.%m.%Y')} (all day)**"
    else:
        dt = get_event_datetime(e)
        time_display = f"**{dt.strftime('%H:%M %d.%m.%Y')}**"
    
    return (
        f"💰 **{e['name']}**\n"
        f"🏢 Room: **{e['room']}**\n"
        f"💵 Prize: **{e['prize']}**\n"
        f"🕒 Start: {time_display}\n"
        f"🔑 Password: **{e['password']}**\n"
        f"{source_emoji} Source: {e.get('source', 'n/a')}\n"
        f"──────────────"
    )

# ------------------------------------------------------
# COMMANDS
# ------------------------------------------------------
async def send_today(message):
    # Use globally stored events from the watcher
    global GLOBAL_EVENTS
    events = GLOBAL_EVENTS if GLOBAL_EVENTS else fetch_freerolls()
    now = datetime.now()
    
    # Events in the next 24 hours (now + 24 hours)
    next_24h_cutoff = now + timedelta(hours=24)
    next_24h = [e for e in events if now <= get_event_datetime(e) <= next_24h_cutoff]

    if not next_24h:
        await send_discord_message(message.channel, "📭 No freerolls in the next 24 hours.")
        return

    await send_discord_message(message.channel, "📅 **Freerolls for the next 24 hours:**\n")
    for e in next_24h:
        await send_discord_message(message.channel, fmt(e))

async def send_next(message):
    # Use globally stored events from the watcher
    global GLOBAL_EVENTS
    events = GLOBAL_EVENTS if GLOBAL_EVENTS else fetch_freerolls()
    now = datetime.now()
    
    # Filter out all-day events and get future events
    future = [e for e in events if not e['is_all_day'] and get_event_datetime(e) > now]

    if not future:
        await send_discord_message(message.channel, "❌ No upcoming freeroll.")
        return

    nxt = future[0]
    delta = get_event_datetime(nxt) - now
    total_minutes = int(delta.total_seconds() / 60)
    
    time_msg = f"⏰ **Starts in {total_minutes} minutes!**\n\n"
    await send_discord_message(message.channel, "👉 **Next freeroll:**\n" + time_msg + fmt(nxt))


async def send_debug(message):
    events = fetch_freerolls()
    await send_discord_message(message.channel, f"🔧 Debug: {len(events)} freerolls loaded.")


async def send_test(message):
    await send_discord_message(message.channel, "🧪 Test OK! The bot is running.")


async def send_help(message):
    help_text = (
        "🃏 **Freeroll Bot Commands:**\n\n"
        "**!day** - Freerolls for the next 24 hours\n"
        "**!next** - Details of the nearest freeroll\n"
        "**!test** - Check bot operation\n"
        "**!help** - This help message\n\n"
        "The bot automatically monitors freerolls and sends notifications:\n"
        "⏰ 1 hour before start\n"
        "🚨 10 minutes before start"
    )
    await send_discord_message(message.channel, help_text)

# ------------------------------------------------------
# STATUS ROTATOR (presence cycle)
# ------------------------------------------------------
STATUS_MESSAGES = cycle(config.get("status_messages", [
    "👹 Monitoring freerolls…",
    "🃏 Hunt is on…",
    "💰 Botzilla in active mode",
    "🧨 10-minute alerts ready",
    "♠️ New freeroll approaching…"
]))

async def status_rotator():
    await bot.wait_until_ready()
    sleep_seconds = config.get("status_rotator_sleep_seconds", 20)
    while not bot.is_closed():
        current_status = next(STATUS_MESSAGES)
        await bot.change_presence(activity=discord.Game(name=current_status))
        await asyncio.sleep(sleep_seconds)

# ------------------------------------------------------
# WATCHER – Daily summary and alerts
# ------------------------------------------------------
# Store sent alerts
# Key: (datetime, name, alert_type) where alert_type: 'daily', '1hour', '10min'
SENT_ALERTS = set()

# Globally stored events from the watcher
GLOBAL_EVENTS: List[TournamentEvent] = []

async def watcher():
    global SENT_ALERTS, GLOBAL_EVENTS
    await bot.wait_until_ready()
    channel_obj = bot.get_channel(CHANNEL_ID)
    
    if channel_obj is None:
        log.error(f"Channel with ID {CHANNEL_ID} not found")
        return
    
    # Type narrowing - ensure we have a text channel
    if not isinstance(channel_obj, (discord.TextChannel, discord.Thread)):
        log.error(f"Channel {CHANNEL_ID} is not a text channel or thread")
        return
    
    channel = cast(Union[discord.TextChannel, discord.Thread], channel_obj)

    last_daily_send = None

    while True:
        events = fetch_freerolls()
        GLOBAL_EVENTS = events  # Store events globally
        now = datetime.now()
        today = now.date()

        # Cleanup: remove events older than today
        cleanup_old_events()
        
        # Load sent events
        sent_events = load_sent_events()
        
        # Events in the next 24 hours (now + 24 hours)
        next_24h_cutoff = now + timedelta(hours=24)
        next_24h = [e for e in events if now <= get_event_datetime(e) <= next_24h_cutoff]
        
        # Only send events that haven't been sent yet (deep compare)
        new_events = [e for e in next_24h if not event_already_sent(e, sent_events)]
        
        if new_events:
            # Check if we've already sent a daily summary today
            # (is there an event with today's date in the sent list)
            has_sent_today = any(
                datetime.fromisoformat(sent["date"]).date() == today 
                for sent in sent_events
            )
            
            # If we've already sent a daily summary today, send with "New daily event" title
            if has_sent_today:
                await send_discord_message(channel, "🆕 **New daily event:**\n")
            else:
                await send_discord_message(channel, "📅 **Freerolls for the next 24 hours:**\n")
            
            for e in new_events:
                await send_discord_message(channel, fmt(e))
                # Add to the sent events list
                add_sent_event(e)

        # Future events for alerts
        # Filter out all-day events from alerts (1h and 10min warnings)
        next_24h_cutoff = now + timedelta(hours=24)
        next_24h_timed = [e for e in events if not e['is_all_day'] and now <= get_event_datetime(e) <= next_24h_cutoff]
        
        # Get threshold values from config
        thresholds = config.get("alert_thresholds", {"warning": 60, "urgent": 10})
        warning_min = thresholds.get("warning", 60)
        urgent_min = thresholds.get("urgent", 10)
        
        for nxt in next_24h_timed:
            delta = get_event_datetime(nxt) - now
            total_minutes = int(delta.total_seconds() / 60)

            # Warning alert (e.g. 1 hour)
            if total_minutes < warning_min and total_minutes > urgent_min:
                event_key = (get_event_datetime(nxt), nxt["name"], 'warning')
                if event_key not in SENT_ALERTS:
                    SENT_ALERTS.add(event_key)
                    await send_discord_message(
                        channel,
                        f"⏰ **Starts in {total_minutes} minutes!**\n\n" + fmt(nxt)
                    )

            # Urgent alert (e.g. 10 minutes)
            if total_minutes < urgent_min and total_minutes >= 0:
                event_key = (get_event_datetime(nxt), nxt["name"], 'urgent')
                if event_key not in SENT_ALERTS:
                    SENT_ALERTS.add(event_key)
                    await send_discord_message(
                        channel,
                        f"🚨 **ATTENTION! Starts in {total_minutes} minutes!**\n\n" + fmt(nxt)
                    )

        # Memory cleanup: remove expired events
        cutoff_time = now - timedelta(hours=2)
        SENT_ALERTS = {
            (dt, name, alert_type) for (dt, name, alert_type) in SENT_ALERTS 
            if dt > cutoff_time
        }

        watcher_sleep = config.get("watcher_sleep_seconds", 300)
        await asyncio.sleep(watcher_sleep)

# ------------------------------------------------------
# BOT EVENTS
# ------------------------------------------------------
@bot.event
async def on_ready():
    log.info(f"Bot online: {bot.user}")

    asyncio.create_task(status_rotator())
    asyncio.create_task(watcher())


@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    # Check if the channel is allowed for commands
    if message.channel.id not in ALLOWED_CHANNEL_IDS:
        return

    content = message.content.lower()

    # Helper function to check for the command with its prefix and suffix
    def is_cmd(cmd_name):
        return content == f"{COMMAND_PREFIX}{cmd_name}{COMMAND_SUFFIX}".lower()

    if is_cmd("day"):
        await send_today(message)

    if is_cmd("next"):
        await send_next(message)

    if is_cmd("test"):
        await send_test(message)

    if is_cmd("help"):
        await send_help(message)



if __name__ == "__main__":
    bot.run(TOKEN)
