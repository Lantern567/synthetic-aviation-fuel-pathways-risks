#!/usr/bin/env python3
"""
检查pyBADA数据文件结构
"""

import os
import pyBADA

def check_pybada_data():
    """检查pyBADA数据文件结构"""
    print("🔍 检查pyBADA数据文件结构")
    print("=" * 50)
    
    # 获取pyBADA安装路径
    bada_path = os.path.dirname(pyBADA.__file__)
    print(f"pyBADA安装路径: {bada_path}")
    
    # 检查aircraft目录
    aircraft_path = os.path.join(bada_path, 'aircraft')
    print(f"Aircraft数据路径: {aircraft_path}")
    
    if os.path.exists(aircraft_path):
        print(f"Aircraft目录内容: {os.listdir(aircraft_path)}")
        
        # 检查BADA3目录
        bada3_path = os.path.join(aircraft_path, 'BADA3')
        if os.path.exists(bada3_path):
            print(f"BADA3目录内容: {os.listdir(bada3_path)}")
            
            # 检查DUMMY目录
            dummy_path = os.path.join(bada3_path, 'DUMMY')
            if os.path.exists(dummy_path):
                print(f"DUMMY目录内容: {os.listdir(dummy_path)}")
                
                # 检查DUMMY.xml文件
                dummy_xml = os.path.join(dummy_path, 'DUMMY.xml')
                if os.path.exists(dummy_xml):
                    print(f"DUMMY.xml文件存在，大小: {os.path.getsize(dummy_xml)} bytes")
                    
                    # 读取文件内容的前几行
                    try:
                        with open(dummy_xml, 'r', encoding='utf-8') as f:
                            lines = f.readlines()[:10]
                            print("DUMMY.xml文件内容预览:")
                            for i, line in enumerate(lines):
                                print(f"  {i+1}: {line.strip()}")
                    except Exception as e:
                        print(f"读取DUMMY.xml文件失败: {e}")
                else:
                    print("❌ DUMMY.xml文件不存在")
            else:
                print("❌ DUMMY目录不存在")
        else:
            print("❌ BADA3目录不存在")
    else:
        print("❌ Aircraft目录不存在")

if __name__ == "__main__":
    check_pybada_data() 