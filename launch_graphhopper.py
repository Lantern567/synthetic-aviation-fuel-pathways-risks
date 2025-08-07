#!/usr/bin/env python3
"""
GraphHopper服务启动器
绕过bash环境问题，直接启动Java进程
"""

import os
import sys
import subprocess
import time
import signal

def check_prerequisites():
    """检查前置条件"""
    print("检查前置条件...")
    
    # 检查Java
    try:
        result = subprocess.run(['java', '-version'], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            print("✓ Java已安装")
        else:
            print("✗ Java检查失败")
            return False
    except Exception as e:
        print(f"✗ Java未找到: {e}")
        return False
    
    # 检查文件
    jar_path = "natural_gas_supply_chain_optimization/data/graphhopper-web-10.2.jar"
    osm_path = "natural_gas_supply_chain_optimization/data/china-latest.osm.pbf"
    config_path = "config.yml"
    
    if not os.path.exists(jar_path):
        print(f"✗ JAR文件不存在: {jar_path}")
        return False
    print(f"✓ JAR文件存在: {jar_path}")
    
    if not os.path.exists(osm_path):
        print(f"✗ OSM数据文件不存在: {osm_path}")
        return False
    size_mb = os.path.getsize(osm_path) / (1024*1024)
    print(f"✓ OSM数据文件存在: {osm_path} ({size_mb:.1f} MB)")
    
    if not os.path.exists(config_path):
        print(f"⚠ 配置文件不存在: {config_path} (将使用默认配置)")
    else:
        print(f"✓ 配置文件存在: {config_path}")
    
    # 创建缓存目录
    cache_dir = "graph-cache"
    if not os.path.exists(cache_dir):
        print(f"创建缓存目录: {cache_dir}")
        os.makedirs(cache_dir, exist_ok=True)
    else:
        print(f"✓ 缓存目录存在: {cache_dir}")
    
    return True

def launch_graphhopper():
    """启动GraphHopper服务"""
    print("\n" + "="*50)
    print("启动GraphHopper路径规划服务")
    print("="*50)
    
    # 准备启动命令
    cmd = [
        'java',
        '-Xmx4g',
        '-Ddw.graphhopper.datareader.file=natural_gas_supply_chain_optimization/data/china-latest.osm.pbf',
        '-Ddw.graphhopper.graph.location=./graph-cache',
        '-Ddw.server.applicationConnectors[0].port=8989',
        '-jar',
        'natural_gas_supply_chain_optimization/data/graphhopper-web-10.2.jar',
        'server',
        'config.yml'
    ]
    
    print("启动参数:")
    print("  内存: 4GB")
    print("  端口: 8989")
    print("  OSM数据: natural_gas_supply_chain_optimization/data/china-latest.osm.pbf")
    print("  缓存目录: ./graph-cache")
    print("\n首次启动需要10-30分钟处理OSM数据，请耐心等待...")
    print("看到 'Started @' 消息表示启动成功")
    print("服务地址: http://localhost:8989")
    print("按Ctrl+C停止服务")
    print("\n" + "-"*50)
    
    process = None
    try:
        # 启动进程
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1
        )
        
        # 实时显示输出
        for line in iter(process.stdout.readline, ''):
            if line:
                print(line.rstrip())
                
                # 检查启动成功标志
                if 'Started @' in line:
                    print("\n" + "="*50)
                    print("🎉 GraphHopper服务启动成功!")
                    print("访问: http://localhost:8989")
                    print("API文档: http://localhost:8989/api-doc")
                    print("="*50)
        
        # 等待进程结束
        process.wait()
        
    except KeyboardInterrupt:
        print("\n\n用户中断服务")
        if process:
            print("正在停止GraphHopper服务...")
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
        print("GraphHopper服务已停止")
        
    except Exception as e:
        print(f"\n启动失败: {e}")
        if process:
            process.terminate()
        return False
    
    return True

def main():
    """主函数"""
    print("GraphHopper服务启动器")
    print("作者: Claude Code Assistant")
    print("版本: 1.0")
    print("-" * 30)
    
    # 设置工作目录
    target_dir = r"D:\Green methanol\green_methanol_for_port_transportation-main\green_methanol_for_port_transportation-main"
    if os.path.exists(target_dir):
        os.chdir(target_dir)
        print(f"工作目录: {os.getcwd()}")
    else:
        print(f"错误: 目标目录不存在 {target_dir}")
        return 1
    
    # 检查前置条件
    if not check_prerequisites():
        print("\n前置条件检查失败，无法启动服务")
        return 1
    
    # 启动服务
    success = launch_graphhopper()
    
    if success:
        print("\nGraphHopper服务正常退出")
        return 0
    else:
        print("\nGraphHopper服务启动失败")
        return 1

if __name__ == "__main__":
    sys.exit(main())