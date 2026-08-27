"""Pure HTML parser for freeroll-password.com."""

import re
from datetime import datetime, timezone, timedelta
from typing import List
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup

from .base import BaseHtmlParser
from ...domain.models import Tournament
from ...domain.poker_room import PokerRoom
from ...domain.prize import Prize
from ...utils.logger import log


class FreeRollPasswordParser(BaseHtmlParser):
    """Parses freeroll tournaments from freeroll-password.com HTML."""

    def __init__(
        self,
        base_url: str = "https://www.freeroll-password.com/",
        timezone: str = "Europe/Budapest",
    ):
        super().__init__(base_url=base_url, timezone=timezone)

    @property
    def source_name(self) -> str:
        return "freeroll-password.com"

    def parse(self, html_content: str) -> List[Tournament]:
        """Extract tournaments from HTML content."""
        if not html_content:
            return []

        soup = BeautifulSoup(html_content, "lxml")
        wrapper = soup.select_one("div.pt-cv-wrapper")
        if not wrapper:
            if len(html_content) > 500:
                log.warning(
                    f"[{self.source_name}] Wrapper 'div.pt-cv-wrapper' not found in HTML ({len(html_content)} bytes). Site layout might have changed."
                )
            return []

        events: List[Tournament] = []
        items = wrapper.select(".pt-cv-content-item")

        for item in items:
            try:
                excerpt = item.select_one(".fpexcerpt")
                if not excerpt:
                    continue

                # Room
                room_span = excerpt.select_one(".exroom")
                room = "Unknown"
                if room_span and room_span.next_sibling:
                    room = str(room_span.next_sibling).strip()

                # Date
                date_span = excerpt.select_one(".date-display-single")
                date_str = date_span.text.strip() if date_span else None

                # Time
                time_span = excerpt.select_one(".extime")
                time_str = None
                if time_span and time_span.next_sibling:
                    time_str = str(time_span.next_sibling).strip()

                # Prize
                prize_span = excerpt.select_one(".exprize")
                prize = "n/a"
                if prize_span and prize_span.next_sibling:
                    prize = str(prize_span.next_sibling).strip()

                # Name
                name_span = excerpt.select_one(".exname")
                name = "Unknown"
                if name_span and name_span.next_sibling:
                    name = str(name_span.next_sibling).strip()

                # Password
                password_span = excerpt.select_one(".expass2")
                password = password_span.text.strip() if password_span else "n/a"

                # URL
                item_link = item.select_one("a")
                event_url = self.base_url
                if item_link and item_link.get("href"):
                    event_url = item_link.get("href")
                    if event_url.startswith("/"):
                        base_match = re.match(r"(https?://[^/]+)", self.base_url)
                        base_domain = base_match.group(1) if base_match else "https://www.freeroll-password.com"
                        event_url = base_domain + event_url

                if date_str:
                    event_date = datetime.strptime(date_str, "%B %d, %Y").date()
                    event_time = None
                    is_all_day = False

                    if time_str:
                        try:
                            # Format: "22:30 GMT+2"
                            tz_match = re.search(r"GMT([+-]\d+)", time_str)
                            tz_offset = int(tz_match.group(1)) if tz_match else 0

                            time_clean = time_str.split()[0]  # HH:MM
                            dt_str = f"{date_str} {time_clean}"
                            dt_naive = datetime.strptime(dt_str, "%B %d, %Y %H:%M")

                            source_tz = timezone(timedelta(hours=tz_offset))
                            dt_aware = dt_naive.replace(tzinfo=source_tz)

                            target_tz = ZoneInfo(self.timezone)
                            dt_target = dt_aware.astimezone(target_tz)

                            event_time = dt_target.time()
                            event_date = dt_target.date()
                        except Exception:
                            is_all_day = True
                            event_time = None
                            name = f"{name} ({time_str})"
                    else:
                        is_all_day = True

                    events.append(
                        Tournament(
                            name=name,
                            room=PokerRoom.from_raw(room),
                            date=event_date,
                            time=event_time,
                            is_all_day=is_all_day,
                            prize=Prize.from_raw(prize),
                            password=password,
                            source=self.source_name,
                            url=event_url,
                        )
                    )
            except Exception as e:
                log.warning(f"[{self.source_name}] Error parsing tournament item: {e}", exc_info=True)
                continue

        return events
