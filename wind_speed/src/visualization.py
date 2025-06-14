import matplotlib.pyplot as plt
import numpy as np

def plot_variable(ds, var_name, time_index=0, level_index=0, save_path=None, custom_data=None, var_name_for_title=None):
    """
    可视化nc文件中的某个变量（二维切片），自动用lon/lat为坐标。
    ds: netCDF4.Dataset对象
    var_name: 变量名
    time_index: 时间维度索引
    level_index: 层级索引（如有）
    save_path: 图片保存路径
    custom_data: 可选，直接传入要可视化的数据（如风速）
    var_name_for_title: 可选，标题显示的变量名
    """
    if custom_data is not None:
        data = custom_data
        dims = ('time', 'lev', 'lat', 'lon')
    else:
        var = ds.variables[var_name]
        dims = var.dimensions
        data = var[:]
    lon = ds.variables['lon'][:]
    lat = ds.variables['lat'][:]
    lev = ds.variables['lev'][:]
    lev_str = f"lev={lev[level_index]}"
    if ('time' in dims) and ('lev' in dims):
        img = data[time_index, level_index, :, :]
    elif 'time' in dims:
        img = data[time_index, :, :]
    else:
        img = data[:]
    plt.figure(figsize=(8,6))
    plt.pcolormesh(lon, lat, img, shading='auto')
    plt.xlabel('Longitude')
    plt.ylabel('Latitude')
    title_var = var_name_for_title if var_name_for_title else var_name
    plt.title(f'{title_var} (time={time_index}, {lev_str})')
    plt.colorbar(label=title_var)
    if save_path:
        plt.savefig(save_path)
    else:
        plt.show() 