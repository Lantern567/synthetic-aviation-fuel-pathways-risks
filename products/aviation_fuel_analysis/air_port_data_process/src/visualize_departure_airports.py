import matplotlib.pyplot as plt
import numpy as np
from cartopy.feature import LAND, RIVERS
from scipy.ndimage import gaussian_filter
import frykit.plot as fplt
import os
import pandas as pd
import matplotlib

# 设置全局字体为微软雅黑
matplotlib.rcParams['font.sans-serif'] = ['Microsoft YaHei']
matplotlib.rcParams['axes.unicode_minus'] = False

# 读取航班数据
excel_path = os.path.join(os.path.dirname(__file__), '../data/22年1月1日至24年12月31日航班数据.xlsx')
df = pd.read_excel(excel_path)

# 提取起飞机场及其坐标，去重（只按机场名和坐标去重）
airports = df[['起飞机场', '起飞机场y', '起飞机场x']].drop_duplicates()

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
for ax in [main_ax, mini_ax]:
    ax.set_facecolor("skyblue")
    ax.add_feature(LAND, fc="floralwhite", ec="k", lw=0.5)
    fplt.add_cn_city(ax, lw=0.2, edgecolor='lightgreen', linestyle='--', zorder=2)
    fplt.add_cn_line(ax, lw=1.2, edgecolor='dimgray', zorder=2.5)
    fplt.add_cn_border(ax, lw=0.75, edgecolor='black', zorder=3)

# 绘制所有起飞机场点
sc = main_ax.scatter(airports['起飞机场x'], airports['起飞机场y'], color='red', s=15, marker='o', transform=data_crs, zorder=10, label='起飞机场')
# 小地图内的点
mini_airports = airports[(airports['起飞机场x'] >= 105) & (airports['起飞机场x'] <= 122) & (airports['起飞机场y'] >= 2) & (airports['起飞机场y'] <= 25)]
mini_ax.scatter(mini_airports['起飞机场x'], mini_airports['起飞机场y'], color='red', s=8, marker='o', transform=data_crs, zorder=10)

# 添加图例
main_ax.legend(loc='lower left', fontsize=8)

# 添加指北针和比例尺
fplt.add_compass(main_ax, 0.92, 0.85, size=15, style="star")
scale_bar = fplt.add_scale_bar(main_ax, 0.05, 0.95, length=1000)
scale_bar.set_xticks([0, 500, 1000])
scale_bar.xaxis.get_label().set_fontsize("small")
# 小地图比例尺
scale_bar2 = fplt.add_scale_bar(mini_ax, 0.4, 0.15, length=500)
scale_bar2.set_xticks([0, 500])
scale_bar2.xaxis.get_label().set_fontsize("small")

# 交互注释功能已禁用（在非GUI环境中运行）

# 确保保存路径存在
output_path = os.path.join(os.path.dirname(__file__), '../results/figures/departure_airports.png')
os.makedirs(os.path.dirname(output_path), exist_ok=True)
# 保存图像
fplt.savefig(output_path)
plt.close(fig)