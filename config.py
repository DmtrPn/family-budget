from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Telegram Bot
    bot_token: str

    # Webhook settings (optional)
    webhook_url: Optional[str] = None  # e.g., https://your.domain.com/webhook
    webhook_port: int = 8080           # Port for local aiohttp server
    webhook_path: str = "/webhook"    # Path to register handler
    webhook_host: str = "0.0.0.0"      # Host for aiohttp server
    
    # Database
    database_url: str = "postgresql://user:password@localhost/family_budget"
    
    # Other
    debug: bool = False
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()