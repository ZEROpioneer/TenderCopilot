"""微信个人通知（通过第三方服务）"""

import requests
from loguru import logger


class WechatNotifier:
    """微信个人通知"""
    
    def __init__(self, config):
        self.config = config.get('wechat', {})
        self.enabled = self.config.get('enabled', False)
        self.service = self.config.get('service', 'serverchan')
        self.token = self.config.get('token', '')
    
    def send(self, title, content):
        """发送通知"""
        if not self.enabled or not self.token:
            logger.warning("⚠️ 微信通知未启用或未配置 token")
            return False
        
        logger.info("📤 正在发送微信通知...")
        
        if self.service == 'serverchan':
            return self._send_serverchan(title, content)
        elif self.service == 'pushplus':
            return self._send_pushplus(title, content)
        else:
            logger.error(f"❌ 不支持的服务: {self.service}")
            return False
    
    def _send_serverchan(self, title, content):
        """Server酱"""
        url = f"https://sctapi.ftqq.com/{self.token}.send"
        data = {'title': title, 'desp': content}
        
        try:
            response = requests.post(url, data=data, timeout=10)
            response.raise_for_status()
            logger.success("✅ 微信通知发送成功（Server酱）")
            return True
        except Exception as e:
            logger.error(f"❌ 微信通知发送失败: {e}")
            return False
    
    def _send_pushplus(self, title, content):
        """PushPlus"""
        url = "http://www.pushplus.plus/send"
        data = {
            'token': self.token,
            'title': title,
            'content': content,
            'template': 'markdown'
        }
        
        try:
            response = requests.post(url, json=data, timeout=10)
            response.raise_for_status()
            logger.success("✅ 微信通知发送成功（PushPlus）")
            return True
        except Exception as e:
            logger.error(f"❌ 微信通知发送失败: {e}")
            return False
