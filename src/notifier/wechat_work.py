"""企业微信通知"""

import requests
from loguru import logger


class WechatWorkNotifier:
    """企业微信机器人通知"""
    
    def __init__(self, config):
        self.webhook_url = config['wechat_work'].get('webhook_url', '')
        self.enabled = config['wechat_work'].get('enabled', False)
        self.mention_users = config['wechat_work'].get('mention_users', [])
    
    def send(self, content):
        """发送 Markdown 消息"""
        if not self.enabled or not self.webhook_url:
            logger.warning("⚠️ 企业微信通知未启用或未配置 webhook_url")
            return False
        
        logger.info("📤 正在发送企业微信通知...")
        
        # 构建消息
        data = {
            "msgtype": "markdown",
            "markdown": {
                "content": content
            }
        }
        
        try:
            response = requests.post(self.webhook_url, json=data, timeout=10)
            response.raise_for_status()
            
            result = response.json()
            if result.get('errcode') == 0:
                logger.success("✅ 企业微信通知发送成功")
                return True
            else:
                logger.error(f"❌ 企业微信通知发送失败: {result.get('errmsg')}")
                return False
                
        except Exception as e:
            logger.error(f"❌ 企业微信通知发送异常: {e}")
            return False
