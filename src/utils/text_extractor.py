"""统一的文本提取工具"""

import re
from typing import List, Optional, Dict
from loguru import logger


class TextExtractor:
    """文本提取器"""
    
    @staticmethod
    def clean_text(text: str) -> str:
        """清理文本（去除多余空白、特殊字符）
        
        Args:
            text: 原始文本
            
        Returns:
            清理后的文本
        """
        if not text:
            return ''
        
        # 去除多余空白
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()
        
        return text
    
    @staticmethod
    def extract_budget(text: str) -> Optional[float]:
        """从文本中提取金额（万元）
        
        Args:
            text: 包含金额的文本
            
        Returns:
            金额（万元），提取失败返回 None
            
        Examples:
            >>> TextExtractor.extract_budget("预算500万元")
            500.0
            >>> TextExtractor.extract_budget("100.5万")
            100.5
        """
        if not text:
            return None
        
        # 匹配模式：数字 + 万/万元
        patterns = [
            r'(\d+\.?\d*)\s*万元',
            r'(\d+\.?\d*)\s*万',
            r'预算[：:]\s*(\d+\.?\d*)\s*万',
            r'限价[：:]\s*(\d+\.?\d*)\s*万',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                try:
                    return float(match.group(1))
                except ValueError:
                    continue
        
        return None
    
    @staticmethod
    def extract_phone(text: str) -> List[str]:
        """从文本中提取电话号码
        
        Args:
            text: 包含电话的文本
            
        Returns:
            电话号码列表
        """
        if not text:
            return []
        
        # 手机号模式
        mobile_pattern = r'1[3-9]\d{9}'
        # 座机模式
        phone_pattern = r'0\d{2,3}-?\d{7,8}'
        
        phones = []
        
        # 提取手机号
        phones.extend(re.findall(mobile_pattern, text))
        
        # 提取座机
        phones.extend(re.findall(phone_pattern, text))
        
        # 去重
        return list(set(phones))
    
    @staticmethod
    def extract_contact_info(text: str) -> Dict[str, any]:
        """提取联系信息（姓名、电话、邮箱）
        
        Args:
            text: 包含联系信息的文本
            
        Returns:
            联系信息字典
        """
        info = {
            'phones': [],
            'emails': [],
            'contact_person': None
        }
        
        if not text:
            return info
        
        # 提取电话
        info['phones'] = TextExtractor.extract_phone(text)
        
        # 提取邮箱
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        info['emails'] = re.findall(email_pattern, text)
        
        # 提取联系人（简单模式）
        contact_patterns = [
            r'联系人[：:]\s*([^\s，,。；;]{2,4})',
            r'采购人[：:]\s*([^\s，,。；;]{2,4})',
        ]
        
        for pattern in contact_patterns:
            match = re.search(pattern, text)
            if match:
                info['contact_person'] = match.group(1)
                break
        
        return info
    
    @staticmethod
    def truncate(text: str, max_length: int = 100, suffix: str = '...') -> str:
        """截断文本
        
        Args:
            text: 原始文本
            max_length: 最大长度
            suffix: 后缀
            
        Returns:
            截断后的文本
        """
        if not text:
            return ''
        
        if len(text) <= max_length:
            return text
        
        return text[:max_length - len(suffix)] + suffix
    
    @staticmethod
    def extract_keywords(text: str, keywords: List[str]) -> List[str]:
        """提取文本中出现的关键词
        
        Args:
            text: 文本
            keywords: 关键词列表
            
        Returns:
            匹配到的关键词列表
        """
        if not text or not keywords:
            return []
        
        text_lower = text.lower()
        matched = []
        
        for keyword in keywords:
            if keyword.lower() in text_lower:
                matched.append(keyword)
        
        return matched
