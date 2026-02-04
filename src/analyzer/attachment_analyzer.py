"""附件内容分析器
分析PDF/Word附件的内容
"""

from loguru import logger
from typing import Dict, List
from pathlib import Path
import re


class AttachmentAnalyzer:
    """附件内容分析器"""
    
    def __init__(self, config: Dict):
        """初始化分析器
        
        Args:
            config: 配置字典
        """
        self.config = config
        logger.info("✅ 附件分析器初始化成功")
    
    def analyze(
        self,
        filepath: str,
        keywords: List[str],
        direction: Dict
    ) -> Dict:
        """分析附件内容
        
        提取：
        1. 资格要求详情
        2. 预算金额
        3. 技术要求
        4. 评分标准
        5. 重要时间节点
        
        Args:
            filepath: 附件文件路径
            keywords: 业务关键词列表
            direction: 业务方向配置
            
        Returns:
            {
                'has_relevant_content': True/False,
                'extracted_info': {...},
                'relevance_score': 0-100,
                'text_length': int
            }
        """
        try:
            # 提取文本
            text = self._extract_text(filepath)
            
            if not text or len(text) < 50:
                return {
                    'has_relevant_content': False,
                    'extracted_info': {},
                    'relevance_score': 0,
                    'text_length': 0,
                    'error': '附件内容为空或过短'
                }
            
            # 检查关键词相关性
            keyword_matches = sum(1 for kw in keywords if kw in text)
            relevance_score = (keyword_matches / len(keywords)) * 100 if keywords else 0
            
            # 提取结构化信息
            extracted_info = {
                'budget': self._extract_budget(text),
                'qualifications': self._extract_qualifications(text),
                'deadline': self._extract_deadline(text),
                'technical_requirements': self._extract_technical_requirements(text, keywords)
            }
            
            return {
                'has_relevant_content': relevance_score > 20,
                'extracted_info': extracted_info,
                'relevance_score': round(relevance_score, 1),
                'text_length': len(text)
            }
            
        except Exception as e:
            logger.error(f"❌ 分析附件失败: {e}")
            return {
                'has_relevant_content': False,
                'extracted_info': {},
                'relevance_score': 0,
                'text_length': 0,
                'error': str(e)
            }
    
    def _extract_text(self, filepath: str) -> str:
        """从附件中提取文本
        
        Args:
            filepath: 文件路径
            
        Returns:
            提取的文本内容
        """
        file_path = Path(filepath)
        
        if not file_path.exists():
            logger.warning(f"⚠️ 附件文件不存在: {filepath}")
            return ''
        
        ext = file_path.suffix.lower()
        
        try:
            if ext == '.pdf':
                return self._extract_from_pdf(filepath)
            elif ext in ['.doc', '.docx']:
                return self._extract_from_docx(filepath)
            else:
                logger.warning(f"⚠️ 不支持的文件格式: {ext}")
                return ''
        except Exception as e:
            logger.error(f"❌ 提取文本失败: {e}")
            return ''
    
    def _extract_from_pdf(self, filepath: str) -> str:
        """从PDF提取文本"""
        try:
            import pdfplumber
            
            text = ''
            with pdfplumber.open(filepath) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + '\n'
            
            return text
        except ImportError:
            logger.warning("⚠️ 未安装 pdfplumber，跳过PDF分析。请运行: pip install pdfplumber")
            return ''
        except Exception as e:
            logger.error(f"❌ 提取PDF文本失败: {e}")
            return ''
    
    def _extract_from_docx(self, filepath: str) -> str:
        """从Word文档提取文本"""
        try:
            from docx import Document
            
            doc = Document(filepath)
            text = '\n'.join([paragraph.text for paragraph in doc.paragraphs])
            
            return text
        except ImportError:
            logger.warning("⚠️ 未安装 python-docx，跳过Word分析。请运行: pip install python-docx")
            return ''
        except Exception as e:
            logger.error(f"❌ 提取Word文本失败: {e}")
            return ''
    
    def _extract_budget(self, text: str) -> Dict:
        """提取预算信息"""
        try:
            # 匹配金额模式
            patterns = [
                r'预算[：:]\s*([0-9.,]+)\s*([万千百]?)元',
                r'限价[：:]\s*([0-9.,]+)\s*([万千百]?)元',
                r'最高限价[：:]\s*([0-9.,]+)\s*([万千百]?)元',
                r'([0-9.,]+)\s*([万千百]?)元以内',
            ]
            
            for pattern in patterns:
                match = re.search(pattern, text)
                if match:
                    amount = match.group(1).replace(',', '')
                    unit = match.group(2)
                    
                    # 转换为数字
                    try:
                        num = float(amount)
                        if unit == '万':
                            num *= 10000
                        elif unit == '千':
                            num *= 1000
                        elif unit == '百':
                            num *= 100
                        
                        return {
                            'found': True,
                            'amount': num,
                            'text': match.group(0)
                        }
                    except:
                        pass
            
            return {'found': False}
            
        except Exception as e:
            logger.debug(f"提取预算失败: {e}")
            return {'found': False}
    
    def _extract_qualifications(self, text: str) -> List[str]:
        """提取资格要求"""
        qualifications = []
        
        # 常见资格关键词
        qual_keywords = ['资质', '证书', '许可证', '执照', '等级', '认证']
        
        # 查找包含资格关键词的句子
        sentences = re.split(r'[。；\n]', text)
        for sentence in sentences:
            if any(kw in sentence for kw in qual_keywords):
                qualifications.append(sentence.strip())
        
        return qualifications[:5]  # 最多返回5条
    
    def _extract_deadline(self, text: str) -> Dict:
        """提取截止时间"""
        try:
            patterns = [
                r'投标截止时间[：:]\s*(\d{4}年\d{1,2}月\d{1,2}日\s*\d{1,2}[:：]\d{2})',
                r'截止时间[：:]\s*(\d{4}-\d{2}-\d{2}\s*\d{2}:\d{2})',
                r'(\d{4}年\d{1,2}月\d{1,2}日\s*\d{1,2}[:：]\d{2})\s*前',
            ]
            
            for pattern in patterns:
                match = re.search(pattern, text)
                if match:
                    return {
                        'found': True,
                        'deadline': match.group(1)
                    }
            
            return {'found': False}
            
        except Exception as e:
            logger.debug(f"提取截止时间失败: {e}")
            return {'found': False}
    
    def _extract_technical_requirements(self, text: str, keywords: List[str]) -> List[str]:
        """提取技术要求（包含业务关键词的句子）"""
        requirements = []
        
        sentences = re.split(r'[。；\n]', text)
        for sentence in sentences:
            # 如果句子包含业务关键词且长度适中
            if any(kw in sentence for kw in keywords) and 10 < len(sentence) < 200:
                requirements.append(sentence.strip())
        
        return requirements[:10]  # 最多返回10条
