"""
管道路径类型定义
定义管道路径相关的数据类，避免循环导入问题
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Tuple
import json

class PipelineRouteNotFoundError(Exception):
    """管道路径未找到异常"""

    def __init__(self, start_lat: float, start_lon: float, end_lat: float, end_lon: float,
                 max_access_distance_km: float, pipeline_types_tried: List[str]):
        self.start_lat = start_lat
        self.start_lon = start_lon
        self.end_lat = end_lat
        self.end_lon = end_lon
        self.max_access_distance_km = max_access_distance_km
        self.pipeline_types_tried = pipeline_types_tried

        message = (f"未找到管道运输路径: "
                  f"起点({start_lat:.6f}, {start_lon:.6f}) -> "
                  f"终点({end_lat:.6f}, {end_lon:.6f}), "
                  f"最大接入距离: {max_access_distance_km}km, "
                  f"尝试的管道类型: {', '.join(pipeline_types_tried)}")
        super().__init__(message)

@dataclass
class PipelineRoute:
    """管道路径结果数据类"""
    total_distance_km: float
    access_distance_km: float  # 起点吸附距离
    pipeline_distance_km: float  # 管道网络距离
    egress_distance_km: float  # 终点吸附距离
    pipeline_types_used: List[str]  # 使用的管道类型
    route_found: bool
    calculation_method: str
    # 新增几何信息字段
    route_geometry: Optional[List[Tuple[float, float]]] = None  # 路径几何坐标序列 [(lat, lon), ...]
    access_point_coords: Optional[Tuple[float, float]] = None  # 起点接入管道的坐标
    egress_point_coords: Optional[Tuple[float, float]] = None  # 终点离开管道的坐标
    start_coords: Optional[Tuple[float, float]] = None  # 起点原始坐标
    end_coords: Optional[Tuple[float, float]] = None  # 终点原始坐标

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'total_distance_km': self.total_distance_km,
            'access_distance_km': self.access_distance_km,
            'pipeline_distance_km': self.pipeline_distance_km,
            'egress_distance_km': self.egress_distance_km,
            'pipeline_types_used': self.pipeline_types_used,
            'route_found': self.route_found,
            'calculation_method': self.calculation_method,
            'route_geometry': self.route_geometry,
            'access_point_coords': self.access_point_coords,
            'egress_point_coords': self.egress_point_coords,
            'start_coords': self.start_coords,
            'end_coords': self.end_coords
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PipelineRoute':
        """从字典创建对象"""
        return cls(
            total_distance_km=data.get('total_distance_km', 0.0),
            access_distance_km=data.get('access_distance_km', 0.0),
            pipeline_distance_km=data.get('pipeline_distance_km', 0.0),
            egress_distance_km=data.get('egress_distance_km', 0.0),
            pipeline_types_used=data.get('pipeline_types_used', []),
            route_found=data.get('route_found', False),
            calculation_method=data.get('calculation_method', ''),
            route_geometry=data.get('route_geometry'),
            access_point_coords=data.get('access_point_coords'),
            egress_point_coords=data.get('egress_point_coords'),
            start_coords=data.get('start_coords'),
            end_coords=data.get('end_coords')
        )

    def to_json(self) -> str:
        """转换为JSON字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str) -> 'PipelineRoute':
        """从JSON字符串创建对象"""
        return cls.from_dict(json.loads(json_str))

@dataclass
class ClusteredPipelineRoute:
    """聚类管道路径结果类"""
    cluster_id: int
    layer1_distances: Dict[str, float]
    layer2_distance: float
    layer3_distance: float
    total_distance_per_member: Dict[str, float]
    route_geometry: Optional[List[Tuple[float, float]]] = None
    cluster_center: Optional[Tuple[float, float]] = None
    pipeline_access_point: Optional[Tuple[float, float]] = None
    pipeline_types_used: List[str] = None
    route_found: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'cluster_id': self.cluster_id,
            'layer1_distances': self.layer1_distances,
            'layer2_distance': self.layer2_distance,
            'layer3_distance': self.layer3_distance,
            'total_distance_per_member': self.total_distance_per_member,
            'route_geometry': self.route_geometry,
            'cluster_center': self.cluster_center,
            'pipeline_access_point': self.pipeline_access_point,
            'pipeline_types_used': self.pipeline_types_used,
            'route_found': self.route_found
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ClusteredPipelineRoute':
        """从字典创建对象"""
        return cls(
            cluster_id=data.get('cluster_id', 0),
            layer1_distances=data.get('layer1_distances', {}),
            layer2_distance=data.get('layer2_distance', 0.0),
            layer3_distance=data.get('layer3_distance', 0.0),
            total_distance_per_member=data.get('total_distance_per_member', {}),
            route_geometry=data.get('route_geometry'),
            cluster_center=data.get('cluster_center'),
            pipeline_access_point=data.get('pipeline_access_point'),
            pipeline_types_used=data.get('pipeline_types_used'),
            route_found=data.get('route_found', True)
        )

    def to_json(self) -> str:
        """转换为JSON字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str) -> 'ClusteredPipelineRoute':
        """从JSON字符串创建对象"""
        return cls.from_dict(json.loads(json_str))

@dataclass
class PipelinePoint:
    """管道点数据类"""
    lat: float
    lon: float
    pipeline_id: str
    pipeline_type: str  # 'crude', 'refined', 'natural_gas'
    segment_id: int  # 在管道中的线段编号