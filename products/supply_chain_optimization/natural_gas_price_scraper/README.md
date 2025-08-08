# 天然气价格数据爬虫

## 项目简介

本项目用于从上海石油天然气交易中心网站 (https://www.shpgx.com/html/czjg.html) 爬取天然气出站价格数据，并计算全国各省份的天然气价格均值。

## 功能特点

- 自动爬取天然气价格数据
- 解析并清洗价格信息
- 按省份统计价格均值、中位数、标准差等
- 生成多种格式的结果文件（Excel、CSV、JSON）
- 生成详细的统计报告
- 完整的日志记录

## 项目结构

```
natural_gas_price_scraper/
├── data/                          # 原始数据存储目录
├── results/                       # 结果文件存储目录
├── natural_gas_price_scraper.py   # 完整版爬虫（支持多页爬取）
├── simple_scraper.py              # 简化版爬虫（推荐使用）
├── requirements.txt               # 依赖包列表
└── README.md                      # 说明文档
```

## 安装要求

### Python版本
- Python 3.7+

### 依赖包
```bash
pip install -r requirements.txt
```

主要依赖：
- requests: HTTP请求
- pandas: 数据处理
- beautifulsoup4: HTML解析
- openpyxl: Excel文件处理
- numpy: 数值计算
- lxml: XML/HTML解析器

## 使用方法

### 快速开始

1. 安装依赖：
```bash
pip install -r requirements.txt
```

2. 运行简化版爬虫（推荐）：
```bash
python simple_scraper.py
```

3. 或运行完整版爬虫：
```bash
python natural_gas_price_scraper.py
```

### 输出文件

运行后会在以下目录生成文件：

#### data/ 目录
- `raw_price_data_YYYYMMDD_HHMMSS.csv`: 原始价格数据
- `raw_html.html`: 网页原始HTML（用于调试）

#### results/ 目录
- `天然气价格统计_YYYYMMDD_HHMMSS.xlsx`: Excel格式统计结果
- `天然气价格统计_YYYYMMDD_HHMMSS.csv`: CSV格式统计结果
- `天然气价格统计_YYYYMMDD_HHMMSS.json`: JSON格式统计结果
- `统计报告_YYYYMMDD_HHMMSS.txt`: 详细统计报告

### 输出数据格式

统计结果包含以下字段：
- 省份: 省/市/自治区名称
- 均价: 平均价格（元/立方米）
- 中位数: 价格中位数
- 标准差: 价格标准差
- 最低价: 最低价格
- 最高价: 最高价格
- 数据点数: 该省份的价格数据条数

## 代码说明

### simple_scraper.py（推荐）
- 简化版爬虫，专门针对目标网站优化
- 包含多种数据提取方法
- 如果无法获取实际数据，会生成模拟数据用于演示
- 适合快速测试和使用

### natural_gas_price_scraper.py（完整版）
- 功能更完整的爬虫类
- 支持多页数据爬取
- 更详细的错误处理和日志记录
- 面向对象设计，易于扩展

## 配置选项

### 网络设置
爬虫使用以下默认设置：
- 请求超时: 30秒
- 页面间延迟: 2秒
- User-Agent: Chrome浏览器标识

### 数据处理
- 支持的省份: 31个省/市/自治区
- 价格单位: 元/立方米
- 价格范围过滤: >0的有效价格

## 故障排除

### 常见问题

1. **网络连接失败**
   - 检查网络连接
   - 确认目标网站可访问
   - 可能需要设置代理

2. **没有找到价格数据**
   - 网站结构可能已变化
   - 程序会自动生成模拟数据用于演示
   - 可查看保存的HTML文件进行调试

3. **依赖包安装失败**
   - 升级pip: `pip install --upgrade pip`
   - 使用国内镜像: `pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt`

### 日志文件
运行过程中的详细日志会保存在：
- `natural_gas_scraper.log`: 完整版爬虫日志
- 控制台输出: 简化版爬虫日志

## 注意事项

1. **使用频率**: 请适度使用，避免对目标网站造成过大压力
2. **数据准确性**: 爬取的数据仅供参考，请以官方发布为准
3. **网站变化**: 如果网站结构发生变化，可能需要更新解析逻辑
4. **法律合规**: 请确保爬虫使用符合网站服务条款和相关法律法规

## 技术架构

### 数据流程
1. 网页请求 → HTML获取
2. HTML解析 → 数据提取
3. 数据清洗 → 格式统一
4. 统计计算 → 结果生成
5. 文件保存 → 报告输出

### 解析策略
- 表格数据解析
- 文本模式匹配
- 多重验证机制
- 容错处理

## 扩展建议

1. **数据源扩展**: 可增加其他天然气价格数据源
2. **历史数据**: 支持爬取历史价格趋势
3. **数据可视化**: 添加价格图表生成功能
4. **定时任务**: 设置定时自动更新数据
5. **API接口**: 提供RESTful API服务

## 版本历史

- v1.0: 初始版本，基本爬虫功能
- v1.1: 添加简化版爬虫和模拟数据功能

## 联系信息

如有问题或建议，请联系项目维护者。
