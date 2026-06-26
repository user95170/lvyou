from __future__ import annotations

import json
import time
from math import atan2, cos, radians, sin, sqrt
from typing import Iterable, List, Optional
from urllib.parse import urlencode
from urllib.request import urlopen

from flask import Blueprint, jsonify, request, current_app

from ..models import ScenicSpot

route_bp = Blueprint("route", __name__, url_prefix="/api/route")


def _haversine_km(lng1: float, lat1: float, lng2: float, lat2: float) -> float:
  """使用 haversine 公式估算两点之间的球面距离（千米）。"""

  r = 6371.0  # 地球半径，km
  lon1, lat1_r = radians(lng1), radians(lat1)
  lon2, lat2_r = radians(lng2), radians(lat2)

  dlon = lon2 - lon1
  dlat = lat2_r - lat1_r

  a = sin(dlat / 2) ** 2 + cos(lat1_r) * cos(lat2_r) * sin(dlon / 2) ** 2
  c = 2 * atan2(sqrt(a), sqrt(1 - a))
  return r * c


def _spots_have_coords(spots: Iterable[ScenicSpot]) -> bool:
  for s in spots:
    if s.longitude is None or s.latitude is None:
      return False
  return True


def _compute_distance_matrix(spots: List[ScenicSpot]) -> List[List[float]]:
  """计算所有景点两两之间的距离矩阵"""
  n = len(spots)
  dist_matrix = [[0.0] * n for _ in range(n)]
  
  for i in range(n):
    for j in range(i + 1, n):
      spot_i, spot_j = spots[i], spots[j]
      if (spot_i.longitude is None or spot_i.latitude is None or
          spot_j.longitude is None or spot_j.latitude is None):
        dist = float('inf')
      else:
        dist = _haversine_km(
          float(spot_i.longitude), float(spot_i.latitude),
          float(spot_j.longitude), float(spot_j.latitude)
        )
      dist_matrix[i][j] = dist
      dist_matrix[j][i] = dist
  
  return dist_matrix


def _compute_route_greedy(spots: List[ScenicSpot]) -> tuple[List[ScenicSpot], float]:
  """使用最近邻启发式算法，对给定景点做一个简单的近似最短路线规划。

  返回：规划后的景点顺序列表和基于直线距离累加的总里程（km）。
  """

  if not spots:
    return [], 0.0

  remaining = spots[1:]
  ordered = [spots[0]]
  total_km = 0.0

  while remaining:
    current = ordered[-1]
    if current.longitude is None or current.latitude is None:
      # 当前点无坐标则直接追加剩余点
      ordered.extend(remaining)
      break

    lng1 = float(current.longitude)
    lat1 = float(current.latitude)

    best_idx = 0
    best_dist = None

    for idx, candidate in enumerate(remaining):
      if candidate.longitude is None or candidate.latitude is None:
        continue
      d = _haversine_km(lng1, lat1, float(candidate.longitude), float(candidate.latitude))
      if best_dist is None or d < best_dist:
        best_dist = d
        best_idx = idx

    next_spot = remaining.pop(best_idx)
    if best_dist is not None:
      total_km += best_dist
    ordered.append(next_spot)

  return ordered, total_km


def _optimize_route_2opt(spots: List[ScenicSpot], dist_matrix: List[List[float]], 
                        max_iterations: int = 100) -> tuple[List[ScenicSpot], float]:
  """使用2-opt算法优化路径
  
  Args:
    spots: 初始景点顺序
    dist_matrix: 距离矩阵
    max_iterations: 最大迭代次数
  
  Returns:
    优化后的景点顺序和总距离
  """
  if len(spots) < 4:  # 2-opt需要至少4个点才有意义
    route_indices = list(range(len(spots)))
    return spots, _calculate_total_distance(route_indices, dist_matrix)
  
  n = len(spots)
  route_indices = list(range(n))
  improved = True
  iteration = 0
  
  while improved and iteration < max_iterations:
    improved = False
    iteration += 1
    
    for i in range(1, n - 2):
      for j in range(i + 1, n - 1):
        if j - i == 1:
          continue  # 相邻边不交换
        
        # 计算当前边的距离
        current_dist = (
          dist_matrix[route_indices[i - 1]][route_indices[i]] +
          dist_matrix[route_indices[j]][route_indices[j + 1]]
        )
        
        # 计算交换后的距离
        new_dist = (
          dist_matrix[route_indices[i - 1]][route_indices[j]] +
          dist_matrix[route_indices[i]][route_indices[j + 1]]
        )
        
        # 如果交换能改进，则进行2-opt交换
        if new_dist < current_dist:
          # 反转i到j之间的路径
          route_indices[i:j+1] = reversed(route_indices[i:j+1])
          improved = True
  
  # 根据优化后的索引重建景点列表
  optimized_spots = [spots[i] for i in route_indices]
  total_dist = _calculate_total_distance(route_indices, dist_matrix)
  
  return optimized_spots, total_dist


def _calculate_total_distance(route_indices: List[int], dist_matrix: List[List[float]]) -> float:
  """计算给定路径的总距离"""
  if not route_indices or len(route_indices) < 2:
    return 0.0
  
  total = 0.0
  for i in range(len(route_indices) - 1):
    a = route_indices[i]
    b = route_indices[i + 1]
    total += dist_matrix[a][b]
  
  return total


def _compute_route_with_score(spots: List[ScenicSpot], dist_matrix: List[List[float]],
                              distance_weight: float = 0.7,
                              popularity_weight: float = 0.3) -> tuple[List[ScenicSpot], float]:
  """综合距离和景点热度的多目标优化路径规划
  
  Args:
    spots: 景点列表
    dist_matrix: 距离矩阵
    distance_weight: 距离权重 (0-1)
    popularity_weight: 热度权重 (0-1)
  
  Returns:
    优化后的景点顺序和总距离
  """
  if not spots:
    return [], 0.0
  
  # 先用贪心获得初始解
  remaining = spots[1:]
  ordered = [spots[0]]
  total_km = 0.0
  
  # 归一化景点热度分数（统一转 float，避免 Decimal/float 混算）
  def _rating_of(s) -> float:
    try:
      return float(s.rating_avg) if s.rating_avg is not None else 0.0
    except (TypeError, ValueError):
      return 0.0

  max_rating = max(_rating_of(s) for s in spots)
  min_rating = min(_rating_of(s) for s in spots)
  rating_range = max_rating - min_rating if max_rating > min_rating else 1.0
  
  while remaining:
    current_idx = spots.index(ordered[-1])
    best_idx = 0
    best_score = float('inf')
    
    for idx, candidate in enumerate(remaining):
      cand_idx = spots.index(candidate)
      distance = dist_matrix[current_idx][cand_idx]
      
      # 归一化景点评分 (越高越好，所以取反)
      rating_score = 1.0 - (_rating_of(candidate) - min_rating) / rating_range
      
      # 综合得分 (距离越短越好，评分越高越好)
      combined_score = distance_weight * distance + popularity_weight * rating_score * 100
      
      if combined_score < best_score:
        best_score = combined_score
        best_idx = idx
    
    next_spot = remaining.pop(best_idx)
    next_idx = spots.index(next_spot)
    total_km += dist_matrix[current_idx][next_idx]
    ordered.append(next_spot)
  
  return ordered, total_km


def _enhance_distance_with_amap(spots: List[ScenicSpot]) -> Optional[float]:
  """如配置了高德 Web 服务 key，则调用驾车路径规划 API 获取更精确的路程。

  仅返回总里程（km），若调用失败则返回 None。
  """

  key = current_app.config.get("AMAP_WEB_KEY")
  if not key:
    return None

  if len(spots) < 2 or not _spots_have_coords(spots):
    return None

  origin = f"{float(spots[0].longitude)},{float(spots[0].latitude)}"
  destination = f"{float(spots[-1].longitude)},{float(spots[-1].latitude)}"

  waypoints_parts: List[str] = []
  for s in spots[1:-1]:
    waypoints_parts.append(f"{float(s.longitude)},{float(s.latitude)}")
  waypoints_v3 = "|".join(waypoints_parts) if waypoints_parts else None
  waypoints_v5 = ";".join(waypoints_parts) if waypoints_parts else None

  api_ver = (current_app.config.get("AMAP_API_VERSION") or "v3").lower()
  if api_ver == "v5":
    params = {
      "origin": origin,
      "destination": destination,
      "key": key,
      "strategy": "32",
    }
    # v5 支持 waypoints，多个点以分号 ';' 分隔，最多 16 个
    if waypoints_v5:
      params["waypoints"] = waypoints_v5
    url = "https://restapi.amap.com/v5/direction/driving?" + urlencode(params)
  else:
    params = {
      "origin": origin,
      "destination": destination,
      "key": key,
    }
    if waypoints_v3:
      params["waypoints"] = waypoints_v3
    url = "https://restapi.amap.com/v3/direction/driving?" + urlencode(params)

  data = _http_get_json(url, timeout=6)
  if not data or data.get("status") != "1":
    try:
      current_app.logger.warning(f"amap_enhance_distance_fail ver={api_ver} info={data.get('info') if isinstance(data, dict) else 'noresp'}")
    except Exception:
      pass
    return None

  route = data.get("route") or {}
  paths = route.get("paths") or []
  if not paths:
    return None

  try:
    distance_m = float(paths[0].get("distance", 0))
  except (TypeError, ValueError):
    return None

  if distance_m <= 0:
    return None

  return distance_m / 1000.0


def _amap_route_options_drive(lng1: float, lat1: float, lng2: float, lat2: float, key: str, strategy: Optional[str] = None) -> List[dict]:
  params = {
    "origin": f"{lng1},{lat1}",
    "destination": f"{lng2},{lat2}",
    "key": key,
    "strategy": str(strategy) if strategy else "10",
  }
  url = "https://restapi.amap.com/v3/direction/driving?" + urlencode(params)
  data = _http_get_json(url, timeout=6)
  if not data or data.get("status") != "1":
    try:
      current_app.logger.warning(f"amap_v3_drive_fail info={data.get('info') if isinstance(data, dict) else 'noresp'}")
      if isinstance(data, dict) and data.get('infocode'):
        _metric_inc("amap_fail_infocode", str(data.get('infocode')))
    except Exception:
      pass
    _metric_inc("amap_route_fail", "v3_drive")
    return []
  paths = (data.get("route") or {}).get("paths") or []
  options: List[dict] = []
  for idx, p in enumerate(paths[:3]):
    try:
      distance_km = round(float(p.get("distance", 0)) / 1000.0, 2)
    except Exception:
      distance_km = None
    try:
      duration_min = max(1, int(round(float(p.get("duration", 0)) / 60.0)))
    except Exception:
      duration_min = None
    options.append({
      "label": "最快" if idx == 0 else f"方案{idx+1}",
      "duration_min": duration_min,
      "distance_km": distance_km,
      "legs": [{"mode": "drive"}],
    })
  _metric_inc("amap_route_success", "v3_drive")
  return options

# 轻量内存缓存用于 AMap GET JSON
_AMAP_CACHE_TTL = 60.0
_AMAP_CACHE_MAX = 128
_AMAP_CACHE: dict[str, tuple[dict, float]] = {}

# 简易 QPS 节流（每进程）与指标
_AMAP_QPS_LIMIT = 8  # 每秒最多外呼次数（每进程）
_AMAP_QPS_STATE: dict[str, tuple[int, int]] = {}
_METRICS: dict[str, object] = {}
_METRICS_START_TS: float = time.time()

def _metric_inc(name: str, key: Optional[str] = None, n: int = 1) -> None:
  try:
    if key is None:
      _METRICS[name] = int(_METRICS.get(name, 0)) + int(n)
    else:
      bucket = _METRICS.get(name)
      if not isinstance(bucket, dict):
        bucket = {}
        _METRICS[name] = bucket
      bucket[key] = int(bucket.get(key, 0)) + int(n)
  except Exception:
    pass

def _http_get_json(url: str, timeout: float = 6.0, use_cache: bool = True) -> Optional[dict]:
  now = time.time()
  if use_cache and url in _AMAP_CACHE:
    data, ts = _AMAP_CACHE[url]
    ttl_cfg = None
    try:
      ttl_cfg = float(current_app.config.get("AMAP_CACHE_TTL", _AMAP_CACHE_TTL))
    except Exception:
      ttl_cfg = _AMAP_CACHE_TTL
    if now - ts < float(ttl_cfg):
      _metric_inc("amap_cache_hit")
      return data
    else:
      _AMAP_CACHE.pop(url, None)
  else:
    _metric_inc("amap_cache_miss")

  # 简易 QPS 限流（仅针对 restapi.amap.com）
  if "restapi.amap.com" in url:
    sec_now = int(now)
    sec, cnt = _AMAP_QPS_STATE.get("amap", (sec_now, 0))
    try:
      qps_limit = int(current_app.config.get("AMAP_QPS_LIMIT", _AMAP_QPS_LIMIT))
    except Exception:
      qps_limit = _AMAP_QPS_LIMIT
    if sec_now == sec:
      if cnt >= qps_limit:
        try:
          current_app.logger.warning("amap_rate_limited_skip")
        except Exception:
          pass
        _metric_inc("amap_rate_limited_skips")
        return None
      else:
        _AMAP_QPS_STATE["amap"] = (sec, cnt + 1)
    else:
      _AMAP_QPS_STATE["amap"] = (sec_now, 1)
  try:
    with urlopen(url, timeout=timeout) as resp:
      data = json.load(resp)
  except Exception as e:
    try:
      current_app.logger.warning(f"amap_http_fail url={url} err={e}")
    except Exception:
      pass
    return None
  if use_cache:
    if len(_AMAP_CACHE) >= _AMAP_CACHE_MAX:
      try:
        _AMAP_CACHE.pop(next(iter(_AMAP_CACHE)))
      except Exception:
        _AMAP_CACHE.clear()
    _AMAP_CACHE[url] = (data, now)
  return data

def _amap_route_options_walk(lng1: float, lat1: float, lng2: float, lat2: float, key: str) -> List[dict]:
  params = {
    "origin": f"{lng1},{lat1}",
    "destination": f"{lng2},{lat2}",
    "key": key,
  }
  url = "https://restapi.amap.com/v3/direction/walking?" + urlencode(params)
  data = _http_get_json(url, timeout=6)
  if not data or data.get("status") != "1":
    try:
      current_app.logger.warning(f"amap_v3_walk_fail info={data.get('info') if isinstance(data, dict) else 'noresp'}")
      if isinstance(data, dict) and data.get('infocode'):
        _metric_inc("amap_fail_infocode", str(data.get('infocode')))
    except Exception:
      pass
    _metric_inc("amap_route_fail", "v3_walk")
    return []
  paths = (data.get("route") or {}).get("paths") or []
  options: List[dict] = []
  for idx, p in enumerate(paths[:3]):
    try:
      distance_km = round(float(p.get("distance", 0)) / 1000.0, 2)
    except Exception:
      distance_km = None
    try:
      duration_min = max(1, int(round(float(p.get("duration", 0)) / 60.0)))
    except Exception:
      duration_min = None
    options.append({
      "label": "步行优先" if idx == 0 else f"步行方案{idx+1}",
      "duration_min": duration_min,
      "distance_km": distance_km,
      "legs": [{"mode": "walk"}],
    })
  _metric_inc("amap_route_success", "v3_walk")
  return options

def _amap_route_options_transit(lng1: float, lat1: float, lng2: float, lat2: float, key: str, city: Optional[str], cityd: Optional[str] = None, strategy: Optional[str] = None) -> List[dict]:
  if not city:
    return []
  params = {
    "origin": f"{lng1},{lat1}",
    "destination": f"{lng2},{lat2}",
    "city": city,
    "key": key,
  }
  if cityd and cityd != city:
    params["cityd"] = cityd
  if strategy is not None:
    params["strategy"] = str(strategy)
  url = "https://restapi.amap.com/v3/direction/transit/integrated?" + urlencode(params)
  data = _http_get_json(url, timeout=6)
  if not data or data.get("status") != "1":
    try:
      current_app.logger.warning(f"amap_v3_transit_fail info={data.get('info') if isinstance(data, dict) else 'noresp'}")
      if isinstance(data, dict) and data.get('infocode'):
        _metric_inc("amap_fail_infocode", str(data.get('infocode')))
    except Exception:
      pass
    _metric_inc("amap_route_fail", "v3_transit")
    return []
  transits = (data.get("route") or {}).get("transits") or []
  options: List[dict] = []
  for idx, t in enumerate(transits[:3]):
    try:
      duration_min = max(1, int(round(float(t.get("duration", 0)) / 60.0)))
    except Exception:
      duration_min = None
    options.append({
      "label": "少换乘" if idx == 0 else f"公交方案{idx+1}",
      "duration_min": duration_min,
      "distance_km": None,
      "legs": [{"mode": "transit"}],
    })
  _metric_inc("amap_route_success", "v3_transit")
  return options

def _amap_guess_citycode(lng: float, lat: float, key: str) -> Optional[str]:
  """通过逆地理编码推断 citycode（优先使用 origin 坐标）。失败返回 None。"""
  params = {
    "location": f"{lng},{lat}",
    "key": key,
  }
  url = "https://restapi.amap.com/v3/geocode/regeo?" + urlencode(params)
  data = _http_get_json(url, timeout=5)
  if data is None:
    return None
  if data.get("status") != "1":
    return None
  ac = ((data.get("regeocode") or {}).get("addressComponent") or {})
  citycode = ac.get("citycode")
  if isinstance(citycode, str) and citycode.strip():
    return citycode.strip()
  return None

def _amap_distance_estimate(lng1: float, lat1: float, lng2: float, lat2: float, key: str, dist_type: int) -> Optional[tuple[float, int]]:
  """调用 AMap 距离测量接口，返回 (distance_km, duration_min)。失败返回 None。

  dist_type: 0=直线(不建议)，1=驾车，3=步行
  """
  params = {
    "origins": f"{lng1},{lat1}",
    "destination": f"{lng2},{lat2}",
    "type": str(int(dist_type)),
    "key": key,
  }
  url = "https://restapi.amap.com/v3/distance?" + urlencode(params)
  data = _http_get_json(url, timeout=6)
  if data is None:
    return None
  if data.get("status") != "1":
    return None
  results = data.get("results") or []
  if not results:
    return None
  r0 = results[0] or {}
  try:
    dist_m = float(r0.get("distance", 0))
  except Exception:
    dist_m = 0.0
  try:
    dur_s = float(r0.get("duration", 0))
  except Exception:
    dur_s = 0.0
  if dist_m <= 0:
    return None
  distance_km = dist_m / 1000.0
  duration_min = max(1, int(round(dur_s / 60.0))) if dur_s > 0 else None
  if duration_min is None:
    return None
  return distance_km, duration_min

def _amap_v5_route_options_drive(lng1: float, lat1: float, lng2: float, lat2: float, key: str, strategy: Optional[str] = None, waypoints: Optional[str] = None) -> List[dict]:
  params = {
    "origin": f"{lng1},{lat1}",
    "destination": f"{lng2},{lat2}",
    "key": key,
    "strategy": str(strategy) if strategy else "32",
  }
  if waypoints:
    params["waypoints"] = waypoints
  url = "https://restapi.amap.com/v5/direction/driving?" + urlencode(params)
  data = _http_get_json(url, timeout=6)
  if not data or data.get("status") != "1":
    try:
      current_app.logger.warning(f"amap_v5_drive_fail info={data.get('info') if isinstance(data, dict) else 'noresp'}")
      if isinstance(data, dict) and data.get('infocode'):
        _metric_inc("amap_fail_infocode", str(data.get('infocode')))
    except Exception:
      pass
    _metric_inc("amap_route_fail", "v5_drive")
    return []
  paths = (data.get("route") or {}).get("paths") or []
  options: List[dict] = []
  for idx, p in enumerate(paths[:3]):
    try:
      distance_km = round(float(p.get("distance", 0)) / 1000.0, 2)
    except Exception:
      distance_km = None
    try:
      duration_min = max(1, int(round(float(p.get("duration", 0)) / 60.0)))
    except Exception:
      duration_min = None
    options.append({
      "label": "最快" if idx == 0 else f"方案{idx+1}",
      "duration_min": duration_min,
      "distance_km": distance_km,
      "legs": [{"mode": "drive"}],
    })
  return options

def _amap_v5_route_options_walk(lng1: float, lat1: float, lng2: float, lat2: float, key: str) -> List[dict]:
  params = {
    "origin": f"{lng1},{lat1}",
    "destination": f"{lng2},{lat2}",
    "key": key,
  }
  url = "https://restapi.amap.com/v5/direction/walking?" + urlencode(params)
  data = _http_get_json(url, timeout=6)
  if not data or data.get("status") != "1":
    try:
      current_app.logger.warning(f"amap_v5_walk_fail info={data.get('info') if isinstance(data, dict) else 'noresp'}")
      if isinstance(data, dict) and data.get('infocode'):
        _metric_inc("amap_fail_infocode", str(data.get('infocode')))
    except Exception:
      pass
    _metric_inc("amap_route_fail", "v5_walk")
    return []
  paths = (data.get("route") or {}).get("paths") or []
  options: List[dict] = []
  for idx, p in enumerate(paths[:3]):
    try:
      distance_km = round(float(p.get("distance", 0)) / 1000.0, 2)
    except Exception:
      distance_km = None
    try:
      duration_min = max(1, int(round(float(p.get("duration", 0)) / 60.0)))
    except Exception:
      duration_min = None
    options.append({
      "label": "步行优先" if idx == 0 else f"步行方案{idx+1}",
      "duration_min": duration_min,
      "distance_km": distance_km,
      "legs": [{"mode": "walk"}],
    })
  return options

def _amap_v5_route_options_transit(
  lng1: float,
  lat1: float,
  lng2: float,
  lat2: float,
  key: str,
  city1: Optional[str],
  city2: Optional[str],
  strategy: Optional[str] = None,
  ad1: Optional[str] = None,
  ad2: Optional[str] = None,
  alternative_route: Optional[int] = None,
  multiexport: Optional[int] = None,
  nightflag: Optional[int] = None,
) -> List[dict]:
  if not city1 or not city2:
    return []
  params = {
    "origin": f"{lng1},{lat1}",
    "destination": f"{lng2},{lat2}",
    "city1": city1,
    "city2": city2,
    "key": key,
  }
  if strategy is not None:
    params["strategy"] = str(strategy)
  if ad1:
    params["ad1"] = str(ad1)
  if ad2:
    params["ad2"] = str(ad2)
  # 注意：官方文档参数名为 "AlternativeRoute"（大小写保留）
  if isinstance(alternative_route, int):
    params["AlternativeRoute"] = str(alternative_route)
  if isinstance(multiexport, int):
    params["multiexport"] = str(multiexport)
  if isinstance(nightflag, int):
    params["nightflag"] = str(nightflag)
  url = "https://restapi.amap.com/v5/direction/transit/integrated?" + urlencode(params)
  data = _http_get_json(url, timeout=6)
  if not data or data.get("status") != "1":
    try:
      current_app.logger.warning(f"amap_v5_transit_fail info={data.get('info') if isinstance(data, dict) else 'noresp'}")
      if isinstance(data, dict) and data.get('infocode'):
        _metric_inc("amap_fail_infocode", str(data.get('infocode')))
    except Exception:
      pass
    _metric_inc("amap_route_fail", "v5_transit")
    return []
  transits = (data.get("route") or {}).get("transits") or []
  options: List[dict] = []
  for idx, t in enumerate(transits[:3]):
    try:
      duration_min = max(1, int(round(float(t.get("duration", 0)) / 60.0)))
    except Exception:
      duration_min = None
    options.append({
      "label": "少换乘" if idx == 0 else f"公交方案{idx+1}",
      "duration_min": duration_min,
      "distance_km": None,
      "legs": [{"mode": "transit"}],
    })
  return options

class _RouteOrigin:
  """用户当前位置作为路线起点的虚拟节点（不写入数据库）。"""

  def __init__(self, lng: float, lat: float, name: str = "我的位置"):
    self.id = None
    self.name = name
    self.longitude = lng
    self.latitude = lat
    self.rating_avg = None
    self.rating_count = 0

  def to_dict(self) -> dict:
    return {
      "id": None,
      "name": self.name,
      "longitude": float(self.longitude),
      "latitude": float(self.latitude),
      "is_origin": True,
      "type": "origin",
    }


def _parse_start_location(data: dict):
  """解析可选的用户起点位置 start_location: {lng, lat}。无效或缺失返回 None。"""
  loc = data.get("start_location")
  if not isinstance(loc, dict):
    return None
  lng = loc.get("lng", loc.get("longitude"))
  lat = loc.get("lat", loc.get("latitude"))
  try:
    lng = float(lng)
    lat = float(lat)
  except (TypeError, ValueError):
    return None
  if not (-180.0 <= lng <= 180.0 and -90.0 <= lat <= 90.0):
    return None
  return _RouteOrigin(lng, lat)


def _build_plan_inputs(data: dict):
  """解析并构建规划输入（景点顺序、缺失ID、起点）。

  返回 (inputs, None) 或 (None, (response, code))。
  inputs 含 ordered_input / missing_ids / origin / spot_ids。
  """
  raw_ids = data.get("spot_ids") or []
  if not isinstance(raw_ids, list) or len(raw_ids) < 2:
    return None, (jsonify({"error": "spot_ids must be a list with at least two ids"}), 400)

  try:
    spot_ids = [int(x) for x in raw_ids]
  except (TypeError, ValueError):
    return None, (jsonify({"error": "spot_ids must contain integers"}), 400)

  start_raw = data.get("start_spot_id")
  start_id = None
  if start_raw is not None:
    try:
      start_id = int(start_raw)
    except (TypeError, ValueError):
      return None, (jsonify({"error": "start_spot_id must be an integer"}), 400)

  # 可选：以用户当前位置作为起点（基于定位的路线规划）
  origin = _parse_start_location(data)
  if data.get("start_location") is not None and origin is None:
    return None, (jsonify({"error": "start_location must contain valid lng/lat"}), 400)

  spots = ScenicSpot.query.filter(ScenicSpot.id.in_(spot_ids)).all()
  if len(spots) < 2:
    return None, (jsonify({"error": "at least two scenic spots must exist"}), 400)

  id_to_spot = {s.id: s for s in spots}
  missing_ids = [sid for sid in spot_ids if sid not in id_to_spot]

  if start_id is None or start_id not in id_to_spot:
    start_id = spot_ids[0]

  # 以 start_id 对列表重新排序，保持用户原始顺序的同时指定起点
  ordered_input: List[ScenicSpot] = []
  if start_id in id_to_spot:
    ordered_input.append(id_to_spot[start_id])
  for sid in spot_ids:
    if sid == start_id:
      continue
    spot = id_to_spot.get(sid)
    if spot is not None:
      ordered_input.append(spot)

  # 若提供用户位置，则将其作为固定起点（贪心/2opt 均保持索引 0 不变）
  if origin is not None:
    ordered_input = [origin] + ordered_input

  return (
    {
      "ordered_input": ordered_input,
      "missing_ids": missing_ids,
      "origin": origin,
      "spot_ids": spot_ids,
    },
    None,
  )


def _route_total_km(route) -> float:
  """沿给定顺序累加相邻点的直线距离（缺坐标的相邻段跳过）。"""
  total = 0.0
  for i in range(len(route) - 1):
    a, b = route[i], route[i + 1]
    if (a.longitude is None or a.latitude is None or
        b.longitude is None or b.latitude is None):
      continue
    total += _haversine_km(
      float(a.longitude), float(a.latitude),
      float(b.longitude), float(b.latitude),
    )
  return total


def _order_by_popularity(ordered_input):
  """保持起点不变，其余按人气（评分数、评分）降序排列。

  采用 rating_count 作为人气主信号（批量数据中该字段有区分度），
  使该方案与"最短路线"形成数据驱动的差异。
  """
  if not ordered_input:
    return [], 0.0
  head = [ordered_input[0]]
  rest = ordered_input[1:]

  def _pop_key(s):
    try:
      rc = int(getattr(s, "rating_count", 0) or 0)
    except (TypeError, ValueError):
      rc = 0
    try:
      ra = float(s.rating_avg) if getattr(s, "rating_avg", None) is not None else 0.0
    except (TypeError, ValueError):
      ra = 0.0
    return (-rc, -ra)

  route = head + sorted(rest, key=_pop_key)
  return route, _route_total_km(route)


def _plan_with_mode(ordered_input, optimize_mode, distance_weight=0.7, popularity_weight=0.3):
  """按指定优化模式生成单一路线，返回 (route, total_km, algorithm, amap_used)。"""
  dist_matrix = _compute_distance_matrix(ordered_input)

  if optimize_mode == "2opt":
    greedy_route, _ = _compute_route_greedy(ordered_input)
    dist_matrix_2opt = _compute_distance_matrix(greedy_route)
    final_route, approx_km = _optimize_route_2opt(greedy_route, dist_matrix_2opt)
    algorithm_name = "greedy_with_2opt_optimization"
  elif optimize_mode == "balanced":
    final_route, approx_km = _compute_route_with_score(
      ordered_input, dist_matrix, distance_weight, popularity_weight
    )
    algorithm_name = f"balanced_optimization_d{distance_weight}_p{popularity_weight}"
  elif optimize_mode == "popularity":
    final_route, approx_km = _order_by_popularity(ordered_input)
    algorithm_name = "popularity_first"
  else:
    final_route, approx_km = _compute_route_greedy(ordered_input)
    algorithm_name = "greedy_nearest_neighbor_haversine"

  amap_km = _enhance_distance_with_amap(final_route)
  use_amap = amap_km is not None
  total_km = amap_km if use_amap else approx_km
  return final_route, total_km, algorithm_name, use_amap


# 多方案命名规划（基于定位 + 所选景点，离线可用）
_PLAN_OPTION_SPECS = [
  {"label": "最短路线", "optimize": "2opt"},
  {"label": "人气优先", "optimize": "popularity"},
  {"label": "兼顾热度", "optimize": "balanced", "distance_weight": 0.6, "popularity_weight": 0.4},
]


@route_bp.post("/plan")
def plan_route():
  """为给定的一组景点做路线规划（增强版）。

  请求 JSON 示例：
  {
    "spot_ids": [3, 6, 5],
    "start_spot_id": 3,        # 可选，默认为 spot_ids[0]
    "start_location": {"lng": .., "lat": ..},  # 可选，以用户定位为起点
    "optimize": "2opt",        # 可选，优化算法: "greedy" | "2opt" | "balanced"
    "distance_weight": 0.7,   # 可选，距离权重 (仅balanced模式)
    "popularity_weight": 0.3  # 可选，热度权重 (仅balanced模式)
  }

  返回：按游览顺序排列的景点列表和估算总路程（km）。
  如配置 AMAP_WEB_KEY 且调用成功，则总路程来自高德驾车路径规划；
  否则使用基于经纬度直线距离的近似值。
  """

  data = request.get_json(silent=True) or {}
  inputs, err = _build_plan_inputs(data)
  if err is not None:
    resp, code = err
    return resp, code

  ordered_input = inputs["ordered_input"]
  optimize_mode = (data.get("optimize") or "greedy").lower()
  try:
    distance_weight = float(data.get("distance_weight", 0.7))
    popularity_weight = float(data.get("popularity_weight", 0.3))
  except (TypeError, ValueError):
    return jsonify({"error": "distance_weight and popularity_weight must be numbers"}), 400

  final_route, total_km, algorithm_name, use_amap = _plan_with_mode(
    ordered_input, optimize_mode, distance_weight, popularity_weight
  )

  return jsonify(
    {
      "route": [s.to_dict() for s in final_route],
      "meta": {
        "total_distance_km": round(total_km, 2) if total_km is not None else None,
        "spot_ids_input": inputs["spot_ids"],
        "missing_ids": inputs["missing_ids"],
        "algorithm": algorithm_name,
        "optimize_mode": optimize_mode,
        "amap_used": use_amap,
        "start_location_used": inputs["origin"] is not None,
      },
    }
  )


@route_bp.post("/plan-options")
def plan_options():
  """基于（可选）用户定位与所选景点，返回多种命名规划方案供对比。

  请求体同 /plan（spot_ids、可选 start_location/start_spot_id）。
  返回 options：每项含 label/optimize/route/total_distance_km/stop_count。
  完全离线可用（无高德 Key 时按经纬度直线距离估算）。
  """

  data = request.get_json(silent=True) or {}
  inputs, err = _build_plan_inputs(data)
  if err is not None:
    resp, code = err
    return resp, code

  ordered_input = inputs["ordered_input"]
  options = []
  seen_orders = set()
  amap_used_any = False

  for spec in _PLAN_OPTION_SPECS:
    final_route, total_km, _algo, use_amap = _plan_with_mode(
      ordered_input,
      spec["optimize"],
      spec.get("distance_weight", 0.7),
      spec.get("popularity_weight", 0.3),
    )
    amap_used_any = amap_used_any or use_amap

    # 顺序相同的方案去重（小规模景点下 greedy 与 2opt 可能一致）
    order_key = tuple(s.id if getattr(s, "id", None) is not None else "origin" for s in final_route)
    if order_key in seen_orders:
      continue
    seen_orders.add(order_key)

    route_items = [s.to_dict() for s in final_route]
    options.append(
      {
        "label": spec["label"],
        "optimize": spec["optimize"],
        "route": route_items,
        "total_distance_km": round(total_km, 2) if total_km is not None else None,
        "stop_count": sum(1 for it in route_items if not it.get("is_origin")),
      }
    )

  return jsonify(
    {
      "options": options,
      "meta": {
        "spot_ids_input": inputs["spot_ids"],
        "missing_ids": inputs["missing_ids"],
        "start_location_used": inputs["origin"] is not None,
        "amap_used": amap_used_any,
      },
    }
  )


@route_bp.post("/options")
def route_options():
  """根据起终点与偏好返回若干方案（示例实现）。

  请求 JSON 示例：
  {
    "origin": {"lng": 111.67, "lat": 40.82},
    "destination": {"lng": 111.72, "lat": 40.80},
    "prefer": "fastest",
    "mode": "transit"  # 可选：drive/transit/walk
  }
  """

  data = request.get_json(silent=True) or {}
  origin = data.get("origin") or {}
  dest = data.get("destination") or {}

  try:
    lng1 = float(origin.get("lng"))
    lat1 = float(origin.get("lat"))
    lng2 = float(dest.get("lng"))
    lat2 = float(dest.get("lat"))
  except Exception:
    return jsonify({"error": "origin/destination with lng/lat required"}), 400

  distance_km = _haversine_km(lng1, lat1, lng2, lat2)
  if distance_km < 0:
    distance_km = 0.0

  mode = (data.get("mode") or "drive").lower()
  key = current_app.config.get("AMAP_WEB_KEY")
  city = data.get("city") or data.get("citycode")

  options: List[dict] = []
  # 预处理 waypoints（仅对 v5 驾车使用）：接受对象数组/二元数组/"lng,lat" 字符串数组
  def _parse_waypoints(req_val) -> Optional[List[str]]:
    if req_val is None:
      return None
    pts: List[str] = []
    try:
      for it in list(req_val):
        if isinstance(it, dict):
          lng = float(it.get("lng"))
          lat = float(it.get("lat"))
          pts.append(f"{lng},{lat}")
        elif isinstance(it, (list, tuple)) and len(it) >= 2:
          lng = float(it[0])
          lat = float(it[1])
          pts.append(f"{lng},{lat}")
        elif isinstance(it, str) and "," in it:
          parts = it.split(",")
          lng = float(parts[0])
          lat = float(parts[1])
          pts.append(f"{lng},{lat}")
        else:
          return None
    except Exception:
      return None
    return pts

  req_waypoints = data.get("waypoints")
  wp_list = _parse_waypoints(req_waypoints)
  if wp_list is not None and len(wp_list) > 16:
    _metric_inc("route_invalid_input", "waypoints_exceed")
    return jsonify({"error": "waypoints exceed 16"}), 400

  if key:
    m = "drive" if mode in {"drive", "driving", "car"} else ("walk" if mode in {"walk", "walking"} else ("transit" if mode in {"transit", "bus"} else "drive"))
    # per-request overrides
    api_ver = (str(data.get("api_version") or current_app.config.get("AMAP_API_VERSION") or "v3")).lower()
    req_strategy = data.get("strategy")
    # specialized overrides
    drive_strategy = data.get("drive_strategy") or req_strategy
    transit_strategy = data.get("transit_strategy") or req_strategy
    # transit city overrides for v5
    city1_req = data.get("city1")
    city2_req = data.get("city2")
    # v5 transit 高级参数（透传）
    ad1_req = data.get("ad1")
    ad2_req = data.get("ad2")
    alt_req = data.get("alternative_route")
    multiexport_req = data.get("multiexport")
    nightflag_req = data.get("nightflag")
    if api_ver == "v5":
      _metric_inc("amap_version_used", "v5")
      if m == "drive":
        waypoints_v5 = ";".join(wp_list) if wp_list else None
        options = _amap_v5_route_options_drive(
          lng1, lat1, lng2, lat2, key,
          strategy=str(drive_strategy) if drive_strategy else None,
          waypoints=waypoints_v5,
        )
      elif m == "walk":
        options = _amap_v5_route_options_walk(lng1, lat1, lng2, lat2, key)
      elif m == "transit":
        c1 = (str(city1_req) if city1_req else None) or (_amap_guess_citycode(lng1, lat1, key) if not city else str(city))
        c2 = (str(city2_req) if city2_req else None) or (_amap_guess_citycode(lng2, lat2, key) if not city else str(city))
        if not city and (c1 or c2):
          _metric_inc("infer_citycode_used")
        # 规范与校验：AlternativeRoute 1..10；multiexport/nightflag 0/1
        try:
          alt_i = int(alt_req) if alt_req is not None else None
        except Exception:
          alt_i = None
        if isinstance(alt_i, int) and (alt_i < 1 or alt_i > 10):
          alt_i = None
        try:
          mult_i = int(multiexport_req) if multiexport_req is not None else None
        except Exception:
          mult_i = None
        if isinstance(mult_i, int) and mult_i not in (0, 1):
          mult_i = None
        try:
          night_i = int(nightflag_req) if nightflag_req is not None else None
        except Exception:
          night_i = None
        if isinstance(night_i, int) and night_i not in (0, 1):
          night_i = None
        options = _amap_v5_route_options_transit(
          lng1, lat1, lng2, lat2, key, c1, c2,
          strategy=str(transit_strategy) if transit_strategy else None,
          ad1=str(ad1_req) if ad1_req else None,
          ad2=str(ad2_req) if ad2_req else None,
          alternative_route=alt_i,
          multiexport=mult_i,
          nightflag=night_i,
        )
      # 若 v5 未返回结果，回退到 v3
      if not options:
        if m == "drive":
          options = _amap_route_options_drive(lng1, lat1, lng2, lat2, key, strategy=str(drive_strategy) if drive_strategy else None)
        elif m == "walk":
          options = _amap_route_options_walk(lng1, lat1, lng2, lat2, key)
        elif m == "transit":
          c1_fb = city or _amap_guess_citycode(lng1, lat1, key)
          c2_fb = _amap_guess_citycode(lng2, lat2, key)
          options = _amap_route_options_transit(lng1, lat1, lng2, lat2, key, c1_fb, c2_fb if c2_fb and c2_fb != c1_fb else None, strategy=str(transit_strategy) if transit_strategy else None)
    else:
      # v3 路径
      _metric_inc("amap_version_used", "v3")
      if m == "drive":
        options = _amap_route_options_drive(lng1, lat1, lng2, lat2, key, strategy=str(drive_strategy) if drive_strategy else None)
      elif m == "walk":
        options = _amap_route_options_walk(lng1, lat1, lng2, lat2, key)
      elif m == "transit":
        c1_fb = city or _amap_guess_citycode(lng1, lat1, key)
        c2_fb = _amap_guess_citycode(lng2, lat2, key)
        if not city and (c1_fb or c2_fb):
          _metric_inc("infer_citycode_used")
        options = _amap_route_options_transit(lng1, lat1, lng2, lat2, key, c1_fb, c2_fb if c2_fb and c2_fb != c1_fb else None, strategy=str(transit_strategy) if transit_strategy else None)

  if options:
    for o in options:
      if o.get("distance_km") is None:
        o["distance_km"] = round(distance_km, 2)
    _metric_inc("route_options_source", "amap")
    _metric_inc("route_options_success")
    return jsonify({"options": options})

  # 回退链：若配置了 key，先尝试 AMap 距离接口（驾车/步行），再回退到直线估算
  if key:
    m = "drive" if mode in {"drive", "driving", "car"} else ("walk" if mode in {"walk", "walking"} else ("transit" if mode in {"transit", "bus"} else "drive"))
    if m in {"drive", "walk"}:
      dist_type = 1 if m == "drive" else 3
      est = _amap_distance_estimate(lng1, lat1, lng2, lat2, key, dist_type)
      if est is not None:
        est_km, est_min = est
        # 基于距离接口构造与原占位一致的多方案返回
        speed_drive = 40.0
        speed_transit = 20.0
        speed_walk = 4.5
        base_speed = speed_drive if mode == "drive" else (speed_transit if mode == "transit" else speed_walk)
        dur_min_fast = max(1, est_min)
        fallback_options = []
        fallback_options.append({
          "label": "最快",
          "duration_min": dur_min_fast,
          "distance_km": round(est_km, 2),
          "legs": [{"mode": mode if mode in {"drive", "transit", "walk"} else "drive"}]
        })
        dur_min_less_transfer = max(dur_min_fast + 5, int(round(60.0 * est_km / max(speed_transit, 1e-6))) + 3)
        fallback_options.append({
          "label": "少换乘",
          "duration_min": dur_min_less_transfer,
          "distance_km": round(est_km, 2),
          "legs": [{"mode": "transit"}]
        })
        dur_min_walk = max(dur_min_fast, int(round(60.0 * est_km / max(speed_walk, 1e-6))))
        fallback_options.append({
          "label": "步行优先",
          "duration_min": dur_min_walk,
          "distance_km": round(est_km, 2),
          "legs": [{"mode": "walk"}]
        })
        _metric_inc("fallback_amap_distance")
        _metric_inc("route_options_source", "amap_distance")
        _metric_inc("route_options_success")
        return jsonify({"options": fallback_options})
  # 回退到直线估算占位
  speed_drive = 40.0
  speed_transit = 20.0
  speed_walk = 4.5

  base_speed = speed_drive if mode == "drive" else (speed_transit if mode == "transit" else speed_walk)
  dur_min_fast = max(1, int(round(60.0 * distance_km / max(base_speed, 1e-6))))
  fallback_options = []
  fallback_options.append({
    "label": "最快",
    "duration_min": dur_min_fast,
    "distance_km": round(distance_km, 2),
    "legs": [{"mode": mode if mode in {"drive", "transit", "walk"} else "drive"}]
  })
  dur_min_less_transfer = max(dur_min_fast + 5, int(round(60.0 * distance_km / max(speed_transit, 1e-6))) + 3)
  fallback_options.append({
    "label": "少换乘",
    "duration_min": dur_min_less_transfer,
    "distance_km": round(distance_km, 2),
    "legs": [{"mode": "transit"}]
  })
  dur_min_walk = max(dur_min_fast, int(round(60.0 * distance_km / max(speed_walk, 1e-6))))
  fallback_options.append({
    "label": "步行优先",
    "duration_min": dur_min_walk,
    "distance_km": round(distance_km, 2),
    "legs": [{"mode": "walk"}]
  })
  _metric_inc("fallback_haversine")
  _metric_inc("route_options_source", "haversine")
  _metric_inc("route_options_success")
  return jsonify({"options": fallback_options})

@route_bp.get("/metrics")
def route_metrics():
  """返回与路线选项相关的轻量运行指标（只读）。"""
  return jsonify(_build_route_metrics_payload())


def _build_route_metrics_payload() -> dict:
  try:
    uptime_sec = int(max(0, time.time() - _METRICS_START_TS))
  except Exception:
    uptime_sec = None
  # 计算汇总
  try:
    def _bucket(name: str) -> dict:
      b = _METRICS.get(name, {})
      return b if isinstance(b, dict) else {}

    amap_succ_b = _bucket("amap_route_success")
    amap_fail_b = _bucket("amap_route_fail")
    amap_fail_infocode_b = _bucket("amap_fail_infocode")
    amap_succ_total = sum(int(v) for v in amap_succ_b.values())
    amap_fail_total = sum(int(v) for v in amap_fail_b.values())
    amap_total = amap_succ_total + amap_fail_total
    amap_success_rate = (amap_succ_total / amap_total) if amap_total > 0 else None

    source_b = _bucket("route_options_source")
    total_options = sum(int(v) for v in source_b.values())

    def _topn_items(d: dict, n: int = 5) -> list:
      try:
        items = [(str(k), int(v)) for k, v in d.items()]
      except Exception:
        items = []
      items.sort(key=lambda kv: kv[1], reverse=True)
      return items[:n]

    summary = {
      "amap_success_total": amap_succ_total,
      "amap_fail_total": amap_fail_total,
      "amap_success_rate": round(amap_success_rate, 4) if isinstance(amap_success_rate, float) else None,
      "route_options_total": total_options,
      "source_breakdown": source_b,
      "fallback_amap_distance": int(_METRICS.get("fallback_amap_distance", 0) or 0),
      "fallback_haversine": int(_METRICS.get("fallback_haversine", 0) or 0),
      "amap_cache_hit": int(_METRICS.get("amap_cache_hit", 0) or 0),
      "amap_cache_miss": int(_METRICS.get("amap_cache_miss", 0) or 0),
      "amap_rate_limited_skips": int(_METRICS.get("amap_rate_limited_skips", 0) or 0),
      "infer_citycode_used": int(_METRICS.get("infer_citycode_used", 0) or 0),
      "top_fail_infocode": _topn_items(amap_fail_infocode_b, 5),
      "top_fail_modes": _topn_items(amap_fail_b, 5),
    }
  except Exception:
    summary = None

  payload = {
    "uptime_sec": uptime_sec,
    "metrics": _METRICS,
    "summary": summary,
  }
  return payload
