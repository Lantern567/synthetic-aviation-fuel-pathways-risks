#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
真实数据爬虫 - 专门用于爬取上海石油天然气交易中心的实际数据
"""

import requests
from bs4 import BeautifulSoup
import pandas as pd
import json
import time
import random
from datetime import datetime
import logging
import os
import re

class RealDataScraper:
    def __init__(self):
        self.base_url = "https://www.shpgx.com/html/czjg.html"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Cache-Control': 'max-age=0'
        })
        
        # 设置日志
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('real_scraper.log', encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
    def get_page_source(self, page_num=1):
        """获取页面源码"""
        try:
            if page_num == 1:
                url = self.base_url
            else:
                # 尝试不同的分页URL格式
                url = f"https://www.shpgx.com/html/czjg.html?page={page_num}"
            
            self.logger.info(f"正在请求页面: {url}")
            
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            # 尝试不同的编码
            if response.encoding == 'ISO-8859-1':
                response.encoding = 'utf-8'
            
            self.logger.info(f"页面请求成功，状态码: {response.status_code}")
            self.logger.info(f"响应内容长度: {len(response.text)}")
            
            return response.text
            
        except Exception as e:
            self.logger.error(f"获取页面失败: {str(e)}")
            return None
    
    def analyze_page_structure(self, html_content):
        """分析页面结构"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        self.logger.info("=== 页面结构分析 ===")
        
        # 1. 查找所有表格
        tables = soup.find_all('table')
        self.logger.info(f"找到 {len(tables)} 个表格")
        
        for i, table in enumerate(tables):
            rows = table.find_all('tr')
            self.logger.info(f"表格 {i+1}: {len(rows)} 行")
            
            # 分析表头
            if rows:
                headers = rows[0].find_all(['th', 'td'])
                header_texts = [h.get_text(strip=True) for h in headers]
                self.logger.info(f"表头: {header_texts}")
                
                # 显示前几行数据
                for j, row in enumerate(rows[1:6]):  # 显示前5行数据
                    cells = row.find_all(['td', 'th'])
                    cell_texts = [c.get_text(strip=True) for c in cells]
                    self.logger.info(f"第{j+1}行: {cell_texts}")
        
        # 2. 查找分页信息
        pagination_elements = soup.find_all(text=re.compile(r'页|记录'))
        self.logger.info("分页信息:")
        for elem in pagination_elements:
            if '页' in elem or '记录' in elem:
                self.logger.info(f"  {elem.strip()}")
        
        # 3. 查找包含数字的元素（可能是价格）
        price_pattern = re.compile(r'\d+\.?\d*')
        price_elements = soup.find_all(text=price_pattern)
        self.logger.info(f"找到 {len(price_elements)} 个包含数字的文本元素")
        
        # 4. 查找可能的数据容器
        data_divs = soup.find_all(['div', 'section'], class_=re.compile(r'data|table|content'))
        self.logger.info(f"找到 {len(data_divs)} 个可能的数据容器")
        
        return soup
    
    def extract_table_data(self, soup):
        """提取表格数据"""
        all_data = []
        
        tables = soup.find_all('table')
        
        for table_idx, table in enumerate(tables):
            self.logger.info(f"处理表格 {table_idx + 1}")
            
            rows = table.find_all('tr')
            if not rows:
                continue
            
            # 获取表头
            header_row = rows[0]
            headers = [th.get_text(strip=True) for th in header_row.find_all(['th', 'td'])]
            
            self.logger.info(f"表头: {headers}")
            
            # 提取数据行
            table_data = []
            for row in rows[1:]:
                cells = row.find_all(['td', 'th'])
                row_data = [cell.get_text(strip=True) for cell in cells]
                
                # 过滤空行
                if any(cell for cell in row_data if cell):
                    table_data.append(row_data)
            
            if table_data:
                self.logger.info(f"表格 {table_idx + 1} 提取到 {len(table_data)} 行数据")
                
                # 将数据转换为字典格式
                for row_data in table_data:
                    if len(row_data) >= len(headers):
                        data_dict = dict(zip(headers, row_data))
                        data_dict['table_index'] = table_idx + 1
                        all_data.append(data_dict)
            else:
                self.logger.info(f"表格 {table_idx + 1} 没有数据")
        
        return all_data
    
    def scrape_single_page(self, page_num=1):
        """爬取单个页面"""
        self.logger.info(f"开始爬取第 {page_num} 页")
        
        # 获取页面源码
        html_content = self.get_page_source(page_num)
        if not html_content:
            return []
        
        # 保存原始HTML用于调试
        debug_file = f"page_{page_num}_debug.html"
        with open(debug_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
        self.logger.info(f"页面源码已保存到: {debug_file}")
        
        # 分析页面结构
        soup = self.analyze_page_structure(html_content)
        
        # 提取表格数据
        data = self.extract_table_data(soup)
        
        self.logger.info(f"第 {page_num} 页提取到 {len(data)} 条记录")
        return data
    
    def detect_pagination(self, html_content):
        """检测分页信息"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 查找分页相关的文本
        text_content = soup.get_text()
        
        # 模式1: "第 X页/共Y页"
        page_match = re.search(r'第\s*(\d+)\s*页[/／]\s*共\s*(\d+)\s*页', text_content)
        if page_match:
            current_page = int(page_match.group(1))
            total_pages = int(page_match.group(2))
            self.logger.info(f"检测到分页信息: 第{current_page}页/共{total_pages}页")
            return total_pages
        
        # 模式2: "共X条记录"
        record_match = re.search(r'共\s*(\d+)\s*条记录', text_content)
        if record_match:
            total_records = int(record_match.group(1))
            # 假设每页25条记录
            estimated_pages = (total_records + 24) // 25
            self.logger.info(f"根据记录数估算页数: {total_records}条记录, 约{estimated_pages}页")
            return estimated_pages
        
        # 模式3: 查找分页链接
        page_links = soup.find_all('a', href=re.compile(r'page|p='))
        if page_links:
            page_numbers = []
            for link in page_links:
                href = link.get('href', '')
                page_match = re.search(r'(?:page|p)=(\d+)', href)
                if page_match:
                    page_numbers.append(int(page_match.group(1)))
            
            if page_numbers:
                max_page = max(page_numbers)
                self.logger.info(f"根据分页链接检测到最大页数: {max_page}")
                return max_page
        
        self.logger.warning("未找到明确的分页信息")
        return 1
    
    def scrape_all_pages(self):
        """爬取所有页面"""
        self.logger.info("开始分析第一页...")
        
        # 先获取第一页来分析结构和分页信息
        first_page_data = self.scrape_single_page(1)
        
        if not first_page_data:
            self.logger.error("第一页爬取失败")
            return []
        
        # 获取第一页的HTML来检测分页
        html_content = self.get_page_source(1)
        total_pages = self.detect_pagination(html_content) if html_content else 1
        
        self.logger.info(f"预计总页数: {total_pages}")
        
        all_data = first_page_data
        
        # 爬取剩余页面
        for page_num in range(2, min(total_pages + 1, 101)):  # 最多爬取100页
            self.logger.info(f"正在爬取第 {page_num} 页...")
            
            page_data = self.scrape_single_page(page_num)
            
            if not page_data:
                self.logger.info(f"第 {page_num} 页无数据，可能已到达最后一页")
                break
            
            all_data.extend(page_data)
            
            # 添加延迟
            time.sleep(random.uniform(2, 4))
        
        self.logger.info(f"总共爬取到 {len(all_data)} 条记录")
        return all_data
    
    def save_results(self, data):
        """保存结果"""
        if not data:
            self.logger.warning("没有数据可保存")
            return
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 保存原始数据
        raw_file = f"results/real_data_raw_{timestamp}.json"
        with open(raw_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        self.logger.info(f"原始数据已保存到: {raw_file}")
        
        # 转换为DataFrame并保存CSV
        df = pd.DataFrame(data)
        csv_file = f"results/real_data_{timestamp}.csv"
        df.to_csv(csv_file, index=False, encoding='utf-8-sig')
        self.logger.info(f"CSV数据已保存到: {csv_file}")
        
        # 生成报告
        report = f"""=== 真实数据爬取报告 ===

爬取时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
数据源: {self.base_url}
总记录数: {len(data)}

=== 数据字段 ===
"""
        if data:
            sample_keys = list(data[0].keys())
            for key in sample_keys:
                report += f"{key}\n"
        
        report_file = f"results/real_data_report_{timestamp}.txt"
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report)
        self.logger.info(f"报告已保存到: {report_file}")

def main():
    scraper = RealDataScraper()
    
    # 先测试单页爬取
    print("正在测试第一页爬取...")
    data = scraper.scrape_single_page(1)
    
    if data:
        print(f"第一页爬取成功，共 {len(data)} 条记录")
        print("样本数据:")
        for i, record in enumerate(data[:3]):  # 显示前3条
            print(f"记录 {i+1}: {record}")
        
        # 询问是否继续爬取所有页面
        print("\n是否继续爬取所有页面？")
        print("1. 是，爬取所有页面")
        print("2. 否，只保存第一页数据")
        
        # 为了自动化，直接爬取所有页面
        print("自动选择：爬取所有页面")
        all_data = scraper.scrape_all_pages()
        scraper.save_results(all_data)
    else:
        print("第一页爬取失败，请检查网络连接和URL")

if __name__ == "__main__":
    main()
