"""
用户行为分析脚本（增强版）

功能：
1. 统计推荐后点击率最高的景点
2. 分析不同推荐策略下的用户交互情况
3. 输出简要的行为统计报告
4. 支持时间段分布分析
5. 支持导出 CSV 报告

运行方式：
    python -m app.pipelines.analyze_behavior [--days 7] [--export csv]
    
参数说明：
    --days N        分析最近 N 天的数据（默认 7）
    --export FORMAT 导出报告格式，支持 csv（可选）
    --top N         Top N 排行榜数量（默认 10）
"""

import argparse
import csv
import sys
from collections import defaultdict, Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    from tabulate import tabulate
    HAS_TABULATE = True
except ImportError:
    HAS_TABULATE = False

from ..db import db
from ..models import UserBehaviorLog, ScenicSpot


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def analyze_scenic_click_rate(days=7, top_n=10):
    """分析最近 N 天内景点推荐的点击情况"""
    
    try:
        since = _utcnow() - timedelta(days=days)
        
        # 查询景点点击行为
        behaviors = (
            UserBehaviorLog.query
            .filter(
                UserBehaviorLog.target_type == 'scenic_spot',
                UserBehaviorLog.behavior_type == 'click',
                UserBehaviorLog.occurred_at >= since
            )
            .all()
        )
        
        if not behaviors:
            print(f"\n⚠️  最近 {days} 天内无景点点击行为记录")
            print("提示：请先在前端首页点击推荐景点以产生行为数据")
            return None
        
        # 统计每个景点的点击次数和独立用户数
        click_counts = Counter()
        user_clicks = defaultdict(set)
        daily_clicks = defaultdict(int)
        
        for log in behaviors:
            click_counts[log.target_id] += 1
            if log.user_id:
                user_clicks[log.target_id].add(log.user_id)
            # 统计每日点击量
            day_key = log.occurred_at.date()
            daily_clicks[day_key] += 1
        
        # 获取景点信息
        spot_ids = list(click_counts.keys())
        spots = ScenicSpot.query.filter(ScenicSpot.id.in_(spot_ids)).all()
        spot_map = {s.id: s for s in spots}
        
        print(f"\n{'='*70}")
        print(f"📊 景点推荐点击统计（最近 {days} 天）")
        print(f"{'='*70}")
        print(f"总点击次数：{len(behaviors)}")
        print(f"涉及景点数：{len(click_counts)}")
        print(f"独立用户数：{len(set(log.user_id for log in behaviors if log.user_id))}")
        
        # 表格化输出 Top N
        print(f"\n🏆 点击次数 Top {top_n}：")
        
        if HAS_TABULATE:
            table_data = []
            for spot_id, count in click_counts.most_common(top_n):
                spot = spot_map.get(spot_id)
                if spot:
                    unique_users = len(user_clicks[spot_id])
                    ctr = f"{(unique_users / count * 100):.1f}%" if count > 0 else "N/A"
                    table_data.append([
                        spot.name[:20],
                        spot.city or 'N/A',
                        count,
                        unique_users,
                        ctr
                    ])
                else:
                    table_data.append([
                        f"景点ID {spot_id} (已删除)",
                        "N/A",
                        count,
                        len(user_clicks[spot_id]),
                        "N/A"
                    ])
            
            headers = ["景点名称", "城市", "点击次数", "独立用户", "用户转化率"]
            print(tabulate(table_data, headers=headers, tablefmt="grid"))
        else:
            for spot_id, count in click_counts.most_common(top_n):
                spot = spot_map.get(spot_id)
                if spot:
                    unique_users = len(user_clicks[spot_id])
                    print(f"  • {spot.name} ({spot.city})")
                    print(f"    点击次数：{count}，独立用户：{unique_users}")
                else:
                    print(f"  • 景点ID {spot_id}（已删除）：{count} 次")
        
        # 每日点击趋势
        if daily_clicks:
            print(f"\n📈 每日点击趋势：")
            sorted_days = sorted(daily_clicks.items())
            for day, count in sorted_days[-7:]:  # 最近7天
                print(f"  {day}: {count} 次")
        
        return {
            'total_clicks': len(behaviors),
            'unique_spots': len(click_counts),
            'unique_users': len(set(log.user_id for log in behaviors if log.user_id)),
            'top_spots': [(spot_map.get(sid, {'name': f'ID{sid}', 'city': 'N/A'}), cnt) 
                          for sid, cnt in click_counts.most_common(top_n)],
            'daily_clicks': dict(daily_clicks)
        }
    
    except Exception as e:
        print(f"\n❌ 分析景点点击数据时出错: {e}")
        import traceback
        traceback.print_exc()
        return None


def analyze_behavior_by_user(days=7, top_n=5):
    """按用户分析行为活跃度"""
    
    try:
        since = _utcnow() - timedelta(days=days)
        
        behaviors = (
            UserBehaviorLog.query
            .filter(UserBehaviorLog.occurred_at >= since)
            .all()
        )
        
        if not behaviors:
            print(f"\n⚠️  最近 {days} 天内无用户行为记录")
            return None
        
        user_behavior_counts = Counter()
        behavior_type_counts = Counter()
        target_type_counts = Counter()
        
        for log in behaviors:
            if log.user_id:
                user_behavior_counts[log.user_id] += 1
            behavior_type_counts[log.behavior_type] += 1
            target_type_counts[log.target_type] += 1
        
        print(f"\n{'='*70}")
        print(f"👥 用户行为活跃度统计（最近 {days} 天）")
        print(f"{'='*70}")
        print(f"总行为记录数：{len(behaviors)}")
        print(f"活跃用户数：{len(user_behavior_counts)}")
        print(f"平均每用户行为数：{len(behaviors) / max(len(user_behavior_counts), 1):.1f}")
        
        # 行为类型分布
        print(f"\n📋 行为类型分布：")
        if HAS_TABULATE:
            type_data = [[btype, count, f"{count/len(behaviors)*100:.1f}%"] 
                         for btype, count in behavior_type_counts.most_common()]
            print(tabulate(type_data, headers=["行为类型", "次数", "占比"], tablefmt="grid"))
        else:
            for behavior_type, count in behavior_type_counts.most_common():
                pct = count / len(behaviors) * 100
                print(f"  • {behavior_type}: {count} 次 ({pct:.1f}%)")
        
        # 目标类型分布
        print(f"\n🎯 目标实体类型分布：")
        for target_type, count in target_type_counts.most_common():
            pct = count / len(behaviors) * 100
            print(f"  • {target_type}: {count} 次 ({pct:.1f}%)")
        
        # 最活跃用户
        if user_behavior_counts:
            print(f"\n🌟 最活跃用户 Top {top_n}：")
            if HAS_TABULATE:
                user_data = [[f"用户 {uid}", count] 
                            for uid, count in user_behavior_counts.most_common(top_n)]
                print(tabulate(user_data, headers=["用户", "行为次数"], tablefmt="grid"))
            else:
                for user_id, count in user_behavior_counts.most_common(top_n):
                    print(f"  • 用户ID {user_id}: {count} 次行为")
        
        return {
            'total_behaviors': len(behaviors),
            'active_users': len(user_behavior_counts),
            'behavior_types': dict(behavior_type_counts),
            'target_types': dict(target_type_counts),
            'avg_behaviors_per_user': len(behaviors) / max(len(user_behavior_counts), 1)
        }
    
    except Exception as e:
        print(f"\n❌ 分析用户行为数据时出错: {e}")
        import traceback
        traceback.print_exc()
        return None


def export_to_csv(scenic_data, user_data, output_path):
    """导出分析结果到 CSV"""
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = output_path or f"behavior_analysis_{timestamp}.csv"
        
        with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            
            # 写入景点点击统计
            writer.writerow(["景点点击统计"])
            writer.writerow(["景点ID", "景点名称", "城市", "点击次数", "独立用户数"])
            if scenic_data and scenic_data.get('top_spots'):
                for spot_info, count in scenic_data['top_spots']:
                    if isinstance(spot_info, dict):
                        writer.writerow([
                            spot_info.get('id', 'N/A'),
                            spot_info.get('name', 'N/A'),
                            spot_info.get('city', 'N/A'),
                            count,
                            'N/A'
                        ])
                    else:
                        writer.writerow([
                            spot_info.id if hasattr(spot_info, 'id') else 'N/A',
                            spot_info.name if hasattr(spot_info, 'name') else 'N/A',
                            spot_info.city if hasattr(spot_info, 'city') else 'N/A',
                            count,
                            'N/A'
                        ])
            
            writer.writerow([])  # 空行
            
            # 写入行为类型统计
            writer.writerow(["行为类型统计"])
            writer.writerow(["行为类型", "次数", "占比"])
            if user_data and user_data.get('behavior_types'):
                total = user_data.get('total_behaviors', 1)
                for btype, count in user_data['behavior_types'].items():
                    writer.writerow([btype, count, f"{count/total*100:.1f}%"])
        
        print(f"\n✅ 分析结果已导出到: {filename}")
        return filename
    
    except Exception as e:
        print(f"\n❌ 导出CSV失败: {e}")
        return None


def check_database_connection():
    """检查数据库连接"""
    try:
        # 尝试简单查询
        UserBehaviorLog.query.limit(1).all()
        return True
    except Exception as e:
        print(f"\n❌ 数据库连接失败: {e}")
        print("请检查：")
        print("  1. 数据库服务是否启动")
        print("  2. config.py 中的数据库配置是否正确")
        print("  3. 数据库表是否已创建（运行 flask db upgrade）")
        return False


if __name__ == '__main__':
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='用户行为分析脚本')
    parser.add_argument('--days', type=int, default=7, help='分析最近N天的数据（默认7天）')
    parser.add_argument('--top', type=int, default=10, help='Top N排行榜数量（默认10）')
    parser.add_argument('--export', choices=['csv'], help='导出报告格式')
    parser.add_argument('--output', type=str, help='输出文件路径')
    args = parser.parse_args()
    
    # 检查 tabulate 是否安装
    if not HAS_TABULATE:
        print("💡 提示：安装 tabulate 可获得更好的表格显示效果")
        print("   pip install tabulate\n")
    
    from flask import Flask
    from ..db import db as _db
    from config import Config
    
    try:
        app = Flask(__name__)
        app.config.from_object(Config)
        _db.init_app(app)
        
        with app.app_context():
            # 检查数据库连接
            if not check_database_connection():
                sys.exit(1)
            
            print("\n" + "=" * 70)
            print("🔍 用户行为分析报告")
            print(f"📅 分析时间范围：最近 {args.days} 天")
            print(f"🕒 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print("=" * 70)
            
            # 分析景点点击率
            scenic_data = analyze_scenic_click_rate(days=args.days, top_n=args.top)
            
            # 分析用户活跃度
            user_data = analyze_behavior_by_user(days=args.days, top_n=min(args.top, 10))
            
            # 导出到 CSV
            if args.export == 'csv':
                export_to_csv(scenic_data, user_data, args.output)
            
            print("\n" + "=" * 70)
            print("✅ 分析完成")
            print("=" * 70)
            
            # 给出建议
            if scenic_data and scenic_data['total_clicks'] < 10:
                print("\n💡 建议：当前行为数据较少，建议：")
                print("   1. 在前端多次点击推荐景点以产生更多行为数据")
                print("   2. 邀请多个用户进行测试以获得更有代表性的统计结果")
    
    except Exception as e:
        print(f"\n❌ 脚本执行出错: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
