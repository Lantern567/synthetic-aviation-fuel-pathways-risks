"""
航空器中文机型到ICAO代码映射模块
用于将中文机型名称转换为pybada库支持的ICAO代码
"""

# 中文机型到ICAO代码映射字典
AIRCRAFT_MAPPING = {
    # 波音系列
    '波音737(中)': 'B737',
    '波音737': 'B737',
    '波音757(中)': 'B757',
    '波音757': 'B757',
    '波音777(大)': 'B777',
    '波音777': 'B777',
    '波音787(大)': 'B787',
    '波音787': 'B787',
    
    # 空客系列
    '空客319(中)': 'A319',
    '空客319': 'A319',
    '空客320(中)': 'A320',
    '空客320': 'A320',
    '空客321(中)': 'A321',
    '空客321': 'A321',
    '空客321(窄体机)': 'A321',
    '空客330(宽体机)': 'A330',
    '空客330': 'A330',
    '空客380(大)': 'A380',
    '空客380': 'A380',
    
    # 其他机型
    'ERJ-190(中)': 'E190',
    'ERJ-190': 'E190',
    '庞巴迪CRJ900': 'CRJ9',
    'CRJ(小)': 'CRJ2',
    'JET': 'B737',  # 默认映射到B737
    '其他机型': 'B737',  # 默认映射到B737
}

# 机型典型载客量 (用于负载系数计算)
AIRCRAFT_CAPACITY = {
    'B737': 160,
    'B757': 200,
    'B777': 350,
    'B787': 290,
    'A319': 140,
    'A320': 160,
    'A321': 200,
    'A330': 290,
    'A380': 550,
    'E190': 100,
    'CRJ9': 90,
    'CRJ2': 50,
}

# 机型典型巡航速度 (马赫数)
AIRCRAFT_CRUISE_MACH = {
    'B737': 0.78,
    'B757': 0.80,
    'B777': 0.84,
    'B787': 0.85,
    'A319': 0.78,
    'A320': 0.78,
    'A321': 0.78,
    'A330': 0.82,
    'A380': 0.85,
    'E190': 0.78,
    'CRJ9': 0.78,
    'CRJ2': 0.75,
}

def get_icao_code(chinese_aircraft_type):
    """
    将中文机型转换为ICAO代码
    
    Args:
        chinese_aircraft_type (str): 中文机型名称
        
    Returns:
        str: ICAO代码，如果未找到则返回默认的B737
    """
    return AIRCRAFT_MAPPING.get(chinese_aircraft_type, 'B737')

def get_aircraft_capacity(icao_code):
    """
    获取机型典型载客量
    
    Args:
        icao_code (str): ICAO代码
        
    Returns:
        int: 典型载客量
    """
    return AIRCRAFT_CAPACITY.get(icao_code, 160)

def get_cruise_mach(icao_code):
    """
    获取机型典型巡航马赫数
    
    Args:
        icao_code (str): ICAO代码
        
    Returns:
        float: 典型巡航马赫数
    """
    return AIRCRAFT_CRUISE_MACH.get(icao_code, 0.78)

def calculate_load_factor(passengers, icao_code):
    """
    计算载客率
    
    Args:
        passengers (int): 实际载客数
        icao_code (str): ICAO代码
        
    Returns:
        float: 载客率 (0-1之间)
    """
    capacity = get_aircraft_capacity(icao_code)
    return min(passengers / capacity, 1.0)  # 载客率不超过100% 