"""Prize Value Object with currency, amount, and ticket recognition."""

import re
from dataclasses import dataclass
from typing import Optional, Any


@dataclass(frozen=True)
class Prize:
    """Immutable Value Object representing tournament prize pool."""
    raw: str
    amount: int
    currency: str = "USD"
    is_ticket: bool = False

    @classmethod
    def from_raw(cls, raw_str: Optional[str]) -> "Prize":
        """Intelligently parse raw prize string into structured Prize object."""
        if not raw_str or not raw_str.strip() or raw_str.strip().lower() in ("n/a", "none", "-"):
            return cls(raw="n/a", amount=0, currency="n/a", is_ticket=False)

        raw = raw_str.strip()

        # Check currency / ticket indicators
        is_ticket = bool(re.search(r"\b(ticket|t\$|t€)\b", raw, re.IGNORECASE))
        currency = "USD"
        if "€" in raw or "eur" in raw.lower():
            currency = "EUR"
        elif "£" in raw or "gbp" in raw.lower():
            currency = "GBP"
        elif "t$" in raw.lower():
            currency = "T$"

        # Extract numeric integer amount
        amount = 0
        try:
            clean_str = raw.replace(",", "").replace(".", "")
            match = re.search(r"\d+", clean_str)
            if match:
                amount = int(match.group())
        except Exception:
            pass

        return cls(raw=raw, amount=amount, currency=currency, is_ticket=is_ticket)

    def is_high_value(self, threshold: int = 500) -> bool:
        """Check if numeric prize value meets or exceeds the threshold."""
        return self.amount >= threshold

    def __str__(self) -> str:
        return self.raw

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, Prize):
            return (
                self.amount == other.amount
                and self.currency == other.currency
                and self.is_ticket == other.is_ticket
            )
        return False

    def __hash__(self) -> int:
        return hash((self.amount, self.currency, self.is_ticket))
