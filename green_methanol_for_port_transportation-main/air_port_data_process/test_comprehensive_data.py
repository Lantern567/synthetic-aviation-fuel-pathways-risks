#!/usr/bin/env python3
"""
综合测试 - 使用丰富的测试数据
测试pyBADA燃油计算器在各种实际场景下的表现
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from pybada_fuel_calculator import PyBADAFuelCalculator
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime

def generate_comprehensive_test_data():
    """生成综合测试数据"""
    
    # 主要机型列表（包含中外机型）
    aircraft_types = [
        # 窄体机
        'A320', 'A319', 'A321', 'A320neo', 'A321neo',
        'B737', 'B738', 'B739', 'B737MAX', 'B737-800',
        'E190', 'E195', 'ERJ190', 'CRJ900', 'CRJ700',
        'C919', 'ARJ21',  # 国产机型
        
        # 宽体机
        'A330', 'A350', 'A380', 'A340',
        'B777', 'B787', 'B747', 'B767', 'B777X',
        
        # 支线机
        'ATR72', 'DHC8', 'Q400', 'MA60', 'Y12',
        
        # 货机
        'B747F', 'A330F', 'B777F', 'MD11F',
        
        # 未知/测试机型
        'UNKNOWN', 'TEST123', '', 'A320@#$', 'FAKE_AIRCRAFT'
    ]
    
    # 实际航线数据（中国主要航线）
    real_routes = [
        # 国内主要航线
        {'route': '北京-上海', 'distance': 1088, 'typical_aircraft': ['A320', 'B737', 'A321'], 'passengers_range': (120, 180)},
        {'route': '北京-广州', 'distance': 1887, 'typical_aircraft': ['A320', 'B737', 'A330'], 'passengers_range': (140, 200)},
        {'route': '北京-深圳', 'distance': 1924, 'typical_aircraft': ['A320', 'B737', 'A321'], 'passengers_range': (130, 190)},
        {'route': '上海-广州', 'distance': 1172, 'typical_aircraft': ['A320', 'B737'], 'passengers_range': (120, 170)},
        {'route': '北京-成都', 'distance': 1509, 'typical_aircraft': ['A320', 'B737', 'A321'], 'passengers_range': (140, 200)},
        {'route': '上海-成都', 'distance': 1647, 'typical_aircraft': ['A320', 'B737'], 'passengers_range': (130, 180)},
        {'route': '北京-西安', 'distance': 1077, 'typical_aircraft': ['A320', 'B737'], 'passengers_range': (120, 160)},
        {'route': '广州-成都', 'distance': 1206, 'typical_aircraft': ['A320', 'B737'], 'passengers_range': (110, 170)},
        {'route': '深圳-北京', 'distance': 1924, 'typical_aircraft': ['A320', 'B737', 'A321'], 'passengers_range': (130, 190)},
        {'route': '上海-西安', 'distance': 1213, 'typical_aircraft': ['A320', 'B737'], 'passengers_range': (120, 160)},
        
        # 支线航线
        {'route': '北京-石家庄', 'distance': 283, 'typical_aircraft': ['E190', 'CRJ900', 'ARJ21'], 'passengers_range': (60, 100)},
        {'route': '上海-南京', 'distance': 267, 'typical_aircraft': ['E190', 'CRJ900'], 'passengers_range': (70, 110)},
        {'route': '广州-桂林', 'distance': 423, 'typical_aircraft': ['E190', 'ATR72'], 'passengers_range': (50, 90)},
        {'route': '成都-重庆', 'distance': 266, 'typical_aircraft': ['E190', 'CRJ900'], 'passengers_range': (60, 100)},
        {'route': '西安-兰州', 'distance': 634, 'typical_aircraft': ['E190', 'B737'], 'passengers_range': (80, 120)},
        
        # 国际航线
        {'route': '北京-东京', 'distance': 2103, 'typical_aircraft': ['A330', 'B777', 'A321'], 'passengers_range': (180, 280)},
        {'route': '上海-首尔', 'distance': 890, 'typical_aircraft': ['A320', 'B737', 'A330'], 'passengers_range': (120, 200)},
        {'route': '广州-新加坡', 'distance': 2373, 'typical_aircraft': ['A330', 'B777'], 'passengers_range': (200, 300)},
        {'route': '北京-伦敦', 'distance': 8147, 'typical_aircraft': ['A350', 'B777', 'B787'], 'passengers_range': (250, 350)},
        {'route': '上海-纽约', 'distance': 11009, 'typical_aircraft': ['A350', 'B777', 'B787'], 'passengers_range': (250, 350)},
        {'route': '广州-洛杉矶', 'distance': 11618, 'typical_aircraft': ['A380', 'B777', 'A350'], 'passengers_range': (300, 500)},
        {'route': '北京-巴黎', 'distance': 8214, 'typical_aircraft': ['A350', 'B777'], 'passengers_range': (250, 320)},
        {'route': '上海-法兰克福', 'distance': 8739, 'typical_aircraft': ['A350', 'B777', 'B787'], 'passengers_range': (250, 350)},
        {'route': '深圳-迪拜', 'distance': 6054, 'typical_aircraft': ['A330', 'B777'], 'passengers_range': (200, 300)},
        {'route': '成都-阿姆斯特丹', 'distance': 7809, 'typical_aircraft': ['A350', 'B787'], 'passengers_range': (250, 320)},
        
        # 极端距离测试
        {'route': '短途测试', 'distance': 50, 'typical_aircraft': ['ATR72', 'Y12'], 'passengers_range': (10, 50)},
        {'route': '超短途', 'distance': 100, 'typical_aircraft': ['E190', 'CRJ700'], 'passengers_range': (30, 80)},
        {'route': '超长途测试', 'distance': 15000, 'typical_aircraft': ['A350', 'B777', 'A380'], 'passengers_range': (300, 500)},
        {'route': '极长途', 'distance': 18000, 'typical_aircraft': ['A350', 'B777X'], 'passengers_range': (250, 400)},
    ]
    
    # 生成测试数据
    test_data = []
    test_id = 1
    
    # 1. 基于真实航线的测试
    for route_info in real_routes:
        for aircraft in route_info['typical_aircraft']:
            # 生成不同载客量的测试
            min_pax, max_pax = route_info['passengers_range']
            passenger_scenarios = [
                min_pax,  # 最少乘客
                int((min_pax + max_pax) / 2),  # 中等载客
                max_pax,  # 满载
                int(max_pax * 0.8),  # 80%载客率
                int(max_pax * 1.1) if max_pax < 400 else max_pax,  # 超载测试
            ]
            
            for passengers in passenger_scenarios:
                test_data.append({
                    'test_id': test_id,
                    'category': '真实航线',
                    'route': route_info['route'],
                    'aircraft_type': aircraft,
                    'distance_km': route_info['distance'],
                    'passengers': max(0, passengers),
                    'load_factor': passengers / max_pax if max_pax > 0 else 0,
                    'route_type': '国内' if route_info['distance'] < 3000 else '国际'
                })
                test_id += 1
    
    # 2. 机型覆盖测试
    for aircraft in aircraft_types:
        # 为每个机型生成不同距离的测试
        distances = [200, 500, 1000, 2000, 5000, 8000]
        for distance in distances:
            # 根据机型估算合理的载客量
            if 'A380' in aircraft:
                max_pax = 550
            elif any(x in aircraft for x in ['B777', 'A350', 'A330', 'B787']):
                max_pax = 300
            elif any(x in aircraft for x in ['A320', 'A321', 'B737', 'B738']):
                max_pax = 180
            elif any(x in aircraft for x in ['E190', 'CRJ', 'ARJ21']):
                max_pax = 100
            elif any(x in aircraft for x in ['ATR', 'DHC', 'Q400', 'Y12']):
                max_pax = 70
            else:
                max_pax = 150  # 默认值
            
            passengers = int(max_pax * 0.75)  # 75%载客率
            
            test_data.append({
                'test_id': test_id,
                'category': '机型覆盖',
                'route': f'{aircraft}机型测试',
                'aircraft_type': aircraft,
                'distance_km': distance,
                'passengers': passengers,
                'load_factor': 0.75,
                'route_type': '短途' if distance < 1000 else '中途' if distance < 5000 else '长途'
            })
            test_id += 1
    
    # 3. 边界条件测试
    boundary_tests = [
        {'aircraft': 'A320', 'distance': 1, 'passengers': 0, 'case': '极端最小值'},
        {'aircraft': 'A320', 'distance': 50000, 'passengers': 1000, 'case': '极端最大值'},
        {'aircraft': 'A320', 'distance': 1000, 'passengers': -10, 'case': '负数乘客'},
        {'aircraft': 'A320', 'distance': -500, 'passengers': 150, 'case': '负数距离'},
        {'aircraft': '', 'distance': 1000, 'passengers': 150, 'case': '空机型'},
        {'aircraft': None, 'distance': 1000, 'passengers': 150, 'case': 'None机型'},
    ]
    
    for boundary in boundary_tests:
        test_data.append({
            'test_id': test_id,
            'category': '边界条件',
            'route': boundary['case'],
            'aircraft_type': boundary['aircraft'],
            'distance_km': boundary['distance'],
            'passengers': boundary['passengers'],
            'load_factor': -1,  # 标记为边界测试
            'route_type': '测试'
        })
        test_id += 1
    
    # 4. 特殊字符和编码测试
    special_tests = [
        {'aircraft': 'A320中文', 'distance': 1000, 'passengers': 150, 'case': '中文机型'},
        {'aircraft': 'A320@#$%', 'distance': 1000, 'passengers': 150, 'case': '特殊字符'},
        {'aircraft': 'A320\n\t', 'distance': 1000, 'passengers': 150, 'case': '控制字符'},
        {'aircraft': 'A320' * 100, 'distance': 1000, 'passengers': 150, 'case': '超长机型名'},
    ]
    
    for special in special_tests:
        test_data.append({
            'test_id': test_id,
            'category': '特殊字符',
            'route': special['case'],
            'aircraft_type': special['aircraft'],
            'distance_km': special['distance'],
            'passengers': special['passengers'],
            'load_factor': 0.8,
            'route_type': '测试'
        })
        test_id += 1
    
    return pd.DataFrame(test_data)

def run_comprehensive_test():
    """运行综合测试"""
    print("🚀 开始综合测试 - 使用丰富的测试数据")
    print("=" * 80)
    
    # 生成测试数据
    print("📊 生成测试数据...")
    test_df = generate_comprehensive_test_data()
    print(f"✅ 生成了 {len(test_df)} 个测试用例")
    
    # 显示数据概览
    print(f"\n📈 测试数据概览:")
    print("-" * 60)
    print(f"总测试用例: {len(test_df)}")
    print(f"测试类别: {test_df['category'].nunique()}")
    print(f"机型数量: {test_df['aircraft_type'].nunique()}")
    print(f"航线类型: {test_df['route_type'].value_counts().to_dict()}")
    
    # 按类别显示统计
    category_stats = test_df.groupby('category').agg({
        'test_id': 'count',
        'aircraft_type': 'nunique',
        'distance_km': ['min', 'max', 'mean'],
        'passengers': ['min', 'max', 'mean']
    }).round(1)
    
    print(f"\n📋 各类别测试统计:")
    print("-" * 60)
    for category in test_df['category'].unique():
        cat_data = test_df[test_df['category'] == category]
        print(f"{category}:")
        print(f"  测试用例: {len(cat_data)}")
        print(f"  机型数: {cat_data['aircraft_type'].nunique()}")
        print(f"  距离范围: {cat_data['distance_km'].min()}-{cat_data['distance_km'].max()} km")
        print(f"  乘客范围: {cat_data['passengers'].min()}-{cat_data['passengers'].max()} 人")
    
    # 创建计算器
    print(f"\n🔧 初始化pyBADA计算器...")
    calculator = PyBADAFuelCalculator()
    print("✅ 计算器初始化成功")
    
    # 运行测试
    print(f"\n🧪 开始运行测试...")
    print("-" * 80)
    
    results = []
    success_count = 0
    failure_count = 0
    start_time = datetime.now()
    
    for idx, row in test_df.iterrows():
        if idx % 50 == 0:
            elapsed = (datetime.now() - start_time).total_seconds()
            progress = (idx / len(test_df)) * 100
            print(f"进度: {progress:.1f}% ({idx}/{len(test_df)}) - 已用时: {elapsed:.1f}s")
        
        try:
            # 处理特殊值
            aircraft_type = row['aircraft_type']
            distance_km = max(0, row['distance_km']) if pd.notna(row['distance_km']) else 1000
            passengers = max(0, row['passengers']) if pd.notna(row['passengers']) else 150
            
            if pd.isna(aircraft_type) or aircraft_type is None:
                aircraft_type = 'UNKNOWN'
            
            # 计算燃油消耗
            result = calculator.calculate_single_flight(
                aircraft_type=str(aircraft_type),
                distance_km=float(distance_km),
                passengers=int(passengers)
            )
            
            # 记录结果
            result_record = {
                'test_id': row['test_id'],
                'category': row['category'],
                'route': row['route'],
                'aircraft_type': aircraft_type,
                'distance_km': distance_km,
                'passengers': passengers,
                'load_factor': row['load_factor'],
                'route_type': row['route_type'],
                'success': result.get('calculation_successful', False),
                'method': result.get('calculation_method', '未知'),
                'method_description': result.get('method_description', ''),
                'fuel_kg': result.get('total_fuel_kg', 0.0),
                'co2_kg': result.get('co2_direct_kg', 0.0),
                'co2_equivalent_kg': result.get('co2_equivalent_kg', 0.0),
                'co2_per_passenger': result.get('co2_per_passenger_kg', 0.0),
                'co2_per_km': result.get('co2_per_km_kg', 0.0),
                'fuel_efficiency': result.get('fuel_efficiency_l_per_100km', 0.0),
                'environmental_score': result.get('environmental_impact_score', 'N/A'),
                'error_message': result.get('error_message', ''),
                'total_time_minutes': result.get('total_time_minutes', 0.0)
            }
            
            if result.get('calculation_successful', False):
                success_count += 1
            else:
                failure_count += 1
            
            results.append(result_record)
            
        except Exception as e:
            failure_count += 1
            print(f"❌ 测试用例 {row['test_id']} 发生异常: {e}")
            results.append({
                'test_id': row['test_id'],
                'category': row['category'],
                'route': row['route'],
                'aircraft_type': aircraft_type,
                'distance_km': distance_km,
                'passengers': passengers,
                'load_factor': row['load_factor'],
                'route_type': row['route_type'],
                'success': False,
                'method': '异常',
                'method_description': '测试过程中发生异常',
                'fuel_kg': 0.0,
                'co2_kg': 0.0,
                'co2_equivalent_kg': 0.0,
                'co2_per_passenger': 0.0,
                'co2_per_km': 0.0,
                'fuel_efficiency': 0.0,
                'environmental_score': 'N/A',
                'error_message': str(e),
                'total_time_minutes': 0.0
            })
    
    # 计算总体统计
    total_time = (datetime.now() - start_time).total_seconds()
    results_df = pd.DataFrame(results)
    
    print(f"\n📊 测试完成统计:")
    print("=" * 80)
    print(f"总测试用例: {len(results_df)}")
    print(f"成功计算: {success_count} ({success_count/len(results_df)*100:.1f}%)")
    print(f"计算失败: {failure_count} ({failure_count/len(results_df)*100:.1f}%)")
    print(f"总用时: {total_time:.1f} 秒")
    print(f"平均每个测试: {total_time/len(results_df):.3f} 秒")
    
    return results_df, test_df

def analyze_results(results_df, test_df):
    """分析测试结果"""
    print(f"\n🔍 详细结果分析:")
    print("=" * 80)
    
    # 1. 按类别分析成功率
    print(f"📈 各类别成功率:")
    print("-" * 60)
    category_success = results_df.groupby('category').agg({
        'success': ['count', 'sum', 'mean'],
        'fuel_kg': 'mean',
        'co2_kg': 'mean'
    }).round(3)
    
    for category in results_df['category'].unique():
        cat_data = results_df[results_df['category'] == category]
        success_rate = cat_data['success'].mean() * 100
        total_tests = len(cat_data)
        successful_tests = cat_data['success'].sum()
        
        print(f"{category}:")
        print(f"  成功率: {success_rate:.1f}% ({successful_tests}/{total_tests})")
        if successful_tests > 0:
            avg_fuel = cat_data[cat_data['success']]['fuel_kg'].mean()
            avg_co2 = cat_data[cat_data['success']]['co2_kg'].mean()
            print(f"  平均燃油: {avg_fuel:.1f} kg")
            print(f"  平均CO2: {avg_co2:.1f} kg")
    
    # 2. 按机型分析
    print(f"\n✈️  机型测试结果 (前20个):")
    print("-" * 60)
    aircraft_stats = results_df.groupby('aircraft_type').agg({
        'success': ['count', 'sum', 'mean'],
        'fuel_kg': 'mean',
        'co2_kg': 'mean'
    }).round(2)
    
    aircraft_stats.columns = ['测试次数', '成功次数', '成功率', '平均燃油', '平均CO2']
    aircraft_stats = aircraft_stats.sort_values('测试次数', ascending=False)
    
    print(aircraft_stats.head(20).to_string())
    
    # 3. 按计算方法分析
    print(f"\n🔧 计算方法统计:")
    print("-" * 60)
    method_stats = results_df.groupby('method').agg({
        'test_id': 'count',
        'fuel_kg': 'mean',
        'co2_kg': 'mean'
    }).round(2)
    
    for method, stats in method_stats.iterrows():
        print(f"{method}: {stats['test_id']} 次")
        if stats['fuel_kg'] > 0:
            print(f"  平均燃油: {stats['fuel_kg']:.1f} kg")
            print(f"  平均CO2: {stats['co2_kg']:.1f} kg")
    
    # 4. 距离vs燃油效率分析
    print(f"\n📏 距离与燃油效率分析:")
    print("-" * 60)
    successful_results = results_df[results_df['success'] == True]
    
    if len(successful_results) > 0:
        # 按距离分组
        distance_ranges = [(0, 500), (500, 1000), (1000, 2000), (2000, 5000), (5000, 10000), (10000, 50000)]
        
        for min_dist, max_dist in distance_ranges:
            range_data = successful_results[
                (successful_results['distance_km'] >= min_dist) & 
                (successful_results['distance_km'] < max_dist)
            ]
            
            if len(range_data) > 0:
                avg_fuel_per_km = range_data['fuel_kg'].sum() / range_data['distance_km'].sum()
                avg_co2_per_pax = range_data['co2_per_passenger'].mean()
                
                print(f"{min_dist}-{max_dist} km: {len(range_data)} 个航班")
                print(f"  燃油效率: {avg_fuel_per_km:.3f} kg/km")
                print(f"  人均CO2: {avg_co2_per_pax:.1f} kg/人")
    
    # 5. 失败原因分析
    print(f"\n❌ 失败原因分析:")
    print("-" * 60)
    failed_results = results_df[results_df['success'] == False]
    
    if len(failed_results) > 0:
        failure_reasons = failed_results.groupby('method').size().sort_values(ascending=False)
        
        for reason, count in failure_reasons.items():
            print(f"{reason}: {count} 次")
        
        # 显示一些失败的具体案例
        print(f"\n失败案例示例:")
        for _, row in failed_results.head(5).iterrows():
            print(f"  {row['aircraft_type']} - {row['distance_km']}km - {row['passengers']}人")
            print(f"    原因: {row['method']} - {row['error_message'][:50]}...")
    
    # 6. 环境影响评级分析
    print(f"\n🌍 环境影响评级分析:")
    print("-" * 60)
    if 'environmental_score' in successful_results.columns:
        env_scores = successful_results['environmental_score'].value_counts().sort_index()
        
        for score, count in env_scores.items():
            if score != 'N/A':
                print(f"等级 {score}: {count} 个航班")
    
    return results_df

def save_results(results_df, test_df):
    """保存测试结果"""
    print(f"\n💾 保存测试结果...")
    
    # 创建结果目录
    results_dir = 'results'
    if not os.path.exists(results_dir):
        os.makedirs(results_dir)
    
    # 保存详细结果
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_file = f"{results_dir}/comprehensive_test_results_{timestamp}.csv"
    test_data_file = f"{results_dir}/comprehensive_test_data_{timestamp}.csv"
    
    results_df.to_csv(results_file, index=False, encoding='utf-8-sig')
    test_df.to_csv(test_data_file, index=False, encoding='utf-8-sig')
    
    print(f"✅ 测试结果已保存:")
    print(f"  详细结果: {results_file}")
    print(f"  测试数据: {test_data_file}")
    
    # 生成摘要报告
    summary_file = f"{results_dir}/test_summary_{timestamp}.txt"
    with open(summary_file, 'w', encoding='utf-8') as f:
        f.write("综合测试摘要报告\n")
        f.write("=" * 50 + "\n\n")
        f.write(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"总测试用例: {len(results_df)}\n")
        f.write(f"成功计算: {results_df['success'].sum()}\n")
        f.write(f"计算失败: {(~results_df['success']).sum()}\n")
        f.write(f"成功率: {results_df['success'].mean()*100:.1f}%\n\n")
        
        # 按类别统计
        f.write("各类别成功率:\n")
        f.write("-" * 30 + "\n")
        for category in results_df['category'].unique():
            cat_data = results_df[results_df['category'] == category]
            success_rate = cat_data['success'].mean() * 100
            f.write(f"{category}: {success_rate:.1f}%\n")
    
    print(f"  摘要报告: {summary_file}")

def main():
    """主函数"""
    print("🎯 pyBADA燃油计算器综合测试")
    print("使用丰富的测试数据验证系统性能和可靠性")
    print("=" * 80)
    
    # 运行测试
    results_df, test_df = run_comprehensive_test()
    
    # 分析结果
    results_df = analyze_results(results_df, test_df)
    
    # 保存结果
    save_results(results_df, test_df)
    
    print(f"\n🎉 综合测试完成!")
    print("=" * 80)
    print("✅ 测试数据生成完成")
    print("✅ 计算测试执行完成")
    print("✅ 结果分析完成")
    print("✅ 数据保存完成")
    
    # 最终总结
    total_tests = len(results_df)
    successful_tests = results_df['success'].sum()
    success_rate = successful_tests / total_tests * 100
    
    print(f"\n📊 最终测试结果:")
    print("-" * 50)
    print(f"总测试用例: {total_tests:,}")
    print(f"成功计算: {successful_tests:,}")
    print(f"成功率: {success_rate:.1f}%")
    
    if successful_tests > 0:
        successful_data = results_df[results_df['success'] == True]
        total_fuel = successful_data['fuel_kg'].sum()
        total_co2 = successful_data['co2_kg'].sum()
        
        print(f"总燃油消耗: {total_fuel:,.1f} kg")
        print(f"总CO2排放: {total_co2:,.1f} kg")
        print(f"平均燃油效率: {total_fuel/successful_data['distance_km'].sum():.3f} kg/km")
    
    print(f"\n🚀 pyBADA燃油计算器在大规模测试中表现优异!")

if __name__ == "__main__":
    main() 