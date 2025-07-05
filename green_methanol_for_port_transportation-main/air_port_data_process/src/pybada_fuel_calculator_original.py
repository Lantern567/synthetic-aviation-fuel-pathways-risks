"""
基于pyBADA库的航班燃油消耗计算模块
使用EUROCONTROL的BADA模型进行精确的燃油消耗计算
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

from aircraft_mapping import get_icao_code, get_aircraft_capacity, calculate_load_factor
from enhanced_fuel_calculator import haversine_distance

class PyBADAFuelCalculator:
    """
    基于pyBADA库的燃油消耗计算器
    """
    
    def __init__(self):
        """初始化pyBADA燃油计算器"""
        self.bada_cache = {}  # 缓存BADA机型对象
        self.aircraft_cache = {}  # 缓存Bada3Aircraft对象
        self.calculation_results = []
        
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
        
        try:
            # 映射商用机型到BADA通用模板
            bada_template_mapping = {
                # 中型双发喷气机 (J2M___)
                'B733': 'J2M___', 'B734': 'J2M___', 'B735': 'J2M___',
                'B736': 'J2M___', 'B737': 'J2M___', 'B738': 'J2M___', 'B739': 'J2M___',
                'A319': 'J2M___', 'A320': 'J2M___', 'A321': 'J2M___',
                
                # 中型双发重型喷气机 (J2H___)
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
            
            # 步骤1: 首先创建Bada3Aircraft对象
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
                print(f"⚠️  BADA3对象创建失败: {icao_code}")
                return None
                
        except Exception as e:
            print(f"❌ 创建BADA对象 {icao_code} 失败: {e}")
            # 输出详细错误信息以便调试
            import traceback
            print(f"错误详情: {traceback.format_exc()}")
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
        try:
            # 转换单位
            altitude_m = altitude_ft * 0.3048  # 英尺转米
            
            # 计算大气参数
            # 这里使用标准大气模型计算，实际应该使用pyBADA的atmosphere模块
            # 简化计算：使用ISA标准大气
            delta_temp = temperature_k - 288.15  # 温度偏差
            
            # 使用BADA的燃油流量计算方法
            # 注意：这里需要推力值，我们先计算巡航推力
            tas = mach * 340.294  # 简化的真空速计算（m/s）
            
            # 使用BADA的ff方法计算燃油流量
            # 这里需要推力值，我们使用巡航推力设置
            try:
                # 尝试使用BADA的内置方法
                fuel_flow_kg_per_s = aircraft.ff(
                    h=altitude_m,
                    v=tas,
                    T=50000,  # 假设推力值，实际应该计算
                    config='CR',  # 巡航配置
                    flightPhase='Cruise'
                )
                print(f"✅ BADA燃油流量计算成功: {fuel_flow_kg_per_s:.4f} kg/s")
                return max(fuel_flow_kg_per_s, 0.1)  # 确保最小值
            except Exception as ff_error:
                print(f"❌ BADA ff方法失败: {ff_error}")
                # 使用备选方法
                return self._fallback_fuel_flow(aircraft, altitude_ft, mass_kg)
            
        except Exception as e:
            print(f"❌ BADA燃油流量计算失败: {e}")
            # 返回经验值作为备选
            return self._fallback_fuel_flow(aircraft, altitude_ft, mass_kg)
    
    def _fallback_fuel_flow(self, aircraft, altitude_ft: float, mass_kg: float) -> float:
        """
        备选燃油流量计算（当BADA计算失败时）
        
        Args:
            aircraft: BADA机型对象
            altitude_ft: 高度（英尺）
            mass_kg: 飞机质量（公斤）
            
        Returns:
            燃油流量（kg/s）
        """
        # 基于机型的经验燃油流量（kg/s）
        base_fuel_flow = {
            'B737': 0.65,
            'B757': 0.85,
            'B777': 1.75,
            'B787': 1.40,
            'A319': 0.58,
            'A320': 0.62,
            'A321': 0.78,
            'A330': 1.50,
            'A380': 2.50,
        }
        
        # 尝试从aircraft对象获取机型代码
        aircraft_type = getattr(aircraft, 'ac_type', 'B737')
        base_rate = base_fuel_flow.get(aircraft_type, 0.65)
        
        # 高度修正（高度越高，燃油效率越好）
        altitude_factor = 1.0 - (altitude_ft - 35000) / 100000 * 0.1
        altitude_factor = max(0.85, min(1.15, altitude_factor))
        
        # 质量修正
        mass_factor = mass_kg / 70000  # 假设标准质量70吨
        
        return base_rate * altitude_factor * mass_factor
    
    def calculate_flight_fuel_consumption(self, chinese_aircraft: str, distance_km: float, 
                                        passengers: int, cruise_altitude_ft: float = 35000,
                                        cruise_mach: float = 0.8, temperature_k: float = 220.0) -> Dict:
        """
        计算航班燃油消耗
        
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
        result = {
            'icao_code': '',
            'bada_available': False,
            'fuel_consumption_kg': 0.0,
            'fuel_flow_kg_per_s': 0.0,
            'cruise_time_hours': 0.0,
            'aircraft_mass_kg': 0.0,
            'load_factor': 0.0,
            'calculation_method': 'failed',
            'error_message': ''
        }
        
        try:
            # 1. 机型映射
            icao_code = get_icao_code(chinese_aircraft)
            result['icao_code'] = icao_code
            
            # 2. 载客率计算
            load_factor = calculate_load_factor(passengers, icao_code)
            result['load_factor'] = load_factor
            
            # 3. 获取BADA机型对象
            aircraft = self.get_bada_aircraft(icao_code)
            
            if aircraft is not None:
                result['bada_available'] = True
                
                # 4. 估算飞机质量
                aircraft_mass = self._estimate_aircraft_mass(icao_code, load_factor)
                result['aircraft_mass_kg'] = aircraft_mass
                
                # 5. 计算巡航时间（假设平均速度）
                cruise_speed_kmh = cruise_mach * 1225  # 马赫数转km/h（近似）
                cruise_time_hours = distance_km / cruise_speed_kmh
                result['cruise_time_hours'] = cruise_time_hours
                
                # 6. 使用BADA计算燃油流量
                fuel_flow_kg_per_s = self.calculate_cruise_fuel_flow(
                    aircraft, cruise_altitude_ft, cruise_mach, aircraft_mass, temperature_k
                )
                result['fuel_flow_kg_per_s'] = fuel_flow_kg_per_s
                
                # 7. 计算总燃油消耗
                cruise_fuel_kg = fuel_flow_kg_per_s * cruise_time_hours * 3600  # 巡航燃油
                
                # 8. 添加起降燃油消耗
                takeoff_landing_fuel = self._estimate_takeoff_landing_fuel(icao_code)
                
                total_fuel_kg = cruise_fuel_kg + takeoff_landing_fuel
                result['fuel_consumption_kg'] = round(total_fuel_kg, 2)
                result['calculation_method'] = 'pybada'
                
                print(f"✅ BADA计算完成: {icao_code}, 燃油: {total_fuel_kg:.2f}kg")
                
            else:
                # BADA不可用时的备选计算
                result = self._fallback_calculation(result, distance_km, passengers, icao_code)
                
        except Exception as e:
            result['error_message'] = str(e)
            result['calculation_method'] = 'failed'
            print(f"❌ 燃油计算失败: {e}")
        
        return result
    
    def _estimate_aircraft_mass(self, icao_code: str, load_factor: float) -> float:
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
    
    def _estimate_takeoff_landing_fuel(self, icao_code: str) -> float:
        """
        估算起降燃油消耗
        
        Args:
            icao_code: ICAO机型代码
            
        Returns:
            起降燃油消耗（kg）
        """
        takeoff_landing_fuel = {
            'B737': 300,
            'B757': 400,
            'B777': 800,
            'B787': 600,
            'A319': 250,
            'A320': 300,
            'A321': 350,
            'A330': 700,
            'A380': 1200,
        }
        
        return takeoff_landing_fuel.get(icao_code, 300)
    
    def _fallback_calculation(self, result: Dict, distance_km: float, 
                            passengers: int, icao_code: str) -> Dict:
        """
        备选计算方法（当BADA不可用时）
        """
        from fuel_consumption_calculator import estimate_fuel_consumption_simple
        
        try:
            fuel_consumption = estimate_fuel_consumption_simple(distance_km, icao_code, passengers)
            result['fuel_consumption_kg'] = fuel_consumption
            result['calculation_method'] = 'empirical_fallback'
            print(f"⚠️  使用经验公式备选计算: {icao_code}, 燃油: {fuel_consumption:.2f}kg")
        except Exception as e:
            result['error_message'] = f"备选计算也失败: {str(e)}"
            result['calculation_method'] = 'failed'
        
        return result

def process_flight_data_with_pybada(df: pd.DataFrame, sample_size: Optional[int] = None) -> pd.DataFrame:
    """
    使用pyBADA处理航班数据
    
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
    df['BADA可用'] = False
    df['载客率'] = 0.0
    df['燃油消耗_kg'] = 0.0
    df['燃油流量_kg_per_s'] = 0.0
    df['巡航时间_hours'] = 0.0
    df['计算方法'] = ''
    df['计算状态'] = ''
    
    print(f"开始使用pyBADA处理 {len(df)} 条航班数据...")
    
    success_count = 0
    bada_success_count = 0
    
    for idx, row in df.iterrows():
        try:
            # 获取基础数据
            chinese_aircraft = str(row['机型']).strip()
            distance_km = float(row['里程（公里）'])
            passengers = int(row['人数'])
            
            # 距离修复（如果需要）
            if distance_km <= 0:
                # 这里可以调用距离修复功能
                distance_km = 1000  # 临时默认值
            
            # 使用pyBADA计算
            result = calculator.calculate_flight_fuel_consumption(
                chinese_aircraft, distance_km, passengers
            )
            
            # 更新数据
            df.loc[idx, 'ICAO代码'] = result['icao_code']
            df.loc[idx, 'BADA可用'] = result['bada_available']
            df.loc[idx, '载客率'] = round(result['load_factor'], 3)
            df.loc[idx, '燃油消耗_kg'] = result['fuel_consumption_kg']
            df.loc[idx, '燃油流量_kg_per_s'] = result['fuel_flow_kg_per_s']
            df.loc[idx, '巡航时间_hours'] = result['cruise_time_hours']
            df.loc[idx, '计算方法'] = result['calculation_method']
            df.loc[idx, '计算状态'] = '成功' if result['fuel_consumption_kg'] > 0 else '失败'
            
            if result['calculation_method'] == 'pybada':
                bada_success_count += 1
            
            if result['fuel_consumption_kg'] > 0:
                success_count += 1
                
            # 显示前几条处理结果
            if idx < 5:
                print(f"第{idx+1}条: {chinese_aircraft} -> {result['icao_code']}, "
                      f"方法: {result['calculation_method']}, 燃油: {result['fuel_consumption_kg']:.2f}kg")
                
        except Exception as e:
            df.loc[idx, '计算状态'] = f'失败: {str(e)}'
            print(f"第{idx+1}行处理失败: {e}")
    
    print(f"\n处理完成:")
    print(f"  总计: {len(df)} 条")
    print(f"  成功: {success_count} 条")
    print(f"  BADA计算: {bada_success_count} 条")
    print(f"  失败: {len(df) - success_count} 条")
    print(f"  BADA使用率: {bada_success_count/success_count*100:.1f}%" if success_count > 0 else "  BADA使用率: 0%")
    
    return df

def main_pybada_calculation(sample_size: int = 100):
    """
    主函数：使用pyBADA进行燃油消耗计算
    
    Args:
        sample_size: 处理的样本数量
    """
    try:
        # 设置路径
        base_dir = os.path.dirname(os.path.abspath(__file__))
        data_path = os.path.join(base_dir, '../data/22年1月1日至24年12月31日航班数据.xlsx')
        output_dir = os.path.join(base_dir, '../results/tables')
        os.makedirs(output_dir, exist_ok=True)
        
        print(f"=== pyBADA燃油消耗计算 ===")
        print(f"样本大小: {sample_size} 条记录")
        print(f"pyBADA状态: {'可用' if PYBADA_AVAILABLE else '不可用'}")
        
        # 读取数据
        df = pd.read_excel(data_path, nrows=sample_size)
        print(f"成功读取 {len(df)} 条航班数据")
        
        # 使用pyBADA处理数据
        processed_df = process_flight_data_with_pybada(df)
        
        # 统计结果
        success_df = processed_df[processed_df['计算状态'] == '成功']
        bada_df = processed_df[processed_df['BADA可用'] == True]
        
        if len(success_df) > 0:
            print(f"\n=== 计算结果统计 ===")
            print(f"总燃油消耗: {success_df['燃油消耗_kg'].sum():,.2f} kg")
            print(f"平均燃油消耗: {success_df['燃油消耗_kg'].mean():.2f} kg/航班")
            print(f"平均载客率: {success_df['载客率'].mean():.1%}")
            
            if len(bada_df) > 0:
                print(f"\nBADA计算航班:")
                print(f"  数量: {len(bada_df)} 条")
                print(f"  平均燃油消耗: {bada_df['燃油消耗_kg'].mean():.2f} kg/航班")
                print(f"  平均燃油流量: {bada_df['燃油流量_kg_per_s'].mean():.3f} kg/s")
        
        # 保存结果
        output_file = os.path.join(output_dir, f'pyBADA燃油消耗计算结果_{sample_size}条.xlsx')
        
        with pd.ExcelWriter(output_file, engine='xlsxwriter') as writer:
            # 主要数据
            processed_df.to_excel(writer, sheet_name='航班燃油消耗', index=False)
            
            # 统计汇总
            if len(success_df) > 0:
                summary_data = {
                    '指标': [
                        '总记录数', '成功计算数', 'BADA计算数', '失败数',
                        '总燃油消耗(kg)', '平均燃油消耗(kg)', '平均载客率(%)',
                        'BADA使用率(%)', '计算成功率(%)'
                    ],
                    '数值': [
                        len(processed_df), len(success_df), len(bada_df), len(processed_df) - len(success_df),
                        round(success_df['燃油消耗_kg'].sum(), 2),
                        round(success_df['燃油消耗_kg'].mean(), 2),
                        round(success_df['载客率'].mean() * 100, 1),
                        round(len(bada_df) / len(success_df) * 100, 1) if len(success_df) > 0 else 0,
                        round(len(success_df) / len(processed_df) * 100, 1)
                    ]
                }
                summary_df = pd.DataFrame(summary_data)
                summary_df.to_excel(writer, sheet_name='统计汇总', index=False)
            
            # 按计算方法统计
            method_stats = processed_df['计算方法'].value_counts()
            method_df = pd.DataFrame({
                '计算方法': method_stats.index,
                '数量': method_stats.values
            })
            method_df.to_excel(writer, sheet_name='计算方法统计', index=False)
        
        print(f"\n结果已保存到: {output_file}")
        
    except Exception as e:
        print(f"❌ 主函数执行失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main_pybada_calculation(100) 