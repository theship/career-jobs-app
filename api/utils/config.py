"""
Configuration loader and settings management
"""

import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """Application settings with environment variable support"""

    # App settings
    app_name: str = Field(default="Career Jobs App")
    app_version: str = Field(default="0.1.0")
    environment: str = Field(default="development")
    debug: bool = Field(default=True)

    # API settings
    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8000)

    # Supabase settings
    supabase_url: str = Field(...)
    supabase_anon_key: str = Field(default="")
    supabase_service_role_key: str = Field(...)

    # OpenAI settings
    openai_api_key: str = Field(...)
    openai_model: str = Field(default="gpt-4o-mini")
    openai_embedding_model: str = Field(default="text-embedding-3-small")

    # JWT settings
    jwt_algorithm: str = Field(default="RS256")
    jwt_audience: str = Field(default="authenticated")
    jwks_cache_ttl: int = Field(default=300)

    # Storage settings
    max_file_size: int = Field(default=10485760)  # 10MB
    allowed_extensions: list = Field(default=[".pdf", ".doc", ".docx", ".txt"])

    # Logging
    log_level: str = Field(default="INFO")

    # Directory paths
    @property
    def CONFIG_DIR(self) -> str:
        """Get the config directory path"""
        return str(Path(__file__).parent.parent.parent / "config")

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "extra": "ignore",  # Ignore extra fields like WANDB_*
    }


def load_yaml_config(config_path: Optional[Path] = None) -> Dict[str, Any]:
    """
    Load configuration from YAML file

    Args:
        config_path: Path to config file (defaults to config/settings.yaml)

    Returns:
        Configuration dictionary
    """
    if config_path is None:
        config_path = Path(__file__).parent.parent.parent / "config" / "settings.yaml"

    if not config_path.exists():
        logger.warning(f"Config file not found: {config_path}")
        return {}

    try:
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)

        # Replace environment variables
        config = _replace_env_vars(config)
        return config

    except Exception as e:
        logger.error(f"Error loading config file: {e}")
        return {}


def _replace_env_vars(config: Any) -> Any:
    """
    Recursively replace environment variable placeholders in config

    Args:
        config: Configuration object (dict, list, or value)

    Returns:
        Configuration with environment variables replaced
    """
    if isinstance(config, dict):
        return {k: _replace_env_vars(v) for k, v in config.items()}
    elif isinstance(config, list):
        return [_replace_env_vars(item) for item in config]
    elif isinstance(config, str) and config.startswith("${") and config.endswith("}"):
        # Parse environment variable with default value
        var_spec = config[2:-1]
        if ":" in var_spec:
            var_name, default_value = var_spec.split(":", 1)
            return os.getenv(var_name, default_value)
        else:
            return os.getenv(var_spec, config)
    else:
        return config


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()


def load_settings() -> Settings:
    """
    Load settings from environment and config files

    Returns:
        Settings instance
    """
    # Load YAML config (for future use)
    load_yaml_config()

    # Create settings with environment variables taking precedence
    settings = get_settings()

    # Log configuration status
    logger.info(f"Loaded configuration for environment: {settings.environment}")

    return settings


# Global settings instance
settings = get_settings()
