from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, validator


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)
    
    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://localhost:5432/satoshis_endgame",
        description="PostgreSQL connection URL with asyncpg driver"
    )
    
    # API Keys
    blockcypher_api_key: Optional[str] = Field(None, description="BlockCypher API key")
    blockchair_api_key: Optional[str] = Field(None, description="Blockchair API key")
    
    # Discord
    discord_webhook_url: str = Field(..., description="Discord webhook URL for alerts")
    
    # Monitoring parameters
    # Note: batch_size is kept for backward compatibility but should be removed
    # when fully migrated to block-based monitoring
    batch_size: int = Field(1, description="Number of addresses per batch (legacy)")
    dormancy_threshold_days: int = Field(365, description="Days of inactivity to consider dormant")
    min_balance_threshold_btc: float = Field(10.0, description="Minimum BTC balance to monitor")
    alert_cooldown_minutes: int = Field(30, description="Minutes between duplicate alerts")
    
    # Quantum emergency thresholds
    min_dormant_wallets_for_alert: int = Field(5, description="Minimum dormant wallets moving to trigger alert")
    emergency_time_window_minutes: int = Field(30, description="Time window for emergency detection")
    
    # Rate limiting
    blockcypher_rate_limit: float = Field(3.0, description="Requests per second for BlockCypher")
    blockchair_rate_limit: float = Field(5.0, description="Requests per second for Blockchair")
    
    # Logging
    log_level: str = Field("INFO", description="Logging level")
    log_format: str = Field("json", description="Log format (json or plain)")
    
    # Block monitoring settings
    # Note: With block-based monitoring, we no longer need individual address
    # monitoring strategies or tier sizes. The system monitors all addresses
    # efficiently by checking new blocks (~144/day instead of 271,584 API calls)
    
    @validator("min_balance_threshold_btc")
    def validate_balance_threshold(cls, v):
        if v < 0:
            raise ValueError("Balance threshold must be non-negative")
        return v
    
    @validator("discord_webhook_url")
    def validate_discord_webhook(cls, v):
        if not v.startswith("https://discord.com/api/webhooks/"):
            raise ValueError("Invalid Discord webhook URL format")
        return v


settings = Settings()