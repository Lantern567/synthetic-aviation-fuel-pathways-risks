"""
批量删除天然气相关代码的脚本
"""

def delete_lines_from_file(file_path, lines_to_delete):
    """
    从文件中删除指定行

    Args:
        file_path: 文件路径
        lines_to_delete: 要删除的行号列表，格式为 [(start1, end1), (start2, end2), ...]
    """
    # 读取文件
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # 创建要保留的行集合
    lines_to_keep = set(range(len(lines)))

    # 移除要删除的行（注意：行号从1开始，但列表索引从0开始）
    for start, end in lines_to_delete:
        for line_num in range(start - 1, end):  # 转换为0-based index
            if line_num in lines_to_keep:
                lines_to_keep.remove(line_num)

    # 保留的行
    new_lines = [lines[i] for i in sorted(lines_to_keep)]

    # 写回文件
    with open(file_path, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)

    total_deleted = sum(end - start + 1 for start, end in lines_to_delete)
    print(f"✅ 成功删除 {total_deleted} 行代码")
    print(f"📝 文件原有 {len(lines)} 行，现有 {len(new_lines)} 行")


if __name__ == "__main__":
    file_path = r"D:\Green methanol\green_methanol_for_port_transportation-main\green_methanol_for_port_transportation-main\products\supply_chain_optimization\green_hydrogen_supply_chain_optimization\src\core\green_hydrogen_optimization_model.py"

    # 定义要删除的行范围
    lines_to_delete = [
        # 1. 天然气位置处理方法
        (767, 844),  # _add_lng_terminals_to_locations 和 _add_ng_pipelines_to_locations

        # 2. 天然气约束方法
        (3283, 3336),  # _add_ng_pipeline_flow_constraints
        (3337, 3353),  # _add_ng_storage_flow_constraints
        (3967, 4058),  # _add_natural_gas_transport_constraints
        (6930, 6979),  # _add_simplified_ng_pipeline_constraints
        (6980, 7054),  # _add_ng_pipeline_daily_capacity_constraints
        (7055, 7120),  # _add_lng_terminal_daily_capacity_constraints (估计)

        # 3. 天然气成本计算方法
        (4131, 4139),  # _calculate_total_ng_transport_cost_per_kg_km
        (4251, 4283),  # _calculate_ng_transport_cost_by_distance
        (4284, 4303),  # _get_ng_transport_unit_cost
        (4304, 4331),  # _estimate_ng_daily_volume_for_route

        # 4. 天然气数据加载方法
        (6070, 6195),  # _load_ng_pipeline_data
        (6196, 6248),  # _load_and_filter_ng_pipeline_data
        (6249, 6309),  # _load_original_pipeline_data
        (6310, 6439),  # _load_lng_terminal_data
        (6540, 6587),  # _load_and_filter_lng_data

        # 5. 天然气供应链分析方法
        (6687, 6735),  # _analyze_natural_gas_supply_for_location
        (6736, 6800),  # _get_natural_gas_price_yuan_per_m3 (估计)
    ]

    print("开始清理天然气代码...")
    print(f"目标文件: {file_path}")
    print(f"计划删除 {len(lines_to_delete)} 个代码段")

    delete_lines_from_file(file_path, lines_to_delete)

    print("清理完成！")
