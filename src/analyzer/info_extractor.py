"""信息提取器（支持 OpenAI / Gemini / 自定义 OpenAI 兼容接口）"""

from loguru import logger
import json
import os
import requests


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
        analyzer_cfg = config['analyzer']
        # provider: openai / gemini / custom_openai / none
        self.provider = analyzer_cfg.get('provider', 'openai')
        self.api_key = analyzer_cfg.get('api_key') or analyzer_cfg.get('openai_api_key', '')
        # 通用模型名（OpenAI / Gemini 使用）
        self.model = analyzer_cfg.get('model', 'gpt-4o-mini')
        self.timeout = analyzer_cfg.get('timeout', 30)

        # 自定义 OpenAI 兼容接口配置（国内大模型等，例如智谱 GLM）
        self.custom_base_url = (analyzer_cfg.get('custom_base_url') or '').rstrip('/')
        self.custom_api_key = analyzer_cfg.get('custom_api_key') or os.getenv('CUSTOM_OPENAI_API_KEY', '')
        # 针对自定义接口单独配置模型名，避免误用 Gemini/OpenAI 的 model 字段
        self.custom_model = analyzer_cfg.get('custom_model') or self.model
        self.client = None

        if self.provider == 'none':
            logger.warning("⚠️ AI 分析已关闭（provider='none'）")
            return
        elif self.provider == 'gemini':
            self._init_gemini()
        elif self.provider == 'custom_openai':
            self._init_custom_openai()
        else:
            # 默认使用 OpenAI 官方接口
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
    
    def _init_custom_openai(self):
        """初始化自定义 OpenAI 兼容接口（仅检查配置，不创建客户端实例）"""
        if not self.custom_base_url or not self.custom_api_key:
            logger.warning("⚠️ 自定义 OpenAI 兼容模型未配置 base_url 或 api_key，AI 将不可用")
            self.client = None
            return
        logger.info(f"✅ 使用自定义 OpenAI 兼容模型: {self.custom_base_url}")
        # 使用 requests 直接调用，因此这里不需要真正的 client 对象
        self.client = True
    
    def extract(self, content):
        """提取招标公告关键信息"""
        # provider=none：显式关闭 AI 分析
        if self.provider == 'none':
            logger.debug("⚠️ provider='none'，跳过 AI 分析")
            return None

        # 自定义 OpenAI 兼容接口
        if self.provider == 'custom_openai':
            if not self.custom_base_url or not self.custom_api_key:
                logger.warning("⚠️ 自定义 OpenAI 兼容模型未正确配置，跳过 AI 分析")
                return None
            logger.info("🤖 开始 AI 分析 (使用 custom_openai)...")
            return self._extract_custom_openai(content)

        # OpenAI / Gemini 官方接口
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

    def _extract_custom_openai(self, content):
        """使用自定义 OpenAI 兼容接口提取"""
        try:
            # 智谱 GLM 的 OpenAI 兼容接口在 base_url 后直接追加 /chat/completions
            # 例如 base_url = https://open.bigmodel.cn/api/paas/v4
            # 最终请求 URL = https://open.bigmodel.cn/api/paas/v4/chat/completions
            url = f"{self.custom_base_url}/chat/completions"
            payload = {
                # 使用为自定义接口单独配置的模型名（如 glm-4-flash）
                "model": self.custom_model,
                "messages": [
                    {"role": "system", "content": "你是专业的招标文件分析助手。"},
                    {
                        "role": "user",
                        "content": self.EXTRACTION_PROMPT.format(content=content[:12000]),
                    },
                ],
                "temperature": 0.3,
                "max_tokens": 2000,
            }
            headers = {
                "Authorization": f"Bearer {self.custom_api_key}",
                "Content-Type": "application/json",
            }

            resp = requests.post(url, json=payload, headers=headers, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()

            # 兼容 OpenAI 风格响应
            message_content = data["choices"][0]["message"]["content"]
            result = json.loads(message_content)
            logger.success("✅ 自定义 OpenAI 兼容模型分析完成")
            return result

        except Exception as e:
            logger.error(f"❌ 自定义 OpenAI 兼容模型分析失败: {e}")
            logger.debug(f"错误详情: {str(e)}")
            return None
