import os
import pandas as pd
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

def test_extract_departure_airport_info():
    # 运行主脚本
    import extract_departure_airport_info
    output_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../results/tables/departure_airport_info.csv'))
    assert os.path.exists(output_path), '输出文件未生成'
    df = pd.read_csv(output_path)
    assert not df.empty, '输出文件内容为空'

if __name__ == '__main__':
    test_extract_departure_airport_info()
    print('测试通过') 