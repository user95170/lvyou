"""
高德地图数据加载脚本

完整的ETL流程：从高德地图API采集POI数据 → 写入数据库

使用前提：
1. 申请高德地图API Key：https://lbs.amap.com/
2. 配置环境变量：set AMAP_API_KEY=your_key

运行方式：
    python -m app.pipelines.load_amap_data --cities 呼和浩特,包头 --type scenic

参数说明：
    --cities: 城市列表，逗号分隔（必需）
    --type: POI类型 scenic/hotel/food/all（默认scenic）
    --max-pages: 每个城市最多采集页数（默认5）
    --dry-run: 仅采集不写入数据库
"""

import logging
import argparse
import os
from pathlib import Path
from datetime import datetime

from flask import Flask
from ..db import db
from ..models import ScenicSpot, Hotel, FoodPlace
from .collectors.amap_collector import AmapCollector
from ..config import Config

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_scenic_spots(data_list):
    """加载景点数据"""
    inserted = 0
    updated = 0
    skipped = 0
    
    for item in data_list:
        # 检查是否已存在
        existing = ScenicSpot.query.filter_by(
            name=item['name'],
            city=item['city']
        ).first()
        
        if existing:
            # 更新（如果坐标更准确）
            if not existing.longitude and item['longitude']:
                existing.longitude = item['longitude']
                existing.latitude = item['latitude']
                existing.address = item['address']
                existing.phone = item['phone']
                existing.tags = ','.join(item['tags']) if item['tags'] else existing.tags
                updated += 1
                logger.info(f"更新景点: {item['name']}")
            else:
                skipped += 1
        else:
            # 插入新景点
            new_spot = ScenicSpot(
                name=item['name'],
                city=item['city'],
                address=item['address'],
                longitude=item['longitude'],
                latitude=item['latitude'],
                category=item['poi_type_name'],  # 使用category而不是type
                description=item['address'],  # 暂用地址作为描述
                tags=','.join(item['tags']) if item['tags'] else None
            )
            db.session.add(new_spot)
            inserted += 1
            logger.info(f"插入景点: {item['name']}")
    
    return inserted, updated, skipped


def load_hotels(data_list):
    """加载酒店数据"""
    inserted = 0
    updated = 0
    skipped = 0
    
    for item in data_list:
        existing = Hotel.query.filter_by(
            name=item['name'],
            city=item['city']
        ).first()
        
        if existing:
            if not existing.longitude and item['longitude']:
                existing.longitude = item['longitude']
                existing.latitude = item['latitude']
                existing.address = item['address']
                existing.phone = item['phone']
                updated += 1
                logger.info(f"更新酒店: {item['name']}")
            else:
                skipped += 1
        else:
            new_hotel = Hotel(
                name=item['name'],
                city=item['city'],
                address=item['address'],
                longitude=item['longitude'],
                latitude=item['latitude'],
                tags=','.join(item['tags']) if item['tags'] else None,
                source='amap'
            )
            db.session.add(new_hotel)
            inserted += 1
            logger.info(f"插入酒店: {item['name']}")
    
    return inserted, updated, skipped


def load_food_places(data_list):
    """加载美食数据"""
    inserted = 0
    updated = 0
    skipped = 0
    
    for item in data_list:
        existing = FoodPlace.query.filter_by(
            name=item['name'],
            city=item['city']
        ).first()
        
        if existing:
            if not existing.longitude and item['longitude']:
                existing.longitude = item['longitude']
                existing.latitude = item['latitude']
                existing.address = item['address']
                existing.phone = item['phone']
                updated += 1
                logger.info(f"更新美食: {item['name']}")
            else:
                skipped += 1
        else:
            new_food = FoodPlace(
                name=item['name'],
                city=item['city'],
                address=item['address'],
                longitude=item['longitude'],
                latitude=item['latitude'],
                tags=','.join(item['tags']) if item['tags'] else None
            )
            db.session.add(new_food)
            inserted += 1
            logger.info(f"插入美食: {item['name']}")
    
    return inserted, updated, skipped


def main(args):
    """主函数"""
    # 检查API Key
    api_key = os.getenv('AMAP_API_KEY') or args.api_key
    if not api_key:
        logger.error("未找到高德地图API Key")
        logger.info("请设置环境变量：set AMAP_API_KEY=your_key")
        logger.info("或使用参数：--api-key your_key")
        return 1
    
    # 解析城市列表
    cities = [c.strip() for c in args.cities.split(',')]
    logger.info(f"将采集以下城市: {', '.join(cities)}")
    
    # 创建采集器
    collector = AmapCollector(api_key=api_key)
    
    # 根据类型采集
    all_stats = {
        'scenic': {'inserted': 0, 'updated': 0, 'skipped': 0},
        'hotel': {'inserted': 0, 'updated': 0, 'skipped': 0},
        'food': {'inserted': 0, 'updated': 0, 'skipped': 0}
    }
    
    types_to_collect = ['scenic', 'hotel', 'food'] if args.type == 'all' else [args.type]
    
    for poi_type in types_to_collect:
        logger.info("=" * 70)
        logger.info(f"开始采集 {poi_type.upper()} 数据")
        logger.info("=" * 70)
        
        # 采集数据
        data = collector.collect_by_cities(
            cities=cities,
            poi_type=poi_type,
            max_pages=args.max_pages
        )
        
        if not data:
            logger.warning(f"未采集到 {poi_type} 数据")
            continue
        
        logger.info(f"采集完成，共 {len(data)} 条 {poi_type} 数据")
        
        # 写入数据库
        if not args.dry_run:
            try:
                if poi_type == 'scenic':
                    inserted, updated, skipped = load_scenic_spots(data)
                elif poi_type == 'hotel':
                    inserted, updated, skipped = load_hotels(data)
                elif poi_type == 'food':
                    inserted, updated, skipped = load_food_places(data)
                
                db.session.commit()
                
                all_stats[poi_type]['inserted'] = inserted
                all_stats[poi_type]['updated'] = updated
                all_stats[poi_type]['skipped'] = skipped
                
                logger.info(
                    f"{poi_type.upper()} 数据写入完成: "
                    f"插入 {inserted}, 更新 {updated}, 跳过 {skipped}"
                )
                
            except Exception as e:
                db.session.rollback()
                logger.error(f"{poi_type} 数据写入失败: {e}")
                return 1
        else:
            logger.info("[DRY RUN] 跳过数据库写入")
    
    # 总结
    logger.info("=" * 70)
    logger.info("数据加载任务完成")
    logger.info("=" * 70)
    
    for poi_type in types_to_collect:
        stats = all_stats[poi_type]
        logger.info(
            f"{poi_type.upper()}: "
            f"插入 {stats['inserted']}, "
            f"更新 {stats['updated']}, "
            f"跳过 {stats['skipped']}"
        )
    
    # 采集统计
    collector_stats = collector.get_stats()
    logger.info(f"\nAPI调用统计:")
    logger.info(f"  总请求数: {collector_stats['total_requests']}")
    logger.info(f"  成功: {collector_stats['successful_requests']}")
    logger.info(f"  失败: {collector_stats['failed_requests']}")
    
    return 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='从高德地图API加载POI数据')
    parser.add_argument('--cities', type=str, required=True,
                        help='城市列表，逗号分隔，如：呼和浩特,包头')
    parser.add_argument('--type', type=str, default='scenic',
                        choices=['scenic', 'hotel', 'food', 'all'],
                        help='POI类型（默认scenic）')
    parser.add_argument('--max-pages', type=int, default=5,
                        help='每个城市最大分页数（默认5，每页20条）')
    parser.add_argument('--api-key', type=str, default='',
                        help='高德地图API Key（也可通过环境变量设置）')
    parser.add_argument('--dry-run', action='store_true',
                        help='仅采集不写入数据库')
    
    args = parser.parse_args()
    
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)
    
    with app.app_context():
        try:
            exit_code = main(args)
            exit(exit_code)
        except KeyboardInterrupt:
            logger.info("\n用户中断")
            exit(130)
        except Exception as e:
            logger.error(f"任务执行失败: {e}")
            import traceback
            traceback.print_exc()
            exit(1)
