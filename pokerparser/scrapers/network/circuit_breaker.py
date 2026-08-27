"""Circuit Breaker pattern implementation for external scraper resilience."""

from datetime import datetime, timedelta
from enum import Enum
from typing import Optional
from ...utils.logger import log


class CircuitState(str, Enum):
    CLOSED = "CLOSED"      # Normal operation: all requests allowed
    OPEN = "OPEN"          # Tripped: requests blocked during cooldown
    HALF_OPEN = "HALF_OPEN"# Trial period: allows probe request after cooldown


class CircuitBreaker:
    """
    Prevents hammering persistently failing external scraper endpoints.
    Automatically trips after consecutive failures and recovers via probe attempts.
    """

    def __init__(
        self,
        name: str = "default",
        failure_threshold: int = 3,
        cooldown_seconds: float = 600.0,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self.state: CircuitState = CircuitState.CLOSED
        self.failure_count: int = 0
        self.last_state_change: datetime = datetime.now()

    def can_execute(self, now: Optional[datetime] = None) -> bool:
        """Determines if a request is permitted based on circuit state and cooldown."""
        current_time = now or datetime.now()

        if self.state == CircuitState.CLOSED:
            return True

        if self.state == CircuitState.OPEN:
            elapsed = (current_time - self.last_state_change).total_seconds()
            if elapsed >= self.cooldown_seconds:
                log.info(
                    f"[{self.name}] Circuit Breaker cooldown expired ({elapsed:.1f}s >= {self.cooldown_seconds}s). Transitioning from OPEN to HALF_OPEN."
                )
                self.state = CircuitState.HALF_OPEN
                self.last_state_change = current_time
                return True
            return False

        # HALF_OPEN allows probe attempts
        return True

    def record_success(self):
        """Records a successful request, resetting state to CLOSED."""
        if self.state != CircuitState.CLOSED:
            log.info(f"[{self.name}] Circuit Breaker recovered successfully. Transitioning to CLOSED.")
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_state_change = datetime.now()

    def record_failure(self, error: Exception):
        """Records a request failure, tripping circuit if threshold is reached."""
        self.failure_count += 1
        current_time = datetime.now()

        if self.state == CircuitState.HALF_OPEN:
            log.warning(
                f"[{self.name}] Probe request failed in HALF_OPEN state: {error}. Re-opening Circuit Breaker for {self.cooldown_seconds}s."
            )
            self.state = CircuitState.OPEN
            self.last_state_change = current_time
        elif self.state == CircuitState.CLOSED and self.failure_count >= self.failure_threshold:
            log.warning(
                f"[{self.name}] Failure threshold reached ({self.failure_count}/{self.failure_threshold}): {error}. Tripping Circuit Breaker to OPEN for {self.cooldown_seconds}s."
            )
            self.state = CircuitState.OPEN
            self.last_state_change = current_time
