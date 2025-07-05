import netCDF4 as nc
import numpy as np
import os
try:
    from .download_utils import download_files_from_txt
except ImportError:
    from download_utils import download_files_from_txt

def read_nc_file(file_path):
    """
    读取netCDF（.nc）文件，返回数据集对象。
    """
    ds = nc.Dataset(file_path, 'r')
    return ds

def calc_wind_speed(ds, u_var='U', v_var='V'):
    """
    根据U、V分量计算合成风速，返回与U/V同shape的风速数组。
    """
    u = ds.variables[u_var][:]
    v = ds.variables[v_var][:]
    wind_speed = np.sqrt(u**2 + v**2)
    return wind_speed

def download_merra2_data():
    txt_path = os.path.join(os.path.dirname(__file__), '../data/subset_M2I3NVASM_5.12.4_20250612_172231_.txt')
    save_dir = os.path.join(os.path.dirname(__file__), '../data')
    download_files_from_txt(txt_path, save_dir)

def load_all_nc_files(data_dir):
    """
    批量读取指定文件夹下所有.nc文件，返回{文件名: Dataset对象}的字典。
    """
    nc_files = [f for f in os.listdir(data_dir) if f.endswith('.nc')]
    nc_dict = {}
    for f in nc_files:
        path = os.path.join(data_dir, f)
        try:
            nc_dict[f] = nc.Dataset(path, 'r')
        except Exception as e:
            print(f"读取失败: {f}, 错误: {e}")
    return nc_dict 