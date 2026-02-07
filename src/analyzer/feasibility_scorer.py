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
        2. 内容相关度 (25分)
        3. AI提取完整性 (20分)
        4. 附件质量 (15分)
        5. 时间综合评分 (15分) - 优化
           - 发布新鲜度 (5分): 越新越好
           - 截止充足度 (10分): 距离截止时间是否充足
        
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
        # 1. 业务方向匹配分（0-60）
        # 使用 KeywordMatcher 的 score（0-1）线性映射到 0-60
        best_match = max(match_results.values(), key=lambda x: x['score'])
        direction_score_raw = best_match['score']  # 0-1
        direction_score = direction_score_raw * 60

        # 针对特定方向（如院线电影等）后续可以在这里加一点点系数
        # 暂时保持统一，避免过度偏置

        # 2. 基础内容相关度（0-20）
        if content_analysis:
            # content_analysis['score'] 是 0-100，线性映射到 0-20
            content_score = (content_analysis.get("score", 0) / 100) * 20
        else:
            # 没有内容分析时给一个中等保守分，避免被打成很低分
            content_score = 10

        # 3. 时间评分（0-20），只要未过期就给中高分，主要用于排序
        time_score_result = self._calculate_time_score(announcement, ai_extracted)
        time_total = time_score_result["total"]  # 仍然是 0-15
        # 轻微放大到 0-20 区间，避免比重过小
        time_score = min(time_total / 15 * 20, 20) if time_total > 0 else 0

        # 4. 地域加分（0-5，额外）
        location_bonus = location_result.get("bonus_score", 0)
        # 控制在 0-5 之间，防止影响过大
        location_bonus = max(0, min(location_bonus, 5))

        # 5. AI / 附件仅用于标签，不直接计入总分
        ai_completeness = self._calculate_ai_completeness(ai_extracted) if ai_extracted else 0
        attachment_quality_score = 0
        if attachment_analysis:
            attachment_quality_score = attachment_analysis.get("relevance_score", 0)

        # 6. 计算总分（方向 + 内容 + 时间 为主干）
        base_total = direction_score + content_score + time_score
        final_total = min(base_total + location_bonus, 100)

        # 构造细分结果
        scores = {
            "direction_match": direction_score,
            "content_relevance": content_score,
            "time": time_score,
            "location_bonus": location_bonus,
            # 以下仅作为参考标签，不参与 base_total
            "ai_completeness_ratio": ai_completeness,          # 0-1
            "attachment_relevance": attachment_quality_score,  # 0-100 原始分
        }

        return {
            "total": round(final_total, 1),
            "base_score": round(base_total, 1),
            "breakdown": {k: round(v, 1) for k, v in scores.items()},
            "level": self._get_level(final_total),
            "passes_filter": self._check_second_filter(
                final_total,
                direction_score,
                time_score_result.get("deadline_adequacy", 0),
            ),
            "time_score_details": time_score_result.get("details", {}),
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
    
    def _calculate_time_score(self, announcement: Dict, ai_extracted: Optional[Dict] = None) -> Dict:
        """计算时间综合评分（优化版）
        
        评分维度：
        - 发布新鲜度 (0-5分): 越新越好
        - 截止充足度 (0-10分): 距离截止时间是否充足
        
        注意：在新的整体策略中，时间只用于区分“是否已过期”和排序，
        不再作为强力淘汰条件，但如果明确已截止，则整体会被视为丢弃档。
        """
        from datetime import datetime, timedelta
        
        now = datetime.now()
        score = {'publish_freshness': 0, 'deadline_adequacy': 0, 'details': {}}
        
        # 1. 发布新鲜度 (5分)
        publish_date_str = announcement.get('publish_date') or announcement.get('pub_date', '')
        if publish_date_str:
            try:
                publish_date = self._parse_date(publish_date_str)
                if publish_date:
                    days_ago = (now - publish_date).days
                    if days_ago <= 1:
                        score['publish_freshness'] = 5
                        score['details']['freshness'] = '今天/昨天发布'
                    elif days_ago <= 3:
                        score['publish_freshness'] = 4
                        score['details']['freshness'] = f'{days_ago}天前发布'
                    elif days_ago <= 7:
                        score['publish_freshness'] = 3
                        score['details']['freshness'] = f'{days_ago}天前发布'
                    elif days_ago <= 14:
                        score['publish_freshness'] = 2
                        score['details']['freshness'] = f'{days_ago}天前发布'
                    else:
                        score['publish_freshness'] = 1
                        score['details']['freshness'] = f'{days_ago}天前发布'
            except:
                score['publish_freshness'] = 2  # 解析失败给默认分
                score['details']['freshness'] = '发布时间未知'
        
        # 2. 截止充足度 (10分)
        deadline_str = None
        if ai_extracted:
            deadline_str = ai_extracted.get('opening_time') or ai_extracted.get('deadline')
        if not deadline_str:
            deadline_str = announcement.get('deadline')
        
        if deadline_str:
            try:
                days_left = self._calculate_days_left(deadline_str)
                
                if days_left < 0:
                    # 已截止：在上层会被视为丢弃，这里标记为 0 分
                    score['deadline_adequacy'] = 0
                    score['details']['deadline'] = '已截止'
                elif days_left <= 3:
                    # 时间较紧，但仍可作为候选
                    score['deadline_adequacy'] = 4
                    score['details']['deadline'] = f'仅剩{days_left}天'
                elif days_left <= 7:
                    score['deadline_adequacy'] = 7
                    score['details']['deadline'] = f'剩余{days_left}天'
                elif days_left <= 15:
                    score['deadline_adequacy'] = 9
                    score['details']['deadline'] = f'剩余{days_left}天'
                else:
                    score['deadline_adequacy'] = 10
                    score['details']['deadline'] = f'剩余{days_left}天，充足'
            except:
                score['deadline_adequacy'] = 6  # 解析失败给略高于中等分
                score['details']['deadline'] = '截止时间解析失败'
        else:
            # 没有截止时间，给中等偏上的分，并在文案中提示
            score['deadline_adequacy'] = 7
            score['details']['deadline'] = '未提供截止时间'
        
        score['total'] = score['publish_freshness'] + score['deadline_adequacy']
        return score
    
    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """解析日期字符串
        
        Args:
            date_str: 日期字符串
            
        Returns:
            datetime对象，失败返回None
        """
        if not date_str:
            return None
        
        try:
            # 尝试多种日期格式
            for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%d', 
                       '%Y年%m月%d日 %H:%M:%S', '%Y年%m月%d日 %H:%M', '%Y年%m月%d日']:
                try:
                    return datetime.strptime(date_str.strip(), fmt)
                except:
                    continue
            
            # 如果包含"年月日"但格式不标准，尝试提取
            import re
            match = re.search(r'(\d{4})[年\-/](\d{1,2})[月\-/](\d{1,2})', date_str)
            if match:
                year, month, day = match.groups()
                return datetime(int(year), int(month), int(day))
            
            return None
        except:
            return None
    
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
        # 1. 首先检查总分是否达到基础推荐门槛
        min_score = self.config.get("scoring", {}).get("min_total_score", 60)
        if total_score < min_score:
            return False

        # 2. 要求方向匹配足够强（方向分至少 40/60）
        # 这里通过传入的 direction_score_z (实际值) 来判断
        # 注意：direction_score_z 在调用处转换为 0-60 区间
        # 为兼容旧签名，这里只检查总分，方向强弱主要体现在总分上

        # 3. 截止时间：只要不是“明显时间不足”即可
        # deadline_score >= 6 代表至少还有约 3 天，这里略微放宽
        if deadline_score < 3:
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
