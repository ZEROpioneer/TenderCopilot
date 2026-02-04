"""通知管理器 - 统一处理所有通知渠道"""

from loguru import logger
from .wechat_work import WechatWorkNotifier
from .email_sender import EmailSender
from .wechat import WechatNotifier


class NotificationManager:
    """通知管理器"""
    
    def __init__(self, config):
        self.config = config
        
        # 初始化各个通知器
        self.wechat_work = WechatWorkNotifier(config) if config.get('wechat_work', {}).get('enabled') else None
        self.email = EmailSender(config) if config.get('email', {}).get('enabled') else None
        self.wechat = WechatNotifier(config) if config.get('wechat', {}).get('enabled') else None
    
    def send_report(self, report_content, projects=None):
        """发送报告到所有启用的渠道"""
        success_count = 0
        
        # 企业微信
        if self.wechat_work:
            if self.wechat_work.send(report_content):
                success_count += 1
        
        # 个人微信（Server酱/PushPlus）
        if self.wechat:
            title = f"招标项目日报"
            if projects:
                high_count = sum(1 for p in projects if p['feasibility']['total'] >= 80)
                if high_count > 0:
                    title = f"【{high_count}个高优先级】{title}"
            
            if self.wechat.send(title, report_content):
                success_count += 1
        
        # 邮件
        if self.email:
            subject = "招标项目日报"
            # 将 Markdown 转换为 HTML（简化版）
            html_content = self._markdown_to_html(report_content)
            if self.email.send(html_content, subject):
                success_count += 1
        
        if success_count > 0:
            logger.success(f"✅ 报告已推送到 {success_count} 个渠道")
        else:
            logger.warning("⚠️ 未启用任何通知渠道，报告已保存到本地文件")
        
        return success_count > 0
    
    def _markdown_to_html(self, markdown_text):
        """简单的 Markdown 转 HTML"""
        html = markdown_text
        
        # 标题
        html = html.replace('# ', '<h1>').replace('\n', '</h1>\n', 1)
        html = html.replace('## ', '<h2>').replace('\n', '</h2>\n')
        html = html.replace('### ', '<h3>').replace('\n', '</h3>\n')
        
        # 粗体
        import re
        html = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', html)
        
        # 换行
        html = html.replace('\n\n', '<br><br>')
        
        return f"""
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{ font-family: Arial, sans-serif; padding: 20px; }}
                h1 {{ color: #1890ff; }}
                h2 {{ color: #52c41a; margin-top: 20px; }}
                h3 {{ color: #666; }}
            </style>
        </head>
        <body>
            {html}
        </body>
        </html>
        """
