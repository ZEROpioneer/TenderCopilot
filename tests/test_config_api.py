# Quick integration check: config API returns expected structure
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def test_get_config():
    from web.api.config import get_config
    r = get_config()
    assert "settings" in r and "business_directions" in r and "notifications" in r and "env_configured" in r
    assert "announcement_filter" in r["settings"]
    assert "analyzer" in r["settings"]
    assert r["settings"]["analyzer"].get("custom_api_key") in ("已配置", "未配置")
    assert "scheduler" in r["settings"]
    assert "wechat_work" in r["notifications"]
    assert r["notifications"]["wechat_work"].get("webhook_url") in ("已配置", "未配置")
    assert r["notifications"]["email"].get("sender_password") in ("已配置", "未配置")
    print("GET config OK")


if __name__ == "__main__":
    test_get_config()
