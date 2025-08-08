"""
Data Cache Manager for 500km Filtered Geographic Data
用于管理500km过滤地理数据的缓存管理器
"""

import os
import json
import pandas as pd
import logging
from typing import Dict, Optional, List
from datetime import datetime, timedelta
import hashlib

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DataCacheManager:
    """
    数据缓存管理器 - 管理500km过滤后的地理数据缓存
    """
    
    def __init__(self, cache_base_dir: str = "cache", cache_expiry_hours: int = 24):
        """
        初始化缓存管理器
        
        Args:
            cache_base_dir: 缓存根目录
            cache_expiry_hours: 缓存过期时间(小时)
        """
        self.cache_base_dir = cache_base_dir
        self.cache_expiry_hours = cache_expiry_hours
        
        # 创建缓存目录结构
        self.filtered_data_dir = os.path.join(cache_base_dir, "filtered_500km_data")
        self.metadata_dir = os.path.join(cache_base_dir, "cache_metadata")
        
        os.makedirs(self.filtered_data_dir, exist_ok=True)
        os.makedirs(self.metadata_dir, exist_ok=True)
        
        # 缓存文件路径
        self.cache_files = {
            'lng_terminals': os.path.join(self.filtered_data_dir, 'lng_terminals_500km.csv'),
            'ng_pipelines': os.path.join(self.filtered_data_dir, 'ng_pipelines_500km.csv'),
            'renewable_plants': os.path.join(self.filtered_data_dir, 'renewable_plants_500km.csv')
        }
        
        # 元数据文件路径
        self.metadata_files = {
            'lng_terminals': os.path.join(self.metadata_dir, 'lng_terminals_metadata.json'),
            'ng_pipelines': os.path.join(self.metadata_dir, 'ng_pipelines_metadata.json'),
            'renewable_plants': os.path.join(self.metadata_dir, 'renewable_plants_metadata.json')
        }
        
        logger.info(f"缓存管理器初始化完成，缓存目录: {self.filtered_data_dir}")
    
    def _generate_file_hash(self, file_path: str) -> str:
        """
        生成文件内容的哈希值
        
        Args:
            file_path: 文件路径
            
        Returns:
            文件内容的MD5哈希值
        """
        if not os.path.exists(file_path):
            return ""
            
        try:
            hasher = hashlib.md5()
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hasher.update(chunk)
            return hasher.hexdigest()
        except Exception as e:
            logger.warning(f"计算文件哈希失败 {file_path}: {e}")
            return ""
    
    def _save_cache_metadata(self, data_type: str, source_file: str, filtered_count: int):
        """
        保存缓存元数据
        
        Args:
            data_type: 数据类型 ('lng_terminals', 'ng_pipelines', 'renewable_plants')
            source_file: 源文件路径
            filtered_count: 过滤后的数据条数
        """
        metadata = {
            'created_at': datetime.now().isoformat(),
            'source_file': source_file,
            'source_file_hash': self._generate_file_hash(source_file),
            'filtered_count': filtered_count,
            'filter_criteria': '500km radius from Beijing (39.9042, 116.4074)',
            'cache_version': '1.0'
        }
        
        try:
            with open(self.metadata_files[data_type], 'w', encoding='utf-8') as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)
            logger.info(f"缓存元数据已保存: {data_type}")
        except Exception as e:
            logger.error(f"保存缓存元数据失败 {data_type}: {e}")
    
    def _load_cache_metadata(self, data_type: str) -> Optional[Dict]:
        """
        加载缓存元数据
        
        Args:
            data_type: 数据类型
            
        Returns:
            缓存元数据字典，如果不存在或无效返回None
        """
        metadata_file = self.metadata_files[data_type]
        if not os.path.exists(metadata_file):
            return None
            
        try:
            with open(metadata_file, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
            return metadata
        except Exception as e:
            logger.warning(f"加载缓存元数据失败 {data_type}: {e}")
            return None
    
    def is_cache_valid(self, data_type: str, source_file: str) -> bool:
        """
        检查缓存是否有效
        
        Args:
            data_type: 数据类型
            source_file: 源文件路径
            
        Returns:
            缓存是否有效
        """
        # 检查缓存文件是否存在
        cache_file = self.cache_files[data_type]
        if not os.path.exists(cache_file):
            logger.debug(f"缓存文件不存在: {cache_file}")
            return False
        
        # 检查元数据
        metadata = self._load_cache_metadata(data_type)
        if not metadata:
            logger.debug(f"缓存元数据不存在: {data_type}")
            return False
        
        # 检查缓存是否过期
        created_at = datetime.fromisoformat(metadata['created_at'])
        expiry_time = created_at + timedelta(hours=self.cache_expiry_hours)
        if datetime.now() > expiry_time:
            logger.info(f"缓存已过期: {data_type} (创建时间: {created_at})")
            return False
        
        # 检查源文件是否变更
        current_hash = self._generate_file_hash(source_file)
        cached_hash = metadata.get('source_file_hash', '')
        if current_hash != cached_hash:
            logger.info(f"源文件已变更: {data_type}")
            return False
        
        logger.debug(f"缓存有效: {data_type}")
        return True
    
    def save_filtered_data(self, data_type: str, filtered_df: pd.DataFrame, source_file: str):
        """
        保存过滤后的数据到缓存
        
        Args:
            data_type: 数据类型
            filtered_df: 过滤后的DataFrame
            source_file: 源文件路径
        """
        try:
            cache_file = self.cache_files[data_type]
            filtered_df.to_csv(cache_file, index=False, encoding='utf-8')
            
            # 保存元数据
            self._save_cache_metadata(data_type, source_file, len(filtered_df))
            
            logger.info(f"过滤数据已缓存: {data_type} ({len(filtered_df)} 条记录)")
        except Exception as e:
            logger.error(f"保存过滤数据失败 {data_type}: {e}")
    
    def load_filtered_data(self, data_type: str) -> Optional[pd.DataFrame]:
        """
        从缓存加载过滤后的数据
        
        Args:
            data_type: 数据类型
            
        Returns:
            过滤后的DataFrame，如果缓存不存在或无效返回None
        """
        cache_file = self.cache_files[data_type]
        if not os.path.exists(cache_file):
            return None
        
        try:
            df = pd.read_csv(cache_file, encoding='utf-8')
            logger.info(f"从缓存加载数据: {data_type} ({len(df)} 条记录)")
            return df
        except Exception as e:
            logger.error(f"从缓存加载数据失败 {data_type}: {e}")
            return None
    
    def clear_cache(self, data_type: str = None):
        """
        清理缓存
        
        Args:
            data_type: 数据类型，如果为None则清理所有缓存
        """
        if data_type:
            data_types = [data_type]
        else:
            data_types = list(self.cache_files.keys())
        
        for dt in data_types:
            # 删除缓存文件
            cache_file = self.cache_files[dt]
            if os.path.exists(cache_file):
                try:
                    os.remove(cache_file)
                    logger.info(f"已删除缓存文件: {cache_file}")
                except Exception as e:
                    logger.error(f"删除缓存文件失败 {cache_file}: {e}")
            
            # 删除元数据文件
            metadata_file = self.metadata_files[dt]
            if os.path.exists(metadata_file):
                try:
                    os.remove(metadata_file)
                    logger.info(f"已删除元数据文件: {metadata_file}")
                except Exception as e:
                    logger.error(f"删除元数据文件失败 {metadata_file}: {e}")
    
    def get_cache_info(self) -> Dict:
        """
        获取缓存信息
        
        Returns:
            缓存信息字典
        """
        cache_info = {}
        
        for data_type in self.cache_files.keys():
            cache_file = self.cache_files[data_type]
            metadata = self._load_cache_metadata(data_type)
            
            info = {
                'cache_exists': os.path.exists(cache_file),
                'metadata_exists': metadata is not None
            }
            
            if info['cache_exists']:
                try:
                    df = pd.read_csv(cache_file)
                    info['record_count'] = len(df)
                    info['file_size'] = os.path.getsize(cache_file)
                except:
                    info['record_count'] = 0
                    info['file_size'] = 0
            
            if metadata:
                info['created_at'] = metadata.get('created_at')
                info['source_file'] = metadata.get('source_file')
                info['filtered_count'] = metadata.get('filtered_count')
            
            cache_info[data_type] = info
        
        return cache_info

# 全局缓存管理器实例
cache_manager = DataCacheManager()