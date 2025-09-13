from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Telegram Bot
    bot_token: str
    
    # Database
    database_url: str = "postgresql://user:password@localhost/family_budget"
    
    # Other
    debug: bool = False
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()