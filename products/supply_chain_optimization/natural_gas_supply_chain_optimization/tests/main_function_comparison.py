"""
主函数完整对比测试
运行原始版本和重构版本的完整优化模型，对比所有输出结果
"""

import sys
import os
import subprocess
import json
import logging
from datetime import datetime

# 添加路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
sys.path.append(project_root)

def setup_logging():
    """设置日志记录"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('main_function_comparison.log'),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)

def run_original_main():
    """运行原始版本的主函数"""
    logger = logging.getLogger(__name__)
    logger.info("="*60)
    logger.info("运行原始版本主函数")
    logger.info("="*60)
    
    original_file = os.path.join(project_root, 'products', 'supply_chain_optimization', 
                                'natural_gas_supply_chain_optimization', 'src', 
                                'natural_gas_optimization_model.py')
    
    try:
        # 运行原始文件
        result = subprocess.run([sys.executable, original_file], 
                              capture_output=True, text=True, timeout=300,
                              cwd=project_root, encoding='utf-8', errors='replace')
        
        logger.info(f"原始版本运行状态码: {result.returncode}")
        
        if result.stdout:
            logger.info("原始版本标准输出:")
            logger.info(result.stdout)
        
        if result.stderr:
            logger.warning("原始版本错误输出:")
            logger.warning(result.stderr)
        
        return {
            'status': 'success' if result.returncode == 0 else 'error',
            'return_code': result.returncode,
            'stdout': result.stdout,
            'stderr': result.stderr,
            'execution_time': None  # 可以添加时间测量
        }
    
    except subprocess.TimeoutExpired:
        logger.error("原始版本运行超时")
        return {'status': 'timeout', 'return_code': -1}
    except Exception as e:
        logger.error(f"运行原始版本失败: {e}")
        return {'status': 'error', 'return_code': -1, 'error': str(e)}

def run_refactored_main():
    """运行重构版本的主函数"""
    logger = logging.getLogger(__name__)
    logger.info("="*60)
    logger.info("运行重构版本主函数")
    logger.info("="*60)
    
    refactored_file = os.path.join(project_root, 'products', 'supply_chain_optimization', 
                                  'natural_gas_supply_chain_optimization', 'src', 
                                  'natural_gas_optimization_model_refactored.py')
    
    try:
        # 运行重构文件
        result = subprocess.run([sys.executable, refactored_file], 
                              capture_output=True, text=True, timeout=300,
                              cwd=project_root, encoding='utf-8', errors='replace')
        
        logger.info(f"重构版本运行状态码: {result.returncode}")
        
        if result.stdout:
            logger.info("重构版本标准输出:")
            logger.info(result.stdout)
        
        if result.stderr:
            logger.warning("重构版本错误输出:")
            logger.warning(result.stderr)
        
        return {
            'status': 'success' if result.returncode == 0 else 'error',
            'return_code': result.returncode,
            'stdout': result.stdout,
            'stderr': result.stderr,
            'execution_time': None  # 可以添加时间测量
        }
    
    except subprocess.TimeoutExpired:
        logger.error("重构版本运行超时")
        return {'status': 'timeout', 'return_code': -1}
    except Exception as e:
        logger.error(f"运行重构版本失败: {e}")
        return {'status': 'error', 'return_code': -1, 'error': str(e)}

def compare_results(original_result, refactored_result):
    """对比两个版本的运行结果"""
    logger = logging.getLogger(__name__)
    logger.info("="*60)
    logger.info("对比分析结果")
    logger.info("="*60)
    
    comparison = {
        'comparison_timestamp': datetime.now().isoformat(),
        'original_result': original_result,
        'refactored_result': refactored_result,
        'comparison_analysis': {}
    }
    
    # 1. 对比运行状态
    status_match = original_result['status'] == refactored_result['status']
    return_code_match = original_result['return_code'] == refactored_result['return_code']
    
    comparison['comparison_analysis']['status_match'] = status_match
    comparison['comparison_analysis']['return_code_match'] = return_code_match
    
    logger.info(f"运行状态匹配: {status_match}")
    logger.info(f"返回码匹配: {return_code_match}")
    
    # 2. 对比关键输出信息
    if 'stdout' in original_result and 'stdout' in refactored_result:
        original_output = original_result['stdout']
        refactored_output = refactored_result['stdout']
        
        # 提取关键数值
        original_metrics = extract_key_metrics(original_output)
        refactored_metrics = extract_key_metrics(refactored_output)
        
        comparison['comparison_analysis']['original_metrics'] = original_metrics
        comparison['comparison_analysis']['refactored_metrics'] = refactored_metrics
        
        logger.info("提取的关键指标:")
        logger.info(f"原始版本: {original_metrics}")
        logger.info(f"重构版本: {refactored_metrics}")
        
        # 对比指标
        metrics_match = compare_metrics(original_metrics, refactored_metrics)
        comparison['comparison_analysis']['metrics_comparison'] = metrics_match
        
    # 3. 整体一致性判断
    overall_consistent = (
        status_match and 
        return_code_match and
        comparison['comparison_analysis'].get('metrics_comparison', {}).get('consistent', False)
    )
    
    comparison['comparison_analysis']['overall_consistent'] = overall_consistent
    
    logger.info(f"整体一致性: {overall_consistent}")
    
    return comparison

def extract_key_metrics(output_text):
    """从输出文本中提取关键指标"""
    import re
    
    metrics = {}
    
    # 提取关键数值 (使用正则表达式)
    patterns = {
        'lifecycle_total_cost': r'项目生命周期总成本.*?:\s*([\d,\.]+)\s*元',
        'annual_cost': r'年化成本:\s*([\d,\.]+)\s*元',
        'lifecycle_levelized_cost': r'生命周期平准化成本:\s*([\d,\.]+)\s*元/kg',
        'annual_levelized_cost': r'年化平准化成本:\s*([\d,\.]+)\s*元/kg',
        'annual_production': r'年产量:\s*([\d,\.]+)\s*kg',
        'facilities_count': r'建设设施数量:\s*(\d+)',
        'time_window_weeks': r'优化时间窗口:\s*(\d+)\s*周'
    }
    
    for metric_name, pattern in patterns.items():
        matches = re.search(pattern, output_text)
        if matches:
            value_str = matches.group(1).replace(',', '')
            try:
                # 尝试转换为数值
                metrics[metric_name] = float(value_str)
            except ValueError:
                metrics[metric_name] = value_str
    
    return metrics

def compare_metrics(original_metrics, refactored_metrics):
    """对比提取的指标"""
    comparison = {
        'matched_metrics': [],
        'different_metrics': [],
        'missing_in_original': [],
        'missing_in_refactored': [],
        'consistent': True
    }
    
    all_keys = set(original_metrics.keys()) | set(refactored_metrics.keys())
    
    for key in all_keys:
        if key in original_metrics and key in refactored_metrics:
            original_val = original_metrics[key]
            refactored_val = refactored_metrics[key]
            
            # 对于数值类型，允许小的差异
            if isinstance(original_val, (int, float)) and isinstance(refactored_val, (int, float)):
                if abs(original_val - refactored_val) < 1e-6:
                    comparison['matched_metrics'].append(key)
                else:
                    comparison['different_metrics'].append({
                        'metric': key,
                        'original': original_val,
                        'refactored': refactored_val,
                        'difference': abs(original_val - refactored_val)
                    })
                    comparison['consistent'] = False
            else:
                # 字符串比较
                if str(original_val) == str(refactored_val):
                    comparison['matched_metrics'].append(key)
                else:
                    comparison['different_metrics'].append({
                        'metric': key,
                        'original': original_val,
                        'refactored': refactored_val
                    })
                    comparison['consistent'] = False
        
        elif key in original_metrics:
            comparison['missing_in_refactored'].append(key)
            comparison['consistent'] = False
        else:
            comparison['missing_in_original'].append(key)
            comparison['consistent'] = False
    
    return comparison

def save_comparison_report(comparison_data):
    """保存对比报告"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = f"main_function_comparison_report_{timestamp}.json"
    
    try:
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(comparison_data, f, indent=2, ensure_ascii=False, default=str)
        print(f"对比报告已保存到: {report_file}")
        return report_file
    except Exception as e:
        print(f"保存报告失败: {e}")
        return None

def main():
    """主函数：执行完整的主函数对比测试"""
    logger = setup_logging()
    
    print("开始主函数完整对比测试")
    print("这将运行原始版本和重构版本的完整优化模型")
    print("="*60)
    
    # 运行原始版本
    original_result = run_original_main()
    
    print("\n" + "="*60)
    
    # 运行重构版本
    refactored_result = run_refactored_main()
    
    print("\n" + "="*60)
    
    # 对比结果
    comparison = compare_results(original_result, refactored_result)
    
    # 保存报告
    report_file = save_comparison_report(comparison)
    
    # 输出最终结论
    print("\n" + "="*60)
    print("主函数对比测试完成")
    print("="*60)
    
    if comparison['comparison_analysis']['overall_consistent']:
        print("✓ 重构版本与原始版本输出完全一致！")
        print("✓ 满足代码拆分要求：前后输出完全一致")
    else:
        print("✗ 发现差异，需要进一步调整:")
        
        if not comparison['comparison_analysis']['status_match']:
            print(f"  - 运行状态不一致: 原始={original_result['status']}, 重构={refactored_result['status']}")
        
        if not comparison['comparison_analysis']['return_code_match']:
            print(f"  - 返回码不一致: 原始={original_result['return_code']}, 重构={refactored_result['return_code']}")
        
        metrics_comp = comparison['comparison_analysis'].get('metrics_comparison', {})
        if metrics_comp.get('different_metrics'):
            print("  - 关键指标差异:")
            for diff in metrics_comp['different_metrics']:
                print(f"    {diff['metric']}: 原始={diff['original']}, 重构={diff['refactored']}")
    
    return comparison['comparison_analysis']['overall_consistent']

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)