import datetime
import time
from collections import OrderedDict
from Exchange.executor import Exchange, Order
from .base_strategy import Strategy, StrategyModes
import pyarrow as pa
from predictors.predictors import *
import pdb


class CWA2SSigma(Strategy):
    def __init__(self, *args):
        super().__init__(*args)
        # inst_wise_df.append[packet.timestamp_seconds, float(packet.open), float(packet.high),float(packet.low), float(packet.close)]
        self.inst_wise_df = dict()
        self.inst_wise_predictors = dict()
        self.period = 14  # for halftrend and dmi
        self.counter = 0
        self.liquidation_time = datetime.time(15, 15)
        self.report_building_time = datetime.time(15, 26)
        self.start_trading = False
        self.inst_map = dict()  # keep , returns, ltp here
        self.mode = StrategyModes.INTERDAY
        # self.mode = StrategyModes.INTRADAY
        # print("mode:", self.mode)
        self.inst_wise_triggers = dict()
        self.inst_wide_risk = dict()
        self.inst_wide_return = dict()
        self.top_gainers = set()
        self.top_losers = set()
        self.loser_min_max = dict()
        self.order_count = 0
        headers = ("inst,timestamp,open,low,high,close,low_1,high_1,high_int,low_int,half_trend,atr_up,atr_down,"
                   "half_trend_value,di_plus,di_minus,adx_smooth,cheetan,risk")
        self.predictor_logger.info(headers)

    def compute_gainers_lossers(self, gainer_len=10, loser_len=10):
        table = pa.table([
            pa.array(self.inst_wide_return.keys()),
            pa.array(self.inst_wide_return.values()),
        ], names=["keys", "values"])
        sorted_table = table.sort_by([("values", "descending")])
        self.top_gainers = set(str(x) for x in sorted_table[0:gainer_len][0])
        self.top_losers = set(str(x) for x in sorted_table[-loser_len:][0])
        # print(self.top_losers, self.top_gainers)


# append packets timestamp, ohlc to inst_wise_df
    def build_data(self, packet):
        if packet.inst not in self.inst_wise_df:
            self.inst_wise_df[packet.inst] = list()
        self.inst_wise_df[packet.inst].append([packet.timestamp, float(packet.o), float(packet.h),
                                               float(packet.l), float(packet.c)])

    def on_begin(self):
        self.momemtum_df = pd.DataFrame()
        for symbol in self.universe:
            print(symbol)
            # what is happening?
            current_stock = pd.read_csv(f"/Users/dg/data/{symbol}.NS.yfinance_stock_data.csv.momentum")
            pdb.set_trace()
            current_stock["symbol"] = symbol
            self.momemtum_df = pd.concat([self.momemtum_df, current_stock])
        self.momemtum_df = self.momemtum_df[
            ["Date", "symbol", "Open", "High", "Low", "Close", "Momentum_10", "Momentum_20", "Momentum_30",
             "Momentum_40", "Momentum_50", "Momentum_90", "Momentum_60"]]
        self.momemtum_df['Date'] = pd.to_datetime(self.momemtum_df['Date']).dt.date
        self.momemtum_df = self.momemtum_df[
            (self.momemtum_df["Date"] >= self.data_building_date) & (self.momemtum_df["Date"] <= self.end_date)]
        
        # in column top rank 10, for each date, rank 1 to highest momentum
        self.momemtum_df['Top_Rank_10'] = self.momemtum_df.groupby('Date')['Momentum_10'].rank(ascending=False)
        self.momemtum_df['Top_Rank_20'] = self.momemtum_df.groupby('Date')['Momentum_60'].rank(ascending=False)
        self.momemtum_df['Bottom_Rank_10'] = self.momemtum_df.groupby('Date')['Momentum_10'].rank(ascending=True)
        self.momemtum_df['Bottom_Rank_20'] = self.momemtum_df.groupby('Date')['Momentum_40'].rank(ascending=True)

    # def check_log_pnl(self, packet):
    #     self.counter += 1
    #     if self.last_pnl_update_time is None:
    #         self.last_pnl_update_time = packet.timestamp
    #         return
    #     if ((packet.timestamp == self.last_pnl_update_time) or
    #             (packet.timestamp - self.last_pnl_update_time).total_seconds() >= 500):
    #         self.log_pnl(packet)
        # print((self.last_packet_time - self.last_pnl_update_time).total_seconds(), packet.timestamp)


# data: packet.timestamp_seconds, float(packet.open), float(packet.high),float(packet.low), float(packet.close
    def cheetah(self, data, len=6, min_true=5):
        greater_close = 0
        greater_high = 0
        lower_low = 0
        lower_close = 0
        low_value = data[0][2]
        high_value = data[0][1]
        for i in range(1, len):
            low_value = min(data[i][2], low_value)
            high_value = max(data[i][1], high_value)
            if data[i][1] > data[i - 1][1]:
                greater_high += 1
            if data[i][3] > data[i - 1][3]:
                greater_close += 1
            if data[i][2] < data[i - 1][2]:
                lower_low += 1
            if data[i][3] < data[i - 1][3]:
                lower_close += 1
        # if the number of occurences where the close of data[i] is greater than close of data[i-1] is >= 5
        # if price is increasing then buy else sell
        if greater_close >= min_true or greater_high >= min_true:
            return "BUY", low_value
        if lower_low >= min_true or lower_close >= min_true:
            return "SELL", high_value
        return False, low_value

    def calculate_predictors(self, df, inst):
        # pdb.set_trace()
        # if inst not in self.inst_wise_predictors:
        #     self.inst_wise_predictors[inst] = list()
        # inst_data_len = len(self.inst_wise_predictors[inst])
        # if inst_data_len > 28:
            # self.inst_wise_predictors[inst] = self.inst_wise_predictors[inst][inst_data_len - 28:]
        
        # what are these?
        df = halftrend_brute(df)
        df = dmi(df)
        df = CWA2sigma(df)
        last_candle = df.tail(1).iloc[0]
        signal, risk = self.cheetah(self.inst_wise_df[inst][-10:], 3,2)
        last_line = last_candle.to_string(index=False, header=False).replace("\n", "#").replace(" ", ""
                                                                                                ).replace("#", ",")
        last_line = f"{inst},{last_line},{signal},{risk}"
        # self.inst_wise_predictors[inst].append(last_line.split(","))
        self.predictor_logger.info(f'{last_line},{signal},{risk}')
        return last_candle, signal, risk

    # def update_inst_info(self, packet):
    #     inst = packet.inst.name_inst
    #     if inst not in self.inst_map:
    #         self.inst_map[inst] = dict()
    #         self.inst_map[inst]["open"] = packet.o
    #         self.inst_map[inst]["day_high"] = packet.h
    #         self.inst_map[inst]["prev_close"] = self.inst_wise_df[packet.inst][-1][4]
    #     self.inst_map[inst]["ltp"] = packet.c
    #     self.inst_map[inst]["day_high"] = max(self.inst_map[inst]["day_high"], packet.h)
    #     self.inst_map[inst]["return"] = ((-self.inst_map[inst]["prev_close"] +
    #                                              float(packet.c))/self.inst_map[inst]["prev_close"]) * 100
    #     self.inst_wide_return[inst] = self.inst_map[inst]["return"]
    #     if len(self.inst_map) > 10:
    #         self.compute_gainers_lossers()

    def on_data(self, packet):
        # print(packet.inst)
        # pdb.set_trace()
        # return
        self.check_log_pnl(packet)

        packet_date = packet.timestamp_seconds.date()  # Get the date part
        packet_time = packet.timestamp_seconds.time()

        # print(packet.timestamp_seconds)

        if self.prev_date is None or packet_date != self.prev_date:
            # It's a new day
            self.order_count = 0
            self.prev_date = packet_date
            # uncomment this if you want every day reports
            self.report_build=False
        # interday stragy no liquidation
        end_date_obj = datetime.datetime.strptime(self.end_date, "%Y%m%d").date()
        # packet date is moving 1 day ahead of enddate or startdate

        if packet_time > self.liquidation_time:
            # if intraday then liquidate
            if (self.mode == StrategyModes.INTRADAY): 
                if packet.inst in self.position and self.position[packet.inst]["quantity"] != 0:
                    self.exchange.cancel_pending_orders(packet)
                    self.liquidate(packet)
            # if interday then liquidate at last day
            else:
                if (packet_date == end_date_obj + datetime.timedelta(days=1)) :
                    if packet.inst in self.position and self.position[packet.inst]["quantity"] != 0:
                        self.exchange.cancel_pending_orders(packet)
                        self.liquidate(packet)
    
        if packet_time >= self.report_building_time:
            # uncomment to build eod reports
            # self.build_eod_report(packet_date)
            if packet_date == end_date_obj + datetime.timedelta(days=1):
                self.build_eostrategy_report()
                # pass






        if self.order_count >= 100:
            return
        # print(self.order_count)
        # if packet.inst not in self.inst_wise_df:
        #     self.inst_wise_df[packet.inst] = list()
        # self.inst_wise_df[packet.inst].append([packet.timestamp_seconds, float(packet.open), float(packet.high),
        #                                        float(packet.low), float(packet.close)])
        # data_size = len(self.inst_wise_df[packet.inst])
        # # keep the latest 300 packets
        # # what if data_size < 300 still works
        # # pdb.set_trace()
        # # max(0, data_size-300)?
        # self.inst_wise_df[packet.inst] = self.inst_wise_df[packet.inst][max(0,data_size - 300):]
        # df = pd.DataFrame(self.inst_wise_df[packet.inst], columns=["timestamp", "open", "low", "high", "close"])
        

        # pdb.set_trace()
        # if data_size > 15:
            # self.calculate_predictors(df, packet.inst)


            # last_candle, signal, risk=self.calculate_predictors(df, packet.inst)
            # pdb.set_trace()
        if self.order_count < 100:
            # what is signal cover?
            self.exchange.place_order(packet.inst, packet.close, "BUY", 1, signal="COVER")
            self.order_count +=1
            # else:
            #     self.exchange.place_order(packet.inst, packet.close, "SELL", 1, signal="COVER")
        # no liquidation??


        # current_momemtum_df = self.momemtum_df[(self.momemtum_df["Date"] == packet.timestamp.date()) & (
        #     self.momemtum_df["symbol"] == packet.inst.name_inst) & (self.momemtum_df["Top_Rank_10"] <= 10) &
        #                                        (self.momemtum_df["Bottom_Rank_10"] <= 10)]

        # if len(current_momemtum_df)==0:
        #     return
        # go_ahead = super().on_data(packet)
        # if not go_ahead:
        #     return
        # if packet.timestamp.date() < self.start_date:
        #     self.build_data(packet)
        #     return
        # if packet.timestamp.time() > self.liquidation_time and self.mode == StrategyModes.INTRADAY:
        #     if packet.inst in self.position and self.position[packet.inst]["quantity"] != 0:
        #         self.exchange.cancel_pending_orders(packet)
        #         self.liquidate(packet)
        #     if packet.timestamp.time() >= self.report_building_time:
        #         self.build_eod_report()
        #     return  # will not take new positions after liquidation time

        # if packet.inst not in self.inst_wise_df:
        #     self.non_tradeable.add(packet.inst)
        #     return
        # self.inst_wise_df[packet.inst].append([packet.timestamp, float(packet.o), float(packet.h),
        #                                        float(packet.l), float(packet.c)])
        # data_size = len(self.inst_wise_df[packet.inst])
        # trim data and calculate signals

        # if packet.inst in self.non_tradeable and packet.inst in self.position and self.position[packet.inst]["quantity"] == 0:
        #     return
        # if data_size > 300:
        #     if not (self.counter % 15 == 0):
        #         return
        #     df = pd.DataFrame(self.inst_wise_df[packet.inst], columns=["timestamp", "open", "low", "high", "close"])
        #     df['timestamp'] = pd.to_datetime(df['timestamp'])
        #     df.index = df.timestamp
        #     df = df.resample('30min').agg({
        #         'open': 'first',  # First value in the 5-minute interval
        #         'high': 'max',  # Maximum value in the 5-minute interval
        #         'low': 'min',  # Minimum value in the 5-minute interval
        #         'close': 'last',  # Last value in the 5-minute interval
        #         # 'volume': 'sum'  # Sum of all volumes in the 5-minute interval
        #     })
        #     self.update_inst_info(packet)
        #     self.inst_wise_df[packet.inst] = self.inst_wise_df[packet.inst][data_size - 300:]
        #     df = pd.DataFrame(self.inst_wise_df[packet.inst], columns=["timestamp", "open", "low", "high", "close"])
        #     predictor, signal, risk = self.calculate_predictors(df, packet.inst)
        #     half_trend_signal = predictor["half_trend"] == "long"
        #     dmi_buy = predictor["di_plus"] > predictor["di_minus"]
        #     di_plus, di_minus = predictor["di_plus"], predictor["di_minus"]
        #     cwa2sigma = predictor["close"] > predictor["UB"]
        #     cwa2sigma_sell = predictor["close"] < predictor["LB"]
        #     min_size = 500000

            #Order Logic

            # if self.start_time < packet.timestamp.time():
            #     inst_name = packet.inst.name_inst
            #     if packet.inst in self.position:
            #         current_pos = abs(self.position[packet.inst]["quantity"])
            #     if signal == "BUY" and (float(packet.c) - risk)/risk * 100 > 0.25 and cwa2sigma:
            #         # if packet.inst in self.inst_live_pnl_map:
            #         #     print(self.inst_live_pnl_map[packet.inst], packet.timestamp, self.position)
            #         if packet.inst not in self.position and (inst_name in self.top_gainers or cwa2sigma):
            #             self.exchange.place_order(packet.inst, packet.c, "BUY",
            #                                       int(min_size // packet.c), signal="CHEETAH")
            #
            #             # self.exchange.place_order(packet.inst, float(packet.c) * 1.005, "SELL",
            #             #                           int(min_size // (packet.c * 2)),
            #             #                           order_type=Order.LIMIT)
            #             # self.exchange.place_order(packet.inst, float(packet.c) * 1.005, "SELL",
            #             #                           int(min_size // (packet.c)),
            #             #                           order_type=Order.LIMIT)
            #             # make position if no position and remove half quantity at order at 30 bps
            #         elif packet.inst in self.position and self.position[packet.inst]["quantity"] < 0:
            #             self.exchange.cancel_pending_orders(packet)
            #             self.exchange.place_order(packet.inst, packet.c, "BUY", current_pos*2, signal="COVER")
            #         elif (packet.inst in self.position and self.position[packet.inst]["quantity"] == 0 and
            #               packet.inst in self.top_gainers):
            #             self.exchange.place_order(packet.inst, packet.c, "BUY",
            #                                       int(min_size // packet.c), signal="CHEETAH")
            #             # self.exchange.place_order(packet.inst, float(packet.c) * 1.005, "SELL",
            #             #                           int(min_size // (packet.c * 2)),
            #             #                           order_type=Order.LIMIT)
            #
            #     if signal == "SELL" and (risk - float(packet.c))/risk * 100 > 0.25:
            #         if (risk - float(packet.c))/risk * 100 > 0.50:
            #             if (packet.inst in self.position and self.position[packet.inst]["quantity"] > 0):
            #                 self.exchange.cancel_pending_orders(packet)
            #                 self.exchange.place_order(packet.inst, packet.c, "SELL", current_pos*2, signal="COVER")
            #             # cover order
            #         if ((packet.inst not in self.position or self.position[packet.inst]["quantity"] == 0)
            #                 and not half_trend_signal) and (inst_name in self.top_losers or cwa2sigma_sell):
            #             self.exchange.place_order(packet.inst, packet.c, "SELL", int(min_size // packet.c),
            #                                       signal="CHEETAH")
            #             # self.exchange.place_order(packet.inst, float(packet.c) * 0.995, "BUY",
            #             #                           int(min_size // (packet.c * 2)), order_type=Order.LIMIT)
            #             # self.exchange.place_order(packet.inst, float(packet.c) * 0.995, "BUY",
            #             #                           int(min_size // (packet.c)))
            #     if packet.inst in self.position and self.inst_live_pnl_map[packet.inst]["pnl"] < -6000:
            #         if self.position[packet.inst]["quantity"] > 0:
            #             self.exchange.cancel_pending_orders(packet)
            #             self.exchange.place_order(packet.inst, packet.c, "SELL", current_pos, signal="MAX_LOSS")
            #         elif self.position[packet.inst]["quantity"] < 0:
            #             self.exchange.cancel_pending_orders(packet)
            #             self.exchange.place_order(packet.inst, packet.c, "BUY", current_pos)
            #     elif packet.inst in self.position and self.inst_live_pnl_map[packet.inst]["max_pnl"] > 6000:
            #         if (self.position[packet.inst]["quantity"] !=0 and
            #                 (self.inst_live_pnl_map[packet.inst]["pnl"]/self.inst_live_pnl_map[packet.inst]["max_pnl"]) * 100 < 70):
            #             self.exchange.cancel_pending_orders(packet)
            #             # print((self.inst_live_pnl_map[packet.inst]["pnl"]/self.inst_live_pnl_map[packet.inst]["max_pnl"]),
            #             #       packet.inst, self.inst_live_pnl_map[packet.inst]["pnl"], self.inst_live_pnl_map[packet.inst]["max_pnl"])
            #             if self.position[packet.inst]["quantity"] > 0:
            #                 self.exchange.place_order(packet.inst, packet.c, "SELL", current_pos, signal="TRAINING")
            #             elif self.position[packet.inst]["quantity"] < 0:
            #                 self.exchange.place_order(packet.inst, packet.c, "BUY", current_pos, signal="TRAILING")
            #
            #

                # remove position if it goes down by 1 percent
                # if packet.inst in self.position and self.position[packet.inst]["quantity"] > 0:
                #     if ((float(self.inst_live_pnl_map[packet.inst]["last_fill_price"]) - float(packet.c))
                #         / float(self.inst_live_pnl_map[packet.inst]["last_fill_price"]) * 100) > 0.5:
                #         self.exchange.place_order(packet.inst, packet.c, "SELL",
                #                                   current_pos)  # elif self.position[packet.inst]["quantity"] >= 0:
                # if packet.inst in self.position and self.position[packet.inst]["quantity"] < 0:
                #     if ((-float(self.inst_live_pnl_map[packet.inst]["last_fill_price"]) + float(packet.c))
                #         / float(self.inst_live_pnl_map[packet.inst]["last_fill_price"]) * 100) > 0.5:
                #         self.exchange.place_order(packet.inst, packet.c, "BUY",
                #                                   current_pos)
                    #     self.exchange.place_order(packet.inst, packet.c, "SELL", 1)
                # self.exchange.place_order(packet.inst, packet.c, "SELL", 1)
            # print(predictor_df)
        # print(self.inst_wise_df[packet.inst])
        # print(self.inst_wise_df)
        # print(self.inst_wise_df)
        # print(packet)
