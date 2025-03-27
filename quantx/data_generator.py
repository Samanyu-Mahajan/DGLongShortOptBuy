import csv
import random
import pandas as pd


# This is a estimator to find the size of data in a day
# Number of rows to generate
num_rows = 5040000

# File path to save the generated data
file_path = 'generated_data.csv'

# Column names
columns = ['token', 'open', 'low', 'high', 'close', 'volume', 'vwap', 'mid_price', 'l1_bid_quantity', 'l1_ask_quantity']

# Function to generate random data for each row
def generate_row():
    token = round(random.uniform(100000, 999999))
    open_price = round(random.uniform(100000, 200000), 2)
    close_price = round(random.uniform(100000, 200000), 2)
    low_price = min(open_price, close_price) - round(random.uniform(0, 10), 2)
    high_price = max(open_price, close_price) + round(random.uniform(0, 10), 2)
    volume = random.randint(1000000, 2000000)
    vwap = round(random.uniform(open_price, open_price+50), 2)
    mid_price = round((open_price + close_price) / 2, 2)
    l1_bid_quantity = random.randint(1, 100)
    l1_ask_quantity = random.randint(1, 100)
    
    return [token, open_price, low_price, high_price, close_price, volume, vwap, mid_price, l1_bid_quantity, l1_ask_quantity]

#Generate data and write to CSV file
with open(file_path, mode='w', newline='') as file:
    writer = csv.writer(file)
    writer.writerow(columns)  # Write header
    for _ in range(num_rows):
        writer.writerow(generate_row())

print(f"Data generated and saved to {file_path}")
# Read the generated data using pandas
# data = pd.read_csv(file_path, engine='pyarrow')
# data.to_feather('generated_data.feather')
# data = pd.read_parquet('generated_data.parquet')
# data.to_parquet('generated_data.parquet', engine='pyarrow', index=False, compression='BROTLI')
# data = pd.read_parquet('generated_data.parquet', engine='pyarrow')
# print(data.count())



# print(data.head())
