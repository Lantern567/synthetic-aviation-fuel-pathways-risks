# DAC PRD v4.0 - Part 2 (Sections 6-14)

本文件为PRD_v4.0的补充部分,包含Sections 6-14

---

## 六、DAC供应模块设计

### 6.1 DACSupplyManager类设计

**新文件**: `src/dac/dac_supply_manager.py`

**职责**: 管理DAC设备CO₂供应,包括容量计算、能耗估算、成本计算

```python
"""
DAC供应管理器
Direct Air Capture Supply Manager

功能:
1. 计算DAC设备所需容量
2. 估算DAC能耗和成本
3. 生成DAC设备配置报告
4. 支持敏感性分析(不同DAC技术参数)
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple
import logging

class DACSupplyManager:
    """
    DAC供应管理器

    简化假设:
    - DAC设备与SAF工厂一体化部署
    - 模块化设计,每模块2000吨CO₂/年
    - 能耗350 kWh/ton CO₂
    - 捕获效率95%
    """

    def __init__(self, config: Dict, logger: logging.Logger = None):
        """
        初始化DAC供应管理器

        Args:
            config: 配置字典(dac_parameters段)
            logger: 日志记录器
        """

        self.config = config
        self.logger = logger or logging.getLogger(__name__)

        # 加载DAC参数
        self.dac_params = config['dac_parameters']
        self.capture_cost = self.dac_params['capture_cost_yuan_per_ton']
        self.energy_per_ton = self.dac_params['energy_kwh_per_ton_co2']
        self.module_capacity = self.dac_params['module_capacity_ton_year']
        self.efficiency = self.dac_params['capture_efficiency']

    def calculate_required_capacity(self,
                                     co2_demand_kg_per_hour: float,
                                     operating_hours: int = 8760) -> Dict:
        """
        计算所需DAC设备容量

        Args:
            co2_demand_kg_per_hour: CO₂需求(kg/h)
            operating_hours: 年运行小时数(默认8760h)

        Returns:
            Dict: {
                'annual_demand_ton': 年需求(ton/年),
                'required_capacity_ton_year': 所需容量(ton/年),
                'num_modules': 模块数量,
                'total_capex_yuan': 总投资(元),
                'annual_opex_yuan': 年运维费(元)
            }
        """

        # 1. 计算年需求
        annual_demand_ton = (co2_demand_kg_per_hour * operating_hours) / 1000

        # 2. 考虑捕获效率,计算所需容量
        required_capacity = annual_demand_ton / self.efficiency

        # 3. 计算模块数量(向上取整)
        num_modules = int(np.ceil(required_capacity / self.module_capacity))

        # 4. 计算投资和运维成本
        capex_per_module = self.dac_params['capex_per_module_yuan']
        opex_ratio = self.dac_params['opex_ratio']

        total_capex = num_modules * capex_per_module
        annual_opex = total_capex * opex_ratio

        result = {
            'annual_demand_ton': annual_demand_ton,
            'required_capacity_ton_year': required_capacity,
            'num_modules': num_modules,
            'installed_capacity_ton_year': num_modules * self.module_capacity,
            'capacity_utilization': annual_demand_ton / (num_modules * self.module_capacity),
            'total_capex_yuan': total_capex,
            'annual_opex_yuan': annual_opex
        }

        self.logger.info(f"DAC容量计算: 需求{annual_demand_ton:.0f}吨/年, "
                         f"需要{num_modules}个模块")

        return result

    def calculate_energy_consumption(self, co2_amount_kg: float) -> Dict:
        """
        计算DAC能耗

        Args:
            co2_amount_kg: CO₂量(kg)

        Returns:
            Dict: {
                'total_energy_kwh': 总能耗(kWh),
                'breakdown': {各部分能耗分解}
            }
        """

        co2_ton = co2_amount_kg / 1000

        # 总能耗
        total_energy = co2_ton * self.energy_per_ton

        # 能耗分解
        breakdown = self.dac_params['energy_breakdown']

        result = {
            'total_energy_kwh': total_energy,
            'breakdown': {
                'fan_blower_kwh': co2_ton * breakdown['fan_blower'],
                'heating_regeneration_kwh': co2_ton * breakdown['heating_regeneration'],
                'compression_kwh': co2_ton * breakdown['compression'],
                'auxiliary_kwh': co2_ton * breakdown['auxiliary']
            }
        }

        return result

    def calculate_capture_cost(self, co2_amount_kg: float, year: int = 2024) -> Dict:
        """
        计算DAC捕获成本

        Args:
            co2_amount_kg: CO₂量(kg)
            year: 年份(用于成本预测)

        Returns:
            Dict: {
                'total_cost_yuan': 总成本(元),
                'unit_cost_yuan_per_ton': 单位成本(元/吨),
                'breakdown': {成本分解}
            }
        """

        co2_ton = co2_amount_kg / 1000

        # 根据年份调整成本(学习曲线)
        if year <= 2024:
            unit_cost = self.dac_params['capture_cost_yuan_per_ton']
        elif year >= 2030:
            unit_cost = self.dac_params['capture_cost_2030_yuan_per_ton']
        else:
            # 线性插值
            cost_2024 = self.dac_params['capture_cost_yuan_per_ton']
            cost_2030 = self.dac_params['capture_cost_2030_yuan_per_ton']
            unit_cost = cost_2024 - (cost_2024 - cost_2030) * (year - 2024) / 6

        total_cost = co2_ton * unit_cost

        # 成本分解
        cost_breakdown_ratios = self.dac_params['cost_breakdown']

        result = {
            'total_cost_yuan': total_cost,
            'unit_cost_yuan_per_ton': unit_cost,
            'breakdown': {
                'capex_amortization': total_cost * cost_breakdown_ratios['capex_amortization'],
                'energy_cost': total_cost * cost_breakdown_ratios['energy'],
                'opex_maintenance': total_cost * cost_breakdown_ratios['opex_maintenance'],
                'other_cost': total_cost * cost_breakdown_ratios['other']
            }
        }

        return result

    def generate_dac_report(self, optimization_results: Dict) -> pd.DataFrame:
        """
        生成DAC设备配置报告

        Args:
            optimization_results: 优化结果字典

        Returns:
            pd.DataFrame: DAC设备报告表
        """

        report_data = []

        for plant_id in optimization_results['saf_plants']:
            plant_data = optimization_results['plants'][plant_id]

            # 计算该工厂的DAC需求
            total_co2_kg = plant_data['total_co2_consumed_kg']

            # 调用容量计算
            capacity_result = self.calculate_required_capacity(
                co2_demand_kg_per_hour=total_co2_kg / 8760
            )

            # 调用能耗计算
            energy_result = self.calculate_energy_consumption(total_co2_kg)

            # 调用成本计算
            cost_result = self.calculate_capture_cost(total_co2_kg)

            report_data.append({
                'SAF工厂ID': plant_id,
                '年CO₂需求(吨)': capacity_result['annual_demand_ton'],
                'DAC模块数量': capacity_result['num_modules'],
                '装机容量(吨/年)': capacity_result['installed_capacity_ton_year'],
                '容量利用率': f"{capacity_result['capacity_utilization']:.1%}",
                '总投资(万元)': capacity_result['total_capex_yuan'] / 10000,
                '年运维费(万元)': capacity_result['annual_opex_yuan'] / 10000,
                '年总能耗(GWh)': energy_result['total_energy_kwh'] / 1e6,
                '年捕获成本(万元)': cost_result['total_cost_yuan'] / 10000,
                '单位成本(元/吨)': cost_result['unit_cost_yuan_per_ton']
            })

        df_report = pd.DataFrame(report_data)

        self.logger.info(f"✅ DAC设备报告生成完成,共{len(df_report)}个工厂")

        return df_report
```

### 6.2 DACSupplyManager集成到优化模型

在主优化模型中调用:

```python
# src/core/dac_hydrogen_optimization_model.py

def __init__(self, config_path):
    # ... 其他初始化 ...

    # 实例化DAC供应管理器
    from src.dac.dac_supply_manager import DACSupplyManager
    self.dac_manager = DACSupplyManager(self.config, self.logger)

def solve_and_analyze(self):
    """求解优化模型并分析结果"""

    # 求解模型
    self.model.optimize()

    # ... 提取优化结果 ...

    # 生成DAC设备报告
    dac_report = self.dac_manager.generate_dac_report(self.optimization_results)

    # 保存报告
    dac_report.to_csv(
        f"results/tables/dac_equipment_configuration_{timestamp}.csv",
        index=False, encoding='utf-8-sig'
    )

    self.logger.info("✅ DAC设备配置报告已保存")
```

---

## 七、碳排放计算模块调整

### 7.1 修改内容总结

**文件**: `src/co2/co2_emission_calculator.py`

**关键修改**:
1. 新增`calculate_dac_capture_emission()`方法(替代CCS捕获排放)
2. 删除`calculate_co2_transport_emission()`方法
3. 修改`calculate_total_saf_emission_dac()`方法(DAC版本)
4. 更新CORSIA合规性判断逻辑

### 7.2 碳强度计算示例

```python
# 示例:计算1000 kg SAF的碳强度

result = emission_calculator.calculate_total_saf_emission_dac(
    saf_production_kg=1000,
    h2_amount_kg=200,  # 0.2 kg H₂/kg SAF
    co2_amount_kg=3500,  # 3.5 kg CO₂/kg SAF
    h2_transport_km=150  # 氢气运输150km
)

print(f"总排放: {result['total_emission_kg']:.2f} kgCO₂e")
print(f"碳强度: {result['carbon_intensity_gco2e_per_mj']:.2f} gCO₂e/MJ")
print(f"CORSIA合规: {'✅ 通过' if result['carbon_intensity_gco2e_per_mj'] < 44.5 else '❌ 不通过'}")

# 输出示例:
# 总排放: -2000.5 kgCO₂e (负排放,因为固定大气CO₂)
# 碳强度: 12.5 gCO₂e/MJ
# CORSIA合规: ✅ 通过
```

---

## 八、详细任务分解(TodoList)

### 8.1 Phase 1: 项目初始化(Day 1, 4小时)

- [ ] **Task 1.1**: 创建新产品目录结构
  - 创建`dac_hydrogen_saf_supply_chain_optimization/`目录
  - 创建子目录:src/, config/, data/, results/, tests/, logs/
  - 预计时间:30分钟

- [ ] **Task 1.2**: 完整复制v2.0代码
  - 从`green_hydrogen_supply_chain_optimization/`复制所有文件
  - 预计时间:15分钟

- [ ] **Task 1.3**: 批量替换import路径
  - 使用PowerShell脚本替换所有.py文件中的import
  - 验证无ImportError
  - 预计时间:1小时

- [ ] **Task 1.4**: 验证模块可导入
  - 测试主模块类可以成功实例化
  - 预计时间:30分钟

### 8.2 Phase 2: 配置文件创建(Day 1-2, 3小时)

- [ ] **Task 2.1**: 创建新配置文件
  - 复制v2.0配置,重命名为`DACHydrogenSAFOptimizer_config.yaml`
  - 预计时间:15分钟

- [ ] **Task 2.2**: 删除CO₂捕获参数
  - 删除`co2_parameters`整个段
  - 删除GIS数据路径
  - 预计时间:30分钟

- [ ] **Task 2.3**: 新增DAC参数段
  - 添加`dac_parameters`(80行)
  - 包含技术类型、能耗、成本等参数
  - 预计时间:1小时

- [ ] **Task 2.4**: 修改碳排放参数
  - 修改`carbon_emission_parameters`
  - 新增DAC排放,删除CO₂运输排放
  - 预计时间:1小时

- [ ] **Task 2.5**: 运行配置验证脚本
  - 创建并运行`config/validate_config.py`
  - 确保所有参数正确
  - 预计时间:30分钟

### 8.3 Phase 3: 核心模型修改(Day 2-4, 10小时)

- [ ] **Task 3.1**: 修改类名和文档字符串
  - `GreenHydrogenSupplyChainOptimizer` → `DACHydrogenSAFOptimizer`
  - 更新docstring说明v4.0特性
  - 预计时间:30分钟

- [ ] **Task 3.2**: 删除CO₂捕获源加载
  - 删除`_load_co2_capture_sources()`方法
  - 删除相关辅助方法
  - 预计时间:1小时

- [ ] **Task 3.3**: 删除CO₂运输优化
  - 删除`_add_co2_transport_constraints()`方法
  - 删除CO₂运输变量定义
  - 删除运输距离计算
  - 预计时间:2小时

- [ ] **Task 3.4**: 新增DAC供应定义
  - 实现`_define_dac_supply()`方法
  - 实现`_add_dac_energy_constraints()`方法
  - 实现`_add_dac_cost_to_objective()`方法
  - 预计时间:3小时

- [ ] **Task 3.5**: 修改CO₂平衡约束
  - 修改`_add_co2_balance_constraints()`为DAC版本
  - 预计时间:1小时

- [ ] **Task 3.6**: 修改模型构建流程
  - 更新`build_model()`方法调用顺序
  - 删除CO₂相关调用,新增DAC调用
  - 预计时间:1小时

- [ ] **Task 3.7**: 代码审查和重构
  - 删除无用变量和方法
  - 添加必要的日志和注释
  - 预计时间:1.5小时

### 8.4 Phase 4: DAC模块开发(Day 3-4, 4小时)

- [ ] **Task 4.1**: 创建DAC模块目录
  - 创建`src/dac/`目录
  - 创建`__init__.py`
  - 预计时间:15分钟

- [ ] **Task 4.2**: 实现DACSupplyManager类
  - 实现`__init__`、`calculate_required_capacity`等方法
  - 共约150行代码
  - 预计时间:2.5小时

- [ ] **Task 4.3**: 集成到主优化模型
  - 在主模型中实例化DACSupplyManager
  - 调用生成DAC报告
  - 预计时间:1小时

- [ ] **Task 4.4**: 单元测试
  - 测试容量计算、能耗计算、成本计算
  - 预计时间:30分钟

### 8.5 Phase 5: 碳排放模块修改(Day 4-5, 3小时)

- [ ] **Task 5.1**: 修改CO₂捕获排放计算
  - 实现`calculate_dac_capture_emission()`
  - 删除`calculate_co2_capture_emission()`
  - 预计时间:1小时

- [ ] **Task 5.2**: 删除CO₂运输排放计算
  - 删除`calculate_co2_transport_emission()`
  - 预计时间:15分钟

- [ ] **Task 5.3**: 修改总排放计算
  - 实现`calculate_total_saf_emission_dac()`
  - 更新碳强度计算
  - 预计时间:1.5小时

- [ ] **Task 5.4**: 单元测试
  - 测试DAC排放计算正确性
  - 验证碳强度在10-15 gCO₂e/MJ范围
  - 预计时间:30分钟

### 8.6 Phase 6: 测试和验证(Day 5-6, 8小时)

- [ ] **Task 6.1**: 准备测试数据
  - 创建小规模测试case
  - 3个SAF工厂,5个机场,1周时间范围
  - 预计时间:1小时

- [ ] **Task 6.2**: 运行优化模型
  - 执行完整优化流程
  - 确保模型可求解
  - 预计时间:2小时(含debug)

- [ ] **Task 6.3**: 结果验证
  - 验证决策变量合理性
  - 检查约束满足情况
  - 验证目标函数值
  - 预计时间:2小时

- [ ] **Task 6.4**: 碳排放验证
  - 验证碳强度计算
  - 确认CORSIA合规
  - 对比v2.0结果
  - 预计时间:1.5小时

- [ ] **Task 6.5**: 生成完整报告
  - 生成所有CSV表格
  - 生成可视化图表
  - 检查输出文件完整性
  - 预计时间:1.5小时

### 8.7 Phase 7: 文档和交付(Day 6-7, 4小时)

- [ ] **Task 7.1**: 编写README.md
  - 项目说明、安装指南、使用示例
  - 预计时间:1.5小时

- [ ] **Task 7.2**: 生成示例输出
  - 运行完整case,生成示例结果
  - 预计时间:1小时

- [ ] **Task 7.3**: 代码注释完善
  - 确保所有函数有docstring
  - 关键逻辑有inline注释
  - 预计时间:1小时

- [ ] **Task 7.4**: 最终验收
  - 运行验收检查清单
  - 确认所有deliverables完成
  - 预计时间:30分钟

**总预计工时**: 36小时 ≈ **7个工作日**(每天5小时)

---

## 九、实施步骤与时间计划

### 9.1 总体时间安排

| 阶段 | 任务 | 工作日 | 工时 | 负责人 | 交付物 |
|-----|------|-------|------|--------|--------|
| **Phase 1** | 项目初始化 | Day 1 | 4h | 开发 | 目录结构+路径替换完成 |
| **Phase 2** | 配置文件创建 | Day 1-2 | 3h | 开发 | 配置文件+验证脚本 |
| **Phase 3** | 核心模型修改 | Day 2-4 | 10h | 开发 | 优化模型代码 |
| **Phase 4** | DAC模块开发 | Day 3-4 | 4h | 开发 | DAC模块代码 |
| **Phase 5** | 碳排放模块修改 | Day 4-5 | 3h | 开发 | 排放计算代码 |
| **Phase 6** | 测试和验证 | Day 5-6 | 8h | 测试+开发 | 测试报告+结果验证 |
| **Phase 7** | 文档和交付 | Day 6-7 | 4h | 开发 | 完整交付包 |
| **总计** | | **7个工作日** | **36h** | | 完整v4.0产品 |

### 9.2 关键里程碑

1. **M1 - Day 2结束**: 配置文件和目录结构完成,可以导入模块
2. **M2 - Day 4结束**: 核心模型和DAC模块开发完成,代码可运行
3. **M3 - Day 6结束**: 测试通过,结果验证完成
4. **M4 - Day 7结束**: 文档完整,项目交付

### 9.3 风险缓冲

- 每个Phase预留10%时间缓冲
- 如遇到Gurobi求解问题,可能需要+1天调优
- 如碳排放计算有争议,可能需要+0.5天讨论

---

## 十、与v2.0的全面对比分析

### 10.1 技术对比

| 维度 | v2.0 工业CCS捕获 | v4.0 DAC大气捕获 | 优势方 |
|-----|----------------|----------------|--------|
| **CO₂来源** | 4311个工业点源 | 大气(415 ppm) | v4.0(无限资源) |
| **CO₂浓度** | 15-20% | 0.04% → 99.5% | v2.0(高浓度) |
| **捕获技术** | CCS烟气捕获 | DAC化学吸附 | - |
| **能耗** | 100-150 kWh/ton | **350 kWh/ton** | v2.0(低能耗) |
| **成本** | 150-250元/吨 | **4500元/吨** | v2.0(低成本) |
| **碳强度** | 25 gCO₂e/MJ | **10-15 gCO₂e/MJ** | **v4.0(最低碳)** |
| **CORSIA合规** | ✅ 满足 | ✅ **优秀满足** | **v4.0** |
| **地理限制** | 需近工业区 | **无限制** | **v4.0** |
| **资源限制** | 受工业产能限制 | **无限制** | **v4.0** |
| **运输复杂度** | 高(管道/罐车) | **无(本地)** | **v4.0** |
| **系统复杂度** | 高(4311点源) | **中(本地设备)** | **v4.0** |
| **技术成熟度** | 高(商业化) | **中(示范阶段)** | v2.0 |
| **成本趋势** | 稳定 | **快速下降** | v4.0(未来) |

### 10.2 经济性对比(单位:元/kg SAF)

| 成本项 | v2.0 | v4.0 | 差异 |
|-------|------|------|------|
| H₂成本 | 5.0 | 5.0 | 0 |
| **CO₂成本** | **0.9** | **15.8** | **+14.9** ⚠️ |
| 甲醇合成 | 2.0 | 2.0 | 0 |
| MTJ转化 | 1.5 | 1.5 | 0 |
| 运输 | 1.5 | 1.2 | -0.3 |
| **总成本** | **10.9** | **25.5** | **+14.6 (+134%)** ⚠️ |

**成本结论**: v4.0当前成本是v2.0的2.3倍,主要因DAC成本高

**2030年预测**(DAC成本降至2500元/吨):

| 成本项 | v2.0(2030) | v4.0(2030) | 差异 |
|-------|-----------|-----------|------|
| CO₂成本 | 0.9 | **8.8** | +7.9 |
| **总成本** | **10.9** | **18.5** | **+7.6 (+70%)** |

### 10.3 环境效益对比

| 指标 | v2.0 | v4.0 | v4.0优势 |
|-----|------|------|---------|
| Well-to-Wake碳强度 | 25 gCO₂e/MJ | **10-15 gCO₂e/MJ** | **-40%至-60%** |
| vs传统航煤减排 | 72% | **83-89%** | **+11-17%** |
| CORSIA超额达标 | 44% | **66-77%** | **+22-33%** |
| CO₂来源可持续性 | 依赖工业(化石) | **100%大气** | ✅ |
| 长期碳中和潜力 | 中等 | **最高** | ✅ |

### 10.4 代码复杂度对比

| 指标 | v2.0 | v4.0 | 变化 |
|-----|------|------|------|
| 决策变量数 | ~600万 | **~40万** | **-94%** ✅ |
| 约束条件数 | ~580万 | **~2.5万** | **-99%** ✅ |
| 代码行数 | ~7300行 | **~7050行** | **-3%** ✅ |
| GIS数据依赖 | 4类文件 | **0类** | **-100%** ✅ |
| 模型求解时间 | 45-60分钟 | **<30分钟(预期)** | **-50%** ✅ |

### 10.5 应用场景对比

| 场景 | v2.0适用性 | v4.0适用性 | 推荐 |
|-----|-----------|-----------|------|
| **追求极致低碳** | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | v4.0 |
| **高端市场/出口** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | v4.0 |
| **无工业基础设施** | ⭐ | ⭐⭐⭐⭐⭐ | v4.0 |
| **ESG目标导向** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | v4.0 |
| **成本敏感项目** | ⭐⭐⭐⭐⭐ | ⭐⭐ | v2.0 |
| **已有工业基础** | ⭐⭐⭐⭐⭐ | ⭐⭐ | v2.0 |
| **短期商业化** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | v2.0 |
| **2030+长期** | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | v4.0 |

---

## 十一、关键技术参数数据源

### 11.1 DAC技术参数

| 参数 | 数值 | 数据来源 |
|-----|------|---------|
| 捕获效率 | 95% | Climeworks (2023) Technology Whitepaper |
| CO₂纯度 | >99.5% | IEA (2023) Direct Air Capture Report |
| 能耗 | 350 kWh/ton | Carbon180 (2024) State of DAC |
| 当前成本 | 4500元/吨 | IEA (2023), 换算至CNY |
| 2030成本 | 2500元/吨 | IPCC (2024) CDR and Storage |
| 模块容量 | 2000 ton/年 | Climeworks Orca plant specification |

### 11.2 碳排放参数

| 参数 | 数值 | 数据来源 |
|-----|------|---------|
| DAC设备隐含排放 | 0.05 kgCO₂e/kg CO₂ | de Jonge et al. (2019) Nature Energy |
| 可再生电力碳强度 | 0.02 kgCO₂e/kWh | 中国可再生能源LCA数据库 (2023) |
| v4.0估算碳强度 | 10-15 gCO₂e/MJ | 本研究计算,保守估算 |

### 11.3 经济参数

| 参数 | 数值 | 数据来源 |
|-----|------|---------|
| CAPEX(单模块) | 1000万元 | IEA (2023), 换算至CNY |
| OPEX比例 | 5%/年 | 行业惯例 |
| 设备寿命 | 20年 | Climeworks技术文档 |
| 成本下降率 | 10%/年 | Carbon180学习曲线预测 |

---

## 十二、风险与缓解措施

### 12.1 技术风险

| 风险 | 影响 | 概率 | 缓解措施 |
|-----|------|------|---------|
| **DAC成本未如期下降** | 高 | 中 | 敏感性分析,准备Plan B(v2.0) |
| **DAC能耗高于预期** | 中 | 低 | 增加可再生能源容量 |
| **DAC设备可靠性问题** | 高 | 低 | 选择成熟供应商(Climeworks) |
| **模块化扩展困难** | 中 | 低 | 预留充足场地和接口 |

### 12.2 模型风险

| 风险 | 影响 | 概率 | 缓解措施 |
|-----|------|------|---------|
| **Gurobi求解失败** | 高 | 低 | 简化约束,增加求解时间 |
| **配置参数错误** | 中 | 中 | 运行验证脚本 |
| **碳排放计算争议** | 中 | 中 | 引用权威数据源,保守估算 |

### 12.3 实施风险

| 风险 | 影响 | 概率 | 缓解措施 |
|-----|------|------|---------|
| **开发时间超期** | 中 | 中 | 预留时间缓冲 |
| **测试数据不足** | 低 | 低 | 使用v2.0测试数据改编 |
| **复用代码bug** | 中 | 低 | 充分测试复用模块 |

---

## 十三、验收标准

### 13.1 功能验收

- [ ] ✅ 模型可成功构建并求解
- [ ] ✅ 所有决策变量取值合理
- [ ] ✅ 所有约束条件满足
- [ ] ✅ 目标函数收敛
- [ ] ✅ DAC供应量满足CO₂需求
- [ ] ✅ 可再生能源满足DAC能耗
- [ ] ✅ 生成完整CSV报告
- [ ] ✅ 生成DAC设备配置报告

### 13.2 性能验收

- [ ] ✅ 模型求解时间 < 30分钟(1周范围)
- [ ] ✅ 决策变量数 < 50万
- [ ] ✅ 约束条件数 < 5万
- [ ] ✅ 内存占用 < 16GB
- [ ] ✅ 代码符合PEP8规范

### 13.3 结果验收

- [ ] ✅ 碳强度 = 10-15 gCO₂e/MJ
- [ ] ✅ CORSIA合规(<44.5 gCO₂e/MJ)
- [ ] ✅ DAC成本符合配置参数
- [ ] ✅ 能耗计算正确(350 kWh/ton)
- [ ] ✅ 与v2.0结果可对比

### 13.4 文档验收

- [ ] ✅ README.md完整清晰
- [ ] ✅ 所有函数有docstring
- [ ] ✅ 配置文件有详细注释
- [ ] ✅ 示例输出文件完整

---

## 十四、附录:关键代码片段

### A1. DAC供应变量定义

```python
# 核心代码:DAC CO₂供应量决策变量
for plant_id in self.saf_plant_ids:
    for t in range(self.T):
        var_name = f"dac_co2_supply_plant{plant_id}_t{t}"
        self.dac_co2_supply[plant_id, t] = self.model.addVar(
            lb=0,
            ub=self.GRB.INFINITY,  # 大气CO₂无限
            name=var_name,
            vtype=self.GRB.CONTINUOUS
        )
```

### A2. DAC能耗约束

```python
# 核心约束:DAC能耗不超过可再生能源供应
for plant_id in self.saf_plant_ids:
    for t in range(self.T):
        dac_energy = (self.dac_co2_supply[plant_id, t] / 1000) * 350
        self.model.addConstr(
            dac_energy <= self.renewable_energy_supply[plant_id, t],
            name=f"dac_energy_limit_{plant_id}_{t}"
        )
```

### A3. DAC成本项

```python
# 目标函数:DAC成本项
dac_cost = self.model.quicksum(
    (self.dac_co2_supply[plant_id, t] / 1000) * 4500  # 元/吨
    for plant_id in self.saf_plant_ids
    for t in range(self.T)
)
self.total_cost += dac_cost
```

### A4. CO₂物料平衡

```python
# 简化的CO₂平衡约束(DAC版本)
for plant_id in self.saf_plant_ids:
    for t in range(self.T):
        co2_supply = self.dac_co2_supply[plant_id, t]  # DAC供应
        co2_demand = (
            self.methanol_production[plant_id, t] * 2.8  # kg CO₂/kg甲醇
        )
        self.model.addConstr(
            co2_supply >= co2_demand,
            name=f"co2_balance_dac_{plant_id}_{t}"
        )
```

### A5. DAC碳排放计算

```python
# DAC捕获过程排放
def calculate_dac_capture_emission(self, co2_kg):
    equipment_emission = co2_kg * 0.05  # 设备隐含排放
    energy_emission = (co2_kg / 1000) * 350 * 0.02  # 能耗排放
    return equipment_emission + energy_emission

# 总排放(简化)
total_emission = (
    h2_emission  # 氢气
    + dac_capture_emission  # DAC捕获
    + h2_transport_emission  # 氢气运输
    + process_emission  # 工艺
    - co2_amount_kg  # CO₂利用负排放
)

carbon_intensity = (total_emission / (saf_kg * 43.15)) * 1000  # gCO₂e/MJ
```

---

## 结语

本PRD详细描述了从v2.0工业CCS捕获版本到v4.0 DAC大气捕获版本的完整迁移和开发计划。

**核心优势**:
- ✅ 碳强度最优(10-15 gCO₂e/MJ)
- ✅ 无地理限制
- ✅ 无资源限制
- ✅ 系统大幅简化

**当前挑战**:
- ⚠️ 成本高(4500元/吨,是v2.0的20倍)
- ⚠️ 能耗高(350 kWh/ton,是v2.0的2.5倍)

**未来展望**:
- 📈 2030年成本预期降至2500元/吨
- 📈 技术成熟度快速提升
- 📈 碳信用价值增加,经济性改善

**实施建议**:
1. 短期(2024-2026): v2.0和v4.0并行,v2.0为主
2. 中期(2026-2030): 逐步过渡到v4.0
3. 长期(2030+): v4.0为主流技术路线

---

**文档版本**: v4.0.0
**最后更新**: 2025-10-28
**下一步**: 开始Phase 1实施
