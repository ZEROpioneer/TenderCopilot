---
name: tender-spider
description: 军队采购网爬虫开发规范。使用 DrissionPage 爬取招标公告、处理反爬、下载附件。当开发或维护招标信息爬虫、处理网页数据抓取时使用。
---

# 军队采购网爬虫开发规范

## 核心原则

使用 DrissionPage 进行无头浏览器爬取，确保稳定性和反爬对抗能力。

## 爬虫实现规范

### 1. 基础配置

```python
from DrissionPage import ChromiumPage
from loguru import logger

class PLAPSpider:
    def __init__(self, headless=True):
        self.page = ChromiumPage()
        if headless:
            self.page.set.headless(True)
```

### 2. 公告列表爬取

**目标**：获取招标公告列表（标题、发布时间、链接、简介）

```python
def fetch_announcements(self, date_range=1):
    """爬取最近 N 天的招标公告"""
    logger.info("🔍 开始爬取招标公告列表")
    
    # 访问列表页
    self.page.get(self.list_url)
    
    # 等待页面加载
    self.page.wait.load_start()
    
    # 提取公告项
    announcements = []
    items = self.page.eles('css:.announcement-item')
    
    for item in items:
        announcement = {
            'title': item.ele('css:.title').text,
            'pub_date': item.ele('css:.date').text,
            'url': item.ele('tag:a').attr('href'),
            'summary': item.ele('css:.summary').text if item.ele('css:.summary') else ''
        }
        announcements.append(announcement)
        logger.info(f"📄 发现公告: {announcement['title']}")
    
    return announcements
```

### 3. 公告详情爬取

**目标**：获取完整公告内容、附件链接

```python
def fetch_detail(self, url):
    """爬取公告详情页"""
    logger.info(f"🔍 正在爬取详情: {url}")
    
    self.page.get(url)
    self.page.wait.load_start()
    
    # 提取内容
    detail = {
        'title': self.page.ele('css:.detail-title').text,
        'content': self.page.ele('css:.detail-content').html,
        'pub_date': self.page.ele('css:.pub-date').text,
        'attachments': []
    }
    
    # 提取附件
    attachment_links = self.page.eles('css:.attachment-link')
    for link in attachment_links:
        detail['attachments'].append({
            'name': link.text,
            'url': link.attr('href')
        })
    
    return detail
```

### 4. 附件下载

**目标**：下载 Word/PDF 报名材料模板

```python
def download_attachment(self, url, save_path):
    """下载附件文件"""
    logger.info(f"⬇️ 下载附件: {url}")
    
    try:
        response = self.page.get(url, retry=3, timeout=30)
        with open(save_path, 'wb') as f:
            f.write(response.content)
        logger.success(f"✅ 附件已保存: {save_path}")
        return True
    except Exception as e:
        logger.error(f"❌ 下载失败: {e}")
        return False
```

## 反爬对抗策略

### 1. 随机延迟

```python
import time
import random

# 请求间隔 2-5 秒
time.sleep(random.uniform(2, 5))
```

### 2. 错误重试

```python
def fetch_with_retry(self, url, max_retries=3):
    """带重试的请求"""
    for i in range(max_retries):
        try:
            self.page.get(url)
            return True
        except Exception as e:
            logger.warning(f"⚠️ 第 {i+1} 次尝试失败: {e}")
            time.sleep(5 * (i + 1))
    
    logger.error(f"❌ 请求失败，已重试 {max_retries} 次")
    return False
```

### 3. User-Agent 轮换

```python
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
    # 更多 UA
]

self.page.set.user_agent(random.choice(USER_AGENTS))
```

## 日志规范

统一使用以下格式：

```python
logger.info("🔍 正在爬取: {title}")      # 开始爬取
logger.success("✅ 爬取成功: {title}")   # 成功
logger.warning("⚠️ 跳过项目: {reason}")  # 警告
logger.error("❌ 爬取失败: {error}")     # 错误
```

## 数据结构

### 公告对象

```python
{
    'id': 'unique_id',              # 唯一标识（由标题+日期生成）
    'title': '项目标题',
    'content': '完整内容（HTML）',
    'pub_date': '2026-02-04',
    'location': '辽宁省大连市',      # 提取的地域信息
    'budget': '100万元',             # 提取的预算信息
    'deadline': '2026-02-10',       # 报名截止日期
    'contact': '联系人信息',
    'attachments': [
        {'name': '报名表.docx', 'url': 'http://...', 'local_path': 'data/attachments/xxx.docx'}
    ],
    'url': 'https://www.plap.mil.cn/...',
    'crawled_at': '2026-02-04 14:30:00'
}
```

## 注意事项

1. **始终使用无头模式**（生产环境）
2. **控制爬取频率**：每天 4 次定时爬取，避免频繁请求
3. **保存原始 HTML**：便于后续重新解析
4. **异常必须记录**：所有异常都要写入日志
5. **优雅退出**：关闭浏览器实例

```python
def close(self):
    """关闭爬虫"""
    if self.page:
        self.page.quit()
        logger.info("🔚 爬虫已关闭")
```
