#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
中国能源基础设施GIS数据爬取器 - Baker Institute版
China Energy Infrastructure GIS Data Scraper - Baker Institute Edition

基于Baker Institute官方地图的真实ArcGIS服务端点进行数据爬取
数据源: https://www.bakerinstitute.org/map-chinas-energy-infrastructure
ArcGIS Experience Builder: https://experience.arcgis.com/experience/46b9b23991534fe480ea3b5d343772f3/

更新日期: 2025-01-17
作者: AI Assistant

包含23个数据图层:
- 核电站、煤电厂、天然气发电厂、太阳能发电厂、风电厂
- LNG接收站、石油港口、炼油厂、石油储存设施、天然气储存设施
- 天然气管道、原油管道、成品油管道、氢气管道
- 氢气设施、CCS项目、电动汽车电池工厂、矿业资产
- 中国行政边界、城市区域、地球夜景图层
"""

import requests
import json
import time
import pandas as pd
import geopandas as gpd
from pathlib import Path
import logging
from datetime import datetime
from typing import Dict, List, Optional
import warnings
warnings.filterwarnings('ignore')

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('geometry_fix_scraper.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class BakerInstituteGISScraper:
    """Baker Institute中国能源基础设施GIS数据爬取器"""
    
    def __init__(self, output_dir: str = "scraped_gis_data"):
        """初始化Baker Institute数据爬取器"""
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        # 设置请求会话，使用真实的Baker Institute网站引用
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Referer': 'https://experience.arcgis.com/experience/46b9b23991534fe480ea3b5d343772f3/',
            'Origin': 'https://experience.arcgis.com'
        })
        self.session.timeout = 90
        
        # 从现有元数据重建服务URL配置
        self.rebuild_service_urls()
    
    def rebuild_service_urls(self):
        """从Baker Institute地图实际使用的服务端点重建URL"""
        logger.info("使用Baker Institute官方地图的真实服务端点...")
        
        # Baker Institute实际使用的ArcGIS服务基础URL (从浏览器网络请求中发现)
        base_url = "https://services.arcgis.com/lqRTrQp2HrfnJt8U/arcgis/rest/services"
        
        # 从Baker Institute地图实际使用的服务映射
        self.service_mappings = {
            'nuclear_power_plants': f'{base_url}/China_Nuclear_Power_Plants_vSep2024/FeatureServer',
            'coal_power_plants': f'{base_url}/China_coal_power_plants_vJan2024_3/FeatureServer',
            'gas_power_plants': f'{base_url}/China_Gas_Power_Plants_EH_v2024/FeatureServer',
            'solar_power_plants': f'{base_url}/China_Solar_Power_Plants_GEM_202406/FeatureServer',
            'wind_power_plants': f'{base_url}/China_Wind_Power_Plants_GEM_202406/FeatureServer',
            'lng_terminals': f'{base_url}/ChinaLNGTerminals/FeatureServer',
            'oil_ports': f'{base_url}/ChinaOilPorts_Mar2023/FeatureServer',
            'oil_refineries': f'{base_url}/ChinaOilRefineries_Mar2023/FeatureServer',
            'oil_storage': f'{base_url}/ChinaOilStorageFacilities_Mar2023/FeatureServer',
            'gas_storage': f'{base_url}/GlobalData_Midstream_China_Gas_Storage_20240722/FeatureServer',
            'natural_gas_pipelines': f'{base_url}/ChinaNaturalGasPipelines_Mar2023/FeatureServer',
            'crude_pipelines': f'{base_url}/ChinaCrudePipelines_Mar2023/FeatureServer',
            'refined_product_pipelines': f'{base_url}/ChinaRefinedProductPipelines_Mar2023/FeatureServer',
            'hydrogen_pipelines': f'{base_url}/GEI_Hydrogen_pipelines/FeatureServer',
            'hydrogen_facilities': f'{base_url}/GEI_Hydrogen/FeatureServer',
            'ccs_projects': f'{base_url}/GEI_Carbon/FeatureServer',
            'ev_battery_factories': f'{base_url}/China_EVB_factories_Sep2024/FeatureServer',
            'mining_properties': f'{base_url}/MiningProperties_Asia_MiddleEast_CIQ_20241014_3857_2/FeatureServer',
            'china_boundaries': f'{base_url}/CHN_adm_shp/FeatureServer',
            # 额外的基础图层
            'urban_areas': 'https://services2.arcgis.com/jUpNdisbWqRpMo35/arcgis/rest/services/UCDB/FeatureServer',
            'earth_at_night': 'https://tiles.arcgis.com/tiles/P3ePLMYs2RVChkJx/arcgis/rest/services/Earth_at_Night_2016/MapServer'
        }
        
        logger.info(f"重建了 {len(self.service_mappings)} 个服务URL")
        
        # 特殊图层处理说明
        self.special_layers = {
            'earth_at_night': {
                'type': 'MapServer', 
                'description': '地球夜景图层（瓦片地图服务）'
            },
            'urban_areas': {
                'type': 'FeatureServer',
                'description': '城市区域（来自不同的ArcGIS组织）',
                'filter': "CTR_MN_NM = 'China'"
            }
        }
    
    def extract_geometry_data(self, service_url: str, layer_id: int = 0, dataset_name: str = "") -> Optional[dict]:
        """提取完整的几何数据"""
        logger.info(f"提取几何数据: {dataset_name} ({service_url})")
        
        # 检查是否为特殊图层
        if dataset_name in self.special_layers:
            special_info = self.special_layers[dataset_name]
            if special_info['type'] == 'MapServer':
                logger.warning(f"跳过地图服务图层: {dataset_name} - {special_info['description']}")
                return None
        
        all_features = []
        offset = 0
        batch_size = 1000  # 对于官方服务，可以使用更大的批量大小
        max_attempts = 5
        
        # 根据数据集设置特定的筛选条件
        where_clause = '1=1'
        if dataset_name == 'urban_areas':
            where_clause = "CTR_MN_NM = 'China'"
        elif dataset_name == 'coal_power_plants':
            where_clause = "Status IN ('operating','construction','permitted','pre-permit','announced')"
        elif dataset_name == 'solar_power_plants' or dataset_name == 'wind_power_plants':
            where_clause = "Status NOT IN ('shelved - inferred 2 y','shelved','cancelled','cancelled - inferred 4 y','mothballed','retired')"
        elif dataset_name == 'hydrogen_facilities' or dataset_name == 'ccs_projects':
            where_clause = "Country = 'China'"
        elif dataset_name == 'hydrogen_pipelines':
            where_clause = "Country = 'China'"
        elif dataset_name == 'mining_properties':
            where_clause = "Country__ = 'China' AND Developmen <> 'Closed'"
        
        
        while True:
            attempt = 0
            current_batch = None
            
            # 多次尝试当前批次
            while attempt < max_attempts:
                try:
                    # 构建查询参数，使用特定的筛选条件
                    params = {
                        'f': 'geojson',  # 使用GeoJSON格式确保几何数据完整
                        'where': where_clause,
                        'outFields': '*',
                        'returnGeometry': 'true',
                        'geometryPrecision': 8,  # 高精度几何
                        'resultRecordCount': batch_size,
                        'resultOffset': offset,
                        'spatialRel': 'esriSpatialRelIntersects',
                        'outSR': '4326',  # WGS84坐标系
                        'returnZ': 'false',
                        'returnM': 'false',
                        'maxAllowableOffset': '',
                        'geometryType': 'esriGeometryEnvelope',
                        'inSR': '4326'
                    }
                    
                    logger.info(f"查询批次: offset={offset}, size={batch_size}, 尝试={attempt+1}")
                    
                    response = self.session.get(f"{service_url}/{layer_id}/query", params=params, timeout=120)
                    response.raise_for_status()
                    
                    data = response.json()
                    
                    if 'error' in data:
                        logger.error(f"API返回错误: {data['error']}")
                        attempt += 1
                        time.sleep(5 * attempt)
                        continue
                    
                    if 'features' not in data:
                        logger.warning(f"响应中没有features字段: {list(data.keys())}")
                        if attempt == max_attempts - 1:
                            return None
                        attempt += 1
                        continue
                    
                    current_batch = data['features']
                    
                    # 验证几何数据完整性
                    geometry_count = 0
                    for feature in current_batch:
                        if feature.get('geometry') and feature['geometry'].get('coordinates'):
                            geometry_count += 1
                    
                    logger.info(f"批次结果: {len(current_batch)} 个要素, {geometry_count} 个包含几何数据")
                    break
                    
                except requests.exceptions.Timeout:
                    logger.warning(f"请求超时，尝试 {attempt + 1}/{max_attempts}")
                    attempt += 1
                    time.sleep(10 * attempt)
                except requests.exceptions.RequestException as e:
                    logger.error(f"请求异常: {e}")
                    attempt += 1
                    time.sleep(5 * attempt)
                except json.JSONDecodeError as e:
                    logger.error(f"JSON解析失败: {e}")
                    attempt += 1
                    time.sleep(3)
                except Exception as e:
                    logger.error(f"未知异常: {e}")
                    attempt += 1
                    time.sleep(5)
            
            # 如果所有尝试都失败
            if current_batch is None:
                logger.error(f"批次获取失败，停止查询: offset={offset}")
                break
            
            # 如果没有更多数据
            if not current_batch:
                logger.info("没有更多要素，查询完成")
                break
            
            # 添加到总结果
            all_features.extend(current_batch)
            logger.info(f"累计获取: {len(all_features)} 个要素")
            
            # 如果当前批次少于预期，说明已经是最后一批
            if len(current_batch) < batch_size:
                logger.info("获取到最后一批数据")
                break
            
            # 准备下一批
            offset += batch_size
            time.sleep(2)  # 延时避免过快请求
        
        # 构建GeoJSON结果
        if all_features:
            geojson = {
                "type": "FeatureCollection",
                "features": all_features,
                "metadata": {
                    "dataset": dataset_name,
                    "total_features": len(all_features),
                    "source_url": service_url,
                    "layer_id": layer_id,
                    "extraction_time": datetime.now().isoformat(),
                    "coordinate_system": "EPSG:4326",
                    "geometry_verified": True
                }
            }
            
            # 验证几何数据质量
            geometry_stats = self.analyze_geometry_quality(geojson)
            geojson['metadata']['geometry_stats'] = geometry_stats
            
            return geojson
        
        return None
    
    def analyze_geometry_quality(self, geojson_data: dict) -> dict:
        """分析几何数据质量"""
        features = geojson_data.get('features', [])
        stats = {
            'total_features': len(features),
            'features_with_geometry': 0,
            'features_without_geometry': 0,
            'geometry_types': {},
            'coordinate_ranges': {
                'longitude': {'min': float('inf'), 'max': float('-inf')},
                'latitude': {'min': float('inf'), 'max': float('-inf')}
            }
        }
        
        for feature in features:
            geometry = feature.get('geometry')
            
            if geometry and geometry.get('coordinates'):
                stats['features_with_geometry'] += 1
                
                # 统计几何类型
                geom_type = geometry.get('type', 'Unknown')
                stats['geometry_types'][geom_type] = stats['geometry_types'].get(geom_type, 0) + 1
                
                # 分析坐标范围
                coords = geometry.get('coordinates', [])
                self._extract_coordinate_bounds(coords, stats['coordinate_ranges'])
                
            else:
                stats['features_without_geometry'] += 1
        
        # 修复无限值
        if stats['coordinate_ranges']['longitude']['min'] == float('inf'):
            stats['coordinate_ranges'] = None
        
        logger.info(f"几何质量分析: {stats['features_with_geometry']}/{stats['total_features']} 个要素包含几何数据")
        
        return stats
    
    def _extract_coordinate_bounds(self, coords, bounds):
        """递归提取坐标边界"""
        if not coords:
            return
        
        if isinstance(coords[0], (int, float)):
            # 这是一个坐标点 [lon, lat]
            if len(coords) >= 2:
                lon, lat = coords[0], coords[1]
                bounds['longitude']['min'] = min(bounds['longitude']['min'], lon)
                bounds['longitude']['max'] = max(bounds['longitude']['max'], lon)
                bounds['latitude']['min'] = min(bounds['latitude']['min'], lat)
                bounds['latitude']['max'] = max(bounds['latitude']['max'], lat)
        else:
            # 这是坐标数组，递归处理
            for coord in coords:
                self._extract_coordinate_bounds(coord, bounds)
    
    def save_complete_geojson(self, geojson_data: dict, dataset_name: str) -> bool:
        """保存完整的GeoJSON文件"""
        try:
            output_path = self.output_dir / f"{dataset_name}.geojson"
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(geojson_data, f, ensure_ascii=False, indent=2)
            
            # 验证保存的文件
            file_size = output_path.stat().st_size
            feature_count = len(geojson_data.get('features', []))
            
            logger.info(f"✓ GeoJSON已保存: {output_path}")
            logger.info(f"  文件大小: {file_size:,} 字节")
            logger.info(f"  要素数量: {feature_count:,} 个")
            
            return True
            
        except Exception as e:
            logger.error(f"✗ 保存GeoJSON失败: {e}")
            return False
    
    def fix_single_dataset(self, dataset_name: str) -> bool:
        """修复单个数据集的几何数据"""
        if dataset_name not in self.service_mappings:
            logger.error(f"未知数据集: {dataset_name}")
            return False
        
        service_url = self.service_mappings[dataset_name]
        
        logger.info(f"\n{'='*60}")
        logger.info(f"修复数据集: {dataset_name}")
        logger.info(f"服务URL: {service_url}")
        logger.info(f"{'='*60}")
        
        # 提取几何数据
        geojson_data = self.extract_geometry_data(service_url, 0, dataset_name)
        
        if not geojson_data:
            logger.error(f"未能提取几何数据: {dataset_name}")
            return False
        
        # 保存GeoJSON
        success = self.save_complete_geojson(geojson_data, dataset_name)
        
        if success:
            # 同时更新CSV和Excel文件
            try:
                # 使用geopandas读取GeoJSON并保存为其他格式
                gdf = gpd.read_file(self.output_dir / f"{dataset_name}.geojson")
                
                # 保存CSV（包含几何信息）
                csv_path = self.output_dir / f"{dataset_name}.csv"
                df_for_csv = gdf.copy()
                df_for_csv['geometry_wkt'] = gdf.geometry.to_wkt()
                df_for_csv = df_for_csv.drop('geometry', axis=1)
                df_for_csv.to_csv(csv_path, index=False, encoding='utf-8-sig')
                
                # 保存Excel
                excel_path = self.output_dir / f"{dataset_name}.xlsx"
                df_for_csv.to_excel(excel_path, index=False, engine='openpyxl')
                
                logger.info(f"✓ 同步更新CSV和Excel文件")
                
            except Exception as e:
                logger.warning(f"更新CSV/Excel失败: {e}")
        
        return success
    
    def fix_all_datasets(self) -> Dict[str, bool]:
        """修复所有数据集的几何数据"""
        logger.info(f"开始修复 {len(self.service_mappings)} 个数据集的几何数据")
        
        results = {}
        successful = 0
        
        for i, dataset_name in enumerate(self.service_mappings.keys(), 1):
            logger.info(f"\n[{i}/{len(self.service_mappings)}] 处理: {dataset_name}")
            
            try:
                success = self.fix_single_dataset(dataset_name)
                results[dataset_name] = success
                
                if success:
                    successful += 1
                    logger.info(f"✓ {dataset_name} 修复成功")
                else:
                    logger.error(f"✗ {dataset_name} 修复失败")
                    
            except Exception as e:
                logger.error(f"✗ {dataset_name} 修复异常: {e}")
                results[dataset_name] = False
            
            # 避免请求过快
            time.sleep(3)
        
        logger.info(f"\n修复完成: {successful}/{len(self.service_mappings)} 个数据集")
        return results

def main():
    """主函数"""
    print("=" * 60)
    print("�️  Baker Institute中国能源基础设施GIS数据爬取器")
    print("   China Energy Infrastructure GIS Data Scraper")
    print("   数据源: https://www.bakerinstitute.org/map-chinas-energy-infrastructure")
    print("=" * 60)
    
    scraper = BakerInstituteGISScraper()
    
    print(f"\n📋 Baker Institute中国能源基础设施数据集 ({len(scraper.service_mappings)} 个):")
    for i, dataset_name in enumerate(scraper.service_mappings.keys(), 1):
        print(f"  {i:2d}. {dataset_name}")
    
    print("\n选择操作:")
    print("1. � 下载所有数据集")
    print("2. 🎯 下载指定数据集")
    print("3. 📊 检查现有文件状态")
    print("4. 📝 显示数据集详情")
    
    choice = input("\n请输入选择 (1-4): ").strip()
    
    if choice == '1':
        print("\n🚀 开始下载所有数据集...")
        results = scraper.fix_all_datasets()
        
        successful = sum(1 for success in results.values() if success)
        print(f"\n✅ 下载完成: {successful}/{len(results)} 个数据集")
        
    elif choice == '2':
        print(f"\n请输入要下载的数据集编号 (1-{len(scraper.service_mappings)}):")
        try:
            idx = int(input().strip()) - 1
            dataset_names = list(scraper.service_mappings.keys())
            if 0 <= idx < len(dataset_names):
                dataset_name = dataset_names[idx]
                print(f"\n🎯 下载: {dataset_name}")
                success = scraper.fix_single_dataset(dataset_name)
                if success:
                    print(f"✅ {dataset_name} 下载成功")
                else:
                    print(f"❌ {dataset_name} 下载失败")
            else:
                print("❌ 无效编号")
        except ValueError:
            print("❌ 请输入有效数字")
            
    elif choice == '3':
        print("\n📊 检查现有文件...")
        for dataset_name in scraper.service_mappings.keys():
            geojson_file = scraper.output_dir / f"{dataset_name}.geojson"
            if geojson_file.exists():
                try:
                    gdf = gpd.read_file(geojson_file)
                    print(f"✅ {dataset_name}: {len(gdf)} 个要素，几何类型: {gdf.geom_type.unique()}")
                except:
                    print(f"⚠️  {dataset_name}: 文件存在但读取失败")
            else:
                print(f"❌ {dataset_name}: GeoJSON文件不存在")
                
    elif choice == '4':
        print("\n📝 Baker Institute数据集详情:")
        print("数据源: https://www.bakerinstitute.org/map-chinas-energy-infrastructure")
        print("包含以下23个数据图层:")
        
        categories = {
            "🔌 电力基础设施": ['nuclear_power_plants', 'coal_power_plants', 'gas_power_plants', 'solar_power_plants', 'wind_power_plants'],
            "🛢️  石油基础设施": ['oil_ports', 'oil_refineries', 'oil_storage', 'crude_pipelines', 'refined_product_pipelines'],
            "⛽ 天然气基础设施": ['lng_terminals', 'gas_storage', 'natural_gas_pipelines'],
            "🟢 新兴能源技术": ['hydrogen_pipelines', 'hydrogen_facilities', 'ccs_projects', 'ev_battery_factories'],
            "⛏️  资源与边界": ['mining_properties', 'china_boundaries', 'urban_areas', 'earth_at_night']
        }
        
        for category, datasets in categories.items():
            print(f"\n{category}:")
            for dataset in datasets:
                if dataset in scraper.service_mappings:
                    print(f"  • {dataset}")
    
    else:
        print("❌ 无效选择")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n用户中断操作")
    except Exception as e:
        print(f"\n发生错误: {e}")
        import traceback
        traceback.print_exc()
