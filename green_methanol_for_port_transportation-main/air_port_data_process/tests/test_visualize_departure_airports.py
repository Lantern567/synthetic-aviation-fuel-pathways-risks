import os
import sys
import importlib.util

def test_visualize_departure_airports():
    # 动态导入可视化脚本
    script_path = os.path.join(os.path.dirname(__file__), '../src/visualize_departure_airports.py')
    spec = importlib.util.spec_from_file_location("visualize_departure_airports", script_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)    # 检查图片是否生成
    output_path = os.path.join(os.path.dirname(__file__), '../results/figures/departure_airports.png')
    assert os.path.exists(output_path), "可视化图片未生成！"