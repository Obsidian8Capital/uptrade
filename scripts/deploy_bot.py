#!/usr/bin/env python3
"""CLI entry point for deploying and managing Hummingbot V2 bots."""
import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config.deployer import BotDeployer, DeploymentError


def _print_json(data: Any) -> None:
    """Pretty-print a JSON-serialisable object to stdout."""
    print(json.dumps(data, indent=2, default=str))


async def _deploy(args: argparse.Namespace) -> dict:
    async with BotDeployer() as deployer:
        return await deployer.deploy_from_yaml(args.config)


async def _deploy_all(args: argparse.Namespace) -> list[dict]:
    async with BotDeployer() as deployer:
        return await deployer.deploy_all(args.directory)


async def _stop(args: argparse.Namespace) -> dict:
    async with BotDeployer() as deployer:
        return await deployer.stop_bot(args.bot_name)


async def _list_bots(args: argparse.Namespace) -> list[dict]:
    async with BotDeployer() as deployer:
        return await deployer.list_bots()


async def _status(args: argparse.Namespace) -> dict:
    async with BotDeployer() as deployer:
        return await deployer.get_bot_status(args.bot_name)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Deploy and manage Hummingbot V2 bots via REST API.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # deploy
    p_deploy = subparsers.add_parser("deploy", help="Deploy a single bot from a YAML config file.")
    p_deploy.add_argument("config", help="Path to the YAML config file.")
    p_deploy.set_defaults(func=_deploy)

    # deploy-all
    p_deploy_all = subparsers.add_parser("deploy-all", help="Deploy all bots from a directory of YAML configs.")
    p_deploy_all.add_argument("directory", help="Path to the directory containing YAML configs.")
    p_deploy_all.set_defaults(func=_deploy_all)

    # stop
    p_stop = subparsers.add_parser("stop", help="Stop a running bot by name.")
    p_stop.add_argument("bot_name", help="Name of the bot to stop.")
    p_stop.set_defaults(func=_stop)

    # list
    p_list = subparsers.add_parser("list", help="List all active bots.")
    p_list.set_defaults(func=_list_bots)

    # status
    p_status = subparsers.add_parser("status", help="Get the status of a specific bot.")
    p_status.add_argument("bot_name", help="Name of the bot to query.")
    p_status.set_defaults(func=_status)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    try:
        result = asyncio.run(args.func(args))
        _print_json(result)
        sys.exit(0)
    except DeploymentError as exc:
        _print_json({"error": exc.detail, "status_code": exc.status_code})
        sys.exit(1)
    except FileNotFoundError as exc:
        _print_json({"error": str(exc)})
        sys.exit(1)
    except Exception as exc:
        _print_json({"error": str(exc)})
        sys.exit(1)


if __name__ == "__main__":
    main()
