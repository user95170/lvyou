"""
OTA数据加载脚本

完整的ETL流程：采集 → 匹配 → 写入content_standard表

运行方式：
    python -m app.pipelines.load_ota_data
"""

import logging
from pathlib import Path
from datetime import datetime, timezone

from flask import Flask
from ..db import db
from ..models import ContentStandard
from .collectors.ota_collector import OTACollector
from .processors.data_matcher import DataMatcher
from ..config import Config

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def load_ota_data_to_db(csv_path: str):
    """
    从OTA CSV数据加载到数据库
    
    Args:
        csv_path: CSV文件路径
    """
    # 1. 采集数据
    logger.info(f"开始采集OTA数据: {csv_path}")
    collector = OTACollector(source='csv', csv_path=csv_path)
    collected_data = collector.collect()
    
    if not collected_data:
        logger.warning("未采集到任何数据")
        return
    
    logger.info(f"采集完成，共 {len(collected_data)} 条数据")
    
    # 2. 匹配实体ID
    logger.info("开始匹配实体ID")
    matcher = DataMatcher(similarity_threshold=0.8)
    
    matched_records = []
    for item in collected_data:
        raw_entity_type = item['entity_type']
        entity_type = raw_entity_type
        if raw_entity_type == 'food':
            entity_type = 'food_place'
        
        # 根据类型匹配
        if raw_entity_type == 'scenic_spot':
            entity_id = matcher.match_scenic_spot(item)
        elif raw_entity_type == 'hotel':
            entity_id = matcher.match_hotel(item)
        elif raw_entity_type in ('food', 'food_place'):
            entity_id = matcher.match_food_place(item)
        else:
            logger.warning(f"未知实体类型: {raw_entity_type}")
            continue
        
        if entity_id:
            matched_records.append({
                'entity_type': entity_type,
                'entity_id': entity_id,
                'data': item
            })
    
    # 打印匹配统计
    stats = matcher.get_stats()
    logger.info(
        f"匹配完成: 成功 {stats['matched_items']}/{stats['total_items']}, "
        f"失败 {stats['unmatched_items']}"
    )
    
    if not matched_records:
        logger.warning("没有匹配到任何实体，无法写入数据库")
        return
    
    # 3. 写入数据库
    logger.info(f"开始写入数据库，共 {len(matched_records)} 条记录")
    
    inserted_count = 0
    updated_count = 0
    
    for record in matched_records:
        entity_type = record['entity_type']
        entity_id = record['entity_id']
        data = record['data']
        
        # 检查是否已存在
        existing = ContentStandard.query.filter_by(
            entity_type=entity_type,
            entity_id=entity_id,
            source_type='ota_stats'
        ).first()
        if existing is None and entity_type == 'food_place':
            existing = ContentStandard.query.filter_by(
                entity_type='food',
                entity_id=entity_id,
                source_type='ota_stats'
            ).first()
            if existing is not None:
                existing.entity_type = 'food_place'

        if existing is None:
            existing = ContentStandard.query.filter_by(
                entity_type=entity_type,
                entity_id=entity_id,
                source_type='ota'
            ).first()
            if existing is None and entity_type == 'food_place':
                existing = ContentStandard.query.filter_by(
                    entity_type='food',
                    entity_id=entity_id,
                    source_type='ota'
                ).first()
                if existing is not None:
                    existing.entity_type = 'food_place'
            if existing is not None:
                existing.source_type = 'ota_stats'
        
        # 计算人气分数 (基于评分和评论数)
        try:
            rating = float(data.get('external_rating') or data.get('rating') or 0.0)
        except (TypeError, ValueError):
            rating = 0.0
        try:
            review_count = int(
                data.get('review_count') or data.get('external_review_count') or 0
            )
        except (TypeError, ValueError):
            review_count = 0
        popularity = (rating / 5.0) * 60 + min(review_count / 100, 40)  # 最高100分
        
        # 构造summary JSON字符串
        import json
        summary_data = {
            'platform': data.get('source_platform'),
            'external_rating': rating,
            'rating': rating,
            'review_count': review_count,
            'external_review_count': review_count,
            'price_range': data.get('price_range'),
            'tags': data.get('tags', '').split(';') if data.get('tags') else []
        }
        
        if existing:
            # 更新
            existing.title = data.get('entity_name')
            existing.popularity_score = popularity
            existing.summary = json.dumps(summary_data, ensure_ascii=False)
            existing.last_update = _utcnow()
            updated_count += 1
        else:
            # 插入
            new_record = ContentStandard(
                entity_type=entity_type,
                entity_id=entity_id,
                source_type='ota_stats',
                title=data.get('entity_name'),
                popularity_score=popularity,
                summary=json.dumps(summary_data, ensure_ascii=False)
            )
            db.session.add(new_record)
            inserted_count += 1
    
    try:
        db.session.commit()
        logger.info(f"数据库写入完成: 插入 {inserted_count} 条，更新 {updated_count} 条")
    except Exception as e:
        db.session.rollback()
        logger.error(f"数据库写入失败: {e}")
        raise


if __name__ == '__main__':
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)
    
    with app.app_context():
        # CSV文件路径
        csv_file = Path(__file__).parent.parent.parent / 'data' / 'ota_sample.csv'
        
        if not csv_file.exists():
            logger.error(f"CSV文件不存在: {csv_file}")
            logger.info("请创建示例CSV文件，或修改脚本中的文件路径")
            exit(1)
        
        try:
            logger.info("=" * 70)
            logger.info("OTA数据加载任务开始")
            logger.info("=" * 70)
            
            load_ota_data_to_db(str(csv_file))
            
            logger.info("=" * 70)
            logger.info("OTA数据加载任务完成")
            logger.info("=" * 70)
        
        except Exception as e:
            logger.error(f"任务执行失败: {e}")
            import traceback
            traceback.print_exc()
            exit(1)
