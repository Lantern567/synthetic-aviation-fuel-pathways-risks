"""
检查Excel数据文件的结构和字段名
用于诊断字段名不匹配的问题
"""

import pandas as pd
import os

def check_excel_structure(file_path):
    """检查Excel文件的结构"""
    print(f"正在检查文件: {file_path}")
    print(f"文件存在: {os.path.exists(file_path)}")
    
    if not os.path.exists(file_path):
        print("❌ 文件不存在!")
        return
    
    file_size_mb = os.path.getsize(file_path) / (1024*1024)
    print(f"文件大小: {file_size_mb:.1f} MB")
    
    try:
        # 检查所有工作表
        print(f"\n📑 检查所有工作表:")
        excel_file = pd.ExcelFile(file_path)
        print(f"工作表数量: {len(excel_file.sheet_names)}")
        
        for i, sheet_name in enumerate(excel_file.sheet_names, 1):
            print(f"\n{'='*50}")
            print(f"工作表 {i}: '{sheet_name}'")
            print(f"{'='*50}")
            
            try:
                # 读取每个工作表的前5行
                sheet_df = pd.read_excel(file_path, sheet_name=sheet_name, nrows=5)
                print(f"数据维度: {sheet_df.shape}")
                print(f"字段总数: {len(sheet_df.columns)}")
                
                # 显示前几个字段名
                print(f"\n前10个字段名:")
                for j, col in enumerate(sheet_df.columns[:10], 1):
                    print(f"  {j:2d}. '{col}' (类型: {sheet_df[col].dtype})")
                
                if len(sheet_df.columns) > 10:
                    print(f"  ... 还有 {len(sheet_df.columns) - 10} 个字段")
                
                # 检查必要字段
                print(f"\n🔍 检查必要字段:")
                required_fields = ['机型', '里程（公里）', '人数']
                found_fields = []
                for field in required_fields:
                    if field in sheet_df.columns:
                        print(f"  ✅ '{field}' - 存在")
                        found_fields.append(field)
                        # 显示该字段的一些样例数据
                        sample_values = sheet_df[field].dropna().head(3).tolist()
                        print(f"      样例值: {sample_values}")
                    else:
                        print(f"  ❌ '{field}' - 缺失")
                        # 尝试找相似的字段名
                        similar_fields = [col for col in sheet_df.columns 
                                        if any(word in col for word in field.split('（')[0].split('_'))]
                        if similar_fields:
                            print(f"      可能的相似字段: {similar_fields}")
                
                # 显示一些数据样例
                print(f"\n📊 前3行数据预览:")
                if len(sheet_df) > 0:
                    print(sheet_df.head(3).to_string())
                else:
                    print("  (无数据)")
                
                # 如果找到了必要字段，读取更多数据
                if len(found_fields) >= 2:
                    print(f"\n🎉 发现包含关键字段的工作表!")
                    try:
                        # 尝试读取总行数
                        full_sheet = pd.read_excel(file_path, sheet_name=sheet_name)
                        print(f"总行数: {len(full_sheet)}")
                        print(f"这可能是我们需要的数据工作表!")
                        
                        # 显示所有字段名
                        print(f"\n完整字段列表:")
                        for j, col in enumerate(full_sheet.columns, 1):
                            print(f"  {j:2d}. '{col}'")
                            
                    except Exception as e:
                        print(f"读取完整工作表失败: {e}")
                        
            except Exception as e:
                print(f"读取工作表 '{sheet_name}' 失败: {e}")
                
    except Exception as e:
        print(f"❌ 读取Excel文件失败: {e}")
        import traceback
        traceback.print_exc()

def main():
    """主程序"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    data_file = os.path.join(project_root, "data", "22年1月1日至24年12月31日航班数据.xlsx")
    
    print("🔍 === Excel数据文件结构检查 ===")
    check_excel_structure(data_file)

if __name__ == "__main__":
    main() 