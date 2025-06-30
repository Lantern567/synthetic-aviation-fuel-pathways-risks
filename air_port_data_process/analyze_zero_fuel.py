#!/usr/bin/env python
"""
分析燃油量为0的机场数据
"""

import os
import sys
import pandas as pd
import numpy as np
import logging

# 添加源代码目录到路径
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from airport_fuel_charts import AirportFuelCharts

def main():
    """主函数"""
    print("="*60)
    print("🔍 分析燃油量为0的机场数据")
    print("="*60)
    
    # 设置日志
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    try:
        # 初始化可视化器
        visualizer = AirportFuelCharts()
        
        # 加载原始数据
        print("📊 加载原始数据...")
        fuel_df = visualizer.load_fuel_calculation_results()
        
        print(f"✅ 成功加载 {len(fuel_df)} 条记录")
        print(f"📋 数据列名: {list(fuel_df.columns)}")
        
        # 检查燃油量列
        fuel_columns = [col for col in fuel_df.columns if '燃油' in col or '油量' in col or 'fuel' in col.lower()]
        print(f"🛢️  燃油量相关列: {fuel_columns}")
        
        if not fuel_columns:
            print("❌ 未找到燃油量列！")
            return
            
        fuel_col = fuel_columns[0]
        print(f"🎯 使用燃油量列: {fuel_col}")
        
        # 获取机场列
        airport_columns = [col for col in fuel_df.columns if '起飞机场' in col]
        if not airport_columns:
            print("❌ 未找到起飞机场列！")
            return
        airport_col = airport_columns[0]
        
        # 分析燃油量数据
        print("\n" + "="*50)
        print("📈 燃油量数据分析")
        print("="*50)
        
        # 基本统计
        print(f"总记录数: {len(fuel_df):,}")
        print(f"燃油量统计:")
        print(f"  - 最小值: {fuel_df[fuel_col].min():.2f}")
        print(f"  - 最大值: {fuel_df[fuel_col].max():.2f}")
        print(f"  - 平均值: {fuel_df[fuel_col].mean():.2f}")
        print(f"  - 中位数: {fuel_df[fuel_col].median():.2f}")
        print(f"  - 标准差: {fuel_df[fuel_col].std():.2f}")
        
        # 检查0值和负值
        zero_fuel = fuel_df[fuel_df[fuel_col] == 0]
        negative_fuel = fuel_df[fuel_df[fuel_col] < 0]
        null_fuel = fuel_df[fuel_df[fuel_col].isna()]
        
        print(f"\n🔍 异常值分析:")
        print(f"  - 燃油量为0的记录: {len(zero_fuel):,} ({len(zero_fuel)/len(fuel_df)*100:.2f}%)")
        print(f"  - 燃油量为负的记录: {len(negative_fuel):,} ({len(negative_fuel)/len(fuel_df)*100:.2f}%)")
        print(f"  - 燃油量为空的记录: {len(null_fuel):,} ({len(null_fuel)/len(fuel_df)*100:.2f}%)")
        
        # 分析0燃油量的记录
        if len(zero_fuel) > 0:
            print(f"\n🔍 分析燃油量为0的记录:")
            
            # 按机场统计
            zero_by_airport = zero_fuel[airport_col].value_counts()
            
            print(f"📍 涉及的机场数: {len(zero_by_airport)}")
            print(f"🔝 燃油量为0记录最多的前10个机场:")
            for airport, count in zero_by_airport.head(10).items():
                print(f"     {airport}: {count:,} 条记录")
            
            # 检查这些记录的其他特征
            print(f"\n📊 燃油量为0记录的其他特征:")
            if '航班号' in zero_fuel.columns:
                print(f"  - 航班号样例: {list(zero_fuel['航班号'].head(5))}")
            
            if '日期' in zero_fuel.columns:
                print(f"  - 日期范围: {zero_fuel['日期'].min()} 到 {zero_fuel['日期'].max()}")
            
            # 检查是否有其他相关列
            other_cols = [col for col in zero_fuel.columns if col not in [fuel_col, airport_col, '航班号', '日期']]
            print(f"  - 其他列: {other_cols[:5]}...")  # 显示前5个
            
            # 保存0燃油量的记录到文件
            output_file = 'results/tables/zero_fuel_records.xlsx'
            os.makedirs(os.path.dirname(output_file), exist_ok=True)
            zero_fuel.to_excel(output_file, index=False)
            print(f"\n💾 燃油量为0的记录已保存到: {output_file}")
        
        # 分析聚合后的数据
        print(f"\n" + "="*50)
        print("📊 聚合后的机场燃油量分析")
        print("="*50)
        
        aggregated = visualizer.aggregate_fuel_by_airport_2024(fuel_df)
        
        # 检查聚合后燃油量为0的机场
        zero_airports = aggregated[aggregated['总燃油量'] == 0]
        
        print(f"🔍 聚合后燃油量为0的机场: {len(zero_airports)}")
        
        if len(zero_airports) > 0:
            print(f"📋 这些机场列表:")
            for _, row in zero_airports.iterrows():
                print(f"     {row['机场名称']}: 航班数量={row['航班数量']}, 平均燃油量={row['平均燃油量']:.2f}")
        
        # 分析燃油量很小的机场
        small_fuel = aggregated[aggregated['总燃油量'] < 1000]  # 小于1000kg
        print(f"\n🔍 燃油量极小(<1000kg)的机场: {len(small_fuel)}")
        
        if len(small_fuel) > 0:
            print(f"📋 这些机场列表:")
            for _, row in small_fuel.iterrows():
                print(f"     {row['机场名称']}: 总燃油量={row['总燃油量']:.2f}kg, 航班数量={row['航班数量']}")
        
        # 检查数据质量
        print(f"\n" + "="*50)
        print("🔍 数据质量检查")
        print("="*50)
        
        # 检查航班号格式
        if '航班号' in fuel_df.columns:
            unique_flights = fuel_df['航班号'].nunique()
            total_records = len(fuel_df)
            print(f"✈️  航班号统计:")
            print(f"  - 唯一航班号数量: {unique_flights:,}")
            print(f"  - 总记录数: {total_records:,}")
            print(f"  - 平均每航班记录数: {total_records/unique_flights:.2f}")
        
        # 检查机场数量
        unique_airports = fuel_df[airport_col].nunique()
        print(f"🏛️  机场统计:")
        print(f"  - 唯一机场数量: {unique_airports}")
        print(f"  - 平均每机场记录数: {len(fuel_df)/unique_airports:.2f}")
        
        # 按机场显示记录数分布
        airport_counts = fuel_df[airport_col].value_counts()
        print(f"📊 各机场记录数分布:")
        print(f"  - 记录最多的机场: {airport_counts.index[0]} ({airport_counts.iloc[0]:,} 条)")
        print(f"  - 记录最少的机场: {airport_counts.index[-1]} ({airport_counts.iloc[-1]:,} 条)")
        print(f"  - 中位数记录数: {airport_counts.median():.0f}")
        
        
    except Exception as e:
        print(f"❌ 分析过程中出错: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main() 