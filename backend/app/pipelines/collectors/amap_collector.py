"""
高德地图POI数据采集器

通过高德地图Web服务API获取景点、酒店、美食等POI数据

API文档：https://lbs.amap.com/api/webservice/guide/api/search
申请Key：https://lbs.amap.com/ (免费配额：每日30万次)

使用示例：
    collector = AmapCollector(api_key='your_key')
    pois = collector.collect(keywords='景点', city='呼和浩特')
"""

import logging
import requests
from typing import List, Dict, Any, Optional
from time import sleep

from .base_collector import BaseCollector

logger = logging.getLogger(__name__)


class AmapCollector(BaseCollector):
    """高德地图POI采集器"""
    
    # POI类型码（参考高德地图分类）
    POI_TYPES = {
        'scenic': '110000',      # 风景名胜
        'hotel': '100100',       # 住宿服务->宾馆酒店
        'food': '050000',        # 餐饮服务
        'shopping': '060000',    # 购物服务
        'entertainment': '080000'  # 体育休闲服务
    }
    
    def __init__(self, api_key: str, **kwargs):
        """
        初始化高德地图采集器
        
        Args:
            api_key: 高德地图API Key
            **kwargs: 传递给BaseCollector的其他参数
        """
        super().__init__(api_key=api_key, rate_limit=0.5, **kwargs)  # 500ms间隔，避免超限
        self.base_url = "https://restapi.amap.com/v3/place"
        self.session = self._create_session()
    
    def _create_session(self) -> requests.Session:
        """创建带重试机制的Session"""
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry
        
        session = requests.Session()
        retry = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[500, 502, 503, 504],
            allowed_methods=["GET", "POST"]
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount('http://', adapter)
        session.mount('https://', adapter)
        return session
    
    def fetch_data(self, keywords: str = '', city: str = '', 
                   poi_type: str = '', max_pages: int = 5, **kwargs) -> List[Dict[str, Any]]:
        """
        从高德地图API获取POI数据
        
        Args:
            keywords: 搜索关键词（如"景点"）
            city: 城市名称（如"呼和浩特"）
            poi_type: POI类型码（如"110000"）或类型名（如"scenic"）
            max_pages: 最大分页数（每页20条）
            
        Returns:
            List[Dict]: 原始POI数据列表
        """
        # 转换类型名为类型码
        if poi_type in self.POI_TYPES:
            poi_type = self.POI_TYPES[poi_type]
        
        all_pois = []
        page = 1
        
        while page <= max_pages:
            self._rate_limit_check()
            
            params = {
                'key': self.api_key,
                'offset': 20,  # 每页20条
                'page': page,
                'extensions': 'all'  # 返回详细信息
            }
            
            # 添加可选参数
            if keywords:
                params['keywords'] = keywords
            if city:
                params['city'] = city
            if poi_type:
                params['types'] = poi_type
            
            try:
                url = f"{self.base_url}/text"
                response = self.session.get(url, params=params, timeout=10)
                data = response.json()
                
                if data.get('status') != '1':
                    logger.error(f"API调用失败: {data.get('info')}, page={page}")
                    break
                
                pois = data.get('pois', [])
                if not pois:
                    logger.info(f"第{page}页无数据，停止翻页")
                    break
                
                all_pois.extend(pois)
                logger.info(f"获取第{page}页，{len(pois)}条数据")
                
                # 检查是否还有更多数据
                count = int(data.get('count', 0))
                if len(all_pois) >= count:
                    logger.info(f"已获取全部数据，共{count}条")
                    break
                
                page += 1
                
            except Exception as e:
                logger.error(f"获取第{page}页数据失败: {e}")
                break
        
        logger.info(f"采集完成，共获取 {len(all_pois)} 条POI数据")
        return all_pois
    
    def parse_item(self, raw_item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        解析单条POI数据
        
        Args:
            raw_item: 高德API返回的原始POI数据
            
        Returns:
            Dict: 标准化后的POI数据，包含以下字段：
                - name: 名称
                - city: 城市
                - address: 地址
                - longitude: 经度
                - latitude: 纬度
                - poi_type: POI类型码
                - poi_type_name: POI类型名称
                - phone: 电话
                - business_hours: 营业时间
                - tags: 标签
                - photos: 图片（可能为空）
                - rating: 评分（可能为None）
                - source: 数据来源
                - external_id: 外部ID
        """
        try:
            # 解析坐标
            location = raw_item.get('location', '')
            if location and ',' in location:
                lng, lat = location.split(',')
            else:
                logger.warning(f"POI缺少坐标信息: {raw_item.get('name')}")
                lng, lat = None, None
            
            # 解析类型
            typecode = raw_item.get('typecode', '')
            typename = raw_item.get('type', '')
            
            # 解析标签
            tag_str = raw_item.get('tag', '')
            if isinstance(tag_str, list):
                tag_str = ''
            tags = [t.strip() for t in tag_str.split(';') if t.strip()] if tag_str else []
            
            # 解析图片
            photos_data = raw_item.get('photos', [])
            photos = [p.get('url') for p in photos_data if p.get('url')]
            
            # 解析电话（可能是字符串或列表）
            tel = raw_item.get('tel', '')
            if isinstance(tel, list):
                tel = ';'.join(tel) if tel else ''
            
            # 解析地址（可能是字符串或列表）
            address = raw_item.get('address', '')
            if isinstance(address, list):
                address = ''
            
            parsed = {
                'name': raw_item.get('name', '').strip(),
                'city': raw_item.get('cityname', '').strip(),
                'address': address.strip() if address else '',
                'longitude': float(lng) if lng else None,
                'latitude': float(lat) if lat else None,
                'poi_type': typecode,
                'poi_type_name': typename,
                'phone': tel,
                'business_hours': raw_item.get('business_area', ''),
                'tags': tags,
                'photos': photos,
                'rating': None,  # 高德API基础版不返回评分
                'source': 'amap',
                'external_id': raw_item.get('id', ''),
                'raw_data': raw_item  # 保留原始数据备用
            }
            
            # 数据验证
            if not parsed['name']:
                logger.warning("POI名称为空，跳过")
                return None
            
            if not parsed['longitude'] or not parsed['latitude']:
                logger.warning(f"POI坐标缺失: {parsed['name']}")
                # 不跳过，允许保存无坐标数据
            
            return parsed
            
        except Exception as e:
            logger.warning(f"解析POI数据失败: {e}, 原始数据: {raw_item}")
            return None
    
    def collect_by_cities(self, cities: List[str], **kwargs) -> List[Dict[str, Any]]:
        """
        批量采集多个城市的POI数据
        
        Args:
            cities: 城市列表
            **kwargs: 传递给fetch_data的参数
            
        Returns:
            List[Dict]: 所有城市的POI数据
        """
        all_data = []
        
        for city in cities:
            logger.info(f"开始采集城市: {city}")
            data = self.collect(city=city, **kwargs)
            all_data.extend(data)
            logger.info(f"城市 {city} 采集完成，获取 {len(data)} 条数据")
        
        return all_data


# 使用示例和测试
if __name__ == '__main__':
    import os
    from pathlib import Path
    
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 从环境变量获取API Key
    api_key = os.getenv('AMAP_API_KEY')
    
    if not api_key:
        print("=" * 70)
        print("未配置高德地图API Key")
        print("=" * 70)
        print("\n请按以下步骤操作：")
        print("1. 访问 https://lbs.amap.com/ 注册账号")
        print("2. 进入控制台 → 应用管理 → 创建应用")
        print("3. 添加Key（选择'Web服务'类型）")
        print("4. 将Key配置到环境变量：")
        print("   Windows: set AMAP_API_KEY=your_key")
        print("   Linux/Mac: export AMAP_API_KEY=your_key")
        print("\n或者在代码中直接设置：")
        print("   api_key = 'your_amap_key_here'")
        print("=" * 70)
        exit(1)
    
    # 创建采集器
    collector = AmapCollector(api_key=api_key)
    
    # 示例1：采集呼和浩特的景点
    print("\n" + "=" * 70)
    print("示例1：采集呼和浩特的景点")
    print("=" * 70)
    
    scenic_data = collector.collect(
        keywords='景点',
        city='呼和浩特',
        max_pages=2  # 测试只采集2页
    )
    
    print(f"\n采集到 {len(scenic_data)} 个景点")
    if scenic_data:
        print("\n前3个景点：")
        for i, spot in enumerate(scenic_data[:3], 1):
            print(f"{i}. {spot['name']} - {spot['address']}")
            print(f"   坐标: ({spot['longitude']}, {spot['latitude']})")
            print(f"   标签: {', '.join(spot['tags'][:3])}")
    
    # 示例2：采集多个城市
    print("\n" + "=" * 70)
    print("示例2：批量采集多个城市（景点）")
    print("=" * 70)
    
    cities = ['呼和浩特', '包头']
    all_data = collector.collect_by_cities(
        cities=cities,
        poi_type='scenic',  # 使用类型码
        max_pages=1  # 每个城市1页
    )
    
    print(f"\n共采集 {len(all_data)} 条数据")
    
    # 统计信息
    stats = collector.get_stats()
    print(f"\n采集统计:")
    print(f"  总请求数: {stats['total_requests']}")
    print(f"  成功: {stats['successful_requests']}")
    print(f"  失败: {stats['failed_requests']}")
    print(f"  数据条数: {stats['total_items']}")
