from config import START_DATE, END_DATE, DATA_BUILDING_DATE, UNIVERSE, DATA_LOC, NUM_TOKENS, TIMER_TIME_SECONDS,CANDLE_TIME_FRAME, NIFTY_TOKEN, OPTIONS, BASE_LOG_PATH #"quantx/logs"

from Exchange.logger import setup_general_logger, setup_stats_csv
from Exchange.executor import Exchange
from data_store.data_feed import DataStore
from strategy.lakshya import CWA2SSigma
from strategy.DGLongShortRev import DGLongShortRev
from strategy.DGLongShortOptBuy import DGLongShortOptBuy

from strategy.base_strategy import Strategy
from concurrent.futures import ThreadPoolExecutor
import threading
import queue

from multiprocessing import Process, Queue
from multiprocessing import Lock

import multiprocessing
import time
import os
import os.path
import pandas as pd
import sys
import datetime as dt


# for options
# universe[0] is underlying
# and universe[1:] is all the options
class Infinity:
    def __init__(self, locks, start_date, end_date, data_building_date, universe,build_data=True, all_data=None, update_time_gap_seconds=60):
        """
          Driver class for Strategy and Exchange
          This class fetches data at go and keeps sending minutely candles to both exchange and strategy
          All these variables can be imported from config as well
        """
        # setup_general_logger(locks[0], start_date, update_time_gap_seconds)
        # setup_stats_csv(update_time_gap_seconds)
        setup_general_logger(locks[0], start_date)
        setup_stats_csv(start_date)
        self.start_date = start_date
        self.end_date = end_date
        self.data_building_date = data_building_date

        self.universe = universe
        # reads all data for all dates btw start and end dates as mkt_data
        # next function reads next row. (packet)
        start = time.time()
        self.underlying_data_obj = DataStore(
            universe=[self.universe[0]],
            start_date=self.start_date,
            end_date=self.end_date,
            data_building_date=self.data_building_date,
            data_path = DATA_LOC, 
            build_data=build_data, 
            all_data=all_data
        )
        self.data_obj = DataStore(
            universe=self.universe,
            start_date=self.start_date,
            end_date=self.end_date,
            data_building_date=self.data_building_date,
            data_path = DATA_LOC, 
            build_data=build_data, 
            all_data=all_data
        )
        self.exchange = Exchange(locks, fill_type="ON_OPEN", log_name=self.start_date)
        # self.strategy = CWA2SSigma(locks, self.universe, self.exchange, "lakshya", self.start_date,
        #                       self.end_date, self.data_building_date)
        params = {
            "max_qty": 100,
            "sl_perc": 0.1,
            "update_time_gap_seconds": update_time_gap_seconds,
            "candle_tf": CANDLE_TIME_FRAME
        }
        if (OPTIONS):
            self.strategy = DGLongShortOptBuy(locks, self.universe, self.exchange, "DGLongShortOptBuy", self.start_date,
                    self.end_date, self.data_building_date, data_obj=self.data_obj, underlying_data_obj = self.underlying_data_obj, 
                    params = params)
        else:
            self.strategy = DGLongShortRev(locks, self.universe, self.exchange, "DGLongShortRev", self.start_date,
                            self.end_date, self.data_building_date, data_obj=self.data_obj, params = params)

        # so that upon order filling strategy is notified
        # stratgy updates self.position
        self.exchange.order_update_subscribers.append(self.strategy)
    # dates = DataFeed.get_all_possible_dates(2024)


    def run(self, update_time_gap_seconds):

        start_time = time.time()
        cnt_packets = 0
        prev_t = None
        while  self.data_obj.counter < self.data_obj.max_length:
            packet = self.data_obj.next()
            cnt_packets+=1
            t = packet.timestamp_seconds
            if (prev_t is None):
                prev_t=t

            if(packet.close==-0.01 or packet.open == -0.01 or packet.low==-0.01 or packet.high==-0.01):
                continue
            self.exchange.on_data(packet)
            self.strategy.on_data(packet)
            # if (t-prev_t>=dt.timedelta(seconds = update_time_gap_seconds)):
            #     # if the update occurs then only update prev_t
            #     if self.strategy.on_timer(t):
            #         prev_t = t
        # print(f"Straegy Finished : {self.universe} - {time.time() - start_time}, cnt_packets = {cnt_packets}")


def run_sim(locks, start_date, end_date, data_building_date, universe, build_data, all_data, update_time_gap_seconds):
    # print(f"START_DATE:{start_date}, END_DATE:{end_date}, DATA_BUILDING_DATE:{data_building_date}, UNIVERSE:{universe}")
    runner_class = Infinity(locks, start_date, end_date, data_building_date, universe, build_data, all_data, update_time_gap_seconds)
    runner_class.run(update_time_gap_seconds)
    del runner_class


def delete_logs():
    current_log_path = f"{BASE_LOG_PATH}/{START_DATE}"
    # dir = f"{current_log_path}/{update_time_gap_seconds}"
    dir = current_log_path
    os.system(f"rm -rf {dir}")  # delete existing log
    # os.mkdir(current_log_path)
    # os.makedirs(current_log_path, exist_ok=True)
    os.mkdir(dir)



def get_universe(num_tokens):
    universe = []
    folder_path = f"{DATA_LOC}/{START_DATE}"
    if os.path.exists(folder_path):
        file_path = f"{folder_path}/nsemd_NSECM_1_{START_DATE}.csv"
        if os.path.isfile(file_path):
            data = pd.read_csv(f"{file_path}", engine="pyarrow")
            universe = data['token'].value_counts().head(num_tokens).index.astype(str).tolist()
    return universe

def get_all_options_nifty(file_path="quantx/prices/2025-02-17.csv", expiry_date = "27MAR2025"):
    # df = pd.read_csv(file_path)
    df = pd.read_csv(file_path, dtype={"token": str}, low_memory=False)  # Fix applied here

    df = df[(df["instrumenttype"] == "OPTIDX")& (df['name'] == "NIFTY") & (df['expiry'] == expiry_date)]
    df["strike"] = df["strike"] / 100
    df["opt_type"] = df["symbol"].str[-2:]  # Last two characters (CE or PE)
    df["opt_type"] = df["opt_type"].map({"CE": "CALL", "PE": "PUT"})  # Map to readable format
    df_filtered = df[["token", "opt_type", "strike", "lotsize"]]
    df_filtered.reset_index(drop=True, inplace=True)
    df_filtered = df_filtered.sort_values(by="strike", ascending=True)
    return [int(x) for x in df_filtered["token"].tolist()]

if __name__ == "__main__":
        # by default read from config unless cmd line argument given
        start = time.time()
        if (len(sys.argv)>1):
            START_DATE = sys.argv[1]
            END_DATE=START_DATE

    

        if (OPTIONS):
            UNIVERSE = get_all_options_nifty()
            all_data = DataStore(
                universe=UNIVERSE,
                start_date=START_DATE,
                end_date=END_DATE,
                data_building_date=DATA_BUILDING_DATE,
                data_path = DATA_LOC
            )
            # 35001,NIFTY27MAR25FUT
            # nifty token is int
            UNIVERSE.insert(0, NIFTY_TOKEN)
        else:
            if (NUM_TOKENS):
                UNIVERSE = get_universe(NUM_TOKENS)
            all_data = DataStore(
                universe=UNIVERSE,
                start_date=START_DATE,
                end_date=END_DATE,
                data_building_date=DATA_BUILDING_DATE,
                data_path = DATA_LOC
            )
        # all_data.mkt_data.to_csv("mkt_data.csv", index=False)
        locks = []
        processes = []

        # lock[0]-- general logger stdout

        # lock[1]: order.csv Exchange
        # lock[2]: order_final.csv Exchange
        # lock[3]: lakshya.csv Strategy
        # lock[4]: lakshya_predictors.csv staretegy
        # lock[5]: stats.csv
        for i in range(6):
            locks.append(Lock())
        delete_logs()

        if (OPTIONS):
            run_sim(locks, START_DATE, END_DATE, DATA_BUILDING_DATE, UNIVERSE, True, None, TIMER_TIME_SECONDS)
        else:
            for u in UNIVERSE:
                p = Process(target=run_sim, args = (locks, START_DATE, END_DATE, DATA_BUILDING_DATE, [u], False, all_data.mkt_data, TIMER_TIME_SECONDS))
                p.start()
                processes.append(p)

            for p in processes:
                p.join()
        end = time.time()
        print(f"main: {end-start} NUM_TOKENS:{NUM_TOKENS}")


# packet
# timestamp            1423214103259841034
# token                                757
# open                               -0.01
# high                               -0.01
# low                                -0.01
# close                              -0.01
# volume                                 0
# VWAP                                  -1
# LTP                              5369.95
# midprice                          5370.0
# l1_bid_vol                           125
# l1_ask_vol                            53
# timestamp_seconds    2025-02-06 09:15:03
# inst                                 757

