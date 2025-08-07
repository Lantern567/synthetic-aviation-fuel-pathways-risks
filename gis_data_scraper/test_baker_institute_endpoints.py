#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Baker Institute服务端点测试脚本
Test Baker Institute Service Endpoints

测试所有Baker Institute地图使用的真实ArcGIS服务端点
"""

import requests
import json
from typing import Dict, List

def test_service_endpoint(service_url: str, service_name: str) -> Dict:
    """测试单个服务端点"""
    try:
        # 测试服务根端点
        response = requests.get(f"{service_url}?f=json", timeout=30)
        response.raise_for_status()
        
        service_info = response.json()
        
        # 测试第一个图层
        layer_response = requests.get(f"{service_url}/0?f=json", timeout=30)
        layer_info = layer_response.json() if layer_response.status_code == 200 else None
        
        # 测试数据查询（获取少量记录）
        query_params = {
            'f': 'json',
            'where': '1=1',
            'outFields': '*',
            'returnGeometry': 'true',
            'resultRecordCount': 5
        }
        
        query_response = requests.get(f"{service_url}/0/query", params=query_params, timeout=30)
        query_data = query_response.json() if query_response.status_code == 200 else None
        
        return {
            'name': service_name,
            'url': service_url,
            'status': 'SUCCESS',
            'service_info': {
                'service_name': service_info.get('name', 'Unknown'),
                'description': service_info.get('description', ''),
                'layers': len(service_info.get('layers', [])),
                'max_record_count': service_info.get('maxRecordCount', 0)
            },
            'layer_info': {
                'name': layer_info.get('name', 'Unknown') if layer_info else 'N/A',
                'type': layer_info.get('type', 'Unknown') if layer_info else 'N/A',
                'geometry_type': layer_info.get('geometryType', 'Unknown') if layer_info else 'N/A'
            },
            'sample_features': len(query_data.get('features', [])) if query_data else 0
        }
        
    except Exception as e:
        return {
            'name': service_name,
            'url': service_url,
            'status': 'ERROR',
            'error': str(e)
        }

def main():
    """主测试函数"""
    print("🧪 Baker Institute服务端点测试")
    print("=" * 60)
    
    # Baker Institute地图实际使用的服务端点
    base_url = "https://services.arcgis.com/lqRTrQp2HrfnJt8U/arcgis/rest/services"
    
    services = {
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
        'urban_areas': 'https://services2.arcgis.com/jUpNdisbWqRpMo35/arcgis/rest/services/UCDB/FeatureServer'
    }
    
    results = []
    successful = 0
    
    for i, (name, url) in enumerate(services.items(), 1):
        print(f"[{i:2d}/{len(services)}] 测试: {name}")
        result = test_service_endpoint(url, name)
        results.append(result)
        
        if result['status'] == 'SUCCESS':
            successful += 1
            print(f"  ✅ 成功 - {result['sample_features']} 个样本要素")
        else:
            print(f"  ❌ 失败 - {result.get('error', 'Unknown error')}")
    
    print("\n" + "=" * 60)
    print(f"📊 测试结果: {successful}/{len(services)} 个服务可用")
    print("=" * 60)
    
    # 显示详细结果
    print("\n📋 详细结果:")
    for result in results:
        if result['status'] == 'SUCCESS':
            print(f"\n✅ {result['name']}")
            print(f"   服务名称: {result['service_info']['service_name']}")
            print(f"   图层数量: {result['service_info']['layers']}")
            print(f"   几何类型: {result['layer_info']['geometry_type']}")
            print(f"   最大记录数: {result['service_info']['max_record_count']}")
        else:
            print(f"\n❌ {result['name']}: {result.get('error', 'Unknown error')}")
    
    # 保存测试结果
    try:
        with open('baker_institute_endpoint_test_results.json', 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"\n💾 测试结果已保存到: baker_institute_endpoint_test_results.json")
    except Exception as e:
        print(f"\n⚠️  保存测试结果失败: {e}")

if __name__ == "__main__":
    main()
