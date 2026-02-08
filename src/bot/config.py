"""
Configuration loader for trading bot.

Reads a YAML config and injects secrets from environment variables.
"""

import os

import yaml
from dotenv import load_dotenv

load_dotenv()


def load_config(config_path: str = "config.yaml") -> dict:
    """
    Load configuration from YAML file.

    Injects OPENROUTER_API_KEY into strategies.ai.api_key automatically.
    """
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    # Inject API key from environment
    if "strategies" in config and "ai" in config["strategies"]:
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY not found in environment")
        config["strategies"]["ai"]["api_key"] = api_key

    return config
