import matplotlib.pyplot as plt
import numpy as np
from cartopy.feature import LAND, RIVERS
from scipy.ndimage import gaussian_filter
import frykit.plot as fplt
import os
import pandas as pd
import re
import matplotlib

# 设置全局字体为微软雅黑
matplotlib.rcParams['font.sans-serif'] = ['Microsoft YaHei']
matplotlib.rcParams['axes.unicode_minus'] = False

# 读取数据
data = fplt.load_test_data()
X, Y = np.meshgrid(data["longitude"], data["latitude"])
Z = gaussian_filter(data["t2m"] - 273.15, sigma=1)

# 设置投影
map_crs = fplt.CN_AZIMUTHAL_EQUIDISTANT
data_crs = fplt.PLATE_CARREE

# 设置刻度
xticks = np.arange(-180, 181, 10)
yticks = np.arange(-90, 91, 10)

# 准备大地图
fig = plt.figure(figsize=(10, 6))
main_ax = fig.add_subplot(projection=map_crs)
fplt.set_map_ticks(main_ax, (74, 136, 13, 57), xticks, yticks)
main_ax.gridlines(xlocs=xticks, ylocs=yticks, lw=0.5, ls="--", color="gray")

# 类似 NCL 的刻度风格
main_ax.tick_params(
    length=8,
    width=0.9,
    labelsize=8,
    top=True,
    right=True,
    labeltop=True,
    labelright=True,
)

# 准备小地图
mini_ax = fplt.add_mini_axes(main_ax)
mini_ax.set_extent((105, 122, 2, 25), data_crs)
mini_ax.gridlines(xlocs=xticks, ylocs=yticks, lw=0.5, ls="--", color="gray")

# 添加要素
land = LAND.with_scale("50m")
for ax in [main_ax, mini_ax]:
    ax.set_facecolor("skyblue")
    ax.add_feature(LAND, fc="floralwhite", ec="k", lw=0.5)
    ax.add_feature(RIVERS.with_scale("50m"), edgecolor='royalblue', lw=0.6, zorder=2.2)  # 河流
    fplt.add_cn_city(ax, lw=0.2, edgecolor='lightgreen', linestyle='--', zorder=2)  # 市界浅绿色虚线
    fplt.add_cn_line(ax, lw=1.2, edgecolor='dimgray', zorder=2.5)  # 九段线，深灰色
    fplt.add_cn_border(ax, lw=0.75, edgecolor='black', zorder=3)  # 国界黑色，线宽减半

# 不再绘制任何contourf热力涂色

# 大地图添加指北针和比例尺（比例尺在左上角）
fplt.add_compass(main_ax, 0.92, 0.85, size=15, style="star")
scale_bar = fplt.add_scale_bar(main_ax, 0.05, 0.95, length=1000)
scale_bar.set_xticks([0, 500, 1000])
scale_bar.xaxis.get_label().set_fontsize("small")

# 小地图添加比例尺
scale_bar = fplt.add_scale_bar(mini_ax, 0.4, 0.15, length=500)
scale_bar.set_xticks([0, 500])
scale_bar.xaxis.get_label().set_fontsize("small")

# 交互式港口点收集
port_points = []  # (lon, lat, name, scatter_obj)
excel_path = os.path.join(os.path.dirname(__file__), '../../data/reserach_port.xlsx')
def dms_to_dd(dms_str):
    """将如38°50′N, 118°21′E格式转为(纬度, 经度)十进制度"""
    lat_str, lon_str = dms_str.split(',')
    def parse_one(s):
        m = re.match(r'(\d+)°(\d+)[′\u0019\u001b\u001a\u0018\u001c\u001d\u001e\u001f]([NSWE])', s.strip())
        if not m:
            return None
        deg, minute, direction = int(m.group(1)), int(m.group(2)), m.group(3)
        val = deg + minute/60
        if direction in 'SW':
            val = -val
        return val
    lat = parse_one(lat_str)
    lon = parse_one(lon_str)
    return lat, lon

if os.path.exists(excel_path):
    df = pd.read_excel(excel_path)
    # 兼容新表头，去除空格和换行
    df.columns = [c.strip() for c in df.columns]
    # 定义颜色和符号映射
    type_style = {
        '干散货-发出港':  {'color': 'red',    'marker': 'o', 'label': '干散货-发出港'},
        '干散货-到达港': {'color': 'blue',   'marker': 's', 'label': '干散货-到达港'},
        '集装箱研究港口': {'color': 'green',  'marker': '^', 'label': '集装箱研究港口'},
    }
    legend_handles = {}
    for _, row in df.iterrows():
        name = row['港口名称']
        coord = row['坐标 (纬度, 经度)']
        port_type = row['研究类型']
        style = type_style.get(port_type, {'color': 'gray', 'marker': 'o', 'label': port_type})
        try:
            lat, lon = dms_to_dd(coord)
        except Exception:
            continue
        # 主图标记（不显示文字，后续交互显示）
        sc = main_ax.scatter(lon, lat, color=style['color'], s=15, marker=style['marker'], transform=data_crs, zorder=10, picker=True, label=style['label'])
        port_points.append((lon, lat, name, sc))
        if style['label'] not in legend_handles:
            legend_handles[style['label']] = sc
        # 小图标记（不显示文字）
        if 105 <= lon <= 122 and 2 <= lat <= 25:
            mini_ax.scatter(lon, lat, color=style['color'], s=8, marker=style['marker'], transform=data_crs, zorder=10)
    # 添加图例
    main_ax.legend(legend_handles.values(), legend_handles.keys(), loc='lower left', fontsize=8, title='研究类型')

# 交互：点击点显示港口名称
annot = main_ax.annotate("", xy=(0,0), xytext=(10,10), textcoords="offset points",
                        bbox=dict(boxstyle="round", fc="w"), arrowprops=dict(arrowstyle="->"), fontsize=9)
annot.set_visible(False)

def on_pick(event):
    for lon, lat, name, sc in port_points:
        if event.artist == sc:
            annot.xy = (event.mouseevent.xdata, event.mouseevent.ydata)
            annot.set_text(name)
            annot.set_visible(True)
            fig.canvas.draw_idle()
            return
    annot.set_visible(False)
    fig.canvas.draw_idle()

fig.canvas.mpl_connect("pick_event", on_pick)

# 保存图片（不显示任何港口名称）
output_path = os.path.join(os.path.dirname(__file__), '../../results/figures/contourf_city.png')
# 关闭注释显示，确保保存时无名称
if 'annot' in locals():
    annot.set_visible(False)
fplt.savefig(output_path)
plt.close(fig)

OUTPUT_PATH = os.path.join(os.path.dirname(__file__), '../../results/figures/contourf_city.png')

def plot_china_city_map_tianditu_style():
    # 设置全局字体为微软雅黑
    matplotlib.rcParams['font.sans-serif'] = ['Microsoft YaHei']
    matplotlib.rcParams['axes.unicode_minus'] = False

    # 读取数据
    data = fplt.load_test_data()
    X, Y = np.meshgrid(data["longitude"], data["latitude"])
    Z = gaussian_filter(data["t2m"] - 273.15, sigma=1)

    # 设置投影
    map_crs = fplt.CN_AZIMUTHAL_EQUIDISTANT
    data_crs = fplt.PLATE_CARREE

    # 设置刻度
    xticks = np.arange(-180, 181, 10)
    yticks = np.arange(-90, 91, 10)

    # 准备大地图
    fig = plt.figure(figsize=(10, 6))
    main_ax = fig.add_subplot(projection=map_crs)
    fplt.set_map_ticks(main_ax, (74, 136, 13, 57), xticks, yticks)
    main_ax.gridlines(xlocs=xticks, ylocs=yticks, lw=0.5, ls="--", color="gray")

    # 类似 NCL 的刻度风格
    main_ax.tick_params(
        length=8,
        width=0.9,
        labelsize=8,
        top=True,
        right=True,
        labeltop=True,
        labelright=True,
    )

    # 准备小地图
    mini_ax = fplt.add_mini_axes(main_ax)
    mini_ax.set_extent((105, 122, 2, 25), data_crs)
    mini_ax.gridlines(xlocs=xticks, ylocs=yticks, lw=0.5, ls="--", color="gray")

    # 添加要素
    land = LAND.with_scale("50m")
    for ax in [main_ax, mini_ax]:
        ax.set_facecolor("skyblue")
        ax.add_feature(LAND, fc="floralwhite", ec="k", lw=0.5)
        ax.add_feature(RIVERS.with_scale("50m"), edgecolor='royalblue', lw=0.6, zorder=2.2)  # 河流
        fplt.add_cn_city(ax, lw=0.2, edgecolor='lightgreen', linestyle='--', zorder=2)  # 市界浅绿色虚线
        fplt.add_cn_line(ax, lw=1.2, edgecolor='dimgray', zorder=2.5)  # 九段线，深灰色
        fplt.add_cn_border(ax, lw=0.75, edgecolor='black', zorder=3)  # 国界黑色，线宽减半

    # 不再绘制任何contourf热力涂色

    # 大地图添加指北针和比例尺（比例尺在左上角）
    fplt.add_compass(main_ax, 0.92, 0.85, size=15, style="star")
    scale_bar = fplt.add_scale_bar(main_ax, 0.05, 0.95, length=1000)
    scale_bar.set_xticks([0, 500, 1000])
    scale_bar.xaxis.get_label().set_fontsize("small")

    # 小地图添加比例尺
    scale_bar = fplt.add_scale_bar(mini_ax, 0.4, 0.15, length=500)
    scale_bar.set_xticks([0, 500])
    scale_bar.xaxis.get_label().set_fontsize("small")

    # 交互式港口点收集
    port_points = []  # (lon, lat, name, scatter_obj)
    excel_path = os.path.join(os.path.dirname(__file__), '../../data/reserach_port.xlsx')
    def dms_to_dd(dms_str):
        """将如38°50′N, 118°21′E格式转为(纬度, 经度)十进制度"""
        lat_str, lon_str = dms_str.split(',')
        def parse_one(s):
            m = re.match(r'(\d+)°(\d+)[′\u0019\u001b\u001a\u0018\u001c\u001d\u001e\u001f]([NSWE])', s.strip())
            if not m:
                return None
            deg, minute, direction = int(m.group(1)), int(m.group(2)), m.group(3)
            val = deg + minute/60
            if direction in 'SW':
                val = -val
            return val
        lat = parse_one(lat_str)
        lon = parse_one(lon_str)
        return lat, lon

    if os.path.exists(excel_path):
        df = pd.read_excel(excel_path)
        # 兼容新表头，去除空格和换行
        df.columns = [c.strip() for c in df.columns]
        # 定义颜色和符号映射
        type_style = {
            '干散货-发出港':  {'color': 'red',    'marker': 'o', 'label': '干散货-发出港'},
            '干散货-到达港': {'color': 'blue',   'marker': 's', 'label': '干散货-到达港'},
            '集装箱研究港口': {'color': 'green',  'marker': '^', 'label': '集装箱研究港口'},
        }
        legend_handles = {}
        for _, row in df.iterrows():
            name = row['港口名称']
            coord = row['坐标 (纬度, 经度)']
            port_type = row['研究类型']
            style = type_style.get(port_type, {'color': 'gray', 'marker': 'o', 'label': port_type})
            try:
                lat, lon = dms_to_dd(coord)
            except Exception:
                continue
            # 主图标记（不显示文字，后续交互显示）
            sc = main_ax.scatter(lon, lat, color=style['color'], s=15, marker=style['marker'], transform=data_crs, zorder=10, picker=True, label=style['label'])
            port_points.append((lon, lat, name, sc))
            if style['label'] not in legend_handles:
                legend_handles[style['label']] = sc
            # 小图标记（不显示文字）
            if 105 <= lon <= 122 and 2 <= lat <= 25:
                mini_ax.scatter(lon, lat, color=style['color'], s=8, marker=style['marker'], transform=data_crs, zorder=10)
        # 添加图例
        main_ax.legend(legend_handles.values(), legend_handles.keys(), loc='lower left', fontsize=8, title='研究类型')

    # 交互：点击点显示港口名称
    annot = main_ax.annotate("", xy=(0,0), xytext=(10,10), textcoords="offset points",
                            bbox=dict(boxstyle="round", fc="w"), arrowprops=dict(arrowstyle="->"), fontsize=9)
    annot.set_visible(False)

    def on_pick(event):
        for lon, lat, name, sc in port_points:
            if event.artist == sc:
                annot.xy = (event.mouseevent.xdata, event.mouseevent.ydata)
                annot.set_text(name)
                annot.set_visible(True)
                fig.canvas.draw_idle()
                return
        annot.set_visible(False)
        fig.canvas.draw_idle()

    fig.canvas.mpl_connect("pick_event", on_pick)

    # 保存图片（不显示任何港口名称）
    if 'annot' in locals():
        annot.set_visible(False)
    fplt.savefig(OUTPUT_PATH)
    plt.close(fig)
