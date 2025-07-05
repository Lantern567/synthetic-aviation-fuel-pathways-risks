#!/usr/bin/env python3
"""
检查pyBADA安装状态和BADA数据文件
"""

import os
import sys

def check_pybada_installation():
    """检查pyBADA安装状态"""
    print("🔍 检查pyBADA安装状态...")
    
    try:
        import pyBADA
        print(f"✅ pyBADA已安装，路径: {pyBADA.__file__}")
        
        # 检查pyBADA目录结构
        pybada_dir = os.path.dirname(pyBADA.__file__)
        print(f"\n📁 pyBADA目录内容:")
        for item in os.listdir(pybada_dir):
            item_path = os.path.join(pybada_dir, item)
            if os.path.isdir(item_path):
                print(f"   📂 {item}/")
            else:
                print(f"   📄 {item}")
        
        # 检查aircraft目录
        aircraft_dir = os.path.join(pybada_dir, "aircraft")
        if os.path.exists(aircraft_dir):
            print(f"\n📁 aircraft目录内容:")
            for item in os.listdir(aircraft_dir):
                item_path = os.path.join(aircraft_dir, item)
                if os.path.isdir(item_path):
                    print(f"   📂 {item}/")
                else:
                    print(f"   📄 {item}")
            
            # 检查BADA3目录
            bada3_dir = os.path.join(aircraft_dir, "BADA3")
            if os.path.exists(bada3_dir):
                print(f"\n📁 BADA3目录内容:")
                for item in os.listdir(bada3_dir):
                    item_path = os.path.join(bada3_dir, item)
                    if os.path.isdir(item_path):
                        print(f"   📂 {item}/")
                    else:
                        print(f"   📄 {item}")
                
                # 检查特定的BADA3子目录
                bada3_data_dir = os.path.join(bada3_dir, "BADA3")
                if os.path.exists(bada3_data_dir):
                    print(f"\n📁 BADA3/BADA3目录内容:")
                    subdirs = [d for d in os.listdir(bada3_data_dir) if os.path.isdir(os.path.join(bada3_data_dir, d))]
                    print(f"   发现 {len(subdirs)} 个飞机模型目录:")
                    for subdir in sorted(subdirs):
                        aircraft_dir_path = os.path.join(bada3_data_dir, subdir)
                        xml_file = os.path.join(aircraft_dir_path, f"{subdir}.xml")
                        if os.path.exists(xml_file):
                            print(f"   ✅ {subdir}/ (包含XML文件)")
                        else:
                            print(f"   ❌ {subdir}/ (缺少XML文件)")
                else:
                    print(f"❌ BADA3数据目录不存在: {bada3_data_dir}")
            else:
                print(f"❌ BADA3目录不存在: {bada3_dir}")
        else:
            print(f"❌ aircraft目录不存在: {aircraft_dir}")
    
    except ImportError as e:
        print(f"❌ pyBADA导入失败: {e}")
        return False
    
    return True

def check_pybada_modules():
    """检查pyBADA各个模块的导入状态"""
    print(f"\n🔍 检查pyBADA模块导入状态...")
    
    modules_to_check = [
        "pyBADA.bada3",
        "pyBADA.TCL", 
        "pyBADA.aircraft",
        "pyBADA.atmosphere",
        "pyBADA.conversions"
    ]
    
    for module_name in modules_to_check:
        try:
            __import__(module_name)
            print(f"✅ {module_name}")
        except ImportError as e:
            print(f"❌ {module_name}: {e}")

def test_bada3_aircraft_creation():
    """测试BADA3飞机对象创建"""
    print(f"\n🔍 测试BADA3飞机对象创建...")
    
    try:
        import pyBADA.bada3 as bada3
        
        # 尝试创建常用飞机模型
        test_aircraft = ['A320', 'B737', 'A319', 'B738']
        
        for aircraft_code in test_aircraft:
            try:
                print(f"   尝试创建 {aircraft_code}...")
                aircraft = bada3.Bada3Aircraft(
                    badaVersion="BADA3",
                    acName=aircraft_code
                )
                print(f"   ✅ {aircraft_code} 创建成功")
            except Exception as e:
                print(f"   ❌ {aircraft_code} 创建失败: {e}")
                
    except ImportError as e:
        print(f"❌ 无法导入pyBADA.bada3: {e}")

def suggest_solutions():
    """提供解决方案建议"""
    print(f"\n💡 解决方案建议:")
    print("1. 检查BADA数据文件是否正确安装")
    print("2. 下载并安装完整的BADA数据集")
    print("3. 配置正确的BADA数据路径")
    print("4. 使用通用飞机模型或DUMMY数据")
    print("5. 实施备用计算方法")

if __name__ == "__main__":
    print("=" * 50)
    print("pyBADA安装诊断工具")
    print("=" * 50)
    
    # 检查安装
    installation_ok = check_pybada_installation()
    
    # 检查模块导入
    check_pybada_modules()
    
    # 测试飞机创建
    test_bada3_aircraft_creation()
    
    # 提供建议
    suggest_solutions()
    
    print("=" * 50)
    print("诊断完成") 