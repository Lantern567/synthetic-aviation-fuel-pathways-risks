"""
场景注册表 - 定义13个SAF场景的模型类、配置文件路径和敏感性参数映射
"""
import os
from pathlib import Path
from typing import Dict, Any, Optional, List

# 项目根目录
PROJECT_ROOT = Path(__file__).resolve().parents[3]

# ============================================================================
# 参数范围定义
# ============================================================================

# NG价格扫描范围 (元/m³)，9个点
NG_PRICE_VALUES = [2.0, 2.5, 3.0, 3.5, 4.2, 5.0, 6.0, 7.0, 8.0]

# 煤价扫描范围 (元/吨)，7个点
COAL_PRICE_VALUES = [280, 350, 420, 525, 630, 700, 840]

# 副产氢PSA设备CAPEX扫描范围 (元/(kg H₂/hour))，7个点
BH_CAPEX_VALUES = [140_000, 180_000, 224_000, 280_000, 320_000, 360_000, 400_000]

# 电价扫描范围 (元/kWh)，5个点
ELECTRICITY_PRICE_VALUES = [0.25, 0.35, 0.50, 0.60, 0.80]

# 电解槽CAPEX扫描范围 (元/(kg H₂/hour))，5个点
ELECTROLYZER_CAPEX_VALUES = [200_000, 360_000, 500_000, 700_000, 1_000_000]

# DAC成本扫描范围 (元/ton CO₂)，8个点（从高成本到低成本展示降本路径）
DAC_COST_VALUES = [4500, 3500, 2500, 1500, 1000, 700, 500, 300]


# ============================================================================
# 场景定义
# ============================================================================

def _cfg(relative_path: str) -> str:
    """返回绝对配置文件路径"""
    return str(PROJECT_ROOT / relative_path)


SCENARIOS: Dict[str, Dict[str, Any]] = {

    # ========== Group A: 天然气路径 (NaturalGasSupplyChainOptimizer) ==========

    "GTL-GH": {
        "description": "天然气两步法（甲醇-SAF），绿氢来自天然气重整",
        "model_module": "products.supply_chain_optimization.natural_gas_supply_chain_optimization.src.core.natural_gas_optimization_model",
        "model_class": "NaturalGasSupplyChainOptimizer",
        "config_path": _cfg("shared/data/NaturalGasSupplyChainOptimizer_config.yaml"),
        "log_subdir": "sensitivity/gtl_gh",
        "sensitivity_params": {
            "ng_price": {
                "values": NG_PRICE_VALUES,
                "config_key": "cost_parameters.raw_materials.natural_gas_price_yuan_per_m3",
                "use_ng_override": True,  # 需要额外调用 set_ng_price_override()
                "label": "天然气价格 (元/m³)",
            }
        }
    },

    "GTL": {
        "description": "天然气一步法FT（天然气→合成燃料）",
        "model_module": "products.supply_chain_optimization.natural_gas_supply_chain_optimization.src.core.natural_gas_optimization_model_one_step",
        "model_class": "NaturalGasSupplyChainOptimizerOneStep",
        "config_path": _cfg("shared/data/NaturalGasSupplyChainOptimizer_config_one_step.yaml"),
        "log_subdir": "sensitivity/gtl",
        "sensitivity_params": {
            "ng_price": {
                "values": NG_PRICE_VALUES,
                "config_key": "cost_parameters.raw_materials.natural_gas_price_yuan_per_m3",
                "use_ng_override": True,
                "label": "天然气价格 (元/m³)",
            }
        }
    },

    "GTL-BH": {
        "description": "天然气+副产氢两步法（钢铁/炼油废气净化，甲醇-SAF）",
        "model_module": "products.supply_chain_optimization.natural_gas_supply_chain_optimization.src.core.natural_gas_optimization_model",
        "model_class": "NaturalGasSupplyChainOptimizer",
        "config_path": _cfg("shared/data/NaturalGasByproductHydrogenOptimizer_config.yaml"),
        "log_subdir": "sensitivity/gtl_bh",
        "sensitivity_params": {
            "ng_price": {
                "values": NG_PRICE_VALUES,
                "config_key": "cost_parameters.raw_materials.natural_gas_price_yuan_per_m3",
                "use_ng_override": True,
                "label": "天然气价格 (元/m³)",
            },
            "bh_capex": {
                "values": BH_CAPEX_VALUES,
                # GTL-BH使用分开的钢铁/炼油CAPEX，两者同步扫描
                "config_key": [
                    "equipment_raw_costs.electrolyzer.byproduct_steel_capex_raw",
                    "equipment_raw_costs.electrolyzer.byproduct_refinery_capex_raw",
                ],
                "scale_factors": [1.0, 224000/280000],  # 炼油=钢铁×(224k/280k)
                "label": "副产氢PSA设备CAPEX (元/(kg/h))",
            }
        }
    },

    # ========== Group B: 煤氢路径 (CoalHydrogenSAFOptimizer) ==========

    "CTL": {
        "description": "煤制氢两步法（煤气化制氢，甲醇-SAF）",
        "model_module": "products.supply_chain_optimization.coal_hydrogen_saf_optimization.src.core.coal_hydrogen_optimization_model",
        "model_class": "CoalHydrogenSAFOptimizer",
        "config_path": _cfg("products/supply_chain_optimization/coal_hydrogen_saf_optimization/data/CoalHydrogenSAFOptimizer_config.yaml"),
        "log_subdir": "sensitivity/ctl",
        "sensitivity_params": {
            "coal_price": {
                "values": COAL_PRICE_VALUES,
                "config_key": "coal_parameters.coal_price_yuan_per_ton",
                "label": "煤炭价格 (元/吨)",
            }
        }
    },

    "CTL-BH": {
        "description": "煤制氢+副产氢两步法",
        "model_module": "products.supply_chain_optimization.coal_hydrogen_saf_optimization.src.core.coal_hydrogen_optimization_model",
        "model_class": "CoalHydrogenSAFOptimizer",
        "config_path": _cfg("shared/data/CoalByproductHydrogenSAFOptimizer_config.yaml"),
        "log_subdir": "sensitivity/ctl_bh",
        "sensitivity_params": {
            "coal_price": {
                "values": COAL_PRICE_VALUES,
                "config_key": "coal_parameters.coal_price_yuan_per_ton",
                "label": "煤炭价格 (元/吨)",
            },
            "bh_capex": {
                "values": BH_CAPEX_VALUES,
                "config_key": "equipment_raw_costs.electrolyzer.capex_raw",
                "label": "副产氢PSA设备CAPEX (元/(kg/h))",
            }
        }
    },

    # ========== Group C: 绿氢路径 (GreenHydrogenSupplyChainOptimizer) ==========

    "CCU-GH-MTJ": {
        "description": "CCU+绿氢两步法（电解水制氢，甲醇-SAF）",
        "model_module": "products.supply_chain_optimization.green_hydrogen_supply_chain_optimization.src.core.green_hydrogen_optimization_model",
        "model_class": "GreenHydrogenSupplyChainOptimizer",
        "config_path": _cfg("shared/data/GreenHydrogenSupplyChainOptimizer_config_two_step.yaml"),
        "model_kwargs": {"process_mode": "two_step"},
        "log_subdir": "sensitivity/ccu_gh_mtj",
        "sensitivity_params": {
            "electricity_capex_grid": {
                "values": [(e, c) for e in ELECTRICITY_PRICE_VALUES for c in ELECTROLYZER_CAPEX_VALUES],
                "config_keys": {
                    "electricity": "cost_parameters.renewable_energy.grid_electricity_price_yuan_per_kwh",
                    "capex": "equipment_raw_costs.electrolyzer.capex_raw",
                },
                "label": "电价 × 电解槽CAPEX 二维扫描",
            }
        }
    },

    "CCU-GH-FT": {
        "description": "CCU+绿氢一步法FT（电解水制氢）",
        "model_module": "products.supply_chain_optimization.green_hydrogen_supply_chain_optimization.src.core.green_hydrogen_optimization_model",
        "model_class": "GreenHydrogenSupplyChainOptimizer",
        "config_path": _cfg("shared/data/GreenHydrogenSupplyChainOptimizer_config.yaml"),  # 与主结果一致（h2_ratio=0.45）
        "model_kwargs": {"process_mode": "one_step"},
        "log_subdir": "sensitivity/ccu_gh_ft",
        "sensitivity_params": {
            "electricity_capex_grid": {
                "values": [(e, c) for e in ELECTRICITY_PRICE_VALUES for c in ELECTROLYZER_CAPEX_VALUES],
                "config_keys": {
                    "electricity": "cost_parameters.renewable_energy.grid_electricity_price_yuan_per_kwh",
                    "capex": "equipment_raw_costs.electrolyzer.capex_raw",
                },
                "label": "电价 × 电解槽CAPEX 二维扫描",
            }
        }
    },

    "CCU-BH-MTJ": {
        "description": "CCU+副产氢两步法（甲醇-SAF）",
        "model_module": "products.supply_chain_optimization.green_hydrogen_supply_chain_optimization.src.core.green_hydrogen_optimization_model",
        "model_class": "GreenHydrogenSupplyChainOptimizer",
        "config_path": _cfg("shared/data/ByproductHydrogenSupplyChainOptimizer_config_two_step.yaml"),
        "model_kwargs": {"process_mode": "two_step"},
        "log_subdir": "sensitivity/ccu_bh_mtj",
        "sensitivity_params": {
            "bh_capex": {
                "values": BH_CAPEX_VALUES,
                # 同步扫描钢铁+炼油两类副产氢PSA设备CAPEX（与GTL-BH一致）
                "config_key": [
                    "equipment_raw_costs.electrolyzer.byproduct_steel_capex_raw",
                    "equipment_raw_costs.electrolyzer.byproduct_refinery_capex_raw",
                ],
                "scale_factors": [1.0, 224000/280000],  # 炼油=钢铁×(224k/280k)
                "label": "副产氢PSA设备CAPEX (元/(kg/h))",
            }
        }
    },

    "CCU-BH-FT": {
        "description": "CCU+副产氢一步法FT",
        "model_module": "products.supply_chain_optimization.green_hydrogen_supply_chain_optimization.src.core.green_hydrogen_optimization_model",
        "model_class": "GreenHydrogenSupplyChainOptimizer",
        "config_path": _cfg("shared/data/ByproductHydrogenSupplyChainOptimizer_config.yaml"),
        "model_kwargs": {"process_mode": "one_step"},
        "log_subdir": "sensitivity/ccu_bh_ft",
        "sensitivity_params": {
            "bh_capex": {
                "values": BH_CAPEX_VALUES,
                "config_key": [
                    "equipment_raw_costs.electrolyzer.byproduct_steel_capex_raw",
                    "equipment_raw_costs.electrolyzer.byproduct_refinery_capex_raw",
                ],
                "scale_factors": [1.0, 224000/280000],
                "label": "副产氢PSA设备CAPEX (元/(kg/h))",
            }
        }
    },

    # ========== Group D: DAC路径 (DACHydrogenSAFOptimizer) ==========

    "DAC-GH-MTJ": {
        "description": "DAC+绿氢两步法（甲醇-SAF）",
        "model_module": "products.supply_chain_optimization.dac_hydrogen_saf_supply_chain_optimization.src.core.dac_hydrogen_optimization_model",
        "model_class": "DACHydrogenSAFOptimizer",
        "config_path": _cfg("shared/config/DACHydrogenSAFOptimizer_config_two_step.yaml"),
        "model_kwargs": {"process_mode": "two_step"},
        "log_subdir": "sensitivity/dac_gh_mtj",
        "sensitivity_params": {
            "dac_cost": {
                "values": DAC_COST_VALUES,
                "config_key": "dac_parameters.capture_cost_yuan_per_ton",
                "label": "DAC捕获成本 (元/ton CO₂)",
            },
            "electricity_capex_grid": {
                "values": [(e, c) for e in ELECTRICITY_PRICE_VALUES for c in ELECTROLYZER_CAPEX_VALUES],
                "config_keys": {
                    "electricity": "cost_parameters.renewable_energy.grid_electricity_price_yuan_per_kwh",
                    "capex": "equipment_raw_costs.electrolyzer.capex_raw",
                },
                "label": "电价 × 电解槽CAPEX 二维扫描",
            }
        }
    },

    "DAC-GH-FT": {
        "description": "DAC+绿氢一步法FT",
        "model_module": "products.supply_chain_optimization.dac_hydrogen_saf_supply_chain_optimization.src.core.dac_hydrogen_optimization_model",
        "model_class": "DACHydrogenSAFOptimizer",
        "config_path": _cfg("shared/config/DACHydrogenSAFOptimizer_config.yaml"),
        "model_kwargs": {"process_mode": "one_step"},
        "log_subdir": "sensitivity/dac_gh_ft",
        "sensitivity_params": {
            "dac_cost": {
                "values": DAC_COST_VALUES,
                "config_key": "dac_parameters.capture_cost_yuan_per_ton",
                "label": "DAC捕获成本 (元/ton CO₂)",
            },
            "electricity_capex_grid": {
                "values": [(e, c) for e in ELECTRICITY_PRICE_VALUES for c in ELECTROLYZER_CAPEX_VALUES],
                "config_keys": {
                    "electricity": "cost_parameters.renewable_energy.grid_electricity_price_yuan_per_kwh",
                    "capex": "equipment_raw_costs.electrolyzer.capex_raw",
                },
                "label": "电价 × 电解槽CAPEX 二维扫描",
            }
        }
    },

    "DAC-BH-MTJ": {
        "description": "DAC+副产氢两步法（甲醇-SAF）",
        "model_module": "products.supply_chain_optimization.dac_hydrogen_saf_supply_chain_optimization.src.core.dac_hydrogen_optimization_model",
        "model_class": "DACHydrogenSAFOptimizer",
        "config_path": _cfg("shared/data/DACByproductHydrogenSAFOptimizer_config_two_step.yaml"),
        "model_kwargs": {"process_mode": "two_step"},
        "log_subdir": "sensitivity/dac_bh_mtj",
        "sensitivity_params": {
            "dac_cost": {
                "values": DAC_COST_VALUES,
                "config_key": "dac_parameters.capture_cost_yuan_per_ton",
                "label": "DAC捕获成本 (元/ton CO₂)",
            },
            "bh_capex": {
                "values": BH_CAPEX_VALUES,
                "config_key": [
                    "equipment_raw_costs.electrolyzer.byproduct_steel_capex_raw",
                    "equipment_raw_costs.electrolyzer.byproduct_refinery_capex_raw",
                ],
                "scale_factors": [1.0, 224000/280000],
                "label": "副产氢PSA设备CAPEX (元/(kg/h))",
            }
        }
    },

    "DAC-BH-FT": {
        "description": "DAC+副产氢一步法FT",
        "model_module": "products.supply_chain_optimization.dac_hydrogen_saf_supply_chain_optimization.src.core.dac_hydrogen_optimization_model",
        "model_class": "DACHydrogenSAFOptimizer",
        "config_path": _cfg("shared/data/DACByproductHydrogenSAFOptimizer_config_one_step.yaml"),
        "model_kwargs": {"process_mode": "one_step"},
        "log_subdir": "sensitivity/dac_bh_ft",
        "sensitivity_params": {
            "dac_cost": {
                "values": DAC_COST_VALUES,
                "config_key": "dac_parameters.capture_cost_yuan_per_ton",
                "label": "DAC捕获成本 (元/ton CO₂)",
            },
            "bh_capex": {
                "values": BH_CAPEX_VALUES,
                "config_key": [
                    "equipment_raw_costs.electrolyzer.byproduct_steel_capex_raw",
                    "equipment_raw_costs.electrolyzer.byproduct_refinery_capex_raw",
                ],
                "scale_factors": [1.0, 224000/280000],
                "label": "副产氢PSA设备CAPEX (元/(kg/h))",
            }
        }
    },
}


def get_scenario(scenario_name: str) -> Dict[str, Any]:
    """获取场景配置"""
    if scenario_name not in SCENARIOS:
        raise ValueError(f"未知场景: {scenario_name}。可用场景: {list(SCENARIOS.keys())}")
    return SCENARIOS[scenario_name]


def list_scenarios() -> List[str]:
    """返回所有场景名称列表"""
    return list(SCENARIOS.keys())


def get_all_run_tasks() -> List[Dict[str, Any]]:
    """
    生成所有敏感性分析任务列表。
    每个任务是一个字典，包含 scenario_name, param_name, param_value (或 param_values 对于二维)。
    """
    tasks = []
    for scenario_name, scenario in SCENARIOS.items():
        for param_name, param_config in scenario["sensitivity_params"].items():
            for v in param_config["values"]:
                task = {
                    "scenario_name": scenario_name,
                    "param_name": param_name,
                    "param_value": v,
                }
                tasks.append(task)
    return tasks


def count_total_runs() -> int:
    """统计总运行次数"""
    return len(get_all_run_tasks())


if __name__ == "__main__":
    print(f"场景总数: {len(SCENARIOS)}")
    print(f"总运行次数: {count_total_runs()}")
    for name, scenario in SCENARIOS.items():
        print(f"\n{name}: {scenario['description']}")
        for param_name, param_config in scenario["sensitivity_params"].items():
            print(f"  {param_name}: {len(param_config['values'])} 个值")
