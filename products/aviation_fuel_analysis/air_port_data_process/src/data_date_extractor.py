"""
数据日期提取器
从原始航班数据中提取实际的日期信息，用于燃油价格计算
"""

import pandas as pd
import os
from datetime import datetime
from typing import List, Dict, Set
import logging

logger = logging.getLogger(__name__)

class DataDateExtractor:
    """数据日期提取器"""
    
    def __init__(self, data_dir=None):
        """
        初始化数据日期提取器
        
        Args:
            data_dir: 数据目录路径
        """
        if data_dir is None:
            # 获取当前脚本所在目录
            base_dir = os.path.dirname(os.path.abspath(__file__))
            data_dir = os.path.join(base_dir, '../data')
        
        self.data_dir = data_dir
        
        # 🔧 智能选择数据文件：优先使用2024年数据文件
        data_file_2024 = os.path.join(data_dir, '2024年航班数据.xlsx')
        data_file_full = os.path.join(data_dir, '22年1月1日至24年12月31日航班数据.xlsx')
        
        if os.path.exists(data_file_2024):
            self.data_file_path = data_file_2024
            self.is_2024_only = True
            logger.info(f"✅ 使用2024年数据文件: {os.path.basename(data_file_2024)}")
        elif os.path.exists(data_file_full):
            self.data_file_path = data_file_full
            self.is_2024_only = False
            logger.info(f"⚠️ 使用完整数据文件: {os.path.basename(data_file_full)}")
        else:
            # 默认使用完整数据文件路径（即使不存在）
            self.data_file_path = data_file_full
            self.is_2024_only = False
            logger.warning(f"❌ 数据文件不存在，使用默认路径: {os.path.basename(data_file_full)}")
        
        # 🔧 直接初始化月份信息，避免复杂的数据读取
        if self.is_2024_only:
            # 2024年数据文件包含2024年1-12月
            self.available_months = set([f"2024-{month:02d}" for month in range(1, 13)])
            self.date_range = (datetime(2024, 1, 1), datetime(2024, 12, 31))
            logger.info("✅ 2024年数据文件：直接设置2024年1-12月可用")
        else:
            # 完整数据文件包含2022-2024年
            self.available_months = set()
            for year in [2022, 2023, 2024]:
                for month in range(1, 13):
                    self.available_months.add(f"{year}-{month:02d}")
            self.date_range = (datetime(2022, 1, 1), datetime(2024, 12, 31))
            logger.info("✅ 完整数据文件：直接设置2022-2024年可用")
        
        logger.info(f"数据日期提取器初始化完成，可用月份数: {len(self.available_months)}")
    
    def extract_available_dates(self, sample_size=100000):
        """
        从原始数据中提取可用的日期信息
        简化版：直接返回预设的日期信息，避免复杂的数据读取
        
        Args:
            sample_size: 基础采样大小（保留参数兼容性）
        
        Returns:
            Dict: 包含可用日期信息的字典
        """
        logger.info(f"返回预设的日期信息（基于数据文件类型）")
        
        if self.is_2024_only:
            # 2024年数据文件
            available_months = [f"2024-{month:02d}" for month in range(1, 13)]
            return {
                'available_months': available_months,
                'date_range': (datetime(2024, 1, 1), datetime(2024, 12, 31)),
                'min_date': datetime(2024, 1, 1),
                'max_date': datetime(2024, 12, 31),
                'latest_month': '2024-12',
                'earliest_month': '2024-01'
            }
        else:
            # 完整数据文件
            available_months = []
            for year in [2022, 2023, 2024]:
                for month in range(1, 13):
                    available_months.append(f"{year}-{month:02d}")
            
            return {
                'available_months': available_months,
                'date_range': (datetime(2022, 1, 1), datetime(2024, 12, 31)),
                'min_date': datetime(2022, 1, 1),
                'max_date': datetime(2024, 12, 31),
                'latest_month': '2024-12',
                'earliest_month': '2022-01'
            }
    
    def _get_default_date_info(self):
        """
        获取默认的日期信息（当无法从数据中提取时使用）
        
        Returns:
            Dict: 默认日期信息
        """
        # 🔧 根据数据文件类型推断的日期范围
        if self.is_2024_only:
            # 2024年数据文件：只包含2024年数据
            default_months = []
            for month in range(1, 13):
                default_months.append(f"2024-{month:02d}")
            
            return {
                'available_months': default_months,
                'date_range': (datetime(2024, 1, 1), datetime(2024, 12, 31)),
                'min_date': datetime(2024, 1, 1),
                'max_date': datetime(2024, 12, 31),
                'latest_month': '2024-12',
                'earliest_month': '2024-01'
            }
        else:
            # 完整数据文件：包含2022-2024年数据
            default_months = []
            for year in [2022, 2023, 2024]:
                for month in range(1, 13):
                    default_months.append(f"{year}-{month:02d}")
            
            return {
                'available_months': default_months,
                'date_range': (datetime(2022, 1, 1), datetime(2024, 12, 31)),
                'min_date': datetime(2022, 1, 1),
                'max_date': datetime(2024, 12, 31),
                'latest_month': '2024-12',
                'earliest_month': '2022-01'
            }
    
    def get_current_month_from_data(self):
        """
        从数据中获取当前应该使用的月份
        
        Returns:
            str: 当前月份 (格式: 'YYYY-MM')
        """
        if self.is_2024_only:
            return '2024-12'
        else:
            return '2024-12'
    
    def is_month_available(self, year_month: str) -> bool:
        """
        检查指定月份是否在数据中可用
        
        Args:
            year_month: 年月字符串 (格式: 'YYYY-MM')
            
        Returns:
            bool: 是否可用
        """
        return year_month in self.available_months
    
    def get_closest_available_month(self, target_month: str) -> str:
        """
        获取最接近目标月份的可用月份
        
        Args:
            target_month: 目标月份 (格式: 'YYYY-MM')
            
        Returns:
            str: 最接近的可用月份
        """
        if target_month in self.available_months:
            return target_month
        
        # 如果目标月份不可用，返回最新的可用月份
        if self.is_2024_only:
            return '2024-12'
        else:
            return '2024-12'
    
    def get_monthly_data_sample(self, year_month: str, sample_size=1000):
        """
        获取指定月份的数据样本
        
        Args:
            year_month: 年月字符串 (格式: 'YYYY-MM')
            sample_size: 样本大小
            
        Returns:
            DataFrame: 指定月份的数据样本
        """
        try:
            if not os.path.exists(self.data_file_path):
                logger.warning(f"数据文件不存在: {self.data_file_path}")
                return pd.DataFrame()
            
            # 读取数据
            df = pd.read_excel(self.data_file_path, nrows=sample_size * 5)  # 读取更多数据以便筛选
            
            # 查找日期列
            date_columns = [col for col in df.columns if '日期' in col]
            
            if not date_columns:
                logger.warning("未找到日期列")
                return df.head(sample_size)
            
            date_col = date_columns[0]
            
            # 转换日期格式
            df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
            
            # 筛选指定月份的数据
            target_year, target_month = year_month.split('-')
            target_year = int(target_year)
            target_month = int(target_month)
            
            monthly_data = df[
                (df[date_col].dt.year == target_year) & 
                (df[date_col].dt.month == target_month)
            ]
            
            if len(monthly_data) == 0:
                logger.warning(f"未找到 {year_month} 的数据")
                return df.head(sample_size)
            
            return monthly_data.head(sample_size)
            
        except Exception as e:
            logger.error(f"获取月度数据样本时出错: {str(e)}")
            return pd.DataFrame()


def main():
    """测试数据日期提取器"""
    extractor = DataDateExtractor()
    
    print("🧪 测试数据日期提取器")
    print("=" * 50)
    
    # 提取可用日期
    date_info = extractor.extract_available_dates()
    
    print(f"可用月份数量: {len(date_info['available_months'])}")
    print(f"日期范围: {date_info['min_date'].strftime('%Y-%m-%d')} 至 {date_info['max_date'].strftime('%Y-%m-%d')}")
    print(f"最早月份: {date_info['earliest_month']}")
    print(f"最新月份: {date_info['latest_month']}")
    
    # 测试月份检查
    test_months = ['2024-12', '2024-11', '2022-01', '2023-06']
    for month in test_months:
        available = extractor.is_month_available(month)
        closest = extractor.get_closest_available_month(month)
        print(f"月份 {month}: 可用={available}, 最近可用月份={closest}")


if __name__ == "__main__":
    main() 