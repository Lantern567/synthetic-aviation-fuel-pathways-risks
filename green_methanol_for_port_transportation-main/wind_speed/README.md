# 绿色甲醇港口运输数据分析项目

## 项目结构

- `data/`：存放原始数据文件（如 .nc、.csv 等）
- `src/`：存放所有源代码，包括数据读入、处理、主算法等
- `results/`：存放分析结果
  - `results/tables/`：存放输出的表格文件（如 .csv、.xlsx 等）
  - `results/figures/`：存放输出的图片文件（如 .png、.jpg 等）
- `tests/`：存放测试代码和单元测试
- `logs/`：存放日志文件

## 规范说明
- 数据的读入、处理、主算法和结果保存需分模块实现，分别存放于 `src/` 下不同子模块。
- 结果输出需存放于 `results/` 下对应子文件夹。
- 所有裸露在外的数据文件需归入 `data/` 文件夹。
- 每次代码更新需同步更新本说明文档。

## 使用说明

### 安装依赖
```bash
pip install -r requirements.txt
```

### 运行主程序
```bash
cd src
python main.py
```

### 运行测试
```bash
pytest ../tests
```

## 新增功能

- 支持通过 NASA Earthdata 认证批量下载 MERRA2 数据（需配置 .netrc 文件）
- 支持批量读取 data 文件夹下所有 .nc 文件，便于后续批量分析
- 所有功能均有自动化单元测试

## 用法示例

### 批量下载
1. 在用户主目录下新建 `.netrc` 文件，内容如下：
   ```
   machine urs.earthdata.nasa.gov
       login 你的用户名
       password 你的密码
   ```
2. 运行：
   ```bash
   python scripts/download_all.py
   ```

### 批量读取
```python
from src.data_loader import load_all_nc_files
nc_dict = load_all_nc_files('data')
# nc_dict: {文件名: Dataset对象}
``` 