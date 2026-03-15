---
description: 
auto_execution_mode: 3
---

# 数据管道与ETL脚本目录

> 本目录包含所有数据采集、清洗、聚合和分析脚本

---

## 📁 目录结构

```
pipelines/
├── README.md                      # 本文件
├── __init__.py                    # 模块初始化
│
├── collectors/                    # 数据采集器（已实现）
│   ├── __init__.py
│   ├── base_collector.py         # 采集器基类
│   ├── amap_collector.py         # 高德地图采集
│   └── ota_collector.py          # OTA平台数据采集（CSV/API）
│
├── processors/                    # 数据处理器（已实现）
│   ├── __init__.py
│   └── data_matcher.py           # 实体匹配（外部ID→内部ID）
│
├── aggregate_content.py           # 已有：内容聚合
├── aggregate_user_profile.py      # 已有：用户画像聚合
├── aggregate_scenic_cf.py         # 已有：CF相似度计算
├── evaluate_recommendation.py     # 已有：推荐评估
├── analyze_behavior.py            # 已有：行为分析
│
└── schedulers/                    # 调度器（规划）
    └── （未实现）
```

---

## 🔄 数据流向

```
外部数据源
    ↓
collectors（采集器）
    ↓
processors（清洗+匹配+聚合）
    ↓
SQLite / MySQL 数据库（标准化表，默认 SQLite）
    ↓
推荐/画像/规划模块消费
```

---

## 📊 已实现的管道

### 1. 内容聚合管道
- **脚本**：`aggregate_content.py`
- **功能**：基于内部评分计算景点/酒店/美食的热度分数
- **运行**：`python -m app.pipelines.aggregate_content`

### 2. 用户画像聚合
- **脚本**：`aggregate_user_profile.py`
- **功能**：根据评分行为聚合用户偏好
- **运行**：`python -m app.pipelines.aggregate_user_profile`

### 3. CF相似度计算
- **脚本**：`aggregate_scenic_cf.py`
- **功能**：计算景点间协同过滤相似度
- **运行**：`python -m app.pipelines.aggregate_scenic_cf`

### 4. 推荐算法评估
- **脚本**：`evaluate_recommendation.py`
- **功能**：离线评估推荐策略Precision@K
- **运行**：`python -m app.pipelines.evaluate_recommendation`

### 5. 行为数据分析
- **脚本**：`analyze_behavior.py`
- **功能**：统计用户行为，支持CSV导出
- **运行**：`python -m app.pipelines.analyze_behavior --days 7`

---

## 🚀 新增数据采集管道（规划）

### 1. OTA数据采集
- **数据源**：携程、美团、去哪儿等
- **采集内容**：
  - 景点：门票价格、销量、评分、评论数
  - 酒店：预订量、价格区间、评分
  - 美食：人均消费、评分、热门菜品
- **落地表**：`content_standard`（多源融合）
- **实现**：已提供 `collectors/ota_collector.py` 与 `load_ota_data.py`，可从 CSV 或 API 接入。

### 2. 社交媒体数据采集
- **数据源**：微博、小红书、抖音等
- **采集内容**：
  - 关键词搜索结果
  - 互动数据（点赞、评论、转发）
  - 情感倾向
- **落地表**：`content_standard` 或 `social_media_post`（新表）
- **实现**：当前使用 `social_media_fetcher.py` 读取示例 CSV 并写入 `content_standard`；采集器化改造为后续规划。

### 3. 地图与交通数据
- **数据源**：高德地图、百度地图
- **采集内容**：
  - POI详情（地址、电话、营业时间）
  - 路况信息
  - 周边设施
- **落地表**：`scenic_spot`（补充）+ `content_standard`
- **实现**：当前使用 `collectors/amap_collector.py` 做 POI 采集；地图/交通数据采集器化为后续规划。

---

## 🛠️ 数据处理流程

### 阶段1：采集（Extract）
```python
# collectors/base_collector.py
class BaseCollector:
    def fetch_data(self):
        """从外部源获取原始数据"""
        pass
    
    def parse_response(self, response):
        """解析API响应或HTML"""
        pass
```

### 阶段2：清洗（Transform）
```python
# processors/（示意）
- 去重
- 数据验证
- 格式标准化
- 异常值处理
```

### 阶段3：匹配（Match）
```python
# processors/data_matcher.py
- 外部实体名称 → 内部ID映射
- 模糊匹配（名称+城市+地址）
- 建立映射表
```

### 阶段4：加载（Load）
```python
# 写入标准化表
- content_standard
- scenic_spot（补充字段）
- social_media_post（可选新表）
```

---

## ⏰ 调度策略

### 每日任务（daily_tasks.py）
```python
# 建议调度时间
01:00 - OTA数据采集（低峰期）
02:00 - 社交媒体数据采集
03:00 - 数据清洗与匹配
04:00 - 内容聚合更新
05:00 - CF相似度重新计算
```

---

## 🔐 安全与合规

### API密钥管理
```bash
# .env 文件（不提交到仓库）
AMAP_API_KEY=your_key_here
MEITUAN_API_KEY=your_key_here
WEIBO_API_KEY=your_key_here
```

### 爬虫礼仪
- 遵守 robots.txt
- 设置合理的请求间隔
- 使用User-Agent
- 不频繁请求

### 数据使用
- 仅用于学术研究
- 不公开分享原始数据
- 尊重平台服务条款

---

## 📝 开发规范

### 新增采集器步骤
1. 继承 `BaseCollector`
2. 实现 `fetch_data()` 和 `parse_response()`
3. 在 `processors/` 中实现对应的清洗逻辑
4. 添加单元测试
5. 更新本 README

### 代码风格
- 遵循 PEP 8
- 添加详细的函数文档字符串
- 使用类型提示
- 完善的异常处理

---

## 📊 监控与日志

### 日志记录
```python
import logging

logger = logging.getLogger(__name__)
logger.info(f"采集完成：{count} 条数据")
logger.error(f"采集失败：{error}")
```

### 性能指标
- 采集成功率
- 数据质量分数
- 处理耗时
- 存储量统计

---

## 🔄 后续扩展方向

1. **实时采集**：从批处理改为流式处理
2. **分布式采集**：使用 Celery + Redis
3. **数据质量监控**：Great Expectations
4. **增量更新**：只采集变化的数据
5. **数据血缘**：追踪数据来源和转换

---

> **维护者**：数据工程团队  
> **最后更新**：2025-11-17  
> **文档版本**：v1.0
