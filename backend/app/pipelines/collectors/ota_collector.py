"""
OTA平台数据采集器

支持采集携程、美团、去哪儿等OTA平台的旅游数据
当前版本：基于CSV示例数据的采集器（可扩展为API采集）
"""

import csv
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

from .base_collector import BaseCollector

logger = logging.getLogger(__name__)


class OTACollector(BaseCollector):
    """OTA平台数据采集器"""
    
    def __init__(self, source: str = 'csv', csv_path: Optional[str] = None, **kwargs):
        """
        初始化OTA采集器
        
        Args:
            source: 数据源类型 ('csv' | 'api')
            csv_path: CSV文件路径（source='csv'时必需）
            **kwargs: 传递给BaseCollector的其他参数
        """
        super().__init__(**kwargs)
        self.source = source
        self.csv_path = csv_path
        
        if source == 'csv' and not csv_path:
            raise ValueError("使用CSV数据源时必须指定csv_path")
    
    def fetch_data(self, **kwargs) -> List[Dict[str, Any]]:
        """
        从数据源获取原始数据
        
        Returns:
            List[Dict]: 原始数据列表
        """
        if self.source == 'csv':
            return self._fetch_from_csv()
        elif self.source == 'api':
            return self._fetch_from_api(**kwargs)
        else:
            raise ValueError(f"不支持的数据源类型: {self.source}")
    
    def _fetch_from_csv(self) -> List[Dict[str, Any]]:
        """从CSV文件读取数据"""
        try:
            data = []
            with open(self.csv_path, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    data.append(row)
            logger.info(f"从CSV读取 {len(data)} 条记录: {self.csv_path}")
            return data
        except Exception as e:
            logger.error(f"读取CSV失败: {e}")
            raise
    
    def _fetch_from_api(self, **kwargs) -> List[Dict[str, Any]]:
        """
        从API获取数据（预留接口）
        
        实现建议：
        1. 根据具体OTA平台的API文档构造请求
        2. 使用 requests 库发送HTTP请求
        3. 解析JSON响应
        4. 应用速率限制（调用 self._rate_limit_check()）
        
        示例：
            response = requests.get(
                'https://api.example.com/scenic-spots',
                headers={'Authorization': f'Bearer {self.api_key}'},
                params=kwargs
            )
            return response.json()['data']
        """
        raise NotImplementedError("API采集功能待实现，请使用CSV模式或自行实现")
    
    def parse_item(self, raw_item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        解析单条OTA数据
        
        Args:
            raw_item: 原始数据项
            
        Returns:
            Dict: 标准化数据，包含以下字段：
                - entity_type: 实体类型 (scenic_spot | hotel | food)
                - entity_name: 实体名称
                - city: 城市
                - external_id: 外部平台ID
                - external_rating: 外部评分
                - external_review_count: 外部评论数
                - price_range: 价格区间
                - sales_volume: 销量等级
                - popularity_index: 热度指数
                - source_platform: 来源平台
                - raw_data: 原始数据（JSON字符串）
        """
        try:
            # 兼容两种CSV列命名：
            # 1) entity_type, entity_name, city, source_platform, external_rating, external_review_count, price_range, tags, description
            # 2) type, name, city, platform, rating, review_count, price_range, ...

            entity_type = (
                raw_item.get('entity_type')
                or raw_item.get('type')
                or 'scenic_spot'
            )
            entity_name = (
                raw_item.get('entity_name')
                or raw_item.get('name')
                or ''
            ).strip()
            city = (raw_item.get('city') or '').strip()

            external_id = raw_item.get('external_id', '')

            rating_raw = (
                raw_item.get('external_rating')
                or raw_item.get('rating')
            )
            review_count_raw = (
                raw_item.get('external_review_count')
                or raw_item.get('review_count')
            )

            try:
                external_rating = float(rating_raw) if rating_raw not in (None, '') else None
            except (TypeError, ValueError):
                external_rating = None

            try:
                external_review_count = int(review_count_raw) if review_count_raw not in (None, '') else 0
            except (TypeError, ValueError):
                external_review_count = 0

            price_range = raw_item.get('price_range', '')

            popularity_raw = raw_item.get('popularity', 0)
            try:
                popularity_index = float(popularity_raw) if popularity_raw not in (None, '') else 0.0
            except (TypeError, ValueError):
                popularity_index = 0.0

            source_platform = (
                raw_item.get('source_platform')
                or raw_item.get('platform')
                or 'unknown'
            )

            tags = raw_item.get('tags', '')

            parsed = {
                'entity_type': entity_type,
                'entity_name': entity_name,
                'city': city,
                'external_id': external_id,
                'external_rating': external_rating,
                'external_review_count': external_review_count,
                'price_range': price_range,
                'sales_volume': raw_item.get('sales_volume', ''),
                'popularity_index': popularity_index,
                'source_platform': source_platform,
                'tags': tags,
                'raw_data': str(raw_item)
            }

            # 数据验证
            if not parsed['entity_name']:
                logger.warning(f"实体名称为空，跳过: {raw_item}")
                return None

            return parsed

        except Exception as e:
            logger.warning(f"解析数据项失败: {e}, 原始数据: {raw_item}")
            return None


# 使用示例
if __name__ == '__main__':
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 示例：从CSV采集
    csv_file = Path(__file__).parent.parent.parent.parent / 'data' / 'ota_sample.csv'
    
    if csv_file.exists():
        collector = OTACollector(source='csv', csv_path=str(csv_file))
        data = collector.collect()
        
        print(f"\n采集到 {len(data)} 条数据")
        if data:
            print("\n示例数据（前3条）:")
            for item in data[:3]:
                print(f"- {item['entity_name']} ({item['city']}) - 评分:{item['external_rating']}")
    else:
        print(f"CSV文件不存在: {csv_file}")
        print("请创建示例CSV文件，包含以下列:")
        print("type,name,city,external_id,rating,review_count,price_range,sales_volume,popularity,platform")
