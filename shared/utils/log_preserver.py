"""
简单的日志挂载模块
用于替代原有的log_preserver模块
"""

import logging
import os
from datetime import datetime

def mount_file_logging(log_dir: str, filename_prefix: str = "optimizer", log_level: int = logging.INFO):
    """
    挂载文件日志记录

    Args:
        log_dir: 日志目录路径
        filename_prefix: 日志文件前缀
        log_level: 日志级别
    """
    try:
        # 创建日志目录
        os.makedirs(log_dir, exist_ok=True)

        # 创建日志文件名
        log_filename = f"{filename_prefix}_{datetime.now().strftime('%Y%m%d')}.log"
        log_path = os.path.join(log_dir, log_filename)
        
        # 配置日志格式
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        
        # 添加文件处理器
        file_handler = logging.FileHandler(log_path, encoding='utf-8')
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        
        # 获取根日志记录器
        root_logger = logging.getLogger()
        root_logger.addHandler(file_handler)
        
        if root_logger.level > log_level:
            root_logger.setLevel(log_level)
            
        return log_path
        
    except Exception as e:
        # 静默失败，不影响主流程
        print(f"Warning: 无法挂载文件日志: {e}")
        return None