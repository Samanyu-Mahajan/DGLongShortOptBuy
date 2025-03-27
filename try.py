import pandas as pd

def get_all_options_nifty(file_path="quantx/prices/2025-02-17.csv", expiry_date = "27MAR2025", output_path = "filtered_2025-02-17"):
    df = pd.read_csv(file_path)
    df = df[(df["instrumenttype"] == "OPTIDX")& (df['name'] == "NIFTY") & (df['expiry'] == expiry_date)]
    df["strike"] = df["strike"] / 100
    df["opt_type"] = df["symbol"].str[-2:]  # Last two characters (CE or PE)
    df["opt_type"] = df["opt_type"].map({"CE": "CALL", "PE": "PUT"})  # Map to readable format
    df_filtered = df[["token", "opt_type", "strike", "lotsize"]]
    df_filtered.reset_index(drop=True, inplace=True)
    df_filtered = df_filtered.sort_values(by="strike", ascending=True)
    df_filtered.to_csv(output_path, index=False)
    return df_filtered


# alloptions = get_all_options_nifty()
# print(alloptions)

import math
print(math.inf)

# class Position:
#     def __init__(self):
#         self.pnl = 0
#         # (total buy orders - total sell orders) * lot size basically total open position
#         self.quantity = 0
#         self.lot_size = 1
#         # number of buy and sell orders (divided by lot size)
#         self.total_buy = 0
#         self.total_sell = 0
#         # total buy + total_sell * lot size
#         self.volume =  0

#         # summation buy_price*qty*lotsize
#         self.avg_buy = 0
#         self.avg_sell = 0
#         # total pnl = avg_sell-avg_buy
#         self.buy_list = []
#         self.sell_list = []
#         self.pnl_list = []
#         # summation of self.pnl_list * lot size = pnl

#         self.sharpe = 0
#         self.drawdown = 0


# p = {}
# p[5] = Position()
# pos = p[5]
# pos.avg_buy+=5
# print(p[5].avg_buy)