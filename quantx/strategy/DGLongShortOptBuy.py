import pandas as pd
import datetime as dt
from copy import copy

# from AlgoTrading import utils, ORDER, TRANSACTION
# from AlgoTrading.Strategies import BaseStrategy

from Exchange.executor import Exchange, Order
from .base_strategy import Strategy, StrategyModes

import streaming_indicators as si
from collections import deque
import pandas as pd
import os


class DGLongShortOptBuy(Strategy):
    '''
    description: identifies long conditions, enters call option , places buy order on strike closest to candle.close(underlying)
    fetch premium candles for the last 3 minutes. get the sl_price as the min of lows of premium candles, place tgt order.
    params:
        symbol: text
        start_time: time
        squareoff_time: time
    '''
    __version__ = '1.0.0'
    STATE_INITIAL = 'INITIAL'
    STATE_SQUAREDOFF = 'SQUAREOFF'

    OPT_TYPES = ['CALL','PUT']


    def get_all_options_nifty(self,file_path="quantx/prices/2025-02-17.csv", expiry_date = "27MAR2025"):
        # if os.path.isfile(file_path):
            # print("is file")
        df = pd.read_csv(file_path, dtype={"token": str}, low_memory=False)  # Fix applied here
        # df = pd.read_csv(file_path)
        df = df[(df["instrumenttype"] == "OPTIDX")& (df['name'] == "NIFTY") & (df['expiry'] == expiry_date)]
        df["strike"] = df["strike"] / 100
        df["opt_type"] = df["symbol"].str[-2:]  # Last two characters (CE or PE)
        df["opt_type"] = df["opt_type"].map({"CE": "CALL", "PE": "PUT"})  # Map to readable format
        df_filtered = df[["token", "opt_type", "strike", "lotsize"]]
        df_filtered.reset_index(drop=True, inplace=True)
        df_filtered = df_filtered.sort_values(by="strike", ascending=True)
        return df_filtered

    def find_option_premium(self, opt_token):
        # print("option token", opt_token)
        if opt_token in self.ltp:
            premium = self.ltp[opt_token]
            # print("premium", premium)
            return premium
        else:
            # print("option premium not found")
            df = self.data_obj.mkt_data
            df = df[df['token']==opt_token]
            premium = df.iloc[0]['open']
            # print("premium", premium)
            return premium
    
    def __init__(self, *args, data_obj, underlying_data_obj, params):
        super().__init__(*args)
        self.instrument = int(self.universe[0])
        self.tf = dt.timedelta(seconds=5)
        self.packet_cnt=0
        self.bool_setup=False
        self.start_time = dt.time(9,15)
        self.setup_time = dt.time(9,20)
        self.ltp = {}
        self.data_obj = data_obj
        self.underlying_data_obj = underlying_data_obj
        
        self.sl_perc = params['sl_perc']
        self.update_time_gap = dt.timedelta(seconds=params['update_time_gap_seconds'])
        self.tf = dt.timedelta(seconds=params['candle_tf'])
        self.state = self.STATE_INITIAL
        self.date = None
        # self.lot = 1


    
    
    def setup(self, t):
        # self.instrument = self.trader.get_instrument({'exchange':'NSE', 'symbol':self.symbol})
        if(self.instrument is None):
            self.logger.error(f"No instrument found for symbol '{self.symbol}'")
            raise Exception("InstrumentNotFound")
        
        # list of names of options? No dataframe of all options
        # expiry=0?
        # all_options = self.trader.get_instrument({
        #     'symbol':self.symbol, 'exchange':self.instrument.exchange, 'type':'OPT', 'expiry':0,
        # }, return_multiple=True, verbose=False)

        all_options = self.get_all_options_nifty()
        # print(all_options)
        if(all_options is None or len(all_options) == 0):
            self.logger.error("No options found for this instrument.")
            raise Exception("NotFnOInstrument")
        self.all_options = {
            ot: all_options[all_options['opt_type'] == ot]
            for ot in self.OPT_TYPES
        }
        # print(self.all_options)

        # indicators
        self.RSI = si.RSI(14)
        self.prev_RSI = deque(maxlen=3)
        self.PLUS_DI = si.PLUS_DI(14)
        self.prev_PLUS_DI = deque(maxlen=3)
        self.MINUS_DI = si.PLUS_DI(14)
        self.prev_MINUS_DI = deque(maxlen=3)
        self.BBANDS = si.BBands(14, 2)
        self.last_update_dt = None
        self.open_positions = []
        
        self.update_indicators(t)
        
        return True

    def update_indicators(self, t):
        # function to fetch candles and update indicators
        if(self.last_update_dt is None):
            candles = self.underlying_data_obj.fetch_candle(self.instrument, t-dt.timedelta(minutes=5), t, self.tf)
            # print(candles)
            if(candles is None):
                self.logger.error(f"No historical candles")
                raise Exception("NoHistoricalData")
        else:#if(self.last_update_dt < t):
            candles = self.underlying_data_obj.fetch_candle(self.instrument, self.last_update_dt, t, self.tf)
            if(candles is None):
                self.logger.error(f"Live candle not received")
                raise Exception("NoLiveData")
                return False
        if(not isinstance(candles, pd.DataFrame)): candles = pd.DataFrame([candles])
        if candles.empty:
            print("Warning: No candle data available.")
            return
        for _, candle in candles.iterrows():
            # print(self.RSI)
            rsi = self.RSI.update(candle['close'])
            self.prev_RSI.append(rsi)
            plus_di = self.PLUS_DI.update(candle)
            self.prev_PLUS_DI.append(plus_di)
            minus_di = self.MINUS_DI.update(candle)
            self.prev_MINUS_DI.append(minus_di)
            self.BBANDS.update(candle['close'])
            self.last_update_dt = candle['datetime'] + self.tf
        # print(candle)
        # print("finally", self.prev_RSI)
        self.rsi_rc = (self.prev_RSI[-1] - self.prev_RSI[-3]) / self.prev_RSI[-3] * 100
        self.plus_di_rc  = (self.prev_PLUS_DI[-1]  - self.prev_PLUS_DI[-3] ) / self.prev_PLUS_DI[-3]  * 100
        self.minus_di_rc = (self.prev_MINUS_DI[-1] - self.prev_MINUS_DI[-3]) / self.prev_MINUS_DI[-3] * 100
        self.band_diff = (self.BBANDS.upperband - self.BBANDS.lowerband) / candle['close'] * 100

        # last candle
        self.candle = candle
        return

    def update(self, t):
        self.update_indicators(t)
        if(self._long_condition()):
            self.logger.info(f"Long condition met {t}")
            self._enter(t, 'CALL')
        elif(self._short_condition()):
            self.logger.info(f"Short condition met {t}")
            self._enter(t, 'PUT')
        return True

    def _long_condition(self):
        return (
            (self.candle['high'] > self.BBANDS.upperband) 
            # (self.rsi_rc > 5) &
            # (self.plus_di_rc > 5) &
            # (self.band_diff > 0.4)
        )

    def _short_condition(self):
        return (
            (self.candle['low'] < self.BBANDS.lowerband) 
            # (self.rsi_rc <= -5) &
            # (self.minus_di_rc > 5) &
            # (self.band_diff > 0.4)
        )
    


    def _enter(self, t, ot):
        # print("entered _enter", t, ot)
        # idx of option having strike closest to underlying
        trade_ins_idx = (self.all_options[ot]['strike'] - self.candle['close']).abs().idxmin()
        trade_ins = self.all_options[ot].loc[trade_ins_idx]
        # entire object trade_ins? No just the name
        # order_id = self.exchange.place_order(self.instrument, self.candle['close'], side, qty*self.qty)

        opt_token = int(trade_ins['token'])
        lot = trade_ins['lotsize']
        # print(self.candle['close'], trade_ins['strike'])

        # gotta find trade ins's current price
        # print(self.ltp)


        premium = self.find_option_premium(opt_token)

        
        # def place_order(self, inst, price, side, quantity, lot, order_type=Order.AGGRESSIVE, signal=""):
        # qty = 1
        order_id = self.exchange.place_order(opt_token, premium, Order.BUY, 1*lot,lot)
        if(order_id is None):
            self.logger.error(f"Error in placing order in {trade_ins.repr}")
            raise Exception("OrderPlacementException")
        # order = self.trader.fetch_order(self, order_id)
        
        # place stoploss order
        # if the premium falls below a threshhold
        # call option we predict markets to go up, premium of call rises. if it falls instead then we are wrong
        # put option we predict markets to go down, put premium to rise. if it falls instead then we were wrong.

        # t = utils.round_time(t)
        # earlier it was self.instrument, here it is trade_ins
        # premium_candles = self.trader.fetch_candle(trade_ins, t-utils.get_timedelta('3m'), t)
        # if(premium_candles is None or len(premium_candles) == 0):
        #     self.logger.error("No candle for option, can't compute SL")
        #     raise Exception("OptionDataError")
        
        order_price = self.candle['close']
        sl_price = premium -self.sl_perc*premium
        # def place_order(self, inst, price, side, quantity, lot, order_type=Order.AGGRESSIVE, signal="", trigger_price = None):

        sl_order_id = self.exchange.place_order(opt_token, sl_price,Order.SELL ,1*lot, lot, Order.SL_LIMIT, trigger_price=sl_price)
        
        # place the order if the trigger price is hit at the trigger price
        # if markets are falling adn trigger price is hit then the order is placed but 
        # by the time the order is to be filled market drop further so selling at trigger price might not get filled. use limit price = ORDER.TYPE.SL_MARKET instead
        
        
        
        if(sl_order_id is None):
            self.error(f"Unable to place SL order in {opt_token}")
            raise Exception("OrderPlacementException")
        # place tgt order
        # target order log in profits
        #  no need to set trigger. it is a sell order wont get executed unless price rises to limit price
        sl_points = premium - sl_price
        tgt_price = round(premium + sl_points, 2)
        # limit order
        tgt_order_id = self.exchange.place_order(opt_token,tgt_price, Order.SELL, 1*lot, lot,order_type=Order.LIMIT)

        if(tgt_order_id is None):
            self.error(f"Unable to place Target order in {opt_token}")
            raise Exception("OrderPlacementException")
        
        # why not append the order id as well? why only the sl adn tgt
        self.open_positions.append(
            {'trade_ins':opt_token, 
             'strike':trade_ins['strike'], 
             'opt_type': ot, 
             'sl_order_id':sl_order_id, 
             'tgt_order_id':tgt_order_id, 
             'lot': lot
            })
        self.logger.info(f"Entered {opt_token}, {trade_ins['strike']}, {ot} at {premium} SL: {sl_price} Target: {tgt_price}")
        return


    # wont get called base class's on order update will be called
    def on_order_update(self, order):
        super().on_order_update(order)
        if(order.status == Order.FILLED):
            # reference self.open_positions updated when pos changed
            # stop loss or target has not been hit
            for pos in self.open_positions:
                if(order.id == pos['sl_order_id']):
                    self.logger.info(f"SL hit in {pos['trade_ins']},  {pos['strike']}, {pos['opt_type']} at {order.fill_price}")
                    pos['sl_order_id'] = None
                    self.exchange.cancel_order(pos['tgt_order_id'])
                    pos['tgt_order_id'] = None
                    return True
                elif(order.id == pos['tgt_order_id']):
                    self.logger.info(f"Target hit in {pos['trade_ins']}, {pos['strike']}, {pos['opt_type']} at {order.fill_price}")
                    pos['tgt_order_id'] = None
                    self.exchange.cancel_order(pos['sl_order_id'])
                    pos['sl_order_id'] = None
                    return True
        
    def squareoff(self, t):
        self.logger.debug("squaring off...")
        # self.open_positions keeps track of all call/put buys
        for pos in self.open_positions:
            if(pos['sl_order_id'] is not None):
                self.exchange.cancel_order(pos['sl_order_id'])
                self.exchange.cancel_order(pos['tgt_order_id'])
                premium = self.find_option_premium(pos['trade_ins'])
                self.logger.info(f"sqauring off placing sell order in {pos['trade_ins']} , {pos['strike']}, {pos['opt_type']} at {premium}")
                order_id = self.exchange.place_order(pos['trade_ins'], premium, Order.SELL, 1*pos['lot'], pos['lot'])
                if(order_id is None):
                    self.logger.error(f"Unable to squareoff position in {pos['trade_ins'].repr}")
                    raise Exception("OrderPlacementException")
        self.state = self.STATE_SQUAREDOFF
        return True
    
    def schedule(self, t):
        from apscheduler.triggers.date import DateTrigger
        # strptime: Parses a string like '09:15' into a datetime.datetime
        start_dt = dt.datetime.combine(t,dt.datetime.strptime(self.params['start_time'],'%H:%M').time())
        end_dt = dt.datetime.combine(t,dt.datetime.strptime(self.params['squareoff_time'],'%H:%M').time())
        
        self.trader.schedule(self.name, DateTrigger(start_dt-utils.get_timedelta('1m')), 'setup')
        self.trader.schedule(self.name, DateTrigger(end_dt), 'squareoff')
        
        from AlgoTrading.schedules import get_schedule
        # update every minutue
        # (start_dt).strftime('%H:%M') Converts the time portion of start_dt back into a string like '09:15' ignores the date
        update_sched = get_schedule((start_dt).strftime('%H:%M'),(end_dt-utils.get_timedelta('10s')).strftime('%H:%M'), '1m')
        self.trader.schedule(self.name, update_sched, 'update')
        
        self.trader.subscribe(self.name, 'order_update', 'on_order_update')

    def setup_for_next_day(self):
        self.eostrategy_report_build = False
        self.bool_setup = False
        self.last_update_dt = None
        self.state = self.STATE_INITIAL


    def on_data(self, packet):
        self.packet_cnt += 1
        # print(self.packet_cnt)
        self.ltp[packet.inst] = packet.open
        # if (packet.inst == 48251):
            # print("$$$$$$$$$$$$$$$$$$$", self.ltp[packet.inst], packet.timestamp_seconds)
        # if (packet.inst == 48346):
        #     print("$$$$$$$$$$$$$$$$$$$", self.ltp[packet.inst])
        if (packet.inst != 35001):
            return
        # print(packet)
        t = packet.timestamp_seconds
        time = t.time()  
        date = t.date()
        if (self.date == None):
            self.date = date
        if (date!= self.date):
            self.date= date
            self.setup_for_next_day()
        
        if (not self.bool_setup and time >= self.setup_time ):
            # print("setting up once", t)
            self.setup(t)
            self.bool_setup = True
            # print("self.last_updated_time", self.last_update_dt)
        elif self.bool_setup and self.last_update_dt is not None and (t - self.last_update_dt) >= self.update_time_gap and time<self.liquidation_time:
            # print("updating once")
            self.upd = True
            self.update(t)
            # print("self.last_updated_time", self.last_update_dt)
        elif self.state != self.STATE_SQUAREDOFF and time>=self.liquidation_time:
            self.squareoff(t)
        elif time>= self.report_building_time:
            # comment this for daily eo strategy reports
            if (date == (dt.datetime.strptime(self.end_date, "%Y%m%d")+ dt.timedelta(days=1)).date()):
                self.build_eostrategy_report()

    # def round_time(t, minute=1):
    #     t = t.replace(second=0, microsecond=0)
    #     t = t - get_timedelta(f'{t.minute%minute}m')
    #     return t