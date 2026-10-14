#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
天然气价格数据爬虫
从上海石油天然气交易中心爬取天然气出站价格数据
"""

import requests
import pandas as pd
import numpy as np
from bs4 import BeautifulSoup
import time
import json
import logging
from datetime import datetime
import os
import re

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('natural_gas_scraper.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class NaturalGasPriceScraper:
    def __init__(self):
        self.base_url = "https://www.shpgx.com/html/czjg.html"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })
        self.data_dir = "data"
        self.results_dir = "results"
        
        # 确保目录存在
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(self.results_dir, exist_ok=True)
        
        # 中国省份列表
        self.provinces = [
            '北京', '天津', '河北', '山西', '内蒙古', '辽宁', '吉林', '黑龙江',
            '上海', '江苏', '浙江', '安徽', '福建', '江西', '山东', '河南',
            '湖北', '湖南', '广东', '广西', '海南', '重庆', '四川', '贵州',
            '云南', '西藏', '陕西', '甘肃', '青海', '宁夏', '新疆'
        ]

    def get_page_content(self, url, page=1):
        """获取页面内容"""
        try:
            if page > 1:
                # 构造分页URL
                url = f"{url}?page={page}"
            
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            response.encoding = 'utf-8'
            
            logger.info(f"成功获取页面内容: {url}")
            return response.text
            
        except requests.RequestException as e:
            logger.error(f"请求失败: {url}, 错误: {e}")
            return None

    def parse_price_data(self, html_content):
        """解析价格数据"""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # 查找价格表格
            price_data = []
            
            # 尝试多种表格选择器
            tables = soup.find_all('table')
            
            for table in tables:
                rows = table.find_all('tr')
                for row in rows[1:]:  # 跳过表头
                    cells = row.find_all(['td', 'th'])
                    if len(cells) >= 3:  # 确保有足够的列
                        row_data = [cell.get_text(strip=True) for cell in cells]
                        if any(province in str(row_data) for province in self.provinces):
                            price_data.append(row_data)
            
            # 如果没有找到表格，尝试查找其他包含价格信息的元素
            if not price_data:
                # 查找包含价格信息的div或其他元素
                price_elements = soup.find_all(['div', 'span', 'p'], text=re.compile(r'[\d.]+元'))
                for element in price_elements:
                    text = element.get_text(strip=True)
                    # 提取价格相关信息
                    if any(province in text for province in self.provinces):
                        price_data.append([text])
            
            logger.info(f"解析到 {len(price_data)} 条价格数据")
            return price_data
            
        except Exception as e:
            logger.error(f"解析HTML内容失败: {e}")
            return []

    def scrape_all_pages(self, max_pages=10):
        """爬取所有页面的数据"""
        all_data = []
        
        for page in range(1, max_pages + 1):
            logger.info(f"正在爬取第 {page} 页...")
            
            html_content = self.get_page_content(self.base_url, page)
            if not html_content:
                logger.warning(f"第 {page} 页获取失败")
                continue
            
            page_data = self.parse_price_data(html_content)
            if not page_data:
                logger.info(f"第 {page} 页没有找到数据，可能已到达最后一页")
                break
            
            all_data.extend(page_data)
            
            # 添加延迟避免过于频繁的请求
            time.sleep(2)
        
        return all_data

    def process_and_analyze_data(self, raw_data):
        """处理和分析数据"""
        try:
            # 创建DataFrame
            if not raw_data:
                logger.warning("没有数据可供处理")
                return None
            
            # 根据数据结构创建DataFrame
            df = pd.DataFrame(raw_data)
            
            # 保存原始数据
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            raw_file = os.path.join(self.data_dir, f"raw_natural_gas_prices_{timestamp}.csv")
            df.to_csv(raw_file, index=False, encoding='utf-8-sig')
            logger.info(f"原始数据已保存到: {raw_file}")
            
            # 数据清洗和处理
            processed_data = self.clean_and_process_data(df)
            
            # 计算省份均值
            province_averages = self.calculate_province_averages(processed_data)
            
            return province_averages
            
        except Exception as e:
            logger.error(f"数据处理失败: {e}")
            return None

    def clean_and_process_data(self, df):
        """清洗和处理数据"""
        try:
            processed_data = []
            
            for _, row in df.iterrows():
                row_text = ' '.join(str(cell) for cell in row if pd.notna(cell))
                
                # 提取省份信息
                province = None
                for prov in self.provinces:
                    if prov in row_text:
                        province = prov
                        break
                
                # 提取价格信息（查找数字+元的模式）
                price_matches = re.findall(r'(\d+\.?\d*)\s*元', row_text)
                prices = [float(price) for price in price_matches if float(price) > 0]
                
                if province and prices:
                    for price in prices:
                        processed_data.append({
                            'province': province,
                            'price': price,
                            'raw_text': row_text
                        })
            
            return pd.DataFrame(processed_data)
            
        except Exception as e:
            logger.error(f"数据清洗失败: {e}")
            return pd.DataFrame()

    def calculate_province_averages(self, df):
        """计算各省份天然气价格均值"""
        try:
            if df.empty:
                logger.warning("没有有效数据计算均值")
                return pd.DataFrame()
            
            # 按省份分组计算统计信息
            province_stats = df.groupby('province')['price'].agg([
                'mean', 'median', 'std', 'min', 'max', 'count'
            ]).round(2)
            
            province_stats.columns = ['均价', '中位数', '标准差', '最低价', '最高价', '数据点数']
            province_stats = province_stats.reset_index()
            province_stats.rename(columns={'province': '省份'}, inplace=True)
            
            # 按均价排序
            province_stats = province_stats.sort_values('均价', ascending=False)
            
            return province_stats
            
        except Exception as e:
            logger.error(f"计算省份均值失败: {e}")
            return pd.DataFrame()

    def save_results(self, province_averages):
        """保存结果"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # 保存Excel文件
            excel_file = os.path.join(self.results_dir, f"省份天然气价格统计_{timestamp}.xlsx")
            province_averages.to_excel(excel_file, index=False, engine='openpyxl')
            logger.info(f"Excel结果已保存到: {excel_file}")
            
            # 保存CSV文件
            csv_file = os.path.join(self.results_dir, f"省份天然气价格统计_{timestamp}.csv")
            province_averages.to_csv(csv_file, index=False, encoding='utf-8-sig')
            logger.info(f"CSV结果已保存到: {csv_file}")
            
            # 保存JSON文件
            json_file = os.path.join(self.results_dir, f"省份天然气价格统计_{timestamp}.json")
            province_averages.to_json(json_file, orient='records', force_ascii=False, indent=2)
            logger.info(f"JSON结果已保存到: {json_file}")
            
            return excel_file, csv_file, json_file
            
        except Exception as e:
            logger.error(f"保存结果失败: {e}")
            return None, None, None

    def generate_summary_report(self, province_averages):
        """生成汇总报告"""
        try:
            if province_averages.empty:
                return "没有数据生成报告"
            
            report = []
            report.append("=" * 60)
            report.append("全国天然气价格统计报告")
            report.append("=" * 60)
            report.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            report.append(f"数据来源: 上海石油天然气交易中心")
            report.append("")
            
            # 基本统计
            report.append("基本统计信息:")
            report.append(f"  统计省份数量: {len(province_averages)}")
            report.append(f"  全国均价: {province_averages['均价'].mean():.2f} 元/立方米")
            report.append(f"  价格中位数: {province_averages['均价'].median():.2f} 元/立方米")
            report.append(f"  价格标准差: {province_averages['均价'].std():.2f}")
            report.append(f"  最高均价: {province_averages['均价'].max():.2f} 元/立方米")
            report.append(f"  最低均价: {province_averages['均价'].min():.2f} 元/立方米")
            report.append("")
            
            # 价格排名前10
            report.append("价格排名前10的省份:")
            top_10 = province_averages.head(10)
            for i, (_, row) in enumerate(top_10.iterrows(), 1):
                report.append(f"  {i:2d}. {row['省份']:8s} {row['均价']:6.2f} 元/立方米")
            report.append("")
            
            # 价格排名后10
            report.append("价格排名后10的省份:")
            bottom_10 = province_averages.tail(10)
            for i, (_, row) in enumerate(bottom_10.iterrows(), 1):
                report.append(f"  {i:2d}. {row['省份']:8s} {row['均价']:6.2f} 元/立方米")
            
            report_text = "\n".join(report)
            
            # 保存报告
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            report_file = os.path.join(self.results_dir, f"天然气价格统计报告_{timestamp}.txt")
            with open(report_file, 'w', encoding='utf-8') as f:
                f.write(report_text)
            
            logger.info(f"统计报告已保存到: {report_file}")
            return report_text
            
        except Exception as e:
            logger.error(f"生成报告失败: {e}")
            return "报告生成失败"

    def run(self):
        """运行爬虫"""
        logger.info("开始爬取天然气价格数据...")
        
        try:
            # 爬取数据
            raw_data = self.scrape_all_pages(max_pages=20)
            
            if not raw_data:
                logger.error("未能获取到任何数据")
                return
            
            # 处理数据
            province_averages = self.process_and_analyze_data(raw_data)
            
            if province_averages is None or province_averages.empty:
                logger.error("数据处理失败或没有有效数据")
                return
            
            # 保存结果
            excel_file, csv_file, json_file = self.save_results(province_averages)
            
            # 生成报告
            report = self.generate_summary_report(province_averages)
            print("\n" + report)
            
            logger.info("爬虫运行完成!")
            logger.info(f"共处理 {len(province_averages)} 个省份的数据")
            
        except Exception as e:
            logger.error(f"爬虫运行失败: {e}")

def main():
    """主函数"""
    scraper = NaturalGasPriceScraper()
    scraper.run()

if __name__ == "__main__":
    main()
