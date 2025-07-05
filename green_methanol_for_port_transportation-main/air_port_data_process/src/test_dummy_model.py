#!/usr/bin/env python3
"""
测试DUMMY模型的pyBADA功能
"""

import pyBADA.bada3 as bada3
import pyBADA.TCL as tcl
import pandas as pd

def test_dummy_model():
    """测试DUMMY模型"""
    print("=== 测试DUMMY模型 ===")
    
    try:
        # 加载DUMMY模型
        print("加载DUMMY模型...")
        aircraft = bada3.Bada3Aircraft(badaVersion="DUMMY", acName="J2M")
        print(f"✅ 成功加载飞机模型: {aircraft.acName}")
        print(f"  最大起飞重量: {aircraft.MTOW} kg")
        print(f"  空重: {aircraft.OEW} kg")
        print(f"  翼面积: {aircraft.S} m²")
        print(f"  发动机数量: {aircraft.numberOfEngines}")
        
        # 计算参考重量
        ref_mass = aircraft.MTOW * 0.8
        print(f"  参考重量: {ref_mass} kg")
        
        # 测试constantSpeedLevel函数
        print("\n测试constantSpeedLevel函数...")
        try:
            cruise_result = tcl.constantSpeedLevel(
                AC=aircraft,
                lengthType='distance',
                length=100,             # 100海里
                speedType='M',          # 马赫数
                v=0.78,                 # 马赫数0.78
                Hp_init=35000,          # 35000英尺
                m_init=60000,           # 60000kg
                DeltaTemp=0.0,          # 标准温度
                wS=0.0,                 # 无风
                stepClimb=False,
                flightPhase="Cruise"
            )
            
            if cruise_result is not None and not cruise_result.empty:
                print(f"✅ constantSpeedLevel成功")
                print(f"  返回数据形状: {cruise_result.shape}")
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
            climb_result = tcl.constantSpeedRating(
                AC=aircraft,
                speedType='CAS',
                v=250,                  # 250kt
                Hp_init=1500,           # 1500英尺
                Hp_final=35000,         # 35000英尺
                m_init=60000,           # 60000kg
                DeltaTemp=0.0,
                wS=0.0,
                turnMetrics={'rateOfTurn': 0.0, 'bankAngle': 0.0, 'directionOfTurn': None}
            )
            
            if climb_result is not None and not climb_result.empty:
                print(f"✅ constantSpeedRating成功")
                print(f"  返回数据形状: {climb_result.shape}")
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
        print(f"❌ DUMMY模型加载失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_dummy_model() 