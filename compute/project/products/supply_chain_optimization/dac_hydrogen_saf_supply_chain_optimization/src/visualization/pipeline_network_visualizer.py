#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
PipelineNetworkVisualizer
=========================

参考 `transport_route_visualizer.py` 的结构，使用 `frykit.plot`
在地图上展示绿氢供应链中的设施与管道网络。
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import matplotlib.pyplot as plt
import matplotlib
import numpy as np
import pandas as pd
from datetime import datetime
from matplotlib.artist import Artist
from matplotlib import lines as mlines

try:
    import geopandas as gpd
except ModuleNotFoundError as e:
    raise ModuleNotFoundError("缺少 geopandas，请先运行 `pip install geopandas shapely fiona pyproj` 后再运行脚本。") from e

try:
    import frykit.plot as fplt
    from cartopy.feature import LAND, RIVERS
except ModuleNotFoundError as e:
    raise ModuleNotFoundError(
        "缺少 frykit，请先执行 `pip install frykit cartopy shapely` 后再运行脚本。"
    ) from e


matplotlib.rcParams["font.sans-serif"] = [
    "Microsoft YaHei",
    "SimHei",
    "SimSun",
    "WenQuanYi Zen Hei",
    "Noto Sans CJK SC",
    "DejaVu Sans",
    "sans-serif",
]
matplotlib.rcParams["axes.unicode_minus"] = False


class PipelineNetworkVisualizer:
    """可视化绿氢供应链的设施分布与管道网络。"""

    def __init__(self) -> None:
        self.logger = logging.getLogger(self.__class__.__name__)
        logging.basicConfig(level=logging.INFO, format="%(message)s")

        root = Path(__file__).resolve().parents[5]
        self.results_dir = root / "products" / "supply_chain_optimization" \
            / "dac_hydrogen_saf_supply_chain_optimization" / "results"
        self.fig_dir = self.results_dir / "figures"
        self.fig_dir.mkdir(exist_ok=True, parents=True)

        self.gis_data_dir = root / "products" / "gis_energy_mapping" \
            / "gis_data_scraper" / "scraped_gis_data"

        # 投影及范围（仿照 transport_route_visualizer 模板）
        self.map_crs = fplt.CN_AZIMUTHAL_EQUIDISTANT
        self.data_crs = fplt.PLATE_CARREE
        self.map_extent = (105, 125, 30, 48)
        self.xticks = np.arange(106, 125, 4)
        self.yticks = np.arange(30, 49, 4)

        self.point_styles = {
            "solar": dict(marker="v", color="#FFB347", s=35, alpha=0.9),
            "wind": dict(marker="^", color="#4DB6AC", s=35, alpha=0.9),
            "airport": dict(marker="o", color="#5C6BC0", s=65, alpha=0.85),
            "co2": dict(marker="s", color="#EF5350", s=22, alpha=0.6),
        }

        self.pipeline_colors = {
            "crude": "#FF8A65",
            "refined": "#4FC3F7",
            "natural_gas": "#81C784",
        }

    # ------------------------------------------------------------------
    # 读取数据
    # ------------------------------------------------------------------

    def _latest(self, pattern: str) -> Path:
        files = sorted(self.results_dir.glob(pattern))
        if not files:
            raise FileNotFoundError(f"未找到匹配 {pattern} 的结果文件。")
        return files[-1]

    def load_point_layers(self) -> Dict[str, pd.DataFrame]:
        renewable = pd.read_csv(self._latest("renewable_energy_plants_*.csv"))
        airports = pd.read_csv(self._latest("airports_*.csv"))

        # ===== v4.0变更: CO2源点文件在DAC版本中已删除 =====
        # v4.0使用DAC直接捕获，无需加载co2_capture_sources.csv
        # 如果文件不存在，返回空DataFrame保持兼容性
        co2_sources_path = self.results_dir.parent / "data" / "co2_capture_sources.csv"
        if co2_sources_path.exists():
            co2_sources = pd.read_csv(co2_sources_path)
        else:
            # v4.0: 返回空DataFrame，不影响其他可视化功能
            co2_sources = pd.DataFrame(columns=["location_name", "latitude", "longitude"])

        def ensure_lat_lon(df: pd.DataFrame) -> pd.DataFrame:
            rename_map = {
                "latitude": ["γ��", "纬度", "Latitude", "lat"],
                "longitude": ["����", "经度", "Longitude", "lon"],
            }
            for target, candidates in rename_map.items():
                if target not in df.columns:
                    for cand in candidates:
                        if cand in df.columns:
                            df = df.rename(columns={cand: target})
                            break
                if target not in df.columns:
                    raise KeyError(f"数据缺少列: {target}")
                df[target] = df[target].astype(float)
            return df

        renewable = ensure_lat_lon(renewable)
        airports = ensure_lat_lon(airports)

        # ===== v4.0变更: 仅在co2_sources非空时处理坐标 =====
        if not co2_sources.empty:
            co2_sources["latitude"] = co2_sources["latitude"].astype(float)
            co2_sources["longitude"] = co2_sources["longitude"].astype(float)

        # 依据名称辨别风电/光伏
        name_col = renewable.columns[0]
        names = renewable[name_col].astype(str).str.lower()
        solar = renewable[names.str.contains("solar")].copy()
        wind = renewable[names.str.contains("wind")].copy()

        airports = airports.rename(columns={airports.columns[0]: "airport_name"})

        # ===== v4.0变更: 仅在co2_sources非空时重命名列 =====
        if not co2_sources.empty and "location_name" in co2_sources.columns:
            co2_sources = co2_sources.rename(columns={"location_name": "source_name"})

        return {
            "solar": solar,
            "wind": wind,
            "airports": airports,
            "co2": co2_sources,
        }

    def load_pipelines(self) -> Dict[str, gpd.GeoDataFrame]:
        files = {
            "crude": self.gis_data_dir / "crude_pipelines.geojson",
            "refined": self.gis_data_dir / "refined_product_pipelines.geojson",
            "natural_gas": self.gis_data_dir / "natural_gas_pipelines.geojson",
        }
        pipelines: Dict[str, gpd.GeoDataFrame] = {}
        for name, path in files.items():
            if not path.exists():
                self.logger.warning("缺少管道文件: %s", path)
                continue
            pipelines[name] = gpd.read_file(path)
        return pipelines

    def load_skipped_routes(self) -> Dict[str, List[Dict]]:
        files = sorted(self.results_dir.glob("complete_solution_*.json"))
        if not files:
            return {}
        data = json.loads(files[-1].read_text(encoding="utf-8"))
        return data.get("skipped_routes", {})

    # ------------------------------------------------------------------
    # 绘制地图
    # ------------------------------------------------------------------

    def create_base_map(self, figsize: Tuple[int, int] = (14, 10)):
        fig = plt.figure(figsize=figsize)
        ax = fig.add_subplot(projection=self.map_crs)

        min_lon, max_lon, min_lat, max_lat = self.map_extent
        try:
            fplt.set_map_ticks(ax, (min_lon, max_lon, min_lat, max_lat),
                               self.xticks, self.yticks)
            ax.gridlines(xlocs=self.xticks, ylocs=self.yticks,
                         lw=0.5, ls="--", color="gray", alpha=0.4)
            ax.tick_params(length=8, width=0.9, labelsize=10,
                           top=True, right=True, labeltop=True, labelright=True)
        except Exception:
            ax.set_xlim(min_lon, max_lon)
            ax.set_ylim(min_lat, max_lat)

        ax.set_facecolor("white")
        return fig, ax

    def scatter_layer(self, ax: plt.Axes, df: pd.DataFrame,
                      style: Dict, label: str, handles: List[Artist]):
        if df.empty:
            return
        scatter = ax.scatter(
            df["longitude"], df["latitude"],
            transform=self.data_crs,
            edgecolors="k", linewidths=0.3,
            **style,
        )
        scatter.set_label(label)
        handles.append(scatter)

    def plot_pipelines(self, ax: plt.Axes,
                       pipelines: Dict[str, gpd.GeoDataFrame],
                       handles: List[Artist]):
        for name, gdf in pipelines.items():
            if gdf.empty:
                continue
            ax.add_geometries(
                gdf["geometry"],
                crs=self.data_crs,
                facecolor="none",
                edgecolor=self.pipeline_colors.get(name, "#999999"),
                linewidth=0.6,
                alpha=0.5,
            )
            handles.append(
                mlines.Line2D(
                    [], [], color=self.pipeline_colors.get(name, "#999999"),
                    linewidth=1.2,
                    label=f"{name.replace('_', ' ').title()} pipelines",
                )
            )

    def plot_skipped_routes(
        self, ax: plt.Axes, routes: Iterable[Dict],
        color: str, label: str, handles: List[Artist],
    ) -> None:
        shown = False
        for item in routes:
            start = item.get("from_coords")
            end = item.get("to_coords")
            if not start or not end:
                continue
            start_lat, start_lon = start
            end_lat, end_lon = end
            params = dict(transform=self.data_crs, color=color,
                          linewidth=0.8, alpha=0.7)
            if not shown:
                params["label"] = label
                shown = True
            ax.plot([start_lon, end_lon], [start_lat, end_lat], **params)
        if shown:
            handles.append(
                mlines.Line2D([], [], color=color, linewidth=1.0, label=label)
            )

    def add_decorations(self, fig: plt.Figure, ax: plt.Axes):
        fplt.add_compass(ax, 0.92, 0.88, size=14, style="star")
        scale_bar = fplt.add_scale_bar(ax, 0.1, 0.08, length=200)
        scale_bar.set_xticks([0, 100, 200])
        scale_bar.xaxis.get_label().set_fontsize("small")

    # ------------------------------------------------------------------
    # 主流程
    # ------------------------------------------------------------------

    def render(self):
        points = self.load_point_layers()
        pipelines = self.load_pipelines()
        skipped = self.load_skipped_routes()

        handles: List[Artist] = []
        fig, ax = self.create_base_map()
        self.plot_pipelines(ax, pipelines, handles)

        self.scatter_layer(ax, points["solar"], self.point_styles["solar"], "Solar plants", handles)
        self.scatter_layer(ax, points["wind"], self.point_styles["wind"], "Wind farms", handles)
        self.scatter_layer(ax, points["co2"], self.point_styles["co2"], "CO₂ capture sources", handles)
        self.scatter_layer(ax, points["airports"], self.point_styles["airport"], "Airports", handles)

        self.plot_skipped_routes(ax, skipped.get("hydrogen_pipeline", []),
                                 color="#D81B60", label="Skipped H₂ routes", handles=handles)
        self.plot_skipped_routes(ax, skipped.get("co2_pipeline", []),
                                 color="#8E24AA", label="Skipped CO₂ routes", handles=handles)

        self.add_decorations(fig, ax)
        ax.legend(handles=handles, loc="upper right", fontsize=9)
        ax.set_title("Green Hydrogen Supply Chain – Pipeline Overview")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = self.fig_dir / f"pipeline_network_overview_{timestamp}.png"
        fig.savefig(output_path, dpi=300, bbox_inches="tight")
        self.logger.info("图像已保存: %s", output_path)
        return fig, ax

    def run(self):
        self.render()
        plt.show()


def main() -> None:
    visualizer = PipelineNetworkVisualizer()
    visualizer.run()


if __name__ == "__main__":
    main()
