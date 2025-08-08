#!/usr/bin/env python3
"""
GIS数据爬取器 - 失败重试脚本
专门用于重新爬取失败的服务，增加重试机制和更优化的参数
"""

from simple_china_energy_gis_scraper import SimpleChinaEnergyGISScraper
import time
import logging

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('retry_scraper.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class RetryChinaEnergyGISScraper(SimpleChinaEnergyGISScraper):
    """增强重试功能的GIS数据爬取器"""
    
    def __init__(self, output_dir: str = "scraped_gis_data"):
        super().__init__(output_dir)
        # 增加超时时间
        self.session.timeout = 120
        
    def query_all_features_geojson_with_retry(self, service_url: str, layer_id: int = 0, 
                                            where: str = "1=1", batch_size: int = 500, 
                                            max_retries: int = 3) -> dict:
        """带重试机制的要素查询"""
        all_features = []
        offset = 0
        
        while True:
            retry_count = 0
            current_batch = None
            
            # 重试当前批次
            while retry_count < max_retries:
                params = {
                    'f': 'geojson',
                    'where': where,
                    'outFields': '*',
                    'resultRecordCount': batch_size,
                    'resultOffset': offset,
                    'returnGeometry': 'true',
                    'spatialRel': 'esriSpatialRelIntersects',
                    'outSR': '4326'
                }
                
                try:
                    logger.info(f"查询偏移量: {offset}, 批量大小: {batch_size} (重试 {retry_count + 1}/{max_retries})")
                    response = self.session.get(
                        f"{service_url}/{layer_id}/query", 
                        params=params, 
                        timeout=120
                    )
                    response.raise_for_status()
                    data = response.json()
                    
                    if 'features' not in data:
                        logger.warning(f"响应中没有features字段: {data}")
                        return None
                    
                    current_batch = data['features']
                    break  # 成功获取，跳出重试循环
                    
                except Exception as e:
                    retry_count += 1
                    logger.error(f"第 {retry_count} 次尝试失败: {e}")
                    if retry_count < max_retries:
                        wait_time = 5 * retry_count  # 递增等待时间
                        logger.info(f"等待 {wait_time} 秒后重试...")
                        time.sleep(wait_time)
                    else:
                        logger.error(f"达到最大重试次数，放弃当前批次")
                        return None
            
            # 检查当前批次结果
            if not current_batch:
                logger.info("没有更多要素，爬取完成")
                break
                
            # 添加当前批次到总结果
            all_features.extend(current_batch)
            logger.info(f"成功获取批次，当前总数: {len(all_features)} 个要素")
            
            # 如果返回的要素数量少于批量大小，说明已经获取完毕
            if len(current_batch) < batch_size:
                logger.info(f"最后一批只有 {len(current_batch)} 个要素，爬取完成")
                break
                
            # 更新偏移量，继续下一批
            offset += batch_size
            time.sleep(1)  # 成功后稍作延时
        
        if all_features:
            geojson = {
                "type": "FeatureCollection",
                "features": all_features
            }
            logger.info(f"总共获取 {len(all_features)} 个要素")
            return geojson
        
        return None
    
    def scrape_service_with_retry(self, service_name: str, service_config: dict) -> bool:
        """带重试机制的服务爬取"""
        logger.info(f"开始重试爬取: {service_config['description']} ({service_name})")
        
        service_url = service_config['url']
        
        # 获取服务信息
        service_info = self.get_service_info(service_url)
        if not service_info:
            logger.error(f"无法获取服务信息: {service_name}")
            return False
        
        # 保存服务元数据
        metadata_path = self.output_dir / f"{service_name}_metadata.json"
        with open(metadata_path, 'w', encoding='utf-8') as f:
            import json
            json.dump(service_info, f, ensure_ascii=False, indent=2)
        
        # 获取所有图层
        layers = service_info.get('layers', [])
        if not layers:
            layers = [{'id': 0, 'name': service_name}]
        
        success = True
        for layer in layers:
            layer_id = layer['id']
            layer_name = layer.get('name', f"layer_{layer_id}")
            
            logger.info(f"重试爬取图层: {layer_name} (ID: {layer_id})")
            
            # 获取图层信息
            layer_info = self.get_layer_info(service_url, layer_id)
            if layer_info:
                layer_metadata_path = self.output_dir / f"{service_name}_layer_{layer_id}_metadata.json"
                with open(layer_metadata_path, 'w', encoding='utf-8') as f:
                    import json
                    json.dump(layer_info, f, ensure_ascii=False, indent=2)
            
            # 使用增强的重试查询
            geojson_data = self.query_all_features_geojson_with_retry(
                service_url, layer_id, batch_size=300  # 减小批量大小
            )
            
            if geojson_data and geojson_data.get('features'):
                feature_count = len(geojson_data['features'])
                logger.info(f"重试成功！获取到 {feature_count} 个要素")
                
                # 确定输出文件名
                output_name = f"{service_name}_layer_{layer_id}" if len(layers) > 1 else service_name
                
                # 保存所有格式
                geojson_path = self.output_dir / f"{output_name}.geojson"
                self.save_geojson(geojson_data, str(geojson_path))
                
                csv_path = self.output_dir / f"{output_name}.csv"
                self.geojson_to_csv(geojson_data, str(csv_path))
                
                excel_path = self.output_dir / f"{output_name}.xlsx"
                self.geojson_to_excel(geojson_data, str(excel_path))
                
            else:
                logger.error(f"重试失败，仍未获取到要素数据: {service_name} layer {layer_id}")
                success = False
        
        return success

def retry_failed_services():
    """重试失败的服务"""
    print("=== GIS数据爬取器 - 失败重试 ===\n")
    
    # 根据日志，失败的服务是gas_power_plants
    failed_services = ['gas_power_plants']
    
    scraper = RetryChinaEnergyGISScraper()
    
    print(f"将重试以下失败的服务: {failed_services}")
    
    successful = 0
    still_failed = []
    
    for service_name in failed_services:
        if service_name not in scraper.feature_servers:
            logger.warning(f"未找到服务配置: {service_name}")
            continue
        
        print(f"\n开始重试: {service_name}")
        
        try:
            if scraper.scrape_service_with_retry(service_name, scraper.feature_servers[service_name]):
                successful += 1
                logger.info(f"✓ 重试成功: {service_name}")
            else:
                still_failed.append(service_name)
                logger.error(f"✗ 重试仍然失败: {service_name}")
        except Exception as e:
            still_failed.append(service_name)
            logger.error(f"✗ 重试异常失败: {service_name} - {e}")
            import traceback
            traceback.print_exc()
    
    print(f"\n=== 重试结果 ===")
    print(f"重试成功: {successful}")
    print(f"仍然失败: {len(still_failed)}")
    
    if still_failed:
        print(f"仍然失败的服务: {still_failed}")
        print("\n建议:")
        print("1. 检查网络连接")
        print("2. 可能需要使用VPN")
        print("3. 稍后再试")
    else:
        print("所有服务都已成功爬取！")

def check_missing_services():
    """检查可能遗漏的服务"""
    print("\n=== 检查遗漏的服务 ===")
    
    scraper = SimpleChinaEnergyGISScraper()
    
    # 检查输出目录中的文件
    output_dir = scraper.output_dir
    if not output_dir.exists():
        print("输出目录不存在")
        return
    
    # 获取已有的数据集
    existing_files = set()
    for file in output_dir.glob("*.geojson"):
        service_name = file.stem
        existing_files.add(service_name)
    
    # 检查遗漏的服务
    all_services = set(scraper.feature_servers.keys())
    missing_services = all_services - existing_files
    
    if missing_services:
        print(f"遗漏的服务: {list(missing_services)}")
        
        choice = input("是否要爬取遗漏的服务? (y/n): ").strip().lower()
        if choice == 'y':
            retry_scraper = RetryChinaEnergyGISScraper()
            retry_scraper.scrape_all(list(missing_services))
    else:
        print("没有遗漏的服务，所有数据集都已完成！")

if __name__ == "__main__":
    try:
        # 首先重试已知的失败服务
        retry_failed_services()
        
        # 然后检查是否有其他遗漏的服务
        check_missing_services()
        
    except KeyboardInterrupt:
        print("\n\n用户中断操作")
    except Exception as e:
        print(f"\n发生错误: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n重试程序结束")
