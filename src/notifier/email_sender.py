"""邮件发送"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from loguru import logger


class EmailSender:
    """邮件发送器"""
    
    def __init__(self, config):
        self.config = config['email']
        self.enabled = self.config.get('enabled', False)
    
    def send(self, content, subject=None):
        """发送邮件"""
        if not self.enabled:
            logger.warning("⚠️ 邮件通知未启用")
            return False
        
        logger.info("📤 正在发送邮件...")
        
        try:
            # 创建邮件
            msg = MIMEMultipart('alternative')
            msg['From'] = self.config['sender']
            msg['To'] = ', '.join(self.config['recipients'])
            msg['Subject'] = subject or f"{self.config.get('subject_prefix', '')}招标项目日报"
            
            # 添加HTML内容
            html_part = MIMEText(content, 'html', 'utf-8')
            msg.attach(html_part)
            
            # 发送邮件
            with smtplib.SMTP_SSL(self.config['smtp_server'], self.config['smtp_port']) as server:
                server.login(self.config['sender'], self.config['sender_password'])
                server.send_message(msg)
            
            logger.success("✅ 邮件发送成功")
            return True
            
        except Exception as e:
            logger.error(f"❌ 邮件发送失败: {e}")
            return False
