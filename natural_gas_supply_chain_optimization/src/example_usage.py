"""
使用示例
展示如何使用重构后的模块化天然气供应链优化系统
"""

import logging
import os
from modules import SupplyChainController, run_quick_optimization

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def example_1_full_optimization():
    """示例1: 运行完整优化流程"""
    print("=== 示例1: 完整优化流程 ===")
    
    # 创建控制器
    controller = SupplyChainController(use_baidu_routing=True)
    
    try:
        # 运行优化
        timestamp = controller.run_full_optimization()
        
        # 获取结果摘要
        summary = controller.get_optimization_summary()
        
        print(f"优化完成，结果时间戳: {timestamp}")
        print(f"优化状态: {summary['optimization_status']}")
        print(f"总成本: {summary['total_cost_yuan']:,.2f} 元")
        print(f"建设设施数: {summary['facilities_built']}")
        print(f"总装机容量: {summary['total_capacity_mw']:.2f} MW")
        
    finally:
        controller.cleanup()

def example_2_quick_optimization():
    """示例2: 使用便捷函数快速优化"""
    print("=== 示例2: 快速优化 ===")
    
    timestamp, summary = run_quick_optimization(use_baidu_routing=False)
    
    print(f"快速优化完成，时间戳: {timestamp}")
    print(f"总成本: {summary['total_cost_yuan']:,.2f} 元")

def example_3_data_loading_only():
    """示例3: 仅加载和处理数据"""
    print("=== 示例3: 数据加载 ===")
    
    controller = SupplyChainController(use_baidu_routing=False)
    
    try:
        # 仅加载数据
        raw_data = controller.load_data_only()
        
        print(f"机场数据: {len(raw_data['airports'])} 条记录")
        print(f"可再生能源数据: {len(raw_data['renewable'])} 条记录")
        print(f"管道数据: {len(raw_data['pipelines'])} 条记录")
        print(f"LNG接收站数据: {len(raw_data['lng_terminals'])} 条记录")
        
        # 处理数据
        controller._process_all_data()
        
        # 导出处理后的数据
        controller.export_processed_data("exported_data")
        print("处理后的数据已导出到 exported_data 目录")
        
    finally:
        controller.cleanup()

def example_4_sensitivity_analysis():
    """示例4: 敏感性分析"""
    print("=== 示例4: 敏感性分析 ===")
    
    controller = SupplyChainController(use_baidu_routing=False)
    
    try:
        # 定义参数变化范围
        parameter_ranges = {
            'discount_rate': [0.06, 0.08, 0.10],
            'electricity_price_yuan_per_mwh': [300, 400, 500]
        }
        
        # 运行敏感性分析
        results = controller.run_sensitivity_analysis(parameter_ranges)
        
        print("敏感性分析完成:")
        for param_combo, timestamp in results.items():
            print(f"  {param_combo}: {timestamp}")
            
    finally:
        controller.cleanup()

def example_5_custom_config():
    """示例5: 使用自定义配置"""
    print("=== 示例5: 自定义配置 ===")
    
    # 创建自定义配置文件
    config_content = {
        "optimization": {
            "time_horizon_weeks": 2,
            "max_transport_distance_km": 800.0
        },
        "economic_parameters": {
            "discount_rate": 0.06,
            "electricity_price_yuan_per_mwh": 350.0
        }
    }
    
    import json
    config_file = "custom_config.json"
    with open(config_file, 'w', encoding='utf-8') as f:
        json.dump(config_content, f, indent=2)
    
    # 使用自定义配置
    controller = SupplyChainController(config_file=config_file, use_baidu_routing=False)
    
    try:
        config_summary = controller.get_config_summary()
        print(f"时间范围: {config_summary['time_horizon_weeks']} 周")
        print(f"最大运输距离: {config_summary['max_transport_distance_km']} km")
        
        # 运行优化
        timestamp = controller.run_full_optimization()
        print(f"自定义配置优化完成: {timestamp}")
        
    finally:
        controller.cleanup()
        # 清理配置文件
        if os.path.exists(config_file):
            os.remove(config_file)

if __name__ == "__main__":
    print("天然气供应链优化系统 - 使用示例")
    print("=" * 50)
    
    try:
        # 运行各个示例
        example_1_full_optimization()
        print()
        
    except Exception as e:
        print(f"示例运行出错: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n示例运行完成！")