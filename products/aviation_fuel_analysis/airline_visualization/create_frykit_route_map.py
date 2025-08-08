"""
使用frykit库创建航线地图的主程序
基于departure_airports的底图风格，添加航线可视化
"""

import pandas as pd
import os
import sys
from datetime import datetime

# 添加src路径以导入自定义模块
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

try:
    from src.visualizer.frykit_route_visualizer import FrykitRouteVisualizer
    from src.data_loader.flight_data_loader import FlightDataLoader
except ImportError as e:
    print(f"导入错误: {e}")
    print("请确保已安装所需依赖: frykit, cartopy, matplotlib")
    sys.exit(1)

def main():
    """主函数"""
    print("🗺️ 开始创建frykit风格的航线地图...")
    
    try:
        # 1. 检查frykit依赖
        try:
            import frykit.plot as fplt
        except ImportError:
            print("❌ 未安装frykit库，请使用以下命令安装:")
            print("pip install frykit")
            return
        
        # 2. 加载数据
        print("📊 正在加载航班数据...")
        data_loader = FlightDataLoader()
        
        # 读取样本数据（减少处理时间）
        raw_data = data_loader.load_raw_data(sample_size=2000)
        if raw_data is None or raw_data.empty:
            print("❌ 无法加载数据")
            return
        
        print(f"✅ 成功加载 {len(raw_data)} 条航班记录")
        
        # 3. 数据清洗（不需要传参数，直接调用）
        cleaned_data = data_loader.clean_and_validate_data()
        if cleaned_data is None or cleaned_data.empty:
            print("❌ 数据清洗后无有效数据")
            return
        
        print(f"✅ 清洗后剩余 {len(cleaned_data)} 条有效记录")
        
        # 4. 创建可视化器
        visualizer = FrykitRouteVisualizer()
        
        # 5. 生成多种航线地图
        
        # 5.1 标准航线地图（200条航线）
        print("\n🎨 生成标准航线地图...")
        fig1, main_ax1, mini_ax1 = visualizer.create_route_visualization(
            cleaned_data, max_routes=200, sample_size=1000
        )
        
        if fig1:
            output_path1 = visualizer.save_visualization(
                fig1, 'frykit_standard_routes.png'
            )
        
        # 5.2 密集航线地图（500条航线）
        print("\n🎨 生成密集航线地图...")
        fig2, main_ax2, mini_ax2 = visualizer.create_route_visualization(
            cleaned_data, max_routes=500, sample_size=2000
        )
        
        if fig2:
            output_path2 = visualizer.save_visualization(
                fig2, 'frykit_dense_routes.png'
            )
        
        # 5.3 精简航线地图（100条航线）
        print("\n🎨 生成精简航线地图...")
        fig3, main_ax3, mini_ax3 = visualizer.create_route_visualization(
            cleaned_data, max_routes=100, sample_size=500
        )
        
        if fig3:
            output_path3 = visualizer.save_visualization(
                fig3, 'frykit_simple_routes.png'
            )
        
        # 6. 生成数据统计报告
        print("\n📊 生成统计报告...")
        
        # 统计信息
        total_routes = len(cleaned_data)
        unique_cities = len(set(cleaned_data['出发城市'].unique()) | set(cleaned_data['到达城市'].unique()))
        unique_airports = len(set(cleaned_data['起飞机场'].unique()) | set(cleaned_data['降落机场'].unique()))
        
        # 距离统计
        if '里程（公里）' in cleaned_data.columns:
            distance_stats = cleaned_data['里程（公里）'].describe()
            avg_distance_str = f"{distance_stats['mean']:.1f}"
            max_distance_str = f"{distance_stats['max']:.1f}"
            min_distance_str = f"{distance_stats['min']:.1f}"
        else:
            avg_distance_str = "无数据"
            max_distance_str = "无数据"
            min_distance_str = "无数据"
        
        # 创建统计报告
        report = f"""
# 航线地图生成报告

## 生成时间
{datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')}

## 数据统计
- 总航班数: {total_routes:,} 条
- 覆盖城市: {unique_cities} 个
- 涉及机场: {unique_airports} 个
- 平均航程: {avg_distance_str} 公里
- 最长航程: {max_distance_str} 公里
- 最短航程: {min_distance_str} 公里

## 生成的地图文件
1. **标准航线地图**: frykit_standard_routes.png (200条航线)
2. **密集航线地图**: frykit_dense_routes.png (500条航线)  
3. **精简航线地图**: frykit_simple_routes.png (100条航线)

## 地图特色
- 🗺️ 采用frykit库的专业中国地图投影
- 🏝️ 包含南海诸岛小地图
- 🧭 带有指北针和比例尺
- 🎨 根据航程距离进行颜色编码
- 📍 区分起飞和降落机场
- 📊 显示详细统计信息

## 技术说明
- 投影方式: 中国等距方位投影
- 坐标系统: WGS84
- 地图底图: frykit内置中国地图
- 航线分类: 短程(<1000km)、中程(1000-2000km)、长程(>2000km)
"""
        
        # 保存报告
        report_path = os.path.join('results', 'frykit_route_map_report.md')
        os.makedirs('results', exist_ok=True)
        
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report)
        
        print(f"✅ 统计报告已保存: {report_path}")
        
        print("\n🎉 frykit航线地图生成完成!")
        print("📂 所有文件保存在 results/charts/ 目录")
        
    except Exception as e:
        print(f"❌ 生成过程中出现错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main() 