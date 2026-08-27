"""Main entry point for running the pokerparser module (python -m pokerparser)."""

from .bot.client import run_bot


def main():
    """Main execution function."""
    run_bot()


if __name__ == "__main__":
    main()
