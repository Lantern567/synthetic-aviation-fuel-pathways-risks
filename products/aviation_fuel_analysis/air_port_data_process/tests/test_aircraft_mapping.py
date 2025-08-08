"""
测试航空器映射模块的单元测试
"""
import unittest
import sys
import os

# 添加src目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from aircraft_mapping import (
    get_icao_code,
    get_aircraft_capacity,
    get_cruise_mach,
    calculate_load_factor
)

class TestAircraftMapping(unittest.TestCase):
    
    def test_get_icao_code_boeing(self):
        """测试波音机型映射"""
        self.assertEqual(get_icao_code('波音737(中)'), 'B737')
        self.assertEqual(get_icao_code('波音737'), 'B737')
        self.assertEqual(get_icao_code('波音777(大)'), 'B777')
        self.assertEqual(get_icao_code('波音787'), 'B787')
    
    def test_get_icao_code_airbus(self):
        """测试空客机型映射"""
        self.assertEqual(get_icao_code('空客319(中)'), 'A319')
        self.assertEqual(get_icao_code('空客320'), 'A320')
        self.assertEqual(get_icao_code('空客321(窄体机)'), 'A321')
        self.assertEqual(get_icao_code('空客330(宽体机)'), 'A330')
    
    def test_get_icao_code_unknown(self):
        """测试未知机型默认映射"""
        self.assertEqual(get_icao_code('未知机型'), 'B737')
        self.assertEqual(get_icao_code(''), 'B737')
    
    def test_get_aircraft_capacity(self):
        """测试载客量获取"""
        self.assertEqual(get_aircraft_capacity('B737'), 160)
        self.assertEqual(get_aircraft_capacity('A380'), 550)
        self.assertEqual(get_aircraft_capacity('E190'), 100)
        self.assertEqual(get_aircraft_capacity('UNKNOWN'), 160)  # 默认值
    
    def test_get_cruise_mach(self):
        """测试巡航马赫数获取"""
        self.assertEqual(get_cruise_mach('B737'), 0.78)
        self.assertEqual(get_cruise_mach('B787'), 0.85)
        self.assertEqual(get_cruise_mach('A380'), 0.85)
        self.assertEqual(get_cruise_mach('UNKNOWN'), 0.78)  # 默认值
    
    def test_calculate_load_factor(self):
        """测试载客率计算"""
        # 正常载客率
        self.assertEqual(calculate_load_factor(80, 'B737'), 0.5)  # 80/160 = 0.5
        self.assertEqual(calculate_load_factor(100, 'E190'), 1.0)  # 100/100 = 1.0
        
        # 超载情况
        self.assertEqual(calculate_load_factor(200, 'B737'), 1.0)  # 不超过100%
        
        # 空载情况
        self.assertEqual(calculate_load_factor(0, 'A320'), 0.0)

if __name__ == '__main__':
    unittest.main() 