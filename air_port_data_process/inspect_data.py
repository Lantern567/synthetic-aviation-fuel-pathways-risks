"""
检查航班数据文件的结构
"""

import pandas as pd
import os

def inspect_flight_data():
    """检查航班数据文件"""
    data_file = 'data/22年1月1日至24年12月31日航班数据.xlsx'
    
    if not os.path.exists(data_file):
        print(f"❌ 数据文件不存在: {data_file}")
        return
    
    print(f"📊 检查数据文件: {data_file}")
    print(f"文件大小: {os.path.getsize(data_file) / (1024*1024):.1f} MB")
    
    try:
        # 只读取前几行来检查结构
        print("\n正在读取数据样本...")
        df_sample = pd.read_excel(data_file, nrows=10)
        
        print(f"\n✅ 数据读取成功")
        print(f"样本数据形状: {df_sample.shape}")
        
        print(f"\n📋 列名 ({len(df_sample.columns)}个):")
        for i, col in enumerate(df_sample.columns, 1):
            print(f"{i:2d}. {col}")
        
        print(f"\n📄 前5行数据:")
        print(df_sample.head().to_string())
        
        # 检查关键字段
        required_fields = ['机型', '里程（公里）', '人数']
        print(f"\n🔍 检查关键字段:")
        for field in required_fields:
            if field in df_sample.columns:
                print(f"✅ {field} - 存在")
                # 显示一些样本值
                sample_values = df_sample[field].dropna().head(3).tolist()
                print(f"   样本值: {sample_values}")
            else:
                print(f"❌ {field} - 缺失")
        
        # 检查可能的替代字段名
        all_columns = df_sample.columns.tolist()
        print(f"\n🔍 寻找相似字段:")
        
        # 寻找包含"机型"的字段
        aircraft_cols = [col for col in all_columns if '机型' in str(col) or '飞机' in str(col) or '型号' in str(col)]
        if aircraft_cols:
            print(f"机型相关字段: {aircraft_cols}")
        
        # 寻找包含"里程"或"距离"的字段
        distance_cols = [col for col in all_columns if '里程' in str(col) or '距离' in str(col) or '公里' in str(col)]
        if distance_cols:
            print(f"里程相关字段: {distance_cols}")
        
        # 寻找包含"人数"或"乘客"的字段
        passenger_cols = [col for col in all_columns if '人数' in str(col) or '乘客' in str(col) or '客' in str(col)]
        if passenger_cols:
            print(f"人数相关字段: {passenger_cols}")
        
        # 尝试读取全部数据获取总数（可能会很慢）
        print(f"\n📊 尝试获取总记录数...")
        try:
            # 使用更快的方法获取行数
            total_rows = sum(1 for _ in pd.read_excel(data_file, chunksize=1000))
            print(f"总记录数: 约 {total_rows * 1000:,} 条")
        except:
            print("⚠️ 无法快速获取总记录数，文件较大")
        
    except Exception as e:
        print(f"❌ 读取数据失败: {e}")

if __name__ == "__main__":
    inspect_flight_data() 