#!/usr/bin/env python3
"""
绿色甲醇供应链成本可视化引擎
Cost Visualization Engine for Green Methanol Supply Chain

提供全面的成本分析和可视化功能，包括：
- 成本结构分析
- 单位成本对比
- 效率分析
- 生命周期成本可视化
- 交互式仪表板

作者: Claude Code
创建时间: 2025-09-12
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import seaborn as sns
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import plotly.offline as pyo
from pathlib import Path
import os
import sys
import logging
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Any
import warnings

# 设置中文字体支持
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

# 忽略警告
warnings.filterwarnings('ignore')

# 配置日志
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class CostVisualizationEngine:
    """
    绿色甲醇供应链成本可视化引擎
    """
    
    def __init__(self, results_dir: str = None):
        """
        初始化可视化引擎
        
        Args:
            results_dir: 结果文件目录路径
        """
        self.results_dir = Path(results_dir) if results_dir else None
        self.data = None
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 成本项目分类
        self.investment_costs = [
            'MTJ工厂建设投资(元)',
            '电解槽建设投资(元)', 
            '运输设备投资(元)',
            'MTJ储存设备投资(元)',
            '氢能管道建设投资(元)'
        ]
        
        self.operational_costs = [
            'MTJ工厂运营成本(元)',
            'MTJ生产运营成本(元)',
            '氢气制取成本(元)',
            '氢气罐车运输成本(元)',
            '氢能管道运输成本(元)',
            '天然气运输成本(元)',
            '天然气原料成本(元)',
            'MTJ运输运营成本(元)',
            'MTJ储存运营成本(元)'
        ]
        
        # 颜色配置
        self.colors = {
            'primary': '#2E86C1',
            'secondary': '#28B463', 
            'accent': '#F39C12',
            'warning': '#E74C3C',
            'info': '#8E44AD',
            'investment': '#3498DB',
            'operational': '#E67E22',
            'penalty': '#E74C3C'
        }
        
        # 创建输出目录
        self._create_output_directories()
        
        logger.info(f"成本可视化引擎初始化完成 - 时间戳: {self.timestamp}")
    
    def _create_output_directories(self):
        """创建输出目录结构"""
        if self.results_dir:
            dirs = ['charts', 'figures', 'reports']
            for dir_name in dirs:
                output_dir = self.results_dir / dir_name
                output_dir.mkdir(exist_ok=True)
                logger.debug(f"创建目录: {output_dir}")
    
    def load_optimization_data(self, file_path: str = None) -> bool:
        """
        加载优化结果数据
        
        Args:
            file_path: CSV文件路径，如果为None则自动查找最新文件
            
        Returns:
            是否成功加载数据
        """
        try:
            if file_path is None:
                file_path = self._find_latest_summary_file()
                
            if not file_path or not os.path.exists(file_path):
                logger.error(f"优化结果文件不存在: {file_path}")
                return False
                
            # 读取CSV文件
            self.data = pd.read_csv(file_path, encoding='utf-8')
            
            if self.data.empty:
                logger.error("优化结果文件为空")
                return False
                
            logger.info(f"成功加载优化数据: {file_path}")
            logger.info(f"数据维度: {self.data.shape}")
            
            return True
            
        except Exception as e:
            logger.error(f"加载优化数据失败: {e}")
            return False
    
    def _find_latest_summary_file(self) -> Optional[str]:
        """查找最新的优化结果文件"""
        if not self.results_dir:
            return None
            
        pattern = "optimization_summary_*.csv"
        files = list(self.results_dir.glob(pattern))
        
        if not files:
            logger.warning(f"未找到优化结果文件: {pattern}")
            return None
            
        # 按时间戳排序，返回最新文件
        latest_file = max(files, key=os.path.getctime)
        logger.info(f"找到最新优化结果文件: {latest_file}")
        return str(latest_file)
    
    def create_cost_breakdown_charts(self) -> Dict[str, str]:
        """
        创建成本结构分解图表
        
        Returns:
            生成的图表文件路径字典
        """
        if self.data is None:
            logger.error("数据未加载，无法创建图表")
            return {}
            
        chart_files = {}
        
        try:
            # 1. 主要成本组成饼图
            chart_files['pie_chart'] = self._create_cost_pie_chart()
            
            # 2. 投资vs运营成本对比柱状图
            chart_files['investment_vs_operational'] = self._create_investment_vs_operational_chart()
            
            # 3. 详细成本结构堆叠柱状图
            chart_files['detailed_breakdown'] = self._create_detailed_breakdown_chart()
            
            # 4. 成本占比热力图
            chart_files['cost_heatmap'] = self._create_cost_ratio_heatmap()
            
            logger.info("成本结构分解图表创建完成")
            
        except Exception as e:
            logger.error(f"创建成本结构图表失败: {e}")
            
        return chart_files
    
    def _create_cost_pie_chart(self) -> str:
        """创建主要成本组成饼图"""
        try:
            # 获取主要成本项
            row = self.data.iloc[0]
            
            major_costs = {
                'MTJ生产运营': row.get('MTJ生产运营成本(元)', 0),
                'MTJ工厂建设投资': row.get('MTJ工厂建设投资(元)', 0),
                '天然气运输': row.get('天然气运输成本(元)', 0),
                'MTJ运输运营': row.get('MTJ运输运营成本(元)', 0),
                'MTJ工厂运营': row.get('MTJ工厂运营成本(元)', 0),
                '氢能管道运输': row.get('氢能管道运输成本(元)', 0),
                '氢能管道建设': row.get('氢能管道建设投资(元)', 0),
                '其他成本': 0
            }
            
            # 计算其他小项成本
            other_items = [
                '电解槽建设投资(元)', '运输设备投资(元)', 'MTJ储存设备投资(元)',
                '氢气制取成本(元)', '氢气罐车运输成本(元)', '天然气原料成本(元)', 'MTJ储存运营成本(元)'
            ]
            
            for item in other_items:
                major_costs['其他成本'] += row.get(item, 0)
            
            # 过滤零值并排序
            major_costs = {k: v for k, v in major_costs.items() if v > 0}
            costs_sorted = dict(sorted(major_costs.items(), key=lambda x: x[1], reverse=True))
            
            # 创建饼图
            fig, ax = plt.subplots(figsize=(12, 10))
            
            values = list(costs_sorted.values())
            labels = list(costs_sorted.keys())
            
            # 计算百分比
            total = sum(values)
            percentages = [v/total*100 for v in values]
            
            # 自定义颜色
            colors = plt.cm.Set3(np.linspace(0, 1, len(labels)))
            
            # 创建饼图 - 分离标签避免重叠
            wedges, texts, autotexts = ax.pie(values, labels=None, autopct='%1.1f%%',
                                            startangle=90, colors=colors, 
                                            pctdistance=0.85, labeldistance=1.1)
            
            # 美化百分比文本
            for autotext in autotexts:
                autotext.set_color('white')
                autotext.set_weight('bold')
                autotext.set_fontsize(10)
            
            # 创建图例避免标签重叠
            legend_labels = [f'{label}\n{value/1e12:.2f}万亿元 ({value/total*100:.1f}%)' 
                           for label, value in zip(labels, values)]
            ax.legend(wedges, legend_labels, title="成本项目",
                     loc="center left", bbox_to_anchor=(1, 0, 0.5, 1),
                     fontsize=10)
                
            ax.set_title('绿色甲醇供应链主要成本结构分析', fontsize=16, fontweight='bold', pad=20)
            
            # 添加总成本信息
            total_cost_text = f'总成本: {total/1e12:.2f}万亿元'
            ax.text(0.02, 0.98, total_cost_text, transform=ax.transAxes, 
                   bbox=dict(boxstyle="round,pad=0.3", facecolor="lightblue"),
                   fontsize=12, verticalalignment='top')
            
            plt.tight_layout()
            
            # 保存图表
            output_file = self.results_dir / 'charts' / f'cost_breakdown_pie_{self.timestamp}.png'
            plt.savefig(output_file, dpi=300, bbox_inches='tight', 
                       facecolor='white', edgecolor='none')
            plt.close()
            
            logger.info(f"主要成本饼图已保存: {output_file}")
            return str(output_file)
            
        except Exception as e:
            logger.error(f"创建成本饼图失败: {e}")
            return ""
    
    def _create_investment_vs_operational_chart(self) -> str:
        """创建投资vs运营成本对比图"""
        try:
            row = self.data.iloc[0]
            
            # 计算投资成本总额
            investment_total = sum(row.get(cost, 0) for cost in self.investment_costs)
            
            # 计算运营成本总额  
            operational_total = sum(row.get(cost, 0) for cost in self.operational_costs)
            
            # 获取短缺惩罚成本
            shortage_cost = row.get('短缺惩罚成本(元)', 0)
            
            # 创建柱状图
            fig, ax = plt.subplots(figsize=(10, 8))
            
            categories = ['投资成本', '运营成本', '短缺惩罚成本']
            values = [investment_total, operational_total, shortage_cost]
            colors = [self.colors['investment'], self.colors['operational'], self.colors['penalty']]
            
            bars = ax.bar(categories, values, color=colors, alpha=0.8, edgecolor='black')
            
            # 添加数值标签
            for bar, value in zip(bars, values):
                height = bar.get_height()
                if value > 1e12:  # 万亿级
                    label = f'{value/1e12:.2f}万亿元'
                elif value > 1e8:  # 亿级
                    label = f'{value/1e8:.2f}亿元'
                else:
                    label = f'{value/1e6:.2f}百万元'
                    
                ax.text(bar.get_x() + bar.get_width()/2., height + max(values)*0.01,
                       label, ha='center', va='bottom', fontweight='bold', fontsize=11)
            
            ax.set_title('投资成本 vs 运营成本 vs 短缺惩罚成本对比', fontsize=14, fontweight='bold')
            ax.set_ylabel('成本 (元)', fontsize=12)
            
            # 格式化y轴
            ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{x/1e12:.1f}万亿'))
            
            # 添加网格
            ax.grid(True, alpha=0.3, axis='y')
            
            plt.tight_layout()
            
            # 保存图表
            output_file = self.results_dir / 'charts' / f'investment_vs_operational_{self.timestamp}.png'
            plt.savefig(output_file, dpi=300, bbox_inches='tight')
            plt.close()
            
            logger.info(f"投资vs运营成本图已保存: {output_file}")
            return str(output_file)
            
        except Exception as e:
            logger.error(f"创建投资vs运营成本图失败: {e}")
            return ""
    
    def _create_detailed_breakdown_chart(self) -> str:
        """创建详细成本结构堆叠柱状图"""
        try:
            row = self.data.iloc[0]
            
            # 准备投资成本数据
            investment_data = {}
            for cost in self.investment_costs:
                value = row.get(cost, 0)
                if value > 0:
                    investment_data[cost.replace('(元)', '')] = value
            
            # 准备运营成本数据
            operational_data = {}
            for cost in self.operational_costs:
                value = row.get(cost, 0) 
                if value > 0:
                    operational_data[cost.replace('(元)', '')] = value
            
            # 创建堆叠柱状图
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(18, 8))
            
            # 投资成本堆叠图
            if investment_data:
                labels1 = list(investment_data.keys())
                values1 = list(investment_data.values())
                colors1 = plt.cm.Blues(np.linspace(0.3, 0.8, len(labels1)))
                
                bars1 = ax1.bar(range(len(labels1)), values1, color=colors1)
                ax1.set_title('投资成本详细结构', fontsize=14, fontweight='bold')
                ax1.set_xticks(range(len(labels1)))
                ax1.set_xticklabels(labels1, rotation=45, ha='right')
                ax1.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{x/1e8:.1f}亿'))
                
                # 添加数值标签
                for bar, value in zip(bars1, values1):
                    height = bar.get_height()
                    if value > 1e8:
                        label = f'{value/1e8:.1f}亿'
                    else:
                        label = f'{value/1e6:.1f}百万'
                    ax1.text(bar.get_x() + bar.get_width()/2., height + max(values1)*0.01,
                           label, ha='center', va='bottom', fontsize=9)
            
            # 运营成本堆叠图
            if operational_data:
                labels2 = list(operational_data.keys())
                values2 = list(operational_data.values())
                colors2 = plt.cm.Oranges(np.linspace(0.3, 0.8, len(labels2)))
                
                bars2 = ax2.bar(range(len(labels2)), values2, color=colors2)
                ax2.set_title('运营成本详细结构', fontsize=14, fontweight='bold')
                ax2.set_xticks(range(len(labels2)))
                ax2.set_xticklabels(labels2, rotation=45, ha='right')
                ax2.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{x/1e12:.1f}万亿' if x > 1e12 else f'{x/1e8:.1f}亿'))
                
                # 添加数值标签
                for bar, value in zip(bars2, values2):
                    height = bar.get_height()
                    if value > 1e12:
                        label = f'{value/1e12:.2f}万亿'
                    elif value > 1e8:
                        label = f'{value/1e8:.1f}亿'
                    else:
                        label = f'{value/1e6:.1f}百万'
                    ax2.text(bar.get_x() + bar.get_width()/2., height + max(values2)*0.01,
                           label, ha='center', va='bottom', fontsize=9)
            
            plt.suptitle('绿色甲醇供应链详细成本结构分析', fontsize=16, fontweight='bold')
            plt.tight_layout()
            
            # 保存图表
            output_file = self.results_dir / 'charts' / f'detailed_cost_breakdown_{self.timestamp}.png'
            plt.savefig(output_file, dpi=300, bbox_inches='tight')
            plt.close()
            
            logger.info(f"详细成本结构图已保存: {output_file}")
            return str(output_file)
            
        except Exception as e:
            logger.error(f"创建详细成本结构图失败: {e}")
            return ""
    
    def _create_cost_ratio_heatmap(self) -> str:
        """创建成本占比热力图"""
        try:
            row = self.data.iloc[0]
            
            # 获取效率和占比数据
            efficiency_data = {
                '电解制氢理论效率(%)': row.get('电解制氢理论效率(%)', 0),
                '电解制氢实际效率(%)': row.get('电解制氢实际效率(%)', 0),
                'MTJ转化效率(%)': row.get('MTJ转化效率(%)', 0),
                '综合电力转MTJ效率(%)': row.get('综合电力转MTJ效率(%)', 0)
            }
            
            cost_ratio_data = {
                '氢气电力成本占比(%)': row.get('氢气电力成本占比(%)', 0),
                '氢气设备成本占比(%)': row.get('氢气设备成本占比(%)', 0),
                '氢气运营成本占比(%)': row.get('氢气运营成本占比(%)', 0),
                'MTJ氢气原料成本占比(%)': row.get('MTJ氢气原料成本占比(%)', 0),
                'MTJ CO2原料成本占比(%)': row.get('MTJ CO2原料成本占比(%)', 0)
            }
            
            # 创建分开的两个子图来避免矩阵形状问题
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))
            
            # 左侧：效率分析柱状图
            eff_labels = list(efficiency_data.keys())
            eff_values = list(efficiency_data.values())
            bars1 = ax1.bar(range(len(eff_labels)), eff_values, 
                          color=plt.cm.Blues(np.linspace(0.4, 0.8, len(eff_labels))), alpha=0.8)
            
            # 添加数值标签
            for bar, value in zip(bars1, eff_values):
                height = bar.get_height()
                ax1.text(bar.get_x() + bar.get_width()/2., height + 1,
                        f'{value:.1f}%', ha='center', va='bottom', fontweight='bold')
            
            ax1.set_title('转化效率分析', fontsize=14, fontweight='bold')
            ax1.set_ylabel('效率 (%)', fontsize=12)
            ax1.set_xticks(range(len(eff_labels)))
            ax1.set_xticklabels([label.replace('(%)', '').replace('电解制氢', '电解\n制氢').replace('综合电力转MTJ', '综合电力\n转MTJ') 
                               for label in eff_labels], fontsize=10)
            ax1.set_ylim(0, max(eff_values) * 1.1)
            ax1.grid(True, alpha=0.3, axis='y')
            
            # 右侧：成本占比分析柱状图
            cost_labels = [k for k, v in cost_ratio_data.items() if v > 0]  # 只显示非零值
            cost_values = [v for v in cost_ratio_data.values() if v > 0]
            
            if cost_labels:
                bars2 = ax2.bar(range(len(cost_labels)), cost_values, 
                              color=plt.cm.Oranges(np.linspace(0.4, 0.8, len(cost_labels))), alpha=0.8)
                
                # 添加数值标签
                for bar, value in zip(bars2, cost_values):
                    height = bar.get_height()
                    ax2.text(bar.get_x() + bar.get_width()/2., height + max(cost_values)*0.01,
                            f'{value:.1f}%', ha='center', va='bottom', fontweight='bold')
                
                ax2.set_xticks(range(len(cost_labels)))
                ax2.set_xticklabels([label.replace('占比(%)', '').replace('氢气', '氢气\n').replace('MTJ', 'MTJ\n') 
                                   for label in cost_labels], fontsize=10)
                ax2.set_ylim(0, max(cost_values) * 1.1)
            else:
                ax2.text(0.5, 0.5, '成本占比数据\n暂无或为零', ha='center', va='center', 
                        transform=ax2.transAxes, fontsize=12,
                        bbox=dict(boxstyle="round,pad=0.3", facecolor="lightgray"))
            
            ax2.set_title('成本占比分析', fontsize=14, fontweight='bold')
            ax2.set_ylabel('占比 (%)', fontsize=12)
            ax2.grid(True, alpha=0.3, axis='y')
            
            plt.suptitle('效率与成本占比分析', fontsize=16, fontweight='bold')
            plt.tight_layout()
            
            # 保存图表
            output_file = self.results_dir / 'charts' / f'efficiency_cost_analysis_{self.timestamp}.png'
            plt.savefig(output_file, dpi=300, bbox_inches='tight')
            plt.close()
            
            logger.info(f"效率与成本占比分析图已保存: {output_file}")
            return str(output_file)
            
        except Exception as e:
            logger.error(f"创建成本占比热力图失败: {e}")
            return ""
    
    def create_cost_waterfall_chart(self) -> str:
        """
        创建成本瀑布图 - 显示从原料到最终产品的成本流
        
        Returns:
            生成的图表文件路径
        """
        if self.data is None:
            logger.error("数据未加载，无法创建瀑布图")
            return ""
            
        try:
            row = self.data.iloc[0]
            
            # 成本瀑布流程
            waterfall_steps = [
                ('起始', 0, 0),  # 起点
                ('电解槽投资', row.get('电解槽建设投资(元)', 0), self.colors['investment']),
                ('MTJ工厂投资', row.get('MTJ工厂建设投资(元)', 0), self.colors['investment']),
                ('氢能管道投资', row.get('氢能管道建设投资(元)', 0), self.colors['investment']),
                ('MTJ工厂运营', row.get('MTJ工厂运营成本(元)', 0), self.colors['operational']),
                ('MTJ生产运营', row.get('MTJ生产运营成本(元)', 0), self.colors['operational']),
                ('天然气运输', row.get('天然气运输成本(元)', 0), self.colors['operational']),
                ('MTJ运输运营', row.get('MTJ运输运营成本(元)', 0), self.colors['operational']),
                ('氢能管道运输', row.get('氢能管道运输成本(元)', 0), self.colors['operational']),
                ('短缺惩罚', row.get('短缺惩罚成本(元)', 0), self.colors['penalty']),
                ('总成本', 0, self.colors['primary'])  # 终点
            ]
            
            # 计算累计值
            cumulative = 0
            positions = []
            values = []
            colors = []
            labels = []
            
            for i, (label, value, color) in enumerate(waterfall_steps):
                if label == '起始':
                    positions.append(0)
                    values.append(0)
                elif label == '总成本':
                    positions.append(cumulative)
                    values.append(cumulative)
                else:
                    positions.append(cumulative)
                    values.append(value)
                    cumulative += value
                
                colors.append(color)
                labels.append(label)
            
            # 创建瀑布图
            fig, ax = plt.subplots(figsize=(16, 10))
            
            # 绘制连接线
            for i in range(len(positions)-1):
                if i > 0:  # 跳过起始点
                    ax.plot([i, i+1], [positions[i] + values[i], positions[i+1]], 
                           'k--', alpha=0.5, linewidth=1)
            
            # 绘制柱子
            bars = []
            for i, (pos, val, color, label) in enumerate(zip(positions, values, colors, labels)):
                if label in ['起始', '总成本']:
                    bar = ax.bar(i, val, bottom=0 if label == '起始' else 0, 
                               color=color, alpha=0.8, edgecolor='black')
                else:
                    bar = ax.bar(i, val, bottom=pos, color=color, alpha=0.8, edgecolor='black')
                bars.append(bar)
                
                # 添加数值标签
                if val > 0:
                    text_y = pos + val/2 if label not in ['起始', '总成本'] else val/2
                    if val > 1e12:
                        value_text = f'{val/1e12:.2f}万亿'
                    elif val > 1e8:
                        value_text = f'{val/1e8:.1f}亿'
                    elif val > 1e6:
                        value_text = f'{val/1e6:.1f}百万'
                    else:
                        value_text = f'{val:.0f}'
                    
                    ax.text(i, text_y, value_text, ha='center', va='center',
                           fontweight='bold', fontsize=10, 
                           color='white' if val > max(values)*0.1 else 'black')
            
            # 设置标签和标题
            ax.set_xticks(range(len(labels)))
            ax.set_xticklabels(labels, rotation=45, ha='right')
            ax.set_title('绿色甲醇供应链成本瀑布图', fontsize=16, fontweight='bold', pad=20)
            ax.set_ylabel('累计成本 (元)', fontsize=12)
            
            # 格式化y轴
            ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{x/1e12:.1f}万亿'))
            
            # 添加网格
            ax.grid(True, alpha=0.3, axis='y')
            
            # 添加图例
            legend_elements = [
                mpatches.Patch(color=self.colors['investment'], label='投资成本'),
                mpatches.Patch(color=self.colors['operational'], label='运营成本'),
                mpatches.Patch(color=self.colors['penalty'], label='短缺惩罚'),
                mpatches.Patch(color=self.colors['primary'], label='总成本')
            ]
            ax.legend(handles=legend_elements, loc='upper left')
            
            plt.tight_layout()
            
            # 保存图表
            output_file = self.results_dir / 'charts' / f'cost_waterfall_{self.timestamp}.png'
            plt.savefig(output_file, dpi=300, bbox_inches='tight')
            plt.close()
            
            logger.info(f"成本瀑布图已保存: {output_file}")
            return str(output_file)
            
        except Exception as e:
            logger.error(f"创建成本瀑布图失败: {e}")
            return ""
    
    def create_unit_cost_analysis_charts(self) -> Dict[str, str]:
        """
        创建单位成本分析图表
        
        Returns:
            生成的图表文件路径字典
        """
        if self.data is None:
            logger.error("数据未加载，无法创建单位成本分析图表")
            return {}
            
        chart_files = {}
        
        try:
            # 1. 氢气vs MTJ单位成本对比
            chart_files['unit_cost_comparison'] = self._create_unit_cost_comparison()
            
            # 2. 效率分析图
            chart_files['efficiency_analysis'] = self._create_efficiency_analysis()
            
            # 3. 成本构成分析
            chart_files['cost_composition'] = self._create_cost_composition_analysis()
            
            # 4. 运输成本分析
            chart_files['transport_cost_analysis'] = self._create_transport_cost_analysis()
            
            logger.info("单位成本分析图表创建完成")
            
        except Exception as e:
            logger.error(f"创建单位成本分析图表失败: {e}")
            
        return chart_files
    
    def _create_unit_cost_comparison(self) -> str:
        """创建单位成本对比图"""
        try:
            row = self.data.iloc[0]
            
            # 单位成本数据
            unit_costs = {
                '氢气单位电力成本': row.get('氢气单位电力成本(元/kg)', 0),
                '氢气设备摊销成本': row.get('氢气设备摊销成本(元/kg)', 0),
                '氢气运营维护成本': row.get('氢气运营维护成本(元/kg)', 0),
                '氢气总单位成本': row.get('氢气总单位成本(元/kg)', 0),
                'MTJ氢气原料成本': row.get('MTJ氢气原料成本(元/kg)', 0),
                'MTJ设备摊销成本': row.get('MTJ设备摊销成本(元/kg)', 0),
                'MTJ运营维护成本': row.get('MTJ运营维护成本(元/kg)', 0),
                'MTJ总单位成本': row.get('MTJ总单位成本(元/kg)', 0)
            }
            
            # 创建分组柱状图
            fig, ax = plt.subplots(figsize=(14, 8))
            
            # 分组数据
            h2_costs = ['氢气单位电力成本', '氢气设备摊销成本', '氢气运营维护成本', '氢气总单位成本']
            mtj_costs = ['MTJ氢气原料成本', 'MTJ设备摊销成本', 'MTJ运营维护成本', 'MTJ总单位成本']
            
            x = np.arange(4)  # 4个成本类别
            width = 0.35  # 柱子宽度
            
            h2_values = [unit_costs[cost] for cost in h2_costs]
            mtj_values = [unit_costs[cost] for cost in mtj_costs]
            
            bars1 = ax.bar(x - width/2, h2_values, width, label='氢气成本', 
                          color=self.colors['primary'], alpha=0.8)
            bars2 = ax.bar(x + width/2, mtj_values, width, label='MTJ成本',
                          color=self.colors['secondary'], alpha=0.8)
            
            # 添加数值标签
            for bars, values in [(bars1, h2_values), (bars2, mtj_values)]:
                for bar, value in zip(bars, values):
                    height = bar.get_height()
                    ax.text(bar.get_x() + bar.get_width()/2., height + max(h2_values + mtj_values)*0.01,
                           f'{value:.2f}', ha='center', va='bottom', fontweight='bold', fontsize=10)
            
            # 设置标签
            ax.set_xlabel('成本类别', fontsize=12)
            ax.set_ylabel('单位成本 (元/kg)', fontsize=12)
            ax.set_title('氢气 vs MTJ 单位成本对比分析', fontsize=14, fontweight='bold')
            ax.set_xticks(x)
            ax.set_xticklabels(['电力/原料成本', '设备摊销成本', '运营维护成本', '总单位成本'])
            ax.legend()
            
            # 添加网格
            ax.grid(True, alpha=0.3, axis='y')
            
            plt.tight_layout()
            
            # 保存图表
            output_file = self.results_dir / 'charts' / f'unit_cost_comparison_{self.timestamp}.png'
            plt.savefig(output_file, dpi=300, bbox_inches='tight')
            plt.close()
            
            logger.info(f"单位成本对比图已保存: {output_file}")
            return str(output_file)
            
        except Exception as e:
            logger.error(f"创建单位成本对比图失败: {e}")
            return ""
    
    def _create_efficiency_analysis(self) -> str:
        """创建效率分析图"""
        try:
            row = self.data.iloc[0]
            
            # 效率数据
            efficiencies = {
                '电解制氢理论效率': row.get('电解制氢理论效率(%)', 0),
                '电解制氢实际效率': row.get('电解制氢实际效率(%)', 0),
                'MTJ转化效率': row.get('MTJ转化效率(%)', 0),
                '综合电力转MTJ效率': row.get('综合电力转MTJ效率(%)', 0)
            }
            
            # 创建雷达图
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 8))
            
            # 左侧：效率对比柱状图
            labels = list(efficiencies.keys())
            values = list(efficiencies.values())
            colors = [self.colors['primary'], self.colors['secondary'], 
                     self.colors['accent'], self.colors['info']]
            
            bars = ax1.bar(range(len(labels)), values, color=colors, alpha=0.8)
            
            # 添加数值标签
            for bar, value in zip(bars, values):
                height = bar.get_height()
                ax1.text(bar.get_x() + bar.get_width()/2., height + 1,
                        f'{value:.1f}%', ha='center', va='bottom', fontweight='bold')
            
            ax1.set_title('转化效率分析', fontsize=14, fontweight='bold')
            ax1.set_ylabel('效率 (%)', fontsize=12)
            ax1.set_xticks(range(len(labels)))
            ax1.set_xticklabels(labels, rotation=45, ha='right')
            ax1.set_ylim(0, 110)
            ax1.grid(True, alpha=0.3, axis='y')
            
            # 右侧：效率损失分析
            theoretical_h2 = row.get('电解制氢理论效率(%)', 100)
            actual_h2 = row.get('电解制氢实际效率(%)', 0)
            mtj_efficiency = row.get('MTJ转化效率(%)', 0)
            overall_efficiency = row.get('综合电力转MTJ效率(%)', 0)
            
            efficiency_losses = [
                ('电解制氢损失', theoretical_h2 - actual_h2),
                ('MTJ转化损失', 100 - mtj_efficiency),
                ('综合效率', overall_efficiency),
                ('总损失', 100 - overall_efficiency)
            ]
            
            loss_labels, loss_values = zip(*efficiency_losses)
            loss_colors = [self.colors['warning'] if '损失' in label else self.colors['secondary'] 
                          for label in loss_labels]
            
            bars2 = ax2.bar(range(len(loss_labels)), loss_values, color=loss_colors, alpha=0.8)
            
            # 添加数值标签
            for bar, value in zip(bars2, loss_values):
                height = bar.get_height()
                ax2.text(bar.get_x() + bar.get_width()/2., height + 0.5,
                        f'{value:.1f}%', ha='center', va='bottom', fontweight='bold')
            
            ax2.set_title('效率损失分析', fontsize=14, fontweight='bold')
            ax2.set_ylabel('效率/损失 (%)', fontsize=12)
            ax2.set_xticks(range(len(loss_labels)))
            ax2.set_xticklabels(loss_labels, rotation=45, ha='right')
            ax2.grid(True, alpha=0.3, axis='y')
            
            plt.suptitle('绿色甲醇供应链效率分析', fontsize=16, fontweight='bold')
            plt.tight_layout()
            
            # 保存图表
            output_file = self.results_dir / 'charts' / f'efficiency_analysis_{self.timestamp}.png'
            plt.savefig(output_file, dpi=300, bbox_inches='tight')
            plt.close()
            
            logger.info(f"效率分析图已保存: {output_file}")
            return str(output_file)
            
        except Exception as e:
            logger.error(f"创建效率分析图失败: {e}")
            return ""
    
    def _create_cost_composition_analysis(self) -> str:
        """创建成本构成分析图"""
        try:
            row = self.data.iloc[0]
            
            # 氢气成本构成
            h2_composition = {
                '电力成本': row.get('氢气电力成本占比(%)', 0),
                '设备成本': row.get('氢气设备成本占比(%)', 0),
                '运营成本': row.get('氢气运营成本占比(%)', 0)
            }
            
            # MTJ成本构成
            mtj_composition = {
                '氢气原料成本': row.get('MTJ氢气原料成本占比(%)', 0),
                'CO2原料成本': row.get('MTJ CO2原料成本占比(%)', 0)
            }
            
            # 创建双饼图
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 8))
            
            # 氢气成本构成饼图
            h2_labels = list(h2_composition.keys())
            h2_values = list(h2_composition.values())
            h2_colors = ['#FF6B6B', '#4ECDC4', '#45B7D1']
            
            # 氢气成本构成饼图 - 避免标签重叠
            wedges1, texts1, autotexts1 = ax1.pie(h2_values, labels=None, autopct='%1.1f%%',
                                                 startangle=90, colors=h2_colors,
                                                 pctdistance=0.85)
            
            for autotext in autotexts1:
                autotext.set_color('white')
                autotext.set_weight('bold')
                autotext.set_fontsize(11)
            
            # 添加图例
            ax1.legend(wedges1, [f'{label}: {value:.1f}%' for label, value in zip(h2_labels, h2_values)],
                      loc="center left", bbox_to_anchor=(1, 0, 0.5, 1), fontsize=10)
            
            ax1.set_title('氢气生产成本构成', fontsize=14, fontweight='bold')
            
            # MTJ成本构成饼图
            if sum(mtj_composition.values()) > 0:
                mtj_labels = list(mtj_composition.keys()) 
                mtj_values = list(mtj_composition.values())
                mtj_colors = ['#96CEB4', '#FECA57']
                
                # MTJ成本构成饼图 - 避免标签重叠
                wedges2, texts2, autotexts2 = ax2.pie(mtj_values, labels=None, autopct='%1.1f%%',
                                                     startangle=90, colors=mtj_colors,
                                                     pctdistance=0.85)
                
                for autotext in autotexts2:
                    autotext.set_color('white')
                    autotext.set_weight('bold')
                    autotext.set_fontsize(11)
                
                # 添加图例
                ax2.legend(wedges2, [f'{label}: {value:.1f}%' for label, value in zip(mtj_labels, mtj_values)],
                          loc="center left", bbox_to_anchor=(1, 0, 0.5, 1), fontsize=10)
                
                ax2.set_title('MTJ生产成本构成', fontsize=14, fontweight='bold')
            else:
                ax2.text(0.5, 0.5, 'MTJ成本构成数据\n暂无或为零', 
                        ha='center', va='center', fontsize=12, 
                        bbox=dict(boxstyle="round,pad=0.3", facecolor="lightgray"))
                ax2.set_title('MTJ生产成本构成', fontsize=14, fontweight='bold')
            
            plt.suptitle('成本构成分析', fontsize=16, fontweight='bold')
            plt.tight_layout()
            
            # 保存图表
            output_file = self.results_dir / 'charts' / f'cost_composition_{self.timestamp}.png'
            plt.savefig(output_file, dpi=300, bbox_inches='tight')
            plt.close()
            
            logger.info(f"成本构成分析图已保存: {output_file}")
            return str(output_file)
            
        except Exception as e:
            logger.error(f"创建成本构成分析图失败: {e}")
            return ""
    
    def _create_transport_cost_analysis(self) -> str:
        """创建运输成本分析图"""
        try:
            row = self.data.iloc[0]
            
            # 运输成本数据
            transport_costs = {
                '氢气运输单位成本': row.get('氢气运输单位成本(元/kg·km)', 0),
                'MTJ运输单位成本': row.get('MTJ运输单位成本(元/kg·km)', 0),
                '氢气储存单位成本': row.get('氢气储存单位成本(元/kg)', 0),
                'MTJ储存单位成本': row.get('MTJ储存单位成本(元/kg)', 0)
            }
            
            # 运输成本总额
            transport_totals = {
                '氢气罐车运输成本': row.get('氢气罐车运输成本(元)', 0),
                '氢能管道运输成本': row.get('氢能管道运输成本(元)', 0),
                '天然气运输成本': row.get('天然气运输成本(元)', 0),
                'MTJ运输运营成本': row.get('MTJ运输运营成本(元)', 0),
                'MTJ储存运营成本': row.get('MTJ储存运营成本(元)', 0)
            }
            
            # 创建双子图
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 12))
            
            # 上图：单位运输成本对比
            unit_labels = list(transport_costs.keys())
            unit_values = list(transport_costs.values())
            unit_colors = [self.colors['primary'], self.colors['secondary'], 
                          self.colors['accent'], self.colors['info']]
            
            bars1 = ax1.bar(range(len(unit_labels)), unit_values, color=unit_colors, alpha=0.8)
            
            # 添加数值标签
            for bar, value in zip(bars1, unit_values):
                height = bar.get_height()
                ax1.text(bar.get_x() + bar.get_width()/2., height + max(unit_values)*0.01,
                        f'{value:.2f}', ha='center', va='bottom', fontweight='bold', fontsize=10)
            
            ax1.set_title('单位运输成本分析', fontsize=14, fontweight='bold')
            ax1.set_ylabel('单位成本 (元/kg或元/kg·km)', fontsize=12)
            ax1.set_xticks(range(len(unit_labels)))
            ax1.set_xticklabels([label.replace('单位成本', '').replace('(元/kg·km)', '').replace('(元/kg)', '') 
                               for label in unit_labels], rotation=45, ha='right')
            ax1.grid(True, alpha=0.3, axis='y')
            
            # 下图：总运输成本分析
            total_labels = list(transport_totals.keys())
            total_values = list(transport_totals.values())
            total_colors = plt.cm.Oranges(np.linspace(0.4, 0.8, len(total_labels)))
            
            # 过滤非零值
            non_zero_items = [(label, value, color) for label, value, color 
                             in zip(total_labels, total_values, total_colors) if value > 0]
            
            if non_zero_items:
                nz_labels, nz_values, nz_colors = zip(*non_zero_items)
                
                bars2 = ax2.bar(range(len(nz_labels)), nz_values, color=nz_colors, alpha=0.8)
                
                # 添加数值标签
                for bar, value in zip(bars2, nz_values):
                    height = bar.get_height()
                    if value > 1e8:
                        label_text = f'{value/1e8:.1f}亿'
                    elif value > 1e6:
                        label_text = f'{value/1e6:.1f}百万'
                    else:
                        label_text = f'{value:.0f}'
                    ax2.text(bar.get_x() + bar.get_width()/2., height + max(nz_values)*0.01,
                            label_text, ha='center', va='bottom', fontweight='bold', fontsize=10)
                
                ax2.set_xticks(range(len(nz_labels)))
                ax2.set_xticklabels([label.replace('成本', '').replace('(元)', '') 
                                   for label in nz_labels], rotation=45, ha='right')
            
            ax2.set_title('总运输成本分析', fontsize=14, fontweight='bold')
            ax2.set_ylabel('总成本 (元)', fontsize=12)
            ax2.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{x/1e8:.1f}亿' if x > 1e8 else f'{x/1e6:.1f}百万'))
            ax2.grid(True, alpha=0.3, axis='y')
            
            plt.tight_layout()
            
            # 保存图表
            output_file = self.results_dir / 'charts' / f'transport_cost_analysis_{self.timestamp}.png'
            plt.savefig(output_file, dpi=300, bbox_inches='tight')
            plt.close()
            
            logger.info(f"运输成本分析图已保存: {output_file}")
            return str(output_file)
            
        except Exception as e:
            logger.error(f"创建运输成本分析图失败: {e}")
            return ""
    
    def create_interactive_dashboard(self) -> str:
        """
        创建交互式HTML仪表板
        
        Returns:
            生成的HTML文件路径
        """
        if self.data is None:
            logger.error("数据未加载，无法创建交互式仪表板")
            return ""
            
        try:
            row = self.data.iloc[0]
            
            # 创建子图
            fig = make_subplots(
                rows=3, cols=2,
                subplot_titles=('成本结构分析', '单位成本对比', '效率分析', 
                              '运输成本分析', '生命周期成本趋势', '成本占比分析'),
                specs=[[{"type": "pie"}, {"type": "bar"}],
                       [{"type": "bar"}, {"type": "bar"}], 
                       [{"type": "scatter"}, {"type": "bar"}]],
                vertical_spacing=0.08,
                horizontal_spacing=0.1
            )
            
            # 1. 成本结构饼图
            major_costs = {
                'MTJ生产运营': row.get('MTJ生产运营成本(元)', 0),
                'MTJ工厂建设投资': row.get('MTJ工厂建设投资(元)', 0),
                '天然气运输': row.get('天然气运输成本(元)', 0),
                'MTJ运输运营': row.get('MTJ运输运营成本(元)', 0),
                '氢能管道运输': row.get('氢能管道运输成本(元)', 0),
                '氢能管道建设': row.get('氢能管道建设投资(元)', 0),
                '其他成本': row.get('电解槽建设投资(元)', 0) + row.get('天然气原料成本(元)', 0)
            }
            
            # 过滤零值
            major_costs = {k: v for k, v in major_costs.items() if v > 0}
            
            fig.add_trace(
                go.Pie(labels=list(major_costs.keys()), 
                      values=list(major_costs.values()),
                      name="成本结构"),
                row=1, col=1
            )
            
            # 2. 单位成本对比
            unit_costs = ['氢气总单位成本(元/kg)', 'MTJ总单位成本(元/kg)']
            unit_values = [row.get(cost, 0) for cost in unit_costs]
            unit_labels = ['氢气单位成本', 'MTJ单位成本']
            
            fig.add_trace(
                go.Bar(x=unit_labels, y=unit_values,
                      name="单位成本",
                      marker_color=[self.colors['primary'], self.colors['secondary']]),
                row=1, col=2
            )
            
            # 3. 效率分析
            efficiencies = {
                '电解制氢理论': row.get('电解制氢理论效率(%)', 0),
                '电解制氢实际': row.get('电解制氢实际效率(%)', 0),
                'MTJ转化': row.get('MTJ转化效率(%)', 0),
                '综合效率': row.get('综合电力转MTJ效率(%)', 0)
            }
            
            fig.add_trace(
                go.Bar(x=list(efficiencies.keys()), 
                      y=list(efficiencies.values()),
                      name="转化效率",
                      marker_color=px.colors.qualitative.Set2),
                row=2, col=1
            )
            
            # 4. 运输成本分析
            transport_costs = {
                '氢气运输': row.get('氢气运输单位成本(元/kg·km)', 0),
                'MTJ运输': row.get('MTJ运输单位成本(元/kg·km)', 0),
                '氢气储存': row.get('氢气储存单位成本(元/kg)', 0),
                'MTJ储存': row.get('MTJ储存单位成本(元/kg)', 0)
            }
            
            fig.add_trace(
                go.Bar(x=list(transport_costs.keys()), 
                      y=list(transport_costs.values()),
                      name="运输成本",
                      marker_color=px.colors.qualitative.Pastel2),
                row=2, col=2
            )
            
            # 5. 生命周期成本趋势（模拟20年数据）
            years = list(range(1, 21))
            annual_cost = row.get('年化成本(元/年)', 0)
            cumulative_costs = [annual_cost * i for i in years]
            
            fig.add_trace(
                go.Scatter(x=years, y=cumulative_costs,
                          mode='lines+markers',
                          name="累计成本",
                          line=dict(color=self.colors['primary'], width=3)),
                row=3, col=1
            )
            
            # 6. 成本占比分析
            cost_ratios = {
                '氢气电力成本占比': row.get('氢气电力成本占比(%)', 0),
                '氢气设备成本占比': row.get('氢气设备成本占比(%)', 0),
                'MTJ氢气原料成本占比': row.get('MTJ氢气原料成本占比(%)', 0)
            }
            
            fig.add_trace(
                go.Bar(x=list(cost_ratios.keys()), 
                      y=list(cost_ratios.values()),
                      name="成本占比",
                      marker_color=px.colors.qualitative.Vivid),
                row=3, col=2
            )
            
            # 更新布局
            fig.update_layout(
                title_text="绿色甲醇供应链成本分析交互式仪表板",
                title_x=0.5,
                title_font_size=20,
                showlegend=False,
                height=1200,
                width=1400,
                font=dict(family="Arial, sans-serif", size=12)
            )
            
            # 更新子图标题
            fig.update_xaxes(title_text="", row=1, col=2)
            fig.update_yaxes(title_text="单位成本(元/kg)", row=1, col=2)
            fig.update_yaxes(title_text="效率(%)", row=2, col=1)
            fig.update_yaxes(title_text="成本(元/kg·km或元/kg)", row=2, col=2)
            fig.update_xaxes(title_text="年份", row=3, col=1)
            fig.update_yaxes(title_text="累计成本(元)", row=3, col=1)
            fig.update_yaxes(title_text="占比(%)", row=3, col=2)
            
            # 添加总结信息
            total_cost = row.get('生命周期总成本(元)', 0)
            levelized_cost = row.get('生命周期平准化成本(元/kg)', 0)
            production = row.get('20年总产量(kg)', 0)
            
            annotation_text = f"""
            <b>关键指标摘要</b><br>
            生命周期总成本: {total_cost/1e12:.2f} 万亿元<br>
            平准化成本: {levelized_cost:.2f} 元/kg<br>
            20年总产量: {production/1e6:.2f} 百万kg<br>
            单位电力消耗: {row.get('单位电力消耗(MWh/kg_MTJ)', 0):.6f} MWh/kg_MTJ
            """
            
            fig.add_annotation(
                text=annotation_text,
                xref="paper", yref="paper",
                x=1.02, y=0.95,
                showarrow=False,
                align="left",
                bgcolor="rgba(255,255,255,0.8)",
                bordercolor="black",
                borderwidth=1
            )
            
            # 保存HTML文件
            output_file = self.results_dir / 'figures' / f'interactive_cost_dashboard_{self.timestamp}.html'
            fig.write_html(str(output_file))
            
            logger.info(f"交互式仪表板已保存: {output_file}")
            return str(output_file)
            
        except Exception as e:
            logger.error(f"创建交互式仪表板失败: {e}")
            return ""
    
    def generate_comprehensive_report(self) -> Dict[str, Any]:
        """
        生成综合成本分析报告
        
        Returns:
            报告生成结果和文件路径
        """
        if self.data is None:
            logger.error("数据未加载，无法生成综合报告")
            return {}
            
        try:
            logger.info("开始生成综合成本分析报告...")
            
            report_results = {
                'timestamp': self.timestamp,
                'generated_files': {},
                'summary': {}
            }
            
            # 1. 生成所有图表
            logger.info("生成成本结构分解图表...")
            breakdown_charts = self.create_cost_breakdown_charts()
            report_results['generated_files'].update(breakdown_charts)
            
            logger.info("生成成本瀑布图...")
            waterfall_chart = self.create_cost_waterfall_chart()
            if waterfall_chart:
                report_results['generated_files']['waterfall_chart'] = waterfall_chart
            
            logger.info("生成单位成本分析图表...")
            unit_cost_charts = self.create_unit_cost_analysis_charts()
            report_results['generated_files'].update(unit_cost_charts)
            
            logger.info("生成交互式仪表板...")
            dashboard = self.create_interactive_dashboard()
            if dashboard:
                report_results['generated_files']['interactive_dashboard'] = dashboard
            
            # 2. 生成报告摘要
            row = self.data.iloc[0]
            report_results['summary'] = {
                'total_lifecycle_cost': row.get('生命周期总成本(元)', 0),
                'levelized_cost': row.get('生命周期平准化成本(元/kg)', 0),
                'levelized_cost_excluding_shortage': row.get('生命周期平准化成本_不含短缺(元/kg)', 0),
                'total_production': row.get('20年总产量(kg)', 0),
                'annual_production': row.get('年产量(kg)', 0),
                'shortage_penalty': row.get('短缺惩罚成本(元)', 0),
                'h2_unit_cost': row.get('氢气总单位成本(元/kg)', 0),
                'mtj_unit_cost': row.get('MTJ总单位成本(元/kg)', 0),
                'overall_efficiency': row.get('综合电力转MTJ效率(%)', 0),
                'power_consumption': row.get('单位电力消耗(MWh/kg_MTJ)', 0)
            }
            
            # 3. 生成文本报告
            report_file = self._generate_text_report(report_results)
            if report_file:
                report_results['generated_files']['text_report'] = report_file
            
            logger.info(f"综合报告生成完成，共生成 {len(report_results['generated_files'])} 个文件")
            
            return report_results
            
        except Exception as e:
            logger.error(f"生成综合报告失败: {e}")
            return {}
    
    def _generate_text_report(self, report_results: Dict[str, Any]) -> str:
        """生成文本报告"""
        try:
            summary = report_results.get('summary', {})
            
            report_content = f"""
绿色甲醇供应链成本分析报告
生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

================================================================================
1. 执行摘要
================================================================================

本报告对绿色甲醇供应链优化结果进行了全面的成本分析。主要发现如下：

总成本概览：
- 生命周期总成本: {summary.get('total_lifecycle_cost', 0)/1e12:.2f} 万亿元
- 生命周期平准化成本: {summary.get('levelized_cost', 0):.2f} 元/kg
- 不含短缺惩罚的平准化成本: {summary.get('levelized_cost_excluding_shortage', 0):.2f} 元/kg
- 短缺惩罚成本影响: {(summary.get('levelized_cost', 0) - summary.get('levelized_cost_excluding_shortage', 0)):.2f} 元/kg

生产规模：
- 年产量: {summary.get('annual_production', 0)/1e6:.2f} 百万kg
- 20年总产量: {summary.get('total_production', 0)/1e9:.2f} 十亿kg

================================================================================
2. 单位成本分析
================================================================================

氢气生产成本: {summary.get('h2_unit_cost', 0):.2f} 元/kg
MTJ生产成本: {summary.get('mtj_unit_cost', 0):.2f} 元/kg

成本比较：
- MTJ单位成本是氢气的 {summary.get('mtj_unit_cost', 1)/max(summary.get('h2_unit_cost', 1), 0.01):.2f} 倍
- 单位电力消耗: {summary.get('power_consumption', 0):.6f} MWh/kg_MTJ

================================================================================
3. 效率分析
================================================================================

综合电力转MTJ效率: {summary.get('overall_efficiency', 0):.1f}%

效率损失分析：
- 理论最高效率: 100%
- 实际综合效率: {summary.get('overall_efficiency', 0):.1f}%
- 效率损失: {100 - summary.get('overall_efficiency', 0):.1f}%

================================================================================
4. 成本驱动因素
================================================================================

主要成本构成（按重要性排序）：
1. MTJ生产运营成本 - 占总成本的主要部分
2. 短缺惩罚成本 - 显著影响平准化成本
3. MTJ工厂建设投资 - 重要的一次性投资
4. 运输和物流成本 - 包括多种运输方式

================================================================================
5. 关键发现与建议
================================================================================

关键发现：
1. 短缺惩罚成本对总成本影响巨大，是优化的重点领域
2. 氢气生产效率有提升空间，当前综合效率为{summary.get('overall_efficiency', 0):.1f}%
3. MTJ单位成本明显高于氢气单位成本，反映了转化过程的复杂性

优化建议：
1. 重点关注需求-供应平衡，减少短缺惩罚
2. 提升电解制氢和MTJ转化效率
3. 优化运输路径和储存策略
4. 考虑规模效应降低单位成本

================================================================================
6. 生成的可视化文件
================================================================================
"""
            
            # 添加生成文件列表
            files = report_results.get('generated_files', {})
            if files:
                report_content += "\n生成的图表和文件：\n"
                for file_type, file_path in files.items():
                    if file_path and os.path.exists(file_path):
                        report_content += f"- {file_type}: {os.path.basename(file_path)}\n"
            
            report_content += f"\n报告生成完毕 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            
            # 保存文本报告
            report_file = self.results_dir / 'reports' / f'cost_analysis_report_{self.timestamp}.txt'
            report_file.parent.mkdir(exist_ok=True)
            
            with open(report_file, 'w', encoding='utf-8') as f:
                f.write(report_content)
            
            logger.info(f"文本报告已保存: {report_file}")
            return str(report_file)
            
        except Exception as e:
            logger.error(f"生成文本报告失败: {e}")
            return ""


def create_cost_visualization_engine(results_dir: str = None) -> CostVisualizationEngine:
    """
    创建成本可视化引擎实例
    
    Args:
        results_dir: 结果目录路径
        
    Returns:
        CostVisualizationEngine实例
    """
    return CostVisualizationEngine(results_dir)


# 主函数用于测试
if __name__ == "__main__":
    # 示例用法
    engine = create_cost_visualization_engine(
        "products/supply_chain_optimization/natural_gas_supply_chain_optimization/results"
    )
    
    # 加载数据
    if engine.load_optimization_data():
        # 生成综合报告
        results = engine.generate_comprehensive_report()
        print(f"报告生成完成，生成了 {len(results.get('generated_files', {}))} 个文件")
    else:
        print("数据加载失败")