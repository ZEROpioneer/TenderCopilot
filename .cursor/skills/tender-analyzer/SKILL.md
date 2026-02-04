---
name: tender-analyzer
description: 招标文件智能分析。使用 OpenAI API 从招标公告中提取关键信息（资格要求、限价、报名信息、开标日期、联系人）。当需要分析招标文档、提取结构化信息时使用。
---

# 招标文件智能分析

## 核心功能

使用 OpenAI GPT 模型从招标公告中自动提取关键业务信息，减少人工阅读成本。

## 需要提取的信息

### 必提字段

1. **供应商资格要求**：营业执照、资质证书、业绩要求等
2. **项目最高限价**：预算金额、限价范围
3. **报名要求和信息**：报名方式、所需材料、报名地点
4. **开标日期地点**：具体时间、地点
5. **项目联系人信息**：姓名、电话、邮箱

### 可选字段

- 项目概况
- 技术要求
- 服务期限
- 付款方式
- 其他特殊要求

## OpenAI API 调用规范

### 1. 提示词模板

```python
EXTRACTION_PROMPT = """
你是一个专业的招标文件分析助手。请从以下招标公告中提取关键信息。

招标公告内容：
{content}

请以 JSON 格式返回以下信息：
{{
    "supplier_qualifications": "供应商资格要求的详细描述",
    "max_budget": "项目最高限价（包含金额和单位）",
    "registration_requirements": {{
        "method": "报名方式（现场/线上/邮寄等）",
        "materials": ["所需材料列表"],
        "location": "报名地点",
        "deadline": "报名截止日期和时间"
    }},
    "bidding_info": {{
        "date": "开标日期（YYYY-MM-DD）",
        "time": "开标时间（HH:MM）",
        "location": "开标地点"
    }},
    "contact": {{
        "name": "联系人姓名",
        "phone": "联系电话",
        "email": "电子邮箱"
    }},
    "project_overview": "项目概况简述",
    "special_requirements": "特殊要求（如有）"
}}

如果某个字段在原文中未提及，请返回 null 或空字符串。
"""
```

### 2. API 调用封装

```python
from openai import OpenAI
from loguru import logger
import json

class InfoExtractor:
    def __init__(self, api_key, model="gpt-4"):
        self.client = OpenAI(api_key=api_key)
        self.model = model
    
    def extract(self, content):
        """提取招标公告关键信息"""
        logger.info("🤖 开始 AI 分析...")
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是专业的招标文件分析助手。"},
                    {"role": "user", "content": EXTRACTION_PROMPT.format(content=content)}
                ],
                temperature=0.3,  # 降低随机性，保证准确性
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            logger.success("✅ AI 分析完成")
            return result
            
        except Exception as e:
            logger.error(f"❌ AI 分析失败: {e}")
            return None
```

### 3. 结果验证

```python
def validate_extraction(result):
    """验证提取结果的完整性"""
    required_fields = [
        'supplier_qualifications',
        'max_budget',
        'registration_requirements',
        'bidding_info',
        'contact'
    ]
    
    missing = []
    for field in required_fields:
        if not result.get(field):
            missing.append(field)
    
    if missing:
        logger.warning(f"⚠️ 缺失字段: {', '.join(missing)}")
    
    return len(missing) == 0
```

## 处理附件文件

### PDF 文件处理

```python
import pdfplumber

def extract_from_pdf(pdf_path):
    """从 PDF 提取文本"""
    logger.info(f"📄 正在读取 PDF: {pdf_path}")
    
    text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text += page.extract_text() + "\n"
    
    return text
```

### Word 文件处理

```python
from docx import Document

def extract_from_docx(docx_path):
    """从 Word 文档提取文本"""
    logger.info(f"📄 正在读取 Word: {docx_path}")
    
    doc = Document(docx_path)
    text = "\n".join([para.text for para in doc.paragraphs])
    
    return text
```

## 智能内容合并

```python
def prepare_content_for_analysis(announcement):
    """准备分析内容"""
    parts = []
    
    # 1. 标题
    parts.append(f"项目标题：{announcement['title']}")
    
    # 2. 网页正文
    if announcement.get('content'):
        parts.append(f"\n正文内容：\n{announcement['content']}")
    
    # 3. 附件内容
    for attachment in announcement.get('attachments', []):
        if attachment.get('local_path'):
            file_path = attachment['local_path']
            
            if file_path.endswith('.pdf'):
                text = extract_from_pdf(file_path)
            elif file_path.endswith('.docx'):
                text = extract_from_docx(file_path)
            else:
                continue
            
            parts.append(f"\n附件《{attachment['name']}》内容：\n{text}")
    
    # 合并并限制长度（GPT token 限制）
    full_text = "\n".join(parts)
    
    # 如果超过 token 限制，进行智能截取
    if len(full_text) > 12000:  # 约 3000 tokens
        logger.warning("⚠️ 内容过长，进行智能截取")
        full_text = smart_truncate(full_text, max_length=12000)
    
    return full_text
```

## 结构化数据存储

### 提取结果格式

```python
{
    'announcement_id': 'xxx',
    'extracted_at': '2026-02-04 14:30:00',
    'extracted_info': {
        'supplier_qualifications': '具有有效的营业执照；具有软件开发相关资质；近三年有类似项目业绩',
        'max_budget': '100万元',
        'registration_requirements': {
            'method': '现场报名',
            'materials': [
                '营业执照副本复印件',
                '资质证书复印件',
                '法定代表人授权书',
                '报名表（加盖公章）'
            ],
            'location': '辽宁省大连市XX区XX路XX号',
            'deadline': '2026-02-10 17:00'
        },
        'bidding_info': {
            'date': '2026-02-15',
            'time': '09:30',
            'location': '辽宁省大连市XX区XX路XX号会议室'
        },
        'contact': {
            'name': '张三',
            'phone': '0411-12345678',
            'email': 'zhangsan@example.com'
        },
        'project_overview': '某部队文化氛围建设项目，包括文化墙设计、制作与安装',
        'special_requirements': '需要保密承诺书'
    },
    'validation_passed': True,
    'confidence_score': 0.95
}
```

## 错误处理策略

### 1. API 调用失败

```python
def extract_with_retry(content, max_retries=3):
    """带重试的提取"""
    for i in range(max_retries):
        try:
            result = extractor.extract(content)
            if result and validate_extraction(result):
                return result
        except Exception as e:
            logger.warning(f"⚠️ 第 {i+1} 次尝试失败: {e}")
            time.sleep(5 * (i + 1))
    
    logger.error("❌ 提取失败，已达最大重试次数")
    return None
```

### 2. 降级策略

如果 AI 提取失败，使用规则提取：

```python
def fallback_extraction(content):
    """规则提取（降级方案）"""
    logger.warning("⚠️ 使用规则提取（降级）")
    
    result = {}
    
    # 正则提取预算
    budget_pattern = r'预算[：:]\s*(\d+\.?\d*)万?元'
    budget_match = re.search(budget_pattern, content)
    if budget_match:
        result['max_budget'] = budget_match.group(1) + '万元'
    
    # 正则提取联系电话
    phone_pattern = r'1[3-9]\d{9}|\d{3,4}-\d{7,8}'
    phone_match = re.search(phone_pattern, content)
    if phone_match:
        result['contact'] = {'phone': phone_match.group(0)}
    
    # ... 更多规则
    
    return result
```

## 质量评估

```python
def calculate_confidence(result):
    """计算提取置信度"""
    score = 0
    
    # 必填字段完整性
    if result.get('supplier_qualifications'):
        score += 0.2
    if result.get('max_budget'):
        score += 0.2
    if result.get('registration_requirements'):
        score += 0.2
    if result.get('bidding_info'):
        score += 0.2
    if result.get('contact'):
        score += 0.2
    
    return score
```

## 使用示例

```python
# 完整分析流程
def analyze_announcement(announcement):
    """分析招标公告"""
    # 1. 准备内容
    content = prepare_content_for_analysis(announcement)
    
    # 2. AI 提取
    result = extract_with_retry(content)
    
    # 3. 降级处理
    if not result:
        result = fallback_extraction(content)
    
    # 4. 验证和评分
    valid = validate_extraction(result)
    confidence = calculate_confidence(result)
    
    return {
        'announcement_id': announcement['id'],
        'extracted_at': datetime.now().isoformat(),
        'extracted_info': result,
        'validation_passed': valid,
        'confidence_score': confidence
    }
```

## 成本控制

- 使用 `gpt-4o-mini` 降低成本（准确性稍低）
- 缓存已分析内容，避免重复调用
- 批量处理时控制并发数
- 设置每日 API 调用额度上限

## 配置

从 `config/settings.yaml` 读取：

```yaml
analyzer:
  openai_api_key: "${OPENAI_API_KEY}"
  model: "gpt-4"
  max_tokens: 2000
  temperature: 0.3
  timeout: 30
```
