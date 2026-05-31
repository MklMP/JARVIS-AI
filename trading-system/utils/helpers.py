import json
import yaml
from typing import Dict, Any
from pathlib import Path


def load_yaml(path: str) -> Dict:
    with open(path, 'r') as f:
        return yaml.safe_load(f)


def save_yaml(path: str, data: Dict):
    with open(path, 'w') as f:
        yaml.dump(data, f, default_flow_style=False)


def load_json(path: str) -> Dict:
    with open(path, 'r') as f:
        return json.load(f)


def save_json(path: str, data: Any):
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)


def format_currency(value: float) -> str:
    if abs(value) >= 1_000_000:
        return f"${value / 1_000_000:.2f}M"
    if abs(value) >= 1_000:
        return f"${value / 1_000:.2f}K"
    return f"${value:.2f}"


def format_pct(value: float) -> str:
    sign = '+' if value > 0 else ''
    return f"{sign}{value:.2f}%"


def ensure_dir(path: str):
    Path(path).mkdir(parents=True, exist_ok=True)
