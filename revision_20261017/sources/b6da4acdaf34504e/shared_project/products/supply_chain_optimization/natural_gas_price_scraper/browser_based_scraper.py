#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基于浏览器的天然气价格数据爬虫
使用Selenium模拟浏览器操作来获取完整的数据
"""

import time
import pandas as pd
import json
import logging
from datetime import datetime
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import re

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('browser_scraper.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class BrowserNaturalGasScraper:
    def __init__(self):
        self.base_url = "https://www.shpgx.com/html/czjg.html"
        self.data_dir = "data"
        self.results_dir = "results"
        
        # 确保目录存在
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(self.results_dir, exist_ok=True)
        
        # 初始化浏览器
        self.driver = None
        self.init_browser()
        
    def init_browser(self):
        """初始化浏览器"""
        try:
            chrome_options = Options()
            chrome_options.add_argument('--headless')  # 无头模式
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--window-size=1920,1080')
            chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')
            
            self.driver = webdriver.Chrome(options=chrome_options)
            self.driver.implicitly_wait(10)
            
            logger.info("浏览器初始化成功")
            
        except Exception as e:
            logger.error(f"浏览器初始化失败: {e}")
            raise
    
    def get_page_data(self, page_num=1):
        """获取指定页面的数据"""
        try:
            # 如果是第一页，直接访问
            if page_num == 1:
                self.driver.get(self.base_url)
                # 等待表格加载
                WebDriverWait(self.driver, 15).until(
                    EC.presence_of_element_located((By.TAG_NAME, "table"))
                )
                time.sleep(3)  # 等待AJAX加载
            else:
                # 导航到指定页面
                self.navigate_to_page(page_num)
            
            # 提取表格数据
            data = self.extract_table_data()
            logger.info(f"第 {page_num} 页获取到 {len(data)} 条数据")
            return data
            
        except Exception as e:
            logger.error(f"获取第 {page_num} 页数据失败: {e}")
            return []
    
    def navigate_to_page(self, page_num):
        """导航到指定页面"""
        try:
            # 方法1: 输入页码到输入框并回车
            page_input = self.driver.find_element(By.XPATH, "//input[@type='text']")
            page_input.clear()
            page_input.send_keys(str(page_num))
            page_input.send_keys("\n")
            
            time.sleep(3)  # 等待页面加载
            
        except Exception as e:
            logger.warning(f"方法1导航失败，尝试方法2: {e}")
            try:
                # 方法2: 多次点击下一页
                current_page = 1
                while current_page < page_num:
                    next_button = self.driver.find_element(By.LINK_TEXT, "下一页")
                    if next_button.get_attribute("href") == "javascript:void(0);":
                        break  # 已到最后一页
                    next_button.click()
                    time.sleep(2)
                    current_page += 1
                    
            except Exception as e2:
                logger.error(f"方法2导航也失败: {e2}")
                raise
    
    def extract_table_data(self):
        """提取表格数据"""
        try:
            # 等待表格数据加载
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "tbody"))
            )
            
            # 查找表格
            table = self.driver.find_element(By.TAG_NAME, "table")
            tbody = table.find_element(By.TAG_NAME, "tbody")
            rows = tbody.find_elements(By.TAG_NAME, "tr")
            
            data = []
            for row in rows:
                cells = row.find_elements(By.TAG_NAME, "td")
                if len(cells) >= 3:
                    row_data = {
                        'date': cells[0].text.strip(),
                        'region': cells[1].text.strip(),
                        'price': cells[2].text.strip()
                    }
                    if row_data['date'] and row_data['region'] and row_data['price']:
                        data.append(row_data)
            
            return data
            
        except Exception as e:
            logger.error(f"提取表格数据失败: {e}")
            return []
    
    def get_total_pages(self):
        """获取总页数"""
        try:
            # 查找分页信息
            pagination_text = self.driver.page_source
            
            # 查找 "第X页/共Y页" 模式
            page_match = re.search(r'第\s*\d+\s*页[/／]\s*共\s*(\d+)\s*页', pagination_text)
            if page_match:
                total_pages = int(page_match.group(1))
                logger.info(f"检测到总页数: {total_pages}")
                return total_pages
            
            # 查找记录总数
            record_match = re.search(r'共\s*(\d+)\s*条记录', pagination_text)
            if record_match:
                total_records = int(record_match.group(1))
                # 假设每页25条记录
                total_pages = (total_records + 24) // 25
                logger.info(f"根据记录数 {total_records} 估算总页数: {total_pages}")
                return total_pages
            
            logger.warning("未找到分页信息，默认返回1页")
            return 1
            
        except Exception as e:
            logger.error(f"获取总页数失败: {e}")
            return 1
    
    def scrape_all_pages(self, max_pages=None):
        """爬取所有页面的数据"""
        try:
            # 访问第一页并获取总页数
            logger.info("正在获取第一页数据...")
            first_page_data = self.get_page_data(1)
            total_pages = self.get_total_pages()
            
            if max_pages:
                total_pages = min(total_pages, max_pages)
            
            logger.info(f"计划爬取 {total_pages} 页数据")
            
            all_data = first_page_data
            
            # 爬取其余页面
            for page_num in range(2, total_pages + 1):
                logger.info(f"正在爬取第 {page_num}/{total_pages} 页...")
                page_data = self.get_page_data(page_num)
                all_data.extend(page_data)
                
                # 添加延迟避免请求过快
                time.sleep(2)
                
                # 每10页输出一次进度
                if page_num % 10 == 0:
                    logger.info(f"已完成 {page_num}/{total_pages} 页，共获取 {len(all_data)} 条数据")
            
            logger.info(f"爬取完成！总共获取 {len(all_data)} 条数据")
            return all_data
            
        except Exception as e:
            logger.error(f"爬取所有页面失败: {e}")
            return []
    
    def save_data(self, data):
        """保存数据"""
        try:
            if not data:
                logger.warning("没有数据需要保存")
                return
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # 转换为DataFrame
            df = pd.DataFrame(data)
            
            # 保存原始数据
            raw_file = os.path.join(self.data_dir, f"natural_gas_prices_raw_{timestamp}.csv")
            df.to_csv(raw_file, index=False, encoding='utf-8-sig')
            logger.info(f"原始数据已保存到: {raw_file}")
            
            # 保存JSON格式
            json_file = os.path.join(self.data_dir, f"natural_gas_prices_raw_{timestamp}.json")
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
            region_avg = df_clean.groupby('region')['price_numeric'].agg([
                'mean', 'std', 'min', 'max', 'count'
            ]).round(2)
            
            # 按日期计算平均价格
            date_avg = df_clean.groupby('date')['price_numeric'].mean().round(2)
            
            # 保存分析结果
            region_file = os.path.join(self.results_dir, f"region_avg_prices_{timestamp}.csv")
            region_avg.to_csv(region_file, encoding='utf-8-sig')
            logger.info(f"地区平均价格已保存到: {region_file}")
            
            date_file = os.path.join(self.results_dir, f"daily_avg_prices_{timestamp}.csv")
            date_avg.to_csv(date_file, encoding='utf-8-sig')
            logger.info(f"每日平均价格已保存到: {date_file}")
            
            # 生成统计报告
            self.generate_report(df_clean, region_avg, timestamp)
            
        except Exception as e:
            logger.error(f"数据分析失败: {e}")
    
    def generate_report(self, df, region_avg, timestamp):
        """生成统计报告"""
        try:
            report = {
                "数据统计摘要": {
                    "总记录数": len(df),
                    "数据时间范围": f"{df['date'].min()} 到 {df['date'].max()}",
                    "涵盖地区数": df['region'].nunique(),
                    "平均价格": f"{df['price_numeric'].mean():.2f} 元/吨",
                    "价格波动范围": f"{df['price_numeric'].min():.2f} - {df['price_numeric'].max():.2f} 元/吨"
                },
                "各地区平均价格排名": region_avg.sort_values('mean', ascending=False).to_dict('index'),
                "生成时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
            report_file = os.path.join(self.results_dir, f"analysis_report_{timestamp}.json")
            with open(report_file, 'w', encoding='utf-8') as f:
                json.dump(report, f, ensure_ascii=False, indent=2, default=str)
            
            logger.info(f"统计报告已生成: {report_file}")
            
            # 打印摘要
            print("\n" + "="*50)
            print("天然气价格数据爬取完成")
            print("="*50)
            print(f"总记录数: {len(df)}")
            print(f"涵盖地区数: {df['region'].nunique()}")
            print(f"平均价格: {df['price_numeric'].mean():.2f} 元/吨")
            print(f"价格范围: {df['price_numeric'].min():.2f} - {df['price_numeric'].max():.2f} 元/吨")
            print("\n前5个最高价格地区:")
            top5 = region_avg.sort_values('mean', ascending=False).head()
            for region, data in top5.iterrows():
                print(f"  {region}: {data['mean']:.2f} 元/吨")
            print("="*50)
            
        except Exception as e:
            logger.error(f"生成报告失败: {e}")
    
    def close(self):
        """关闭浏览器"""
        if self.driver:
            self.driver.quit()
            logger.info("浏览器已关闭")

def main():
    """主函数"""
    scraper = None
    try:
        scraper = BrowserNaturalGasScraper()
        
        # 爬取所有页面数据
        print("开始爬取天然气价格数据...")
        all_data = scraper.scrape_all_pages(max_pages=5)  # 先爬取5页测试
        
        if all_data:
            scraper.save_data(all_data)
        else:
            print("没有获取到任何数据")
            
    except Exception as e:
        logger.error(f"程序执行失败: {e}")
        print(f"程序执行失败: {e}")
        
    finally:
        if scraper:
            scraper.close()

if __name__ == "__main__":
    main()
