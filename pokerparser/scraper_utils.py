import os
import aiohttp
import asyncio
import discord
import re
from typing import List, Optional
from datetime import datetime
from zoneinfo import ZoneInfo

from .models import TournamentEvent
from .freeroll_password import FreeRollPasswordParser
from .freerollpass import FreerollParser
from .logger import log
from .core import config, t, TIMEZONE
from .views import TournamentView


# The global events variable
GLOBAL_EVENTS: List[TournamentEvent] = []

URL_PASSWORD = config.get("url_password", "https://freeroll-password.com/")
URL_PASS = config.get("url_pass", "https://freerollpass.com/")

async def fetch_freerolls_password() -> List[TournamentEvent]:
    try:
        parser = FreeRollPasswordParser(url=URL_PASSWORD)
        tournaments = await parser.get_tournaments()
        return tournaments if tournaments else []
    except:
        return []

async def fetch_freerolls_pass() -> List[TournamentEvent]:
    try:
        parser = FreerollParser(url=URL_PASS)
        tournaments = await parser.get_tournaments()
        return tournaments if tournaments else []
    except:
        return []

def get_event_datetime(event: TournamentEvent) -> datetime:
    if event['is_all_day'] or event['time'] is None:
        return datetime.combine(event['date'], datetime.min.time())
    return datetime.combine(event['date'], event['time'])

async def fetch_freerolls() -> List[TournamentEvent]:
    events: List[TournamentEvent] = []
    results = await asyncio.gather(
        fetch_freerolls_password(),
        fetch_freerolls_pass(),
        return_exceptions=True
    )
    for result in results:
        if isinstance(result, list):
            events.extend(result)
    events.sort(key=lambda x: get_event_datetime(x))
    
    global GLOBAL_EVENTS
    GLOBAL_EVENTS = events
    return events

def extract_prize_value(prize_str: str) -> int:
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

async def create_event_embed(e: TournamentEvent, urgent=False) -> tuple[discord.Embed, Optional[discord.File], Optional[discord.ui.View]]:
    source_emoji = "🌐" if e.get('source') == "freeroll-password.com" else "🎯"
    if e['is_all_day'] or e['time'] is None:
        time_display = t("fmt_all_day", date=e['date'].strftime('%d.%m.%Y'))
    else:
        dt = get_event_datetime(e)
        dt_aware = dt.replace(tzinfo=ZoneInfo(TIMEZONE))
        timestamp = int(dt_aware.timestamp())

        time_display = f"**{dt.strftime('%H:%M %d.%m.%Y')}** (<t:{timestamp}:R>)"
        
    prize_val = extract_prize_value(e['prize'])
    threshold = config.get("high_value_threshold", 500)
    
    # Premium Hex Colors
    COLOR_GOLD = 0xd4af37      # Metallic Gold
    COLOR_NEPHRITE = 0x27ae60  # Deep Green
    COLOR_POMEGRANATE = 0xc0392b # Royal Red
    
    embed_color = COLOR_NEPHRITE
    if urgent:
        embed_color = COLOR_POMEGRANATE
    elif prize_val >= threshold:
        embed_color = COLOR_GOLD
        
    embed = discord.Embed(title=f"💰 {e['name']}", color=embed_color)
    
    # Primary Details (Inline 1x3 row)
    embed.add_field(name=t("embed_room"), value=f"**{e['room']}**", inline=True)
    embed.add_field(name=t("embed_prize"), value=f"**{e['prize']}**", inline=True)
    
    password_text = f"`{e['password']}`" if e['password'] != "not required" else "❌"
    embed.add_field(name=t("embed_password"), value=password_text, inline=True)

    # Secondary Details (Full row)
    embed.add_field(name=t("embed_start"), value=time_display, inline=False)
    
    # Source Info & Branding
    embed.set_footer(text=f"{t('embed_source_short')}: {e.get('source', 'n/a')} • {t('help_footer')}")
    
    room_clean = e['room'].lower().replace(' ', '')
    logo_filename = f"{room_clean}-x2.png"
    logo_path = os.path.join(os.path.dirname(__file__), "..", "assets", "logos", logo_filename)
    
    file_attachment = None
    if not os.path.exists(logo_path):
        os.makedirs(os.path.dirname(logo_path), exist_ok=True)
        dl_url = f"https://freerollpass.com/storage/app/media/logo/{logo_filename}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(dl_url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=5) as resp:
                    if resp.status == 200:
                        content = await resp.read()
                        with open(logo_path, 'wb') as f:
                            f.write(content)
        except Exception as ex:
            log.debug(f"Failed to download logo for {room_clean}: {ex}")

    if os.path.exists(logo_path):
        file_attachment = discord.File(logo_path, filename=logo_filename)
        embed.set_thumbnail(url=f"attachment://{logo_filename}")
            
    view = TournamentView(url=e.get('url'), password=e.get('password'))
    return embed, file_attachment, view
