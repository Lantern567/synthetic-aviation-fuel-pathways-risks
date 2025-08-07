## [新增] 批量下载与批量读取MERRA2 nc数据
- 新增 scripts/download_all.py 支持NASA Earthdata认证批量下载
- 新增 src/data_loader.py::load_all_nc_files 支持批量读取所有nc文件
- 所有功能均有自动化单元测试
- 更新README用法说明 