"""
Cache Management Utility
缓存管理工具 - 提供缓存清理、状态查看等功能
"""

import os
import logging
from typing import Optional
from data_cache_manager import cache_manager

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

def main():
    """主函数 - 命令行界面"""
    utility = CacheManagementUtility()
    
    while True:
        print("\n缓存管理工具")
        print("=" * 40)
        print("1. 查看缓存状态")
        print("2. 验证缓存有效性")
        print("3. 清理所有缓存")
        print("4. 清理特定缓存")
        print("5. 重建缓存")
        print("0. 退出")
        
        choice = input("\n请选择操作 (0-5): ").strip()
        
        if choice == '0':
            print("退出缓存管理工具")
            break
        elif choice == '1':
            utility.show_cache_status()
        elif choice == '2':
            utility.validate_cache()
        elif choice == '3':
            confirm = input("确定要清理所有缓存吗? (y/N): ").strip().lower()
            if confirm == 'y':
                utility.clear_cache()
        elif choice == '4':
            print("\n可选的数据类型:")
            print("  lng_terminals  - LNG接收站")
            print("  ng_pipelines   - 天然气管道")
            print("  renewable_plants - 可再生能源电站")
            
            data_type = input("\n请输入数据类型: ").strip()
            if data_type in ['lng_terminals', 'ng_pipelines', 'renewable_plants']:
                confirm = input(f"确定要清理 {data_type} 缓存吗? (y/N): ").strip().lower()
                if confirm == 'y':
                    utility.clear_cache(data_type)
            else:
                print("无效的数据类型")
        elif choice == '5':
            confirm = input("确定要重建缓存吗? (y/N): ").strip().lower()
            if confirm == 'y':
                utility.rebuild_cache()
        else:
            print("无效的选择，请重试")

if __name__ == "__main__":
    main()