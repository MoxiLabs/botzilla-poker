import discord
from discord.ext import commands
import asyncio
import aiohttp
import re
import json
import os
import sys
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from itertools import cycle
from typing import List, cast, Union, Optional
from .freerollpass import FreerollParser
from .freeroll_password import FreeRollPasswordParser
from .models import TournamentEvent
from dotenv import load_dotenv
from .logger import log, setup_logger, setup_discord_logging, logging
from .database import init_db, is_event_sent, add_sent_event, has_sent_today, cleanup_old_events

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
# LOCALIZATION
# ------------------------------------------------------
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

URL_PASSWORD = config.get("url_password", "https://freeroll-password.com/")
URL_PASS = config.get("url_pass", "https://freerollpass.com/")

# Command settings
COMMAND_PREFIX = config.get("command_prefix", "!")
COMMAND_SUFFIX = config.get("command_suffix", "")

bot = commands.Bot(command_prefix=COMMAND_PREFIX, intents=intents, help_command=None)

@bot.check
async def globally_block_dms_and_channels(ctx):
    return ctx.channel.id in ALLOWED_CHANNEL_IDS

# ------------------------------------------------------
# DISCORD WRAPPER FOR DRY RUN
# ------------------------------------------------------
async def send_discord_message(target, content: str = None, embed: discord.Embed = None, file: discord.File = None):
    """Send message to Discord or print to console based on DRY_RUN env variable"""
    dry_run = os.environ.get('DRY_RUN', '')
    
    if dry_run:  # Non-empty string means DRY_RUN mode
        msg = f"[DRY_RUN] Message to {target}: {content if content else ''}"
        if embed:
            msg += f" [Embed: {embed.title}]"
        if file:
            msg += f" [File: {file.filename}]"
        log.info(msg)
    else:
        if file:
            await target.send(content=content, embed=embed, file=file)
        else:
            await target.send(content=content, embed=embed)

# ------------------------------------------------------
# SCRAPER – freeroll-password.com
# ------------------------------------------------------
async def fetch_freerolls_password() -> List[TournamentEvent]:
    """Fetch freerolls from freeroll-password.com"""
    try:
        parser = FreeRollPasswordParser(url=URL_PASSWORD)
        tournaments = await parser.get_tournaments()
        return tournaments if tournaments else []
    except:
        return []


# ------------------------------------------------------
# SCRAPER – freerollpass.com
# ------------------------------------------------------
async def fetch_freerolls_pass() -> List[TournamentEvent]:
    """Fetch freerolls from freerollpass.com"""
    try:
        parser = FreerollParser(url=URL_PASS)
        tournaments = await parser.get_tournaments()
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

async def fetch_freerolls() -> List[TournamentEvent]:
    """Fetch freerolls from all sources and combine them"""
    events: List[TournamentEvent] = []    # Fetch from both sources
    
    # Run both async fetchers concurrently
    results = await asyncio.gather(
        fetch_freerolls_password(),
        fetch_freerolls_pass(),
        return_exceptions=True
    )
    
    for result in results:
        if isinstance(result, list):
            events.extend(result)
            
    # Sort by date and time
    events.sort(key=lambda x: get_event_datetime(x))
    return events

# ------------------------------------------------------
# FORMATTER
# ------------------------------------------------------
def extract_prize_value(prize_str: str) -> int:
    """Extract integer value from prize string (e.g. '$500' -> 500)"""
    if not prize_str:
        return 0
    try:
        clean_str = prize_str.replace(',', '').replace('.', '')
        match = re.search(r'\d+', clean_str)
        if match:
            return int(match.group())
    except Exception:
        pass
    return 0

# No hardcoded thumbnails needed anymore, generated dynamically and cached locally

async def create_event_embed(e: TournamentEvent, urgent=False) -> tuple[discord.Embed, Optional[discord.File]]:
    source_emoji = "🌐" if e.get('source') == "freeroll-password.com" else "🎯"
    
    # Format time display
    if e['is_all_day'] or e['time'] is None:
        time_display = t("fmt_all_day", date=e['date'].strftime('%d.%m.%Y'))
    else:
        dt = get_event_datetime(e)
        # Make the naive datetime aware of its actual timezone (Budapest)
        dt_aware = dt.replace(tzinfo=ZoneInfo("Europe/Budapest"))
        timestamp = int(dt_aware.timestamp())
        time_display = f"**{dt.strftime('%H:%M %d.%m.%Y')}** (<t:{timestamp}:R>)"
        
    prize_val = extract_prize_value(e['prize'])
    threshold = config.get("high_value_threshold", 500)
    
    # Determine Color
    embed_color = discord.Color.green()
    if urgent:
        embed_color = discord.Color.red()
    elif prize_val >= threshold:
        embed_color = discord.Color.gold()
        
    embed = discord.Embed(
        title=f"💰 {e['name']}",
        color=embed_color
    )
    
    embed.add_field(name=t("embed_room"), value=f"**{e['room']}**", inline=True)
    embed.add_field(name=t("embed_prize"), value=f"**{e['prize']}**", inline=True)
    embed.add_field(name=t("embed_start"), value=time_display, inline=False)
    
    password_text = f"`{e['password']}`" if e['password'] != "not required" else "❌"
    embed.add_field(name=t("embed_password"), value=password_text, inline=True)
    
    embed.add_field(name=t("embed_source", emoji=source_emoji), value=e.get('source', 'n/a'), inline=True)
    
    # Dynamically fetch and attach room thumbnail 
    room_clean = e['room'].lower().replace(' ', '')
    logo_filename = f"{room_clean}-x2.png"
    logo_path = os.path.join(os.path.dirname(__file__), "..", "assets", "logos", logo_filename)
    
    file_attachment = None
    if not os.path.exists(logo_path):
        os.makedirs(os.path.dirname(logo_path), exist_ok=True)
        dl_url = f"https://freerollpass.com/storage/app/media/logo/{logo_filename}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(dl_url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}, timeout=5) as resp:
                    if resp.status == 200:
                        content = await resp.read()
                        with open(logo_path, 'wb') as f:
                            f.write(content)
        except Exception as ex:
            log.debug(f"Failed to download logo for {room_clean}: {ex}")

    if os.path.exists(logo_path):
        # We must open caching a File object for the Discord message
        file_attachment = discord.File(logo_path, filename=logo_filename)
        embed.set_thumbnail(url=f"attachment://{logo_filename}")
            
    return embed, file_attachment

# ------------------------------------------------------
# COMMANDS
# ------------------------------------------------------
@bot.command(name=f"day{COMMAND_SUFFIX}")
async def cmd_day(ctx):
    # Use globally stored events from the watcher
    global GLOBAL_EVENTS
    events = GLOBAL_EVENTS if GLOBAL_EVENTS else await fetch_freerolls()
    now = datetime.now()
    
    # Events in the next 24 hours (now + 24 hours)
    next_24h_cutoff = now + timedelta(hours=24)
    next_24h = [e for e in events if now <= get_event_datetime(e) <= next_24h_cutoff]

    if not next_24h:
        await send_discord_message(ctx.channel, t("no_freerolls_24h"))
        return

    await send_discord_message(ctx.channel, content=t("freerolls_next_24h"))
    for e in next_24h:
        emb, attach = await create_event_embed(e)
        await send_discord_message(ctx.channel, embed=emb, file=attach)

@bot.command(name=f"next{COMMAND_SUFFIX}")
async def cmd_next(ctx):
    # Use globally stored events from the watcher
    global GLOBAL_EVENTS
    events = GLOBAL_EVENTS if GLOBAL_EVENTS else await fetch_freerolls()
    now = datetime.now()
    
    # Filter out all-day events and get future events
    future = [e for e in events if not e['is_all_day'] and get_event_datetime(e) > now]

    if not future:
        await send_discord_message(ctx.channel, t("no_upcoming_freeroll"))
        return

    nxt = future[0]
    delta = get_event_datetime(nxt) - now
    total_minutes = int(delta.total_seconds() / 60)
    
    time_msg = t("starts_in_minutes", min=total_minutes)
    emb, attach = await create_event_embed(nxt)
    await send_discord_message(ctx.channel, content=t("next_freeroll") + time_msg, embed=emb, file=attach)


@bot.command(name=f"debug{COMMAND_SUFFIX}")
async def cmd_debug(ctx):
    events = await fetch_freerolls()
    await send_discord_message(ctx.channel, t("debug_freerolls_loaded", count=len(events)))


@bot.command(name=f"test{COMMAND_SUFFIX}")
async def cmd_test(ctx):
    await send_discord_message(ctx.channel, t("test_ok"))


@bot.command(name=f"help{COMMAND_SUFFIX}")
async def cmd_help(ctx):
    await send_discord_message(ctx.channel, t("help_text"))

# ------------------------------------------------------
# STATUS ROTATOR (presence cycle)
# ------------------------------------------------------
STATUS_MESSAGES = cycle(TRANSLATIONS.get("status_messages", config.get("status_messages", [
    "👹 Monitoring freerolls…",
    "🃏 Hunt is on…",
    "💰 Botzilla in active mode",
    "🧨 10-minute alerts ready",
    "♠️ New freeroll approaching…"
])))

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
        events = await fetch_freerolls()
        GLOBAL_EVENTS = events  # Store events globally
        now = datetime.now()
        today = now.date()

        # Cleanup: remove events older than today
        await cleanup_old_events(today)
        
        # Events in the next 24 hours (now + 24 hours)
        next_24h_cutoff = now + timedelta(hours=24)
        next_24h = [e for e in events if now <= get_event_datetime(e) <= next_24h_cutoff]
        
        new_events = []
        for e in next_24h:
            if not await is_event_sent(e):
                new_events.append(e)
        
        if new_events:
            if await has_sent_today(today):
                await send_discord_message(channel, content=t("new_daily_event"))
            else:
                await send_discord_message(channel, content=t("freerolls_next_24h"))
            
            for e in new_events:
                emb, attach = await create_event_embed(e)
                await send_discord_message(channel, embed=emb, file=attach)
                # Add to the sent events list
                await add_sent_event(e)

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
                    emb, attach = await create_event_embed(nxt)
                    await send_discord_message(
                        channel,
                        content=t("starts_in_minutes", min=total_minutes),
                        embed=emb,
                        file=attach
                    )

            # Urgent alert (e.g. 10 minutes)
            if total_minutes < urgent_min and total_minutes >= 0:
                event_key = (get_event_datetime(nxt), nxt["name"], 'urgent')
                if event_key not in SENT_ALERTS:
                    SENT_ALERTS.add(event_key)
                    emb, attach = await create_event_embed(nxt, urgent=True)
                    await send_discord_message(
                        channel,
                        content=t("urgent_starts_in_minutes", min=total_minutes),
                        embed=emb,
                        file=attach
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
    
    # Initialize SQLite database
    await init_db()

    asyncio.create_task(status_rotator())
    asyncio.create_task(watcher())



if __name__ == "__main__":
    bot.run(TOKEN)
