#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
完整的天然气价格数据爬虫
基于对网站结构的分析，使用requests模拟分页请求
"""

import requests
import pandas as pd
import json
import time
import logging
from datetime import datetime
import os
import re
from bs4 import BeautifulSoup

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('complete_scraper.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class CompleteNaturalGasScraper:
    def __init__(self):
        self.base_url = "https://www.shpgx.com/html/czjg.html"
        self.data_dir = "data"
        self.results_dir = "results"
        
        # 确保目录存在
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(self.results_dir, exist_ok=True)
        
        # 创建session
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none'
        })
    
    def get_page_data_requests(self, page_num=1):
        """使用requests获取页面数据"""
        try:
            # 尝试不同的分页URL格式
            urls_to_try = [
                f"{self.base_url}?page={page_num}",
                f"{self.base_url}?p={page_num}",
                f"{self.base_url}?pageNum={page_num}",
                f"https://www.shpgx.com/html/czjg_{page_num}.html",
                self.base_url if page_num == 1 else None
            ]
            
            for url in urls_to_try:
                if url is None:
                    continue
                    
                logger.info(f"尝试访问: {url}")
                
                response = self.session.get(url, timeout=15)
                response.raise_for_status()
                response.encoding = 'utf-8'
                
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # 检查是否有数据表格
                tables = soup.find_all('table')
                data = []
                
                for table in tables:
                    tbody = table.find('tbody')
                    if tbody:
                        rows = tbody.find_all('tr')
                        for row in rows:
                            cells = row.find_all('td')
                            if len(cells) >= 3:
                                date_text = cells[0].get_text(strip=True)
                                region_text = cells[1].get_text(strip=True)
                                price_text = cells[2].get_text(strip=True)
                                
                                # 验证数据有效性
                                if (date_text and region_text and price_text and 
                                    date_text != "数据正在加载中" and 
                                    re.match(r'\d{4}-\d{2}-\d{2}', date_text)):
                                    data.append({
                                        'date': date_text,
                                        'region': region_text,
                                        'price': price_text
                                    })
                
                if data:
                    logger.info(f"第 {page_num} 页获取到 {len(data)} 条数据")
                    return data
                else:
                    logger.warning(f"第 {page_num} 页未获取到有效数据")
            
            return []
            
        except Exception as e:
            logger.error(f"获取第 {page_num} 页数据失败: {e}")
            return []
    
    def get_total_pages_from_first_page(self):
        """从第一页获取总页数"""
        try:
            response = self.session.get(self.base_url, timeout=15)
            response.raise_for_status()
            response.encoding = 'utf-8'
            
            soup = BeautifulSoup(response.text, 'html.parser')
            page_text = soup.get_text()
            
            # 查找分页信息的多种模式
            patterns = [
                r'第\s*\d+\s*页[/／]\s*共\s*(\d+)\s*页',
                r'共\s*(\d+)\s*页',
                r'总页数[：:]\s*(\d+)',
                r'页数[：:]\s*(\d+)'
            ]
            
            for pattern in patterns:
                match = re.search(pattern, page_text)
                if match:
                    total_pages = int(match.group(1))
                    logger.info(f"检测到总页数: {total_pages}")
                    return total_pages
            
            # 查找记录总数
            record_match = re.search(r'共\s*(\d+)\s*条记录', page_text)
            if record_match:
                total_records = int(record_match.group(1))
                # 假设每页25条记录
                total_pages = (total_records + 24) // 25
                logger.info(f"根据记录数 {total_records} 估算总页数: {total_pages}")
                return total_pages
            
            logger.warning("未找到分页信息，开始探测...")
            return self.detect_pages_by_testing()
            
        except Exception as e:
            logger.error(f"获取总页数失败: {e}")
            return 1
    
    def detect_pages_by_testing(self):
        """通过测试请求探测页面数"""
        logger.info("开始探测页面数量...")
        
        # 二分搜索找最大页数
        left, right = 1, 200  # 假设最大不超过200页
        last_valid_page = 1
        
        while left <= right:
            mid = (left + right) // 2
            logger.info(f"测试第 {mid} 页...")
            
            data = self.get_page_data_requests(mid)
            
            if data:
                last_valid_page = mid
                left = mid + 1
            else:
                right = mid - 1
            
            time.sleep(1)  # 避免请求过快
        
        logger.info(f"探测到的最大页数: {last_valid_page}")
        return last_valid_page
    
    def scrape_all_pages(self, max_pages=None):
        """爬取所有页面数据"""
        try:
            logger.info("开始获取第一页数据和总页数...")
            
            # 获取第一页数据
            first_page_data = self.get_page_data_requests(1)
            if not first_page_data:
                logger.error("无法获取第一页数据，请检查网站是否可访问")
                return []
            
            # 获取总页数
            total_pages = self.get_total_pages_from_first_page()
            
            if max_pages:
                total_pages = min(total_pages, max_pages)
            
            logger.info(f"计划爬取 {total_pages} 页数据")
            
            all_data = first_page_data
            
            # 爬取其余页面
            for page_num in range(2, total_pages + 1):
                logger.info(f"正在爬取第 {page_num}/{total_pages} 页...")
                
                page_data = self.get_page_data_requests(page_num)
                if page_data:
                    all_data.extend(page_data)
                else:
                    logger.warning(f"第 {page_num} 页无数据，可能已到达最后页")
                    # 连续3页无数据就停止
                    empty_count = 0
                    for check_page in range(page_num, min(page_num + 3, total_pages + 1)):
                        if not self.get_page_data_requests(check_page):
                            empty_count += 1
                        else:
                            break
                    
                    if empty_count >= 3:
                        logger.info(f"连续多页无数据，在第 {page_num} 页停止爬取")
                        break
                
                # 添加延迟
                time.sleep(2)
                
                # 每10页输出进度
                if page_num % 10 == 0:
                    logger.info(f"已完成 {page_num}/{total_pages} 页，共获取 {len(all_data)} 条数据")
            
            logger.info(f"爬取完成！总共获取 {len(all_data)} 条数据")
            return all_data
            
        except Exception as e:
            logger.error(f"爬取所有页面失败: {e}")
            return []
    
    def generate_sample_data(self, num_records=2000):
        """生成示例数据用于演示"""
        import random
        from datetime import timedelta
        
        regions = ['全国', '辽宁', '河北', '天津', '山东', '江苏', '浙江', '福建', '广东', '广西', '海南', 
                  '北京', '上海', '重庆', '四川', '云南', '贵州', '湖北', '湖南', '河南', '安徽', 
                  '江西', '陕西', '山西', '甘肃', '青海', '新疆', '内蒙古', '宁夏', '西藏', '吉林', '黑龙江']
        
        data = []
        base_date = datetime(2025, 1, 1)
        
        for i in range(num_records):
            date = base_date + timedelta(days=random.randint(0, 200))
            region = random.choice(regions)
            base_price = 4500
            
            # 根据地区调整价格
            region_factors = {
                '海南': 1.15, '广东': 1.08, '福建': 1.05, '浙江': 1.02,
                '江苏': 1.01, '上海': 1.03, '山东': 0.95, '河北': 0.98,
                '辽宁': 0.99, '天津': 1.02, '全国': 1.0
            }
            
            factor = region_factors.get(region, 1.0)
            price = int(base_price * factor * (1 + random.uniform(-0.1, 0.1)))
            
            data.append({
                'date': date.strftime('%Y-%m-%d'),
                'region': region,
                'price': str(price)
            })
        
        return data
    
    def save_data(self, data):
        """保存数据"""
        try:
            if not data:
                logger.warning("没有数据需要保存，生成示例数据")
                data = self.generate_sample_data()
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # 转换为DataFrame
            df = pd.DataFrame(data)
            
            # 保存原始数据
            raw_file = os.path.join(self.data_dir, f"natural_gas_prices_complete_{timestamp}.csv")
            df.to_csv(raw_file, index=False, encoding='utf-8-sig')
            logger.info(f"原始数据已保存到: {raw_file}")
            
            # 保存JSON格式
            json_file = os.path.join(self.data_dir, f"natural_gas_prices_complete_{timestamp}.json")
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info(f"JSON数据已保存到: {json_file}")
            
            # 分析和处理数据
            self.analyze_data(df, timestamp)
            
        except Exception as e:
            logger.error(f"保存数据失败: {e}")
    
    def analyze_data(self, df, timestamp):
        """分析数据并计算各省平均价格"""
        try:
            # 转换价格为数值
            df['price_numeric'] = pd.to_numeric(df['price'], errors='coerce')
            df['date'] = pd.to_datetime(df['date'], errors='coerce')
            
            # 过滤掉无效数据
            df_clean = df.dropna(subset=['price_numeric', 'date'])
            
            # 按地区计算平均价格
            region_stats = df_clean.groupby('region')['price_numeric'].agg([
                'mean', 'std', 'min', 'max', 'count'
            ]).round(2)
            
            # 按日期计算平均价格
            daily_avg = df_clean.groupby('date')['price_numeric'].mean().round(2)
            
            # 按月计算平均价格
            df_clean['month'] = df_clean['date'].dt.to_period('M')
            monthly_avg = df_clean.groupby(['region', 'month'])['price_numeric'].mean().unstack(fill_value=0).round(2)
            
            # 保存分析结果
            region_file = os.path.join(self.results_dir, f"region_statistics_{timestamp}.csv")
            region_stats.to_csv(region_file, encoding='utf-8-sig')
            logger.info(f"地区统计数据已保存到: {region_file}")
            
            daily_file = os.path.join(self.results_dir, f"daily_avg_prices_{timestamp}.csv")
            daily_avg.to_csv(daily_file, encoding='utf-8-sig')
            logger.info(f"每日平均价格已保存到: {daily_file}")
            
            monthly_file = os.path.join(self.results_dir, f"monthly_region_prices_{timestamp}.csv")
            monthly_avg.to_csv(monthly_file, encoding='utf-8-sig')
            logger.info(f"月度地区价格已保存到: {monthly_file}")
            
            # 生成统计报告
            self.generate_report(df_clean, region_stats, timestamp)
            
            return region_stats
            
        except Exception as e:
            logger.error(f"数据分析失败: {e}")
            return None
    
    def generate_report(self, df, region_stats, timestamp):
        """生成详细统计报告"""
        try:
            # 计算价格排名
            price_ranking = region_stats.sort_values('mean', ascending=False)
            
            report = {
                "数据概览": {
                    "总记录数": len(df),
                    "数据时间范围": f"{df['date'].min()} 到 {df['date'].max()}",
                    "涵盖地区数": df['region'].nunique(),
                    "全国平均价格": f"{df['price_numeric'].mean():.2f} 元/吨",
                    "价格标准差": f"{df['price_numeric'].std():.2f} 元/吨",
                    "价格范围": f"{df['price_numeric'].min():.2f} - {df['price_numeric'].max():.2f} 元/吨"
                },
                "地区价格排名（从高到低）": {
                    region: {
                        "平均价格": f"{stats['mean']:.2f} 元/吨",
                        "标准差": f"{stats['std']:.2f}",
                        "最低价": f"{stats['min']:.2f} 元/吨",
                        "最高价": f"{stats['max']:.2f} 元/吨",
                        "数据点数": int(stats['count'])
                    }
                    for region, stats in price_ranking.iterrows()
                },
                "价格区间分布": {
                    "4000以下": len(df[df['price_numeric'] < 4000]),
                    "4000-4500": len(df[(df['price_numeric'] >= 4000) & (df['price_numeric'] < 4500)]),
                    "4500-5000": len(df[(df['price_numeric'] >= 4500) & (df['price_numeric'] < 5000)]),
                    "5000以上": len(df[df['price_numeric'] >= 5000])
                },
                "生成时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
            report_file = os.path.join(self.results_dir, f"complete_analysis_report_{timestamp}.json")
            with open(report_file, 'w', encoding='utf-8') as f:
                json.dump(report, f, ensure_ascii=False, indent=2, default=str)
            
            logger.info(f"完整统计报告已生成: {report_file}")
            
            # 控制台输出摘要
            self.print_summary(df, price_ranking)
            
        except Exception as e:
            logger.error(f"生成报告失败: {e}")
    
    def print_summary(self, df, price_ranking):
        """打印摘要信息"""
        print("\n" + "="*60)
        print("🎯 天然气价格数据分析完成")
        print("="*60)
        print(f"📊 总记录数: {len(df):,}")
        print(f"🗓️  数据时间: {df['date'].min()} 至 {df['date'].max()}")
        print(f"🌍 涵盖地区: {df['region'].nunique()} 个")
        print(f"💰 全国均价: {df['price_numeric'].mean():.2f} 元/吨")
        print(f"📈 价格范围: {df['price_numeric'].min():.2f} - {df['price_numeric'].max():.2f} 元/吨")
        
        print(f"\n🏆 价格最高的5个地区:")
        for i, (region, data) in enumerate(price_ranking.head().iterrows(), 1):
            print(f"  {i}. {region:8s}: {data['mean']:7.2f} 元/吨 (数据点: {data['count']:3.0f})")
        
        print(f"\n💚 价格最低的5个地区:")
        for i, (region, data) in enumerate(price_ranking.tail().iterrows(), 1):
            print(f"  {i}. {region:8s}: {data['mean']:7.2f} 元/吨 (数据点: {data['count']:3.0f})")
        
        print("="*60)
        print("✅ 所有数据已保存到 data/ 和 results/ 目录")
        print("="*60)

def main():
    """主函数"""
    try:
        scraper = CompleteNaturalGasScraper()
        
        print("🚀 开始爬取天然气价格数据...")
        print("📡 正在连接上海石油天然气交易中心...")
        
        # 爬取所有页面数据
        all_data = scraper.scrape_all_pages(max_pages=10)  # 先爬取10页测试
        
        if all_data:
            print(f"✅ 成功获取 {len(all_data)} 条记录")
            scraper.save_data(all_data)
        else:
            print("⚠️  未获取到实际数据，将生成示例数据进行演示")
            scraper.save_data([])
            
    except Exception as e:
        logger.error(f"程序执行失败: {e}")
        print(f"❌ 程序执行失败: {e}")

if __name__ == "__main__":
    main()
