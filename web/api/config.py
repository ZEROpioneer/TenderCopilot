"""Config API: read and write YAML config (safe subset) and .env for secrets."""
import re
import yaml
from pathlib import Path
from typing import Any, Dict, List, Tuple

from fastapi import APIRouter, HTTPException

ROOT = Path(__file__).resolve().parent.parent.parent
CONFIG_DIR = ROOT / "config"
ENV_PATH = ROOT / ".env"

ENV_WHITELIST = {"CUSTOM_OPENAI_API_KEY", "WECHAT_WORK_WEBHOOK", "EMAIL_PASSWORD"}

router = APIRouter()


def _load_yaml(path: Path) -> Dict:
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _save_yaml(path: Path, data: Dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)


def _read_env_parsed() -> Tuple[Dict[str, str], List[str]]:
    """Parse .env: return (key->value for whitelist keys), list of all lines (to preserve comments)."""
    values = {}
    lines: List[str] = []
    if ENV_PATH.exists():
        raw = ENV_PATH.read_text(encoding="utf-8")
        for line in raw.splitlines():
            lines.append(line)
            m = re.match(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$", line)
            if m and m.group(1) in ENV_WHITELIST:
                val = m.group(2).strip().strip("'\"")
                values[m.group(1)] = val
    return values, lines


def _read_env_configured() -> Dict[str, bool]:
    """Return which env keys are set (no plaintext)."""
    values, _ = _read_env_parsed()
    return {k: bool(values.get(k)) for k in ENV_WHITELIST}


def _write_env(updates: Dict[str, str]) -> None:
    """Write only whitelist keys to .env; non-empty values only. Preserve other lines."""
    if not updates:
        return
    updates = {k: v for k, v in updates.items() if k in ENV_WHITELIST and v and str(v).strip()}
    if not updates:
        return
    _, existing_lines = _read_env_parsed()
    existing_keys = set()
    new_lines = []
    for line in existing_lines:
        m = re.match(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=", line)
        if m and m.group(1) in ENV_WHITELIST:
            key = m.group(1)
            existing_keys.add(key)
            if key in updates:
                new_lines.append(f"{key}={updates[key]}")
                continue
        new_lines.append(line)
    for k, v in updates.items():
        if k not in existing_keys:
            new_lines.append(f"{k}={v}")
    ENV_PATH.parent.mkdir(parents=True, exist_ok=True)
    ENV_PATH.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


@router.get("")
def get_config():
    """Return editable config as JSON. Sensitive values are masked."""
    settings = _load_yaml(CONFIG_DIR / "settings.yaml")
    business = _load_yaml(CONFIG_DIR / "business_directions.yaml")
    notifications = _load_yaml(CONFIG_DIR / "notifications.yaml")

    # Mask sensitive keys (only show whether set)
    def mask(d: Dict, keys: list) -> Dict:
        out = dict(d)
        for k in keys:
            if k in out and out[k] and not (isinstance(out[k], str) and out[k].startswith("${") and out[k].endswith("}")):
                out[k] = "***已配置***"
        return out

    n = notifications.get("wechat_work") or {}
    notif_masked = mask(dict(n), ["webhook_url"])
    if "wechat_work" in notifications:
        notifications = {**notifications, "wechat_work": {**n, **notif_masked}}
    email = notifications.get("email") or {}
    if "email" in notifications:
        notifications["email"] = mask(dict(email), ["sender_password"])
    if "analyzer" in (settings or {}):
        settings["analyzer"] = mask(dict(settings["analyzer"]), ["custom_api_key", "api_key"])

    env_configured = _read_env_configured()
    # 根据 .env 是否配置，统一返回“已配置/未配置”（不返回明文与 ${VAR）
    if "analyzer" in (settings or {}):
        settings["analyzer"] = dict(settings["analyzer"])
        if env_configured.get("CUSTOM_OPENAI_API_KEY"):
            settings["analyzer"]["custom_api_key"] = "已配置"
        else:
            settings["analyzer"]["custom_api_key"] = "未配置"
    if "wechat_work" in (notifications or {}):
        notifications["wechat_work"] = dict(notifications["wechat_work"])
        notifications["wechat_work"]["webhook_url"] = "已配置" if env_configured.get("WECHAT_WORK_WEBHOOK") else "未配置"
    if "email" in (notifications or {}):
        notifications["email"] = dict(notifications["email"])
        notifications["email"]["sender_password"] = "已配置" if env_configured.get("EMAIL_PASSWORD") else "未配置"
    return {
        "settings": settings or {},
        "business_directions": business.get("business_directions", business) if isinstance(business, dict) else {},
        "notifications": notifications or {},
        "env_configured": env_configured,
    }


MASKED_VALUES = ("***已配置***", "已配置", "未配置")


def _strip_masked(d: Dict, placeholders: Tuple[str, ...] = MASKED_VALUES) -> Dict:
    """Remove keys whose value is a placeholder so we don't write them to YAML."""
    out = {}
    for k, v in d.items():
        if v in placeholders:
            continue
        if isinstance(v, dict):
            out[k] = _strip_masked(v, placeholders)
        else:
            out[k] = v
    return out


def _deep_merge(base: Dict, update: Dict, placeholders: Tuple[str, ...] = MASKED_VALUES) -> Dict:
    """Deep merge: update overwrites base; placeholder values are stripped and not written."""
    update = _strip_masked(update, placeholders)
    out = dict(base)
    for k, v in update.items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


@router.put("")
def put_config(payload: Dict[str, Any]):
    """Update config. Merges payload into existing files; writes env to .env when provided."""
    if "env" in payload and isinstance(payload["env"], dict):
        _write_env(payload["env"])
    if "settings" in payload:
        path = CONFIG_DIR / "settings.yaml"
        existing = _load_yaml(path)
        existing = _deep_merge(existing, payload["settings"])
        _save_yaml(path, existing)
    if "business_directions" in payload:
        path = CONFIG_DIR / "business_directions.yaml"
        existing = _load_yaml(path)
        existing["business_directions"] = payload["business_directions"]
        _save_yaml(path, existing)
    if "notifications" in payload:
        path = CONFIG_DIR / "notifications.yaml"
        existing = _load_yaml(path)
        notif_update = _strip_masked(payload["notifications"])
        for k, v in notif_update.items():
            if isinstance(v, dict) and k in existing and isinstance(existing[k], dict):
                existing[k] = _deep_merge(existing[k], v)
            else:
                existing[k] = v
        _save_yaml(path, existing)
    return {"status": "ok"}
