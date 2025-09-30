# -*- coding: utf-8 -*-
"""
敏感性分析三维权衡关系可视化
展示经济性、环境影响、供应保障三个维度的权衡
"""

import os
import io
import logging
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from matplotlib import cm
from matplotlib.colors import Normalize

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TradeoffVisualizer:
    """三维权衡关系可视化器"""

    def __init__(self, data_file: str, output_dir: str):
        """
        初始化可视化器

        Args:
            data_file: 完整数据文件路径 (results.csv)
            output_dir: 输出目录路径
        """
        self.data_file = data_file
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

        # 图表设置
        self.figsize = (12, 9)
        self.dpi = 300

    def load_data(self) -> pd.DataFrame:
        """加载数据"""
        if not os.path.exists(self.data_file):
            raise FileNotFoundError(f"数据文件不存在: {self.data_file}")

        df = pd.read_csv(self.data_file, encoding='utf-8-sig')
        logger.info(f"已加载数据: {self.data_file}, 形状: {df.shape}")

        # 不过滤数据,展示所有数据点(包括需求满足度为0的点)
        # df = df[df['demand_fulfillment_ratio'] > 0].copy()
        logger.info(f"有效数据点: {len(df)}")

        return df

    def create_3d_tradeoff_plot(self, df: pd.DataFrame,
                                x_col: str, y_col: str, z_col: str,
                                x_label: str, y_label: str, z_label: str,
                                title: str, filename: str):
        """
        创建三维权衡关系图

        Args:
            df: 数据DataFrame
            x_col: X轴列名
            y_col: Y轴列名
            z_col: Z轴列名
            x_label: X轴标签
            y_label: Y轴标签
            z_label: Z轴标签
            title: 图表标题
            filename: 输出文件名
        """
        # 提取数据
        X = df[x_col].values.copy()
        Y = df[y_col].values.copy()
        Z = df[z_col].values.copy()
        param_values = df['param_value'].values.copy()

        # 处理全零点：当三个指标都为0时，用门槛值替代经济成本
        zero_mask = (X == 0) & (Y == 0) & (Z == 0)
        if zero_mask.any():
            X[zero_mask] = param_values[zero_mask]
            logger.info(f"已将 {zero_mask.sum()} 个零值点的成本替换为门槛值 {param_values[zero_mask]}")

        # 过滤NaN值
        valid_mask = ~(np.isnan(X) | np.isnan(Y) | np.isnan(Z))
        X_valid = X[valid_mask]
        Y_valid = Y[valid_mask]
        Z_valid = Z[valid_mask]
        param_valid = param_values[valid_mask]

        if len(X_valid) == 0:
            logger.warning(f"没有有效数据,跳过图表: {filename}")
            return

        # 创建图表
        fig = plt.figure(figsize=self.figsize)
        ax = fig.add_subplot(111, projection='3d')

        # 颜色映射 - 使用Z值(需求满足度)作为颜色
        norm = Normalize(vmin=Z_valid.min(), vmax=Z_valid.max())
        colors = cm.viridis(norm(Z_valid))

        # 绘制散点图
        scatter = ax.scatter(X_valid, Y_valid, Z_valid, c=colors, marker='o', s=100,
                            edgecolors='black', linewidths=0.5, alpha=0.8, label='数据点')

        # 绘制平面投影曲线
        # 按参数值排序以获得连续曲线
        sort_idx = np.argsort(param_valid)
        X_sorted = X_valid[sort_idx]
        Y_sorted = Y_valid[sort_idx]
        Z_sorted = Z_valid[sort_idx]

        # 获取坐标轴范围
        xlim = ax.get_xlim()
        ylim = ax.get_ylim()
        zlim = ax.get_zlim()

        # 1. XY平面投影（底面，Z=zlim[0]）- 成本 vs 碳排放
        ax.plot(X_sorted, Y_sorted, zlim[0],
                color='gray', linewidth=2, alpha=0.6, linestyle='--',
                label='XY平面投影')

        # 2. XZ平面投影（侧面，Y=ylim[1]）- 成本 vs 需求
        ax.plot(X_sorted, ylim[1], Z_sorted,
                color='blue', linewidth=2, alpha=0.6, linestyle='--',
                label='XZ平面投影')

        # 3. YZ平面投影（背面，X=xlim[0]）- 碳排放 vs 需求
        ax.plot(xlim[0], Y_sorted, Z_sorted,
                color='red', linewidth=2, alpha=0.6, linestyle='--',
                label='YZ平面投影')

        # 设置标签
        ax.set_xlabel(x_label, fontsize=12, labelpad=10)
        ax.set_ylabel(y_label, fontsize=12, labelpad=10)
        ax.set_zlabel(z_label, fontsize=12, labelpad=10)
        ax.set_title(title, fontsize=14, pad=20, weight='bold')

        # 添加颜色条
        mappable = cm.ScalarMappable(norm=norm, cmap=cm.viridis)
        mappable.set_array(Z_valid)
        cbar = fig.colorbar(mappable, ax=ax, shrink=0.6, aspect=15, pad=0.1)
        cbar.set_label(z_label, fontsize=11)

        # 添加图例
        ax.legend(loc='upper left', fontsize=9, framealpha=0.8)

        # 设置视角
        ax.view_init(elev=20, azim=45)

        # 添加网格
        ax.grid(True, alpha=0.3)

        # 调整布局
        plt.tight_layout()

        # 保存图表 - 使用BytesIO避免Windows长路径问题
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=self.dpi, bbox_inches='tight')
        plt.close()

        # 写入文件（切换到目标目录使用短文件名）
        original_dir = os.getcwd()
        try:
            # 确保输出目录存在
            abs_output_dir = os.path.abspath(self.output_dir)
            os.makedirs(abs_output_dir, exist_ok=True)

            os.chdir(abs_output_dir)
            with open(filename, 'wb') as f:
                f.write(buf.getvalue())
            logger.info(f"✓ 权衡图已保存: {os.path.join(abs_output_dir, filename)}")
        finally:
            os.chdir(original_dir)

    def create_all_tradeoff_plots(self):
        """创建所有三维权衡图"""
        # 加载数据
        df = self.load_data()

        if len(df) == 0:
            logger.error("没有有效数据,无法生成权衡图")
            return

        # 图1: 经济-总碳排放-需求
        logger.info("生成图1: 经济-总碳排放-需求 三维权衡图...")
        self.create_3d_tradeoff_plot(
            df=df,
            x_col='lifecycle_levelized_cost',
            y_col='total_carbon_emission',
            z_col='demand_fulfillment_ratio',
            x_label='平准化成本 (元/kg)',
            y_label='总碳排放 (ton CO₂)',
            z_label='需求满足度 (%)',
            title='经济性-环境影响-供应保障 三维权衡关系\n(总碳排放)',
            filename='t1.png'  # 使用超短文件名避免Windows长路径bug
        )

        # 图2: 经济-质量碳强度-需求
        logger.info("生成图2: 经济-质量碳强度-需求 三维权衡图...")
        self.create_3d_tradeoff_plot(
            df=df,
            x_col='lifecycle_levelized_cost',
            y_col='carbon_intensity_mass',
            z_col='demand_fulfillment_ratio',
            x_label='平准化成本 (元/kg)',
            y_label='质量碳强度 (kg CO₂/kg 甲醇)',
            z_label='需求满足度 (%)',
            title='经济性-环境影响-供应保障 三维权衡关系\n(质量碳强度)',
            filename='t2.png'  # 使用超短文件名避免Windows长路径bug
        )

        # 图3: 经济-能量碳强度-需求
        logger.info("生成图3: 经济-能量碳强度-需求 三维权衡图...")
        self.create_3d_tradeoff_plot(
            df=df,
            x_col='lifecycle_levelized_cost',
            y_col='carbon_intensity_energy',
            z_col='demand_fulfillment_ratio',
            x_label='平准化成本 (元/kg)',
            y_label='能量碳强度 (kg CO₂/MJ)',
            z_label='需求满足度 (%)',
            title='经济性-环境影响-供应保障 三维权衡关系\n(能量碳强度)',
            filename='t3.png'  # 使用超短文件名避免Windows长路径bug
        )


def main():
    """测试函数"""
    import sys
    from pathlib import Path

    if len(sys.argv) < 3:
        print("用法: python sensitivity_visualization_tradeoff.py <data_file> <output_dir>")
        sys.exit(1)

    data_file = sys.argv[1]
    output_dir = sys.argv[2]

    visualizer = TradeoffVisualizer(data_file, output_dir)
    visualizer.create_all_tradeoff_plots()


if __name__ == "__main__":
    main()
