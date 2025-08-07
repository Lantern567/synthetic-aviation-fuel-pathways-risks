"""
测试运行脚本
运行所有的单元测试并生成测试报告
"""
import unittest
import sys
import os
from datetime import datetime

# 添加src目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

def run_specific_tests():
    """运行特定的核心模块测试"""
    test_files = [
        'test_aircraft_mapping.py',
        'test_extract_departure_airport_info.py',
        'test_visualize_departure_airports.py',
    ]
    
    print("=" * 80)
    print(f"运行核心模块测试 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    for test_file in test_files:
        if os.path.exists(test_file):
            try:
                # 导入测试模块
                module_name = test_file.replace('.py', '')
                module = __import__(module_name)
                
                # 添加测试到套件
                suite.addTests(loader.loadTestsFromModule(module))
                print(f"✓ 加载测试文件: {test_file}")
            except Exception as e:
                print(f"✗ 加载测试文件失败: {test_file} - {e}")
    
    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # 输出测试结果
    print("\n" + "=" * 80)
    print("测试结果总结:")
    print("=" * 80)
    print(f"运行测试数量: {result.testsRun}")
    print(f"失败测试数量: {len(result.failures)}")
    print(f"错误测试数量: {len(result.errors)}")
    
    if result.failures:
        print("\n失败的测试:")
        for test, traceback in result.failures:
            print(f"  - {test}: {traceback}")
    
    if result.errors:
        print("\n错误的测试:")
        for test, traceback in result.errors:
            print(f"  - {test}: {traceback}")
    
    success_rate = (result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100
    print(f"\n测试成功率: {success_rate:.1f}%")
    
    return result.wasSuccessful()

def check_import_health():
    """检查核心模块的导入健康状态"""
    print("\n" + "=" * 80)
    print("检查核心模块导入状态")
    print("=" * 80)
    
    modules_to_check = [
        'aircraft_mapping',
        'extract_departure_airport_info',
        'visualize_departure_airports',
    ]
    
    import_results = {}
    
    for module_name in modules_to_check:
        try:
            __import__(module_name)
            print(f"✓ {module_name} - 导入成功")
            import_results[module_name] = True
        except Exception as e:
            print(f"✗ {module_name} - 导入失败: {e}")
            import_results[module_name] = False
    
    healthy_count = sum(import_results.values())
    total_count = len(import_results)
    
    print(f"\n模块健康状态: {healthy_count}/{total_count} ({healthy_count/total_count*100:.1f}%)")
    
    return all(import_results.values())

if __name__ == '__main__':
    print("绿色甲醇港口运输 - 航空港数据处理模块测试")
    print("=" * 80)
    
    # 检查模块导入状态
    imports_healthy = check_import_health()
    
    if imports_healthy:
        # 运行测试
        tests_passed = run_specific_tests()
        
        if tests_passed:
            print("\n🎉 所有测试通过!")
            sys.exit(0)
        else:
            print("\n❌ 部分测试失败!")
            sys.exit(1)
    else:
        print("\n❌ 模块导入检查失败!")
        sys.exit(1) 