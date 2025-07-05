"""
使用pyBADA库进行航班燃油消耗和碳排放计算
集成完整的BADA3模型和TCL轨迹计算库
"""

import logging
import numpy as np
import pandas as pd
from typing import Dict, Tuple, Optional, NamedTuple
import sys
import os

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    import pyBADA.bada3 as bada3
    import pyBADA.TCL as tcl
    PYBADA_AVAILABLE = True
    logger.info("✅ pyBADA库导入成功")
except ImportError as e:
    PYBADA_AVAILABLE = False
    logger.error(f"❌ pyBADA库导入失败: {e}")
    logger.error("请确保已安装pyBADA库: pip install pyBADA")

# 添加当前目录到路径以导入aircraft_mapping
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from aircraft_mapping import get_icao_code, get_aircraft_capacity, get_cruise_mach, calculate_load_factor
    logger.info("✅ 机型映射模块导入成功")
    AIRCRAFT_MAPPING_AVAILABLE = True
except ImportError as e:
    logger.error(f"❌ 机型映射模块导入失败: {e}")
    AIRCRAFT_MAPPING_AVAILABLE = False


class FlightPhaseResult(NamedTuple):
    """飞行阶段结果数据结构"""
    phase_name: str
    fuel_kg: float
    distance_nm: float  # 改为海里单位
    time_minutes: float
    altitude_start_ft: float
    altitude_end_ft: float
    speed_mach: float
    mass_start_kg: float
    mass_end_kg: float
    # 详细轨迹数据
    trajectory_data: Optional[pd.DataFrame]


class FlightTrajectoryResult(NamedTuple):
    """完整飞行轨迹结果"""
    total_fuel_kg: float
    total_distance_km: float
    total_time_minutes: float
    climb_result: FlightPhaseResult
    cruise_result: FlightPhaseResult
    descent_result: FlightPhaseResult
    # 碳排放相关
    co2_direct_kg: float
    co2_equivalent_kg: float  # 包含NOx和H2O的CO2当量
    co2_rf_equivalent_kg: float  # 辐射强迫CO2当量
    # 详细排放指标
    co2_per_passenger_kg: float
    co2_per_km_kg: float
    co2_per_pkm_kg: float  # 每旅客公里CO2排放
    # NOx和水蒸气排放
    nox_kg: float
    h2o_kg: float
    # 综合轨迹数据
    full_trajectory: Optional[pd.DataFrame]


class PyBADAFuelCalculator:
    """使用pyBADA进行燃油消耗和碳排放计算"""
    
    # 排放因子（基于最新ICAO和IPCC标准）
    CO2_EMISSION_FACTOR = 3.16  # kg CO2 per kg fuel (更新的ICAO标准)
    NOX_EMISSION_FACTOR = 0.012  # kg NOx per kg fuel (EDB v29 标准)
    H2O_EMISSION_FACTOR = 1.237   # kg H2O per kg fuel (化学计算精确值)
    
    # 温室效应系数（IPCC AR6标准）
    NOX_GWP_100 = 273  # NOx的100年全球变暖潜能值 (IPCC AR6)
    H2O_HIGH_ALTITUDE_FACTOR = 0.85  # 高空水蒸气效应系数（对流层上层）
    RF_MULTIPLIER = 2.7  # 高空辐射强迫系数（Lee et al. 2021研究）
    
    # 高度相关的排放修正因子
    HIGH_ALTITUDE_NOX_FACTOR = 1.3  # 高空NOx形成增强因子
    CONTRAILS_FACTOR = 1.5  # 凝结尾迹效应系数
    CIRRUS_CLOUD_FACTOR = 0.8  # 卷云形成效应
    
    # 标准大气条件
    STD_PRESSURE_PA = 101325
    STD_TEMPERATURE_K = 288.15
    DELTA_TEMP = 0.0
    
    # 单位转换
    KM_TO_NM = 0.539957  # 公里转海里
    NM_TO_KM = 1.852     # 海里转公里
    
    # 燃油相关常数
    FUEL_DENSITY_KG_L = 0.804  # 航空煤油密度 kg/L
    FUEL_LHV_MJ_KG = 43.15     # 航空煤油低热值 MJ/kg
    
    def __init__(self):
        """初始化燃油计算器"""
        if not PYBADA_AVAILABLE:
            raise ImportError("pyBADA库不可用")
        
        if not AIRCRAFT_MAPPING_AVAILABLE:
            raise ImportError("机型映射模块不可用")
        
        self.aircraft_mapping = AircraftParameterAdapter()
        self._aircraft_cache = {}
        
        logger.info("✅ PyBADA燃油计算器初始化完成")
    
    def get_aircraft_model(self, aircraft_type: str):
        """获取飞机模型，支持DUMMY备用模型"""
        if aircraft_type in self._aircraft_cache:
            return self._aircraft_cache[aircraft_type]
        
        try:
            # 映射到BADA机型代码
            bada_code = self.aircraft_mapping.get_bada_aircraft_code(aircraft_type)
            if not bada_code:
                logger.warning(f"无法映射机型: {aircraft_type}，使用DUMMY模型")
                bada_code = "DUMMY"
            
            # 尝试创建特定的BADA3飞机模型
            try:
                aircraft = bada3.Bada3Aircraft(
                    badaVersion="BADA3",
                    acName=bada_code
                )
                self._aircraft_cache[aircraft_type] = aircraft
                logger.info(f"✅ 成功加载飞机模型: {aircraft_type} -> {bada_code}")
                return aircraft
                
            except Exception as specific_error:
                logger.warning(f"❌ 特定模型加载失败 {aircraft_type} -> {bada_code}: {specific_error}")
                
                # 如果特定模型失败，尝试使用DUMMY模型
                if bada_code != "DUMMY":
                    logger.info(f"🔄 为 {aircraft_type} 尝试使用DUMMY通用模型...")
                    try:
                        dummy_aircraft = bada3.Bada3Aircraft(
                            badaVersion="BADA3",
                            acName="DUMMY"
                        )
                        self._aircraft_cache[aircraft_type] = dummy_aircraft
                        logger.info(f"✅ 成功使用DUMMY模型替代: {aircraft_type}")
                        return dummy_aircraft
                    except Exception as dummy_error:
                        logger.error(f"❌ DUMMY模型也加载失败: {dummy_error}")
                        return None
                else:
                    # 连DUMMY都失败了
                    logger.error(f"❌ DUMMY模型加载失败: {specific_error}")
                    return None
            
        except Exception as e:
            logger.error(f"❌ 加载飞机模型过程中发生错误 {aircraft_type}: {e}")
            return None
    
    def calculate_trajectory_with_tcl(self, aircraft_type: str, distance_km: float, 
                                    passengers: int) -> Optional[FlightTrajectoryResult]:
        """使用TCL计算完整飞行轨迹"""
        try:
            # 获取飞机模型
            aircraft = self.get_aircraft_model(aircraft_type)
            if not aircraft:
                return None
            
            # 获取飞机基本参数
            max_mass = self.aircraft_mapping.get_aircraft_parameter(aircraft_type, 'max_mass', 70000)
            empty_mass = self.aircraft_mapping.get_aircraft_parameter(aircraft_type, 'empty_mass', 40000)
            max_passengers = self.aircraft_mapping.get_aircraft_parameter(aircraft_type, 'max_passengers', 150)
            cruise_altitude = self.aircraft_mapping.get_aircraft_parameter(aircraft_type, 'cruise_altitude', 35000)
            
            # 计算起飞重量
            passenger_mass = passengers * 90  # 90kg per passenger (including luggage)
            load_factor = min(1.0, passengers / max_passengers)
            # 燃油估算基于距离和负载系数
            fuel_mass_estimate = self._estimate_fuel_requirement(distance_km, load_factor, aircraft_type)
            
            initial_mass = empty_mass + passenger_mass + fuel_mass_estimate
            initial_mass = min(initial_mass, max_mass)
            
            # 距离分配（转换为海里）
            total_distance_nm = distance_km * self.KM_TO_NM
            climb_distance_nm = min(total_distance_nm * 0.15, 150)  # 爬升段，最多150海里
            descent_distance_nm = min(total_distance_nm * 0.15, 150)  # 下降段，最多150海里  
            cruise_distance_nm = total_distance_nm - climb_distance_nm - descent_distance_nm
            
            logger.info(f"飞行计划: 爬升 {climb_distance_nm:.1f}海里, 巡航 {cruise_distance_nm:.1f}海里, 下降 {descent_distance_nm:.1f}海里")
            
            # 计算各飞行阶段
            climb_result = self._calculate_climb_phase_tcl(
                aircraft, climb_distance_nm, initial_mass, cruise_altitude
            )
            
            cruise_result = self._calculate_cruise_phase_tcl(
                aircraft, cruise_distance_nm, climb_result.mass_end_kg, cruise_altitude
            )
            
            descent_result = self._calculate_descent_phase_tcl(
                aircraft, descent_distance_nm, cruise_result.mass_end_kg, cruise_altitude
            )
            
            # 汇总结果
            total_fuel = climb_result.fuel_kg + cruise_result.fuel_kg + descent_result.fuel_kg
            total_time = climb_result.time_minutes + cruise_result.time_minutes + descent_result.time_minutes
            
            # 合并轨迹数据
            full_trajectory = self._merge_trajectory_data([
                climb_result.trajectory_data,
                cruise_result.trajectory_data, 
                descent_result.trajectory_data
            ])
            
            # 计算详细碳排放
            emissions = self._calculate_detailed_emissions(total_fuel, passengers, distance_km, cruise_altitude)
            
            return FlightTrajectoryResult(
                total_fuel_kg=total_fuel,
                total_distance_km=distance_km,
                total_time_minutes=total_time,
                climb_result=climb_result,
                cruise_result=cruise_result,
                descent_result=descent_result,
                full_trajectory=full_trajectory,
                **emissions
            )
            
        except Exception as e:
            logger.error(f"❌ TCL轨迹计算失败 {aircraft_type}: {e}")
            return None
    
    def _estimate_fuel_requirement(self, distance_km: float, load_factor: float, 
                                 aircraft_type: str) -> float:
        """估算燃油需求"""
        # 基础燃油消耗率 (kg/km)
        base_consumption = 3.0
        
        # 距离系数（长途航班效率更高）
        distance_factor = 1.0 if distance_km < 1000 else 0.9 if distance_km < 3000 else 0.8
        
        # 负载系数调整
        load_adjustment = 0.7 + 0.3 * load_factor
        
        # 储备燃油 (5% + 45分钟应急)
        estimated_fuel = distance_km * base_consumption * distance_factor * load_adjustment
        reserve_fuel = estimated_fuel * 0.05 + 300  # 300kg for 45min reserve
        
        return estimated_fuel + reserve_fuel
    
    def _calculate_climb_phase_tcl(self, aircraft, distance_nm: float, 
                                 initial_mass: float, target_altitude: float) -> FlightPhaseResult:
        """使用TCL计算爬升阶段"""
        try:
            # 爬升参数
            initial_altitude = 1500  # 起始高度 ft
            climb_speed_cas = 250    # 校准空速 kt (低空)
            climb_mach = 0.78       # 高空马赫数
            
            # 使用constantSpeedRating进行爬升计算
            trajectory_df = tcl.constantSpeedRating(
                AC=aircraft,
                speedType='CAS',  # 低空使用校准空速
                v=climb_speed_cas,
                Hp_init=initial_altitude,
                Hp_final=target_altitude,
                m_init=initial_mass,
                DeltaTemp=self.DELTA_TEMP,
                wS=0.0,  # 无风
                phase='Climb',
                config='CR'  # 巡航配置
            )
            
            # 提取关键数据
            if trajectory_df is not None and not trajectory_df.empty:
                total_fuel = trajectory_df['FUELCONSUMED'].iloc[-1]  # 总燃油消耗
                total_time = trajectory_df['time'].iloc[-1] / 60  # 转换为分钟
                final_mass = initial_mass - total_fuel
                actual_distance = trajectory_df['dist'].iloc[-1]  # 实际飞行距离（海里）
                
                logger.info(f"爬升阶段完成: 燃油 {total_fuel:.1f}kg, 时间 {total_time:.1f}分钟, 距离 {actual_distance:.1f}海里")
            else:
                raise ValueError("TCL计算返回空结果")
            
            return FlightPhaseResult(
                phase_name="climb",
                fuel_kg=total_fuel,
                distance_nm=actual_distance,
                time_minutes=total_time,
                altitude_start_ft=initial_altitude,
                altitude_end_ft=target_altitude,
                speed_mach=climb_mach,
                mass_start_kg=initial_mass,
                mass_end_kg=final_mass,
                trajectory_data=trajectory_df
            )
            
        except Exception as e:
            logger.warning(f"TCL爬升计算失败，使用备用方法: {e}")
            return self._fallback_climb_calculation(distance_nm, initial_mass, target_altitude)
    
    def _calculate_cruise_phase_tcl(self, aircraft, distance_nm: float,
                                  initial_mass: float, cruise_altitude: float) -> FlightPhaseResult:
        """使用TCL计算巡航阶段"""
        try:
            cruise_mach = 0.82  # 典型巡航马赫数
            
            # 使用constantSpeedLevel进行巡航计算
            # 参数格式：AC, speedType, v, Hp_init, lengthType, length, m_init, DeltaTemp, [其他参数]
            trajectory_df = tcl.constantSpeedLevel(
                AC=aircraft,
                speedType='M',                # 速度类型：马赫数
                v=cruise_mach,               # 马赫数
                Hp_init=cruise_altitude,     # 巡航高度 ft
                lengthType='distance',       # 长度类型：距离
                length=distance_nm,          # 距离（海里）
                m_init=initial_mass,         # 初始质量 kg
                DeltaTemp=self.DELTA_TEMP,   # 温度偏差
                wS=0.0,                      # 风速（无风）
                stepClimb=False,             # 不进行阶梯爬升
                config='CR'                  # 配置：巡航
            )
            
            # 提取关键数据
            if trajectory_df is not None and not trajectory_df.empty:
                total_fuel = trajectory_df['FUELCONSUMED'].iloc[-1]
                total_time = trajectory_df['time'].iloc[-1] / 60  # 转换为分钟
                final_mass = initial_mass - total_fuel
                actual_distance = trajectory_df['dist'].iloc[-1]
                
                # 添加阶段标识到轨迹数据
                trajectory_df = trajectory_df.copy()
                trajectory_df['phase'] = 'cruise'
                trajectory_df['phase_time'] = trajectory_df['time']
                
                logger.info(f"巡航阶段完成: 燃油 {total_fuel:.1f}kg, 时间 {total_time:.1f}分钟, 距离 {actual_distance:.1f}海里")
            else:
                raise ValueError("TCL计算返回空结果")
            
            return FlightPhaseResult(
                phase_name="cruise",
                fuel_kg=total_fuel,
                distance_nm=actual_distance,
                time_minutes=total_time,
                altitude_start_ft=cruise_altitude,
                altitude_end_ft=cruise_altitude,
                speed_mach=cruise_mach,
                mass_start_kg=initial_mass,
                mass_end_kg=final_mass,
                trajectory_data=trajectory_df
            )
            
        except Exception as e:
            logger.warning(f"TCL巡航计算失败，使用备用方法: {e}")
            return self._fallback_cruise_calculation(distance_nm, initial_mass, cruise_altitude)
    
    def _calculate_descent_phase_tcl(self, aircraft, distance_nm: float,
                                   initial_mass: float, cruise_altitude: float) -> FlightPhaseResult:
        """使用TCL计算下降阶段"""
        try:
            final_altitude = 2000    # 最终高度 ft (进近高度)
            descent_mach = 0.78     # 下降马赫数
            descent_cas = 250       # 低空校准空速
            
            # 使用constantSpeedRating进行下降计算
            # 下降阶段的速度处理：高空使用马赫数，低空切换到校准空速
            trajectory_df = tcl.constantSpeedRating(
                AC=aircraft,
                Hp_init=cruise_altitude,     # 初始高度 ft
                Hp_final=final_altitude,     # 最终高度 ft
                speedType='M',               # 速度类型：马赫数（高空）
                v=descent_mach,              # 马赫数
                m_init=initial_mass,         # 初始质量 kg
                DeltaTemp=self.DELTA_TEMP,   # 温度偏差
                wS=0.0,                      # 风速（无风）
                config='CR'                  # 配置：巡航（下降时发动机推力减小）
            )
            
            # 提取关键数据
            if trajectory_df is not None and not trajectory_df.empty:
                total_fuel = trajectory_df['FUELCONSUMED'].iloc[-1]
                total_time = trajectory_df['time'].iloc[-1] / 60  # 转换为分钟
                final_mass = initial_mass - total_fuel
                actual_distance = trajectory_df['dist'].iloc[-1]
                
                # 添加阶段标识到轨迹数据
                trajectory_df = trajectory_df.copy()
                trajectory_df['phase'] = 'descent'
                trajectory_df['phase_time'] = trajectory_df['time']
                
                logger.info(f"下降阶段完成: 燃油 {total_fuel:.1f}kg, 时间 {total_time:.1f}分钟, 距离 {actual_distance:.1f}海里")
            else:
                raise ValueError("TCL计算返回空结果")
            
            return FlightPhaseResult(
                phase_name="descent",
                fuel_kg=total_fuel,
                distance_nm=actual_distance,
                time_minutes=total_time,
                altitude_start_ft=cruise_altitude,
                altitude_end_ft=final_altitude,
                speed_mach=descent_mach,
                mass_start_kg=initial_mass,
                mass_end_kg=final_mass,
                trajectory_data=trajectory_df
            )
            
        except Exception as e:
            logger.warning(f"TCL下降计算失败，使用备用方法: {e}")
            return self._fallback_descent_calculation(distance_nm, initial_mass, cruise_altitude)
    
    def _fallback_climb_calculation(self, distance_nm: float, initial_mass: float, 
                                  target_altitude: float) -> FlightPhaseResult:
        """备用爬升计算方法"""
        fuel_per_nm = 15  # kg/nm for climb
        time_per_nm = 0.1  # hours per nm
        
        fuel_used = distance_nm * fuel_per_nm
        time_minutes = distance_nm * time_per_nm * 60
        
        return FlightPhaseResult(
            phase_name="climb",
            fuel_kg=fuel_used,
            distance_nm=distance_nm,
            time_minutes=time_minutes,
            altitude_start_ft=1500,
            altitude_end_ft=target_altitude,
            speed_mach=0.78,
            mass_start_kg=initial_mass,
            mass_end_kg=initial_mass - fuel_used,
            trajectory_data=None
        )
    
    def _fallback_cruise_calculation(self, distance_nm: float, initial_mass: float,
                                   cruise_altitude: float) -> FlightPhaseResult:
        """备用巡航计算方法"""
        fuel_per_nm = 5   # kg/nm for cruise
        speed_kt = 450    # 典型巡航速度
        
        fuel_used = distance_nm * fuel_per_nm
        time_minutes = (distance_nm / speed_kt) * 60
        
        return FlightPhaseResult(
            phase_name="cruise",
            fuel_kg=fuel_used,
            distance_nm=distance_nm,
            time_minutes=time_minutes,
            altitude_start_ft=cruise_altitude,
            altitude_end_ft=cruise_altitude,
            speed_mach=0.82,
            mass_start_kg=initial_mass,
            mass_end_kg=initial_mass - fuel_used,
            trajectory_data=None
        )
    
    def _fallback_descent_calculation(self, distance_nm: float, initial_mass: float,
                                    cruise_altitude: float) -> FlightPhaseResult:
        """备用下降计算方法"""
        fuel_per_nm = 3   # kg/nm for descent (lower than cruise)
        time_per_nm = 0.08  # hours per nm
        
        fuel_used = distance_nm * fuel_per_nm
        time_minutes = distance_nm * time_per_nm * 60
        
        return FlightPhaseResult(
            phase_name="descent",
            fuel_kg=fuel_used,
            distance_nm=distance_nm,
            time_minutes=time_minutes,
            altitude_start_ft=cruise_altitude,
            altitude_end_ft=2000,
            speed_mach=0.78,
            mass_start_kg=initial_mass,
            mass_end_kg=initial_mass - fuel_used,
            trajectory_data=None
        )
    
    def _merge_trajectory_data(self, trajectory_list) -> Optional[pd.DataFrame]:
        """合并各阶段的轨迹数据"""
        try:
            valid_trajectories = [df for df in trajectory_list if df is not None and not df.empty]
            if not valid_trajectories:
                return None
            
            # 调整时间和距离为累积值
            merged_df = pd.DataFrame()
            time_offset = 0
            distance_offset = 0
            
            for i, df in enumerate(valid_trajectories):
                df_copy = df.copy()
                df_copy['time'] += time_offset
                df_copy['dist'] += distance_offset
                df_copy['phase'] = ['climb', 'cruise', 'descent'][i]
                
                if merged_df.empty:
                    merged_df = df_copy
                else:
                    merged_df = pd.concat([merged_df, df_copy], ignore_index=True)
                
                time_offset = df_copy['time'].iloc[-1]
                distance_offset = df_copy['dist'].iloc[-1]
            
            return merged_df
        except Exception as e:
            logger.warning(f"轨迹数据合并失败: {e}")
            return None
    
    def _calculate_detailed_emissions(self, fuel_kg: float, passengers: int, 
                                    distance_km: float, cruise_altitude: float) -> Dict:
        """计算详细的排放指标，包括高空效应和环境影响"""
        
        # 基础排放计算
        co2_direct = fuel_kg * self.CO2_EMISSION_FACTOR
        nox_kg = fuel_kg * self.NOX_EMISSION_FACTOR
        h2o_kg = fuel_kg * self.H2O_EMISSION_FACTOR
        
        # 其他排放物质（基于ICAO Engine Emissions Database）
        co_kg = fuel_kg * 0.0008   # 一氧化碳
        hc_kg = fuel_kg * 0.0002   # 碳氢化合物
        so2_kg = fuel_kg * 0.0008  # 二氧化硫
        pm_kg = fuel_kg * 0.00004  # 颗粒物质
        
        # 高空效应修正因子
        altitude_factor = self._get_altitude_emission_factor(cruise_altitude)
        
        # NOx的高空效应和辐射强迫
        nox_high_altitude = nox_kg * self.HIGH_ALTITUDE_NOX_FACTOR * altitude_factor
        nox_co2_equivalent = nox_high_altitude * self.NOX_GWP_100
        
        # 水蒸气的高空效应（主要在对流层上层）
        h2o_effect = h2o_kg * self.H2O_HIGH_ALTITUDE_FACTOR * altitude_factor
        
        # 凝结尾迹和卷云效应（仅在高空）
        contrails_co2_equiv = 0.0
        cirrus_co2_equiv = 0.0
        if cruise_altitude > 25000:  # 8000m以上
            contrails_co2_equiv = co2_direct * self.CONTRAILS_FACTOR * (cruise_altitude / 35000)
            cirrus_co2_equiv = co2_direct * self.CIRRUS_CLOUD_FACTOR * (cruise_altitude / 35000)
        
        # 总CO2当量（包含所有温室效应）
        co2_equivalent = (co2_direct + 
                         nox_co2_equivalent + 
                         h2o_effect + 
                         contrails_co2_equiv + 
                         cirrus_co2_equiv)
        
        # 辐射强迫效应总和
        rf_multiplier = self._get_radiative_forcing_multiplier(cruise_altitude)
        co2_rf_equivalent = co2_equivalent * rf_multiplier
        
        # 单位排放指标
        passengers_actual = max(1, passengers)
        distance_actual = max(1, distance_km)
        
        co2_per_passenger = co2_direct / passengers_actual
        co2_per_km = co2_direct / distance_actual
        co2_per_pkm = co2_direct / (passengers_actual * distance_actual)
        
        # 燃油效率指标
        fuel_efficiency_l_per_100km = (fuel_kg / self.FUEL_DENSITY_KG_L) / distance_actual * 100
        energy_intensity_mj_per_pkm = (fuel_kg * self.FUEL_LHV_MJ_KG) / (passengers_actual * distance_actual)
        
        return {
            # 直接排放
            'co2_direct_kg': co2_direct,
            'nox_kg': nox_kg,
            'h2o_kg': h2o_kg,
            'co_kg': co_kg,
            'hc_kg': hc_kg,
            'so2_kg': so2_kg,
            'pm_kg': pm_kg,
            
            # 气候影响
            'co2_equivalent_kg': co2_equivalent,
            'co2_rf_equivalent_kg': co2_rf_equivalent,
            'nox_co2_equivalent_kg': nox_co2_equivalent,
            'contrails_co2_equivalent_kg': contrails_co2_equiv,
            'cirrus_co2_equivalent_kg': cirrus_co2_equiv,
            
            # 单位指标
            'co2_per_passenger_kg': co2_per_passenger,
            'co2_per_km_kg': co2_per_km,
            'co2_per_pkm_kg': co2_per_pkm,
            
            # 效率指标
            'fuel_efficiency_l_per_100km': fuel_efficiency_l_per_100km,
            'energy_intensity_mj_per_pkm': energy_intensity_mj_per_pkm,
            'carbon_intensity_kg_co2_per_pkm': co2_per_pkm,
            
            # 环境评级
            'environmental_impact_score': self._calculate_environmental_score(
                co2_per_pkm, fuel_efficiency_l_per_100km, cruise_altitude
            )
        }
    
    def _get_altitude_emission_factor(self, altitude_ft: float) -> float:
        """根据高度计算排放修正因子"""
        if altitude_ft < 20000:
            return 1.0
        elif altitude_ft < 30000:
            return 1.1
        elif altitude_ft < 40000:
            return 1.3
        else:
            return 1.5
    
    def _get_radiative_forcing_multiplier(self, altitude_ft: float) -> float:
        """根据高度计算辐射强迫乘子"""
        if altitude_ft < 25000:
            return 1.5
        elif altitude_ft < 35000:
            return 2.7
        else:
            return 3.2
    
    def _calculate_environmental_score(self, co2_per_pkm: float, 
                                     fuel_efficiency: float, altitude: float) -> str:
        """计算环境影响评级 (A-F)"""
        # 基于CO2强度的评分标准
        if co2_per_pkm < 0.08:
            base_score = 5  # A
        elif co2_per_pkm < 0.12:
            base_score = 4  # B
        elif co2_per_pkm < 0.16:
            base_score = 3  # C
        elif co2_per_pkm < 0.20:
            base_score = 2  # D
        elif co2_per_pkm < 0.25:
            base_score = 1  # E
        else:
            base_score = 0  # F
        
        # 高空效应惩罚
        if altitude > 35000:
            base_score = max(0, base_score - 1)
        
        score_map = {0: 'F', 1: 'E', 2: 'D', 3: 'C', 4: 'B', 5: 'A'}
        return score_map[base_score]
    
    def calculate_single_flight(self, aircraft_type: str, distance_km: float, 
                              passengers: int) -> Dict:
        """计算单个航班的燃油消耗和排放"""
        try:
            result = self.calculate_trajectory_with_tcl(aircraft_type, distance_km, passengers)
            
            if result is None:
                logger.warning(f"计算失败，使用备用方法: {aircraft_type}")
                return self._fallback_single_flight_calculation(aircraft_type, distance_km, passengers)
            
            # 格式化结果
            formatted_result = {
                'aircraft_type': aircraft_type,
                'distance_km': distance_km,
                'passengers': passengers,
                
                # 燃油消耗
                'total_fuel_kg': result.total_fuel_kg,
                'fuel_per_km': result.total_fuel_kg / distance_km,
                'fuel_per_passenger': result.total_fuel_kg / max(1, passengers),
                
                # 飞行时间
                'total_time_minutes': result.total_time_minutes,
                'climb_time_minutes': result.climb_result.time_minutes,
                'cruise_time_minutes': result.cruise_result.time_minutes,
                'descent_time_minutes': result.descent_result.time_minutes,
                
                # 各阶段燃油
                'climb_fuel_kg': result.climb_result.fuel_kg,
                'cruise_fuel_kg': result.cruise_result.fuel_kg,
                'descent_fuel_kg': result.descent_result.fuel_kg,
                
                # 排放指标
                'co2_direct_kg': result.co2_direct_kg,
                'co2_equivalent_kg': result.co2_equivalent_kg,
                'co2_rf_equivalent_kg': result.co2_rf_equivalent_kg,
                'co2_per_passenger_kg': result.co2_per_passenger_kg,
                'co2_per_km_kg': result.co2_per_km_kg,
                'co2_per_pkm_kg': result.co2_per_pkm_kg,
                'nox_kg': result.nox_kg,
                'h2o_kg': result.h2o_kg,
                
                # 效率指标
                'fuel_efficiency_l_per_100km': result.fuel_efficiency_l_per_100km,
                'energy_intensity_mj_per_pkm': result.energy_intensity_mj_per_pkm,
                'carbon_intensity_kg_co2_per_pkm': result.co2_per_pkm_kg,
                
                # 计算状态
                'calculation_successful': True,
                'used_tcl': True
            }
            
            logger.info(f"✅ 航班计算完成: {aircraft_type}, 燃油 {result.total_fuel_kg:.1f}kg, CO2 {result.co2_direct_kg:.1f}kg")
            return formatted_result
            
        except Exception as e:
            logger.error(f"❌ 航班计算失败 {aircraft_type}: {e}")
            return self._fallback_single_flight_calculation(aircraft_type, distance_km, passengers)
    
    def _fallback_single_flight_calculation(self, aircraft_type: str, distance_km: float,
                                          passengers: int) -> Dict:
        """备用单航班计算方法 - 基于真实航空工程数据的改进算法"""
        
        logger.info(f"🔧 使用备用计算方法: {aircraft_type}, {distance_km}km, {passengers}人")
        
        # 获取机型基础参数
        bada_code = self.aircraft_mapping.get_bada_aircraft_code(aircraft_type) or "A320"
        aircraft_params = self.aircraft_mapping.AIRCRAFT_PARAMETERS.get(bada_code, 
                                                                       self.aircraft_mapping.AIRCRAFT_PARAMETERS["A320"])
        
        max_passengers = aircraft_params['max_passengers']
        empty_mass = aircraft_params['empty_mass']
        max_mass = aircraft_params['max_mass']
        cruise_altitude = aircraft_params['cruise_altitude']
        
        # 计算负载系数和实际质量
        load_factor = min(1.0, passengers / max_passengers)
        passenger_mass = passengers * 90  # 包含行李的乘客重量
        
        # 改进的燃油消耗模型（基于实际航空数据）
        # 基础消耗率根据机型调整
        if 'A380' in bada_code or 'B777' in bada_code or 'B787' in bada_code:
            # 宽体机
            base_fuel_rate = 4.5  # kg/km
            taxi_fuel = 300       # 滑行燃油
            reserve_factor = 0.08 # 储备燃油系数
        elif 'B737' in bada_code or 'A320' in bada_code or 'A319' in bada_code:
            # 窄体机
            base_fuel_rate = 3.2  # kg/km
            taxi_fuel = 200
            reserve_factor = 0.06
        elif 'E190' in bada_code or 'CRJ' in bada_code:
            # 支线飞机
            base_fuel_rate = 2.8  # kg/km
            taxi_fuel = 150
            reserve_factor = 0.05
        else:
            # 默认（中型客机）
            base_fuel_rate = 3.2
            taxi_fuel = 200
            reserve_factor = 0.06
        
        # 距离效率修正（长途航班更高效）
        if distance_km < 500:
            distance_efficiency = 1.3    # 短途效率低
        elif distance_km < 1500:
            distance_efficiency = 1.1    # 中程
        elif distance_km < 4000:
            distance_efficiency = 1.0    # 长途基准
        else:
            distance_efficiency = 0.95   # 超长途效率高
        
        # 负载系数对燃油的影响
        load_adjustment = 0.75 + 0.35 * load_factor  # 空载75%，满载110%
        
        # 高度效率修正
        altitude_efficiency = min(1.0, cruise_altitude / 35000) * 0.9 + 0.1
        
        # 计算基础燃油消耗
        cruise_fuel = distance_km * base_fuel_rate * distance_efficiency * load_adjustment * altitude_efficiency
        
        # 爬升和下降燃油（基于高度和距离）
        climb_distance = min(distance_km * 0.15, 200)  # 爬升距离
        descent_distance = min(distance_km * 0.15, 200)  # 下降距离
        
        climb_fuel_rate = base_fuel_rate * 2.5  # 爬升燃油率是巡航的2.5倍
        descent_fuel_rate = base_fuel_rate * 0.8  # 下降燃油率是巡航的0.8倍
        
        climb_fuel = climb_distance * climb_fuel_rate * load_adjustment
        descent_fuel = descent_distance * descent_fuel_rate * load_adjustment
        
        # 总燃油消耗
        operational_fuel = cruise_fuel + climb_fuel + descent_fuel + taxi_fuel
        reserve_fuel = operational_fuel * reserve_factor
        total_fuel = operational_fuel + reserve_fuel
        
        # 飞行时间估算（改进）
        if distance_km < 500:
            avg_speed_kmh = 420  # 短途平均速度低
        elif distance_km < 2000:
            avg_speed_kmh = 480  # 中程
        else:
            avg_speed_kmh = 520  # 长途
        
        flight_time_hours = distance_km / avg_speed_kmh
        total_time_minutes = flight_time_hours * 60 + 30  # 加上滑行时间
        
        # 各阶段时间分配
        climb_time = min(total_time_minutes * 0.2, 25)
        descent_time = min(total_time_minutes * 0.2, 25)
        cruise_time = total_time_minutes - climb_time - descent_time
        
        # 改进的排放计算（包含高空效应）
        co2_direct = total_fuel * self.CO2_EMISSION_FACTOR
        
        # 高空效应修正
        altitude_factor = self._get_altitude_emission_factor(cruise_altitude)
        nox_kg = total_fuel * self.NOX_EMISSION_FACTOR * altitude_factor
        h2o_kg = total_fuel * self.H2O_EMISSION_FACTOR
        
        # 高空辐射强迫效应
        rf_multiplier = self._get_radiative_forcing_multiplier(cruise_altitude)
        co2_equivalent = co2_direct * rf_multiplier
        
        # 单位指标
        co2_per_passenger = co2_direct / max(1, passengers)
        co2_per_km = co2_direct / distance_km
        co2_per_pkm = co2_direct / max(1, passengers * distance_km)
        
        # 燃油效率
        fuel_efficiency_l_per_100km = (total_fuel / self.FUEL_DENSITY_KG_L) / distance_km * 100
        energy_intensity = (total_fuel * self.FUEL_LHV_MJ_KG) / max(1, passengers * distance_km)
        
        result = {
            'aircraft_type': aircraft_type,
            'distance_km': distance_km,
            'passengers': passengers,
            
            # 燃油消耗详细信息
            'total_fuel_kg': total_fuel,
            'cruise_fuel_kg': cruise_fuel,
            'climb_fuel_kg': climb_fuel,
            'descent_fuel_kg': descent_fuel,
            'taxi_fuel_kg': taxi_fuel,
            'reserve_fuel_kg': reserve_fuel,
            'fuel_per_km': total_fuel / distance_km,
            'fuel_per_passenger': total_fuel / max(1, passengers),
            
            # 飞行时间
            'total_time_minutes': total_time_minutes,
            'climb_time_minutes': climb_time,
            'cruise_time_minutes': cruise_time,
            'descent_time_minutes': descent_time,
            
            # 排放指标
            'co2_direct_kg': co2_direct,
            'co2_equivalent_kg': co2_equivalent,
            'co2_rf_equivalent_kg': co2_equivalent,  # 备用方法中简化处理
            'co2_per_passenger_kg': co2_per_passenger,
            'co2_per_km_kg': co2_per_km,
            'co2_per_pkm_kg': co2_per_pkm,
            'nox_kg': nox_kg,
            'h2o_kg': h2o_kg,
            
            # 效率指标
            'fuel_efficiency_l_per_100km': fuel_efficiency_l_per_100km,
            'energy_intensity_mj_per_pkm': energy_intensity,
            'carbon_intensity_kg_co2_per_pkm': co2_per_pkm,
            
            # 飞行参数
            'load_factor': load_factor,
            'cruise_altitude_ft': cruise_altitude,
            'average_speed_kmh': avg_speed_kmh,
            
            # 计算状态
            'calculation_successful': True,
            'used_tcl': False,
            'calculation_method': 'fallback_improved',
            'bada_code_used': bada_code
        }
        
        logger.info(f"✅ 备用计算完成: {aircraft_type}, 燃油 {total_fuel:.1f}kg, CO2 {co2_direct:.1f}kg")
        return result


def process_flight_data_with_pybada(df: pd.DataFrame) -> pd.DataFrame:
    """处理航班数据并计算燃油消耗和排放"""
    if not PYBADA_AVAILABLE:
        logger.error("pyBADA库不可用，无法处理数据")
        return df
    
    calculator = PyBADAFuelCalculator()
    results = []
    
    for idx, row in df.iterrows():
        try:
            aircraft_type = row.get('aircraft_type', 'A320')
            distance_km = row.get('distance_km', 0)
            passengers = row.get('passengers', 150)
            
            if distance_km <= 0:
                logger.warning(f"第{idx}行距离无效: {distance_km}")
                continue
            
            result = calculator.calculate_single_flight(aircraft_type, distance_km, passengers)
            result['original_index'] = idx
            results.append(result)
            
            if idx % 10 == 0:
                logger.info(f"已处理 {idx+1}/{len(df)} 条记录")
                
        except Exception as e:
            logger.error(f"处理第{idx}行数据时出错: {e}")
            continue
    
    if not results:
        logger.warning("没有成功处理任何数据")
        return df
    
    # 创建结果DataFrame
    results_df = pd.DataFrame(results)
    
    # 合并原始数据和计算结果
    final_df = df.copy()
    for col in results_df.columns:
        if col != 'original_index':
            final_df[col] = None
    
    for _, result_row in results_df.iterrows():
        idx = result_row['original_index']
        for col in results_df.columns:
            if col != 'original_index':
                final_df.loc[idx, col] = result_row[col]
    
    logger.info(f"✅ 成功处理 {len(results)} 条航班数据")
    return final_df


class AircraftParameterAdapter:
    """机型参数适配器，提供统一的接口"""
    
    # 机型参数映射（基于pyBADA和ICAO标准）
    AIRCRAFT_PARAMETERS = {
        # DUMMY通用模型（用于未知机型的备用方案）
        'DUMMY': {
            'max_mass': 78000,  # kg - 中型客机标准
            'empty_mass': 42000,  # kg
            'max_passengers': 160,
            'cruise_altitude': 35000,  # ft
            'cruise_mach': 0.78
        },
        'A319': {
            'max_mass': 75500,  # kg
            'empty_mass': 40800,  # kg
            'max_passengers': 140,
            'cruise_altitude': 35000,  # ft
            'cruise_mach': 0.78
        },
        'A320': {
            'max_mass': 78000,
            'empty_mass': 42400,
            'max_passengers': 160,
            'cruise_altitude': 35000,
            'cruise_mach': 0.78
        },
        'A321': {
            'max_mass': 93500,
            'empty_mass': 48500,
            'max_passengers': 200,
            'cruise_altitude': 35000,
            'cruise_mach': 0.78
        },
        'A330': {
            'max_mass': 242000,
            'empty_mass': 120000,
            'max_passengers': 290,
            'cruise_altitude': 37000,
            'cruise_mach': 0.82
        },
        'A380': {
            'max_mass': 575000,
            'empty_mass': 280000,
            'max_passengers': 550,
            'cruise_altitude': 39000,
            'cruise_mach': 0.85
        },
        'B737': {
            'max_mass': 79000,
            'empty_mass': 41000,
            'max_passengers': 160,
            'cruise_altitude': 35000,
            'cruise_mach': 0.78
        },
        'B757': {
            'max_mass': 116000,
            'empty_mass': 58000,
            'max_passengers': 200,
            'cruise_altitude': 37000,
            'cruise_mach': 0.80
        },
        'B777': {
            'max_mass': 347000,
            'empty_mass': 138800,
            'max_passengers': 350,
            'cruise_altitude': 39000,
            'cruise_mach': 0.84
        },
        'B787': {
            'max_mass': 254000,
            'empty_mass': 120000,
            'max_passengers': 290,
            'cruise_altitude': 41000,
            'cruise_mach': 0.85
        },
        'E190': {
            'max_mass': 51800,
            'empty_mass': 28000,
            'max_passengers': 100,
            'cruise_altitude': 35000,
            'cruise_mach': 0.78
        },
        'CRJ9': {
            'max_mass': 38000,
            'empty_mass': 24300,
            'max_passengers': 90,
            'cruise_altitude': 35000,
            'cruise_mach': 0.78
        }
    }
    
    def get_bada_aircraft_code(self, aircraft_type: str) -> Optional[str]:
        """获取BADA机型代码，支持中文机型名称和备用方案"""
        if AIRCRAFT_MAPPING_AVAILABLE:
            bada_code = get_icao_code(aircraft_type)
            if bada_code:
                return bada_code
        
        # 扩展的机型名称映射（支持中文）
        aircraft_type_clean = str(aircraft_type).lower().strip()
        
        # 空客系列
        if any(keyword in aircraft_type_clean for keyword in ['a320', '空客320', 'airbus320', 'a-320']):
            return 'A320'
        elif any(keyword in aircraft_type_clean for keyword in ['a319', '空客319', 'airbus319', 'a-319']):
            return 'A319'
        elif any(keyword in aircraft_type_clean for keyword in ['a321', '空客321', 'airbus321', 'a-321']):
            return 'A321'
        elif any(keyword in aircraft_type_clean for keyword in ['a330', '空客330', 'airbus330', 'a-330']):
            return 'A330'
        elif any(keyword in aircraft_type_clean for keyword in ['a380', '空客380', 'airbus380', 'a-380']):
            return 'A380'
        elif any(keyword in aircraft_type_clean for keyword in ['a350', '空客350', 'airbus350', 'a-350']):
            return 'A359'  # BADA中A350的代码
        
        # 波音系列
        elif any(keyword in aircraft_type_clean for keyword in ['b737', '波音737', 'boeing737', 'b-737', '737']):
            return 'B737'
        elif any(keyword in aircraft_type_clean for keyword in ['b738', '波音738', 'boeing738', 'b-738', '738']):
            return 'B738'  # 波音737-800
        elif any(keyword in aircraft_type_clean for keyword in ['b757', '波音757', 'boeing757', 'b-757', '757']):
            return 'B757'
        elif any(keyword in aircraft_type_clean for keyword in ['b767', '波音767', 'boeing767', 'b-767', '767']):
            return 'B767'
        elif any(keyword in aircraft_type_clean for keyword in ['b777', '波音777', 'boeing777', 'b-777', '777']):
            return 'B777'
        elif any(keyword in aircraft_type_clean for keyword in ['b787', '波音787', 'boeing787', 'b-787', '787']):
            return 'B787'
        
        # 支线飞机
        elif any(keyword in aircraft_type_clean for keyword in ['erj', 'emb190', 'e190', 'erj-190', '巴西航空190']):
            return 'E190'
        elif any(keyword in aircraft_type_clean for keyword in ['crj', 'crj9', 'crj900', 'crj-900', '庞巴迪crj900']):
            return 'CRJ9'
        elif any(keyword in aircraft_type_clean for keyword in ['atr', 'atr72', 'atr-72']):
            return 'AT72'
        elif any(keyword in aircraft_type_clean for keyword in ['dash', 'dh8', 'q400']):
            return 'DH8D'
        
        # 宽体机
        elif any(keyword in aircraft_type_clean for keyword in ['md11', 'md-11']):
            return 'MD11'
        elif any(keyword in aircraft_type_clean for keyword in ['dc10', 'dc-10']):
            return 'DC10'
        
        # 货机
        elif any(keyword in aircraft_type_clean for keyword in ['747f', '747-f', 'b747f']):
            return 'B74F'
        elif any(keyword in aircraft_type_clean for keyword in ['md11f', 'md-11f']):
            return 'M11F'
        
        # 如果都不匹配，记录警告并返回None（将在上级函数中使用DUMMY）
        logger.warning(f"未找到匹配的BADA机型代码: {aircraft_type}，将使用DUMMY通用模型")
        return None
    
    def get_aircraft_parameter(self, aircraft_type: str, parameter: str, default_value):
        """获取飞机参数，支持DUMMY备用方案"""
        bada_code = self.get_bada_aircraft_code(aircraft_type)
        
        # 首先尝试获取特定机型的参数
        if bada_code and bada_code in self.AIRCRAFT_PARAMETERS:
            return self.AIRCRAFT_PARAMETERS[bada_code].get(parameter, default_value)
        
        # 如果特定机型不存在，使用DUMMY通用模型
        if 'DUMMY' in self.AIRCRAFT_PARAMETERS:
            dummy_value = self.AIRCRAFT_PARAMETERS['DUMMY'].get(parameter, default_value)
            logger.debug(f"使用DUMMY模型参数 {parameter}={dummy_value} for {aircraft_type}")
            return dummy_value
        
        # 最后才使用默认值
        logger.debug(f"使用默认参数 {parameter}={default_value} for {aircraft_type}")
        return default_value


if __name__ == "__main__":
    # 测试代码
    if PYBADA_AVAILABLE:
        calculator = PyBADAFuelCalculator()
        
        # 测试单个航班计算
        test_result = calculator.calculate_single_flight("A320", 1000, 150)
        print("测试结果:")
        for key, value in test_result.items():
            print(f"  {key}: {value}")
    else:
        print("pyBADA库不可用，无法进行测试") 