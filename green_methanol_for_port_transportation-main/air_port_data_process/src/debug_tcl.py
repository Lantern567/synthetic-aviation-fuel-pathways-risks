#!/usr/bin/env python3
"""
调试pyBADA TCL函数调用
"""

import pyBADA.bada3 as bada3
import pyBADA.TCL as tcl
import pandas as pd

def test_tcl_functions():
    """测试TCL函数的正确调用方式"""
    print("=== 测试pyBADA TCL函数 ===")
    
    try:
        # 加载飞机模型
        print("加载飞机模型...")
        aircraft = bada3.Bada3Aircraft(badaVersion="BADA3", acName="A320")
        print(f"✅ 成功加载飞机模型: {aircraft.acName}")
        
        # 测试constantSpeedLevel函数
        print("\n测试constantSpeedLevel函数...")
        try:
            # 根据文档，正确的参数顺序应该是：
            # AC, lengthType, length, speedType, v, Hp_init, m_init, DeltaTemp, [其他可选参数]
            cruise_result = tcl.constantSpeedLevel(
                AC=aircraft,
                lengthType='distance',  # 'distance' 或 'time'
                length=100,             # 距离（海里）
                speedType='M',          # 速度类型：'M', 'CAS', 'TAS'
                v=0.78,                 # 马赫数
                Hp_init=35000,          # 初始高度（英尺）
                m_init=70000,           # 初始质量（kg）
                DeltaTemp=0.0,          # 温度偏差（K）
                wS=0.0,                 # 风速（kt）
                stepClimb=False,        # 是否阶梯爬升
                flightPhase="Cruise"    # 飞行阶段
            )
            
            if cruise_result is not None and not cruise_result.empty:
                print(f"✅ constantSpeedLevel成功")
                print(f"  返回数据形状: {cruise_result.shape}")
                print(f"  列名: {list(cruise_result.columns)}")
                print(f"  燃油消耗: {cruise_result['FUELCONSUMED'].iloc[-1]:.1f} kg")
                print(f"  飞行时间: {cruise_result['time'].iloc[-1]:.1f} s")
                print(f"  飞行距离: {cruise_result['dist'].iloc[-1]:.1f} NM")
            else:
                print("❌ constantSpeedLevel返回空结果")
                
        except Exception as e:
            print(f"❌ constantSpeedLevel失败: {e}")
            import traceback
            traceback.print_exc()
        
        # 测试constantSpeedRating函数
        print("\n测试constantSpeedRating函数...")
        try:
            # 根据文档，正确的参数顺序应该是：
            # AC, speedType, v, Hp_init, Hp_final, m_init, DeltaTemp, [其他可选参数]
            climb_result = tcl.constantSpeedRating(
                AC=aircraft,
                speedType='CAS',        # 速度类型
                v=250,                  # 校准空速（kt）
                Hp_init=1500,           # 初始高度（ft）
                Hp_final=35000,         # 最终高度（ft）
                m_init=70000,           # 初始质量（kg）
                DeltaTemp=0.0,          # 温度偏差（K）
                wS=0.0,                 # 风速（kt）
                turnMetrics={'rateOfTurn': 0.0, 'bankAngle': 0.0, 'directionOfTurn': None}
            )
            
            if climb_result is not None and not climb_result.empty:
                print(f"✅ constantSpeedRating成功")
                print(f"  返回数据形状: {climb_result.shape}")
                print(f"  列名: {list(climb_result.columns)}")
                print(f"  燃油消耗: {climb_result['FUELCONSUMED'].iloc[-1]:.1f} kg")
                print(f"  飞行时间: {climb_result['time'].iloc[-1]:.1f} s")
                print(f"  飞行距离: {climb_result['dist'].iloc[-1]:.1f} NM")
            else:
                print("❌ constantSpeedRating返回空结果")
                
        except Exception as e:
            print(f"❌ constantSpeedRating失败: {e}")
            import traceback
            traceback.print_exc()
            
    except Exception as e:
        print(f"❌ 飞机模型加载失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_tcl_functions() 