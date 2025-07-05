"""
基于pyBADA库的航班燃油消耗计算模块（清理版）
仅使用EUROCONTROL的BADA模型进行精确的燃油消耗计算
"""

import os
import numpy as np
import pandas as pd
import math
from typing import Dict, Tuple, Optional

# pyBADA库导入
try:
    import pyBADA.bada3 as bada3
    PYBADA_AVAILABLE = True
    print("✅ pyBADA库已成功导入")
except ImportError as e:
    PYBADA_AVAILABLE = False
    print(f"❌ pyBADA库导入失败: {e}")
    raise ImportError("本模块需要pyBADA库，请先安装")

from aircraft_mapping import get_icao_code, get_aircraft_capacity, calculate_load_factor
from enhanced_fuel_calculator import haversine_distance

class PyBADAFuelCalculator:
    """
    基于pyBADA库的燃油消耗计算器（仅使用BADA模型）
    """
    
    def __init__(self):
        """初始化pyBADA燃油计算器"""
        self.bada_cache = {}  # 缓存BADA机型对象
        self.aircraft_cache = {}  # 缓存Bada3Aircraft对象
        
        if not PYBADA_AVAILABLE:
            raise ImportError("pyBADA库不可用，请安装pyBADA库")
    
    def get_bada_aircraft(self, icao_code: str) -> Optional[object]:
        """
        获取BADA机型对象
        
        Args:
            icao_code (str): ICAO机型代码
            
        Returns:
            BADA aircraft object或None
        """
        if icao_code in self.bada_cache:
            return self.bada_cache[icao_code]
        
        # 映射商用机型到BADA通用模板
        bada_template_mapping = {
            # 中型双发喷气机 (J2M___)
            'B733': 'J2M___', 'B734': 'J2M___', 'B735': 'J2M___',
            'B736': 'J2M___', 'B737': 'J2M___', 'B738': 'J2M___', 'B739': 'J2M___',
            'A319': 'J2M___', 'A320': 'J2M___', 'A321': 'J2M___',
            
            # 重型双发喷气机 (J2H___)
            'B752': 'J2H___', 'B753': 'J2H___',
            'B762': 'J2H___', 'B763': 'J2H___', 'B764': 'J2H___',
            'B772': 'J2H___', 'B773': 'J2H___', 'B777': 'J2H___', 'B778': 'J2H___',
            'B787': 'J2H___', 'B788': 'J2H___', 'B789': 'J2H___',
            'A330': 'J2H___', 'A332': 'J2H___', 'A333': 'J2H___',
            'A350': 'J2H___', 'A359': 'J2H___',
            
            # 四发重型喷气机 (J4H___)
            'B742': 'J4H___', 'B743': 'J4H___', 'B744': 'J4H___', 'B748': 'J4H___',
            'A340': 'J4H___', 'A342': 'J4H___', 'A343': 'J4H___', 'A345': 'J4H___', 'A346': 'J4H___',
            'A380': 'J4H___', 'A388': 'J4H___',
            
            # 涡轮螺旋桨 (TP2M__)
            'AT43': 'TP2M__', 'AT44': 'TP2M__', 'AT45': 'TP2M__', 'AT46': 'TP2M__',
            'AT72': 'TP2M__', 'AT73': 'TP2M__', 'AT75': 'TP2M__', 'AT76': 'TP2M__',
        }
        
        # 获取对应的BADA模板
        bada_template = bada_template_mapping.get(icao_code, 'J2M___')  # 默认为中型双发
        print(f"映射 {icao_code} → {bada_template}")
        
        try:
            # 步骤1: 创建Bada3Aircraft对象
            cache_key = f"{icao_code}_{bada_template}"
            if cache_key not in self.aircraft_cache:
                bada_aircraft = bada3.Bada3Aircraft(
                    badaVersion="DUMMY",  # 使用DUMMY版本
                    acName=bada_template, # 使用BADA模板名称
                    filePath="D:/anaconda/envs/green_methanol_for_port_transportation/Lib/site-packages/pyBADA/aircraft/BADA3/DUMMY"
                )
                self.aircraft_cache[cache_key] = bada_aircraft
                print(f"✅ 成功创建Bada3Aircraft: {bada_template}")
            else:
                bada_aircraft = self.aircraft_cache[cache_key]
            
            # 步骤2: 使用Bada3Aircraft对象创建BADA3对象
            aircraft = bada3.BADA3(bada_aircraft)
            
            if aircraft is not None:
                self.bada_cache[icao_code] = aircraft
                print(f"✅ 成功创建BADA3对象: {icao_code} ({bada_template})")
                return aircraft
            else:
                print(f"❌ BADA3对象创建失败: {icao_code}")
                return None
                
        except Exception as e:
            print(f"❌ 创建BADA对象 {icao_code} 失败: {e}")
            return None
    
    def calculate_cruise_fuel_flow(self, aircraft, altitude_ft: float, mach: float, 
                                 mass_kg: float, temperature_k: float) -> float:
        """
        使用BADA模型计算巡航燃油流量
        
        Args:
            aircraft: BADA机型对象
            altitude_ft: 高度（英尺）
            mach: 马赫数
            mass_kg: 飞机质量（公斤）
            temperature_k: 温度（开尔文）
            
        Returns:
            燃油流量（kg/s）
        """
        # 转换单位
        altitude_m = altitude_ft * 0.3048  # 英尺转米
        tas = mach * 340.294  # 真空速计算（m/s）
        
        # 使用BADA的ff方法计算燃油流量
        fuel_flow_kg_per_s = aircraft.ff(
            h=altitude_m,
            v=tas,
            T=50000,  # 巡航推力估算（牛顿）
            config='CR',  # 巡航配置
            flightPhase='Cruise'
        )
        
        print(f"✅ BADA燃油流量计算成功: {fuel_flow_kg_per_s:.4f} kg/s")
        return max(fuel_flow_kg_per_s, 0.1)  # 确保最小值
    
    def estimate_aircraft_mass(self, icao_code: str, load_factor: float) -> float:
        """
        估算飞机质量
        
        Args:
            icao_code: ICAO机型代码
            load_factor: 载客率
            
        Returns:
            飞机质量（kg）
        """
        # 机型典型重量数据（kg）
        aircraft_weights = {
            'B737': {'oew': 45000, 'mtow': 79000, 'payload': 20000},
            'B757': {'oew': 58000, 'mtow': 116000, 'payload': 23000},
            'B777': {'oew': 145000, 'mtow': 350000, 'payload': 65000},
            'B787': {'oew': 120000, 'mtow': 250000, 'payload': 45000},
            'A319': {'oew': 40000, 'mtow': 75000, 'payload': 17000},
            'A320': {'oew': 43000, 'mtow': 78000, 'payload': 18000},
            'A321': {'oew': 48000, 'mtow': 93000, 'payload': 24000},
            'A330': {'oew': 120000, 'mtow': 240000, 'payload': 50000},
            'A380': {'oew': 280000, 'mtow': 560000, 'payload': 90000},
        }
        
        weights = aircraft_weights.get(icao_code, aircraft_weights['B737'])
        
        # 估算当前质量 = 空重 + 载客率 * 最大载荷 + 燃油重量估算
        current_mass = weights['oew'] + load_factor * weights['payload'] + weights['mtow'] * 0.15
        
        return min(current_mass, weights['mtow'])
    
    def estimate_takeoff_landing_fuel(self, icao_code: str) -> float:
        """
        估算起降燃油消耗
        
        Args:
            icao_code: ICAO机型代码
            
        Returns:
            起降燃油消耗（kg）
        """
        takeoff_landing_fuel = {
            'B737': 300, 'B757': 400, 'B777': 800, 'B787': 600,
            'A319': 250, 'A320': 300, 'A321': 350, 'A330': 700, 'A380': 1200,
        }
        return takeoff_landing_fuel.get(icao_code, 300)
    
    def calculate_flight_fuel_consumption(self, chinese_aircraft: str, distance_km: float, 
                                        passengers: int, cruise_altitude_ft: float = 35000,
                                        cruise_mach: float = 0.8, temperature_k: float = 220.0) -> Dict:
        """
        使用pyBADA计算航班燃油消耗
        
        Args:
            chinese_aircraft: 中文机型名称
            distance_km: 飞行距离（公里）
            passengers: 载客数
            cruise_altitude_ft: 巡航高度（英尺）
            cruise_mach: 巡航马赫数
            temperature_k: 巡航温度（开尔文）
            
        Returns:
            包含燃油消耗信息的字典
        """
        # 1. 机型映射
        icao_code = get_icao_code(chinese_aircraft)
        
        # 2. 载客率计算
        load_factor = calculate_load_factor(passengers, icao_code)
        
        # 3. 获取BADA机型对象
        aircraft = self.get_bada_aircraft(icao_code)
        
        if aircraft is None:
            raise ValueError(f"无法创建BADA对象用于机型: {icao_code}")
        
        # 4. 估算飞机质量
        aircraft_mass = self.estimate_aircraft_mass(icao_code, load_factor)
        
        # 5. 计算巡航时间
        cruise_speed_kmh = cruise_mach * 1225  # 马赫数转km/h（近似）
        cruise_time_hours = distance_km / cruise_speed_kmh
        
        # 6. 使用BADA计算燃油流量
        fuel_flow_kg_per_s = self.calculate_cruise_fuel_flow(
            aircraft, cruise_altitude_ft, cruise_mach, aircraft_mass, temperature_k
        )
        
        # 7. 计算总燃油消耗
        cruise_fuel_kg = fuel_flow_kg_per_s * cruise_time_hours * 3600  # 巡航燃油
        takeoff_landing_fuel = self.estimate_takeoff_landing_fuel(icao_code)  # 起降燃油
        total_fuel_kg = cruise_fuel_kg + takeoff_landing_fuel
        
        print(f"✅ BADA计算完成: {icao_code}, 燃油: {total_fuel_kg:.2f}kg")
        
        return {
            'icao_code': icao_code,
            'fuel_consumption_kg': round(total_fuel_kg, 2),
            'fuel_flow_kg_per_s': round(fuel_flow_kg_per_s, 4),
            'cruise_time_hours': round(cruise_time_hours, 3),
            'aircraft_mass_kg': round(aircraft_mass, 0),
            'load_factor': round(load_factor, 3),
            'calculation_method': 'pybada'
        }

def process_flight_data_with_pybada(df: pd.DataFrame, sample_size: Optional[int] = None) -> pd.DataFrame:
    """
    使用pyBADA处理航班数据（仅BADA计算）
    
    Args:
        df: 航班数据DataFrame
        sample_size: 处理的样本数量，None表示全部处理
        
    Returns:
        处理后的DataFrame
    """
    if sample_size:
        df = df.head(sample_size).copy()
    else:
        df = df.copy()
    
    calculator = PyBADAFuelCalculator()
    
    # 添加新字段
    df['ICAO代码'] = ''
    df['载客率'] = 0.0
    df['燃油消耗_kg'] = 0.0
    df['燃油流量_kg_per_s'] = 0.0
    df['巡航时间_hours'] = 0.0
    df['计算方法'] = 'pybada'
    
    print(f"开始使用pyBADA处理 {len(df)} 条航班数据...")
    
    success_count = 0
    
    for idx, row in df.iterrows():
        try:
            # 获取基础数据
            chinese_aircraft = str(row['机型']).strip()
            distance_km = float(row['里程（公里）'])
            passengers = int(row['人数'])
            
            # 使用pyBADA计算
            result = calculator.calculate_flight_fuel_consumption(
                chinese_aircraft, distance_km, passengers
            )
            
            # 更新DataFrame
            df.at[idx, 'ICAO代码'] = result['icao_code']
            df.at[idx, '载客率'] = result['load_factor']
            df.at[idx, '燃油消耗_kg'] = result['fuel_consumption_kg']
            df.at[idx, '燃油流量_kg_per_s'] = result['fuel_flow_kg_per_s']
            df.at[idx, '巡航时间_hours'] = result['cruise_time_hours']
            df.at[idx, '计算方法'] = result['calculation_method']
            
            success_count += 1
            
        except Exception as e:
            print(f"❌ 处理航班数据失败 (第{idx+1}行): {e}")
            df.at[idx, '计算方法'] = 'failed'
    
    print(f"处理完成: {success_count}/{len(df)} 条记录成功")
    return df

def demo_pybada_calculation():
    """演示pyBADA计算"""
    calculator = PyBADAFuelCalculator()
    
    # 测试案例
    test_cases = [
        {"aircraft": "波音737(中)", "distance": 3049, "passengers": 150},
        {"aircraft": "空客320", "distance": 1500, "passengers": 120},
        {"aircraft": "波音777", "distance": 8000, "passengers": 250},
    ]
    
    print("=== pyBADA燃油计算演示 ===")
    
    for i, case in enumerate(test_cases, 1):
        print(f"\n测试案例 {i}:")
        print(f"机型: {case['aircraft']}")
        print(f"距离: {case['distance']} km")
        print(f"载客: {case['passengers']} 人")
        
        try:
            result = calculator.calculate_flight_fuel_consumption(
                case['aircraft'], case['distance'], case['passengers']
            )
            
            print(f"结果:")
            print(f"  ICAO代码: {result['icao_code']}")
            print(f"  燃油消耗: {result['fuel_consumption_kg']} kg")
            print(f"  燃油流量: {result['fuel_flow_kg_per_s']} kg/s")
            print(f"  巡航时间: {result['cruise_time_hours']} 小时")
            print(f"  载客率: {result['load_factor']:.1%}")
            
        except Exception as e:
            print(f"❌ 计算失败: {e}")

if __name__ == "__main__":
    demo_pybada_calculation() 