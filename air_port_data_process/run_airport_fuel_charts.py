#!/usr/bin/env python
"""
运行机场燃油量图表可视化分析
"""

import os
import sys
import logging
from datetime import datetime

# 添加源代码目录到路径
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from airport_fuel_charts import AirportFuelCharts

def main():
    """主函数"""
    print("="*60)
    print("🛫 机场燃油量图表可视化分析")
    print("="*60)
    
    # 设置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('logs/airport_fuel_charts.log', encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    
    try:
        # 初始化可视化器
        print("🔧 初始化可视化器...")
        visualizer = AirportFuelCharts()
        
        print("📊 开始生成机场燃油量图表...")
        
        # 运行完整分析
        results = visualizer.run_complete_analysis()
        
        if results:
            print("\n✅ 分析完成！生成的文件：")
            for chart_type, file_path in results.items():
                if file_path:
                    print(f"   📈 {chart_type}: {os.path.basename(file_path)}")
                else:
                    print(f"   ❌ {chart_type}: 生成失败")
        else:
            print("❌ 分析失败！")
            
    except Exception as e:
        logging.error(f"运行时出错: {e}")
        print(f"❌ 运行时出错: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 