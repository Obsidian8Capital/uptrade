#!/usr/bin/env python3
"""Standalone entry point for the UpTrade data updater service."""
import argparse
import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.data.updater import DataUpdaterService
from src.logging_config import setup_logging


def main():
    parser = argparse.ArgumentParser(description="UpTrade Data Updater Service")
    parser.add_argument(
        "--symbols",
        type=str,
        default=None,
        help="Comma-separated Polygon symbols (e.g., X:BTCUSD,X:ETHUSD)",
    )
    parser.add_argument(
        "--timeframes",
        type=str,
        default="1m,5m,1h",
        help="Comma-separated timeframes (default: 1m,5m,1h)",
    )
    parser.add_argument(
        "--config-dir",
        type=str,
        default="src/config/examples/",
        help="Path to bot config directory (used if --symbols not set)",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level (default: INFO)",
    )
    args = parser.parse_args()

    setup_logging(level=args.log_level)

    if args.symbols:
        symbols = [s.strip() for s in args.symbols.split(",")]
        timeframes = [t.strip() for t in args.timeframes.split(",")]
        updater = DataUpdaterService(symbols=symbols, timeframes=timeframes)
    else:
        updater = DataUpdaterService.from_bot_configs(args.config_dir)

    print(f"UpTrade Data Updater")
    print(f"  Symbols:    {updater.symbols}")
    print(f"  Timeframes: {updater.timeframes}")
    print(f"  Starting...")

    asyncio.run(updater.run())


if __name__ == "__main__":
    main()
