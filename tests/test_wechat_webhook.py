"""测试企业微信 Webhook 配置"""

import requests
import yaml

# 读取配置
with open('config/notifications.yaml', 'r', encoding='utf-8') as f:
    config = yaml.safe_load(f)

webhook_url = config['wechat_work']['webhook_url']

print(f"📤 正在测试企业微信 Webhook...")
print(f"URL: {webhook_url}")

# 构建测试消息
data = {
    "msgtype": "markdown",
    "markdown": {
        "content": """# 🎯 TenderCopilot 测试消息

> 企业微信通知配置成功！

## ✅ 配置信息

- **Webhook 状态**: 正常
- **消息格式**: Markdown
- **测试时间**: 刚刚

---

**TenderCopilot 招投标智能助手** 已就绪，随时准备为您推送项目信息！
"""
    }
}

try:
    response = requests.post(webhook_url, json=data, timeout=10)
    result = response.json()
    
    print(f"\n响应状态码: {response.status_code}")
    print(f"响应内容: {result}")
    
    if result.get('errcode') == 0:
        print("\n✅ 测试成功！请查看企业微信群消息。")
    else:
        print(f"\n❌ 测试失败：{result.get('errmsg')}")
        print("\n可能的原因：")
        print("1. Webhook URL 不正确")
        print("2. 机器人被删除或禁用")
        print("3. 网络连接问题")
        
except Exception as e:
    print(f"\n❌ 请求异常: {e}")
    print("\n请检查：")
    print("1. 网络连接是否正常")
    print("2. URL 是否完整")
