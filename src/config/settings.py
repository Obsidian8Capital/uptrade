"""Central configuration loading from environment variables."""
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """UpTrade application settings loaded from environment."""

    # Database
    postgres_user: str = Field(default="uptrade")
    postgres_password: str = Field(default="uptrade_dev_password")
    postgres_db: str = Field(default="uptrade")
    postgres_host: str = Field(default="localhost")
    postgres_port: int = Field(default=5432)

    # Polygon.io
    polygon_api_key: str = Field(default="")

    # Hummingbot API
    hb_api_user: str = Field(default="admin")
    hb_api_password: str = Field(default="")
    hb_api_host: str = Field(default="localhost")
    hb_api_port: int = Field(default=8000)

    # Hummingbot Gateway
    gw_passphrase: str = Field(default="")
    gw_host: str = Field(default="localhost")
    gw_port: int = Field(default=15888)

    # Application
    log_level: str = Field(default="INFO")
    data_retention_days: int = Field(default=365)

    @property
    def database_url(self) -> str:
        """Build SQLAlchemy database URL."""
        return (
            f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def async_database_url(self) -> str:
        """Build async database URL."""
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def hb_api_url(self) -> str:
        """Build Hummingbot API base URL."""
        return f"http://{self.hb_api_host}:{self.hb_api_port}"

    @property
    def gw_url(self) -> str:
        """Build Gateway base URL."""
        return f"https://{self.gw_host}:{self.gw_port}"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}
