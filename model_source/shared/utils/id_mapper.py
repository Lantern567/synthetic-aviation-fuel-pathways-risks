"""
ID映射工具类
用于将业务ID映射到超图节点ID
"""

from typing import Optional, Dict, Any


class IDMapper:
    """将业务逻辑ID映射到超图节点ID的工具类"""

    @staticmethod
    def co2_source_to_node_id(source_id: str, clustering_results) -> Optional[str]:
        """
        将CO2源ID映射到超图节点ID

        Args:
            source_id: CO2源业务ID (例如: 'coal_plant_001', 'lng_terminal_002')
            clustering_results: 聚类结果对象

        Returns:
            超图节点ID (例如: 'co2_cluster_5', 'co2_noise_coal_plant_001')
            如果未找到返回None
        """
        if not clustering_results:
            return None

        # 检查是否在某个聚类中
        if hasattr(clustering_results, 'clusters') and clustering_results.clusters:
            for cluster in clustering_results.clusters:
                if source_id in cluster.member_locations:
                    return f"co2_cluster_{cluster.cluster_id}"

        # 检查是否是噪声点
        if hasattr(clustering_results, 'noise_points') and clustering_results.noise_points:
            for noise_loc, _ in clustering_results.noise_points:
                if noise_loc == source_id:
                    return f"co2_noise_{source_id}"

        return None

    @staticmethod
    def factory_to_node_id(factory_id: str) -> str:
        """
        将工厂ID映射到超图节点ID

        Args:
            factory_id: 工厂业务ID

        Returns:
            超图节点ID (例如: 'saf_factory_beijing')
        """
        return f"saf_factory_{factory_id}"

    @staticmethod
    def get_cluster_info(source_id: str, clustering_results) -> Optional[Dict[str, Any]]:
        """
        获取CO2源的聚类信息

        Args:
            source_id: CO2源ID
            clustering_results: 聚类结果对象

        Returns:
            聚类信息字典 {'cluster_id': int/str, 'is_noise': bool, 'center_coord': tuple}
            如果未找到返回None
        """
        if not clustering_results:
            return None

        # 检查聚类
        if hasattr(clustering_results, 'clusters') and clustering_results.clusters:
            for cluster in clustering_results.clusters:
                if source_id in cluster.member_locations:
                    return {
                        'cluster_id': cluster.cluster_id,
                        'is_noise': False,
                        'center_coord': cluster.center_coord
                    }

        # 检查噪声点
        if hasattr(clustering_results, 'noise_points') and clustering_results.noise_points:
            for noise_loc, noise_coord in clustering_results.noise_points:
                if noise_loc == source_id:
                    return {
                        'cluster_id': f"noise_{source_id}",
                        'is_noise': True,
                        'center_coord': noise_coord
                    }

        return None
