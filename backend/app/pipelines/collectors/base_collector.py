"""
数据采集器基类

所有具体的采集器都应继承此基类
"""

import time
import logging
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class BaseCollector(ABC):
    """数据采集器基类"""
    
    def __init__(self, api_key: Optional[str] = None, rate_limit: float = 1.0):
        """
        初始化采集器
        
        Args:
            api_key: API密钥（如需要）
            rate_limit: 请求间隔（秒），默认1秒
        """
        self.api_key = api_key
        self.rate_limit = rate_limit
        self.last_request_time = 0
        self.stats = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'total_items': 0,
            'start_time': None,
            'end_time': None
        }
    
    def _rate_limit_check(self):
        """检查并执行速率限制"""
        if self.last_request_time > 0:
            elapsed = time.time() - self.last_request_time
            if elapsed < self.rate_limit:
                time.sleep(self.rate_limit - elapsed)
        self.last_request_time = time.time()
    
    @abstractmethod
    def fetch_data(self, **kwargs) -> List[Dict[str, Any]]:
        """
        从数据源获取数据（子类必须实现）
        
        Returns:
            List[Dict]: 原始数据列表
        """
        pass
    
    @abstractmethod
    def parse_item(self, raw_item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        解析单条原始数据（子类必须实现）
        
        Args:
            raw_item: 原始数据项
            
        Returns:
            Dict: 标准化后的数据项，解析失败返回None
        """
        pass
    
    def collect(self, **kwargs) -> List[Dict[str, Any]]:
        """
        执行完整的采集流程
        
        Returns:
            List[Dict]: 标准化后的数据列表
        """
        self.stats['start_time'] = datetime.now()
        logger.info(f"{self.__class__.__name__} 开始采集数据")
        
        try:
            # 获取原始数据
            raw_data = self.fetch_data(**kwargs)
            self.stats['total_requests'] += 1
            self.stats['successful_requests'] += 1
            
            # 解析数据
            parsed_data = []
            for raw_item in raw_data:
                try:
                    parsed_item = self.parse_item(raw_item)
                    if parsed_item:
                        parsed_data.append(parsed_item)
                        self.stats['total_items'] += 1
                except Exception as e:
                    logger.warning(f"解析数据项失败: {e}")
                    continue
            
            self.stats['end_time'] = datetime.now()
            self._log_stats()
            
            return parsed_data
            
        except Exception as e:
            self.stats['failed_requests'] += 1
            self.stats['end_time'] = datetime.now()
            logger.error(f"采集失败: {e}")
            return []
    
    def _log_stats(self):
        """记录采集统计信息"""
        duration = (self.stats['end_time'] - self.stats['start_time']).total_seconds()
        logger.info(
            f"{self.__class__.__name__} 采集完成: "
            f"成功 {self.stats['successful_requests']}/{self.stats['total_requests']} 请求, "
            f"获取 {self.stats['total_items']} 条数据, "
            f"耗时 {duration:.2f} 秒"
        )
    
    def get_stats(self) -> Dict[str, Any]:
        """获取采集统计信息"""
        return self.stats.copy()
