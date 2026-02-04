"""可行性评分器（多维度评分）"""

from datetime import datetime
from loguru import logger
from typing import Dict, Optional


class FeasibilityScorer:
    """可行性评分（支持多维度评分和分类策略）"""
    
    def __init__(self, config: Dict):
        """初始化评分器
        
        Args:
            config: 配置字典
        """
        self.config = config
        logger.info("✅ 评分器初始化成功")
    
    def calculate(
        self,
        announcement: Dict,
        match_results: Dict,
        location_result: Dict,
        content_analysis: Optional[Dict] = None,
        ai_extracted: Optional[Dict] = None,
        attachment_analysis: Optional[Dict] = None,
        direction_id: str = None
    ) -> Dict:
        """计算综合评分（0-100）
        
        评分维度（根据类别调整）：
        1. 关键词匹配 (20分)
        2. 内容相关度 (25分) - 新增
        3. AI提取完整性 (20分) - 新增
        4. 附件质量 (15分) - 新增
        5. 时间充足度 (10分)
        
        地域加分（不计入总分，额外加分）：
        - 文化氛围类 + 大连市：+5分
        - 其他类别靠近辽宁省：+1~3分
        
        Args:
            announcement: 公告信息
            match_results: 关键词匹配结果
            location_result: 地域匹配结果
            content_analysis: 内容分析结果（可选）
            ai_extracted: AI提取结果（可选）
            attachment_analysis: 附件分析结果（可选）
            direction_id: 业务方向ID
            
        Returns:
            评分结果字典
        """
        scores = {
            'keyword_match': 0,      # 关键词匹配度 (0-20)
            'content_relevance': 0,  # 内容相关度 (0-25)
            'ai_completeness': 0,    # AI提取完整性 (0-20)
            'attachment_quality': 0, # 附件质量 (0-15)
            'deadline_adequacy': 0,  # 时间充足度 (0-10)
            'location_bonus': 0      # 地域加分 (0-10，额外)
        }
        
        # 1. 关键词匹配分（最高 20 分）
        best_match = max(match_results.values(), key=lambda x: x['score'])
        scores['keyword_match'] = best_match['score'] * 20
        
        # 2. 内容相关度分（最高 25 分）
        if content_analysis:
            # 内容分析的score是0-100，需要转换到0-25
            scores['content_relevance'] = (content_analysis.get('score', 0) / 100) * 25
        else:
            # 如果没有内容分析，给基础分
            scores['content_relevance'] = 10
        
        # 3. AI提取完整性分（最高 20 分）
        if ai_extracted:
            completeness = self._calculate_ai_completeness(ai_extracted)
            scores['ai_completeness'] = completeness * 20
        else:
            scores['ai_completeness'] = 5  # 默认低分
        
        # 4. 附件质量分（最高 15 分）
        if attachment_analysis:
            # 附件分析的relevance_score是0-100
            scores['attachment_quality'] = (attachment_analysis.get('relevance_score', 0) / 100) * 15
        else:
            scores['attachment_quality'] = 0
        
        # 5. 时间充足度分（最高 10 分）
        scores['deadline_adequacy'] = self._calculate_deadline_score(announcement, ai_extracted)
        
        # 6. 地域加分（根据类别）
        scores['location_bonus'] = location_result.get('bonus_score', 0)
        
        # 计算总分（地域加分单独计算）
        base_total = sum(v for k, v in scores.items() if k != 'location_bonus')
        final_total = base_total + scores['location_bonus']
        final_total = min(final_total, 100)  # 最高100分
        
        return {
            'total': round(final_total, 1),
            'base_score': round(base_total, 1),
            'breakdown': {k: round(v, 1) for k, v in scores.items()},
            'level': self._get_level(final_total),
            'passes_filter': self._check_second_filter(final_total, ai_extracted, scores['deadline_adequacy'])
        }
    
    def _calculate_ai_completeness(self, ai_extracted: Dict) -> float:
        """计算AI提取的完整性（0-1.0）
        
        检查关键字段是否被成功提取：
        - 资格要求
        - 预算信息
        - 报名方式
        - 开标时间
        - 联系人
        
        Args:
            ai_extracted: AI提取结果
            
        Returns:
            完整性分数 0-1.0
        """
        if not ai_extracted:
            return 0
        
        # 定义关键字段
        key_fields = ['qualifications', 'budget', 'registration_method', 'opening_time', 'contact']
        
        # 计算有效字段数
        valid_count = 0
        for field in key_fields:
            value = ai_extracted.get(field)
            # 检查字段是否有实质内容
            if value and str(value).strip() and str(value) not in ['无', '未提供', 'N/A', '']:
                valid_count += 1
        
        completeness = valid_count / len(key_fields)
        return completeness
    
    def _calculate_deadline_score(self, announcement: Dict, ai_extracted: Optional[Dict]) -> float:
        """计算时间充足度评分（0-10）
        
        Args:
            announcement: 公告信息
            ai_extracted: AI提取结果
            
        Returns:
            时间评分 0-10
        """
        # 尝试从多个来源获取截止时间
        deadline_str = None
        
        if ai_extracted:
            deadline_str = ai_extracted.get('opening_time') or ai_extracted.get('deadline')
        
        if not deadline_str:
            deadline_str = announcement.get('deadline')
        
        if not deadline_str:
            # 没有明确截止时间，给中等分
            return 5
        
        try:
            days_left = self._calculate_days_left(deadline_str)
            
            if days_left >= 7:
                return 10  # 充足时间
            elif days_left >= 5:
                return 8
            elif days_left >= 3:
                return 6  # 最少3天（用户要求）
            elif days_left >= 1:
                return 3  # 时间紧张
            else:
                return 0  # 已过期
        except:
            return 5  # 解析失败，给中等分
    
    def _calculate_days_left(self, deadline_str: str) -> int:
        """计算剩余天数
        
        Args:
            deadline_str: 截止时间字符串
            
        Returns:
            剩余天数
        """
        try:
            # 尝试多种日期格式
            for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%d', 
                       '%Y年%m月%d日 %H:%M', '%Y年%m月%d日']:
                try:
                    deadline = datetime.strptime(deadline_str.strip(), fmt)
                    days = (deadline - datetime.now()).days
                    return max(0, days)
                except:
                    continue
            
            # 如果包含"年月日"但格式不标准，尝试提取
            import re
            match = re.search(r'(\d{4})[年-](\d{1,2})[月-](\d{1,2})', deadline_str)
            if match:
                year, month, day = match.groups()
                deadline = datetime(int(year), int(month), int(day))
                days = (deadline - datetime.now()).days
                return max(0, days)
            
            return 7  # 默认7天
        except:
            return 7
    
    def _check_second_filter(
        self,
        total_score: float,
        ai_extracted: Optional[Dict],
        deadline_score: float
    ) -> bool:
        """二次过滤检查
        
        过滤标准：
        1. 投标时间 >= 3天
        2. 综合评分 >= 60分
        3. 没有明确不符合的资格要求（可选）
        
        Args:
            total_score: 总分
            ai_extracted: AI提取结果
            deadline_score: 时间评分
            
        Returns:
            True: 通过二次过滤
            False: 不通过
        """
        # 检查总分
        min_score = self.config.get('scoring', {}).get('min_total_score', 60)
        if total_score < min_score:
            return False
        
        # 检查时间（deadline_score >= 6 表示至少3天）
        if deadline_score < 6:
            return False
        
        # TODO: 可以添加资格要求检查（需要AI模型支持）
        
        return True
    
    def _get_level(self, score: float) -> str:
        """评分等级
        
        Args:
            score: 总分
            
        Returns:
            等级描述
        """
        if score >= 80:
            return '高度推荐'
        elif score >= 70:
            return '强烈推荐'
        elif score >= 60:
            return '推荐'
        elif score >= 50:
            return '可考虑'
        else:
            return '不推荐'
