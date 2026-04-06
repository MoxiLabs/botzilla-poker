"""URL parser for freeroll-password.com"""

import re
import asyncio
import aiohttp
from bs4 import BeautifulSoup
from typing import List, Dict, Optional
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from .models import TournamentEvent
from .core import TIMEZONE


class FreeRollPasswordParser:
    def __init__(self, url: str = "https://www.freeroll-password.com/"):
        self.url = url
    
    async def fetch_page(self) -> str:
        """Fetch the HTML content from the URL"""
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        async with aiohttp.ClientSession() as session:
            async with session.get(self.url, headers=headers, timeout=30) as response:
                response.raise_for_status()
                return await response.text()
    
    def parse_freerolls(self, html_content: str) -> List[TournamentEvent]:
        """Parse the freeroll list from HTML content"""
        soup = BeautifulSoup(html_content, "html.parser")
        wrapper = soup.select_one("div.pt-cv-wrapper")
        
        if not wrapper:
            return []

        events: List[TournamentEvent] = []
        items = wrapper.select(".pt-cv-content-item")

        for item in items:
            try:
                excerpt = item.select_one(".fpexcerpt")
                if not excerpt:
                    continue

                # Parse room
                room_span = excerpt.select_one(".exroom")
                room = "Unknown"
                if room_span and room_span.next_sibling:
                    room = str(room_span.next_sibling).strip()

                # Parse date
                date_span = excerpt.select_one(".date-display-single")
                date_str = date_span.text.strip() if date_span else None

                # Parse time with timezone
                time_span = excerpt.select_one(".extime")
                time_str = None
                if time_span and time_span.next_sibling:
                    time_str = str(time_span.next_sibling).strip()

                # Parse prize
                prize_span = excerpt.select_one(".exprize")
                prize = "n/a"
                if prize_span and prize_span.next_sibling:
                    prize = str(prize_span.next_sibling).strip()

                # Parse name
                name_span = excerpt.select_one(".exname")
                name = "Unknown"
                if name_span and name_span.next_sibling:
                    name = str(name_span.next_sibling).strip()

                # Parse password
                password_span = excerpt.select_one(".expass2")
                password = password_span.text.strip() if password_span else "n/a"

                # Parse datetime with timezone conversion
                if date_str:
                    # Parse date: "November 24, 2025"
                    event_date = datetime.strptime(date_str, "%B %d, %Y").date()
                    event_time = None
                    is_all_day = False
                    
                    if time_str:
                        try:
                            # Format: "22:30 GMT+2"
                            # Extract timezone offset from time string
                            tz_match = re.search(r'GMT([+-]\d+)', time_str)
                            tz_offset = int(tz_match.group(1)) if tz_match else 0
                            
                            time_clean = time_str.split()[0]  # Get just HH:MM
                            dt_str = f"{date_str} {time_clean}"
                            dt_naive = datetime.strptime(dt_str, "%B %d, %Y %H:%M")
                            
                            # Create timezone-aware datetime
                            source_tz = timezone(timedelta(hours=tz_offset))
                            dt_aware = dt_naive.replace(tzinfo=source_tz)
                            
                            # Convert to configured timezone (handles CET/CEST automatically)
                            budapest_tz = ZoneInfo(TIMEZONE)
                            dt_budapest = dt_aware.astimezone(budapest_tz)

                            
                            # Extract time from converted datetime
                            event_time = dt_budapest.time()
                            # Date might change due to timezone conversion
                            event_date = dt_budapest.date()
                        except Exception:
                            # If time parsing fails, mark as all-day and append to name
                            is_all_day = True
                            event_time = None
                            name = f"{name} ({time_str})"
                    else:
                        # No time string means all-day event
                        is_all_day = True
                    
                    events.append({
                        "date": event_date,
                        "time": event_time,
                        "is_all_day": is_all_day,
                        "room": room,
                        "name": name,
                        "prize": prize,
                        "password": password,
                        "source": "freeroll-password.com"
                    })
            except Exception as e:
                continue

        return events
    
    async def get_tournaments(self) -> List[TournamentEvent]:
        """Fetch and parse all tournaments"""
        html_content = await self.fetch_page()
        return await asyncio.to_thread(self.parse_freerolls, html_content)