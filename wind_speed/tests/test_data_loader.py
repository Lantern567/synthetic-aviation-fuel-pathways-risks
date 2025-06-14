import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))
from data_loader import read_nc_file, download_merra2_data, load_all_nc_files

def test_read_nc_file():
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    nc_path = os.path.join(base_dir, "data", "MERRA2_400.inst3_3d_asm_Nv.20240101.SUB.nc")
    ds = read_nc_file(nc_path)
    assert ds is not None
    assert hasattr(ds, 'variables')
    assert len(ds.variables.keys()) > 0 

def test_download_merra2_data():
    download_merra2_data()
    # 检查部分已知文件是否下载
    assert os.path.exists('data/MERRA2_400.inst3_3d_asm_Nv.20240101.SUB.nc') 

def test_load_all_nc_files():
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    data_dir = os.path.join(base_dir, 'data')
    nc_dict = load_all_nc_files(data_dir)
    assert isinstance(nc_dict, dict)
    assert len(nc_dict) > 0
    for k, ds in nc_dict.items():
        assert hasattr(ds, 'variables') 