"""
天然气管道坐标集成器
从GeoJSON文件中提取管道坐标数据，并与价格数据进行匹配集成
"""

import json
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import re
from geopy.distance import geodesic

class PipelineCoordinateIntegrator:
    """天然气管道坐标集成器"""
    
    def __init__(self, geojson_path: str, price_data_path: str):
        """
        初始化集成器
        
        Args:
            geojson_path: GeoJSON文件路径
            price_data_path: 价格数据CSV文件路径
        """
        self.geojson_path = Path(geojson_path)
        self.price_data_path = Path(price_data_path)
        self.geojson_data = None
        self.price_data = None
        
    def load_geojson_data(self) -> Dict:
        """加载GeoJSON数据"""
        try:
            with open(self.geojson_path, 'r', encoding='utf-8') as f:
                self.geojson_data = json.load(f)
            print(f"成功加载GeoJSON数据，包含 {len(self.geojson_data['features'])} 个管道要素")
            return self.geojson_data
        except Exception as e:
            print(f"加载GeoJSON数据失败: {e}")
            raise
    
    def load_price_data(self) -> pd.DataFrame:
        """加载价格数据"""
        try:
            self.price_data = pd.read_csv(self.price_data_path, encoding='utf-8')
            print(f"成功加载价格数据，包含 {len(self.price_data)} 条记录")
            return self.price_data
        except Exception as e:
            print(f"加载价格数据失败: {e}")
            raise
    
    def extract_pipeline_coordinates(self) -> Dict[str, Dict]:
        """
        从GeoJSON中提取管道坐标信息
        
        Returns:
            Dict: 管道名称到坐标信息的映射
        """
        if not self.geojson_data:
            self.load_geojson_data()
        
        pipeline_coords = {}
        
        for feature in self.geojson_data['features']:
            properties = feature['properties']
            geometry = feature['geometry']
            
            # 获取管道名称
            name = properties.get('Name', '')
            if not name:
                continue
            
            # 获取其他属性
            operator = properties.get('Operator', '')
            capacity = properties.get('Capacity', 0)
            status = properties.get('Status', '')
            
            # 处理坐标（LineString格式）
            if geometry['type'] == 'LineString':
                coordinates = geometry['coordinates']
                
                # 计算起点和终点坐标
                start_coord = coordinates[0]  # [longitude, latitude]
                end_coord = coordinates[-1]
                
                # 计算中心点坐标（所有坐标点的平均值）
                lons = [coord[0] for coord in coordinates]
                lats = [coord[1] for coord in coordinates]
                center_lon = sum(lons) / len(lons)
                center_lat = sum(lats) / len(lats)
                
                # 计算管道长度（公里）
                total_length = 0
                for i in range(len(coordinates) - 1):
                    point1 = (coordinates[i][1], coordinates[i][0])  # (lat, lon)
                    point2 = (coordinates[i+1][1], coordinates[i+1][0])
                    total_length += geodesic(point1, point2).kilometers
                
                pipeline_coords[name] = {
                    'operator': operator,
                    'capacity': capacity,
                    'status': status,
                    'start_longitude': start_coord[0],
                    'start_latitude': start_coord[1],
                    'end_longitude': end_coord[0],
                    'end_latitude': end_coord[1],
                    'center_longitude': center_lon,
                    'center_latitude': center_lat,
                    'length_km': total_length,
                    'coordinates_count': len(coordinates)
                }
        
        print(f"提取了 {len(pipeline_coords)} 个管道的坐标信息")
        return pipeline_coords
    
    def fuzzy_match_pipeline_names(self, geojson_names: List[str], price_names: List[str], 
                                 threshold: float = 0.7) -> Dict[str, str]:
        """
        对管道名称进行模糊匹配
        
        Args:
            geojson_names: GeoJSON中的管道名称列表
            price_names: 价格数据中的管道名称列表
            threshold: 匹配阈值
            
        Returns:
            Dict: 价格数据名称到GeoJSON名称的映射
        """
        from difflib import SequenceMatcher
        
        matches = {}
        
        for price_name in price_names:
            best_match = None
            best_score = 0
            
            for geojson_name in geojson_names:
                # 计算相似度
                similarity = SequenceMatcher(None, price_name.lower(), geojson_name.lower()).ratio()
                
                if similarity > best_score and similarity >= threshold:
                    best_score = similarity
                    best_match = geojson_name
            
            if best_match:
                matches[price_name] = best_match
                print(f"匹配: '{price_name}' -> '{best_match}' (相似度: {best_score:.3f})")
        
        print(f"成功匹配 {len(matches)} 个管道名称")
        return matches
    
    def integrate_coordinates(self) -> pd.DataFrame:
        """
        将坐标信息集成到价格数据中
        
        Returns:
            pd.DataFrame: 集成了坐标信息的数据框
        """
        if not self.price_data:
            self.load_price_data()
        
        # 提取管道坐标
        pipeline_coords = self.extract_pipeline_coordinates()
        
        # 获取名称列表
        geojson_names = list(pipeline_coords.keys())
        price_names = self.price_data['pipeline_name'].tolist()
        
        # 进行名称匹配
        name_matches = self.fuzzy_match_pipeline_names(geojson_names, price_names)
        
        # 创建集成数据
        integrated_data = self.price_data.copy()
        
        # 添加坐标列
        coord_columns = ['start_longitude', 'start_latitude', 'end_longitude', 'end_latitude',
                        'center_longitude', 'center_latitude', 'length_km', 'coordinates_count']
        
        for col in coord_columns:
            integrated_data[col] = np.nan
        
        # 填充坐标数据
        matched_count = 0
        for idx, row in integrated_data.iterrows():
            pipeline_name = row['pipeline_name']
            
            if pipeline_name in name_matches:
                geojson_name = name_matches[pipeline_name]
                coord_info = pipeline_coords[geojson_name]
                
                for col in coord_columns:
                    integrated_data.at[idx, col] = coord_info[col]
                
                matched_count += 1
        
        print(f"成功为 {matched_count} 个管道集成了坐标信息")
        
        # 添加便于使用的lat/lon列（使用中心坐标）
        integrated_data['lat'] = integrated_data['center_latitude']
        integrated_data['lon'] = integrated_data['center_longitude']
        
        return integrated_data
    
    def save_integrated_data(self, output_path: str, integrated_data: pd.DataFrame = None):
        """
        保存集成后的数据
        
        Args:
            output_path: 输出文件路径
            integrated_data: 集成数据（如果为None则重新生成）
        """
        if integrated_data is None:
            integrated_data = self.integrate_coordinates()
        
        try:
            integrated_data.to_csv(output_path, index=False, encoding='utf-8')
            print(f"成功保存集成数据到: {output_path}")
            
            # 打印统计信息
            total_pipelines = len(integrated_data)
            with_coords = integrated_data['lat'].notna().sum()
            without_coords = total_pipelines - with_coords
            
            print(f"\n数据统计:")
            print(f"总管道数: {total_pipelines}")
            print(f"有坐标信息: {with_coords}")
            print(f"无坐标信息: {without_coords}")
            print(f"坐标覆盖率: {with_coords/total_pipelines*100:.1f}%")
            
        except Exception as e:
            print(f"保存数据失败: {e}")
            raise

def main():
    """主函数"""
    # 设置文件路径
    project_root = Path(__file__).parent.parent
    geojson_path = project_root.parent / "gis_data_scraper" / "scraped_gis_data" / "natural_gas_pipelines.geojson"
    price_data_path = project_root / "data" / "integrated_gas_pipeline_price_data.csv"
    output_path = project_root / "data" / "integrated_gas_pipeline_price_data_with_coords.csv"
    
    print("开始管道坐标集成流程...")
    print(f"GeoJSON文件: {geojson_path}")
    print(f"价格数据文件: {price_data_path}")
    print(f"输出文件: {output_path}")
    
    # 创建集成器
    integrator = PipelineCoordinateIntegrator(
        geojson_path=str(geojson_path),
        price_data_path=str(price_data_path)
    )
    
    # 执行集成
    integrated_data = integrator.integrate_coordinates()
    
    # 保存结果
    integrator.save_integrated_data(str(output_path), integrated_data)
    
    print("\n管道坐标集成完成！")

if __name__ == "__main__":
    main()