"""Configuration and settings management for Botzilla."""

from dataclasses import dataclass, field
import json
import os
import sys
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv

# Load .env file automatically
load_dotenv()


@dataclass
class LoggingSettings:
    level: str = "INFO"
    file: str = "botzilla.log"
    max_mb: int = 5
    backup_count: int = 3

    @property
    def max_bytes(self) -> int:
        return self.max_mb * 1024 * 1024


@dataclass
class AlertThresholds:
    warning: int = 60
    urgent: int = 10


@dataclass
class Settings:
    discord_token: str = ""
    channel_id: Optional[int] = None
    allowed_channel_ids: List[int] = field(default_factory=list)
    timezone: str = "Europe/Budapest"
    locale: str = "hu"
    command_prefix: str = "!"
    command_suffix: str = ""
    url_password: str = "https://freeroll-password.com/"
    url_pass: str = "https://freerollpass.com/"
    high_value_threshold: int = 500
    watcher_sleep_seconds: int = 300
    status_rotator_sleep_seconds: int = 20
    status_messages: List[str] = field(default_factory=list)
    alert_thresholds: AlertThresholds = field(default_factory=AlertThresholds)
    logging: LoggingSettings = field(default_factory=LoggingSettings)
    dry_run: bool = False
    db_file: str = "botzilla.db"


def load_raw_config() -> Dict[str, Any]:
    """Find and load config.json from various possible paths."""
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    possible_paths = [
        "config.json",
        os.path.join(base_dir, "config.json"),
        os.path.join(os.getcwd(), "config.json"),
    ]
    for config_path in possible_paths:
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading config from {config_path}: {e}", file=sys.stderr)
                continue
    return {}


def get_settings() -> Settings:
    """Load settings from environment variables and config.json."""
    raw = load_raw_config()

    token = os.environ.get("DISCORD_TOKEN") or raw.get("discord_token", "")
    dry_run_env = os.environ.get("DRY_RUN", "")
    dry_run = bool(dry_run_env and dry_run_env.lower() not in ("0", "false", "no"))

    channel_id = raw.get("channel_id")
    allowed_channels = raw.get("allowed_channel_ids", [])
    if not allowed_channels and channel_id:
        allowed_channels = [channel_id]

    log_dict = raw.get("logging", {})
    logging_cfg = LoggingSettings(
        level=log_dict.get("level", "INFO"),
        file=log_dict.get("file", "botzilla.log"),
        max_mb=log_dict.get("max_mb", 5),
        backup_count=log_dict.get("backup_count", 3),
    )

    alert_dict = raw.get("alert_thresholds", {})
    alert_cfg = AlertThresholds(
        warning=alert_dict.get("warning", 60),
        urgent=alert_dict.get("urgent", 10),
    )

    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    db_file = os.path.join(base_dir, "botzilla.db")

    return Settings(
        discord_token=token,
        channel_id=channel_id,
        allowed_channel_ids=allowed_channels,
        timezone=raw.get("timezone", "Europe/Budapest"),
        locale=raw.get("locale", "hu"),
        command_prefix=raw.get("command_prefix", "!"),
        command_suffix=raw.get("command_suffix", ""),
        url_password=raw.get("url_password", "https://freeroll-password.com/"),
        url_pass=raw.get("url_pass", "https://freerollpass.com/"),
        high_value_threshold=raw.get("high_value_threshold", 500),
        watcher_sleep_seconds=raw.get("watcher_sleep_seconds", 300),
        status_rotator_sleep_seconds=raw.get("status_rotator_sleep_seconds", 20),
        status_messages=raw.get("status_messages", []),
        alert_thresholds=alert_cfg,
        logging=logging_cfg,
        dry_run=dry_run,
        db_file=db_file,
    )
