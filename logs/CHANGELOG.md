# 更新日志

## 2024-06-09
- 初始化数据分析项目文件夹结构：data, src, results, results/tables, results/figures, tests, logs。
- 将原始数据文件 MERRA2_400.inst3_3d_asm_Nv.20240101.SUB.nc 移动到 data 文件夹。
- 新增 README.md 说明文档。
- 新增 src/data_loader.py，实现nc文件读取。
- 新增 src/visualization.py，实现变量可视化。
- 新增 src/main.py，主流程演示。
- 新增 requirements.txt，添加依赖。
- 新增 tests/test_data_loader.py 和 tests/test_visualization.py，单元测试数据读取和可视化。 