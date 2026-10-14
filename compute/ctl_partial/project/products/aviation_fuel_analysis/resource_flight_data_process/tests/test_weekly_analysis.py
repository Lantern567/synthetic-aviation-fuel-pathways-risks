import unittest
import pandas as pd
import numpy as np
import os
import sys
from datetime import datetime, timedelta

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'weekly_analysis'))

from data_loader import AirportDataLoader
from weekly_calculator import WeeklyParameterCalculator
from results_saver import ResultsSaver

class TestWeeklyAnalysis(unittest.TestCase):
    
    def setUp(self):
        # Create sample test data
        self.test_data = self.create_test_data()
        self.test_file = os.path.join(os.path.dirname(__file__), 'test_data.xlsx')
        self.test_data.to_excel(self.test_file, index=False)
        
        self.test_results_dir = os.path.join(os.path.dirname(__file__), 'test_results')
        os.makedirs(self.test_results_dir, exist_ok=True)
    
    def tearDown(self):
        # Clean up test files
        if os.path.exists(self.test_file):
            os.remove(self.test_file)
    
    def create_test_data(self):
        # Create sample data with 2 airports and various dates in 2024
        np.random.seed(42)
        
        dates = []
        airports = []
        
        # Create data for first few weeks of 2024
        for week in range(1, 5):  # First 4 weeks
            week_start = datetime(2024, 1, 1) + timedelta(weeks=week-1)
            for day in range(7):  # Each day of the week
                if np.random.random() > 0.3:  # 70% chance of having flights
                    current_date = week_start + timedelta(days=day)
                    # Generate 1-5 flights per day
                    num_flights = np.random.randint(1, 6)
                    for _ in range(num_flights):
                        dates.append(current_date)
                        airports.append(np.random.choice(['北京', '滨海']))
        
        n_records = len(dates)
        
        data = {
            '起降机场': airports,
            'flight_date': dates,
            'total_fuel_kg': np.random.normal(5000, 1000, n_records),
            'fuel_per_km': np.random.normal(2.5, 0.5, n_records),
            'fuel_per_passenger': np.random.normal(30, 5, n_records),
            'total_time_minutes': np.random.normal(120, 20, n_records),
            'co2_direct_kg': np.random.normal(15000, 3000, n_records),
            'fuel_cost_yuan_avg': np.random.normal(8000, 1500, n_records),
            'distance_km': np.random.normal(1000, 200, n_records),
            'passengers': np.random.randint(50, 200, n_records),
            'climb_time_minutes': np.random.normal(15, 3, n_records),
            'cruise_time_minutes': np.random.normal(90, 15, n_records),
            'descent_time_minutes': np.random.normal(15, 3, n_records)
        }
        
        return pd.DataFrame(data)
    
    def test_data_loader(self):
        """Test the AirportDataLoader class"""
        loader = AirportDataLoader(self.test_file)
        df = loader.load_data()
        
        self.assertIsNotNone(df)
        self.assertGreater(len(df), 0)
        self.assertIn('flight_date', df.columns)
        
        # Test unique airports
        airports = loader.get_unique_airports()
        self.assertEqual(len(airports), 2)
        self.assertIn('北京', airports)
        self.assertIn('滨海', airports)
        
        # Test filtering by airport
        beijing_data = loader.filter_by_airport('北京')
        self.assertIsNotNone(beijing_data)
        self.assertTrue(all(beijing_data[loader.get_airport_column()] == '北京'))
    
    def test_weekly_calculator(self):
        """Test the WeeklyParameterCalculator class"""
        calculator = WeeklyParameterCalculator()
        
        # Test week generation
        weeks = calculator.generate_2024_weeks()
        self.assertEqual(len(weeks), 52)
        self.assertEqual(weeks[0]['week_number'], 1)
        self.assertEqual(weeks[0]['week_start'], datetime(2024, 1, 1))
        
        # Test daily parameter calculation
        loader = AirportDataLoader(self.test_file)
        df = loader.load_data()
        beijing_data = loader.filter_by_airport('北京')
        
        daily_stats = calculator.calculate_daily_parameters(beijing_data)
        self.assertIsNotNone(daily_stats)
        self.assertGreater(len(daily_stats), 0)
        self.assertIn('date', daily_stats.columns)
        self.assertIn('flight_count', daily_stats.columns)
        
        # Test weekly parameter calculation
        weekly_results = calculator.calculate_weekly_parameters(beijing_data)
        self.assertIsNotNone(weekly_results)
        self.assertGreater(len(weekly_results), 0)
        self.assertIn('week_number', weekly_results.columns)
        self.assertIn('total_flights', weekly_results.columns)
    
    def test_results_saver(self):
        """Test the ResultsSaver class"""
        loader = AirportDataLoader(self.test_file)
        loader.load_data()
        
        calculator = WeeklyParameterCalculator()
        all_results = calculator.process_all_airports(loader)
        
        results_saver = ResultsSaver(self.test_results_dir)
        output_info = results_saver.save_all_results(all_results)
        
        self.assertIn('table_file', output_info)
        self.assertIn('charts_dir', output_info)
        self.assertIn('timestamp', output_info)
        
        # Check if files were created
        self.assertTrue(os.path.exists(output_info['table_file']))
        self.assertTrue(os.path.exists(output_info['charts_dir']))
    
    def test_full_integration(self):
        """Test the full integration workflow"""
        loader = AirportDataLoader(self.test_file)
        df = loader.load_data()
        
        calculator = WeeklyParameterCalculator()
        all_results = calculator.process_all_airports(loader)
        
        # Verify results structure
        self.assertIsInstance(all_results, dict)
        self.assertGreater(len(all_results), 0)
        
        for airport, weekly_data in all_results.items():
            self.assertIsInstance(weekly_data, pd.DataFrame)
            if len(weekly_data) > 0:
                self.assertIn('week_number', weekly_data.columns)
                self.assertIn('airport', weekly_data.columns)
                self.assertTrue(all(weekly_data['airport'] == airport))
    
    def test_edge_cases(self):
        """Test edge cases and error handling"""
        calculator = WeeklyParameterCalculator()
        
        # Test with empty data
        empty_df = pd.DataFrame()
        daily_stats = calculator.calculate_daily_parameters(empty_df)
        self.assertEqual(len(daily_stats), 0)
        
        # Test with data having missing dates
        data_with_nans = self.test_data.copy()
        data_with_nans.loc[0:5, 'flight_date'] = pd.NaT
        
        daily_stats = calculator.calculate_daily_parameters(data_with_nans)
        self.assertGreater(len(daily_stats), 0)  # Should still process valid dates
    
    def test_parameter_calculations(self):
        """Test specific parameter calculations"""
        loader = AirportDataLoader(self.test_file)
        df = loader.load_data()
        
        calculator = WeeklyParameterCalculator()
        
        # Test daily calculations
        beijing_data = loader.filter_by_airport('北京')
        daily_stats = calculator.calculate_daily_parameters(beijing_data)
        
        # Check if statistical calculations are reasonable
        for _, day in daily_stats.iterrows():
            if not pd.isna(day.get('total_fuel_kg_mean')):
                self.assertGreater(day['total_fuel_kg_mean'], 0)
            if not pd.isna(day.get('flight_count')):
                self.assertGreater(day['flight_count'], 0)

class TestDataValidation(unittest.TestCase):
    """Additional tests for data validation"""
    
    def test_data_types(self):
        """Test data type validation"""
        # This would be expanded based on specific requirements
        self.assertTrue(True)  # Placeholder
    
    def test_business_logic(self):
        """Test business logic validations"""
        # Test that weekly aggregations make sense
        # Test that nearest week logic works correctly
        self.assertTrue(True)  # Placeholder

def run_tests():
    """Run all tests and return results"""
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test classes
    suite.addTests(loader.loadTestsFromTestCase(TestWeeklyAnalysis))
    suite.addTests(loader.loadTestsFromTestCase(TestDataValidation))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result

if __name__ == '__main__':
    print("Running weekly analysis tests...")
    result = run_tests()
    
    if result.wasSuccessful():
        print("\n✅ All tests passed!")
        exit_code = 0
    else:
        print(f"\n❌ {len(result.failures + result.errors)} test(s) failed")
        exit_code = 1
    
    sys.exit(exit_code)