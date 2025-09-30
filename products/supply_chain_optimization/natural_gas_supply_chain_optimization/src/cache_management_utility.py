"""
Cache Management Utility
缓存管理工具 - 提供缓存清理、状态查看等功能
支持地理数据缓存、路径规划缓存和性能监控
"""

import os
import logging
from typing import Optional
from data_cache_manager import cache_manager

# 尝试导入新的缓存组件
try:
    from unified_cache_configuration import UnifiedCacheConfiguration
    from pipeline_route_cache_manager import PipelineRouteCacheManager
    from cache_performance_monitor import performance_monitor
    from graphhopper_routing_engine import GraphHopperDistanceCalculator
    from hydrogen_pipeline_distance_calculator import HydrogenPipelineDistanceCalculator
    ADVANCED_CACHE_AVAILABLE = True
except ImportError as e:
    logging.warning(f"部分高级缓存组件不可用: {e}")
    ADVANCED_CACHE_AVAILABLE = False

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CacheManagementUtility:
    """
    缓存管理工具类
    """
    
    def __init__(self):
        self.cache_manager = cache_manager
    
    def show_cache_status(self):
        """显示缓存状态"""
        print("=" * 60)
        print("缓存状态报告")
        print("=" * 60)
        
        cache_info = self.cache_manager.get_cache_info()
        
        for data_type, info in cache_info.items():
            print(f"\n[{data_type.upper()}]")
            print(f"  缓存文件存在: {'是' if info['cache_exists'] else '否'}")
            print(f"  元数据存在:   {'是' if info['metadata_exists'] else '否'}")
            
            if info.get('record_count') is not None:
                print(f"  数据条数:     {info['record_count']:,}")
            if info.get('file_size') is not None:
                file_size_kb = info['file_size'] / 1024
                print(f"  文件大小:     {file_size_kb:.1f} KB")
            if info.get('created_at'):
                print(f"  创建时间:     {info['created_at']}")
            if info.get('source_file'):
                print(f"  源文件:       {os.path.basename(info['source_file'])}")
            if info.get('filtered_count') is not None:
                print(f"  过滤后数量:   {info['filtered_count']:,}")
        
        print("\n" + "=" * 60)
    
    def clear_cache(self, data_type: Optional[str] = None):
        """
        清理缓存
        
        Args:
            data_type: 数据类型，如果为None则清理所有缓存
        """
        if data_type:
            print(f"清理 {data_type} 缓存...")
            self.cache_manager.clear_cache(data_type)
            print(f"{data_type} 缓存已清理")
        else:
            print("清理所有缓存...")
            self.cache_manager.clear_cache()
            print("所有缓存已清理")
    
    def validate_cache(self):
        """验证缓存有效性"""
        print("验证缓存有效性...")
        
        # 模拟检查源文件路径
        from natural_gas_optimization_model import get_project_base_dir
        
        base_dir = get_project_base_dir()
        source_files = {
            'lng_terminals': os.path.join(base_dir, "gis_data_scraper", "scraped_gis_data", "lng_terminals.csv"),
            'ng_pipelines': os.path.join(base_dir, "natural_gas_supply_chain_optimization", "data", "integrated_gas_pipeline_price_data_with_coords.csv"),
            'renewable_plants': 'temp_renewable_file'  # 可再生能源使用临时文件标识
        }
        
        for data_type, source_file in source_files.items():
            is_valid = self.cache_manager.is_cache_valid(data_type, source_file)
            status = "有效" if is_valid else "无效"
            print(f"  {data_type}: {status}")
        
        print("缓存验证完成")
    
    def rebuild_cache(self):
        """重建缓存（清理后会在下次使用时自动重建）"""
        print("重建缓存（清理现有缓存）...")
        self.clear_cache()
        print("缓存已清理，将在下次数据加载时自动重建")

    # ======= 高级缓存管理功能 =======

    def show_comprehensive_cache_status(self):
        """显示包含路径规划缓存在内的综合缓存状态"""
        print("=" * 80)
        print("综合缓存状态报告")
        print("=" * 80)

        if not ADVANCED_CACHE_AVAILABLE:
            print("⚠️  高级缓存组件不可用，仅显示基础缓存信息")
            self.show_cache_status()
            return

        # 显示基础地理数据缓存
        print("\n🗺️  地理数据缓存状态")
        print("-" * 50)
        basic_cache_info = self.cache_manager.get_cache_info()
        for data_type, info in basic_cache_info.items():
            print(f"\n[{data_type.upper()}]")
            print(f"  缓存文件存在: {'✅ 是' if info['cache_exists'] else '❌ 否'}")
            print(f"  元数据存在:   {'✅ 是' if info['metadata_exists'] else '❌ 否'}")

            if info.get('record_count') is not None:
                print(f"  数据条数:     {info['record_count']:,}")
            if info.get('file_size') is not None:
                file_size_kb = info['file_size'] / 1024
                print(f"  文件大小:     {file_size_kb:.1f} KB")
            if info.get('created_at'):
                print(f"  创建时间:     {info['created_at']}")

        # 显示路径规划缓存
        print(f"\n🛣️  路径规划缓存状态")
        print("-" * 50)
        path_planning_info = cache_manager.get_path_planning_cache_info()
        for cache_type, info in path_planning_info.items():
            print(f"\n[{cache_type.upper()}]")
            print(f"  缓存存在:     {'✅ 是' if info.get('cache_exists', False) else '❌ 否'}")
            print(f"  缓存类型:     {info.get('cache_type', 'Unknown')}")
            if info.get('route_count') is not None:
                print(f"  路径数量:     {info['route_count']:,}")
            if info.get('last_update'):
                print(f"  最后更新:     {info['last_update']}")
            if info.get('error'):
                print(f"  错误信息:     ❌ {info['error']}")

        # 显示缓存完整性验证
        print(f"\n🔍 缓存完整性验证")
        print("-" * 50)
        validation_result = cache_manager.validate_path_planning_cache_integrity()
        status_emoji = {
            'healthy': '✅',
            'warning': '⚠️',
            'error': '❌'
        }
        print(f"整体状态: {status_emoji.get(validation_result['overall_status'], '❓')} {validation_result['overall_status']}")

        for cache_type, status_info in validation_result['cache_files_status'].items():
            status = status_info.get('status', 'unknown')
            print(f"  {cache_type}: {status}")

        if validation_result['recommendations']:
            print("\n💡 建议:")
            for recommendation in validation_result['recommendations']:
                print(f"  • {recommendation}")

        print("\n" + "=" * 80)

    def show_performance_monitoring_status(self):
        """显示性能监控状态"""
        print("=" * 60)
        print("性能监控状态")
        print("=" * 60)

        if not ADVANCED_CACHE_AVAILABLE:
            print("❌ 性能监控组件不可用")
            return

        try:
            monitor_status = performance_monitor.get_monitor_status()

            print(f"监控状态:         {'🟢 运行中' if monitor_status['monitoring_active'] else '🔴 已停止'}")
            print(f"实时指标数量:     {monitor_status['realtime_metrics_count']:,}")
            print(f"数据库存在:       {'✅ 是' if monitor_status['database_exists'] else '❌ 否'}")
            print(f"数据库大小:       {monitor_status['database_size_mb']:.2f} MB")
            print(f"报告数量:         {monitor_status['reports_count']}")
            print(f"数据保留时间:     {monitor_status['retention_days']} 天")
            print(f"采样间隔:         {monitor_status['sampling_interval_seconds']} 秒")

            # 显示最近的性能总结
            print(f"\n📊 性能总结 (最近1小时)")
            print("-" * 40)
            summary = performance_monitor.generate_performance_summary("1h")
            print(f"总操作数:         {summary.total_operations}")
            print(f"平均响应时间:     {summary.average_response_time_ms:.2f} ms")
            print(f"最大响应时间:     {summary.max_response_time_ms:.2f} ms")
            print(f"平均命中率:       {summary.average_hit_rate_percent:.1f}%")
            print(f"错误计数:         {summary.error_count}")
            print(f"效率评分:         {summary.cache_efficiency_score:.1f}/100")

        except Exception as e:
            print(f"❌ 获取性能监控状态失败: {e}")

        print("=" * 60)

    def manage_graphhopper_cache(self):
        """管理GraphHopper缓存"""
        if not ADVANCED_CACHE_AVAILABLE:
            print("❌ GraphHopper缓存管理功能不可用")
            return

        while True:
            print("\n" + "=" * 50)
            print("GraphHopper 缓存管理")
            print("=" * 50)
            print("1. 查看缓存统计")
            print("2. 清理过期缓存")
            print("3. 优化缓存性能")
            print("4. 清空所有缓存")
            print("5. LRU清理")
            print("0. 返回主菜单")

            choice = input("\n请选择操作 (0-5): ").strip()

            if choice == '0':
                break
            elif choice == '1':
                try:
                    calculator = GraphHopperDistanceCalculator()
                    stats = calculator.get_enhanced_cache_statistics()
                    self._display_graphhopper_stats(stats)
                except Exception as e:
                    print(f"❌ 获取GraphHopper统计失败: {e}")

            elif choice == '2':
                try:
                    calculator = GraphHopperDistanceCalculator()
                    result = calculator.cleanup_expired_cache()
                    print(f"✅ 清理完成: 删除{result['removed_entries']}个过期条目，释放{result['space_freed_bytes']/1024:.1f}KB")
                except Exception as e:
                    print(f"❌ 清理过期缓存失败: {e}")

            elif choice == '3':
                try:
                    calculator = GraphHopperDistanceCalculator()
                    result = calculator.optimize_cache_performance()
                    print("✅ 优化完成:")
                    for optimization in result.get('optimizations_applied', []):
                        print(f"  • {optimization}")
                except Exception as e:
                    print(f"❌ 优化缓存性能失败: {e}")

            elif choice == '4':
                confirm = input("⚠️  确定要清空所有GraphHopper缓存吗? (y/N): ").strip().lower()
                if confirm == 'y':
                    try:
                        calculator = GraphHopperDistanceCalculator()
                        result = calculator.clear_all_cache()
                        print(f"✅ 缓存已清空: 删除{result['cleared_entries']}个条目，释放{result['freed_space_bytes']/1024:.1f}KB")
                    except Exception as e:
                        print(f"❌ 清空缓存失败: {e}")

            elif choice == '5':
                try:
                    max_entries = input("请输入最大缓存条目数 (默认10000): ").strip()
                    max_entries = int(max_entries) if max_entries else 10000

                    calculator = GraphHopperDistanceCalculator()
                    result = calculator.cleanup_lru_cache(max_entries)
                    print(f"✅ LRU清理完成: 删除{result['removed_entries']}个条目，释放{result['space_freed_bytes']/1024:.1f}KB")
                except Exception as e:
                    print(f"❌ LRU清理失败: {e}")
            else:
                print("无效选择，请重试")

    def manage_pipeline_cache(self):
        """管理管道路径缓存"""
        if not ADVANCED_CACHE_AVAILABLE:
            print("❌ 管道路径缓存管理功能不可用")
            return

        while True:
            print("\n" + "=" * 50)
            print("管道路径缓存管理")
            print("=" * 50)
            print("1. 查看缓存统计")
            print("2. 清理过期缓存")
            print("3. 优化缓存性能")
            print("4. 清空所有缓存")
            print("5. 验证数据源")
            print("0. 返回主菜单")

            choice = input("\n请选择操作 (0-5): ").strip()

            if choice == '0':
                break
            elif choice == '1':
                try:
                    calculator = HydrogenPipelineDistanceCalculator("dummy_path")
                    stats = calculator.get_cache_statistics()
                    self._display_pipeline_stats(stats)
                except Exception as e:
                    print(f"❌ 获取管道缓存统计失败: {e}")

            elif choice == '2':
                try:
                    calculator = HydrogenPipelineDistanceCalculator("dummy_path")
                    result = calculator.cleanup_expired_cache()
                    print(f"✅ 清理完成: {result}")
                except Exception as e:
                    print(f"❌ 清理过期缓存失败: {e}")

            elif choice == '3':
                try:
                    calculator = HydrogenPipelineDistanceCalculator("dummy_path")
                    result = calculator.optimize_cache_performance()
                    print(f"✅ 优化完成: {result}")
                except Exception as e:
                    print(f"❌ 优化缓存性能失败: {e}")

            elif choice == '4':
                confirm = input("⚠️  确定要清空所有管道缓存吗? (y/N): ").strip().lower()
                if confirm == 'y':
                    try:
                        calculator = HydrogenPipelineDistanceCalculator("dummy_path")
                        result = calculator.clear_cache()
                        print(f"✅ 缓存已清空: {result}")
                    except Exception as e:
                        print(f"❌ 清空缓存失败: {e}")

            elif choice == '5':
                try:
                    calculator = HydrogenPipelineDistanceCalculator("dummy_path")
                    result = calculator.validate_cache_data_sources()
                    self._display_validation_result(result)
                except Exception as e:
                    print(f"❌ 验证数据源失败: {e}")
            else:
                print("无效选择，请重试")

    def generate_performance_report(self):
        """生成性能报告"""
        if not ADVANCED_CACHE_AVAILABLE:
            print("❌ 性能报告功能不可用")
            return

        print("\n生成性能报告")
        print("-" * 30)

        # 选择时间期间
        print("选择时间期间:")
        print("1. 最近1小时")
        print("2. 最近24小时")
        print("3. 最近7天")

        period_choice = input("请选择时间期间 (1-3): ").strip()
        period_map = {'1': '1h', '2': '24h', '3': '7d'}
        time_period = period_map.get(period_choice, '1h')

        # 选择格式
        print("\n选择输出格式:")
        print("1. JSON格式")
        print("2. HTML格式")

        format_choice = input("请选择格式 (1-2): ").strip()
        output_format = 'html' if format_choice == '2' else 'json'

        try:
            report_file = performance_monitor.generate_detailed_report(time_period, output_format)
            print(f"✅ 性能报告已生成: {report_file}")
        except Exception as e:
            print(f"❌ 生成性能报告失败: {e}")

    def _display_graphhopper_stats(self, stats):
        """显示GraphHopper缓存统计"""
        print("\n📊 GraphHopper 缓存统计")
        print("-" * 40)

        basic = stats.get('basic_stats', {})
        print(f"总条目数:         {basic.get('total_entries', 0)}")
        print(f"活跃条目数:       {basic.get('active_entries', 0)}")
        print(f"过期条目数:       {basic.get('expired_entries', 0)}")
        print(f"总大小:           {basic.get('total_size_mb', 0):.2f} MB")
        print(f"平均访问次数:     {basic.get('avg_access_count', 0):.1f}")
        print(f"最大访问次数:     {basic.get('max_access_count', 0)}")

        efficiency = stats.get('cache_efficiency', {})
        print(f"\n🎯 缓存效率")
        print(f"命中率:           {efficiency.get('hit_rate_percent', 0):.1f}%")
        print(f"总请求数:         {efficiency.get('total_requests', 0)}")
        print(f"缓存命中数:       {efficiency.get('cache_hits', 0)}")
        print(f"节省时间:         {efficiency.get('total_time_saved_seconds', 0):.1f} 秒")

    def _display_pipeline_stats(self, stats):
        """显示管道缓存统计"""
        print("\n📊 管道缓存统计")
        print("-" * 40)

        basic = stats.get('basic_stats', {})
        print(f"总计算次数:       {basic.get('total_calculations', 0)}")
        print(f"缓存命中次数:     {basic.get('cache_hits', 0)}")
        print(f"成功路径数:       {basic.get('successful_routes', 0)}")
        print(f"失败路径数:       {basic.get('failed_routes', 0)}")
        print(f"缓存命中率:       {basic.get('cache_hit_rate', 0):.1f}%")

        pipeline_usage = stats.get('pipeline_usage', {})
        print(f"\n🛠️  管道类型使用统计")
        for pipeline_type, count in pipeline_usage.items():
            print(f"  {pipeline_type}: {count}")

    def _display_validation_result(self, result):
        """显示验证结果"""
        print("\n🔍 数据源验证结果")
        print("-" * 40)

        files = result.get('pipeline_data_files', {})
        for pipeline_type, file_info in files.items():
            exists = file_info.get('exists', False)
            size_mb = file_info.get('size_bytes', 0) / 1024 / 1024
            print(f"{pipeline_type}:")
            print(f"  文件存在: {'✅' if exists else '❌'}")
            print(f"  文件大小: {size_mb:.2f} MB")

        validation = result.get('cache_validation', {})
        if isinstance(validation, dict) and 'status' in validation:
            print(f"\n缓存验证状态: {validation['status']}")

    def clear_all_advanced_caches(self):
        """清理所有高级缓存"""
        if not ADVANCED_CACHE_AVAILABLE:
            print("❌ 高级缓存功能不可用")
            return

        confirm = input("⚠️  确定要清理所有高级缓存吗? 这将包括:\n"
                       "  • GraphHopper路径缓存\n"
                       "  • 管道路径缓存\n"
                       "  • 路径规划统计数据\n"
                       "  • 性能监控数据\n"
                       "继续? (y/N): ").strip().lower()

        if confirm != 'y':
            print("操作已取消")
            return

        results = []

        # 清理路径规划缓存
        try:
            result = cache_manager.clear_path_planning_cache()
            results.append(f"✅ 路径规划缓存: 清理{len(result['cleared_files'])}个文件，释放{result['total_freed_space_mb']:.2f}MB")
        except Exception as e:
            results.append(f"❌ 路径规划缓存清理失败: {e}")

        # 清理GraphHopper缓存
        try:
            calculator = GraphHopperDistanceCalculator()
            result = calculator.clear_all_cache()
            results.append(f"✅ GraphHopper缓存: 清理{result['cleared_entries']}个条目，释放{result['freed_space_bytes']/1024:.1f}KB")
        except Exception as e:
            results.append(f"❌ GraphHopper缓存清理失败: {e}")

        # 清理管道缓存
        try:
            calculator = HydrogenPipelineDistanceCalculator("dummy_path")
            result = calculator.clear_cache()
            results.append("✅ 管道缓存已清理")
        except Exception as e:
            results.append(f"❌ 管道缓存清理失败: {e}")

        # 清理性能监控数据
        try:
            performance_monitor.cleanup_old_metrics()
            results.append("✅ 性能监控数据已清理")
        except Exception as e:
            results.append(f"❌ 性能监控数据清理失败: {e}")

        print("\n高级缓存清理结果:")
        for result in results:
            print(f"  {result}")

        print("✅ 高级缓存清理完成")

def main():
    """主函数 - 增强的命令行界面"""
    utility = CacheManagementUtility()

    while True:
        print("\n" + "🗂️  " + "缓存管理工具" + " 🗂️")
        print("=" * 60)

        # 基础功能
        print("\n📊 基础缓存管理:")
        print("1. 查看基础缓存状态")
        print("2. 验证缓存有效性")
        print("3. 清理所有基础缓存")
        print("4. 清理特定基础缓存")
        print("5. 重建基础缓存")

        # 高级功能 - 仅在可用时显示
        if ADVANCED_CACHE_AVAILABLE:
            print("\n🚀 高级缓存管理:")
            print("6. 查看综合缓存状态")
            print("7. 性能监控状态")
            print("8. 管理GraphHopper缓存")
            print("9. 管理管道路径缓存")
            print("10. 生成性能报告")
            print("11. 清理所有高级缓存")
        else:
            print("\n⚠️  高级缓存功能不可用 (缺少组件)")

        print("\n0. 退出")
        print("=" * 60)

        max_choice = 11 if ADVANCED_CACHE_AVAILABLE else 5
        choice = input(f"\n请选择操作 (0-{max_choice}): ").strip()

        # 基础功能处理
        if choice == '0':
            print("👋 退出缓存管理工具")
            break
        elif choice == '1':
            utility.show_cache_status()
        elif choice == '2':
            utility.validate_cache()
        elif choice == '3':
            confirm = input("⚠️  确定要清理所有基础缓存吗? (y/N): ").strip().lower()
            if confirm == 'y':
                utility.clear_cache()
        elif choice == '4':
            print("\n可选的基础缓存数据类型:")
            print("  lng_terminals    - LNG接收站数据")
            print("  ng_pipelines     - 天然气管道数据")
            print("  renewable_plants - 可再生能源电站数据")

            data_type = input("\n请输入数据类型: ").strip()
            if data_type in ['lng_terminals', 'ng_pipelines', 'renewable_plants']:
                confirm = input(f"确定要清理 {data_type} 缓存吗? (y/N): ").strip().lower()
                if confirm == 'y':
                    utility.clear_cache(data_type)
            else:
                print("❌ 无效的数据类型")
        elif choice == '5':
            confirm = input("⚠️  确定要重建基础缓存吗? (y/N): ").strip().lower()
            if confirm == 'y':
                utility.rebuild_cache()

        # 高级功能处理
        elif ADVANCED_CACHE_AVAILABLE:
            if choice == '6':
                utility.show_comprehensive_cache_status()
            elif choice == '7':
                utility.show_performance_monitoring_status()
            elif choice == '8':
                utility.manage_graphhopper_cache()
            elif choice == '9':
                utility.manage_pipeline_cache()
            elif choice == '10':
                utility.generate_performance_report()
            elif choice == '11':
                utility.clear_all_advanced_caches()
            else:
                print("❌ 无效的选择，请重试")
        else:
            if choice in ['6', '7', '8', '9', '10', '11']:
                print("❌ 高级缓存功能不可用，请检查组件安装")
            else:
                print("❌ 无效的选择，请重试")

if __name__ == "__main__":
    main()