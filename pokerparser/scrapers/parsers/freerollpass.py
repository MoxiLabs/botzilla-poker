"""Pure HTML parser for freerollpass.com."""

import re
from datetime import datetime
from typing import List
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup

from .base import BaseHtmlParser
from ...domain.models import Tournament
from ...domain.poker_room import PokerRoom
from ...domain.prize import Prize
from ...utils.logger import log


class FreerollPassParser(BaseHtmlParser):
    """Parses freeroll tournaments from freerollpass.com HTML."""

    def __init__(
        self,
        base_url: str = "https://freerollpass.com/",
        timezone: str = "Europe/Budapest",
    ):
        super().__init__(base_url=base_url, timezone=timezone)

    @property
    def source_name(self) -> str:
        return "freerollpass.com"

    def parse(self, html_content: str) -> List[Tournament]:
        """Extract tournaments from HTML content."""
        if not html_content:
            return []

        soup = BeautifulSoup(html_content, "lxml")
        freeroll_list = soup.find("ul", id="freerollList")
        if not freeroll_list:
            if len(html_content) > 500:
                log.warning(
                    f"[{self.source_name}] Element '#freerollList' not found in HTML ({len(html_content)} bytes). Site layout might have changed."
                )
            return []

        tournaments: List[Tournament] = []
        list_items = freeroll_list.find_all("li", class_="row")

        for item in list_items:
            try:
                # Column 1: Time, Date, Prize
                time_col = item.find("div", class_="col-4")
                if not time_col:
                    continue

                time_div = time_col.find("div", class_="f-size-30-576-40")
                date_div = time_col.find("div", class_="f-size-15-576-20")
                prize_div = time_col.find("div", class_="c-yellow")

                if not time_div or not date_div or not prize_div:
                    continue

                time_text = time_div.text.strip()
                date_text = date_div.text.strip()

                for svg in prize_div.find_all("svg"):
                    svg.decompose()
                prize_text = prize_div.text.strip()

                # Column 2: Room, Name, URL, Password
                info_col = item.find("div", class_="col-8")
                if not info_col:
                    continue

                room_text = "Unknown"
                title_room = info_col.find("div", class_="title-room")
                if title_room and title_room.find("a"):
                    room_text = title_room.find("a").text.strip()

                name_text = "Unknown"
                name_span = info_col.find("span", class_="fl-text-name")
                event_url = self.base_url
                if name_span:
                    for svg in name_span.find_all("svg"):
                        svg.decompose()
                    name_text = name_span.text.strip()

                    parent_a = name_span.find_parent("a")
                    if parent_a and parent_a.get("href"):
                        href = parent_a.get("href")
                        event_url = href if not href.startswith("/") else self.base_url.rstrip("/") + href
                    elif title_room and title_room.find("a") and title_room.find("a").get("href"):
                        href = title_room.find("a").get("href")
                        event_url = href if not href.startswith("/") else self.base_url.rstrip("/") + href

                # Extract password robustly across all freerollpass.com variations
                password = "not required"
                password_div = info_col.find(lambda tag: tag.name == "div" and "Password" in tag.text)
                if password_div:
                    full_text = password_div.text.strip()
                    if "will be available at" in full_text:
                        password = "n/a"
                    elif "not required" in full_text.lower() or "no password" in full_text.lower():
                        password = "not required"
                    else:
                        # Non-label candidate badges (e.g. <strong class="fl-badge bg-red">cooler</strong>)
                        candidates = password_div.find_all(["strong", "span", "b"])
                        pw_candidates = [
                            c.text.strip()
                            for c in candidates
                            if "Password" not in c.text and c.text.strip()
                        ]
                        if pw_candidates:
                            password = pw_candidates[-1]
                        else:
                            # Fallback regex parsing
                            match = re.search(r"Password\s*:\s*([^\s\n\r]+)", full_text, re.IGNORECASE)
                            if match:
                                password = match.group(1).strip()
                            else:
                                password = "n/a"

                # Parse DateTime (Source times are in UTC)
                dt_str = f"{date_text} {time_text}"
                try:
                    dt_naive = datetime.strptime(dt_str, "%d.%m.%Y %H:%M")
                except ValueError:
                    try:
                        dt_naive = datetime.strptime(dt_str, "%m/%d/%Y %H:%M")
                    except ValueError:
                        continue

                source_tz = ZoneInfo("UTC")
                dt_aware = dt_naive.replace(tzinfo=source_tz)

                target_tz = ZoneInfo(self.timezone)
                dt_target = dt_aware.astimezone(target_tz)

                tournaments.append(
                    Tournament(
                        name=name_text,
                        room=PokerRoom.from_raw(room_text),
                        date=dt_target.date(),
                        time=dt_target.time(),
                        is_all_day=False,
                        prize=Prize.from_raw(prize_text),
                        password=password,
                        source=self.source_name,
                        url=event_url,
                    )
                )
            except Exception as e:
                log.warning(f"[{self.source_name}] Error parsing tournament item: {e}", exc_info=True)
                continue

        return tournaments
