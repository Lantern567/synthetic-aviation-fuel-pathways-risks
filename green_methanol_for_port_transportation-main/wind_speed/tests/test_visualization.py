import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))
from data_loader import read_nc_file
from visualization import plot_variable

def test_plot_variable():
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    nc_path = os.path.join(base_dir, "data", "MERRA2_400.inst3_3d_asm_Nv.20240101.SUB.nc")
    ds = read_nc_file(nc_path)
    # 只测试shape维度大于等于2的主变量
    main_vars = [k for k in ds.variables.keys() if len(ds.variables[k].shape) >= 2]
    assert main_vars, "未找到可视化的主变量！"
    for var_name in main_vars:
        save_path = os.path.join(base_dir, "results", "figures", f"{var_name}_test.png")
        plot_variable(ds, var_name, save_path=save_path)
        assert os.path.exists(save_path) 