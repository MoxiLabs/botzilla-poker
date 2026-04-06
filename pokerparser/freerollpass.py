import datetime as dt
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup
import aiohttp
import asyncio
from typing import List, Dict, Optional
from .models import TournamentEvent
from .core import TIMEZONE



class FreerollParser:
    """Parser for poker freeroll tournaments from freerollpass.com"""
    
    def __init__(self, url: str = "https://freerollpass.com/"):
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
    
    def _calculate_timezone_offset(self, html_content: str) -> int:
        """Calculate timezone offset by comparing server time with current configured timezone time"""

        try:
            soup = BeautifulSoup(html_content, 'lxml')
            loader_time = soup.find('div', class_='loader-time')
            
            if not loader_time:
                return 1  # Default CET offset
            
            # Get server time and date
            utime_div = loader_time.find('div', id='utime')
            udate_div = loader_time.find('div', id='udate')
            
            if not utime_div or not udate_div:
                return 1  # Default CET offset
            
            server_time_str = utime_div.text.strip()  # e.g., "22:07"
            server_date_str = udate_div.text.strip()  # e.g., "24.11.2025"
            
            if not server_time_str or not server_date_str:
                return 1  # Default CET offset
            
            # Parse server datetime
            server_dt_str = f"{server_date_str} {server_time_str}"
            try:
                server_dt = datetime.strptime(server_dt_str, "%d.%m.%Y %H:%M")
            except ValueError as e:
                log.warning(f"Failed to calculate timezone offset: {e}")
                return 1
            
            # Get current configured timezone time (handles CET/CEST automatically)
            budapest_tz = ZoneInfo(TIMEZONE)
            budapest_now = datetime.now(budapest_tz)
            budapest_offset = int(budapest_now.utcoffset().total_seconds() / 3600)

            budapest_now_naive = budapest_now.replace(tzinfo=None)
            
            # Calculate the difference in hours between server time and configured timezone time
            time_diff = server_dt - budapest_now_naive

            offset_diff = round(time_diff.total_seconds() / 3600)
            
            # The actual timezone offset is Budapest offset plus the difference
            offset_hours = budapest_offset + offset_diff
            
            # Clamp to reasonable timezone range (-12 to +14)
            offset_hours = max(-12, min(14, offset_hours))
            
            print(f"Detected timezone offset: GMT+{offset_hours} (server time: {server_dt_str}, {TIMEZONE} time: {budapest_now.strftime('%d.%m.%Y %H:%M')})", flush=True)

            
            return offset_hours
            
        except Exception as e:
            print(f"Warning: Failed to calculate timezone offset: {e}", flush=True)
            return 0  # Default UTC on error
    
    def parse_freerolls(self, html_content: str) -> List[Dict]:
        """Parse the freeroll list from HTML content"""
        soup = BeautifulSoup(html_content, 'lxml')
        freeroll_list = soup.find('ul', id='freerollList')
        
        if not freeroll_list:
            return []
        
        # Calculate timezone offset from server time
        timezone_offset = self._calculate_timezone_offset(html_content)
        
        tournaments = []
        list_items = freeroll_list.find_all('li', class_='row')
        
        for item in list_items:
            tournament = self._parse_tournament_item(item)
            if tournament:
                # Add calculated timezone offset to each tournament
                tournament['timezone_offset'] = timezone_offset
                tournaments.append(tournament)
        
        return tournaments
    
    def _parse_tournament_item(self, item) -> Optional[Dict]:
        """Parse a single tournament list item"""
        try:
            tournament = {}
            
            # Check if it's a hot event
            hot_ribbon = item.find('div', class_='ribbon-hot')
            tournament['is_hot_event'] = hot_ribbon is not None
            
            # Parse time and date from the first column
            time_col = item.find('div', class_='col-4')
            if time_col:
                time_div = time_col.find('div', class_='f-size-30-576-40')
                date_div = time_col.find('div', class_='f-size-15-576-20')
                
                if time_div:
                    time_text = time_div.text.strip()
                    tournament['time'] = time_text
                    
                if date_div:
                    tournament['date'] = date_div.text.strip()
                
                # Registration until
                reg_div = time_col.find('div', class_='pt-1')
                if reg_div:
                    reg_span = reg_div.find('span', class_='f-weight-500')
                    if reg_span:
                        tournament['registration_until'] = reg_span.text.strip()
                
                # Prize pool - find the yellow colored div
                prize_div = time_col.find('div', class_='c-yellow')
                if prize_div:
                    # Remove SVG elements and get text
                    for svg in prize_div.find_all('svg'):
                        svg.decompose()
                    prize_text = prize_div.text.strip()
                    tournament['prize_pool'] = prize_text
            
            # Parse poker room and tournament name from the second column
            info_col = item.find('div', class_='col-8')
            if info_col:
                # Poker room
                title_room = info_col.find('div', class_='title-room')
                if title_room:
                    room_link = title_room.find('a')
                    if room_link:
                        room_text = room_link.text.strip()
                        tournament['poker_room'] = room_text
                
                # Tournament name
                name_span = info_col.find('span', class_='fl-text-name')
                if name_span:
                    # Remove the zoom icon SVG if present
                    for svg in name_span.find_all('svg'):
                        svg.decompose()
                    tournament['tournament_name'] = name_span.text.strip()
                    # Event URL can be found in <a> tags nearby or room link
                    parent_a = name_span.find_parent('a')
                    if parent_a and parent_a.get('href'):
                        event_url = parent_a.get('href')
                        if event_url.startswith('/'):
                            event_url = self.url.rstrip('/') + event_url
                        tournament['url'] = event_url
                    elif title_room and title_room.find('a') and title_room.find('a').get('href'):
                        # Fallback to room link
                        rurl = title_room.find('a').get('href')
                        if rurl.startswith('/'):
                            rurl = self.url.rstrip('/') + rurl
                        tournament['url'] = rurl
                    else:
                        tournament['url'] = self.url
                
                # Password
                password_div = info_col.find('div', id=True)
                if password_div and 'Password' in password_div.text:
                    # Check for actual password
                    password_span = password_div.find('strong', class_='c-red-1')
                    if password_span:
                        tournament['password'] = password_span.text.strip()
                    else:
                        # Check for "not required" badge
                        badge = password_div.find('span', class_='fl-badge')
                        if badge and 'not required' in badge.text:
                            tournament['password'] = None
                            tournament['password_required'] = False
                        else:
                            tournament['password_required'] = True
                
                # Additional features (bonuses, special notes, etc.)
                features = []
                feature_divs = info_col.find_all('div', class_='pt-1')
                for fdiv in feature_divs:
                    if fdiv.find('svg') and fdiv.find('div', class_='d-table'):
                        feature_text = fdiv.find('div', class_='d-table').text.strip()
                        if feature_text and 'Password' not in fdiv.text:
                            features.append(feature_text)
                
                if features:
                    tournament['features'] = features
            
            # Only return if we have at least basic info
            if tournament.get('time') and tournament.get('prize_pool'):
                return tournament
            
        except Exception as e:
            # Skip items that can't be parsed
            print(f"Warning: Failed to parse tournament item: {e}", flush=True)
            return None
        
        return None
    
    async def get_tournaments(self) -> List[TournamentEvent]:
        """Fetch and parse all tournaments"""
        html_content = await self.fetch_page()
        tournaments = await asyncio.to_thread(self.parse_freerolls, html_content)
        
        events: List[TournamentEvent] = []
        for tournament in tournaments:
            try:
                # Parse date and time with timezone
                date_str = tournament.get('date')  # e.g., "24.11.2025"
                time_str = tournament.get('time')  # e.g., "21:00"
                tz_offset = tournament.get('timezone_offset', 1)  # Get calculated offset, default to GMT+1
                
                if not date_str or not time_str:
                    continue

                # Combine date and time (date_str already contains the year)
                dt_str = f"{date_str} {time_str}"
                try:
                    # Format: "24.11.2025 21:00"
                    dt_naive = datetime.strptime(dt_str, "%d.%m.%Y %H:%M")
                except:
                    try:
                        # Try alternative format: "11/24/2025 21:00"
                        dt_naive = datetime.strptime(dt_str, "%m/%d/%Y %H:%M")
                    except:
                        continue

                # The times on freerollpass.com in raw HTML are rendered in UK time (Europe/London)
                # We attach the London timezone to the naive datetime, and convert it to Budapest time.
                # This perfectly handles both CET/CEST and GMT/BST DST offsets!
                source_tz = ZoneInfo("Europe/London")
                dt_aware = dt_naive.replace(tzinfo=source_tz)
                
                budapest_tz = ZoneInfo(TIMEZONE)
                dt_budapest = dt_aware.astimezone(budapest_tz)


                # Get password
                password = tournament.get('password', 'n/a')
                if password is None:
                    password = "not required"

                events.append({
                    "date": dt_budapest.date(),
                    "time": dt_budapest.time(),
                    "is_all_day": False,  # freerollpass.com always has specific times
                    "room": tournament.get('poker_room', 'Unknown'),
                    "name": tournament.get('tournament_name', 'Unknown'),
                    "prize": tournament.get('prize_pool', 'n/a'),
                    "password": password,
                    "source": "freerollpass.com",
                    "url": tournament.get('url', self.url)
                })
            except Exception as e:
                continue

        return events
