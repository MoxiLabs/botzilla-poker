"""Centralized HTTP network client with retry, rate-limiting, and User-Agent rotation."""

import asyncio
import itertools
from typing import Optional, List, Dict
import aiohttp
from ...utils.logger import log

DEFAULT_USER_AGENTS = [
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) "
        "Gecko/20100101 Firefox/125.0"
    ),
]


class HttpFetcher:
    """Async HTTP fetcher providing retry with exponential backoff and rate limiting."""

    def __init__(
        self,
        session: Optional[aiohttp.ClientSession] = None,
        user_agents: Optional[List[str]] = None,
        max_concurrency: int = 5,
        default_timeout: float = 30.0,
    ):
        self._session = session
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._user_agents = itertools.cycle(user_agents or DEFAULT_USER_AGENTS)
        self.default_timeout = default_timeout

    @property
    def session(self) -> Optional[aiohttp.ClientSession]:
        """Get the active aiohttp.ClientSession."""
        return self._session

    @session.setter
    def session(self, session: Optional[aiohttp.ClientSession]):
        """Set or replace the aiohttp.ClientSession."""
        self._session = session

    def get_random_headers(self, custom_headers: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        """Generates realistic standard browser headers with rotated User-Agent."""
        ua = next(self._user_agents)
        headers = {
            "User-Agent": ua,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,hu;q=0.8",
            "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1",
        }
        if "Firefox" in ua:
            headers.pop("Sec-Ch-Ua", None)
            headers.pop("Sec-Ch-Ua-Mobile", None)
            headers.pop("Sec-Ch-Ua-Platform", None)
        elif "Macintosh" in ua:
            headers["Sec-Ch-Ua-Platform"] = '"macOS"'
        elif "Linux" in ua:
            headers["Sec-Ch-Ua-Platform"] = '"Linux"'

        if custom_headers:
            headers.update(custom_headers)
        return headers

    async def fetch_text(
        self,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None,
        max_retries: int = 3,
        backoff_factor: float = 1.0,
    ) -> str:
        """
        Fetch HTML or text from given URL with retries on transient errors.
        """
        request_headers = self.get_random_headers(headers)
        timeout_val = timeout or self.default_timeout
        client_timeout = aiohttp.ClientTimeout(total=timeout_val)

        last_error = None
        for attempt in range(1, max_retries + 1):
            async with self._semaphore:
                try:
                    if self._session and not self._session.closed:
                        async with self._session.get(
                            url, headers=request_headers, timeout=client_timeout
                        ) as response:
                            response.raise_for_status()
                            return await response.text()
                    else:
                        async with aiohttp.ClientSession() as session:
                            async with session.get(
                                url, headers=request_headers, timeout=client_timeout
                            ) as response:
                                response.raise_for_status()
                                return await response.text()
                except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                    last_error = e
                    if attempt < max_retries:
                        sleep_time = backoff_factor * (2 ** (attempt - 1))
                        log.warning(
                            f"HTTP GET {url} failed (attempt {attempt}/{max_retries}): {e}. Retrying in {sleep_time}s..."
                        )
                        await asyncio.sleep(sleep_time)
                    else:
                        log.error(f"HTTP GET {url} failed permanently after {max_retries} attempts: {e}")

        raise last_error or RuntimeError(f"Failed to fetch {url}")
