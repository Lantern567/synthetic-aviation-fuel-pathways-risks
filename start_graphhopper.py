#!/usr/bin/env python3
"""
启动GraphHopper服务的Python脚本
"""

import os
import sys
import subprocess
import time

def check_files():
    """检查必要文件是否存在"""
    print("检查必要文件...")
    
    jar_path = "natural_gas_supply_chain_optimization/data/graphhopper-web-10.2.jar"
    osm_path = "natural_gas_supply_chain_optimization/data/china-latest.osm.pbf"
    config_path = "config.yml"
    
    if not os.path.exists(jar_path):
        print(f"[错误] JAR文件不存在: {jar_path}")
        return False
        
    if not os.path.exists(osm_path):
        print(f"[错误] OSM数据文件不存在: {osm_path}")
        return False
        
    if not os.path.exists(config_path):
        print(f"[警告] 配置文件不存在: {config_path}")
    
    print("[OK] 所有必要文件都存在")
    return True

def check_java():
    """检查Java是否可用"""
    print("检查Java安装...")
    try:
        result = subprocess.run(['java', '-version'], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            print("[OK] Java已安装")
            return True
        else:
            print("[错误] Java未正确安装")
            return False
    except FileNotFoundError:
        print("[错误] Java未安装或不在PATH中")
        return False
    except Exception as e:
        print(f"[错误] Java检查失败: {e}")
        return False

def create_graph_cache_dir():
    """创建图缓存目录"""
    cache_dir = "graph-cache"
    if not os.path.exists(cache_dir):
        print(f"创建图缓存目录: {cache_dir}")
        os.makedirs(cache_dir)
    else:
        print(f"[OK] 图缓存目录已存在: {cache_dir}")

def start_graphhopper():
    """启动GraphHopper服务"""
    print("\n" + "="*50)
    print("启动GraphHopper路径规划服务")
    print("="*50)
    
    # 准备启动命令
    java_cmd = [
        'java',
        '-Xmx4g',
        '-Ddw.graphhopper.datareader.file=natural_gas_supply_chain_optimization/data/china-latest.osm.pbf',
        '-Ddw.graphhopper.graph.location=./graph-cache',
        '-jar',
        'natural_gas_supply_chain_optimization/data/graphhopper-web-10.2.jar',
        'server',
        'config.yml'
    ]
    
    print("启动参数:")
    print(f"  OSM数据: natural_gas_supply_chain_optimization/data/china-latest.osm.pbf")
    print(f"  端口: 8989")
    print(f"  缓存目录: ./graph-cache")
    print(f"  内存: 4GB")
    print("\n首次启动可能需要10-30分钟来处理OSM数据，请耐心等待...")
    print("看到 'Started @' 消息后表示启动成功")
    print("服务地址: http://localhost:8989")
    print("按Ctrl+C停止服务")
    print("\n" + "-"*50)
    
    try:
        # 启动服务
        process = subprocess.Popen(java_cmd, 
                                 stdout=subprocess.PIPE, 
                                 stderr=subprocess.STDOUT,
                                 universal_newlines=True,
                                 bufsize=1)
        
        # 实时输出日志
        while True:
            output = process.stdout.readline()
            if output == '' and process.poll() is not None:
                break
            if output:
                print(output.strip())
                
        rc = process.poll()
        if rc != 0:
            print(f"\n[错误] GraphHopper服务异常退出，返回码: {rc}")
        else:
            print(f"\n[信息] GraphHopper服务正常退出")
            
    except KeyboardInterrupt:
        print(f"\n\n用户中断服务")
        if 'process' in locals():
            process.terminate()
            process.wait()
        print("GraphHopper服务已停止")
    except Exception as e:
        print(f"\n[错误] 启动失败: {e}")

def main():
    """主函数"""
    print("GraphHopper服务启动器")
    print("="*30)
    
    # 检查环境
    if not check_java():
        print("\n请安装Java 8或更高版本后重试")
        sys.exit(1)
        
    if not check_files():
        print("\n请确保所有必要文件都存在")
        sys.exit(1)
    
    # 创建缓存目录
    create_graph_cache_dir()
    
    # 启动服务
    start_graphhopper()

if __name__ == "__main__":
    main()