"""
检查Excel文件中所有工作表的结构
"""

import pandas as pd
import os

def main():
    """主程序"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    data_file = os.path.join(project_root, "data", "22年1月1日至24年12月31日航班数据.xlsx")
    
    print("🔍 === 检查所有工作表 ===")
    print(f"文件: {data_file}")
    
    try:
        # 检查所有工作表
        excel_file = pd.ExcelFile(data_file)
        print(f"工作表数量: {len(excel_file.sheet_names)}")
        
        for i, sheet_name in enumerate(excel_file.sheet_names, 1):
            print(f"\n{'='*60}")
            print(f"工作表 {i}: '{sheet_name}'")
            print(f"{'='*60}")
            
            try:
                # 先检查总行数
                temp_df = pd.read_excel(data_file, sheet_name=sheet_name)
                total_rows = len(temp_df)
                total_cols = len(temp_df.columns)
                print(f"总行数: {total_rows:,}, 总列数: {total_cols}")
                
                if total_rows == 0:
                    print("⚠️  空工作表")
                    continue
                
                # 读取前5行检查结构
                sheet_df = pd.read_excel(data_file, sheet_name=sheet_name, nrows=min(5, total_rows))
                
                # 显示前10个字段名
                print(f"\n前10个字段名:")
                for j, col in enumerate(sheet_df.columns[:10], 1):
                    sample_data = sheet_df[col].dropna().tolist()[:2]
                    print(f"  {j:2d}. '{col}' - 样例: {sample_data}")
                
                if len(sheet_df.columns) > 10:
                    print(f"  ... 还有 {len(sheet_df.columns) - 10} 个字段")
                
                # 检查关键字段
                required_fields = ['机型', '里程（公里）', '人数']
                found_any = False
                for field in required_fields:
                    if field in sheet_df.columns:
                        print(f"  ✅ 发现关键字段: '{field}'")
                        found_any = True
                
                # 如果找到关键字段，显示完整字段列表
                if found_any:
                    print(f"\n🎉 这是包含航班数据的工作表!")
                    print(f"完整字段列表:")
                    for j, col in enumerate(temp_df.columns, 1):
                        print(f"  {j:2d}. '{col}'")
                    break  # 找到了就停止
                
            except Exception as e:
                print(f"❌ 读取工作表失败: {e}")
                
    except Exception as e:
        print(f"❌ 处理失败: {e}")

if __name__ == "__main__":
    main() 