#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
天然气价格数据爬虫 - 使用Selenium获取真实数据
从上海石油天然气交易中心爬取天然气出站价格数据
"""

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import pandas as pd
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
        logging.FileHandler('selenium_scraper.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class NaturalGasSeleniumScraper:
    def __init__(self):
        self.base_url = "https://www.shpgx.com/html/czjg.html"
        self.data_dir = "data"
        self.results_dir = "results"
        
        # 确保目录存在
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(self.results_dir, exist_ok=True)
        
        # 设置Chrome选项
        self.chrome_options = Options()
        self.chrome_options.add_argument('--no-sandbox')
        self.chrome_options.add_argument('--disable-dev-shm-usage')
        self.chrome_options.add_argument('--disable-gpu')
        self.chrome_options.add_argument('--window-size=1920,1080')
        # 注释掉headless模式以便调试
        # self.chrome_options.add_argument('--headless')
        
        self.driver = None
        
    def setup_driver(self):
        """初始化WebDriver"""
        try:
            self.driver = webdriver.Chrome(options=self.chrome_options)
            self.driver.implicitly_wait(10)
            logger.info("WebDriver初始化成功")
            return True
        except Exception as e:
            logger.error(f"WebDriver初始化失败: {e}")
            return False
    
    def get_page_data(self, page_num=1):
        """获取指定页面的数据"""
        try:
            # 如果是第一页，直接访问
            if page_num == 1:
                self.driver.get(self.base_url)
                logger.info(f"访问第1页")
            else:
                # 对于其他页面，输入页码并跳转
                page_input = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='text']"))
                )
                page_input.clear()
                page_input.send_keys(str(page_num))
                
                # 按回车或点击跳转
                page_input.send_keys('\n')
                time.sleep(2)
                logger.info(f"跳转到第{page_num}页")
            
            # 等待表格数据加载
            WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "table tbody tr"))
            )
            
            # 等待数据完全加载（检查是否还有"数据正在加载中"）
            time.sleep(3)
            
            # 获取表格数据
            rows = self.driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
            page_data = []
            
            for row in rows:
                try:
                    cells = row.find_elements(By.TAG_NAME, "td")
                    if len(cells) >= 3:
                        date = cells[0].text.strip()
                        region = cells[1].text.strip()
                        price = cells[2].text.strip()
                        
                        if date and region and price and "数据正在加载中" not in row.text:
                            page_data.append({
                                'date': date,
                                'region': region,
                                'price': price
                            })
                except Exception as e:
                    logger.warning(f"解析行数据时出错: {e}")
                    continue
            
            logger.info(f"第{page_num}页获取到{len(page_data)}条数据")
            return page_data
            
        except TimeoutException:
            logger.error(f"第{page_num}页加载超时")
            return []
        except Exception as e:
            logger.error(f"获取第{page_num}页数据时出错: {e}")
            return []
    
    def get_total_pages(self):
        """获取总页数"""
        try:
            # 查找分页信息
            page_info = self.driver.find_element(By.XPATH, "//*[contains(text(), '页/共')]")
            page_text = page_info.text
            
            # 提取总页数
            match = re.search(r'页/共(\d+)页', page_text)
            if match:
                total_pages = int(match.group(1))
                logger.info(f"检测到总页数: {total_pages}")
                return total_pages
            else:
                logger.warning("无法解析总页数")
                return 1
                
        except NoSuchElementException:
            logger.warning("未找到分页信息")
            return 1
        except Exception as e:
            logger.error(f"获取总页数时出错: {e}")
            return 1
    
    def scrape_all_data(self, max_pages=None):
        """爬取所有数据"""
        if not self.setup_driver():
            return []
        
        all_data = []
        
        try:
            # 访问第一页获取总页数
            self.driver.get(self.base_url)
            time.sleep(5)  # 等待页面完全加载
            
            total_pages = self.get_total_pages()
            if max_pages:
                total_pages = min(total_pages, max_pages)
            
            logger.info(f"开始爬取，总共{total_pages}页")
            
            # 爬取每一页
            for page_num in range(1, total_pages + 1):
                logger.info(f"正在爬取第{page_num}/{total_pages}页...")
                
                page_data = self.get_page_data(page_num)
                if page_data:
                    all_data.extend(page_data)
                    logger.info(f"第{page_num}页成功获取{len(page_data)}条数据")
                else:
                    logger.warning(f"第{page_num}页未获取到数据")
                
                # 添加延迟避免请求过快
                time.sleep(1)
                
                # 每10页保存一次数据
                if page_num % 10 == 0:
                    self.save_interim_data(all_data, page_num)
            
            logger.info(f"爬取完成，总共获取{len(all_data)}条数据")
            
        except KeyboardInterrupt:
            logger.info("用户中断爬取")
        except Exception as e:
            logger.error(f"爬取过程中出错: {e}")
        finally:
            if self.driver:
                self.driver.quit()
                logger.info("WebDriver已关闭")
        
        return all_data
    
    def save_interim_data(self, data, page_num):
        """保存中间数据"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            interim_file = os.path.join(self.data_dir, f"interim_data_page_{page_num}_{timestamp}.json")
            
            with open(interim_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"中间数据已保存到: {interim_file}")
        except Exception as e:
            logger.error(f"保存中间数据失败: {e}")
    
    def process_and_save_data(self, data):
        """处理和保存数据"""
        if not data:
            logger.warning("没有数据可供处理")
            return
        
        try:
            # 创建DataFrame
            df = pd.DataFrame(data)
            
            # 数据清洗
            df['price'] = pd.to_numeric(df['price'], errors='coerce')
            df['date'] = pd.to_datetime(df['date'], errors='coerce')
            
            # 移除无效数据
            df = df.dropna()
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # 保存原始数据
            raw_file = os.path.join(self.data_dir, f"natural_gas_prices_raw_{timestamp}.csv")
            df.to_csv(raw_file, index=False, encoding='utf-8-sig')
            logger.info(f"原始数据已保存到: {raw_file}")
            
            # 按省份计算平均价格
            province_avg = df.groupby('region')['price'].agg(['mean', 'count', 'std']).round(2)
            province_avg.columns = ['平均价格(元/吨)', '数据点数量', '标准差']
            province_avg = province_avg.sort_values('平均价格(元/吨)', ascending=False)
            
            # 保存省份统计数据
            stats_file = os.path.join(self.results_dir, f"province_gas_price_stats_{timestamp}.csv")
            province_avg.to_csv(stats_file, encoding='utf-8-sig')
            logger.info(f"省份统计数据已保存到: {stats_file}")
            
            # 保存详细JSON数据
            json_file = os.path.join(self.results_dir, f"detailed_gas_prices_{timestamp}.json")
            df.to_json(json_file, orient='records', force_ascii=False, indent=2, date_format='iso')
            logger.info(f"详细数据已保存到: {json_file}")
            
            # 生成统计报告
            self.generate_report(df, province_avg, timestamp)
            
            logger.info("数据处理和保存完成")
            
        except Exception as e:
            logger.error(f"处理和保存数据时出错: {e}")
    
    def generate_report(self, df, province_avg, timestamp):
        """生成统计报告"""
        try:
            report_file = os.path.join(self.results_dir, f"gas_price_report_{timestamp}.txt")
            
            with open(report_file, 'w', encoding='utf-8') as f:
                f.write("=" * 60 + "\n")
                f.write("全国天然气价格统计报告\n")
                f.write("=" * 60 + "\n")
                f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"数据来源: 上海石油天然气交易中心\n\n")
                
                f.write(f"数据概览:\n")
                f.write(f"- 总记录数: {len(df)}\n")
                f.write(f"- 地区数量: {df['region'].nunique()}\n")
                f.write(f"- 数据日期范围: {df['date'].min()} 至 {df['date'].max()}\n")
                f.write(f"- 全国价格范围: {df['price'].min():.2f} - {df['price'].max():.2f} 元/吨\n")
                f.write(f"- 全国平均价格: {df['price'].mean():.2f} 元/吨\n\n")
                
                f.write("各省份天然气平均价格排名:\n")
                f.write("-" * 40 + "\n")
                for i, (region, row) in enumerate(province_avg.iterrows(), 1):
                    f.write(f"{i:2d}. {region:8s}: {row['平均价格(元/吨)']:7.2f} 元/吨 "
                           f"(数据点: {row['数据点数量']:3.0f})\n")
                
                f.write("\n" + "=" * 60 + "\n")
            
            logger.info(f"统计报告已保存到: {report_file}")
            
        except Exception as e:
            logger.error(f"生成报告时出错: {e}")

def main():
    """主函数"""
    scraper = NaturalGasSeleniumScraper()
    
    logger.info("开始爬取天然气价格数据...")
    
    # 爬取前10页数据进行测试（可以修改为None爬取所有页面）
    data = scraper.scrape_all_data(max_pages=10)
    
    if data:
        logger.info(f"爬取完成，共获取{len(data)}条数据")
        scraper.process_and_save_data(data)
    else:
        logger.error("未获取到任何数据")

if __name__ == "__main__":
    main()
