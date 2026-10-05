"""Central configuration. Every tunable lives here and can be overridden by an
environment variable or a `.env` file (pydantic-settings does the loading), so
no secret (like the Sarvam key) is ever hard-coded."""
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path

ENV_FILE = Path(__file__).resolve().parent.parent / ".env" 

class Settings(BaseSettings):

    model_config = SettingsConfigDict(env_file=ENV_FILE, extra="ignore")

    database_url: str 

    sarvam_api_key: str = ""
    sarvam_base_url: str = "https://api.sarvam.ai/v1"
    sarvam_model: str = "sarvam-105b"
    llm_timeout_seconds: int = 180
    # sarvam-105b is a reasoning model: its "thinking" tokens count against
    # max_tokens, so keep this generous or the JSON answer gets cut off.
    llm_max_tokens: int = 4096

    parse_workers: int = 4              # parallel resume-parsing LLM calls
    agent_use_llm_planner: bool = True  # let the LLM choose among ready tools
    export_dir: str = "exports"
    cors_origins: list[str] = ["http://localhost:5173"]


settings = Settings()
