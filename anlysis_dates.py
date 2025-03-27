import os
import csv
import numpy as np
import matplotlib.pyplot as plt

def plot_equity_curve_and_drawdowns(pnl_list, equity_curve, drawdowns):
    # Plot PnL
    plt.subplot(3, 1, 1)
    plt.plot(pnl_list, label='PnL per Trade', color='blue')
    plt.title('PnL per Trade')
    plt.ylabel('PnL')
    plt.grid(True)
    plt.legend()

    # Plot Equity Curve
    plt.subplot(3, 1, 2)
    plt.plot(equity_curve, label='Equity Curve', color='green')
    plt.title('Equity Curve')
    plt.ylabel('Equity')
    plt.grid(True)
    plt.legend()

    # Plot Drawdowns
    plt.subplot(3, 1, 3)
    plt.plot(drawdowns, label='Drawdown', color='red')
    plt.title('Drawdown')
    plt.ylabel('Drawdown')
    plt.xlabel('Trade Index')
    plt.grid(True)
    plt.legend()

    plt.tight_layout()
    plt.show()


# Directory containing stats CSV files
report_dir = "quantx/reports"
output_csv = os.path.join(report_dir, "final_analysis.csv")
output_txt = os.path.join(report_dir, "final_analysis.txt")  # New text file

# Columns to sum
columns_to_sum = ["PNL", "Total orders", "Total trades", "Volume traded", "Winning trades"]

# Initialize aggregated data
aggregated_data = {col: 0 for col in columns_to_sum}
aggregated_data["Token"] = None  # Placeholder for token
pnl_list = []  # List to store PNL values from each file
wp_list = []   # Win points list
lp_list = []   # Loss points list
turnover_list = []

# Process all {date}_stats.csv files
for root, _, files in os.walk(report_dir):
    for file in files:
        if file.endswith("_stats.csv"):  # Find all {date}_stats.csv files
            file_path = os.path.join(root, file)
            
            # Read CSV
            with open(file_path, "r") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    x = float(row["PNL turnover ratio in bps"])
                    alpha = float(row["Win loss points"])
                    pnl = float(row["PNL"])
                    
                    if alpha - 1 != 0:
                        wp = alpha * pnl / (alpha - 1)
                        lp = pnl / (alpha - 1)
                    else:
                        wp, lp = 0, 0
                    
                    turnover = (pnl * 10000) / x if x != 0 else 0  # Avoid division by zero

                    if aggregated_data["Token"] is None:  # Take Token from any file
                        aggregated_data["Token"] = row["Token"]
                    
                    # Store PNL & win/loss points
                    pnl_list.append(pnl)
                    wp_list.append(wp)
                    lp_list.append(lp)
                    turnover_list.append(turnover)
                    
                    # Sum up other numerical columns
                    for col in columns_to_sum:
                        aggregated_data[col] += float(row[col])

# Compute final statistics
total_pnl = sum(pnl_list)
win_loss_points = sum(wp_list) / sum(lp_list) if sum(lp_list) != 0 else 0
total_turnover = sum(turnover_list)
pnl_turnover_ratio_bps = (total_pnl / total_turnover * 10000) if total_turnover != 0 else 0

if len(pnl_list) == 0 or np.std(pnl_list) == 0:
    sharpe = np.nan  # or set to 0, depending on your preference
else:
    sharpe = np.mean(pnl_list) / np.std(pnl_list)
sharpe_annualized = sharpe * np.sqrt(252)

equity_curve = np.cumsum(pnl_list)
running_max = np.maximum.accumulate(equity_curve)
drawdowns = np.divide(
    equity_curve - running_max,
    running_max,
    out=np.zeros_like(equity_curve),
    where=running_max != 0
)   

# for i in range(len(equity_curve)):
#     print(equity_curve[i]-running_max[i], running_max[i], drawdowns[i])
if len(drawdowns) == 0:
    max_drawdown = np.nan  # or set to 0, depending on your use case
else:
    max_drawdown = np.min(drawdowns)

                # Equity Curve Plot
plot_equity_curve_and_drawdowns(pnl_list, equity_curve, drawdowns)

# Compute Win Loss Ratio
total_trades = aggregated_data["Total trades"]
winning_trades = aggregated_data["Winning trades"]
win_loss_ratio = winning_trades / (total_trades - winning_trades) if (total_trades - winning_trades) != 0 else 0

# Write final_analysis.csv
with open(output_csv, "w", newline="") as f:
    writer = csv.writer(f)
    
    # Write headers
    writer.writerow([
        "Token", "PNL", "Total orders", "Total trades", "Volume traded",
        "Winning trades", "Win Loss Ratio", "Win Loss Points",
        "PNL Turnover Ratio (bps)", "Sharpe Ratio", "Drawdown"
    ])
    
    # Write aggregated row
    writer.writerow([
        aggregated_data["Token"],
        total_pnl,
        aggregated_data["Total orders"],
        aggregated_data["Total trades"],
        aggregated_data["Volume traded"],
        aggregated_data["Winning trades"],
        win_loss_ratio,
        win_loss_points,
        pnl_turnover_ratio_bps,
        sharpe_annualized,
        max_drawdown
    ])

# Write final_analysis.txt (Readable format)
with open(output_txt, "w") as f:
    f.write(f"Total PNL = {total_pnl}\n")
    f.write(f"Token = {aggregated_data['Token']}\n")
    f.write(f"Total Orders = {aggregated_data['Total orders']}\n")
    f.write(f"Total Trades = {aggregated_data['Total trades']}\n")
    f.write(f"Volume Traded = {aggregated_data['Volume traded']}\n")
    f.write(f"Winning Trades = {aggregated_data['Winning trades']}\n")
    f.write(f"Win Loss Ratio = {win_loss_ratio}\n")
    f.write(f"Win Loss Points = {win_loss_points}\n")
    f.write(f"PNL Turnover Ratio (bps) = {pnl_turnover_ratio_bps}\n")
    f.write(f"Sharpe Ratio = {sharpe_annualized}\n")
    f.write(f"Drawdown = {max_drawdown}\n")
    f.write("#" * 80 + "\n")  # Separator line

# Print for verification
# print(f"PNL List from each file: {pnl_list}")
# print(f"Total PNL: {total_pnl}")
# print(f"Final analysis saved at:\n - {output_csv} (CSV Format)\n - {output_txt} (Readable Text Format)")
