# Botzilla

Botzilla is an asynchronous Discord bot and poker freeroll tournament aggregator. It scrapes, normalizes, deduplicates, and broadcasts upcoming online poker freeroll tournaments and passwords in real-time. Built on Python with `discord.py` (Components V2), it features modular Clean Architecture, event-driven pub/sub messaging, fault-tolerant networking with circuit breakers, and interactive UI views.

---

## Key Features

- **Multi-Source Scraping and Data Fusion**: Concurrently fetches tournament schedules from multiple sources (such as `freeroll-password.com` and `freerollpass.com`). Tournament entries are merged and deduplicated using SHA-256 event fingerprinting to combine the most accurate passwords, prize pools, and source links.
- **Resilient Network Layer**: Implements the Circuit Breaker pattern (`CLOSED`, `OPEN`, `HALF_OPEN`), exponential backoff retries, concurrency semaphores, and rotating browser User-Agents to prevent request failures and protect upstream endpoints.
- **Discord Components V2 UI**: Modern layout containers with color-coded accent borders (Gold for high-value prize pools, Green for standard events, Red for urgent alerts, Slate Blue for help and informational messages). Includes interactive dropdown menus for filtering by poker room, carousel pagination, and one-click ephemeral password copy buttons.
- **Automated Broadcasts and Timed Alerts**:
  - Daily tournament summaries announcing newly discovered freerolls.
  - Advance warning alerts (default: 60 minutes prior to start).
  - Urgent alerts (default: 10 minutes prior to start).
  - Configurable presence rotator cycling status messages.
- **Inversion of Control (IoC) and Clean Architecture**: Modular dependency injection container (`AppContainer`) separating domain entities, services, storage, networking, and UI layers for maximum maintainability and testability.
- **Event-Driven Messaging**: Asynchronous in-memory `EventBus` for decoupled communication between background scrapers, domain services, and Discord broadcasters.
- **Persistent Storage**: Lightweight asynchronous SQLite (`aiosqlite`) persistence with batch lookups, chunked transactions, auto-reconnection, and automatic cleanup of expired events.
- **Internationalization (i18n)**: Multi-language support with fallback mechanisms (English `en` and Hungarian `hu`).

---

## Architecture Overview

```
                        +----------------------+
                        |   External Scrapers  |
                        +----------+-----------+
                                   |
                                   v
                        +----------------------+
                        |   Scraper Manager    |
                        |   & Data Fusion      |
                        +----------+-----------+
                                   |
                                   v
+------------------+    +----------------------+    +--------------------+
|  EventRepository |<-->|  Tournament Service  |--->|    Event Bus       |
|  (aiosqlite)     |    |  & Alert Service     |    +---------+----------+
+------------------+    +----------------------+              |
                                                              v
+------------------+    +----------------------+    +--------------------+
|  Discord UI /    |<---|  Discord Broadcaster |<---| Subscribers        |
|  Components V2   |    |  & Cogs              |    +--------------------+
+------------------+    +----------------------+
```

---

## Project Structure

```
botzilla/
|-- assets/
|   `-- logos/                  # Cached poker room logo images
|-- config.json                 # Main configuration file
|-- locales/                    # Localization dictionary files (en.json, hu.json)
|-- pokerparser/
|   |-- __init__.py
|   |-- __main__.py             # Module entry point
|   |-- container.py            # IoC Dependency Injection Container (AppContainer)
|   |-- bot/
|   |   |-- broadcaster.py      # Event listener and message broadcaster
|   |   |-- client.py           # Custom PokerBot client and setup lifecycle
|   |   |-- cogs/
|   |   |   |-- admin.py        # Admin maintenance commands (!sync, !clear_commands)
|   |   |   |-- commands.py     # Hybrid user commands (/day, /next, /help, /test, /debug)
|   |   |   `-- tasks.py        # Periodic background loops (watcher, status rotator)
|   |   `-- ui/
|   |       |-- assets.py       # Asynchronous logo manager and CDN downloader
|   |       |-- components.py   # Discord Components V2 layout and container builder
|   |       `-- views.py        # Interactive UI views (FreerollPaginatorView)
|   |-- config/
|   |   |-- i18n.py             # Translation and localization service
|   |   `-- settings.py         # Typed settings loader (.env and config.json)
|   |-- domain/
|   |   |-- models.py           # Tournament domain model and SHA-256 deduplication
|   |   |-- poker_room.py       # PokerRoom entity and normalization
|   |   `-- prize.py            # Prize value object and currency parser
|   |-- events/
|   |   |-- bus.py              # In-memory asynchronous EventBus
|   |   `-- events.py           # Domain events definitions
|   |-- scrapers/
|   |   |-- base.py             # Abstract scraper interface
|   |   |-- freeroll_password.py# Scraper for freeroll-password.com
|   |   |-- freerollpass.py     # Scraper for freerollpass.com
|   |   |-- manager.py          # Scraper orchestrator and tournament fusion engine
|   |   |-- network/
|   |   |   |-- circuit_breaker.py # Circuit breaker implementation
|   |   |   `-- http_client.py     # Resilient async HTTP client with retries
|   |   `-- parsers/            # HTML parsing strategies
|   |-- services/
|   |   |-- alert_service.py    # Alert scheduling, deduplication, and cleanup
|   |   `-- tournament_service.py # Tournament caching, querying, and filtering
|   |-- storage/
|   |   |-- database.py         # Asynchronous SQLite connection and schema manager
|   |   `-- repository.py       # Database repository for tracked events
|   `-- utils/
|       |-- datetime_utils.py   # Timezone conversion and Discord timestamp utilities
|       `-- logger.py           # Rotating file and console logging configuration
|-- requirements.txt            # Python dependencies
|-- run.py                      # Standalone runner script
`-- tests/                      # Comprehensive unit and integration test suite
```

---

## Installation and Setup

### Prerequisites

- Python 3.10 or higher
- Discord Bot Token with the **Message Content Intent** enabled in the [Discord Developer Portal](https://discord.com/developers/applications)

### 1. Clone the Repository

```bash
git clone https://github.com/MoxiLabs/botzilla-poker.git
cd botzilla
```

### 2. Create and Activate a Virtual Environment

On Linux / macOS:
```bash
python3 -m venv .venv
source .venv/bin/activate
```

On Windows (Command Prompt / PowerShell):
```powershell
python -m venv .venv
.venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment and Settings

Create a `.env` file in the root directory:

```env
DISCORD_TOKEN=your_bot_token_here
DRY_RUN=false
```

Alternatively, configure the bot directly inside `config.json`.

---

## Docker Deployment (Recommended)

Botzilla includes full Docker and Docker Compose support for easy deployment on Linux servers, VPS, or local Docker hosts.

### 1. Setup Environment

Copy `.env.example` to `.env` and set your token:

```bash
cp .env.example .env
```

Ensure `DISCORD_TOKEN` is set in `.env`:

```env
DISCORD_TOKEN=your_bot_token_here
```

### 2. Start Botzilla

```bash
docker compose up -d --build
```

### 3. Container Management

- **View live logs**:
  ```bash
  docker compose logs -f
  ```
- **Restart container**:
  ```bash
  docker compose restart
  ```
- **Stop container**:
  ```bash
  docker compose down
  ```

### Persistent Volumes
- `./data/` &rarr; Stores SQLite database (`botzilla.db`) across restarts.
- `./logs/` &rarr; Stores rotating log files (`botzilla.log`).
- `./assets/logos/` &rarr; Caches squarified poker room logos.
- `./config.json` &rarr; Mounted read-only; modify config without rebuilding image.

---

## Configuration Reference

The `config.json` file controls all runtime parameters:

```json
{
  "timezone": "Europe/Budapest",
  "channel_id": 1441900656377073904,
  "allowed_channel_ids": [
    1441900656377073904,
    1486515344674787399
  ],
  "url_password": "https://freeroll-password.com/",
  "url_pass": "https://freerollpass.com/",
  "locale": "hu",
  "watcher_sleep_seconds": 300,
  "status_rotator_sleep_seconds": 20,
  "alert_thresholds": {
    "warning": 60,
    "urgent": 10
  },
  "command_prefix": "!",
  "command_suffix": "_poker",
  "high_value_threshold": 500,
  "logging": {
    "level": "INFO",
    "file": "botzilla.log",
    "max_mb": 5,
    "backup_count": 3
  }
}
```

### Configuration Options

| Option | Type | Description |
| :--- | :--- | :--- |
| `timezone` | string | IANA timezone used for tournament time normalization (e.g., `Europe/Budapest`). |
| `channel_id` | integer | Default Discord channel ID where automated alerts and summaries are posted. |
| `allowed_channel_ids` | list[int] | List of channel IDs where the bot accepts user commands. If empty, all channels are permitted. |
| `url_password` | string | URL for the `freeroll-password.com` scraper source. |
| `url_pass` | string | URL for the `freerollpass.com` scraper source. |
| `locale` | string | Active language code (`hu` or `en`). |
| `watcher_sleep_seconds` | integer | Interval in seconds between periodic scraper runs (default: 300). |
| `status_rotator_sleep_seconds` | integer | Interval in seconds between presence status updates (default: 20). |
| `alert_thresholds.warning` | integer | Minutes prior to tournament start for the advance warning alert (default: 60). |
| `alert_thresholds.urgent` | integer | Minutes prior to tournament start for the urgent alert (default: 10). |
| `command_prefix` | string | Prefix for legacy/text commands (default: `!`). |
| `command_suffix` | string | Optional command suffix appended to commands (e.g., `_poker` enables `!sync_poker`). |
| `high_value_threshold` | integer | Prize pool amount threshold to highlight tournaments in Gold styling (default: 500). |
| `logging.level` | string | Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`). |
| `logging.file` | string | Path to log file (default: `botzilla.log`). |
| `logging.max_mb` | integer | Maximum size per log file in megabytes before rotation. |
| `logging.backup_count` | integer | Number of rotated backup log files to retain. |
| `dry_run` | boolean / env | When enabled (`DRY_RUN=true`), Discord messages are logged to console instead of sent. |

---

## Commands

Botzilla supports both Discord Application (Slash) Commands and Prefix Commands.

### User Commands

| Slash Command | Prefix Command | Description |
| :--- | :--- | :--- |
| `/day [room] [min_prize]` | `!day` | Displays all freerolls scheduled in the next 24 hours with room filtering and pagination. |
| `/next` | `!next` | Displays the single nearest upcoming timed freeroll with a countdown. |
| `/help` | `!help` | Displays the help and user manual container. |
| `/test` | `!test` | Healthcheck command to verify the bot is active and responding. |
| `/debug` | `!debug` | Displays technical details, including the number of loaded freerolls and cache status. |

### Administrative Commands

Administrative commands require the `Administrator` permission on Discord.

| Prefix Command | Description |
| :--- | :--- |
| `!sync` | Synchronizes slash commands with the current Discord server (instant). |
| `!sync global` | Synchronizes slash commands globally across all servers (takes up to 1 hour to propagate). |
| `!sync copy` | Copies global slash commands to the current server and synchronizes immediately. |
| `!clear_commands` | Deletes registered slash commands from Discord for cleanup. |

*Note: If `command_suffix` is defined (e.g. `_poker`), commands also accept the suffixed format (e.g., `!sync_poker`).*

---

## Running the Bot

### Normal Execution

Run via the standalone runner:

```bash
python run.py
```

Or execute as a Python module:

```bash
python -m pokerparser
```

### First-Time Slash Command Sync

After inviting the bot to your Discord server, run the sync command in any channel where the bot has read and write permissions:

```
!sync
```

*(or `!sync_poker` if `command_suffix` is set to `_poker`)*

---

## Running the Test Suite

The project includes unit, parser, and integration tests using Python's standard `unittest` framework.

To execute all tests:

```bash
python -m unittest discover tests
```

To run a specific test module:

```bash
python -m unittest tests.test_container
python -m unittest tests.test_network_lifecycle
python -m unittest tests.test_database_and_fusion
```

---

## License

This project is licensed under the MIT License.
