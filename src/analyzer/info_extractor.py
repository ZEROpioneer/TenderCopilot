"""信息提取器（支持 OpenAI / Gemini / 自定义 OpenAI 兼容接口）"""

from loguru import logger
import json
import os
import requests
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from src.schema import TenderItem


# 解析失败时的安全默认值
_DEFAULT_EXTRACTED = {
    "score": 60,
    "confidentiality_req": "未知",
    "project_summary": "未知",
    "doc_deadline": "未知",
    "bid_deadline": "未知",
    "budget_info": "未公布",
}


class InfoExtractor:
    """招标信息提取器（精准提取 4 大核心要素）"""

    EXTRACTION_PROMPT = """你是一个专业的军队采购招投标分析师。请阅读以下招标公告，并提取关键信息。
你必须返回一个合法的 JSON 字符串，包含以下字段，不要输出任何 Markdown 标记：

{{
  "score": 85,
  "confidentiality_req": "提取是否需要保密资质（如：三级保密资质、不需要、未提及）",
  "project_summary": "用20个字以内概括核心采购内容",
  "doc_deadline": "提取报名或获取招标文件的截止时间。未提及填'未知'",
  "bid_deadline": "提取开标或递交响应文件的准确时间。未提及填'未知'",
  "budget_info": "提取项目预算或最高限价。未提及填'未公布'"
}}

招标公告内容：
{content}

请只返回 JSON，不要有其他内容。"""
    
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
    
    def _parse_and_assign(self, raw_text: str, item: Optional["TenderItem"] = None) -> dict:
        """解析 AI 返回的 JSON，赋给 item，返回解析后的 dict。解析失败时使用安全默认值。"""
        text = (raw_text or "").strip()
        for prefix in ("```json", "```"):
            if text.startswith(prefix):
                text = text[len(prefix):].strip()
        if text.endswith("```"):
            text = text[:-3].strip()
        # 尝试解析：先直接解析，失败则截取首尾 { } 之间的内容
        result = None
        for candidate in (
            [text]
            + ([text[text.find("{") : text.rfind("}") + 1]] if "{" in text and "}" in text else [])
        ):
            try:
                result = json.loads(candidate)
                break
            except json.JSONDecodeError:
                continue
        if result is None:
            logger.warning("⚠️ AI 返回非合法 JSON，使用默认值")
            result = dict(_DEFAULT_EXTRACTED)

        def _str(v, default=""):
            return str(v).strip() if v is not None else default

        score = result.get("score")
        score_val = max(0, min(100, float(score))) if isinstance(score, (int, float)) else _DEFAULT_EXTRACTED["score"]
        confidentiality_req = _str(result.get("confidentiality_req"), _DEFAULT_EXTRACTED["confidentiality_req"])
        project_summary = _str(result.get("project_summary"), _DEFAULT_EXTRACTED["project_summary"])
        doc_deadline = _str(result.get("doc_deadline"), _DEFAULT_EXTRACTED["doc_deadline"])
        bid_deadline = _str(result.get("bid_deadline"), _DEFAULT_EXTRACTED["bid_deadline"])
        budget_info = _str(result.get("budget_info"), _DEFAULT_EXTRACTED["budget_info"])

        if item is not None:
            item.ai_score = score_val
            item.confidentiality_req = confidentiality_req
            item.project_summary = project_summary
            item.doc_deadline = doc_deadline
            item.bid_deadline = bid_deadline
            item.budget_info = budget_info

        return {
            "score": score_val,
            "confidentiality_req": confidentiality_req,
            "project_summary": project_summary,
            "doc_deadline": doc_deadline,
            "bid_deadline": bid_deadline,
            "budget_info": budget_info,
        }

    def extract(self, content: str, item: Optional["TenderItem"] = None) -> Optional[dict]:
        """提取招标公告关键信息，解析后赋给 item 对应属性。"""
        # provider=none：显式关闭 AI 分析
        if self.provider == 'none':
            logger.debug("⚠️ provider='none'，跳过 AI 分析")
            return None

        # 【临时绕过】跳过 AI 调用，使用默认结构
        BYPASS_AI = os.getenv('TENDERCOPILOT_BYPASS_AI', '1') == '1'
        if BYPASS_AI:
            result = dict(_DEFAULT_EXTRACTED)
            if item is not None:
                item.ai_score = result["score"]
                item.confidentiality_req = result["confidentiality_req"]
                item.project_summary = result["project_summary"]
                item.doc_deadline = result["doc_deadline"]
                item.bid_deadline = result["bid_deadline"]
                item.budget_info = result["budget_info"]
            return result

        # 自定义 OpenAI 兼容接口
        if self.provider == 'custom_openai':
            if not self.custom_base_url or not self.custom_api_key:
                logger.warning("⚠️ 自定义 OpenAI 兼容模型未正确配置，跳过 AI 分析")
                return None
            logger.info("🤖 开始 AI 分析 (使用 custom_openai)...")
            return self._extract_custom_openai(content, item)

        # OpenAI / Gemini 官方接口
        if not self.client:
            logger.warning("⚠️ AI 客户端未初始化")
            return None

        logger.info(f"🤖 开始 AI 分析 (使用 {self.provider})...")

        if self.provider == 'gemini':
            return self._extract_gemini(content, item)
        else:
            return self._extract_openai(content, item)
    
    def _extract_openai(self, content: str, item: Optional["TenderItem"] = None) -> Optional[dict]:
        """使用 OpenAI 提取"""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是专业的军队采购招投标分析师，只返回合法 JSON。"},
                    {"role": "user", "content": self.EXTRACTION_PROMPT.format(content=content[:12000])}
                ],
                temperature=0.3,
                response_format={"type": "json_object"}
            )
            raw = response.choices[0].message.content
            result = self._parse_and_assign(raw, item)
            logger.success("✅ OpenAI 分析完成")
            return result
        except Exception as e:
            logger.error(f"❌ OpenAI 分析失败: {e}")
            result = dict(_DEFAULT_EXTRACTED)
            if item is not None:
                item.ai_score = result["score"]
                item.confidentiality_req = result["confidentiality_req"]
                item.project_summary = result["project_summary"]
                item.doc_deadline = result["doc_deadline"]
                item.bid_deadline = result["bid_deadline"]
                item.budget_info = result["budget_info"]
            return result

    def _extract_gemini(self, content: str, item: Optional["TenderItem"] = None) -> Optional[dict]:
        """使用 Gemini 提取"""
        try:
            prompt = self.EXTRACTION_PROMPT.format(content=content[:30000])
            response = self.client.generate_content(
                prompt,
                generation_config={'temperature': 0.3, 'max_output_tokens': 2048}
            )
            raw = response.text.strip()
            result = self._parse_and_assign(raw, item)
            logger.success("✅ Gemini 分析完成")
            return result
        except Exception as e:
            logger.error(f"❌ Gemini 分析失败: {e}")
            logger.debug(f"错误详情: {str(e)}")
            result = dict(_DEFAULT_EXTRACTED)
            if item is not None:
                item.ai_score = result["score"]
                item.confidentiality_req = result["confidentiality_req"]
                item.project_summary = result["project_summary"]
                item.doc_deadline = result["doc_deadline"]
                item.bid_deadline = result["bid_deadline"]
                item.budget_info = result["budget_info"]
            return result

    def _extract_custom_openai(self, content: str, item: Optional["TenderItem"] = None) -> Optional[dict]:
        """使用自定义 OpenAI 兼容接口提取"""
        try:
            url = f"{self.custom_base_url}/chat/completions"
            payload = {
                "model": self.custom_model,
                "messages": [
                    {"role": "system", "content": "你是专业的军队采购招投标分析师，只返回合法 JSON。"},
                    {"role": "user", "content": self.EXTRACTION_PROMPT.format(content=content[:12000])},
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
            message_content = data["choices"][0]["message"]["content"]
            result = self._parse_and_assign(message_content, item)
            logger.success("✅ 自定义 OpenAI 兼容模型分析完成")
            return result
        except Exception as e:
            logger.error(f"❌ 自定义 OpenAI 兼容模型分析失败: {e}")
            logger.debug(f"错误详情: {str(e)}")
            result = dict(_DEFAULT_EXTRACTED)
            if item is not None:
                item.ai_score = result["score"]
                item.confidentiality_req = result["confidentiality_req"]
                item.project_summary = result["project_summary"]
                item.doc_deadline = result["doc_deadline"]
                item.bid_deadline = result["bid_deadline"]
                item.budget_info = result["budget_info"]
            return result
