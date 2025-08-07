import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging
import os

class AirportDataLoader:
    def __init__(self, data_path):
        self.data_path = data_path
        self.df = None
        self.setup_logging()
    
    def setup_logging(self):
        log_dir = os.path.join(os.path.dirname(self.data_path), '..', 'logs')
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, f'weekly_analysis_{datetime.now().strftime("%Y%m%d")}.log')
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def load_data(self):
        try:
            self.logger.info(f"Loading data from {self.data_path}")
            self.df = pd.read_excel(self.data_path)
            
            self.df['flight_date'] = pd.to_datetime(self.df['flight_date'], errors='coerce')
            
            self.logger.info(f"Data loaded successfully. Shape: {self.df.shape}")
            self.logger.info(f"Date range: {self.df['flight_date'].min()} to {self.df['flight_date'].max()}")
            self.logger.info(f"Unique airports: {self.df.iloc[:, 0].unique()}")
            
            null_dates = self.df['flight_date'].isnull().sum()
            if null_dates > 0:
                self.logger.warning(f"Found {null_dates} rows with invalid dates")
                self.df = self.df.dropna(subset=['flight_date'])
            
            return self.df
            
        except Exception as e:
            self.logger.error(f"Error loading data: {str(e)}")
            raise
    
    def get_airport_column(self):
        return self.df.columns[0] if self.df is not None else None
    
    def get_unique_airports(self):
        if self.df is not None:
            airport_col = self.get_airport_column()
            return self.df[airport_col].unique()
        return []
    
    def filter_by_airport(self, airport_name):
        if self.df is not None:
            airport_col = self.get_airport_column()
            return self.df[self.df[airport_col] == airport_name].copy()
        return None
    
    def get_date_range(self):
        if self.df is not None:
            return self.df['flight_date'].min(), self.df['flight_date'].max()
        return None, None