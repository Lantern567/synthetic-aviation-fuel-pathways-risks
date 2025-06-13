from data_loader import read_nc_file, calc_wind_speed
from visualization import plot_variable
import os
import numpy as np

if __name__ == "__main__":
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    nc_path = os.path.join(base_dir, "data", "MERRA2_400.inst3_3d_asm_Nv.20240101.SUB.nc")
    ds = read_nc_file(nc_path)
    print("文件变量列表：", list(ds.variables.keys()))
    main_vars = [k for k in ds.variables.keys() if len(ds.variables[k].shape) >= 2]
    time_values = ds.variables['time'][:]
    lev_values = ds.variables['lev'][:]
    # 合成风速
    wind_speed = calc_wind_speed(ds)
    for t_idx, t_val in enumerate(time_values):
        for l_idx, l_val in enumerate(lev_values):
            print(f"可视化变量: wind_speed, time={t_val}, lev={l_val}")
            save_path = os.path.join(base_dir, "results", "figures", f"wind_speed_time{t_val}_lev{l_val}.png")
            # wind_speed shape: (time, lev, lat, lon)
            plot_variable(ds, None, time_index=t_idx, level_index=l_idx, save_path=save_path, custom_data=wind_speed, var_name_for_title='wind_speed')
    if not main_vars:
        print("未找到可视化的主变量！")
    else:
        for var_name in main_vars:
            for t_idx, t_val in enumerate(time_values):
                for l_idx, l_val in enumerate(lev_values):
                    print(f"可视化变量: {var_name}, time={t_val}, lev={l_val}")
                    save_path = os.path.join(base_dir, "results", "figures", f"{var_name}_time{t_val}_lev{l_val}.png")
                    plot_variable(ds, var_name, time_index=t_idx, level_index=l_idx, save_path=save_path) 