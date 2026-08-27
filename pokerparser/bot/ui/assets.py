import asyncio
import os
from typing import Optional, Union, Set
import aiohttp

from ...domain.poker_room import PokerRoom
from ...utils.logger import log


class AssetManager:
    """Manages poker room logos, local caching, and rate-limited async downloading."""

    def __init__(
        self,
        base_dir: Optional[str] = None,
        session: Optional[aiohttp.ClientSession] = None,
        max_concurrency: int = 5,
    ):
        if base_dir:
            self.logos_dir = base_dir
        else:
            project_root = os.path.dirname(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            )
            self.logos_dir = os.path.join(project_root, "assets", "logos")
        self._session = session
        self._known_logos: Set[str] = set()
        self._failed_downloads: Set[str] = set()
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._scan_existing_logos()

    def _scan_existing_logos(self):
        """Pre-populate in-memory cache of existing logo files and ensure they are 1:1 squarified."""
        if os.path.exists(self.logos_dir):
            try:
                files = os.listdir(self.logos_dir)
                for f in files:
                    full_path = os.path.join(self.logos_dir, f)
                    if os.path.isfile(full_path) and f.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
                        self.squarify_file(full_path)
                self._known_logos.update(files)
            except Exception as e:
                log.debug(f"Failed to scan/squarify existing logos: {e}")

    @property
    def session(self) -> Optional[aiohttp.ClientSession]:
        """Get the active aiohttp.ClientSession."""
        return self._session

    @session.setter
    def session(self, session: Optional[aiohttp.ClientSession]):
        """Set or replace the aiohttp.ClientSession."""
        self._session = session

    def get_logo_filename(self, room: Union[PokerRoom, str]) -> str:
        """Returns normalized filename for a given room or PokerRoom object."""
        poker_room = room if isinstance(room, PokerRoom) else PokerRoom.from_raw(room)
        return poker_room.logo_filename

    def get_logo_path(self, room: Union[PokerRoom, str]) -> str:
        """Returns full local file path for room logo."""
        return os.path.join(self.logos_dir, self.get_logo_filename(room))

    async def ensure_logo(self, room: Union[PokerRoom, str]) -> Optional[str]:
        """Checks if logo exists; if not, attempts download from CDN with concurrency limits. Returns path if available."""
        filename = self.get_logo_filename(room)
        path = self.get_logo_path(room)

        if filename in self._known_logos:
            return path

        if filename in self._failed_downloads:
            return None

        exists = await asyncio.to_thread(os.path.exists, path)
        if exists:
            await asyncio.to_thread(self.squarify_file, path)
            self._known_logos.add(filename)
            return path

        await asyncio.to_thread(os.makedirs, self.logos_dir, exist_ok=True)
        dl_url = f"https://freerollpass.com/storage/app/media/logo/{filename}"

        async with self._semaphore:
            try:
                headers = {"User-Agent": "Mozilla/5.0"}
                timeout = aiohttp.ClientTimeout(total=5)

                if self._session and not self._session.closed:
                    async with self._session.get(dl_url, headers=headers, timeout=timeout) as resp:
                        if resp.status == 200:
                            content = await resp.read()
                            await asyncio.to_thread(self._save_file, path, content)
                            self._known_logos.add(filename)
                            return path
                        else:
                            self._failed_downloads.add(filename)
                else:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(dl_url, headers=headers, timeout=timeout) as resp:
                            if resp.status == 200:
                                content = await resp.read()
                                await asyncio.to_thread(self._save_file, path, content)
                                self._known_logos.add(filename)
                                return path
                            else:
                                self._failed_downloads.add(filename)
            except Exception as ex:
                self._failed_downloads.add(filename)
                log.debug(f"Failed to download logo for {room}: {ex}")

        return None

    @classmethod
    def squarify_file(cls, path: str):
        """Ensures a local image file on disk is padded to 1:1 square with transparent background."""
        try:
            from PIL import Image
            with Image.open(path) as img:
                w, h = img.size
                if w == h:
                    return
            with open(path, "rb") as f:
                content = f.read()
            processed = cls._squarify_image_bytes(content)
            with open(path, "wb") as f:
                f.write(processed)
        except Exception as e:
            log.debug(f"Failed to squarify existing logo file {path}: {e}")

    @classmethod
    def _save_file(cls, path: str, content: bytes):
        """Thread-safe synchronous file writer with automatic 1:1 square canvas padding."""
        processed = cls._squarify_image_bytes(content)
        with open(path, "wb") as f:
            f.write(processed)

    @staticmethod
    def _squarify_image_bytes(content: bytes, padding_ratio: float = 0.05) -> bytes:
        """Pads rectangular images to 1:1 square canvas with transparent background so Discord thumbnail does not crop."""
        try:
            from PIL import Image
            import io

            with Image.open(io.BytesIO(content)) as img:
                img = img.convert("RGBA")
                w, h = img.size
                if w == h and padding_ratio == 0:
                    return content

                max_side = max(w, h)
                canvas_size = int(max_side * (1.0 + 2 * padding_ratio))
                square_img = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))

                offset_x = (canvas_size - w) // 2
                offset_y = (canvas_size - h) // 2
                square_img.paste(img, (offset_x, offset_y), img)

                out = io.BytesIO()
                square_img.save(out, format="PNG")
                return out.getvalue()
        except Exception as e:
            log.debug(f"Could not squarify image: {e}")
            return content
