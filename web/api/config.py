"""Config API: read and write YAML config (safe subset) and .env for secrets."""
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

import yaml
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

ROOT = Path(__file__).resolve().parent.parent.parent
CONFIG_DIR = ROOT / "config"
ENV_PATH = ROOT / ".env"
SCORING_CONFIG_PATH = CONFIG_DIR / "scoring_config.yaml"

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
    s = (settings or {}).setdefault("scoring", {})
    if "push_threshold" not in s:
        s["push_threshold"] = 65
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


def _reload_scheduler():
    """配置保存后触发热重载定时任务。"""
    try:
        from web.scheduler_engine import reload_scheduler
        reload_scheduler()
    except Exception as e:
        from loguru import logger
        logger.warning(f"⏰ 定时任务热重载失败: {e}")


@router.put("")
def put_config(payload: Dict[str, Any]):
    """Update config. Merges payload into existing files; writes env to .env when provided."""
    if "env" in payload and isinstance(payload["env"], dict):
        _write_env(payload["env"])
    if "settings" in payload:
        path = CONFIG_DIR / "settings.yaml"
        existing = _load_yaml(path)
        existing = _deep_merge(existing, payload["settings"])
        s = existing.setdefault("scoring", {})
        if "push_threshold" not in s:
            s["push_threshold"] = 65
        _save_yaml(path, existing)
        _reload_scheduler()
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


# --- 评分权重配置 ---

DEFAULT_SCORING_WEIGHTS = {
    "title_keyword": 30,
    "content_keyword": 15,
    "location_match": 20,
    "budget_high": 10,
    "time_urgent": -10,
}


@router.get("/scoring")
def get_scoring_config():
    """加载 scoring_config.yaml，用于前端评分权重表单。"""
    data = _load_yaml(SCORING_CONFIG_PATH)
    if not data:
        data = {"weights": dict(DEFAULT_SCORING_WEIGHTS), "budget_high_threshold_wan": 50, "time_urgent_threshold_days": 3, "custom_rules": []}
    weights = data.get("weights", {})
    for k, v in DEFAULT_SCORING_WEIGHTS.items():
        if k not in weights:
            weights[k] = v
    data["weights"] = weights
    data["custom_rules"] = data.get("custom_rules") or []
    return data


def _parse_custom_rules_from_form(form) -> List[Dict]:
    """从 form 数组解析 custom_rules。支持 rule_name[], rule_field[], rule_operator[], rule_value[], rule_score[]"""
    def glist(key):
        return form.getlist(key) if hasattr(form, "getlist") else ([form.get(key)] if form.get(key) is not None else [])
    names = glist("rule_name[]") or glist("rule_name")
    fields = glist("rule_field[]") or glist("rule_field")
    operators = glist("rule_operator[]") or glist("rule_operator")
    values = glist("rule_value[]") or glist("rule_value")
    scores = glist("rule_score[]") or glist("rule_score")
    n = max(len(names), len(fields), len(operators), len(values), len(scores), 1)
    names = (names + [""] * n)[:n]
    fields = (fields + ["title"] * n)[:n]
    operators = (operators + ["contains_any"] * n)[:n]
    values = (values + [""] * n)[:n]
    scores = (scores + ["0"] * n)[:n]
    rules = []
    for t in zip(names, fields, operators, values, scores):
        name, field, op, val, sc = (str(x or "").strip() for x in t)
        if not name and not field:
            continue
        try:
            sc_int = int(sc) if sc else 0
        except (ValueError, TypeError):
            sc_int = 0
        rules.append({"name": name or "自定义规则", "field": field or "title", "operator": op or "contains_any", "value": val, "score": sc_int})
    return rules


@router.post("/scoring")
async def put_scoring_config(request: Request):
    """保存评分权重到 scoring_config.yaml。支持 JSON 或 form 提交。"""
    # 支持 form 提交（用于传统表单）
    content_type = request.headers.get("content-type", "")
    if "application/x-www-form-urlencoded" in content_type or "multipart/form-data" in content_type:
        form = await request.form()
        existing = _load_yaml(SCORING_CONFIG_PATH) or {}
        weights = dict(existing.get("weights", DEFAULT_SCORING_WEIGHTS))
        for k, v in DEFAULT_SCORING_WEIGHTS.items():
            raw = form.get(f"weights[{k}]") or form.get(k)
            if raw is not None:
                try:
                    weights[k] = int(raw)
                except (ValueError, TypeError):
                    pass
        budget_wan = form.get("budget_high_threshold_wan") or 50
        time_days = form.get("time_urgent_threshold_days") or 3
        try:
            budget_wan = int(budget_wan) if budget_wan is not None else 50
        except (ValueError, TypeError):
            budget_wan = 50
        try:
            time_days = int(time_days) if time_days is not None else 3
        except (ValueError, TypeError):
            time_days = 3
        custom_rules = _parse_custom_rules_from_form(form)
    else:
        try:
            body = await request.json()
        except Exception:
            body = {}
        weights = body.get("weights", {})
        if not isinstance(weights, dict):
            raise HTTPException(400, "weights 必须为对象")
        budget_wan = int(body.get("budget_high_threshold_wan", 50))
        time_days = int(body.get("time_urgent_threshold_days", 3))
        custom_rules = body.get("custom_rules") or []

    out = {
        "weights": {k: int(weights.get(k, v)) for k, v in DEFAULT_SCORING_WEIGHTS.items()},
        "budget_high_threshold_wan": budget_wan,
        "time_urgent_threshold_days": time_days,
        "custom_rules": custom_rules if isinstance(custom_rules, list) else [],
    }
    # 校验 custom_rules 结构
    validated_rules = []
    for r in out["custom_rules"]:
        if isinstance(r, dict) and r.get("field"):
            validated_rules.append({
                "name": str(r.get("name", "")).strip() or "自定义规则",
                "field": str(r.get("field", "title")).strip() or "title",
                "operator": str(r.get("operator", "contains_any")).strip() or "contains_any",
                "value": str(r.get("value", "")).strip(),
                "score": int(r.get("score", 0)) if r.get("score") is not None else 0,
            })
    out["custom_rules"] = validated_rules
    _save_yaml(SCORING_CONFIG_PATH, out)
    if request.headers.get("HX-Request") == "true":
        return HTMLResponse('<span class="text-green-400">已保存</span>')
    return {"status": "ok", "message": "评分权重已保存"}
