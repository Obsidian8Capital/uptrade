#!/usr/bin/env python3
"""CLI utility for managing the Hummingbot Gateway DEX connector."""
from __future__ import annotations

import argparse
import asyncio
import getpass
import json
import sys
from pathlib import Path
from typing import Sequence

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config.gateway_config import (
    GatewayClient,
    SUPPORTED_CHAINS,
)


# ---------------------------------------------------------------------------
# Subcommand handlers
# ---------------------------------------------------------------------------

async def cmd_health(args: argparse.Namespace) -> None:
    """Check Gateway health status."""
    async with GatewayClient() as client:
        result = await client.health_check()
        print(json.dumps(result, indent=2))


async def cmd_connectors(args: argparse.Namespace) -> None:
    """List available connectors."""
    async with GatewayClient() as client:
        connectors = await client.list_connectors()
        print("Available connectors:")
        for name in connectors:
            print(f"  - {name}")


async def cmd_add_wallet(args: argparse.Namespace) -> None:
    """Add a wallet to the Gateway (prompts for private key)."""
    chain = args.chain
    network = args.network

    if chain not in SUPPORTED_CHAINS:
        print(f"Warning: '{chain}' is not in SUPPORTED_CHAINS. Proceeding anyway.")

    private_key = getpass.getpass("Enter private key: ")
    if not private_key:
        print("Error: private key is required.", file=sys.stderr)
        sys.exit(1)

    async with GatewayClient() as client:
        result = await client.add_wallet(chain, network, private_key)
        print(json.dumps(result, indent=2))


async def cmd_check(args: argparse.Namespace) -> None:
    """Verify connector status for a chain."""
    async with GatewayClient() as client:
        result = await client.check_connector_status(args.chain)
        print(json.dumps(result, indent=2))


async def cmd_approve(args: argparse.Namespace) -> None:
    """Approve a token for spending by a connector."""
    address = args.address
    if not address:
        address = input("Wallet address: ").strip()
    if not address:
        print("Error: wallet address is required.", file=sys.stderr)
        sys.exit(1)

    async with GatewayClient() as client:
        result = await client.approve_token(
            chain=args.chain,
            network=args.network,
            address=address,
            spender=args.spender,
            token=args.token,
        )
        print(json.dumps(result, indent=2))


async def cmd_balances(args: argparse.Namespace) -> None:
    """Check token balances for a wallet."""
    tokens = [t.strip() for t in args.tokens.split(",") if t.strip()]
    if not tokens:
        print("Error: at least one token is required.", file=sys.stderr)
        sys.exit(1)

    chain_config = SUPPORTED_CHAINS.get(args.chain)
    network = chain_config.network if chain_config else "mainnet"

    async with GatewayClient() as client:
        result = await client.get_balances(
            chain=args.chain,
            network=network,
            address=args.address,
            tokens=tokens,
        )
        print(json.dumps(result, indent=2))


# ---------------------------------------------------------------------------
# CLI definition
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Manage the Hummingbot Gateway DEX connector.",
    )
    sub = parser.add_subparsers(dest="command", help="Available commands")

    # health
    sub.add_parser("health", help="Check Gateway health status")

    # connectors
    sub.add_parser("connectors", help="List available connectors")

    # add-wallet
    p_add = sub.add_parser("add-wallet", help="Add a wallet to the Gateway")
    p_add.add_argument("--chain", required=True, help="Blockchain name (e.g. ethereum)")
    p_add.add_argument("--network", default="mainnet", help="Network name (default: mainnet)")

    # check
    p_check = sub.add_parser("check", help="Verify connector status for a chain")
    p_check.add_argument("--chain", required=True, help="Blockchain name")

    # approve
    p_approve = sub.add_parser("approve", help="Approve a token for a connector")
    p_approve.add_argument("--chain", required=True, help="Blockchain name")
    p_approve.add_argument("--token", required=True, help="Token symbol (e.g. USDC)")
    p_approve.add_argument("--spender", required=True, help="Connector/spender name")
    p_approve.add_argument("--address", default="", help="Wallet address")
    p_approve.add_argument("--network", default="mainnet", help="Network name")

    # balances
    p_bal = sub.add_parser("balances", help="Check token balances")
    p_bal.add_argument("--chain", required=True, help="Blockchain name")
    p_bal.add_argument("--address", required=True, help="Wallet address")
    p_bal.add_argument("--tokens", required=True, help="Comma-separated token symbols")

    return parser


def main(argv: Sequence[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        sys.exit(0)

    handlers = {
        "health": cmd_health,
        "connectors": cmd_connectors,
        "add-wallet": cmd_add_wallet,
        "check": cmd_check,
        "approve": cmd_approve,
        "balances": cmd_balances,
    }

    handler = handlers[args.command]
    asyncio.run(handler(args))


if __name__ == "__main__":
    main()
