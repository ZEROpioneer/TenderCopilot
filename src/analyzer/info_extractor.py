"""信息提取器（支持 OpenAI 和 Gemini）"""

from loguru import logger
import json
import os


class InfoExtractor:
    """招标信息提取器"""
    
    EXTRACTION_PROMPT = """
你是一个专业的招标文件分析助手。请从以下招标公告中提取关键信息。

招标公告内容：
{content}

请以 JSON 格式返回以下信息：
{{
    "supplier_qualifications": "供应商资格要求的详细描述",
    "max_budget": "项目最高限价（包含金额和单位）",
    "registration_requirements": {{
        "method": "报名方式",
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

如果某个字段在原文中未提及，请返回 null。
请只返回 JSON，不要有其他内容。
"""
    
    def __init__(self, config):
        self.provider = config['analyzer'].get('provider', 'openai')  # openai 或 gemini
        self.api_key = config['analyzer'].get('api_key') or config['analyzer'].get('openai_api_key', '')
        self.model = config['analyzer'].get('model', 'gpt-4o-mini')
        
        if self.provider == 'gemini':
            self._init_gemini()
        else:
            self._init_openai()
    
    def _init_openai(self):
        """初始化 OpenAI"""
        try:
            from openai import OpenAI
            self.client = OpenAI(api_key=self.api_key)
            logger.info("✅ 使用 OpenAI API")
        except Exception as e:
            logger.error(f"❌ OpenAI 初始化失败: {e}")
            self.client = None
    
    def _init_gemini(self):
        """初始化 Gemini"""
        try:
            import google.generativeai as genai
            genai.configure(api_key=self.api_key)
            self.client = genai.GenerativeModel(self.model)
            logger.info("✅ 使用 Google Gemini API")
        except Exception as e:
            logger.error(f"❌ Gemini 初始化失败: {e}")
            logger.info("提示: 需要安装 google-generativeai，运行: pip install google-generativeai")
            self.client = None
    
    def extract(self, content):
        """提取招标公告关键信息"""
        if not self.client:
            logger.warning("⚠️ AI 客户端未初始化")
            return None
        
        logger.info(f"🤖 开始 AI 分析 (使用 {self.provider})...")
        
        if self.provider == 'gemini':
            return self._extract_gemini(content)
        else:
            return self._extract_openai(content)
    
    def _extract_openai(self, content):
        """使用 OpenAI 提取"""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是专业的招标文件分析助手。"},
                    {"role": "user", "content": self.EXTRACTION_PROMPT.format(content=content[:12000])}
                ],
                temperature=0.3,
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            logger.success("✅ OpenAI 分析完成")
            return result
            
        except Exception as e:
            logger.error(f"❌ OpenAI 分析失败: {e}")
            return None
    
    def _extract_gemini(self, content):
        """使用 Gemini 提取"""
        try:
            prompt = self.EXTRACTION_PROMPT.format(content=content[:30000])  # Gemini 支持更长内容
            
            response = self.client.generate_content(
                prompt,
                generation_config={
                    'temperature': 0.3,
                    'max_output_tokens': 2048,
                }
            )
            
            # 提取 JSON
            text = response.text.strip()
            
            # 移除可能的 markdown 代码块标记
            if text.startswith('```json'):
                text = text[7:]
            if text.startswith('```'):
                text = text[3:]
            if text.endswith('```'):
                text = text[:-3]
            
            result = json.loads(text.strip())
            logger.success("✅ Gemini 分析完成")
            return result
            
        except Exception as e:
            logger.error(f"❌ Gemini 分析失败: {e}")
            logger.debug(f"错误详情: {str(e)}")
            return None
