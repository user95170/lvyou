"""
数据匹配器

将外部数据源的实体匹配到内部数据库ID
"""

import logging
from typing import Optional, List, Dict, Any
from difflib import SequenceMatcher

from ...db import db
from ...models import ScenicSpot, Hotel, FoodPlace

logger = logging.getLogger(__name__)


class DataMatcher:
    """实体匹配器：外部数据 → 内部ID"""
    
    def __init__(self, similarity_threshold: float = 0.8):
        """
        初始化匹配器
        
        Args:
            similarity_threshold: 相似度阈值 (0-1)，高于此值视为匹配
        """
        self.similarity_threshold = similarity_threshold
        self.stats = {
            'total_items': 0,
            'matched_items': 0,
            'unmatched_items': 0
        }
    
    def _calculate_similarity(self, str1: str, str2: str) -> float:
        """计算两个字符串的相似度"""
        return SequenceMatcher(None, str1.lower(), str2.lower()).ratio()
    
    def match_scenic_spot(self, external_data: Dict[str, Any]) -> Optional[int]:
        """
        匹配景点
        
        Args:
            external_data: 外部数据，需包含 name, city 字段
            
        Returns:
            int: 内部景点ID，未匹配返回None
        """
        name = external_data.get('entity_name', '').strip()
        city = external_data.get('city', '').strip()
        
        if not name:
            return None
        
        self.stats['total_items'] += 1
        
        # 尝试精确匹配
        spot = ScenicSpot.query.filter(
            ScenicSpot.name == name,
            ScenicSpot.city == city
        ).first()
        
        if spot:
            self.stats['matched_items'] += 1
            logger.debug(f"精确匹配景点: {name} -> ID:{spot.id}")
            return spot.id
        
        # 模糊匹配
        candidates = ScenicSpot.query.filter(
            ScenicSpot.city == city
        ).all()
        
        best_match = None
        best_similarity = 0
        
        for candidate in candidates:
            similarity = self._calculate_similarity(name, candidate.name)
            if similarity > best_similarity:
                best_similarity = similarity
                best_match = candidate
        
        if best_match and best_similarity >= self.similarity_threshold:
            self.stats['matched_items'] += 1
            logger.debug(
                f"模糊匹配景点: {name} -> {best_match.name} "
                f"(ID:{best_match.id}, 相似度:{best_similarity:.2f})"
            )
            return best_match.id
        
        # 未匹配
        self.stats['unmatched_items'] += 1
        logger.warning(f"未匹配到景点: {name} ({city})")
        return None
    
    def match_hotel(self, external_data: Dict[str, Any]) -> Optional[int]:
        """匹配酒店（类似景点匹配逻辑）"""
        name = external_data.get('entity_name', '').strip()
        city = external_data.get('city', '').strip()
        
        if not name:
            return None
        
        self.stats['total_items'] += 1
        
        # 精确匹配
        hotel = Hotel.query.filter(
            Hotel.name == name,
            Hotel.city == city
        ).first()
        
        if hotel:
            self.stats['matched_items'] += 1
            return hotel.id
        
        # 模糊匹配
        candidates = Hotel.query.filter(Hotel.city == city).all()
        
        best_match = None
        best_similarity = 0
        
        for candidate in candidates:
            similarity = self._calculate_similarity(name, candidate.name)
            if similarity > best_similarity:
                best_similarity = similarity
                best_match = candidate
        
        if best_match and best_similarity >= self.similarity_threshold:
            self.stats['matched_items'] += 1
            return best_match.id
        
        self.stats['unmatched_items'] += 1
        logger.warning(f"未匹配到酒店: {name} ({city})")
        return None
    
    def match_food_place(self, external_data: Dict[str, Any]) -> Optional[int]:
        """匹配美食（类似景点匹配逻辑）"""
        name = external_data.get('entity_name', '').strip()
        city = external_data.get('city', '').strip()
        
        if not name:
            return None
        
        self.stats['total_items'] += 1
        
        # 精确匹配
        food = FoodPlace.query.filter(
            FoodPlace.name == name,
            FoodPlace.city == city
        ).first()
        
        if food:
            self.stats['matched_items'] += 1
            return food.id
        
        # 模糊匹配
        candidates = FoodPlace.query.filter(FoodPlace.city == city).all()
        
        best_match = None
        best_similarity = 0
        
        for candidate in candidates:
            similarity = self._calculate_similarity(name, candidate.name)
            if similarity > best_similarity:
                best_similarity = similarity
                best_match = candidate
        
        if best_match and best_similarity >= self.similarity_threshold:
            self.stats['matched_items'] += 1
            return best_match.id
        
        self.stats['unmatched_items'] += 1
        logger.warning(f"未匹配到美食: {name} ({city})")
        return None
    
    def get_stats(self) -> Dict[str, int]:
        """获取匹配统计"""
        return self.stats.copy()
    
    def reset_stats(self):
        """重置统计"""
        self.stats = {
            'total_items': 0,
            'matched_items': 0,
            'unmatched_items': 0
        }
