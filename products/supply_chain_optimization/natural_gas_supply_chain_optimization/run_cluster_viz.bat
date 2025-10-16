@echo off
chcp 65001
python test_clustering_visualization.py > cluster_viz_output.txt 2>&1
type cluster_viz_output.txt