# 功能需求说明

## FEATURE:
- 拆分 `products\supply_chain_optimization\natural_gas_supply_chain_optimization\src\natural_gas_optimization_model.py` ,根据功能分为几个类
- 不要改变原来的`products\supply_chain_optimization\natural_gas_supply_chain_optimization\src\natural_gas_optimization_model.py` 代码
- 拆分的代码要完全和原来对应地方的代码一致，除非要进行必要的改变，不然最好不要进行任何的变化
- 在原来的src里面要保留主程序的调用
- 拆分出来的各项工具，请防止在外部的tools和shared文件里面，作为一些共享或者工具类
- 要对拆分出来的类进行前后的对比，确保前后的输出完全一致。
- 注意一些文件路径的问题，特别是在拆分了新的类以后，要确保文件路径正确

## EXAMPLES:


## DOCUMENTATION:


## OTHER CONSIDERATIONS:


技术要求：
- 环境：必须在 `green_methanol_for_port_transportation` conda环境中运行
- 并发：充分利用CPU/GPU资源进行并行计算

数据处理要求：
- 输入格式：支持CSV、Excel、GeoJSON等标准格式
- 输出格式：结果必须保存在 `results/` 目录下的对应子目录
- 时间戳：所有输出文件包含时间戳 (YYYYMMDD_HHMMSS)
- 元数据：重要数据集需要包含元数据文件

代码质量要求：
- 模块化：遵循项目的模块化结构 (src/, data/, results/, tests/, logs/)
- 测试：必须包含单元测试和集成测试
- 文档：所有函数需要docstring，模块需要README
- 日志：使用Python logging模块，生成带日期的日志文件

集成要求：
- 兼容性：与现有模块 (air_port_data_process/, gis_data_scraper/, natural_gas_supply_chain_optimization/) 保持兼容
- 数据流：遵循项目的数据流模式，确保可以与其他模块数据交换
- 依赖管理：新依赖需要添加到requirements.txt

领域知识：
- 绿色甲醇：了解绿色甲醇的生产、运输、使用特性
- 航空燃料：熟悉航空燃料计算标准（BADA3模型等）
- 能源供应链：理解能源供应链优化的基本原理
- 港口物流：掌握港口运输和物流优化方法

常见陷阱：
- 坐标系统：确保地理坐标使用正确的坐标系（WGS84）
- 单位换算：注意能源单位的正确换算（kg, MJ, kWh等）
- 中文支持：确保可视化中中文字体正确显示
- 数据验证：对输入数据进行完整性和合理性检查