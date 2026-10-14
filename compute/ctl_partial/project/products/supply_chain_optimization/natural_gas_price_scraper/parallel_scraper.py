#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
并行天然气价格数据爬虫 - 使用多进程并行爬取所有页面
"""

import time
import pandas as pd
import json
import logging
from datetime import datetime
import os
import re
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from multiprocessing import Pool, Manager, cpu_count
import math
from functools import partial

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(processName)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('parallel_scraper.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class ParallelNaturalGasScraper:
    def __init__(self):
        self.base_url = "https://www.shpgx.com/html/czjg.html"
        
        # 确保目录存在
        os.makedirs('data', exist_ok=True)
        os.makedirs('results', exist_ok=True)
        
    def setup_driver(self):
        """设置Chrome浏览器driver"""
        try:
            chrome_options = Options()
            chrome_options.add_argument('--headless')  # 无头模式，提高性能
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--disable-images')  # 禁用图片加载
            chrome_options.add_argument('--disable-javascript')  # 禁用JavaScript（如果不影响数据加载）
            chrome_options.add_argument('--window-size=1920,1080')
            chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
            
            # 禁用日志输出
            chrome_options.add_argument('--disable-logging')
            chrome_options.add_argument('--log-level=3')
            chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            
            driver = webdriver.Chrome(options=chrome_options)
            return driver
            
        except Exception as e:
            logger.error(f"设置Chrome driver失败: {e}")
            return None
    
    def scrape_single_page(self, page_num, shared_results):
        """爬取单个页面的数据"""
        driver = None
        try:
            logger.info(f"开始爬取第 {page_num} 页")
            
            driver = self.setup_driver()
            if not driver:
                logger.error(f"第 {page_num} 页: 无法设置driver")
                return
            
            wait = WebDriverWait(driver, 30)
            
            # 访问网站
            driver.get(self.base_url)
            time.sleep(5)  # 等待页面加载
            
            # 如果不是第一页，需要导航到指定页面
            if page_num > 1:
                try:
                    # 找到页码输入框
                    page_input = driver.find_element(By.XPATH, "//input[@type='text']")
                    page_input.clear()
                    page_input.send_keys(str(page_num))
                    
                    # 按回车或点击跳转
                    page_input.send_keys("\n")
                    time.sleep(3)
                except Exception as e:
                    logger.warning(f"第 {page_num} 页: 无法直接跳转，尝试点击方式")
                    # 如果直接跳转失败，使用点击下一页的方式
                    current_page = 1
                    while current_page < page_num:
                        try:
                            next_button = driver.find_element(By.XPATH, "//a[contains(text(), '下一页')]")
                            if next_button.is_enabled():
                                driver.execute_script("arguments[0].click();", next_button)
                                time.sleep(2)
                                current_page += 1
                            else:
                                break
                        except:
                            break
            
            # 等待表格加载
            time.sleep(3)
            
            # 获取表格数据
            table = driver.find_element(By.CSS_SELECTOR, "table")
            rows = table.find_elements(By.TAG_NAME, "tr")
            
            page_data = []
            for i, row in enumerate(rows):
                if i == 0:  # 跳过表头
                    continue
                
                cells = row.find_elements(By.TAG_NAME, "td")
                if len(cells) >= 3:
                    row_data = [cell.text.strip() for cell in cells]
                    if row_data[0] and "加载中" not in str(row_data):
                        page_data.append(row_data)
            
            # 将结果添加到共享列表
            if page_data:
                shared_results.extend(page_data)
                logger.info(f"第 {page_num} 页: 成功获取 {len(page_data)} 条数据")
            else:
                logger.warning(f"第 {page_num} 页: 未获取到数据")
                
        except Exception as e:
            logger.error(f"第 {page_num} 页爬取失败: {e}")
        
        finally:
            if driver:
                driver.quit()
    
    def get_total_pages(self):
        """获取总页数"""
        driver = None
        try:
            driver = self.setup_driver()
            if not driver:
                return 90  # 默认返回90页
            
            driver.get(self.base_url)
            time.sleep(10)
            
            # 获取页面文本
            page_text = driver.page_source
            
            # 查找分页信息
            record_match = re.search(r'共\s*(\d+)\s*条记录', page_text)
            if record_match:
                total_records = int(record_match.group(1))
                total_pages = math.ceil(total_records / 25)  # 假设每页25条记录
                logger.info(f"检测到总记录数: {total_records}，总页数: {total_pages}")
                return total_pages
            
            # 如果找不到记录数，查找页数信息
            page_match = re.search(r'共\s*(\d+)\s*页', page_text)
            if page_match:
                total_pages = int(page_match.group(1))
                logger.info(f"检测到总页数: {total_pages}")
                return total_pages
            
            logger.warning("未找到分页信息，使用默认值90页")
            return 90
            
        except Exception as e:
            logger.error(f"获取总页数失败: {e}")
            return 90
        
        finally:
            if driver:
                driver.quit()
    
    def parallel_scrape_all_pages(self, num_cores=20):
        """并行爬取所有页面"""
        logger.info(f"开始并行爬取，使用 {num_cores} 个进程核心")
        
        # 获取总页数
        total_pages = self.get_total_pages()
        logger.info(f"总共需要爬取 {total_pages} 页")
        
        # 创建共享列表来存储结果
        with Manager() as manager:
            shared_results = manager.list()
            
            # 创建页面编号列表
            page_numbers = list(range(1, total_pages + 1))
            
            # 创建进程池
            with Pool(processes=num_cores) as pool:
                # 创建部分函数，传入共享结果列表
                scrape_func = partial(self.scrape_single_page, shared_results=shared_results)
                
                # 启动并行爬取
                pool.map(scrape_func, page_numbers)
            
            # 转换为普通列表
            all_data = list(shared_results)
        
        logger.info(f"并行爬取完成，总共获取 {len(all_data)} 条数据")
        return all_data
    
    def save_and_process_data(self, data):
        """保存和处理数据"""
        if not data:
            logger.warning("没有数据可保存")
            return None, None
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 创建DataFrame
        df = pd.DataFrame(data, columns=['日期', '地区', '价格(元/吨)'])
        
        # 保存原始数据
        raw_file = f"data/raw_parallel_data_{timestamp}.csv"
        df.to_csv(raw_file, index=False, encoding='utf-8-sig')
        logger.info(f"原始数据已保存到: {raw_file}")
        
        # 数据清洗
        try:
            # 清洗价格数据
            df['价格数值'] = df['价格(元/吨)'].str.extract(r'(\d+\.?\d*)').astype(float)
            
            # 清洗日期
            df['日期'] = pd.to_datetime(df['日期'], errors='coerce')
            
            # 移除无效数据
            df_clean = df.dropna(subset=['价格数值'])
            
            # 计算省份均值
            province_avg = df_clean.groupby('地区')['价格数值'].agg(['mean', 'count', 'min', 'max']).reset_index()
            province_avg.columns = ['省份', '平均价格(元/吨)', '数据点数', '最低价格(元/吨)', '最高价格(元/吨)']
            province_avg = province_avg.round(2).sort_values('平均价格(元/吨)', ascending=False)
            
            # 保存处理后的数据
            processed_file = f"results/processed_parallel_data_{timestamp}.csv"
            df_clean.to_csv(processed_file, index=False, encoding='utf-8-sig')
            
            avg_file = f"results/province_average_parallel_{timestamp}.csv"
            province_avg.to_csv(avg_file, index=False, encoding='utf-8-sig')
            
            # 保存JSON格式
            json_file = f"results/province_average_parallel_{timestamp}.json"
            province_avg.to_json(json_file, orient='records', force_ascii=False, indent=2)
            
            logger.info(f"处理后数据已保存到: {processed_file}")
            logger.info(f"省份均值已保存到: {avg_file}")
            logger.info(f"JSON格式已保存到: {json_file}")
            
            # 生成详细统计报告
            self.generate_detailed_report(df_clean, province_avg, timestamp)
            
            return df_clean, province_avg
            
        except Exception as e:
            logger.error(f"数据处理失败: {e}")
            return df, None
    
    def generate_detailed_report(self, df_clean, province_avg, timestamp):
        """生成详细统计报告"""
        try:
            # 计算时间范围
            date_range = f"{df_clean['日期'].min().strftime('%Y-%m-%d')} 到 {df_clean['日期'].max().strftime('%Y-%m-%d')}"
            
            report = {
                "爬取时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "数据概览": {
                    "总数据条数": len(df_clean),
                    "地区数量": len(province_avg),
                    "数据时间范围": date_range,
                    "价格范围": f"{df_clean['价格数值'].min():.2f} - {df_clean['价格数值'].max():.2f} 元/吨",
                    "全国平均价格": f"{df_clean['价格数值'].mean():.2f} 元/吨"
                },
                "地区价格统计": {
                    "价格最高的地区": {
                        "地区": province_avg.iloc[0]['省份'],
                        "平均价格": f"{province_avg.iloc[0]['平均价格(元/吨)']} 元/吨",
                        "数据点数": int(province_avg.iloc[0]['数据点数'])
                    },
                    "价格最低的地区": {
                        "地区": province_avg.iloc[-1]['省份'],
                        "平均价格": f"{province_avg.iloc[-1]['平均价格(元/吨)']} 元/吨",
                        "数据点数": int(province_avg.iloc[-1]['数据点数'])
                    }
                },
                "完整地区排名": province_avg.to_dict('records')
            }
            
            report_file = f"results/detailed_report_parallel_{timestamp}.json"
            with open(report_file, 'w', encoding='utf-8') as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
            
            logger.info(f"详细报告已保存到: {report_file}")
            
        except Exception as e:
            logger.error(f"生成报告失败: {e}")

def main():
    """主函数"""
    logger.info("开始并行爬取天然气价格数据...")
    
    # 检查可用的CPU核心数
    available_cores = cpu_count()
    logger.info(f"系统可用CPU核心数: {available_cores}")
    
    # 使用20个核心，如果系统核心数不足则使用全部可用核心
    cores_to_use = min(20, available_cores)
    logger.info(f"将使用 {cores_to_use} 个核心进行并行爬取")
    
    scraper = ParallelNaturalGasScraper()
    
    # 记录开始时间
    start_time = time.time()
    
    # 并行爬取所有数据
    data = scraper.parallel_scrape_all_pages(num_cores=cores_to_use)
    
    # 记录结束时间
    end_time = time.time()
    duration = end_time - start_time
    
    if data:
        processed_data, province_avg = scraper.save_and_process_data(data)
        
        print(f"\n{'='*60}")
        print(f"🎉 并行爬取完成！")
        print(f"{'='*60}")
        print(f"⏱️  总耗时: {duration:.2f} 秒")
        print(f"💾 总数据条数: {len(data)}")
        print(f"🚀 使用核心数: {cores_to_use}")
        print(f"📊 平均每核心处理: {len(data)/cores_to_use:.1f} 条数据")
        
        if province_avg is not None and len(province_avg) > 0:
            print(f"🏆 地区数量: {len(province_avg)}")
            print(f"\n📈 价格最高的5个地区:")
            for i, (_, row) in enumerate(province_avg.head(5).iterrows(), 1):
                print(f"  {i}. {row['省份']}: {row['平均价格(元/吨)']} 元/吨 ({row['数据点数']}条数据)")
            
            print(f"\n📉 价格最低的5个地区:")
            for i, (_, row) in enumerate(province_avg.tail(5).iterrows(), 1):
                print(f"  {i}. {row['省份']}: {row['平均价格(元/吨)']} 元/吨 ({row['数据点数']}条数据)")
        
        print(f"{'='*60}")
        logger.info("并行爬取任务完成!")
    else:
        logger.error("未获取到任何数据")

if __name__ == "__main__":
    main()
