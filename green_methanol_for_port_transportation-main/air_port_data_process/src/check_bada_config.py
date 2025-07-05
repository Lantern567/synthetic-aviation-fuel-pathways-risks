#!/usr/bin/env python3
"""
检查pyBADA配置和可用飞机列表
"""

import pyBADA.configuration as config
import os

def check_bada_configuration():
    """检查pyBADA配置"""
    print("=== 检查pyBADA配置 ===")
    
    try:
        # 检查数据路径
        data_path = config.getDataPath()
        print(f"数据路径: {data_path}")
        print(f"数据路径存在: {os.path.exists(data_path)}")
        
        # 检查飞机路径
        aircraft_path = config.getAircraftPath()
        print(f"飞机路径: {aircraft_path}")
        print(f"飞机路径存在: {os.path.exists(aircraft_path)}")
        
        # 检查BADA3路径
        bada3_path = config.getBadaFamilyPath("BADA3")
        print(f"BADA3路径: {bada3_path}")
        print(f"BADA3路径存在: {os.path.exists(bada3_path)}")
        
        # 检查BADA3版本列表
        try:
            bada3_versions = config.getVersionsList("BADA3")
            print(f"BADA3版本列表: {bada3_versions}")
            
            # 检查每个版本的飞机列表
            for version in bada3_versions:
                try:
                    aircraft_list = config.getAircraftList("BADA3", version)
                    print(f"BADA3 {version} 可用飞机: {aircraft_list}")
                    
                    # 检查版本路径
                    version_path = config.getBadaVersionPath("BADA3", version)
                    print(f"BADA3 {version} 路径: {version_path}")
                    print(f"BADA3 {version} 路径存在: {os.path.exists(version_path)}")
                    
                    # 列出版本目录内容
                    if os.path.exists(version_path):
                        subfolders = config.list_subfolders(version_path)
                        print(f"BADA3 {version} 子目录: {subfolders}")
                    
                except Exception as e:
                    print(f"获取BADA3 {version} 飞机列表失败: {e}")
                    
        except Exception as e:
            print(f"获取BADA3版本列表失败: {e}")
            
        # 检查BADA4
        try:
            bada4_versions = config.getVersionsList("BADA4")
            print(f"BADA4版本列表: {bada4_versions}")
            
            for version in bada4_versions:
                try:
                    aircraft_list = config.getAircraftList("BADA4", version)
                    print(f"BADA4 {version} 可用飞机: {aircraft_list}")
                except Exception as e:
                    print(f"获取BADA4 {version} 飞机列表失败: {e}")
                    
        except Exception as e:
            print(f"获取BADA4版本列表失败: {e}")
            
    except Exception as e:
        print(f"检查配置失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_bada_configuration() 