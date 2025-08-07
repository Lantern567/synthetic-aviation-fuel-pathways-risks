"""
数据处理模式示例 - 基于绿色甲醇项目的标准数据处理流程

这个文件展示了项目中标准的数据处理模式，包括：
- 数据读取和预处理
- 错误处理和日志记录
- 数据验证和清理
- 结果输出和保存
"""

import logging
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path
import sys
import os
from datetime import datetime
from dataclasses import dataclass

# =============================================================================
# 1. 日志配置模式
# =============================================================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# =============================================================================
# 2. 数据类定义模式
# =============================================================================
@dataclass
class ProcessingResult:
    """数据处理结果的标准结构"""
    success: bool
    data: Optional[pd.DataFrame]
    message: str
    metadata: Dict[str, Any]
    timestamp: str


# =============================================================================
# 3. 可选依赖导入模式
# =============================================================================
# 优雅地处理可选依赖
try:
    import some_optional_library
    OPTIONAL_LIB_AVAILABLE = True
    logger.info("✅ 可选库导入成功")
except ImportError as e:
    OPTIONAL_LIB_AVAILABLE = False
    logger.warning(f"⚠️ 可选库不可用: {e}")

# =============================================================================
# 4. 数据读取模式
# =============================================================================
def read_data_with_validation(file_path: str, 
                             required_columns: List[str] = None,
                             **kwargs) -> ProcessingResult:
    """
    标准数据读取模式，包含完整的错误处理和验证
    
    Args:
        file_path: 数据文件路径
        required_columns: 必需的列名列表
        **kwargs: 传递给pandas读取函数的额外参数
        
    Returns:
        ProcessingResult: 标准化的处理结果
    """
    try:
        # 路径验证
        if not Path(file_path).exists():
            return ProcessingResult(
                success=False,
                data=None,
                message=f"文件不存在: {file_path}",
                metadata={},
                timestamp=datetime.now().isoformat()
            )
        
        # 根据文件扩展名选择读取方法
        file_ext = Path(file_path).suffix.lower()
        
        if file_ext == '.csv':
            df = pd.read_csv(file_path, **kwargs)
        elif file_ext in ['.xlsx', '.xls']:
            df = pd.read_excel(file_path, **kwargs)
        else:
            return ProcessingResult(
                success=False,
                data=None,
                message=f"不支持的文件格式: {file_ext}",
                metadata={},
                timestamp=datetime.now().isoformat()
            )
        
        # 数据基本验证
        if df.empty:
            return ProcessingResult(
                success=False,
                data=None,
                message="读取的数据为空",
                metadata={},
                timestamp=datetime.now().isoformat()
            )
        
        # 列名验证
        if required_columns:
            missing_cols = set(required_columns) - set(df.columns)
            if missing_cols:
                return ProcessingResult(
                    success=False,
                    data=None,
                    message=f"缺少必需的列: {missing_cols}",
                    metadata={"available_columns": list(df.columns)},
                    timestamp=datetime.now().isoformat()
                )
        
        logger.info(f"✅ 成功读取数据: {df.shape[0]}行, {df.shape[1]}列")
        
        return ProcessingResult(
            success=True,
            data=df,
            message=f"成功读取 {df.shape[0]} 行数据",
            metadata={
                "shape": df.shape,
                "columns": list(df.columns),
                "dtypes": df.dtypes.to_dict()
            },
            timestamp=datetime.now().isoformat()
        )
        
    except Exception as e:
        logger.error(f"❌ 数据读取失败: {e}")
        return ProcessingResult(
            success=False,
            data=None,
            message=f"数据读取错误: {str(e)}",
            metadata={"error_type": type(e).__name__},
            timestamp=datetime.now().isoformat()
        )

# =============================================================================
# 5. 数据清理和预处理模式
# =============================================================================
def clean_and_preprocess(df: pd.DataFrame, 
                        config: Dict[str, Any] = None) -> ProcessingResult:
    """
    标准数据清理和预处理流程
    
    Args:
        df: 原始数据框
        config: 清理配置参数
        
    Returns:
        ProcessingResult: 处理后的结果
    """
    try:
        if config is None:
            config = {}
        
        original_shape = df.shape
        cleaned_df = df.copy()
        
        # 1. 删除重复行
        if config.get('remove_duplicates', True):
            duplicates_before = cleaned_df.duplicated().sum()
            cleaned_df = cleaned_df.drop_duplicates()
            if duplicates_before > 0:
                logger.info(f"删除 {duplicates_before} 行重复数据")
        
        # 2. 处理缺失值
        missing_strategy = config.get('missing_strategy', 'drop')
        if missing_strategy == 'drop':
            missing_before = cleaned_df.isnull().sum().sum()
            cleaned_df = cleaned_df.dropna()
            if missing_before > 0:
                logger.info(f"删除包含缺失值的行，共 {missing_before} 个缺失值")
        elif missing_strategy == 'fill':
            fill_values = config.get('fill_values', {})
            cleaned_df = cleaned_df.fillna(fill_values)
        
        # 3. 数据类型转换
        dtype_mappings = config.get('dtype_mappings', {})
        for col, dtype in dtype_mappings.items():
            if col in cleaned_df.columns:
                try:
                    cleaned_df[col] = cleaned_df[col].astype(dtype)
                except Exception as e:
                    logger.warning(f"列 {col} 类型转换失败: {e}")
        
        # 4. 数值范围验证
        range_validations = config.get('range_validations', {})
        for col, (min_val, max_val) in range_validations.items():
            if col in cleaned_df.columns:
                mask = (cleaned_df[col] >= min_val) & (cleaned_df[col] <= max_val)
                invalid_count = (~mask).sum()
                if invalid_count > 0:
                    logger.warning(f"列 {col} 中有 {invalid_count} 个值超出范围 [{min_val}, {max_val}]")
                    cleaned_df = cleaned_df[mask]
        
        final_shape = cleaned_df.shape
        
        logger.info(f"✅ 数据清理完成: {original_shape} -> {final_shape}")
        
        return ProcessingResult(
            success=True,
            data=cleaned_df,
            message=f"数据清理完成，从 {original_shape[0]} 行减少到 {final_shape[0]} 行",
            metadata={
                "original_shape": original_shape,
                "final_shape": final_shape,
                "removed_rows": original_shape[0] - final_shape[0]
            },
            timestamp=datetime.now().isoformat()
        )
        
    except Exception as e:
        logger.error(f"❌ 数据清理失败: {e}")
        return ProcessingResult(
            success=False,
            data=None,
            message=f"数据清理错误: {str(e)}",
            metadata={"error_type": type(e).__name__},
            timestamp=datetime.now().isoformat()
        )

# =============================================================================
# 6. 结果保存模式
# =============================================================================
def save_results(df: pd.DataFrame, 
                output_dir: str,
                file_prefix: str = "result",
                formats: List[str] = ["csv", "xlsx"]) -> ProcessingResult:
    """
    标准结果保存模式，支持多种格式和时间戳
    
    Args:
        df: 要保存的数据框
        output_dir: 输出目录
        file_prefix: 文件名前缀
        formats: 输出格式列表
        
    Returns:
        ProcessingResult: 保存结果
    """
    try:
        # 确保输出目录存在
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # 生成带时间戳的文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        saved_files = []
        
        for fmt in formats:
            filename = f"{file_prefix}_{timestamp}.{fmt}"
            file_path = output_path / filename
            
            if fmt == "csv":
                df.to_csv(file_path, index=False, encoding='utf-8-sig')
            elif fmt == "xlsx":
                df.to_excel(file_path, index=False, engine='openpyxl')
            else:
                logger.warning(f"不支持的格式: {fmt}")
                continue
            
            saved_files.append(str(file_path))
            logger.info(f"✅ 保存文件: {file_path}")
        
        return ProcessingResult(
            success=True,
            data=df,
            message=f"成功保存 {len(saved_files)} 个文件",
            metadata={
                "saved_files": saved_files,
                "output_dir": str(output_path),
                "timestamp": timestamp
            },
            timestamp=datetime.now().isoformat()
        )
        
    except Exception as e:
        logger.error(f"❌ 结果保存失败: {e}")
        return ProcessingResult(
            success=False,
            data=df,
            message=f"保存失败: {str(e)}",
            metadata={"error_type": type(e).__name__},
            timestamp=datetime.now().isoformat()
        )

# =============================================================================
# 7. 完整处理流程示例
# =============================================================================
def process_data_pipeline(input_file: str, 
                         output_dir: str,
                         processing_config: Dict[str, Any] = None) -> ProcessingResult:
    """
    完整数据处理流水线示例
    
    这个函数展示了如何组合使用上述各个函数来构建完整的数据处理流程
    """
    try:
        # 1. 读取数据
        logger.info(f"开始处理数据文件: {input_file}")
        
        read_result = read_data_with_validation(input_file)
        if not read_result.success:
            return read_result
        
        # 2. 清理数据
        logger.info("开始数据清理...")
        clean_result = clean_and_preprocess(read_result.data, processing_config)
        if not clean_result.success:
            return clean_result
        
        # 3. 保存结果
        logger.info("保存处理结果...")
        save_result = save_results(
            clean_result.data, 
            output_dir,
            file_prefix="processed_data"
        )
        
        logger.info("✅ 数据处理流水线完成")
        
        return ProcessingResult(
            success=True,
            data=clean_result.data,
            message="完整处理流程成功完成",
            metadata={
                "pipeline_steps": ["read", "clean", "save"],
                "read_metadata": read_result.metadata,
                "clean_metadata": clean_result.metadata,
                "save_metadata": save_result.metadata
            },
            timestamp=datetime.now().isoformat()
        )
        
    except Exception as e:
        logger.error(f"❌ 处理流水线失败: {e}")
        return ProcessingResult(
            success=False,
            data=None,
            message=f"流水线错误: {str(e)}",
            metadata={"error_type": type(e).__name__},
            timestamp=datetime.now().isoformat()
        )

# =============================================================================
# 使用示例
# =============================================================================
if __name__ == "__main__":
    # 这是使用模式的示例，不会实际执行
    
    # 示例配置
    config = {
        'remove_duplicates': True,
        'missing_strategy': 'drop',
        'dtype_mappings': {
            'numeric_column': 'float64',
            'category_column': 'category'
        },
        'range_validations': {
            'price': (0, 10000),
            'quantity': (0, 1000)
        }
    }
    
    # 处理数据
    result = process_data_pipeline(
        input_file="data/input.csv",
        output_dir="results/tables/",
        processing_config=config
    )
    
    if result.success:
        print(f"✅ 处理成功: {result.message}")
        print(f"数据形状: {result.data.shape}")
    else:
        print(f"❌ 处理失败: {result.message}")