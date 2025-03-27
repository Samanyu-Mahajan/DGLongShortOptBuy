# for logs of start date
# for uodate_time_gap in range 5 .. 60
# read from corresponding folder plot pnl
# one colour line for one token



import os
import pandas as pd
import matplotlib.pyplot as plt
from config import START_DATE

# Define time intervals
time_intervals = list(range(5, 65, 5))  # [5,10,15,...,60]

# Dictionary to store PnL data for each instrument
pnl_data = {}

# Base directory where the stats files are located
base_dir = f"quantx/logs/{START_DATE}"

# Loop through each folder
for t in time_intervals:
    folder_path = os.path.join(base_dir, str(t))  
    stats_path = os.path.join(folder_path, "stats.csv")

    if os.path.exists(stats_path):
        try:
            df = pd.read_csv(stats_path)
            df.columns = df.columns.str.upper()  # Normalize column names

            if {'TOKEN', 'PNL'}.issubset(df.columns):  # Ensure required columns exist
                for _, row in df.iterrows():
                    instrument = row['TOKEN']
                    pnl = row['PNL']

                    if instrument not in pnl_data:
                        pnl_data[instrument] = {}

                    pnl_data[instrument][t] = pnl  # Store PnL per instrument

        except Exception as e:
            print(f"Error reading {stats_path}: {e}")

# Convert to DataFrame
analysis_df = pd.DataFrame.from_dict(pnl_data, orient='index').T
analysis_df.index.name = 'Time'

# Save to CSV
analysis_csv_path = os.path.join(base_dir, "analysis.csv")
analysis_df.to_csv(analysis_csv_path)

# Plot results
plt.figure(figsize=(10, 5))
for instrument in analysis_df.columns:
    plt.plot(analysis_df.index, analysis_df[instrument], marker='o', linestyle='-', label=f"PnL - {instrument}")

plt.xlabel("Time Interval (s)")
plt.ylabel("PnL")
plt.title("PnL vs Time Interval for Each Instrument")
plt.legend()
plt.grid()

# Save plot
analysis_plot_path = os.path.join(base_dir, "analysis_plot.png")
plt.savefig(analysis_plot_path)
plt.show()

print(f"Analysis saved: {analysis_csv_path}")
print(f"Plot saved: {analysis_plot_path}")
