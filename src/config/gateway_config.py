"""Gateway DEX connector configuration and client utilities."""
import logging
import os
from typing import Any, Optional

import httpx
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class GatewayConfig(BaseModel):
    """Configuration for connecting to the Hummingbot Gateway API."""

    api_url: str = Field(
        default_factory=lambda: os.getenv("GW_API_URL", "http://localhost:15888")
    )
    passphrase: str = Field(
        default_factory=lambda: os.getenv("GW_PASSPHRASE", "")
    )


class ChainConfig(BaseModel):
    """Blockchain chain and connector mapping."""

    chain: str
    network: str = "mainnet"
    rpc_url: str = ""
    connector: str = ""


SUPPORTED_CHAINS: dict[str, ChainConfig] = {
    "ethereum": ChainConfig(
        chain="ethereum", network="mainnet", connector="uniswap"
    ),
    "polygon": ChainConfig(
        chain="polygon", network="mainnet", connector="uniswap"
    ),
    "arbitrum": ChainConfig(
        chain="arbitrum", network="mainnet", connector="uniswap"
    ),
    "solana": ChainConfig(
        chain="solana", network="mainnet", connector="jupiter"
    ),
    "hyperliquid": ChainConfig(
        chain="hyperliquid", network="mainnet", connector="hyperliquid"
    ),
    "dydx": ChainConfig(
        chain="dydx", network="mainnet", connector="dydx"
    ),
}


class GatewayClient:
    """Async HTTP client for the Hummingbot Gateway REST API."""

    def __init__(self, config: Optional[GatewayConfig] = None) -> None:
        if config is None:
            config = GatewayConfig()
        self.config = config
        self._client = httpx.AsyncClient(
            base_url=config.api_url,
            timeout=30.0,
            headers={"Content-Type": "application/json"},
        )

    async def health_check(self) -> dict[str, Any]:
        """Check Gateway health status."""
        response = await self._client.get("/gateway/status")
        response.raise_for_status()
        return response.json()

    async def list_connectors(self) -> list[str]:
        """Return the list of available connector names."""
        response = await self._client.get("/gateway/connectors")
        response.raise_for_status()
        data: dict[str, Any] = response.json()
        return data.get("connectors", [])

    async def add_wallet(
        self,
        chain: str,
        network: str,
        private_key: str,
        address: Optional[str] = None,
    ) -> dict[str, Any]:
        """Register a wallet with the Gateway."""
        payload: dict[str, str] = {
            "chain": chain,
            "network": network,
            "privateKey": private_key,
        }
        if address:
            payload["address"] = address
        response = await self._client.post("/gateway/wallet/add", json=payload)
        response.raise_for_status()
        return response.json()

    async def get_balances(
        self,
        chain: str,
        network: str,
        address: str,
        tokens: list[str],
    ) -> dict[str, Any]:
        """Fetch token balances for a wallet."""
        payload: dict[str, Any] = {
            "chain": chain,
            "network": network,
            "address": address,
            "tokenSymbols": tokens,
        }
        response = await self._client.post(
            "/gateway/wallet/balances", json=payload
        )
        response.raise_for_status()
        return response.json()

    async def approve_token(
        self,
        chain: str,
        network: str,
        address: str,
        spender: str,
        token: str,
    ) -> dict[str, Any]:
        """Approve a token for spending by a connector."""
        payload: dict[str, str] = {
            "chain": chain,
            "network": network,
            "address": address,
            "spender": spender,
            "token": token,
        }
        response = await self._client.post(
            "/gateway/evm/approve", json=payload
        )
        response.raise_for_status()
        return response.json()

    async def check_connector_status(self, chain: str) -> dict[str, Any]:
        """Check whether a chain's connector is available on the Gateway."""
        try:
            health = await self.health_check()
            connectors = await self.list_connectors()
            chain_config = SUPPORTED_CHAINS.get(chain)
            connector_name = chain_config.connector if chain_config else chain
            return {
                "chain": chain,
                "gateway_status": health.get("status", "unknown"),
                "connector_available": connector_name in connectors,
                "connector": connector_name,
            }
        except Exception as e:
            logger.error("Connector status check failed for %s: %s", chain, e)
            return {
                "chain": chain,
                "gateway_status": "error",
                "error": str(e),
            }

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()

    async def __aenter__(self) -> "GatewayClient":
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()
