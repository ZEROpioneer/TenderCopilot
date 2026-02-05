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
        """发送 Markdown 消息（自动按长度拆分多条）"""
        if not self.enabled or not self.webhook_url:
            logger.warning("⚠️ 企业微信通知未启用或未配置 webhook_url")
            return False

        # 企业微信 markdown.content 最大 4096 字符，这里预留一点安全空间
        MAX_LEN = 3800
        if not content:
            logger.warning("⚠️ 空内容，跳过企业微信通知发送")
            return False

        # 拆分为多段
        chunks = [content[i : i + MAX_LEN] for i in range(0, len(content), MAX_LEN)]
        total = len(chunks)

        logger.info(f"📤 正在发送企业微信通知，共 {total} 条消息（自动分段）...")

        all_success = True
        for idx, chunk in enumerate(chunks, start=1):
            # 为多段消息加一个简单的分段提示
            if total > 1:
                prefix = f"【第 {idx}/{total} 条】\n"
                body = prefix + chunk
            else:
                body = chunk

            data = {
                "msgtype": "markdown",
                "markdown": {
                    "content": body,
                },
            }

            try:
                response = requests.post(self.webhook_url, json=data, timeout=10)
                response.raise_for_status()

                result = response.json()
                if result.get("errcode") == 0:
                    logger.success(f"✅ 企业微信通知第 {idx}/{total} 条发送成功")
                else:
                    logger.error(f"❌ 企业微信通知第 {idx}/{total} 条发送失败: {result.get('errmsg')}")
                    all_success = False
            except Exception as e:
                logger.error(f"❌ 企业微信通知第 {idx}/{total} 条发送异常: {e}")
                all_success = False

        return all_success
