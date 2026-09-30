#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
真实天然气价格数据爬虫 - 使用Selenium获取动态加载的数据
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

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('selenium_scraper.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class SeleniumNaturalGasScraper:
    def __init__(self):
        self.base_url = "https://www.shpgx.com/html/czjg.html"
        self.driver = None
        self.wait = None
        
        # 确保目录存在
        os.makedirs('data', exist_ok=True)
        os.makedirs('results', exist_ok=True)
        
    def setup_driver(self):
        """设置Chrome浏览器driver"""
        try:
            chrome_options = Options()
            # 不使用headless模式，这样可以看到浏览器操作
            # chrome_options.add_argument('--headless')  
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--window-size=1920,1080')
            chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
            
            logger.info("尝试启动Chrome浏览器...")
            
            # 直接尝试使用系统中的Chrome
            self.driver = webdriver.Chrome(options=chrome_options)
            self.wait = WebDriverWait(self.driver, 30)
            logger.info("成功启动Chrome浏览器")
            return True
            
        except Exception as e:
            logger.error(f"启动Chrome失败: {e}")
            logger.info("请确保已安装Chrome浏览器和ChromeDriver")
            return False
    
    def get_table_data(self):
        """获取当前页面的表格数据"""
        try:
            # 等待页面加载
            time.sleep(5)
            
            # 尝试多种表格选择器
            table_selectors = [
                "table.table.table-striped",
                "table",
                "#pngexchangedata-dt",
                ".table-responsive table"
            ]
            
            table = None
            for selector in table_selectors:
                try:
                    table = self.driver.find_element(By.CSS_SELECTOR, selector)
                    if table:
                        logger.info(f"找到表格，使用选择器: {selector}")
                        break
                except:
                    continue
            
            if not table:
                logger.error("未找到数据表格")
                return []
            
            # 获取表格行
            rows = table.find_elements(By.TAG_NAME, "tr")
            logger.info(f"找到 {len(rows)} 行数据")
            
            data = []
            headers = []
            
            for i, row in enumerate(rows):
                cells = row.find_elements(By.TAG_NAME, "td")
                if not cells:  # 可能是表头，尝试th
                    cells = row.find_elements(By.TAG_NAME, "th")
                    if cells and not headers:
                        headers = [cell.text.strip() for cell in cells]
                        logger.info(f"表头: {headers}")
                        continue
                
                if len(cells) >= 3:
                    row_data = [cell.text.strip() for cell in cells]
                    # 过滤掉空行和"数据正在加载中"等提示
                    if (row_data[0] and 
                        "加载中" not in str(row_data) and 
                        "暂无数据" not in str(row_data) and
                        row_data[0] != ""):
                        data.append(row_data)
            
            logger.info(f"获取到 {len(data)} 条有效数据")
            if data:
                logger.info(f"示例数据: {data[0]}")
            
            return data
            
        except Exception as e:
            logger.error(f"获取表格数据失败: {e}")
            return []
    
    def get_pagination_info(self):
        """获取分页信息"""
        try:
            # 等待页面完全加载
            time.sleep(3)
            
            # 获取页面文本
            page_text = self.driver.page_source
            
            # 尝试多种分页信息匹配模式
            patterns = [
                r'第\s*(\d+)\s*页[/／]\s*共\s*(\d+)\s*页.*?共\s*(\d+)\s*条记录',
                r'第\s*(\d+)\s*页[/／]\s*共\s*(\d+)\s*页',
                r'共\s*(\d+)\s*条记录',
                r'(\d+)\s*页/共\s*(\d+)\s*页'
            ]
            
            for pattern in patterns:
                match = re.search(pattern, page_text)
                if match:
                    groups = match.groups()
                    if len(groups) >= 3:  # 有页码和记录数
                        current_page = int(groups[0])
                        total_pages = int(groups[1])
                        total_records = int(groups[2])
                        logger.info(f"分页信息: 第{current_page}页/共{total_pages}页，共{total_records}条记录")
                        return current_page, total_pages, total_records
                    elif len(groups) >= 2:  # 只有页码
                        current_page = int(groups[0])
                        total_pages = int(groups[1])
                        logger.info(f"分页信息: 第{current_page}页/共{total_pages}页")
                        return current_page, total_pages, 0
                    elif len(groups) >= 1:  # 只有记录数
                        total_records = int(groups[0])
                        # 假设每页25条记录
                        total_pages = (total_records + 24) // 25
                        logger.info(f"根据记录数推算: 共{total_records}条记录，约{total_pages}页")
                        return 1, total_pages, total_records
            
            # 尝试查找分页元素
            try:
                # 查找包含分页信息的元素
                pagination_elements = self.driver.find_elements(By.XPATH, "//*[contains(text(), '页') or contains(text(), '条记录')]")
                for element in pagination_elements:
                    text = element.text.strip()
                    if text:
                        logger.info(f"找到分页相关文本: {text}")
                        # 再次尝试正则匹配
                        for pattern in patterns:
                            match = re.search(pattern, text)
                            if match:
                                groups = match.groups()
                                if len(groups) >= 2:
                                    return int(groups[0]), int(groups[1]), int(groups[2]) if len(groups) >= 3 else 0
            except:
                pass
            
            # 如果还是找不到，查看是否有下一页按钮来判断是否有多页
            try:
                next_buttons = self.driver.find_elements(By.XPATH, "//a[contains(text(), '下一页')]")
                if next_buttons and any(btn.is_enabled() for btn in next_buttons):
                    logger.info("找到下一页按钮，预设爬取10页")
                    return 1, 10, 0  # 预设最多10页
            except:
                pass
            
            logger.warning("未找到分页信息，默认只爬取当前页")
            return 1, 1, 0
            
        except Exception as e:
            logger.error(f"获取分页信息失败: {e}")
            return 1, 1, 0
    
    def click_next_page(self):
        """点击下一页"""
        try:
            # 查找下一页按钮
            next_button = self.driver.find_element(By.XPATH, "//a[contains(text(), '下一页')]")
            
            # 检查按钮是否可用（不包含disabled类）
            if next_button.is_enabled() and next_button.is_displayed():
                # 使用JavaScript点击，因为链接是javascript:void(0)
                self.driver.execute_script("arguments[0].click();", next_button)
                logger.info("成功点击下一页")
                time.sleep(3)  # 等待页面加载
                return True
            else:
                logger.info("下一页按钮不可用")
                return False
                
        except Exception as e:
            logger.error(f"点击下一页失败: {e}")
            return False
    
    def scrape_all_pages(self, max_pages=10):
        """爬取所有页面的数据"""
        if not self.setup_driver():
            logger.error("无法设置浏览器driver，爬取失败")
            return []
        
        all_data = []
        
        try:
            # 访问首页
            logger.info(f"访问网站: {self.base_url}")
            self.driver.get(self.base_url)
            
            # 等待页面完全加载
            time.sleep(10)
            
            # 获取总页数信息
            current_page, total_pages, total_records = self.get_pagination_info()
            
            # 限制最大爬取页数
            if max_pages:
                total_pages = min(total_pages, max_pages)
            
            logger.info(f"开始爬取，计划爬取{total_pages}页")
            
            # 爬取每一页
            page_count = 0
            consecutive_empty_pages = 0
            
            while page_count < total_pages:
                page_count += 1
                logger.info(f"正在爬取第 {page_count} 页...")
                
                # 获取当前页数据
                page_data = self.get_table_data()
                if page_data:
                    all_data.extend(page_data)
                    consecutive_empty_pages = 0  # 重置空页面计数
                    logger.info(f"第 {page_count} 页获取到 {len(page_data)} 条数据，累计 {len(all_data)} 条")
                    
                    # 打印一些示例数据
                    if len(page_data) > 0:
                        logger.info(f"示例数据: {page_data[0]}")
                else:
                    consecutive_empty_pages += 1
                    logger.warning(f"第 {page_count} 页未获取到数据")
                    
                    # 如果连续3页都没有数据，可能已经到了最后
                    if consecutive_empty_pages >= 3:
                        logger.info("连续多页无数据，可能已到达最后一页")
                        break
                
                # 如果不是最后一页，点击下一页
                if page_count < total_pages:
                    if not self.click_next_page():
                        logger.info("无法继续翻页，停止爬取")
                        break
                
            logger.info(f"爬取完成，总共获取 {len(all_data)} 条数据")
            return all_data
            
        except Exception as e:
            logger.error(f"爬取过程中出错: {e}")
            return all_data
        
        finally:
            if self.driver:
                logger.info("爬取完成，5秒后自动关闭浏览器...")
                time.sleep(5)  # 给用户时间查看结果
                self.driver.quit()
                logger.info("浏览器已关闭")
    
    def save_and_process_data(self, data):
        """保存和处理数据"""
        if not data:
            logger.warning("没有数据可保存")
            return None, None
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 创建DataFrame
        df = pd.DataFrame(data, columns=['日期', '地区', '价格(元/吨)'])
        
        # 保存原始数据
        raw_file = f"data/raw_selenium_data_{timestamp}.csv"
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
            processed_file = f"results/processed_selenium_data_{timestamp}.csv"
            df_clean.to_csv(processed_file, index=False, encoding='utf-8-sig')
            
            avg_file = f"results/province_average_selenium_{timestamp}.csv"
            province_avg.to_csv(avg_file, index=False, encoding='utf-8-sig')
            
            logger.info(f"处理后数据已保存到: {processed_file}")
            logger.info(f"省份均值已保存到: {avg_file}")
            
            return df_clean, province_avg
            
        except Exception as e:
            logger.error(f"数据处理失败: {e}")
            return df, None

def main():
    """主函数"""
    logger.info("开始使用Selenium爬取天然气价格数据...")
    
    scraper = SeleniumNaturalGasScraper()
    
    # 爬取更多页数据
    data = scraper.scrape_all_pages(max_pages=20)  # 增加到20页
    
    if data:
        processed_data, province_avg = scraper.save_and_process_data(data)
        
        print(f"\n=== 爬取结果统计 ===")
        print(f"总数据条数: {len(data)}")
        
        if province_avg is not None and len(province_avg) > 0:
            print(f"地区数量: {len(province_avg)}")
            print(f"平均价格最高的5个地区:")
            for _, row in province_avg.head(5).iterrows():
                print(f"  {row['省份']}: {row['平均价格(元/吨)']} 元/吨 ({row['数据点数']}条数据)")
            
            print(f"\n平均价格最低的5个地区:")
            for _, row in province_avg.tail(5).iterrows():
                print(f"  {row['省份']}: {row['平均价格(元/吨)']} 元/吨 ({row['数据点数']}条数据)")
        
        logger.info("爬取任务完成!")
    else:
        logger.error("未获取到任何数据")

if __name__ == "__main__":
    main()
