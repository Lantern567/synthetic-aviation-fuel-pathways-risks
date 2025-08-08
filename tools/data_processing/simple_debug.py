#!/usr/bin/env python3
import sys
import os
import pandas as pd

# Add source path
sys.path.append('natural_gas_supply_chain_optimization/src')

try:
    from natural_gas_optimization_model import NaturalGasSupplyChainOptimizer
    
    # Create optimizer
    optimizer = NaturalGasSupplyChainOptimizer(
        time_horizon_weeks=1,
        use_graphhopper_routing=True,
        graphhopper_host="localhost",
        graphhopper_port=8989
    )
    print("Optimizer initialized successfully")
    
    # Test GraphHopper service
    health_check = optimizer.routing_engine.check_service_health()
    print(f"GraphHopper service health: {health_check}")
    
    if health_check:
        # Test simple route
        result = optimizer.routing_engine.calculate_route_distance(
            39.9042, 116.4074,  # Beijing
            31.2304, 121.4737,  # Shanghai
            vehicle="car",
            include_route_geometry=False
        )
        print(f"Beijing to Shanghai distance: {result.get('distance_km', 0):.1f} km")
        
        # Create test data
        renewable_data = pd.DataFrame({
            'location': ['Beijing', 'Shanghai'],
            'latitude': [39.9042, 31.2304],
            'longitude': [116.4074, 121.4737],
            'solar_capacity_mw': [1000, 1500],
            'wind_capacity_mw': [800, 1200]
        })
        
        airport_data = pd.DataFrame({
            'airport': ['PEK', 'PVG'],
            'city': ['Beijing', 'Shanghai'],
            'latitude': [40.0801, 31.1443],
            'longitude': [121.8083, 121.8083],
            'capacity': [100, 120]
        })
        
        # Load data - this is where the error likely occurs
        print("Loading data...")
        optimizer.load_data(renewable_data, airport_data)
        print("Data loaded successfully")
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()