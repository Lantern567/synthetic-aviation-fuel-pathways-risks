import sys
import types
import importlib
from pathlib import Path
import pandas as pd


def test_average_distance_calculation_without_mtj_attributes():
    # 在导入目标模块前，注入gurobipy最小桩以避免真实依赖
    mock_gurobi = types.SimpleNamespace(
        GRB=types.SimpleNamespace(OPTIMAL=2, INFEASIBLE=3, UNBOUNDED=5)
    )
    sys.modules['gurobipy'] = mock_gurobi

    # 确保项目根目录在sys.path
    project_root = Path(__file__).resolve().parents[4]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    mod = importlib.import_module(
        'products.supply_chain_optimization.natural_gas_supply_chain_optimization.src.natural_gas_optimization_model_refactored'
    )
    Optimizer = getattr(mod, 'NaturalGasSupplyChainOptimizer')

    # 构造最小化数据集（2个机场，简短时域）
    optimizer = Optimizer(time_horizon_weeks=1, use_graphhopper_routing=False)

    airport_df = pd.DataFrame([
        {"airport": "北京首都国际机场", "week_1": 1000},
        {"airport": "上海浦东国际机场", "week_1": 1200},
    ])

    # 直接从Excel处理流程走，覆盖load_data路径
    airport_data = optimizer._process_excel_airport_data(airport_df)

    # 简单的可再生能源数据（两条小时记录）
    renewable_df = pd.DataFrame([
        {"plant_name": "北京太阳能电站1", "type": "solar_plant", "latitude": 40.2, "longitude": 116.5,
         "capacity_mw": 100, "power_output_mw": 50, "hour": 0},
        {"plant_name": "河北风电场1", "type": "wind_farm", "latitude": 39.8, "longitude": 115.5,
         "capacity_mw": 200, "power_output_mw": 120, "hour": 0},
    ])

    # 调用load_data（内部会在未启用GraphHopper时跳过距离统计计算）
    optimizer.load_data(renewable_data=renewable_df, airport_data=airport_data)

    # 在未启用GraphHopper情况下，平均距离应保持为默认或None，不抛异常
    assert hasattr(optimizer, "avg_hydrogen_transport_distance")
    assert hasattr(optimizer, "avg_ng_transport_distance")

    # 显式调用内部方法，确认不会因mtj_locations缺失而报错
    optimizer._calculate_average_distances()

    # 计算后应有数值（容错下可能为默认值）
    assert optimizer.avg_hydrogen_transport_distance is not None
    assert optimizer.avg_ng_transport_distance is not None


