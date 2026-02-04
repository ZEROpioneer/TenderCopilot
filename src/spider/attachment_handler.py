"""附件下载处理"""

import requests
from pathlib import Path
from loguru import logger


class AttachmentHandler:
    """附件下载处理器"""
    
    def __init__(self, config):
        self.config = config
        self.download_dir = Path('data/attachments')
        self.download_dir.mkdir(parents=True, exist_ok=True)
        
        self.max_size = config['spider'].get('max_attachment_size', 10) * 1024 * 1024  # MB to bytes
        self.allowed_types = config['spider'].get('attachment_types', ['.pdf', '.docx', '.doc'])
    
    def download(self, attachment):
        """下载附件"""
        url = attachment['url']
        name = attachment['name']
        
        # 检查文件类型
        if not any(url.lower().endswith(ext) for ext in self.allowed_types):
            logger.warning(f"⚠️ 跳过不支持的文件类型: {name}")
            return None
        
        logger.info(f"⬇️ 下载附件: {name}")
        
        try:
            # 下载文件
            response = requests.get(url, timeout=30, stream=True)
            response.raise_for_status()
            
            # 检查文件大小
            content_length = int(response.headers.get('Content-Length', 0))
            if content_length > self.max_size:
                logger.warning(f"⚠️ 文件过大，跳过: {name} ({content_length / 1024 / 1024:.2f}MB)")
                return None
            
            # 生成文件名
            filename = self._generate_filename(name, url)
            filepath = self.download_dir / filename
            
            # 保存文件
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            logger.success(f"✅ 附件已保存: {filepath}")
            return str(filepath)
            
        except Exception as e:
            logger.error(f"❌ 下载失败: {name} - {e}")
            return None
    
    def _generate_filename(self, name, url):
        """生成唯一文件名"""
        import hashlib
        from datetime import datetime
        
        # 提取扩展名
        ext = Path(url).suffix
        if not ext:
            ext = '.pdf'  # 默认
        
        # 生成时间戳 + hash
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
        
        return f"{timestamp}_{url_hash}{ext}"
