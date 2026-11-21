from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    model_config = {"env_file": ".env"}
    comet_api_key: str = ""
    cost_budget_free: float = 100.0

@lru_cache
def get_settings():
    return Settings()

settings = get_settings()
