"""
下载GraphHopper JAR文件
"""

import requests
import os
from pathlib import Path

def download_graphhopper_jar():
    """下载GraphHopper Web JAR文件"""
    jar_url = "https://repo1.maven.org/maven2/com/graphhopper/graphhopper-web/10.2/graphhopper-web-10.2.jar"
    jar_filename = "graphhopper-web-10.2.jar"
    
    print(f"开始下载GraphHopper JAR文件...")
    print(f"URL: {jar_url}")
    print(f"目标文件: {jar_filename}")
    
    try:
        # 检查文件是否已存在
        if os.path.exists(jar_filename):
            file_size_mb = os.path.getsize(jar_filename) / (1024 * 1024)
            print(f"文件已存在: {jar_filename} ({file_size_mb:.1f} MB)")
            return True
        
        # 下载文件
        response = requests.get(jar_url, stream=True, timeout=60)
        response.raise_for_status()
        
        total_size = int(response.headers.get('content-length', 0))
        downloaded_size = 0
        
        with open(jar_filename, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded_size += len(chunk)
                    
                    # 显示进度
                    if total_size > 0:
                        progress = (downloaded_size / total_size) * 100
                        print(f"\r进度: {progress:.1f}% ({downloaded_size / (1024*1024):.1f}/{total_size / (1024*1024):.1f} MB)", end='', flush=True)
        
        print(f"\n下载完成: {jar_filename}")
        
        # 验证文件大小
        actual_size = os.path.getsize(jar_filename)
        if total_size > 0 and actual_size != total_size:
            print(f"警告: 文件大小不匹配 (期望: {total_size}, 实际: {actual_size})")
            return False
        
        print(f"文件大小: {actual_size / (1024*1024):.1f} MB")
        return True
        
    except requests.exceptions.RequestException as e:
        print(f"下载失败: {e}")
        return False
    except Exception as e:
        print(f"下载过程中发生错误: {e}")
        return False

def download_config_example():
    """下载GraphHopper配置示例文件"""
    config_url = "https://raw.githubusercontent.com/graphhopper/graphhopper/10.x/config-example.yml"
    config_filename = "config-example.yml"
    
    print(f"\n下载配置示例文件...")
    print(f"URL: {config_url}")
    
    try:
        if os.path.exists(config_filename):
            print(f"配置文件已存在: {config_filename}")
            return True
        
        response = requests.get(config_url, timeout=30)
        response.raise_for_status()
        
        with open(config_filename, 'w', encoding='utf-8') as f:
            f.write(response.text)
        
        print(f"配置文件下载完成: {config_filename}")
        return True
        
    except Exception as e:
        print(f"配置文件下载失败: {e}")
        return False

def main():
    """主函数"""
    print("GraphHopper文件下载工具")
    print("=" * 40)
    
    # 下载JAR文件
    jar_success = download_graphhopper_jar()
    
    # 下载配置文件
    config_success = download_config_example()
    
    print(f"\n" + "=" * 40)
    print("下载结果:")
    print(f"  GraphHopper JAR: {'成功' if jar_success else '失败'}")
    print(f"  配置示例文件: {'成功' if config_success else '失败'}")
    
    if jar_success:
        print(f"\n下一步:")
        print(f"1. 确保OSM数据文件存在: natural_gas_supply_chain_optimization/data/china-latest.osm.pbf")
        print(f"2. 运行启动脚本: start_graphhopper.bat")
        print(f"3. 或手动启动: java -jar graphhopper-web-10.2.jar server config.yml")
    
    return jar_success and config_success

if __name__ == "__main__":
    success = main()
    if not success:
        input("\n按回车键退出...")