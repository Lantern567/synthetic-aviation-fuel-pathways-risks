import os
import sys
import pytest

# 将src/visualization加入sys.path，便于导入
sys.path.append(os.path.join(os.path.dirname(__file__), '../src/visualization'))
from china_map_plot import plot_china_city_map_tianditu_style, OUTPUT_PATH

def test_plot_china_city_map_tianditu_style():
    # 删除已有图片
    if os.path.exists(OUTPUT_PATH):
        os.remove(OUTPUT_PATH)
    plot_china_city_map_tianditu_style()
    assert os.path.exists(OUTPUT_PATH), "图片未成功生成！" 