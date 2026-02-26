"""统一配置管理器

功能：
- 统一加载所有配置文件
- 支持点号路径访问（如 config.get('spider.timeout')）
- 配置验证和默认值处理
- 环境变量自动替换
- 配置缓存
"""

import os
import yaml
from pathlib import Path
from typing import Any, Dict, Optional
from loguru import logger


class ConfigError(Exception):
    """配置错误"""
    pass


class ConfigManager:
    """配置管理器"""
    
    def __init__(self, config_dir: str = 'config'):
        """初始化配置管理器
        
        Args:
            config_dir: 配置文件目录路径
        """
        self.config_dir = Path(config_dir)
        self._config: Dict[str, Any] = {}
        self._loaded = False
    
    def load_all(self) -> 'ConfigManager':
        """加载所有配置文件
        
        Returns:
            ConfigManager 实例（支持链式调用）
        """
        if self._loaded:
            logger.debug("配置已加载，跳过重复加载")
            return self
        
        try:
            # 1. 加载主配置
            logger.debug("加载主配置文件...")
            settings = self._load_yaml('settings.yaml')
            self._config.update(settings)
            
            # 2. 加载业务方向配置
            logger.debug("加载业务方向配置...")
            business = self._load_yaml('business_directions.yaml')
            self._config['business_directions'] = business.get('business_directions', {})
            self._config['global_exclude'] = business.get('global_exclude', {})
            
            # 3. 加载通知配置
            logger.debug("加载通知配置...")
            notifications = self._load_yaml('notifications.yaml')
            self._config.update(notifications)
            
            # 3.5 加载评分配置（可选，用于动态规则引擎）
            try:
                scoring = self._load_yaml('scoring_config.yaml')
                if scoring:
                    self._config['scoring_config'] = scoring
            except FileNotFoundError:
                self._config['scoring_config'] = {
                    'weights': {
                        'title_keyword': 30,
                        'content_keyword': 15,
                        'location_match': 20,
                        'budget_high': 10,
                        'time_urgent': -10,
                    },
                    'budget_high_threshold_wan': 50,
                    'time_urgent_threshold_days': 3,
                    'custom_rules': [],
                }
            
            # 4. 尝试加载可选配置（向后兼容）
            # 确保 announcement_filter.smart_track 有默认值
            af = self._config.get('announcement_filter', {})
            if 'smart_track' not in af:
                af['smart_track'] = {
                    'enabled': True,
                    'score_threshold': 60,
                    'smart_track_types': ['更正公告', '流标公告', '废标公告', '变更公告'],
                }
            
            # filter_settings.yaml（将被废弃，如果存在则合并）
            try:
                filter_settings = self._load_yaml('filter_settings.yaml')
                if filter_settings:
                    logger.warning("⚠️ filter_settings.yaml 已废弃，请迁移到 settings.yaml")
                    # 只合并 crawl_strategy 如果主配置中没有
                    if 'crawl_strategy' not in self._config and 'crawl_strategy' in filter_settings:
                        self._config['crawl_strategy'] = filter_settings['crawl_strategy']
            except FileNotFoundError:
                pass
            
            # search_keywords.yaml（将被废弃）
            try:
                search_config = self._load_yaml('search_keywords.yaml')
                if search_config:
                    logger.warning("⚠️ search_keywords.yaml 已废弃，关键词将从 business_directions.yaml 读取")
                    # 只在没有 crawl_strategy 时才使用
                    if 'crawl_strategy' not in self._config and 'crawl_strategy' in search_config:
                        self._config['crawl_strategy'] = search_config['crawl_strategy']
            except FileNotFoundError:
                pass
            
            # 5. 处理环境变量
            logger.debug("处理环境变量...")
            self._process_env_vars()
            
            # 6. 应用默认值
            logger.debug("应用默认值...")
            self._apply_defaults()
            
            # 7. 验证配置
            logger.debug("验证配置...")
            self.validate()
            
            self._loaded = True
            logger.success("✅ 配置加载完成")
            
            return self
            
        except Exception as e:
            logger.error(f"❌ 配置加载失败: {e}")
            raise ConfigError(f"配置加载失败: {e}") from e
    
    def _load_yaml(self, filename: str) -> Dict[str, Any]:
        """加载 YAML 配置文件
        
        Args:
            filename: 文件名
            
        Returns:
            配置字典
        """
        filepath = self.config_dir / filename
        if not filepath.exists():
            raise FileNotFoundError(f"配置文件不存在: {filepath}")
        
        with open(filepath, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
            return config or {}
    
    def _process_env_vars(self):
        """处理配置中的环境变量引用
        
        将形如 ${VAR_NAME} 的字符串替换为环境变量值。
        仅对「当前启用功能」所需的环境变量未设置时发出警告，避免噪音。
        """
        # 收集当前启用功能所需的环境变量
        required_vars = set()
        provider = self._config.get("analyzer", {}).get("provider", "")
        if provider == "gemini":
            required_vars.add("GEMINI_API_KEY")
        elif provider == "custom_openai":
            required_vars.add("CUSTOM_OPENAI_API_KEY")
        elif provider == "openai":
            required_vars.add("OPENAI_API_KEY")

        n = self._config.get("wechat_work", {}) or {}
        if n.get("enabled"):
            required_vars.add("WECHAT_WORK_WEBHOOK")
        n = self._config.get("email", {}) or {}
        if n.get("enabled"):
            required_vars.add("EMAIL_PASSWORD")
        n = self._config.get("wechat", {}) or {}
        if n.get("enabled"):
            required_vars.add("WECHAT_PERSONAL_TOKEN")
        n = self._config.get("dingtalk", {}) or {}
        if n.get("enabled"):
            required_vars.add("DINGTALK_WEBHOOK")
            required_vars.add("DINGTALK_SECRET")

        def replace_env_vars(obj):
            if isinstance(obj, dict):
                return {k: replace_env_vars(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [replace_env_vars(item) for item in obj]
            elif isinstance(obj, str) and obj.startswith("${") and obj.endswith("}"):
                var_name = obj[2:-1]
                env_value = os.getenv(var_name)
                if env_value is None or (isinstance(env_value, str) and not env_value.strip()):
                    if var_name in required_vars:
                        logger.warning(f"⚠️ 环境变量未设置（当前功能需要）: {var_name}")
                    return ""
                return env_value
            return obj

        self._config = replace_env_vars(self._config)
    
    def _apply_defaults(self):
        """应用默认值"""
        defaults = {
            'crawl_strategy': {
                'max_pages': 5,
                'max_consecutive_exists': 5,
                'initial_hours': 168,
            },
            'spider': {
                'max_concurrent_details': 3,
                'wait_ajax_load': 0.5,
                'wait_page_refresh': 1,
                'wait_between_pages': 2,
            },
            'deep_analysis': {
                'enabled': True,
                'analyze_content': True,
                'extract_ai': True,
                'analyze_attachments': True,
            },
        }
        
        # 递归合并默认值（不覆盖已有配置）
        def merge_defaults(config, defaults):
            for key, value in defaults.items():
                if key not in config:
                    config[key] = value
                elif isinstance(value, dict) and isinstance(config[key], dict):
                    merge_defaults(config[key], value)
        
        merge_defaults(self._config, defaults)
    
    def validate(self):
        """验证配置完整性和有效性"""
        required_keys = [
            'database',
            'spider',
            'business_directions',
        ]
        
        missing_keys = []
        for key in required_keys:
            if key not in self._config:
                missing_keys.append(key)
        
        if missing_keys:
            raise ConfigError(f"缺少必需配置项: {', '.join(missing_keys)}")
        
        # 验证数据库配置
        if 'path' not in self._config.get('database', {}):
            raise ConfigError("缺少数据库路径配置: database.path")
        
        # 验证业务方向配置
        if not self._config.get('business_directions'):
            raise ConfigError("业务方向配置为空: business_directions")
        
        # 验证评分阈值
        thresholds = self._config.get('thresholds', {})
        for key, value in thresholds.items():
            if isinstance(value, (int, float)) and not (0 <= value <= 100):
                logger.warning(f"⚠️ 评分阈值超出范围 [0-100]: {key}={value}")
    
    def get(self, key_path: str, default: Any = None) -> Any:
        """获取配置值，支持点号路径访问
        
        Args:
            key_path: 配置路径，如 'spider.timeout' 或 'database.path'
            default: 默认值
            
        Returns:
            配置值，如果不存在则返回默认值
            
        Examples:
            >>> config.get('spider.timeout')
            >>> config.get('database.path')
            >>> config.get('analyzer.api_key', '')
        """
        if not self._loaded:
            self.load_all()
        
        keys = key_path.split('.')
        value = self._config
        
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
                if value is None:
                    return default
            else:
                return default
        
        return value
    
    def __getitem__(self, key: str) -> Any:
        """支持字典式访问（向后兼容）
        
        Args:
            key: 配置键
            
        Returns:
            配置值
        """
        if not self._loaded:
            self.load_all()
        
        return self._config[key]
    
    def __contains__(self, key: str) -> bool:
        """支持 in 操作符
        
        Args:
            key: 配置键
            
        Returns:
            是否包含该键
        """
        if not self._loaded:
            self.load_all()
        
        return key in self._config
    
    def to_dict(self) -> Dict[str, Any]:
        """获取完整配置字典
        
        Returns:
            配置字典
        """
        if not self._loaded:
            self.load_all()
        
        return self._config.copy()
    
    def reload(self):
        """重新加载配置"""
        self._config = {}
        self._loaded = False
        self.load_all()
