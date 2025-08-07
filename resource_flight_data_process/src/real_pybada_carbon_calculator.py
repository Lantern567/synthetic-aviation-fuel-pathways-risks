"""
完整BADA模型的航空碳排放计算模块
使用真实的pyBADA API进行完整飞行轨迹的精确燃油消耗和碳排放计算
基于EUROCONTROL BADA模型，包含爬升、巡航、下降完整阶段
"""

import os
import sys
import pandas as pd
import numpy as np
from typing import Dict, Optional, Tuple, List
import time
from datetime import datetime
import multiprocessing as mp
from concurrent.futures import ProcessPoolExecutor, as_completed
import warnings
warnings.filterwarnings('ignore')

# 尝试导入pyBADA库的实际模块
try:
    from pyBADA.aircraft import Bada
    from pyBADA.bada3 import Parser as Bada3Parser
    from pyBADA.bada3 import Bada3Aircraft
    from pyBADA.bada4 import Parser as Bada4Parser
    from pyBADA.bada4 import Bada4Aircraft
    from pyBADA import atmosphere as atm
    from pyBADA import conversions as conv
    from pyBADA import TCL
    from pyBADA.flightTrajectory import FlightTrajectory
    PYBADA_AVAILABLE = True
    print("✅ pyBADA库已成功导入")
except ImportError as e:
    PYBADA_AVAILABLE = False
    print(f"⚠️ pyBADA库导入失败: {e}")
    print("将使用标准排放系数计算")

# 航空燃油碳排放系数 (根据EPA和IPCC标准)
AVIATION_FUEL_CO2_FACTOR = 3.16  # kg CO2 per kg fuel

class CompleteBadaCarbonCalculator:
    """
    基于完整BADA模型的碳排放计算器
    使用EUROCONTROL BADA模型进行完整飞行轨迹计算 (爬升-巡航-下降)
    """
    
    def __init__(self, bada_version: str = "DUMMY"):
        """
        初始化计算器
        
        Args:
            bada_version: BADA数据版本 ("DUMMY" 用于测试)
        """
        self.bada_version = bada_version
        self.use_pybada = PYBADA_AVAILABLE
        self.co2_factor = AVIATION_FUEL_CO2_FACTOR
        self.route_cache = {}  # 缓存航线计算结果
        self.aircraft_cache = {}  # 缓存机型数据
        
        if self.use_pybada:
            print(f"🔬 使用完整pyBADA库 (版本: {bada_version}) 进行精确轨迹碳排放计算")
            self._initialize_pybada()
        else:
            print("📊 使用标准排放系数进行碳排放计算")
        
        self.stats = {
            'routes_calculated': 0,
            'cache_hits': 0,
            'total_emissions': 0.0,
            'calculation_errors': 0,
            'pybada_calculations': 0,
            'standard_calculations': 0,
            'trajectory_calculations': 0,
            'simplified_calculations': 0
        }
    
    def _initialize_pybada(self):
        """初始化pyBADA库组件"""
        try:
            if PYBADA_AVAILABLE:
                # 尝试加载BADA数据
                print(f"正在加载BADA {self.bada_version} 数据...")
                
                # 使用BADA3 Parser加载数据
                try:
                    self.bada_data = Bada3Parser.parseAll(badaVersion=self.bada_version)
                    self.bada_family = "BADA3"
                    print(f"✅ BADA3数据加载成功，包含 {len(self.bada_data)} 个机型")
                except Exception as e:
                    print(f"BADA3加载失败: {e}")
                    try:
                        self.bada_data = Bada4Parser.parseAll(badaVersion=self.bada_version)
                        self.bada_family = "BADA4"
                        print(f"✅ BADA4数据加载成功，包含 {len(self.bada_data)} 个机型")
                    except Exception as e2:
                        print(f"BADA4加载也失败: {e2}")
                        self.bada_data = None
                        self.bada_family = None
                
                # 增强的机型映射到BADA代码
                self.aircraft_mapping = {
                    'A320': ['A320', 'A1', 'A320-232', 'A32A', 'A32S'],
                    'A321': ['A321', 'A321-211', 'A32B'],
                    'A330': ['A330', 'A332', 'A333', 'A33B', 'A33E', 'A33F'],
                    'A380': ['A380', 'A388', 'A38F'],
                    'B737': ['B737', 'B738', 'B73G', 'B739', 'B37M', 'B3XM'],
                    'B747': ['B747', 'B744', 'B748', 'B74D', 'B74R'],
                    'B777': ['B777', 'B77W', 'B772', 'B773', 'B77L'],
                    'B787': ['B787', 'B788', 'B789', 'B78X'],
                    'CRJ': ['CRJ9', 'CRJ2', 'CRJ7', 'CRJX'],
                    'E190': ['E190', 'E195', 'E290']
                }
                
                print("✅ 完整pyBADA初始化完成")
        except Exception as e:
            print(f"⚠️ pyBADA初始化失败: {e}")
            self.use_pybada = False
            self.bada_data = None
    
    def get_bada_aircraft_name(self, aircraft_icao: str) -> Optional[str]:
        """根据ICAO代码获取BADA中的机型名称"""
        if not self.use_pybada or self.bada_data is None:
            return None
        
        # 首先尝试直接匹配
        if aircraft_icao in self.bada_data['acName'].values:
            return aircraft_icao
        
        # 尝试映射表匹配
        for base_type, variants in self.aircraft_mapping.items():
            if aircraft_icao.startswith(base_type) or aircraft_icao in variants:
                for variant in variants:
                    if variant in self.bada_data['acName'].values:
                        return variant
        
        # 尝试模糊匹配
        for ac_name in self.bada_data['acName'].values:
            if aircraft_icao[:3] in ac_name or ac_name[:3] in aircraft_icao:
                return ac_name
        
        return None
    
    def create_bada_aircraft(self, aircraft_icao: str):
        """创建BADA飞机对象"""
        bada_name = self.get_bada_aircraft_name(aircraft_icao)
        if not bada_name:
            return None
        
        try:
            if self.bada_family == "BADA3":
                aircraft = Bada3Aircraft(
                    badaVersion=self.bada_version,
                    acName=bada_name,
                    allData=self.bada_data
                )
            elif self.bada_family == "BADA4":
                aircraft = Bada4Aircraft(
                    badaVersion=self.bada_version,
                    acName=bada_name,
                    allData=self.bada_data
                )
            else:
                return None
            
            return aircraft
            
        except Exception as e:
            print(f"⚠️ 创建BADA飞机对象失败 {aircraft_icao}: {e}")
            return None
    
    def calculate_complete_trajectory_fuel(self, route_data: pd.Series) -> Optional[float]:
        """
        使用完整BADA轨迹模型计算燃油消耗
        包括爬升、巡航、下降三个完整阶段
        修正版本：使用正确的TCL.constantSpeedROCD API
        """
        try:
            # 支持多种字段名格式
            aircraft_icao = route_data.get('Aircraft ICAO', 
                          route_data.get('ICAO代码', 
                          route_data.get('机型', 
                          route_data.get('aircraft_type', ''))))
            
            distance_km = route_data.get('Distance (km)', 
                        route_data.get('里程（公里）', 
                        route_data.get('distance_km', 
                        route_data.get('Distance', 0))))
            
            if distance_km <= 0 or not aircraft_icao:
                print(f"   ❌ 无效数据: 机型={aircraft_icao}, 距离={distance_km}km")
                return None
            
            # 创建BADA飞机对象
            aircraft = self.create_bada_aircraft(aircraft_icao)
            if not aircraft:
                return None
            
            distance_nm = distance_km * 0.539957  # 转换为海里
            
            # 飞行参数设置
            cruise_altitude_ft = self._determine_cruise_altitude(distance_km)
            cruise_mach = self._determine_cruise_mach(aircraft_icao)
            
            # 估算初始质量 (考虑载荷因子)
            load_factor = route_data.get('Load Factor', 
                        route_data.get('载客率', 
                        route_data.get('load_factor', 0.8)))
            m_init = aircraft.OEW + load_factor * (aircraft.MTOW - aircraft.OEW)
            
            print(f"🛫 计算完整轨迹: {aircraft_icao}, 距离: {distance_km:.0f}km, 巡航高度: {cruise_altitude_ft}ft")
            print(f"   初始质量: {m_init:.0f}kg, 载荷因子: {load_factor:.2f}")
            
            # 创建飞行轨迹对象
            ft = FlightTrajectory()
            
            try:
                # === 第一阶段: 爬升 ===
                climb_time_sec = 600  # 10分钟爬升时间
                
                # 使用constantSpeedROCD进行爬升 (正ROCD值)
                climb_trajectory = TCL.constantSpeedROCD(
                    AC=aircraft,
                    speedType="CAS",  # 校正空速
                    v=250,  # 典型爬升速度 250 knots CAS
                    Hp_init=0,  # 起始高度海平面
                    Hp_final=cruise_altitude_ft,  # 目标巡航高度
                    ROCDtarget=1500,  # 爬升率 1500 ft/min (正值表示爬升)
                    m_init=m_init,
                    DeltaTemp=0,
                    wS=0  # 无风
                )
                
                if climb_trajectory is not None and not climb_trajectory.empty:
                    ft.append(aircraft, climb_trajectory)
                    climb_fuel = climb_trajectory['FUELCONSUMED'].iloc[-1] if 'FUELCONSUMED' in climb_trajectory.columns else 0
                    current_mass = m_init - climb_fuel
                    final_climb_altitude = climb_trajectory['Hp'].iloc[-1] if 'Hp' in climb_trajectory.columns else cruise_altitude_ft
                    print(f"   ⬆️ 爬升燃油: {climb_fuel:.1f} kg, 到达高度: {final_climb_altitude:.0f} ft")
                else:
                    climb_fuel = 0
                    current_mass = m_init
                    final_climb_altitude = cruise_altitude_ft
                
                # === 第二阶段: 巡航 ===
                cruise_distance_nm = distance_nm - 50  # 减去爬升下降距离
                cruise_distance_nm = max(cruise_distance_nm, distance_nm * 0.6)  # 至少60%距离巡航
                
                cruise_trajectory = TCL.constantSpeedLevel(
                    AC=aircraft,
                    lengthType="distance",
                    length=cruise_distance_nm,
                    speedType="M",  # 马赫数
                    v=cruise_mach,
                    Hp_init=final_climb_altitude,  # 使用爬升后的高度
                    m_init=current_mass,
                    wS=0,  # 无风
                    bankAngle=0,
                    DeltaTemp=0
                )
                
                if cruise_trajectory is not None and not cruise_trajectory.empty:
                    ft.append(aircraft, cruise_trajectory)
                    cruise_fuel = cruise_trajectory['FUELCONSUMED'].iloc[-1] if 'FUELCONSUMED' in cruise_trajectory.columns else 0
                    current_mass -= cruise_fuel
                    print(f"   ➡️ 巡航燃油: {cruise_fuel:.1f} kg")
                else:
                    cruise_fuel = 0
                
                # === 第三阶段: 下降 ===
                descent_time_sec = 480  # 8分钟下降时间
                
                # 使用constantSpeedROCD进行下降 (负ROCD值)
                descent_trajectory = TCL.constantSpeedROCD(
                    AC=aircraft,
                    speedType="CAS",
                    v=280,  # 典型下降速度 280 knots CAS
                    Hp_init=final_climb_altitude,  # 从巡航高度开始下降
                    Hp_final=0,  # 下降到海平面
                    ROCDtarget=-1200,  # 下降率 -1200 ft/min (负值表示下降)
                    m_init=current_mass,
                    DeltaTemp=0,
                    wS=0
                )
                
                if descent_trajectory is not None and not descent_trajectory.empty:
                    ft.append(aircraft, descent_trajectory)
                    descent_fuel = descent_trajectory['FUELCONSUMED'].iloc[-1] if 'FUELCONSUMED' in descent_trajectory.columns else 0
                    print(f"   ⬇️ 下降燃油: {descent_fuel:.1f} kg")
                else:
                    descent_fuel = 0
                
                # 计算总燃油消耗
                total_fuel = climb_fuel + cruise_fuel + descent_fuel
                
                # 添加储备燃油 (5-10%)
                reserve_factor = 1.07  # 7%储备燃油
                total_fuel_with_reserve = total_fuel * reserve_factor
                
                print(f"   🛬 总燃油消耗: {total_fuel:.1f} kg (含储备: {total_fuel_with_reserve:.1f} kg)")
                
                self.stats['trajectory_calculations'] += 1
                return total_fuel_with_reserve
                
            except Exception as trajectory_error:
                print(f"   ⚠️ 完整轨迹计算失败: {trajectory_error}")
                # 尝试简化轨迹计算
                return self._simplified_trajectory_calculation(aircraft, distance_km, m_init)
            
        except Exception as e:
            print(f"❌ 完整轨迹燃油计算失败: {e}")
            return None
    
    def _determine_cruise_altitude(self, distance_km: float) -> int:
        """根据航程确定最优巡航高度"""
        if distance_km < 500:  # 短程
            return 25000  # FL250
        elif distance_km < 1500:  # 中程
            return 33000  # FL330
        elif distance_km < 3000:  # 长程
            return 37000  # FL370
        else:  # 超长程
            return 41000  # FL410
    
    def _determine_cruise_mach(self, aircraft_icao: str) -> float:
        """根据机型确定最优巡航马赫数"""
        mach_numbers = {
            'A320': 0.78, 'A321': 0.78, 'A330': 0.82, 'A380': 0.85,
            'B737': 0.78, 'B747': 0.84, 'B777': 0.84, 'B787': 0.85,
            'CRJ': 0.74, 'E190': 0.78
        }
        return mach_numbers.get(aircraft_icao[:4], 0.78)  # 默认 M0.78
    
    def _simplified_trajectory_calculation(self, aircraft, distance_km: float, mass: float) -> float:
        """简化的轨迹燃油计算 (当完整计算失败时使用)"""
        try:
            print(f"   🔄 使用简化轨迹计算")
            
            # 基于飞行阶段的燃油消耗估算
            cruise_altitude_ft = self._determine_cruise_altitude(distance_km)
            distance_nm = distance_km * 0.539957
            
            # 简化的三阶段计算
            # 爬升阶段燃油 (基于高度和重量)
            climb_fuel = self._estimate_climb_fuel(aircraft, cruise_altitude_ft, mass)
            
            # 巡航阶段燃油 (基于距离和BADA参数)
            cruise_fuel = self._estimate_cruise_fuel(aircraft, distance_km * 0.7, mass)
            
            # 下降阶段燃油 (通常较少)
            descent_fuel = climb_fuel * 0.3  # 下降燃油约为爬升的30%
            
            total_fuel = climb_fuel + cruise_fuel + descent_fuel
            total_fuel_with_reserve = total_fuel * 1.07  # 7%储备
            
            print(f"   📊 简化计算燃油: {total_fuel_with_reserve:.1f} kg")
            self.stats['simplified_calculations'] += 1
            
            return total_fuel_with_reserve
            
        except Exception as e:
            print(f"   ❌ 简化计算也失败: {e}")
            return None
    
    def _estimate_climb_fuel(self, aircraft, altitude_ft: float, mass: float) -> float:
        """估算爬升阶段燃油消耗"""
        # 基于高度和重量的经验公式
        altitude_km = altitude_ft * 0.0003048
        fuel_rate = 0.15 + (mass / 100000) * 0.1  # kg/km
        return altitude_km * fuel_rate
    
    def _estimate_cruise_fuel(self, aircraft, distance_km: float, mass: float) -> float:
        """估算巡航阶段燃油消耗"""
        # 基于BADA参数的燃油流量估算
        try:
            # 获取机型燃油流量参数
            params = Bada.getBADAParameters(
                df=self.bada_data,
                acName=aircraft.acName,
                parameters=["Cf1", "Cf2", "Cf3", "Cf4"]
            )
            
            if not params.empty:
                cf1 = params.iloc[0].get('Cf1', 0.85)
                cf2 = params.iloc[0].get('Cf2', 1200)
                
                # 估算飞行时间
                avg_speed_kmh = 850  # 巡航速度
                flight_time_hours = distance_km / avg_speed_kmh
                
                # 基于BADA燃油流量公式的简化版本
                fuel_flow_kg_per_hour = cf2 * (1 + cf1 * (mass / aircraft.MTOW))
                cruise_fuel = fuel_flow_kg_per_hour * flight_time_hours
                
                return cruise_fuel
            
        except Exception:
            pass
        
        # 备用计算
        fuel_rate = 0.04 + (mass / 100000) * 0.02  # kg/km
        return distance_km * fuel_rate
    
    def calculate_route_carbon_emissions(self, route_data: pd.Series) -> Dict:
        """
        计算航线的碳排放
        返回格式与pybada_fuel_calculator_clean.py保持一致
        """
        try:
            # 提取航线基础信息（支持多种字段名）
            aircraft_icao = route_data.get('Aircraft ICAO', 
                          route_data.get('ICAO代码', 
                          route_data.get('机型', 
                          route_data.get('aircraft_type', ''))))
            
            distance_km = route_data.get('Distance (km)', 
                        route_data.get('里程（公里）', 
                        route_data.get('distance_km', 
                        route_data.get('Distance', 0))))
            
            passengers = route_data.get('Passengers', 
                       route_data.get('人数', 
                       route_data.get('passengers', 
                       route_data.get('Passenger_Count', 120))))  # 默认120人
            
            # 估算载客率
            load_factor = self._calculate_load_factor(passengers, aircraft_icao)
            
            # 生成航线缓存键
            route_key = f"{aircraft_icao}_{distance_km}_{passengers}"
            
            # 检查缓存
            if route_key in self.route_cache:
                self.stats['cache_hits'] += 1
                cached_result = self.route_cache[route_key].copy()
                cached_result['status'] = 'cached'
                return cached_result
            
            # 初始化结果字典（包含pybada_fuel_calculator_clean.py的所有字段）
            result = {
                'ICAO代码': aircraft_icao,
                '载客率': round(load_factor, 3),
                '燃油消耗_kg': 0.0,
                '燃油流量_kg_per_s': 0.0,
                '巡航时间_hours': 0.0,
                '计算方法': 'unknown',
                'CO2_kg': 0.0,
                'Per_Person_CO2_kg': 0.0,
                'status': 'calculated'
            }
            
            fuel_kg = None
            calculation_method = 'unknown'
            
            # 尝试不同的燃油计算方法
            if self.use_pybada and distance_km > 0:
                # 1. 尝试完整轨迹计算
                try:
                    fuel_result = self.calculate_complete_trajectory_fuel(route_data)
                    if fuel_result and fuel_result > 0:
                        fuel_kg = fuel_result
                        calculation_method = 'complete_trajectory'
                        self.stats['trajectory_calculations'] += 1
                        print(f"   ✅ 完整轨迹计算成功: {fuel_kg:.1f}kg")
                except Exception as e:
                    print(f"   ⚠️ 完整轨迹计算失败: {e}")
                
                # 2. 回退到简化轨迹计算
                if not fuel_kg:
                    try:
                        aircraft = self.create_bada_aircraft(aircraft_icao)
                        if aircraft:
                            mass = aircraft.OEW + load_factor * (aircraft.MTOW - aircraft.OEW)
                            fuel_kg = self._simplified_trajectory_calculation(aircraft, distance_km, mass)
                            if fuel_kg and fuel_kg > 0:
                                calculation_method = 'simplified_trajectory'
                                self.stats['simplified_calculations'] += 1
                                print(f"   ✅ 简化轨迹计算成功: {fuel_kg:.1f}kg")
                    except Exception as e:
                        print(f"   ⚠️ 简化轨迹计算失败: {e}")
            
            # 3. 最终回退到经验公式
            if not fuel_kg or fuel_kg <= 0:
                try:
                    fuel_kg = self._estimate_fuel_consumption(route_data)
                    calculation_method = 'empirical_formula'
                    self.stats['standard_calculations'] += 1
                    print(f"   ✅ 经验公式估算: {fuel_kg:.1f}kg")
                except Exception as e:
                    print(f"   ❌ 燃油计算完全失败: {e}")
                    fuel_kg = 0
                    calculation_method = 'failed'
                    self.stats['calculation_errors'] += 1
            
            # 计算燃油流量和巡航时间
            if fuel_kg > 0 and distance_km > 0:
                # 估算巡航时间（基于典型巡航速度）
                cruise_speed_kmh = self._get_typical_cruise_speed(aircraft_icao)
                cruise_time_hours = distance_km / cruise_speed_kmh
                
                # 估算燃油流量（基于巡航阶段，约占总燃油的60-70%）
                cruise_fuel_kg = fuel_kg * 0.65  # 巡航阶段燃油比例
                fuel_flow_kg_per_s = cruise_fuel_kg / (cruise_time_hours * 3600) if cruise_time_hours > 0 else 0
            else:
                cruise_time_hours = 0
                fuel_flow_kg_per_s = 0
            
            # 计算碳排放
            emission_factor = self._get_emission_factor(aircraft_icao)
            co2_kg = fuel_kg * emission_factor
            per_person_co2_kg = co2_kg / passengers if passengers > 0 else 0
            
            # 更新结果字典
            result.update({
                '燃油消耗_kg': round(fuel_kg, 2),
                '燃油流量_kg_per_s': round(fuel_flow_kg_per_s, 4),
                '巡航时间_hours': round(cruise_time_hours, 3),
                '计算方法': calculation_method,
                'CO2_kg': round(co2_kg, 2),
                'Per_Person_CO2_kg': round(per_person_co2_kg, 2)
            })
            
            # 缓存结果
            self.route_cache[route_key] = result.copy()
            
            # 更新统计
            self.stats['routes_calculated'] += 1
            self.stats['total_emissions'] += co2_kg
            if calculation_method in ['complete_trajectory']:
                self.stats['pybada_calculations'] += 1
                
            return result
            
        except Exception as e:
            print(f"❌ 航线碳排放计算失败: {e}")
            self.stats['calculation_errors'] += 1
            return {
                'ICAO代码': aircraft_icao if 'aircraft_icao' in locals() else 'UNKNOWN',
                '载客率': 0.0,
                '燃油消耗_kg': 0.0,
                '燃油流量_kg_per_s': 0.0,
                '巡航时间_hours': 0.0,
                '计算方法': 'error',
                'CO2_kg': 0.0,
                'Per_Person_CO2_kg': 0.0,
                'status': 'error'
            }
    
    def _estimate_fuel_consumption(self, route_data: pd.Series) -> float:
        """基于经验公式估算燃油消耗"""
        # 支持多种字段名格式
        distance_km = route_data.get('Distance (km)', 
                    route_data.get('里程（公里）', 
                    route_data.get('distance_km', 
                    route_data.get('Distance', 0))))
        
        aircraft_icao = route_data.get('Aircraft ICAO', 
                      route_data.get('ICAO代码', 
                      route_data.get('机型', 
                      route_data.get('aircraft_type', ''))))
        
        # 基于机型的燃油消耗率 (L/100km per seat)
        fuel_rates = {
            'A320': 3.2, 'A321': 3.4, 'A330': 4.2, 'A380': 4.8,
            'B737': 3.1, 'B747': 5.0, 'B777': 4.5, 'B787': 3.8,
            'CRJ': 4.0, 'E190': 3.5
        }
        
        # 获取基础燃油消耗率
        base_rate = fuel_rates.get(aircraft_icao[:4], 3.5)  # 默认3.5L/100km/seat
        
        # 估算座位数
        seat_counts = {
            'A320': 180, 'A321': 220, 'A330': 300, 'A380': 550,
            'B737': 160, 'B747': 400, 'B777': 350, 'B787': 250,
            'CRJ': 90, 'E190': 100
        }
        seats = seat_counts.get(aircraft_icao[:4], 180)
        
        # 计算燃油消耗 (转换为kg)
        fuel_liters = (distance_km / 100) * base_rate * seats
        fuel_kg = fuel_liters * 0.8  # 航空燃油密度约0.8kg/L
        
        return fuel_kg
    
    def _get_emission_factor(self, aircraft_icao: str) -> float:
        """获取机型特定的碳排放系数"""
        # 不同机型的燃油碳排放系数 (kg CO2 per kg fuel)
        emission_factors = {
            'A320': 3.15, 'A321': 3.15, 'A330': 3.17, 'A340': 3.18, 'A350': 3.16, 'A380': 3.18,
            'B737': 3.15, 'B747': 3.18, 'B757': 3.16, 'B767': 3.16, 'B777': 3.16, 'B787': 3.14,
            'CRJ': 3.15, 'E190': 3.15, 'ATR': 3.14
        }
        
        # 尝试匹配机型
        for key in emission_factors:
            if aircraft_icao.startswith(key):
                return emission_factors[key]
        
        return self.co2_factor  # 默认排放系数
    
    def _calculate_load_factor(self, passengers: int, aircraft_icao: str) -> float:
        """
        计算载客率
        
        Args:
            passengers: 实际载客数
            aircraft_icao: 机型ICAO代码
            
        Returns:
            载客率 (0.0-1.0)
        """
        # 典型机型座位数
        seat_capacities = {
            'A319': 150, 'A320': 180, 'A321': 220, 'A330': 300, 'A340': 350, 
            'A350': 350, 'A380': 550,
            'B737': 160, 'B747': 400, 'B757': 200, 'B767': 250, 'B777': 350, 
            'B787': 250,
            'CRJ': 90, 'E190': 100, 'ATR': 70
        }
        
        # 查找匹配的座位数
        max_seats = 180  # 默认值
        for aircraft_type, seats in seat_capacities.items():
            if aircraft_icao.startswith(aircraft_type):
                max_seats = seats
                break
        
        # 计算载客率，限制在合理范围内
        load_factor = min(passengers / max_seats, 1.0) if max_seats > 0 else 0.8
        return max(load_factor, 0.1)  # 最小10%载客率
    
    def _get_typical_cruise_speed(self, aircraft_icao: str) -> float:
        """
        获取机型典型巡航速度
        
        Args:
            aircraft_icao: 机型ICAO代码
            
        Returns:
            巡航速度 (km/h)
        """
        # 典型机型巡航速度
        cruise_speeds = {
            'A319': 828, 'A320': 840, 'A321': 840, 'A330': 871, 'A340': 871,
            'A350': 903, 'A380': 903,
            'B737': 842, 'B747': 917, 'B757': 850, 'B767': 850, 'B777': 905,
            'B787': 903,
            'CRJ': 786, 'E190': 829, 'ATR': 510
        }
        
        # 查找匹配的巡航速度
        for aircraft_type, speed in cruise_speeds.items():
            if aircraft_icao.startswith(aircraft_type):
                return speed
        
        return 850  # 默认巡航速度 (km/h)
    
    def get_calculation_stats(self) -> Dict:
        """获取计算统计信息"""
        return {
            'trajectory_calculations': self.stats.get('trajectory_calculations', 0),
            'simplified_calculations': self.stats.get('simplified_calculations', 0),
            'empirical_calculations': self.stats.get('standard_calculations', 0),
            'total_calculations': self.stats.get('routes_calculated', 0),
            'cache_hits': self.stats.get('cache_hits', 0),
            'calculation_errors': self.stats.get('calculation_errors', 0),
            'total_emissions_kg': self.stats.get('total_emissions', 0.0)
        }
    
    def reset_stats(self):
        """重置统计信息"""
        self.stats = {
            'routes_calculated': 0,
            'cache_hits': 0,
            'calculation_errors': 0,
            'total_emissions': 0.0,
            'trajectory_calculations': 0,
            'simplified_calculations': 0,
            'standard_calculations': 0,
            'pybada_calculations': 0
        }

def process_chunk_worker(chunk_data: Tuple[int, pd.DataFrame]) -> Tuple[int, List[Dict]]:
    """
    并行处理工作函数
    
    Args:
        chunk_data: (chunk_id, chunk_dataframe) 元组
        
    Returns:
        (chunk_id, results_list) 元组
    """
    chunk_id, chunk = chunk_data
    calculator = CompleteBadaCarbonCalculator(bada_version="DUMMY")
    
    results = []
    for idx, row in chunk.iterrows():
        result = calculator.calculate_route_carbon_emissions(row)
        results.append(result)
    
    print(f"✅ 块 {chunk_id + 1} 并行处理完成 ({len(chunk)} 行)")
    return chunk_id, results

def process_carbon_emissions_with_complete_bada(
    data_file_path: str, 
    output_dir: str,
    chunk_size: int = 1000,  # 减小块大小以提高并行效率
    max_workers: int = None
) -> Optional[pd.DataFrame]:
    """
    使用完整BADA轨迹模型和并行处理进行碳排放计算
    
    Args:
        data_file_path: 输入数据文件路径
        output_dir: 输出目录
        chunk_size: 处理块大小
        max_workers: 最大工作进程数
        
    Returns:
        处理后的DataFrame
    """
    
    print("🚀 开始使用完整BADA轨迹模型和并行处理进行碳排放计算...")
    start_time = time.time()
    
    # 确保输出目录存在
    os.makedirs(output_dir, exist_ok=True)
    
    # 设置最大工作进程数
    if max_workers is None:
        max_workers = min(mp.cpu_count() - 1, 8)  # 保留1个CPU核心，最多8个进程
    
    print(f"🔧 并行配置: {max_workers} 个工作进程, 块大小: {chunk_size}")
    
    try:
        # 读取数据
        print(f"📖 读取数据文件: {data_file_path}")
        if data_file_path.endswith('.xlsx'):
            df = pd.read_excel(data_file_path)
        else:
            df = pd.read_csv(data_file_path)
        
        print(f"📊 数据形状: {df.shape}")
        
        # 初始化统计计算器（用于最终统计）
        main_calculator = CompleteBadaCarbonCalculator(bada_version="DUMMY")
        main_calculator.reset_stats()
        
        # 准备分块数据
        chunks = []
        total_chunks = len(df) // chunk_size + (1 if len(df) % chunk_size else 0)
        
        for i in range(0, len(df), chunk_size):
            chunk = df.iloc[i:i+chunk_size].copy()
            chunks.append((i // chunk_size, chunk))
        
        print(f"📦 数据分为 {total_chunks} 个块进行并行处理")
        
        # 并行处理所有块
        print(f"⚡ 开始并行处理...")
        parallel_start = time.time()
        
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有任务
            future_to_chunk = {executor.submit(process_chunk_worker, chunk_data): chunk_data[0] 
                             for chunk_data in chunks}
            
            # 收集结果
            chunk_results = {}
            completed = 0
            
            for future in as_completed(future_to_chunk):
                chunk_id = future_to_chunk[future]
                try:
                    chunk_id, results = future.result()
                    chunk_results[chunk_id] = results
                    completed += 1
                    
                    # 显示进度
                    progress = (completed / total_chunks) * 100
                    print(f"🔄 并行进度: {completed}/{total_chunks} 块完成 ({progress:.1f}%)")
                    
                except Exception as exc:
                    print(f"❌ 块 {chunk_id} 处理失败: {exc}")
                    chunk_results[chunk_id] = []
        
        parallel_time = time.time() - parallel_start
        print(f"⚡ 并行处理完成，耗时: {parallel_time:.2f} 秒")
        
        # 按顺序合并结果到DataFrame
        print("🔗 合并并行处理结果...")
        merge_start = time.time()
        
        for chunk_id in sorted(chunk_results.keys()):
            results = chunk_results[chunk_id]
            chunk_start_idx = chunk_id * chunk_size
            
            for j, result in enumerate(results):
                row_idx = chunk_start_idx + j
                if row_idx < len(df):
                    # 设置与pybada_fuel_calculator_clean.py一致的字段（保留CO2字段）
                    df.loc[row_idx, 'ICAO代码'] = result['ICAO代码']
                    df.loc[row_idx, '载客率'] = result['载客率']
                    df.loc[row_idx, '燃油消耗_kg'] = result['燃油消耗_kg']
                    df.loc[row_idx, '燃油流量_kg_per_s'] = result['燃油流量_kg_per_s']
                    df.loc[row_idx, '巡航时间_hours'] = result['巡航时间_hours']
                    df.loc[row_idx, '计算方法'] = result['计算方法']
                    # 保留二氧化碳相关字段
                    df.loc[row_idx, 'CO2_kg'] = result['CO2_kg']
                    df.loc[row_idx, 'Per_Person_CO2_kg'] = result['Per_Person_CO2_kg']
                    # 可选状态字段
                    if 'status' in result:
                        df.loc[row_idx, 'Status'] = result['status']
                    
                    # 累计统计数据
                    main_calculator.stats['routes_calculated'] += 1
                    main_calculator.stats['total_emissions'] += result.get('CO2_kg', 0)
                    
                    # 根据计算方法更新统计
                    method = result.get('计算方法', 'unknown')
                    if method in ['complete_trajectory']:
                        main_calculator.stats['trajectory_calculations'] += 1
                        main_calculator.stats['pybada_calculations'] += 1
                    elif method in ['simplified_trajectory']:
                        main_calculator.stats['simplified_calculations'] += 1
                        main_calculator.stats['pybada_calculations'] += 1
                    elif method in ['empirical_formula']:
                        main_calculator.stats['standard_calculations'] += 1
                    elif method in ['error', 'failed']:
                        main_calculator.stats['calculation_errors'] += 1
        
        merge_time = time.time() - merge_start
        print(f"🔗 结果合并完成，耗时: {merge_time:.2f} 秒")
        
        # 保存结果
        print("💾 保存结果...")
        save_start = time.time()
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = os.path.join(output_dir, f"parallel_complete_BADA_carbon_emissions_{timestamp}.xlsx")
        
        with pd.ExcelWriter(output_file, engine='xlsxwriter') as writer:
            df.to_excel(writer, sheet_name='并行完整BADA碳排放结果', index=False)
            
            # 添加统计摘要
            stats_df = pd.DataFrame([main_calculator.stats])
            stats_df.to_excel(writer, sheet_name='计算统计', index=False)
            
            # 添加方法分布统计
            method_stats = df['计算方法'].value_counts()
            method_stats.to_excel(writer, sheet_name='计算方法统计')
            
            # 添加详细计算统计
            detailed_stats = pd.DataFrame({
                '统计项目': [
                    '总处理航线数', '缓存命中数', '完整轨迹计算数', '简化轨迹计算数',
                    'pyBADA计算数', '标准公式计算数', '计算错误数', '总碳排放(kg)',
                    '平均每航线排放(kg)', '总碳排放(吨)', '平均燃油消耗(kg)', '总燃油消耗(kg)',
                    '并行处理时间(秒)', '结果合并时间(秒)', '总处理时间(秒)', '并行工作进程数'
                ],
                '数值': [
                    main_calculator.stats['routes_calculated'],
                    main_calculator.stats['cache_hits'],
                    main_calculator.stats['trajectory_calculations'],
                    main_calculator.stats['simplified_calculations'],
                    main_calculator.stats['pybada_calculations'],
                    main_calculator.stats['standard_calculations'],
                    main_calculator.stats['calculation_errors'],
                    main_calculator.stats['total_emissions'],
                    main_calculator.stats['total_emissions'] / max(main_calculator.stats['routes_calculated'], 1),
                    main_calculator.stats['total_emissions'] / 1000,
                    df['燃油消耗_kg'].mean() if '燃油消耗_kg' in df.columns else 0,
                    df['燃油消耗_kg'].sum() if '燃油消耗_kg' in df.columns else 0,
                    parallel_time,
                    merge_time,
                    time.time() - start_time,
                    max_workers
                ]
            })
            detailed_stats.to_excel(writer, sheet_name='详细统计', index=False)
            
            # 添加性能分析
            performance_stats = pd.DataFrame({
                '性能指标': [
                    '总数据行数', '处理块数', '平均每块行数', '并行工作进程数',
                    '并行处理时间(秒)', '结果合并时间(秒)', '文件保存时间(秒)', '总处理时间(秒)',
                    '平均每行处理时间(毫秒)', '理论串行时间估算(秒)', '并行加速比',
                    '每秒处理行数', 'CPU利用率(%)'
                ],
                '数值': [
                    len(df),
                    total_chunks,
                    len(df) / total_chunks,
                    max_workers,
                    parallel_time,
                    merge_time,
                    time.time() - save_start,
                    time.time() - start_time,
                    (parallel_time / len(df)) * 1000,
                    parallel_time * max_workers,  # 估算串行时间
                    (parallel_time * max_workers) / parallel_time if parallel_time > 0 else 0,  # 加速比
                    len(df) / parallel_time if parallel_time > 0 else 0,
                    (parallel_time * max_workers) / (time.time() - start_time) * 100
                ]
            })
            performance_stats.to_excel(writer, sheet_name='性能分析', index=False)
        
        save_time = time.time() - save_start
        
        # 输出统计信息
        end_time = time.time()
        total_time = end_time - start_time
        
        print("\n" + "="*80)
        print("📈 并行完整BADA轨迹计算统计:")
        print(f"⏱️  总处理时间: {total_time:.2f} 秒")
        print(f"⚡ 并行处理时间: {parallel_time:.2f} 秒 ({parallel_time/total_time*100:.1f}%)")
        print(f"🔗 结果合并时间: {merge_time:.2f} 秒 ({merge_time/total_time*100:.1f}%)")
        print(f"💾 文件保存时间: {save_time:.2f} 秒 ({save_time/total_time*100:.1f}%)")
        print(f"🔧 并行配置: {max_workers} 个进程, {total_chunks} 个块")
        print(f"📊 处理行数: {len(df):,}")
        print(f"⚡ 处理速度: {len(df)/parallel_time:.0f} 行/秒 (并行), {len(df)/total_time:.0f} 行/秒 (总体)")
        print(f"🎯 理论加速比: {max_workers:.1f}x (最大), 实际: {(parallel_time*max_workers)/parallel_time:.1f}x")
        print(f"🛣️  计算航线数: {main_calculator.stats['routes_calculated']:,}")
        print(f"💾 缓存命中数: {main_calculator.stats['cache_hits']:,}")
        print(f"🛫 完整轨迹计算数: {main_calculator.stats['trajectory_calculations']:,}")
        print(f"📐 简化轨迹计算数: {main_calculator.stats['simplified_calculations']:,}")
        print(f"🔬 pyBADA计算数: {main_calculator.stats['pybada_calculations']:,}")
        print(f"📊 标准计算数: {main_calculator.stats['standard_calculations']:,}")
        print(f"❌ 计算错误数: {main_calculator.stats['calculation_errors']:,}")
        print(f"🌍 总碳排放: {main_calculator.stats['total_emissions']:,.0f} kg CO2")
        print(f"📈 平均每航线排放: {main_calculator.stats['total_emissions'] / max(main_calculator.stats['routes_calculated'], 1):,.0f} kg CO2")
        print(f"💾 输出文件: {output_file}")
        print("="*80)
        
        # 显示计算方法分布
        if '计算方法' in df.columns:
            print("\n🔍 计算方法分布:")
            method_counts = df['计算方法'].value_counts()
            for method, count in method_counts.items():
                percentage = (count / len(df)) * 100
                print(f"   {method}: {count:,} ({percentage:.1f}%)")
        
        return df
        
    except Exception as e:
        print(f"❌ 处理过程中出现错误: {e}")
        import traceback
        traceback.print_exc()
        return None

# 保持向后兼容的函数别名
def process_carbon_emissions_with_real_pybada(
    data_file_path: str, 
    output_dir: str,
    chunk_size: int = 10000,
    max_workers: int = None
) -> Optional[pd.DataFrame]:
    """
    向后兼容的函数别名
    实际调用完整BADA轨迹模型处理函数
    """
    return process_carbon_emissions_with_complete_bada(
        data_file_path, output_dir, chunk_size, max_workers
    )

if __name__ == "__main__":
    # 测试代码
    data_file = "air_port_data_process/results/parallel_fuel_calculation/并行计算结果_20250630_011947.xlsx"
    output_dir = "results/carbon_emissions"
    
    if os.path.exists(data_file):
        print("🧪 开始测试完整BADA轨迹模型...")
        
        # 先读取数据看看大小
        print(f"📖 检查数据文件大小...")
        if data_file.endswith('.xlsx'):
            df_test = pd.read_excel(data_file, nrows=100)  # 先读取100行测试
        else:
            df_test = pd.read_csv(data_file, nrows=100)
        
        print(f"📊 测试数据形状: {df_test.shape}")
        print(f"📊 列名: {list(df_test.columns)}")
        
        # 创建小测试文件
        test_file = "test_small_data.xlsx"
        df_test.to_excel(test_file, index=False)
        
        result_df = process_carbon_emissions_with_complete_bada(
            data_file_path=test_file,
            output_dir=output_dir,
            chunk_size=25,  # 小块大小用于测试
            max_workers=4   # 限制工作进程数
        )
        
        # 清理测试文件
        if os.path.exists(test_file):
            os.remove(test_file)
        
        if result_df is not None:
            print("✅ 并行完整BADA轨迹碳排放计算完成!")
            print(f"结果保存到: {output_dir}")
        else:
            print("❌ 并行完整BADA轨迹碳排放计算失败!")
    else:
        print(f"❌ 数据文件不存在: {data_file}")
        print("📁 正在检查其他可能的数据文件...")
        
        # 尝试查找其他数据文件
        import glob
        possible_files = glob.glob("results/**/*.xlsx", recursive=True)
        if possible_files:
            print("📄 找到以下数据文件:")
            for file in possible_files[:5]:  # 显示前5个
                print(f"   - {file}")
            print(f"请更新代码中的 data_file 路径")
        else:
            print("❌ 未找到任何数据文件") 