"""PokerRoom Value Object with identifier, normalization, and logo helpers."""

from dataclasses import dataclass
from typing import Optional, Union, Any


@dataclass(frozen=True)
class PokerRoom:
    """Immutable Value Object representing a poker room or network."""
    name: str
    clean_id: str

    @property
    def logo_filename(self) -> str:
        """Returns standard logo filename for assets (e.g. 'pokerstars-x2.png')."""
        return f"{self.clean_id}-x2.png"

    @classmethod
    def from_raw(cls, raw_name: Optional[Union[str, "PokerRoom"]]) -> "PokerRoom":
        """Factory method to sanitize and normalize poker room names."""
        if isinstance(raw_name, PokerRoom):
            return raw_name

        if not raw_name or not str(raw_name).strip():
            return cls(name="Unknown", clean_id="unknown")

        name = str(raw_name).strip()
        clean_id = name.lower().replace(" ", "").replace("-", "").replace(".", "")

        # Canonical name normalizations
        if clean_id in ("pokerstars", "stars", "ps"):
            name = "PokerStars"
            clean_id = "pokerstars"
        elif clean_id in ("888poker", "888", "888p"):
            name = "888poker"
            clean_id = "888poker"
        elif clean_id in ("ggpoker", "gg", "natural8"):
            name = "GGPoker"
            clean_id = "ggpoker"
        elif clean_id in ("wpt", "wptglobal"):
            name = "WPT Global"
            clean_id = "wpt"
        elif clean_id in ("partypoker", "party"):
            name = "PartyPoker"
            clean_id = "partypoker"
        elif clean_id in ("betonline", "bol"):
            name = "BetOnline"
            clean_id = "betonline"
        elif clean_id in ("unibet", "unibetpoker"):
            name = "Unibet"
            clean_id = "unibet"

        return cls(name=name, clean_id=clean_id)

    def __str__(self) -> str:
        return self.name

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, PokerRoom):
            return self.clean_id == other.clean_id
        return False

    def __hash__(self) -> int:
        return hash(self.clean_id)
