import datetime

from Exchange.logger import setup_logger, get_current_log_path, formatter, get_general_logger, get_csv_file_name
from Exchange.executor import Exchange, Order
import pdb
import numpy as np
import matplotlib.pyplot as plt


# for one instrument
class Position:
    def __init__(self):
        self.pnl = 0
        # (total buy orders - total sell orders) * lot size basically total open position
        self.quantity = 0
        self.lot = 1
        # number of buy and sell orders (divided by lot size)
        self.total_buy = 0
        self.total_sell = 0
        # total_buy + total_sell
        self.total_trades = 0
        # total buy + total_sell * lot size
        self.volume =  0

        # summation buy_price*qty*lotsize
        self.avg_buy = 0
        self.avg_sell = 0
        # total pnl = avg_sell-avg_buy
        # turnover is avg_buy + avg_sell
        self.turnover =0
        # list are divided by lot
        self.buy_list = []
        self.sell_list = []
        self.pnl_list = []
        # win_pnl = sum(pnl for pnl in pnl_list if pnl > 0)
        self.win_pnl = 0
        self.loss_pnl = 0
        # summation of self.pnl_list * lot size = pnl
        # self.winning_trades = 0
        # self.sharpe = 0
        # self.drawdown = 0




class StrategyModes:
    INTRADAY = 1 # this mode will liquidate position at 15:15 IST
    INTERDAY = 2 # this mode will not liquidate position at all

# general logger is written to at init of startegy and build_eod_report quantx/logs/20250205/stdout.log
# self.logger quantx/logs/20250205/20250205_lakshya.csv
class Strategy:
    """
    name: name is basically an identifier for the strategy used for initializing logger
    start_date: the date from which the strategy should start
    end_date : the end date when the strategy stops
    data_building_date :  the data start date for initializing predictors , must be less than start_date
    exchange : an exchange object to hit the orders to
    inst_live_pnl_map : dict of inst-pnl for currently open positions

    """
    def __init__(self, locks, universe: list, exchange: Exchange, name, start_date:str,
                 end_date:str, data_building_date):

        current_log_path = get_current_log_path()         # quantx/logs/20250205
        self.general_logger = get_general_logger()     # quantx/logs/20250205/stdout.log
        self.csv_file_name = get_csv_file_name()
        self.locks = locks
        self.name = name
        self.counter = 0
        # '20250205'
        self.start_date = start_date#datetime.datetime.strptime(start_date, "%Y%m%d").date()
        self.end_date = end_date#datetime.datetime.strptime(end_date, "%Y%m%d").date()
        self.data_building_date = data_building_date#datetime.datetime.strptime(data_building_date, "%Y%m%d").date()
        self.universe = universe
        self.exchange = exchange
        # difference between self.logger and general logger and predictor logger
        # name: lakshya_logger_20250205
        # log_file: quantx/logs/20250205/20250205_lakshya.csv
        self.logger  = setup_logger(locks[3], f"{self.name}_logger_{start_date}",
                                    f"{current_log_path}/{self.start_date}_{self.name}.csv",
                                    formatter)
        # name: lakshya_logger_20250205_predictors
        # log_file: quantx/logs/20250205/20250205_lakshya_predictors.csv
        self.predictor_logger = setup_logger(locks[4], f"{self.name}_logger_{start_date}_predictors",
                                   f"{current_log_path}/{self.start_date}_{self.name}_predictors.csv",
                                   formatter)
        # pdb.set_trace()
        self.last_pnl_update_time = None
        self.position = dict()  # {"HDFCBANK":{"quantity":10, "avg_buy":100}}
        headers = "inst,timestamp,timestamp, position,pnl"
        self.logger.info(headers)


        self.liquidation_time = datetime.time(15, 16)  # time to start liquidating intraday strats, default
        self.mode = StrategyModes.INTRADAY
        self.start_time = datetime.time(9, 15)
        self.inst_live_pnl_map = dict()
        self.inst_wise_pnl = dict()
        self.report_build = False
        self.eostrategy_report_build = False
        # fifo matching first buy order with first sell order.
        # should be per instr dictionary actually   
        self.buy_order_prices = {}
        self.sell_order_prices = {}
        self.pnl = []

#         2025-03-12 15:47:39,854 INFO, 
# universe:['757']
# start_date:20250205
# end_date:20250205


        # self.general_logger.info(f"\nuniverse:{self.universe}\nstart_date:{self.start_date}\n"
        #                     f"end_date:{self.end_date}\n")
        


        self.non_tradeable = set()
        self.liquidation_time = datetime.time(15, 15)
        self.report_building_time = datetime.time(15, 26)
        self.prev_date = None
        # pdb.set_trace()



     # # log_file: quantx/logs/20250205/20250205_lakshya.csv

    def log_pnl(self, packet):
        # print("in log_pnl")

        inst = packet.inst
        if inst not in self.position:
            return
        # pdb.set_trace()

        
        # what is this?
        #  if volume traded buy = volume traded sell then pnl = sellingprice-costprice
        # avg sell is summation volume* selling price
        if self.position[inst]["quantity"] == 0:
            pnl = self.position[inst]["avg_sell"] - self.position[inst]["avg_buy"]
        # for buy side
        # assuming the buy position is sold at packet.close
        elif self.position[inst]["quantity"] > 0:
            pnl = (self.position[inst]["avg_sell"] - self.position[inst]["avg_buy"] +
                   (self.position[inst]["quantity"] * float(packet.close)))
            
            # what is this?
            # above pnl is total pnl where is live pnl is for currently open positions
            self.inst_live_pnl_map[inst]["pnl"] = ((float(packet.close) - self.inst_live_pnl_map[inst]["last_fill_price"]) *
                                                   self.position[inst]["quantity"])
            
            self.inst_live_pnl_map[inst]["max_pnl"] = max(self.inst_live_pnl_map[inst]["pnl"],
                                                          self.inst_live_pnl_map[inst]["max_pnl"])
        # assuming the sell position is bought at packet.close
        elif self.position[inst]["quantity"] < 0:
            pnl = (self.position[inst]["avg_sell"] - self.position[inst]["avg_buy"] +
                   (self.position[inst]["quantity"] * float(packet.close)))
            self.inst_live_pnl_map[inst]["pnl"] = ((-float(packet.close) + self.inst_live_pnl_map[inst]["last_fill_price"])
                                                   * abs(self.position[inst]["quantity"]))
            self.inst_live_pnl_map[inst]["max_pnl"] = max(self.inst_live_pnl_map[inst]["pnl"],
                                                          self.inst_live_pnl_map[inst]["max_pnl"])
        # if pnl < -20000:
        #     self.non_tradeable.add(packet.inst)
        # throws error inst is int 757 .name_ist
        # self.inst_wise_pnl[inst.name_inst] = pnl 
        # inst wise pnl is updated here and used in eod report.
        self.inst_wise_pnl[inst] = pnl 


        # # log_file: quantx/logs/20250205/20250205_lakshya.csv
        log_line = f"{inst},{packet.timestamp},{packet.timestamp_seconds}, {self.position[inst]['quantity']},{pnl}"
        # print(log_line)
        self.logger.info(log_line)
        # pdb.set_trace()
        # if packet.inst.name_inst == "BANDHANBNK":
        #     print(self.inst_live_pnl_map[packet.inst], packet.inst)

    def check_log_pnl(self, packet):
        self.counter += 1
        if self.last_pnl_update_time is None:
            self.last_pnl_update_time = packet.timestamp
            return
        # if ((packet.timestamp == self.last_pnl_update_time) or
        #         (packet.timestamp - self.last_pnl_update_time).total_seconds() >= 500):
        #     print("abcdf, packet_timestamp, self.last_pnl_update_time", packet.timestamp, self.last_pnl_update_time)
        #     self.log_pnl(packet)
        # log at intervals of 500 seconds
        if ((packet.timestamp-self.last_pnl_update_time)//10**9)>=500:
            # print("abcdf, packet_timestamp, self.last_pnl_update_time", packet.timestamp_seconds, packet.timestamp, self.last_pnl_update_time)
            self.log_pnl(packet)
            self.last_pnl_update_time=packet.timestamp
            


#  strategy does nothing
    def on_data(self, packet):
        # print("inside on_data")
        # print("abcdef")
        # print(packet)
        self.check_log_pnl(packet)
        # self.exchange.place_order(packet.inst, packet.close, "BUY", 1, signal="COVER")

        # if time> 3:15 cancel pending orders and liquidate instrument
        # if packet.timestamp.time() > self.liquidation_time and self.mode == StrategyModes.INTRADAY:
        packet_time = packet.timestamp_seconds.time()
        packet_date = packet.timestamp_seconds.time()
  
        # print(packet_time)
        if packet_time > self.liquidation_time and self.mode == StrategyModes.INTRADAY:

            if packet.inst in self.position and self.position[packet.inst]["quantity"] != 0:
                self.exchange.cancel_pending_orders(packet)
                self.liquidate(packet)
            return False
        # if packet.timestamp.time() >= self.report_building_time:
        # if packet_time >= self.report_building_time:
        #     self.build_eod_report()
        #     return False

        # done in lakshya
        # packet date is moving 1 day ahead of enddate or startdate
        if packet_time >= self.report_building_time:
            self.build_eod_report(packet_date)
            # print("building eod report for", packet_date)
            return False
        # what is nontradeable
        if packet.inst in self.non_tradeable and self.position[packet.inst]["quantity"] == 0:
            return False
        return True

    def build_data(self, packet):
        pass # to be implemented in strategy

    def raise_day_begin(self, packet):
        print(packet.timestamp)
        pass

# general logger used
# built everyday
    def build_eod_report(self, date):
        # print("eod report")
        # quesstion: why not do the same logic for both modes. intraday uses self.position and interday uses self.inst_wise_pnl
        # positions have been liquidated for intraday therefore pnl can directly be calculated using self.position
        # for interday if calling build_eod_report every day, positions have not been liquidated so pnl would require complicated caluaction involving packet.close
        # this calulation is done in inst_wise_pnl on 500s basis. so we use that. pnl lagging behind
        #   
        # print(len(self.exchange.completed_order))
        if self.report_build:
            return
        # print(self.position)
        # print(self.inst_wise_pnl)

        if not self.report_build and self.mode == StrategyModes.INTRADAY:
            # print("in intraday")
            total_pnl = 0
            turnover = 0
            for key, value in self.position.items():
                # quantity =0 because positions are liquidated.
                inst_pnl = value['avg_sell'] - value['avg_buy']
                total_pnl += inst_pnl
                # what is turnover why is it so
                turnover += value['avg_sell'] + value['avg_buy']

                self.general_logger.info(f"{key}:{inst_pnl},{key}\n")
            self.general_logger.info(f"Total Orders:{len(self.exchange.completed_order)}\n")
            self.general_logger.info(f"Total PNL:{total_pnl}, START_DATE : {self.start_date}, CUR_DATE:{date}\n")
            self.general_logger.info("###############################################################################\n")

            self.report_build = True
        elif not self.report_build and self.mode == StrategyModes.INTERDAY:
            # print("in inter day")
            total_pnl = 0
            # pdb.set_trace()
            for key, value in self.inst_wise_pnl.items():
                self.general_logger.info(f"{key}:{value}\n")
                total_pnl += value
            self.general_logger.info(f"Total Orders:{len(self.exchange.completed_order)}\n")
            self.general_logger.info(f"Total PNL:{total_pnl}, START_DATE : {self.start_date}, CUR_DATE:{date}\n")
            self.general_logger.info("###############################################################################\n")

            self.report_build = True

    # called by exchange when order filled. 
    # updates self.position 

    def plot_equity_curve_and_drawdowns(self, equity_curve, drawdowns):
        # Plot PnL
        plt.subplot(3, 1, 1)
        plt.plot(self.pnl, label='PnL per Trade', color='blue')
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


    def update_position(self, inst):
        pos = self.position[inst]
        pos.total_trades = (pos.total_buy + pos.total_sell)
        pos.volume = pos.total_trades *pos.lot
        if (len(pos.sell_list)!=len(pos.buy_list)):
            print("buy, sell unequal")
            print("sell_list", len(pos.sell_list), pos.sell_list)
            print("buy_list", len(pos.buy_list), pos.buy_list)
        for i in range(min(len(pos.sell_list), len(pos.buy_list))):
            pos.pnl_list.append(pos.sell_list[i] - pos.buy_list[i])
        # pos.pnl_list = np.array(pos.sell_list) - np.array(pos.buy_list)
        pos.win_pnl = sum(pnl for pnl in pos.pnl_list if pnl > 0)*pos.lot
        pos.loss_pnl = sum(-pnl for pnl in pos.pnl_list if pnl < 0)*pos.lot
        pos.turnover = pos.avg_buy + pos.avg_sell
        pos.pnl = pos.avg_sell - pos.avg_buy
        pnl2 = sum(pos.pnl_list)*pos.lot
        pnl_close = abs(pos.pnl-pnl2)<=1e-2
        if (not pnl_close):
            print(f"pos.pnl {pos.pnl}, pnl2 {pnl2}") 
        # assert pnl_close
        # assert(pos.total_buy == len(pos.buy_list))
        # assert(pos.total_sell == len(pos.sell_list))
        # assert(pos.total_buy == pos.total_sell)
        # assert(pos.volume == pos.total_trades*pos.lot)


    def build_eostrategy_report(self):
        if self.eostrategy_report_build == True:
            return
        # self.universe[0] is not a problem because for options it is nifty token for equities we are parellizing per token so for each process there is only one element in self.universe
        self.general_logger.info(f"########################## End of startegy report for {self.universe[0]}#####################################\n")
        total_pnl = 0
        total_volume = 0
        total_trades = 0
        total_pnl_list = []
        win_pnl = 0
        loss_pnl = 0
        total_turnover = 0

        for inst in self.position:
            self.update_position(inst)
            pos = self.position[inst]
            self.general_logger.info(f"{inst}:{pos.pnl}\n")
            total_pnl+=pos.pnl
            total_volume+=pos.volume
            total_trades += pos.total_trades
            total_pnl_list.extend(pos.pnl_list)
            win_pnl += pos.win_pnl
            loss_pnl += pos.loss_pnl
            total_turnover+=pos.turnover

        winning_trades = sum(1 for pnl in total_pnl_list if pnl > 0)
        import math
        win_ratio = winning_trades / (total_trades - winning_trades) if (total_trades - winning_trades) != 0 else math.inf
        win_loss_points = win_pnl/loss_pnl if loss_pnl != 0 else math.inf
        pnl_turnover_ratio = (total_pnl / total_turnover) * 10_000 if total_turnover != 0 else 0


        if len(total_pnl_list) == 0 or np.std(total_pnl_list) == 0:
            sharpe = np.nan  # or set to 0, depending on your preference
        else:
            sharpe = np.mean(total_pnl_list) / np.std(total_pnl_list)
        sharpe_annualized = sharpe * np.sqrt(252)

        equity_curve = np.cumsum(total_pnl_list)
        running_max = np.maximum.accumulate(equity_curve)
        drawdowns = np.divide(
            equity_curve - running_max,
            running_max,
            out=np.zeros_like(equity_curve),
            where=running_max != 0
        )   
        if len(drawdowns) == 0:
            max_drawdown = np.nan  # or set to 0, depending on your use case
        else:
            max_drawdown = np.min(drawdowns)
        
                # Equity Curve Plot
        # self.plot_equity_curve_and_drawdowns(equity_curve, drawdowns)


        # write to general logger logs/{date}/stdout.csv
        self.general_logger.info(f"Total PNL:{total_pnl}, START_DATE : {self.start_date}, END_DATE:{self.end_date}\n")
        self.general_logger.info(f"Total Orders:{len(self.exchange.completed_order)}\n")
        self.general_logger.info(f"Total Trades: total quanity buys + sells:{total_trades}\n")
        self.general_logger.info(f"Total volume traded:  {total_volume}\n")
        self.general_logger.info(f"Winning Trades:{winning_trades}\n")
        self.general_logger.info(f"Win Ratio :{win_ratio}\n")
        self.general_logger.info(f"Win loss points:{win_loss_points}\n")
        self.general_logger.info(f"PNL turover ratio in bps:{pnl_turnover_ratio}\n")
        self.general_logger.info(f"Sharpe Annually: {sharpe_annualized}\n")
        self.general_logger.info(f"Drawdown: {max_drawdown}\n")
        self.general_logger.info("###############################################################################\n")


            #    'Token', 
            #     'PNL',
            #     'Total orders',
            #     'Total trades',
            #     'Volume traded',
            #     'Winning trades',
            #     'Win Loss Ratio',
            #     'Win loss points',
            #     'PNl turover ratio in bps',
            #     'Annualised Sharpe ratio',
            #     'Drawdown'

        # write to log/{date}/stat.csv
        row = [self.universe[0], total_pnl,len(self.exchange.completed_order),total_trades, total_volume,winning_trades,win_ratio, win_loss_points, pnl_turnover_ratio, sharpe_annualized, max_drawdown]
        import csv
        # No lock: risky in multiprocess
        with self.locks[5]:
            with open(self.csv_file_name, mode='a', newline='') as file:
                writer = csv.writer(file)
                writer.writerow(row)


        # write to a file in reports

        log_file = f"quantx/reports/{self.start_date}_stats"
        import os
        os.makedirs(os.path.dirname(log_file), exist_ok=True)


        from config import TIMER_TIME_SECONDS,CANDLE_TIME_FRAME, NIFTY_TOKEN
        with open(log_file, "w") as f:  
            f.write(f"Total PNL = {total_pnl}\n")
            f.write(f"Total Orders = {len(self.exchange.completed_order)}\n")  
            f.write(f"Total Trades (buys + sells) = {total_trades}\n")  
            f.write(f"Total Volume Traded = {total_volume}\n")  
            f.write(f"Winning Trades = {winning_trades}\n")  
            f.write(f"Win Ratio = {win_ratio}\n")  
            f.write(f"Win Loss Points = {win_loss_points}\n")  
            f.write(f"PNL Turnover Ratio (bps) = {pnl_turnover_ratio}\n")  
            f.write(f"Sharpe Annually = {sharpe_annualized}\n")  
            f.write(f"Drawdown = {max_drawdown}\n") 

            f.write("Config:\n")
            f.write(f"START_DATE = {self.start_date}\n")
            f.write(f"END_DATE = {self.end_date}\n")
            f.write(f"TIMER_TIME_SECONDS = {TIMER_TIME_SECONDS}\n")
            f.write(f"CANDLE_TIME_FRAME = {CANDLE_TIME_FRAME}\n")
            f.write(f"NIFTY_TOKEN = {NIFTY_TOKEN}\n") 
            f.write("#" * 79 + "\n")  # Separator line  

        # write to a csv in reports
        import csv
        report_dir = f"quantx/reports"
        os.makedirs(report_dir, exist_ok=True) 
        csv_file_path = os.path.join(report_dir, f"{self.start_date}_stats.csv")

        headers = [
            "Token",
            "PNL",
            "Total orders",
            "Total trades",
            "Volume traded",
            "Winning trades",
            "Win Loss Ratio",
            "Win loss points",
            "PNL turnover ratio in bps",
            "Annualized Sharpe ratio",
            "Drawdown"
        ]

        # Prepare the data row
        row = [
            self.universe[0],  # Token
            total_pnl,
            len(self.exchange.completed_order),
            total_trades,
            total_volume,
            winning_trades,
            win_ratio,
            win_loss_points,
            pnl_turnover_ratio,
            sharpe_annualized,
            max_drawdown
        ]

        # Write the data to CSV
        with open(csv_file_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            writer.writerow(row)

        print(f"Stats written to {csv_file_path}")
        
        self.eostrategy_report_build = True





    def on_order_update(self, order: Order):
        # print("inside on_order_update")
        # pdb.set_trace()
        # print(self.universe)
        if order.inst not in self.position:
            self.position[order.inst] = Position()
            # self.inst_live_pnl_map[order.inst] = {"pnl": 0, "max_pnl": 0, "last_fill_price": 0}
        pos = self.position[order.inst]
        pos.lot = order.lot
        num_orders = int(order.quantity/order.lot)

        if order.side == Order.BUY and order.status == Order.FILLED:
            for _ in range(num_orders):
                pos.buy_list.append(float(order.fill_price))
                pos.total_buy+=1
            pos.quantity += order.quantity 
            pos.avg_buy += order.quantity * float(order.fill_price)
        elif order.side == Order.SELL and order.status == Order.FILLED:
            for _ in range(num_orders):
                pos.sell_list.append(float(order.fill_price))
                pos.total_sell+=1
            pos.quantity -= order.quantity
            pos.avg_sell += abs(order.quantity) * float(order.fill_price)
        
        # why order type != order.limit?
        # if self.position[order.inst]["quantity"] != 0 and order.FILLED and order.order_type != Order.LIMIT:
        # if self.position[order.inst]["quantity"] != 0 and order.FILLED :
            # self.inst_live_pnl_map[order.inst]["last_fill_price"] = float(order.fill_price)
        # why initializing?
        # becuase since position is closed there is no live pnl
        # elif self.position[order.inst]["quantity"] == 0 and order.FILLED:
            # self.inst_live_pnl_map[order.inst] = {"pnl": 0, "max_pnl": 0, "last_fill_price": 0}


    # close all positions
    def liquidate(self, packet):
        inst = packet.inst
        if self.position[inst]["quantity"] > 0:
            self.exchange.place_order(inst, packet.close, "SELL", abs(self.position[inst]["quantity"]),
                                      order_type=Order.LIQUIDATE)
        elif self.position[inst]["quantity"] < 0:
            self.exchange.place_order(inst, packet.close, "BUY", abs(self.position[inst]["quantity"]),
                                      order_type=Order.LIQUIDATE)()
