"""Load YAML config and inject env vars."""

import os

import yaml
from dotenv import load_dotenv

load_dotenv()


def load_config(config_path: str = "config.yaml") -> dict:
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    if "strategies" in config and "ai" in config["strategies"]:
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY not found in environment")
        config["strategies"]["ai"]["api_key"] = api_key

    return config
