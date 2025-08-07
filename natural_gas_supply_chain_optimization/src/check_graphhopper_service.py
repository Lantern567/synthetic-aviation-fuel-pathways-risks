"""
GraphHopper服务检查和诊断工具
"""

import sys
import os
import requests
import subprocess
import time
from pathlib import Path

# 添加当前目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def check_java_installation():
    """检查Java是否安装"""
    print("检查Java安装...")
    try:
        result = subprocess.run(['java', '-version'], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            # Java版本信息通常输出到stderr
            version_info = result.stderr.split('\n')[0] if result.stderr else result.stdout.split('\n')[0]
            print(f"✓ Java已安装: {version_info}")
            return True
        else:
            print("✗ Java未正确安装")
            return False
    except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError):
        print("✗ Java未安装或不在PATH中")
        print("  请安装Java 8或更高版本")
        return False

def check_osm_data_file():
    """检查OSM数据文件"""
    print("\n检查OSM数据文件...")
    
    possible_paths = [
        "data/china-latest.osm.pbf",
        "../data/china-latest.osm.pbf",
        "../../data/china-latest.osm.pbf",
        "d:/Green methanol/green_methanol_for_port_transportation-main/green_methanol_for_port_transportation-main/data/china-latest.osm.pbf"
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            file_size = os.path.getsize(path) / (1024 * 1024)  # MB
            print(f"✓ OSM数据文件存在: {path}")
            print(f"  文件大小: {file_size:.1f} MB")
            return True, path
    
    print("✗ OSM数据文件不存在")
    print("  请下载中国OSM数据文件:")
    print("  wget https://download.geofabrik.de/asia/china-latest.osm.pbf")
    print("  并放置在 data/ 目录下")
    return False, None

def check_graphhopper_jar():
    """检查GraphHopper JAR文件"""
    print("\n检查GraphHopper JAR文件...")
    
    # 查找GraphHopper JAR文件
    jar_patterns = [
        "graphhopper-web-*.jar",
        "graphhopper*.jar"
    ]
    
    current_dir = Path(".")
    for pattern in jar_patterns:
        jar_files = list(current_dir.glob(pattern))
        if jar_files:
            jar_file = jar_files[0]
            file_size = jar_file.stat().st_size / (1024 * 1024)  # MB
            print(f"✓ GraphHopper JAR文件存在: {jar_file}")
            print(f"  文件大小: {file_size:.1f} MB")
            return True, str(jar_file)
    
    print("✗ GraphHopper JAR文件不存在")
    print("  请下载GraphHopper:")
    print("  wget https://github.com/graphhopper/graphhopper/releases/download/9.1/graphhopper-web-9.1.jar")
    return False, None

def check_config_file():
    """检查配置文件"""
    print("\n检查配置文件...")
    
    config_paths = ["config.yml", "application.yml", "config.yaml"]
    
    for config_path in config_paths:
        if os.path.exists(config_path):
            print(f"✓ 配置文件存在: {config_path}")
            return True, config_path
    
    print("✗ 配置文件不存在")
    print("  请确保config.yml文件存在")
    return False, None

def check_graphhopper_service(host="localhost", port=8989):
    """检查GraphHopper服务状态"""
    print(f"\n检查GraphHopper服务 ({host}:{port})...")
    
    base_url = f"http://{host}:{port}"
    
    # 检查健康状态
    try:
        health_url = f"{base_url}/health"
        print(f"尝试连接: {health_url}")
        
        response = requests.get(health_url, timeout=5)
        if response.status_code == 200:
            print("✓ GraphHopper服务运行正常")
            
            # 尝试获取服务信息
            try:
                info_url = f"{base_url}/info"
                info_response = requests.get(info_url, timeout=5)
                if info_response.status_code == 200:
                    info_data = info_response.json()
                    print(f"  版本信息: {info_data.get('version', 'N/A')}")
                    print(f"  支持的配置: {info_data.get('profiles', 'N/A')}")
            except:
                pass  # 忽略信息获取错误
            
            return True
        else:
            print(f"✗ GraphHopper服务返回异常状态码: {response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        print(f"✗ 无法连接到GraphHopper服务 {base_url}")
        print("  服务可能未启动")
        return False
    except requests.exceptions.Timeout:
        print(f"✗ 连接超时: {base_url}")
        return False
    except Exception as e:
        print(f"✗ 连接失败: {e}")
        return False

def test_route_calculation(host="localhost", port=8989):
    """测试路径计算功能"""
    print(f"\n测试路径计算功能...")
    
    base_url = f"http://{host}:{port}"
    
    # 测试北京到上海的路径
    beijing_lat, beijing_lon = 39.9042, 116.4074
    shanghai_lat, shanghai_lon = 31.2304, 121.4737
    
    try:
        route_url = f"{base_url}/route"
        params = {
            'point': [f'{beijing_lat},{beijing_lon}', f'{shanghai_lat},{shanghai_lon}'],
            'vehicle': 'car',
            'calc_points': False,
            'instructions': False
        }
        
        print(f"测试路径规划: 北京 -> 上海")
        response = requests.get(route_url, params=params, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            if 'paths' in data and len(data['paths']) > 0:
                path = data['paths'][0]
                distance_km = path.get('distance', 0) / 1000
                time_hours = path.get('time', 0) / (1000 * 3600)
                
                print(f"✓ 路径计算成功")
                print(f"  距离: {distance_km:.1f} 公里")
                print(f"  时间: {time_hours:.1f} 小时")
                return True
            else:
                print("✗ 路径计算返回空结果")
                return False
        else:
            print(f"✗ 路径计算失败，状态码: {response.status_code}")
            print(f"  响应: {response.text}")
            return False
            
    except Exception as e:
        print(f"✗ 路径计算测试失败: {e}")
        return False

def provide_startup_instructions():
    """提供启动说明"""
    print("\n" + "="*60)
    print("GraphHopper服务启动说明")
    print("="*60)
    
    print("\n方法1: 使用提供的启动脚本")
    print("  双击运行: start_graphhopper.bat")
    
    print("\n方法2: 手动启动")
    print("  java -Xmx4g \\")
    print("       -Ddw.graphhopper.datareader.file=data/china-latest.osm.pbf \\")
    print("       -Ddw.graphhopper.graph.location=./graph-cache \\")
    print("       -Ddw.server.applicationConnectors[0].port=8989 \\")
    print("       -jar graphhopper-web-*.jar server config.yml")
    
    print("\n注意事项:")
    print("1. 首次启动需要处理OSM数据，可能需要几分钟到几十分钟")
    print("2. 确保有足够的内存（推荐4GB以上）")
    print("3. 确保8989端口未被占用")
    print("4. 处理完成后会在graph-cache目录生成图数据")

def main():
    """主检查函数"""
    print("GraphHopper服务诊断工具")
    print("="*60)
    
    # 检查各个组件
    java_ok = check_java_installation()
    osm_ok, osm_path = check_osm_data_file()
    jar_ok, jar_path = check_graphhopper_jar()
    config_ok, config_path = check_config_file()
    
    print(f"\n组件检查总结:")
    print(f"  Java: {'✓' if java_ok else '✗'}")
    print(f"  OSM数据: {'✓' if osm_ok else '✗'}")
    print(f"  GraphHopper JAR: {'✓' if jar_ok else '✗'}")
    print(f"  配置文件: {'✓' if config_ok else '✗'}")
    
    # 检查服务状态
    service_ok = check_graphhopper_service()
    
    if service_ok:
        # 如果服务正常，测试路径计算
        test_route_calculation()
        print(f"\n✓ GraphHopper服务完全正常，可以正常使用路径规划功能")
    else:
        print(f"\n服务检查总结:")
        print(f"  GraphHopper服务: ✗")
        
        if java_ok and jar_ok and config_ok:
            provide_startup_instructions()
        else:
            print(f"\n请先解决以上组件问题，然后再启动GraphHopper服务")
    
    print(f"\n" + "="*60)

if __name__ == "__main__":
    main()
    input("\n按回车键退出...")  # 防止窗口立即关闭