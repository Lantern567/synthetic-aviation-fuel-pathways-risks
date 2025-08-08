#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
中国能源基础设施GIS数据爬取器 - 高级版本
Advanced China Energy Infrastructure GIS Data Scraper

基于Baker Institute中国能源基础设施地图
https://www.bakerinstitute.org/map-chinas-energy-infrastructure

作者: AI Assistant
日期: 2025-08-03
功能: 爬取中国20个能源基础设施数据集，支持多格式输出
"""

import requests
import json
import time
import pandas as pd
import geopandas as gpd
from pathlib import Path
import logging
from datetime import datetime
from typing import Dict, List, Optional, Union
import warnings
warnings.filterwarnings('ignore')

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('advanced_gis_scraper.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class AdvancedChinaEnergyGISScraper:
    """高级中国能源基础设施GIS数据爬取器"""
    
    def __init__(self, output_dir: str = "scraped_gis_data"):
        """初始化爬取器"""
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        # 设置请求会话
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Referer': 'https://www.bakerinstitute.org/'
        })
        self.session.timeout = 60
        
        # Baker Institute 能源基础设施服务配置
        self.base_url = "https://services1.arcgis.com/0MSEUqKaxRlEPj5g/arcgis/rest/services"
        
        # 20个能源基础设施数据集
        self.feature_servers = {
            # 电力基础设施
            'nuclear_power_plants': {
                'url': f'{self.base_url}/Nuclear_power_plants_Existing_and_Retired/FeatureServer',
                'description': '核电站（现有和已退役）',
                'geometry_type': 'Point',
                'layer_id': 0
            },
            'coal_power_plants': {
                'url': f'{self.base_url}/Coal_power_plants_Operating_and_Retired/FeatureServer',
                'description': '燃煤电厂（运营和已退役）', 
                'geometry_type': 'Point',
                'layer_id': 0
            },
            'gas_power_plants': {
                'url': f'{self.base_url}/Gas_power_plants_Operating_and_Retired/FeatureServer',
                'description': '燃气电厂（运营和已退役）',
                'geometry_type': 'Point',
                'layer_id': 0
            },
            
            # 可再生能源
            'solar_power_plants': {
                'url': f'{self.base_url}/Solar_power_plants_Operating_Under_Construction_and_Announced/FeatureServer',
                'description': '太阳能电站（运营、在建和计划）',
                'geometry_type': 'Point',
                'layer_id': 0
            },
            'wind_power_plants': {
                'url': f'{self.base_url}/Wind_power_plants_Operating_Under_Construction_and_Announced/FeatureServer',
                'description': '风电场（运营、在建和计划）',
                'geometry_type': 'Point',
                'layer_id': 0
            },
            
            # 石油天然气基础设施
            'lng_terminals': {
                'url': f'{self.base_url}/LNG_terminals_Existing_Under_Construction_and_Proposed/FeatureServer',
                'description': 'LNG接收站（现有、在建和计划）',
                'geometry_type': 'Point',
                'layer_id': 0
            },
            'oil_ports': {
                'url': f'{self.base_url}/Oil_ports_Major/FeatureServer',
                'description': '主要石油港口',
                'geometry_type': 'Point',
                'layer_id': 0
            },
            'oil_refineries': {
                'url': f'{self.base_url}/Oil_refineries_Existing_and_Announced/FeatureServer',
                'description': '石油炼厂（现有和计划）',
                'geometry_type': 'Point',
                'layer_id': 0
            },
            'oil_storage': {
                'url': f'{self.base_url}/Oil_storage_Strategic_and_Commercial/FeatureServer',
                'description': '石油储存设施（战略和商业）',
                'geometry_type': 'Point',
                'layer_id': 0
            },
            'gas_storage': {
                'url': f'{self.base_url}/Gas_storage_Underground_and_LNG/FeatureServer',
                'description': '天然气储存设施（地下和LNG）',
                'geometry_type': 'Point',
                'layer_id': 0
            },
            
            # 管道基础设施
            'natural_gas_pipelines': {
                'url': f'{self.base_url}/Natural_gas_pipelines_Existing_Under_Construction_and_Proposed/FeatureServer',
                'description': '天然气管道（现有、在建和计划）',
                'geometry_type': 'LineString',
                'layer_id': 0
            },
            'crude_pipelines': {
                'url': f'{self.base_url}/Crude_pipelines_Existing_Under_Construction_and_Proposed/FeatureServer',
                'description': '原油管道（现有、在建和计划）',
                'geometry_type': 'LineString',
                'layer_id': 0
            },
            'refined_product_pipelines': {
                'url': f'{self.base_url}/Refined_product_pipelines_Existing_Under_Construction_and_Proposed/FeatureServer',
                'description': '成品油管道（现有、在建和计划）',
                'geometry_type': 'LineString',
                'layer_id': 0
            },
            'hydrogen_pipelines': {
                'url': f'{self.base_url}/Hydrogen_pipelines_Existing_and_Proposed/FeatureServer',
                'description': '氢气管道（现有和计划）',
                'geometry_type': 'LineString',
                'layer_id': 0
            },
            
            # 新兴能源技术
            'hydrogen_facilities': {
                'url': f'{self.base_url}/Hydrogen_production_facilities_Existing_Under_Construction_and_Announced/FeatureServer',
                'description': '氢能生产设施（现有、在建和计划）',
                'geometry_type': 'Point',
                'layer_id': 0
            },
            'ccs_projects': {
                'url': f'{self.base_url}/CCS_projects_Existing_Under_Construction_and_Announced/FeatureServer',
                'description': 'CCS项目（现有、在建和计划）',
                'geometry_type': 'Point',
                'layer_id': 0
            },
            'ev_battery_factories': {
                'url': f'{self.base_url}/Electric_vehicle_battery_factories_Existing_Under_Construction_and_Announced/FeatureServer',
                'description': '电动汽车电池工厂（现有、在建和计划）',
                'geometry_type': 'Point',
                'layer_id': 0
            },
            
            # 矿产资源
            'mining_properties': {
                'url': f'{self.base_url}/Mining_properties_Critical_minerals/FeatureServer',
                'description': '关键矿物采矿资产',
                'geometry_type': 'Point',
                'layer_id': 0
            },
            
            # 地理边界和城市区域
            'china_boundaries': {
                'url': f'{self.base_url}/China_provincial_boundaries/FeatureServer',
                'description': '中国省级行政边界',
                'geometry_type': 'Polygon',
                'layer_id': 0
            },
            'urban_areas': {
                'url': f'{self.base_url}/China_urban_areas_Major/FeatureServer',
                'description': '中国主要城市区域',
                'geometry_type': 'Polygon',
                'layer_id': 0
            }
        }
        
        logger.info(f"初始化完成，配置了 {len(self.feature_servers)} 个数据集")
    
    def test_service_connection(self, service_url: str) -> bool:
        """测试服务连接"""
        try:
            response = self.session.get(f"{service_url}?f=json")
            response.raise_for_status()
            data = response.json()
            return 'layers' in data or 'serviceDescription' in data
        except Exception as e:
            logger.error(f"连接测试失败 {service_url}: {e}")
            return False
    
    def get_service_info(self, service_url: str) -> Optional[dict]:
        """获取服务基本信息"""
        try:
            logger.info(f"获取服务信息: {service_url}")
            response = self.session.get(f"{service_url}?f=json")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"获取服务信息失败: {e}")
            return None
    
    def get_layer_info(self, service_url: str, layer_id: int = 0) -> Optional[dict]:
        """获取图层详细信息"""
        try:
            response = self.session.get(f"{service_url}/{layer_id}?f=json")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"获取图层信息失败: {e}")
            return None
    
    def query_features_with_geometry(self, service_url: str, layer_id: int = 0, 
                                   where: str = "1=1", batch_size: int = 1000) -> Optional[dict]:
        """查询要素并获取几何信息"""
        all_features = []
        offset = 0
        
        logger.info(f"开始查询要素: {service_url}/{layer_id}")
        
        while True:
            params = {
                'f': 'geojson',
                'where': where,
                'outFields': '*',
                'returnGeometry': 'true',
                'geometryPrecision': 6,
                'resultRecordCount': batch_size,
                'resultOffset': offset,
                'spatialRel': 'esriSpatialRelIntersects',
                'outSR': '4326'  # WGS84坐标系
            }
            
            try:
                response = self.session.get(f"{service_url}/{layer_id}/query", params=params)
                response.raise_for_status()
                data = response.json()
                
                if 'features' not in data:
                    logger.warning(f"响应中没有features字段: {list(data.keys())}")
                    break
                
                current_batch = data['features']
                if not current_batch:
                    logger.info("没有更多要素，查询完成")
                    break
                
                all_features.extend(current_batch)
                logger.info(f"获取批次: {len(current_batch)} 个要素，总计: {len(all_features)}")
                
                if len(current_batch) < batch_size:
                    logger.info("最后一批数据，查询完成")
                    break
                
                offset += batch_size
                time.sleep(0.5)  # 避免请求过快
                
            except Exception as e:
                logger.error(f"查询要素失败: {e}")
                break
        
        if all_features:
            geojson = {
                "type": "FeatureCollection",
                "features": all_features,
                "metadata": {
                    "total_features": len(all_features),
                    "source": service_url,
                    "query_time": datetime.now().isoformat(),
                    "coordinate_system": "EPSG:4326"
                }
            }
            return geojson
        
        return None
    
    def apply_china_filter(self, geojson_data: dict, dataset_name: str) -> dict:
        """应用中国地理范围过滤器"""
        if not geojson_data or 'features' not in geojson_data:
            return geojson_data
        
        # 中国大致地理范围 (经纬度)
        china_bounds = {
            'min_lon': 73.0,   # 西部边界
            'max_lon': 135.0,  # 东部边界  
            'min_lat': 18.0,   # 南部边界
            'max_lat': 54.0    # 北部边界
        }
        
        original_count = len(geojson_data['features'])
        filtered_features = []
        
        for feature in geojson_data['features']:
            geometry = feature.get('geometry')
            if not geometry:
                continue
            
            # 检查几何类型并提取坐标
            coords = None
            geom_type = geometry.get('type')
            
            if geom_type == 'Point':
                coords = [geometry['coordinates']]
            elif geom_type in ['LineString', 'MultiPoint']:
                coords = geometry['coordinates']
            elif geom_type in ['Polygon', 'MultiLineString']:
                coords = []
                for ring in geometry['coordinates']:
                    coords.extend(ring)
            elif geom_type == 'MultiPolygon':
                coords = []
                for polygon in geometry['coordinates']:
                    for ring in polygon:
                        coords.extend(ring)
            
            # 检查是否在中国范围内
            if coords:
                in_china = False
                for coord in coords:
                    if len(coord) >= 2:
                        lon, lat = coord[0], coord[1]
                        if (china_bounds['min_lon'] <= lon <= china_bounds['max_lon'] and 
                            china_bounds['min_lat'] <= lat <= china_bounds['max_lat']):
                            in_china = True
                            break
                
                if in_china:
                    filtered_features.append(feature)
        
        filtered_count = len(filtered_features)
        logger.info(f"{dataset_name}: 过滤前 {original_count} 个要素，过滤后 {filtered_count} 个要素")
        
        geojson_data['features'] = filtered_features
        if 'metadata' in geojson_data:
            geojson_data['metadata']['china_filtered'] = True
            geojson_data['metadata']['original_count'] = original_count
            geojson_data['metadata']['filtered_count'] = filtered_count
        
        return geojson_data
    
    def save_geojson(self, geojson_data: dict, output_path: str) -> bool:
        """保存GeoJSON文件"""
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(geojson_data, f, ensure_ascii=False, indent=2)
            logger.info(f"✓ GeoJSON已保存: {output_path}")
            return True
        except Exception as e:
            logger.error(f"✗ 保存GeoJSON失败: {e}")
            return False
    
    def geojson_to_dataframe(self, geojson_data: dict) -> pd.DataFrame:
        """将GeoJSON转换为DataFrame"""
        features = geojson_data.get('features', [])
        rows = []
        
        for feature in features:
            properties = feature.get('properties', {})
            geometry = feature.get('geometry', {})
            
            row = properties.copy()
            row['geometry_type'] = geometry.get('type', '')
            
            # 添加坐标信息
            if geometry.get('type') == 'Point':
                coords = geometry.get('coordinates', [])
                if len(coords) >= 2:
                    row['longitude'] = coords[0]
                    row['latitude'] = coords[1]
            elif geometry.get('type') in ['LineString', 'Polygon']:
                coords = geometry.get('coordinates', [])
                if coords:
                    # 对于线和面，记录第一个点的坐标
                    first_coord = coords[0] if isinstance(coords[0], list) else coords
                    if len(first_coord) >= 2:
                        row['start_longitude'] = first_coord[0]
                        row['start_latitude'] = first_coord[1]
            
            rows.append(row)
        
        return pd.DataFrame(rows)
    
    def save_csv(self, geojson_data: dict, output_path: str) -> bool:
        """保存CSV文件"""
        try:
            df = self.geojson_to_dataframe(geojson_data)
            df.to_csv(output_path, index=False, encoding='utf-8-sig')
            logger.info(f"✓ CSV已保存: {output_path} ({len(df)} 行)")
            return True
        except Exception as e:
            logger.error(f"✗ 保存CSV失败: {e}")
            return False
    
    def save_excel(self, geojson_data: dict, output_path: str) -> bool:
        """保存Excel文件"""
        try:
            df = self.geojson_to_dataframe(geojson_data)
            df.to_excel(output_path, index=False, engine='openpyxl')
            logger.info(f"✓ Excel已保存: {output_path} ({len(df)} 行)")
            return True
        except Exception as e:
            logger.error(f"✗ 保存Excel失败: {e}")
            return False
    
    def scrape_single_dataset(self, dataset_name: str, config: dict) -> bool:
        """爬取单个数据集"""
        logger.info(f"\n{'='*50}")
        logger.info(f"开始爬取: {config['description']} ({dataset_name})")
        logger.info(f"{'='*50}")
        
        service_url = config['url']
        layer_id = config.get('layer_id', 0)
        
        # 测试连接
        if not self.test_service_connection(service_url):
            logger.error(f"服务连接失败: {dataset_name}")
            return False
        
        # 获取服务信息
        service_info = self.get_service_info(service_url)
        if not service_info:
            logger.error(f"无法获取服务信息: {dataset_name}")
            return False
        
        # 保存元数据
        metadata_path = self.output_dir / f"{dataset_name}_metadata.json"
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(service_info, f, ensure_ascii=False, indent=2)
        
        # 获取图层信息
        layer_info = self.get_layer_info(service_url, layer_id)
        if layer_info:
            layer_metadata_path = self.output_dir / f"{dataset_name}_layer_{layer_id}_metadata.json"
            with open(layer_metadata_path, 'w', encoding='utf-8') as f:
                json.dump(layer_info, f, ensure_ascii=False, indent=2)
        
        # 查询要素数据
        geojson_data = self.query_features_with_geometry(service_url, layer_id)
        
        if not geojson_data or not geojson_data.get('features'):
            logger.error(f"未获取到要素数据: {dataset_name}")
            return False
        
        # 应用中国地理过滤器
        geojson_data = self.apply_china_filter(geojson_data, dataset_name)
        
        if not geojson_data.get('features'):
            logger.warning(f"过滤后没有要素: {dataset_name}")
            return False
        
        feature_count = len(geojson_data['features'])
        logger.info(f"获取到 {feature_count} 个要素")
        
        # 保存多种格式
        success = True
        
        # GeoJSON格式
        geojson_path = self.output_dir / f"{dataset_name}.geojson"
        success &= self.save_geojson(geojson_data, str(geojson_path))
        
        # CSV格式
        csv_path = self.output_dir / f"{dataset_name}.csv"
        success &= self.save_csv(geojson_data, str(csv_path))
        
        # Excel格式
        excel_path = self.output_dir / f"{dataset_name}.xlsx"
        success &= self.save_excel(geojson_data, str(excel_path))
        
        if success:
            logger.info(f"✓ {dataset_name} 爬取完成！")
        else:
            logger.error(f"✗ {dataset_name} 爬取部分失败")
        
        return success
    
    def scrape_all_datasets(self, specific_datasets: Optional[List[str]] = None) -> Dict[str, bool]:
        """爬取所有数据集"""
        datasets_to_scrape = specific_datasets or list(self.feature_servers.keys())
        results = {}
        
        logger.info(f"开始批量爬取 {len(datasets_to_scrape)} 个数据集")
        start_time = time.time()
        
        successful = 0
        failed = 0
        
        for i, dataset_name in enumerate(datasets_to_scrape, 1):
            if dataset_name not in self.feature_servers:
                logger.warning(f"未知数据集: {dataset_name}")
                results[dataset_name] = False
                failed += 1
                continue
            
            logger.info(f"\n[{i}/{len(datasets_to_scrape)}] 处理: {dataset_name}")
            
            try:
                success = self.scrape_single_dataset(dataset_name, self.feature_servers[dataset_name])
                results[dataset_name] = success
                
                if success:
                    successful += 1
                else:
                    failed += 1
                    
            except Exception as e:
                logger.error(f"爬取异常: {dataset_name} - {e}")
                results[dataset_name] = False
                failed += 1
            
            # 避免过快请求
            time.sleep(2)
        
        # 统计结果
        elapsed_time = time.time() - start_time
        logger.info(f"\n{'='*60}")
        logger.info(f"批量爬取完成！")
        logger.info(f"总耗时: {elapsed_time:.1f} 秒")
        logger.info(f"成功: {successful} 个数据集")
        logger.info(f"失败: {failed} 个数据集")
        logger.info(f"成功率: {successful/(successful+failed)*100:.1f}%")
        
        if failed > 0:
            failed_datasets = [name for name, success in results.items() if not success]
            logger.info(f"失败的数据集: {failed_datasets}")
        
        logger.info(f"{'='*60}")
        
        return results
    
    def generate_summary_report(self) -> dict:
        """生成爬取总结报告"""
        report = {
            'scrape_time': datetime.now().isoformat(),
            'total_datasets': len(self.feature_servers),
            'datasets_info': {},
            'file_statistics': {}
        }
        
        # 检查输出文件
        for dataset_name in self.feature_servers:
            dataset_info = {
                'description': self.feature_servers[dataset_name]['description'],
                'geometry_type': self.feature_servers[dataset_name]['geometry_type'],
                'files_created': []
            }
            
            # 检查各种格式文件
            for ext in ['.geojson', '.csv', '.xlsx']:
                file_path = self.output_dir / f"{dataset_name}{ext}"
                if file_path.exists():
                    dataset_info['files_created'].append(ext)
                    
                    # 获取文件大小
                    file_size = file_path.stat().st_size
                    if ext not in report['file_statistics']:
                        report['file_statistics'][ext] = {'count': 0, 'total_size': 0}
                    report['file_statistics'][ext]['count'] += 1
                    report['file_statistics'][ext]['total_size'] += file_size
            
            report['datasets_info'][dataset_name] = dataset_info
        
        # 保存报告
        report_path = self.output_dir / 'scraping_summary_report.json'
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        logger.info(f"总结报告已保存: {report_path}")
        return report

def main():
    """主函数"""
    print("=" * 60)
    print("中国能源基础设施GIS数据爬取器 - 高级版本")
    print("Advanced China Energy Infrastructure GIS Data Scraper")
    print("=" * 60)
    
    # 创建爬取器实例
    scraper = AdvancedChinaEnergyGISScraper()
    
    print(f"\n配置的数据集 ({len(scraper.feature_servers)} 个):")
    for i, (name, config) in enumerate(scraper.feature_servers.items(), 1):
        print(f"{i:2d}. {config['description']} ({name})")
    
    # 询问用户选择
    print("\n选择操作:")
    print("1. 爬取全部数据集")
    print("2. 爬取指定数据集")
    print("3. 测试服务连接")
    print("4. 生成总结报告")
    
    choice = input("\n请输入选择 (1-4): ").strip()
    
    if choice == '1':
        # 爬取全部数据集
        results = scraper.scrape_all_datasets()
        scraper.generate_summary_report()
        
    elif choice == '2':
        # 爬取指定数据集
        print("\n请输入要爬取的数据集名称 (用空格分隔):")
        dataset_names = input().strip().split()
        if dataset_names:
            results = scraper.scrape_all_datasets(dataset_names)
        else:
            print("未输入有效的数据集名称")
            
    elif choice == '3':
        # 测试服务连接
        print("\n测试所有服务连接...")
        for name, config in scraper.feature_servers.items():
            status = "✓" if scraper.test_service_connection(config['url']) else "✗"
            print(f"{status} {name}: {config['description']}")
            
    elif choice == '4':
        # 生成总结报告
        report = scraper.generate_summary_report()
        print(f"总结报告已生成: {len(report['datasets_info'])} 个数据集")
        
    else:
        print("无效选择")
    
    print("\n程序结束")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n用户中断操作")
    except Exception as e:
        print(f"\n发生错误: {e}")
        import traceback
        traceback.print_exc()
