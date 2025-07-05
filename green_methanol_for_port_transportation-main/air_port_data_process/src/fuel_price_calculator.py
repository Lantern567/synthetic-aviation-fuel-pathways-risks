"""
航空燃油价格计算器
基于2024年800公里以上航段燃油价格数据
包含燃油价格波动分析和成本计算功能
"""

import pandas as pd
from datetime import datetime
from typing import Dict, Tuple, Optional
import logging

logger = logging.getLogger(__name__)

class FuelPriceCalculator:
    """航空燃油价格计算器"""
    
    # 2024年800公里以上航段燃油价格数据（元/吨）
    FUEL_PRICE_2024 = {
        '2024-01': {'base_price': 70, 'cost_range': (6490, 6719), 'trend': '延续2023年底的回落趋势'},
        '2024-02': {'base_price': 50, 'cost_range': (6054, 6283), 'trend': '成本显著下降'},
        '2024-03': {'base_price': 50, 'cost_range': (6054, 6283), 'trend': '成本维持稳定'},
        '2024-04': {'base_price': 50, 'cost_range': (6054, 6283), 'trend': '成本维持稳定'},
        '2024-05': {'base_price': 50, 'cost_range': (6054, 6283), 'trend': '成本维持稳定'},
        '2024-06': {'base_price': 40, 'cost_range': (5836, 6065), 'trend': '成本进一步下降'},
        '2024-07': {'base_price': 30, 'cost_range': (5573, 5802), 'trend': '达到全年成本最低点'},
        '2024-08': {'base_price': 50, 'cost_range': (6054, 6283), 'trend': '成本触底反弹'},
        '2024-09': {'base_price': 70, 'cost_range': (6490, 6719), 'trend': '成本大幅上涨'},
        '2024-10': {'base_price': 70, 'cost_range': (6490, 6719), 'trend': '成本维持高位'},
        '2024-11': {'base_price': 80, 'cost_range': (6719, 6948), 'trend': '达到全年成本最高点'},
        '2024-12': {'base_price': 60, 'cost_range': (6272, 6501), 'trend': '成本从高位回落'}
    }
    
    # 燃油密度 (公斤/升)
    FUEL_DENSITY = 0.8  # 航空煤油密度约为0.8kg/L
    
    # 燃油计价单位转换
    YUAN_PER_TON_TO_YUAN_PER_KG = 0.001  # 元/吨 转 元/公斤
    
    def __init__(self):
        """初始化燃油价格计算器"""
        self.current_month = datetime.now().strftime('%Y-%m')
        logger.info("✅ 燃油价格计算器初始化完成")
    
    def get_fuel_price_by_month(self, year_month: str = None) -> Dict:
        """获取指定月份的燃油价格信息"""
        if year_month is None:
            year_month = self.current_month
        
        if year_month in self.FUEL_PRICE_2024:
            return self.FUEL_PRICE_2024[year_month]
        else:
            # 如果查询的月份不在数据中，使用最新的价格数据
            logger.warning(f"未找到{year_month}的燃油价格数据，使用2024-12的数据")
            return self.FUEL_PRICE_2024['2024-12']
    
    def get_current_fuel_price(self) -> float:
        """获取当前燃油价格（元/公斤）"""
        current_data = self.get_fuel_price_by_month()
        # 使用综合采购成本区间的中位数
        cost_range = current_data['cost_range']
        avg_cost_per_ton = (cost_range[0] + cost_range[1]) / 2
        
        # 转换为元/公斤
        price_per_kg = avg_cost_per_ton * self.YUAN_PER_TON_TO_YUAN_PER_KG
        return price_per_kg
    
    def calculate_fuel_cost(self, fuel_kg: float, year_month: str = None, 
                          use_price_range: bool = False) -> Dict:
        """
        计算燃油成本
        
        Args:
            fuel_kg: 燃油消耗量（公斤）
            year_month: 指定月份（格式：'2024-01'），默认使用当前月份
            use_price_range: 是否返回价格区间（最低价和最高价）
        
        Returns:
            包含燃油成本信息的字典
        """
        fuel_data = self.get_fuel_price_by_month(year_month)
        
        if use_price_range:
            # 计算价格区间
            min_cost_per_ton = fuel_data['cost_range'][0]
            max_cost_per_ton = fuel_data['cost_range'][1]
            
            min_price_per_kg = min_cost_per_ton * self.YUAN_PER_TON_TO_YUAN_PER_KG
            max_price_per_kg = max_cost_per_ton * self.YUAN_PER_TON_TO_YUAN_PER_KG
            
            min_cost = fuel_kg * min_price_per_kg
            max_cost = fuel_kg * max_price_per_kg
            avg_cost = (min_cost + max_cost) / 2
            
            return {
                'fuel_kg': fuel_kg,
                'month': year_month or self.current_month,
                'fuel_cost_yuan_min': min_cost,
                'fuel_cost_yuan_max': max_cost,
                'fuel_cost_yuan_avg': avg_cost,
                'price_per_kg_min': min_price_per_kg,
                'price_per_kg_max': max_price_per_kg,
                'price_per_kg_avg': (min_price_per_kg + max_price_per_kg) / 2,
                'cost_range_yuan': f"{min_cost:.0f} - {max_cost:.0f}",
                'market_trend': fuel_data['trend'],
                'base_surcharge': fuel_data['base_price']
            }
        else:
            # 使用平均价格
            avg_cost_per_ton = (fuel_data['cost_range'][0] + fuel_data['cost_range'][1]) / 2
            price_per_kg = avg_cost_per_ton * self.YUAN_PER_TON_TO_YUAN_PER_KG
            total_cost = fuel_kg * price_per_kg
            
            return {
                'fuel_kg': fuel_kg,
                'month': year_month or self.current_month,
                'fuel_cost_yuan': total_cost,
                'price_per_kg': price_per_kg,
                'market_trend': fuel_data['trend'],
                'base_surcharge': fuel_data['base_price']
            }
    
    def get_yearly_price_trend(self) -> pd.DataFrame:
        """获取2024年全年燃油价格趋势"""
        trend_data = []
        
        for month, data in self.FUEL_PRICE_2024.items():
            avg_cost = (data['cost_range'][0] + data['cost_range'][1]) / 2
            price_per_kg = avg_cost * self.YUAN_PER_TON_TO_YUAN_PER_KG
            
            trend_data.append({
                'month': month,
                'base_surcharge': data['base_price'],
                'cost_min': data['cost_range'][0],
                'cost_max': data['cost_range'][1],
                'cost_avg': avg_cost,
                'price_per_kg': price_per_kg,
                'trend': data['trend']
            })
        
        return pd.DataFrame(trend_data)
    
    def calculate_route_fuel_cost(self, flight_data: Dict, year_month: str = None) -> Dict:
        """
        计算航线燃油成本
        
        Args:
            flight_data: 包含燃油消耗数据的航班信息
            year_month: 指定月份
        
        Returns:
            包含详细燃油成本信息的字典
        """
        fuel_kg = flight_data.get('fuel_kg', 0.0)
        passengers = flight_data.get('passengers', 1)
        distance_km = flight_data.get('distance_km', 1)
        
        # 计算燃油成本（含价格区间）
        cost_info = self.calculate_fuel_cost(fuel_kg, year_month, use_price_range=True)
        
        # 计算单位成本指标
        cost_per_passenger = cost_info['fuel_cost_yuan_avg'] / max(1, passengers)
        cost_per_km = cost_info['fuel_cost_yuan_avg'] / max(1, distance_km)
        cost_per_passenger_km = cost_info['fuel_cost_yuan_avg'] / max(1, passengers * distance_km)
        
        # 合并所有信息
        result = {
            **cost_info,
            'route': flight_data.get('route', 'Unknown'),
            'aircraft': flight_data.get('aircraft', 'Unknown'),
            'passengers': passengers,
            'distance_km': distance_km,
            'fuel_cost_per_passenger': cost_per_passenger,
            'fuel_cost_per_km': cost_per_km,
            'fuel_cost_per_passenger_km': cost_per_passenger_km,
            'fuel_efficiency_yuan_per_100km': cost_per_km * 100
        }
        
        return result
    
    def compare_monthly_costs(self, fuel_kg: float) -> pd.DataFrame:
        """比较不同月份的燃油成本"""
        monthly_costs = []
        
        for month in self.FUEL_PRICE_2024.keys():
            cost_info = self.calculate_fuel_cost(fuel_kg, month, use_price_range=True)
            monthly_costs.append({
                'month': month,
                'fuel_cost_yuan': cost_info['fuel_cost_yuan_avg'],
                'cost_range': cost_info['cost_range_yuan'],
                'price_per_kg': cost_info['price_per_kg_avg'],
                'trend': cost_info['market_trend'],
                'base_surcharge': cost_info['base_surcharge']
            })
        
        df = pd.DataFrame(monthly_costs)
        df['cost_change_pct'] = df['fuel_cost_yuan'].pct_change() * 100
        
        return df

    def get_monthly_price_info(self, month: str) -> Dict:
        """获取指定月份的价格信息"""
        if month in self.FUEL_PRICE_2024:
            price_data = self.FUEL_PRICE_2024[month]
            return {
                'month': month,
                'base_surcharge': price_data['base_price'],
                'cost_range': price_data['cost_range'],
                'trend': price_data['trend'],
                'price_per_kg_min': price_data['cost_range'][0] / 1000,  # 转换为元/公斤
                'price_per_kg_max': price_data['cost_range'][1] / 1000
            }
        else:
            # 返回当前月份数据
            current_price = self.get_current_price()
            return {
                'month': month,
                'base_surcharge': current_price.get('base_surcharge', 60),
                'cost_range': current_price.get('cost_range', (6000, 6500)),
                'trend': '数据不可用',
                'price_per_kg_min': 6.0,
                'price_per_kg_max': 6.5
            }
    
    def analyze_price_volatility(self) -> Dict:
        """分析价格波动性"""
        # 提取所有价格数据
        prices = []
        months = []
        
        for month, data in self.FUEL_PRICE_2024.items():
            min_price, max_price = data['cost_range']
            avg_price = (min_price + max_price) / 2
            prices.append(avg_price)
            months.append(month)
        
        if not prices:
            return {
                'volatility_rate': 0.0,
                'highest_month': 'N/A',
                'highest_price': 0.0,
                'lowest_month': 'N/A',
                'lowest_price': 0.0
            }
        
        # 计算波动率
        mean_price = sum(prices) / len(prices)
        variance = sum((p - mean_price) ** 2 for p in prices) / len(prices)
        volatility_rate = (variance ** 0.5) / mean_price if mean_price > 0 else 0.0
        
        # 找出最高和最低价格
        max_idx = prices.index(max(prices))
        min_idx = prices.index(min(prices))
        
        return {
            'volatility_rate': volatility_rate,
            'highest_month': months[max_idx],
            'highest_price': prices[max_idx],
            'lowest_month': months[min_idx],
            'lowest_price': prices[min_idx],
            'average_price': mean_price,
            'price_range': max(prices) - min(prices)
        }

    def get_current_price(self) -> Dict:
        """获取当前价格信息（用于兼容性）"""
        # 返回12月的价格作为当前价格
        return self.get_fuel_price_by_month('2024-12')


def format_currency(amount: float) -> str:
    """格式化货币显示"""
    if amount >= 10000:
        return f"¥{amount:,.0f}"
    else:
        return f"¥{amount:.2f}"


def analyze_fuel_cost_efficiency(flight_results: list) -> Dict:
    """分析航班燃油成本效率"""
    if not flight_results:
        return {}
    
    df = pd.DataFrame(flight_results)
    
    # 按机型分析燃油成本效率
    aircraft_efficiency = df.groupby('aircraft').agg({
        'fuel_cost_yuan_avg': 'mean',
        'fuel_cost_per_passenger': 'mean',
        'fuel_cost_per_km': 'mean',
        'distance_km': 'mean',
        'passengers': 'mean'
    }).round(2)
    
    # 按航线类型分析
    def classify_route(distance):
        if distance < 800:
            return '国内短程'
        elif distance < 2500:
            return '国内中程'
        elif distance < 6000:
            return '国际中程'
        else:
            return '洲际长程'
    
    df['route_type'] = df['distance_km'].apply(classify_route)
    route_efficiency = df.groupby('route_type').agg({
        'fuel_cost_yuan_avg': 'mean',
        'fuel_cost_per_passenger': 'mean',
        'fuel_cost_per_km': 'mean'
    }).round(2)
    
    return {
        'aircraft_efficiency': aircraft_efficiency,
        'route_efficiency': route_efficiency,
        'overall_stats': {
            'total_routes': len(df),
            'avg_fuel_cost': df['fuel_cost_yuan_avg'].mean(),
            'avg_cost_per_passenger': df['fuel_cost_per_passenger'].mean(),
            'max_cost_route': df.loc[df['fuel_cost_yuan_avg'].idxmax()]['route'],
            'min_cost_route': df.loc[df['fuel_cost_yuan_avg'].idxmin()]['route']
        }
    }


if __name__ == "__main__":
    # 测试燃油价格计算器
    calculator = FuelPriceCalculator()
    
    # 测试单次燃油成本计算
    test_fuel = 5000  # 5吨燃油
    print("🧪 测试燃油价格计算器")
    print("=" * 50)
    
    cost_info = calculator.calculate_fuel_cost(test_fuel, use_price_range=True)
    print(f"燃油消耗: {test_fuel} kg")
    print(f"燃油成本区间: {cost_info['cost_range_yuan']} 元")
    print(f"平均成本: ¥{cost_info['fuel_cost_yuan_avg']:.2f}")
    print(f"市场趋势: {cost_info['market_trend']}")
    
    # 测试全年价格趋势
    print(f"\n📈 2024年燃油价格趋势:")
    trend_df = calculator.get_yearly_price_trend()
    print(trend_df[['month', 'base_surcharge', 'price_per_kg', 'trend']].to_string(index=False)) 