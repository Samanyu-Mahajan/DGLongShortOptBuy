import pandas as pd
import datetime as dt
from copy import copy

import streaming_indicators as si
from collections import deque

from collections import OrderedDict
from Exchange.executor import Exchange, Order
from .base_strategy import Strategy, StrategyModes
import pyarrow as pa
from predictors.predictors import *
import pdb



# Target and SL checks
# for long position
# close > SMA target hit
# close < SL_price SL hit
# for short position
# close < SMA target hit
# close > SL_price SL hit

class TRANSACTION:
    BUY = "BUY"
    SELL = "SELL"

class DGLongShortRev(Strategy):
    '''
    description: Reversal of DGLongShort for equity
    params:
        symbol: text
        start_time: time
        squareoff_time: time
        qty: number,1
        max_qty: number,1
        sl_percent: number,.01
    '''
    __version__ = '1.0.0'
    STATE_INITIAL = 'INITIAL'
    STATE_SQUAREDOFF = 'SQUAREDOFF'

# self.params:
# self.params['qty']
# self.params['max_qty']
# self.params['sl_percent'] eg 20
# self.params['symbol']
# self.params['start_time']
# self.params['squareoff_time']



# self.trader.fetch_candle
# self.trader.get_instrument
    def __init__(self, *args, data_obj, params):
        super().__init__(*args)
        self.params = params
        self.data_obj = data_obj
        self.inst_wise_df = dict()
        # max quantity + or - one can reach
        self.start_time = dt.time(9,15)
        self.setup_time = dt.time(9,20)
        self.max_qty = params['max_qty']
        self.qty=1
        self.instrument = int(self.universe[0])
        self.sl_perc = params['sl_perc']
        self.bool_setup = False
        self.packet_data = pd.DataFrame(columns=['datetime', 'open', 'high', 'low', 'close'])
        self.packet_cnt = 0
        self.last_update_dt = None
        self.upd = False
        self.state = self.STATE_INITIAL
        self.update_time_gap = dt.timedelta(seconds=params['update_time_gap_seconds'])
        self.tf = dt.timedelta(seconds=params['candle_tf'])






    def setup(self, t):
        # self.symbol = self.params['symbol'].upper()
        # self.instrument = self.trader.get_instrument({'exchange':'NSE', 'symbol':self.symbol})
        # if(self.instrument is None):
        #     self.logger.error(f"No instrument found for symbol '{self.symbol}'")
        #     raise Exception("InstrumentNotFound")
        # self.qty = int(self.params['qty'])
        # self.max_qty = int(self.params['max_qty'])
        # self.sl_perc = float(self.params['sl_percent'])/100
        


        # indicators

        self.RSI = si.RSI(14)
        self.prev_RSI = deque(maxlen=3)
        self.PLUS_DI = si.PLUS_DI(14)
        self.prev_PLUS_DI = deque(maxlen=3)
        self.MINUS_DI = si.PLUS_DI(14)
        self.prev_MINUS_DI = deque(maxlen=3)
        self.BBANDS = si.BBands(14, 2)
        self.SMA = si.SMA(7)
        self.update_indicators(t)

        self.position_count = 0

        return True

    def update_indicators(self, t):
        # function to fetch candles and update indicators
        if(self.last_update_dt is None):
            candles = self.data_obj.fetch_candle(self.instrument, t-dt.timedelta(minutes=5), t, self.tf)
            # print(candles)
            # return
            if(candles is None):
                self.logger.error(f"No historical candles")
                raise Exception("NoHistoricalData")
        else:#if(self.last_update_dt < t):
            candles = self.data_obj.fetch_candle(self.instrument, self.last_update_dt, t, self.tf)
            # print(candles)
            if(candles is None):
                self.logger.error(f"Live candle not received")
                # raise Exception("NoLiveData")
                return False
        if(not isinstance(candles, pd.DataFrame)): candles = pd.DataFrame([candles])
        if(len(candles) == 0):
            self.logger.error(f"No candles received")
            return False
        for _, candle in candles.iterrows():
            rsi = self.RSI.update(candle['close'])
            self.prev_RSI.append(rsi)
            plus_di = self.PLUS_DI.update(candle)
            self.prev_PLUS_DI.append(plus_di)
            minus_di = self.MINUS_DI.update(candle)
            self.prev_MINUS_DI.append(minus_di)
            self.BBANDS.update(candle['close'])
            self.SMA.update(candle['close'])
            self.last_update_dt = candle['datetime'] + self.tf
        if(len(self.prev_RSI) >= 3 and self.prev_RSI[-3] is None):
            self.logger.error(f"RSI values not set yet")
            return False
        self.rsi_rc = (self.prev_RSI[-1] - self.prev_RSI[-3]) / self.prev_RSI[-3] * 100
        self.plus_di_rc  = (self.prev_PLUS_DI[-1]  - self.prev_PLUS_DI[-3] ) / self.prev_PLUS_DI[-3]  * 100
        self.minus_di_rc = (self.prev_MINUS_DI[-1] - self.prev_MINUS_DI[-3]) / self.prev_MINUS_DI[-3] * 100
        self.band_diff = (self.BBANDS.upperband - self.BBANDS.lowerband) / candle['close'] * 100
        self.candle = candle
        return True

    def update(self, t):
        updated = self.update_indicators(t)
        if(not updated): return False
        if(self.position_count < self.max_qty and self._long_condition()):
            self.logger.info("Long condition met")
            entry_price = self.place_order(TRANSACTION.BUY)
            self.position_count += 1
            if(self.position_count > 0):
                # it's in long
                self.sl_price = round(entry_price - self.sl_perc * entry_price, 2)
                self.logger.debug(f"SL for long: {self.sl_price}")
               
        elif(self.position_count > -self.max_qty and self._short_condition()):
            self.logger.info("Short condition met")
            entry_price = self.place_order(TRANSACTION.SELL)
            self.position_count -= 1
            if(self.position_count < 0):
                # it's in short
                self.sl_price = round(entry_price + self.sl_perc * entry_price, 2)
                self.logger.debug(f"SL for short: {self.sl_price}")

        # Target and SL checks
        # for long position
        # close > SMA target hit
        # close < SL_price SL hit
        # for short position
        # close < SMA target hit
        # close > SL_price SL hit
        if(self.position_count > 0):
            _exit = False
            if(self.candle['close'] > self.SMA.value):
                self.logger.info("Target hit on LONG side")
                _exit = True
            elif(self.candle['close'] < self.sl_price):
                self.logger.info("SL hit on LONG side")
                _exit = True
            if(_exit):
                self.place_order(TRANSACTION.SELL, self.position_count)
                self.position_count = 0
        elif(self.position_count < 0):
            _exit = False
            if(self.candle['close'] < self.SMA.value):
                self.logger.info("Target hit on SHORT side")
                _exit = True
            elif(self.candle['close'] > self.sl_price):
                self.logger.info("SL hit on SHORT side")
                _exit = True
            if(_exit):
                self.place_order(TRANSACTION.BUY, -self.position_count)
                self.position_count = 0
        return True

    # def _long_condition(self):
    def _short_condition(self):
        return (
            (self.candle['high'] > self.BBANDS.upperband) &
            (self.rsi_rc > 5) &
            (self.plus_di_rc > 5) &
            (self.band_diff > 0.4)
        )

    # def _short_condition(self):
    def _long_condition(self):
        return (
            (self.candle['low'] < self.BBANDS.lowerband) &
            (self.rsi_rc <= -5) &
            (self.minus_di_rc < -5) &
            (self.band_diff > 0.4)
        )
    # def place_order(self, inst, price, side, quantity, order_type=Order.AGGRESSIVE, signal=""):

    def place_order(self, side, qty=1):
        order_id = self.exchange.place_order(self.instrument, self.candle['close'], side, qty*self.qty)
        if(order_id is None):
            self.logger.error(f"Error in placing order in {side}")
            raise Exception("OrderPlacementException")
        # order = self.trader.fetch_order(self, order_id)
        # self.logger.info(f"{side} {qty} at {order['traded_price']}")
        return self.candle['close']
        

    # not doing self.position_count = 0
    def squareoff(self, t):
        self.logger.debug("squaring off...")
        if(self.position_count > 0):
            self.place_order(TRANSACTION.SELL, self.position_count)
        elif(self.position_count < 0):
            self.place_order(TRANSACTION.BUY, -self.position_count)
        self.state = self.STATE_SQUAREDOFF
        return True
    
    def schedule(self, t):
        from apscheduler.triggers.date import DateTrigger
        start_dt = dt.datetime.combine(t,dt.datetime.strptime(self.params['start_time'],'%H:%M').time())
        end_dt = dt.datetime.combine(t,dt.datetime.strptime(self.params['squareoff_time'],'%H:%M').time())
        
        # self.trader.schedule(self.name, DateTrigger(start_dt-utils.get_timedelta('1m')), 'setup')
        self.trader.subscribe(self.name, 'start', 'setup')
        self.trader.schedule(self.name, DateTrigger(end_dt), 'squareoff')
        
        from AlgoTrading.schedules import get_schedule
        update_sched = get_schedule((start_dt).strftime('%H:%M'),(end_dt-utils.get_timedelta('10s')).strftime('%H:%M'), '1m')
        self.trader.schedule(self.name, update_sched, 'update')



    def on_data(self, packet):
        self.packet_cnt += 1
        t = packet.timestamp_seconds
        time = t.time()  
        date = t.date()

        # new_row = {
        #     'datetime': packet.timestamp_seconds,
        #     'open': packet.open,
        #     'high': packet.high,
        #     'low': packet.low,
        #     'close': packet.close
        # }
        # if self.packet_data.empty:
        #     self.packet_data = pd.DataFrame([new_row])
        # else:
        #     self.packet_data = pd.concat([self.packet_data, pd.DataFrame([new_row])], ignore_index=True)

        
        # print(len(self.packet_data))
        # from_dt = dt.datetime.combine(date, dt.time(9, 15, 0))   # 9:15:00
        # to_dt   = dt.datetime.combine(date, dt.time(9, 15, 10))
        # tf = '5s'
        # if (self.packet_cnt>10):
        #     print("self.packet_data", self.packet_data)
        #     candles = self.fetch_candle(from_dt, to_dt, tf)
        #     print(candles)
        
        if (not self.bool_setup and time >= self.setup_time ):
            # print("setting up once", t)
            self.setup(t)
            self.bool_setup = True
            # print("self.last_updated_time", self.last_update_dt)
        elif self.bool_setup and self.last_update_dt is not None and (t - self.last_update_dt) >= self.update_time_gap and time<self.liquidation_time:
            # print("updating once")
            self.upd = True
            # self.update(t)
            # print("self.last_updated_time", self.last_update_dt)
        elif self.state != self.STATE_SQUAREDOFF and time>=self.liquidation_time:
            self.squareoff(t)
        elif time>= self.report_building_time:
            # print(time)
            self.build_eostrategy_report()



    def on_timer(self, t):

        if self.bool_setup and self.last_update_dt is not None and (t - self.last_update_dt) >= self.update_time_gap and t.time()<self.liquidation_time:
            # print("t", t)
            updated = self.update(t)
            # print("last_updated_dt", self.last_update_dt)
            return updated
        return False