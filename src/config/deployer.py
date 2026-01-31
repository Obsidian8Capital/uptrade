"""Bot deployment system for Hummingbot V2 via REST API."""
import logging
from pathlib import Path
from typing import Any

import httpx

from src.config.bot_config import BotDeploymentConfig, load_bot_config

logger = logging.getLogger(__name__)


# Indicator name -> controller_type mapping
INDICATOR_CONTROLLER_MAP = {
    "SniperProX": "vbt_sniper",
    "VZOProX": "vbt_vzo",
    "SpectralAnalysis": "vbt_cycle",
}


def _indicator_to_controller_type(indicator_name: str) -> str:
    """Map an indicator name to its Hummingbot controller_type string."""
    if indicator_name not in INDICATOR_CONTROLLER_MAP:
        raise ValueError(
            f"Unknown indicator: {indicator_name}. "
            f"Supported: {list(INDICATOR_CONTROLLER_MAP.keys())}"
        )
    return INDICATOR_CONTROLLER_MAP[indicator_name]


class DeploymentError(Exception):
    """Raised when a Hummingbot API deployment operation fails."""

    def __init__(
        self,
        detail: str,
        status_code: int = 0,
        response_body: dict | None = None,
    ):
        self.detail = detail
        self.status_code = status_code
        self.response_body = response_body
        super().__init__(detail)


class BotDeployer:
    """Async client for deploying bots via the Hummingbot V2 REST API."""

    def __init__(
        self,
        api_url: str | None = None,
        username: str | None = None,
        password: str | None = None,
    ):
        if api_url is None or username is None or password is None:
            try:
                from src.config.settings import Settings

                settings = Settings()
                api_url = api_url or str(settings.hb_api_url)
                username = username or settings.hb_api_user
                password = password or settings.hb_api_password
            except Exception:
                api_url = api_url or "http://localhost:8000"
                username = username or "admin"
                password = password or "admin"

        self._api_url = api_url
        self._auth = httpx.BasicAuth(username, password)
        self._client = httpx.AsyncClient(
            base_url=api_url,
            auth=self._auth,
            timeout=30.0,
        )

    async def deploy_bot(self, config: BotDeploymentConfig) -> dict:
        """Deploy a bot from a BotDeploymentConfig."""
        controller_type = _indicator_to_controller_type(config.indicator.name)

        controller_config: dict[str, Any] = {
            "controller_type": controller_type,
            "connector_name": config.market.exchange,
            "trading_pair": config.market.pair,
            "total_amount_quote": float(config.execution.amount_quote),
            "max_executors_per_side": config.execution.max_executors,
            "cooldown_time": config.execution.cooldown,
            "leverage": config.execution.leverage,
            "stop_loss": float(config.execution.stop_loss),
            "take_profit": float(config.execution.take_profit),
            "time_limit": config.execution.time_limit,
            "candles_max": config.market.candles_max,
            "timeframe": config.market.timeframe.value
            if hasattr(config.market.timeframe, "value")
            else str(config.market.timeframe),
        }

        # Add indicator-specific params
        if config.indicator.params:
            controller_config.update(config.indicator.params)

        payload = {
            "controller_config": controller_config,
            "bot_name": config.bot_name,
        }

        try:
            response = await self._client.post(
                "/bot-orchestration/deploy-v2-script",
                json=payload,
            )
        except httpx.ConnectError:
            # Retry once on connection error
            logger.warning("Connection failed, retrying...")
            try:
                response = await self._client.post(
                    "/bot-orchestration/deploy-v2-script",
                    json=payload,
                )
            except httpx.ConnectError as e:
                raise DeploymentError(
                    f"Cannot connect to Hummingbot API at {self._api_url}: {e}"
                )

        if response.status_code in (200, 201):
            return response.json()
        raise DeploymentError(
            detail=f"Deploy failed: {response.text}",
            status_code=response.status_code,
            response_body=(
                response.json()
                if response.headers.get("content-type", "").startswith(
                    "application/json"
                )
                else None
            ),
        )

    async def stop_bot(self, bot_name: str) -> dict:
        """Stop a running bot by name."""
        response = await self._client.post(
            "/bot-orchestration/stop-bot",
            json={"bot_name": bot_name},
        )
        if response.status_code in (200, 201):
            return response.json()
        raise DeploymentError(
            detail=f"Stop failed: {response.text}",
            status_code=response.status_code,
        )

    async def list_bots(self) -> list[dict]:
        """List all active bots and their statuses."""
        response = await self._client.get("/bot-orchestration/status")
        if response.status_code == 200:
            return response.json()
        raise DeploymentError(
            detail=f"List failed: {response.text}",
            status_code=response.status_code,
        )

    async def get_bot_status(self, bot_name: str) -> dict:
        """Get the status of a specific bot."""
        response = await self._client.get(
            f"/bot-orchestration/bot-status/{bot_name}"
        )
        if response.status_code == 200:
            return response.json()
        raise DeploymentError(
            detail=f"Status failed: {response.text}",
            status_code=response.status_code,
        )

    async def deploy_from_yaml(self, path: str) -> dict:
        """Load a YAML config file and deploy the bot it describes."""
        config = load_bot_config(path)
        return await self.deploy_bot(config)

    async def deploy_all(self, directory: str) -> list[dict]:
        """Deploy all YAML-configured bots found in *directory*."""
        results: list[dict] = []
        config_dir = Path(directory)
        for yaml_file in sorted(config_dir.glob("*.y*ml")):
            try:
                config = load_bot_config(str(yaml_file))
                result = await self.deploy_bot(config)
                results.append(
                    {"file": str(yaml_file), "status": "success", "result": result}
                )
            except Exception as e:
                results.append(
                    {"file": str(yaml_file), "status": "error", "error": str(e)}
                )
        return results

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()

    async def __aenter__(self) -> "BotDeployer":
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()
