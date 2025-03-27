from .logger import setup_logger, formatter, get_current_log_path
import datetime
from config import FILL_TYPE
import pandas as pd



class Order:
    BUY = "BUY"
    SELL = "SELL"
    AGGRESSIVE = "AGGRESSIVE"
    LIQUIDATE = "LIQUIDATE"
    SL_LIMIT = "SL_LIMIT"
    LIMIT = "LIMIT"
    PENDING = "PENDING"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"

    def __init__(self, id, price, inst, side, quantity, lot, logger="order", order_type="AGGRESSIVE", trigger_price = None):
        self.id = id
        self.price = price
        self.inst = inst
        self.side = side  # "BUY", "SELL"
        self.status = "INITIATED"
        self.quantity = quantity
        self.fill_price = 0
        self.order_type = order_type  # AGGRESSIVE, LIMIT, SL_LIMIT
        self.order_time = None
        self.order_timestamp = None
        self.fill_time = None
        self.fill_timestamp = None
        self.signal = ""
        self.trigger_price = trigger_price
        self.lot =lot
# exchange has logger: pending placed orderd and fill_logger: filled orders
class Exchange:
    """
    Every packet is first received by the exchange and then the strategy
    orders: inst wise open orders
    fill_type: can be filled on OPEN_OPEN, ON_MID, ON_VWAP
    completed_order: maintain a list of all orders completed so far
    order_update_subscribers : this can be any type of object to receive order updates -  in our case it is a strategy
    """

    # log_name=self.start_date
    def __init__(self, locks, fill_type, logger="order", log_name=None):
        self.locks = locks
        # #quantx/logs/20250205/
        current_log_path = get_current_log_path()
        self.orders = dict()
        self.completed_order = list()
        self.counter = 0
        self.fill_type = fill_type  # ON_OPEN, ON_MID, ON_VWAP
        # #quantx/logs/20250205/20250205_order.csv
        self.logger = setup_logger(locks[1], f"order_logger_{log_name}",
                                   f"{current_log_path}/{log_name}_{logger}.csv", formatter)
        
        # #quantx/logs/20250205/20250205_order_final.csv
        self.fill_logger = setup_logger(locks[2], f"fill_logger_{log_name}",
                                        f"{current_log_path}/{log_name}_order_final.csv", formatter)
        log_headers = "id, order_time, order_timestamp, fill_time, fill_timestamp, price, inst, side, status, quantity, fill_price, order_type, signal"
        self.logger.info(log_headers)
        self.fill_logger.info(log_headers)
        self.current_time = None
        self.order_update_subscribers = list()


#  if order pending the log it in self.logger else log it in self.fill_logger
    def log_order(self, order):
        log_line = (f"{order.id}, {order.order_time}, {order.order_timestamp}, {order.fill_time}, {order.fill_timestamp}, {order.price}, {order.inst}, {order.side},"
                    f" {order.status}, {order.quantity},{order.fill_price}, {order.order_type}, {order.signal}")
        if order.status == "PENDING":
            self.logger.info(log_line)
        elif order.status == "FILLED":
            self.fill_logger.info(log_line)



# self.counter increments by 1 order id.
    def place_order(self, inst, price, side, quantity, lot, order_type=Order.AGGRESSIVE, signal="", trigger_price = None):
        # print("placing order at price", price, self.counter)
        if inst not in self.orders:
            self.orders[inst] = list()
        order = Order(self.counter, price, inst, side, quantity,lot, trigger_price=trigger_price)
        order.status = Order.PENDING
        # time something like 1423214124878024234
        # what is this?
        order.order_time = self.current_time
        order.order_timestamp = pd.to_datetime(order.order_time // 10**9, unit='s')
        order.order_type = order_type
        order.signal = signal
        # order pending logged to self.logger 
        self.log_order(order)
        self.orders[inst].append(order)
        self.counter +=1
        return self.counter-1

# cancel all orders of packet.inst
    def cancel_pending_orders(self, packet):
        # print(f"CANCELLING ORDERS OF {packet.inst},{packet.timestamp}")
        orders_to_fill = self.orders.get(packet.inst, [])
        if len(orders_to_fill) > 0:
            self.orders[packet.inst] = list()
        return 0
    
    def cancel_order(self, order_id):
        for inst in self.orders:
            self.orders[inst] = [order for order in self.orders[inst] if order.id != order_id]



    def raise_order_update(self, order):
        for strategy in self.order_update_subscribers:
            strategy.on_order_update(order)

    def post_filled_order_checks(self, order, packet):
        order.fill_time = self.current_time
        order.fill_timestamp = pd.to_datetime(order.fill_time // 10**9, unit='s')
        order.status = Order.FILLED
        self.raise_order_update(order)
        self.completed_order.append(order)
        # print(len(self.completed))
        # fill logger
        self.log_order(order)
        self.orders.get(packet.inst).remove(order)

    def on_data(self, packet):
        """
        :param packet: inst, o, h, l, c , volume
        :return:
        """
        self.current_time = packet.timestamp
        # If packet.inst does not exist, it returns an empty list [] (instead of raising a KeyError).


        # buy_orders, sell_orders, aggressive_orders = self.orders.get(packet.inst, [])
        # for order in aggressive_orders:
        #     order.fill_price = packet.open  # filling at open                        
        #     self.post_filled_order_checks(order, packet)            

        
        orders_to_fill = self.orders.get(packet.inst, [])
        # get orders for current packet instrument  
        if orders_to_fill:
            for order in orders_to_fill:
                if order.price == 0:  # market order for liquidation
                    order.price = float(packet.open)
                if order.side == Order.BUY:
                    # SL order for buy will be a sell order with low sl price
                    # SL order for sell will be a buy order with high price
                    if order.order_type == Order.SL_LIMIT:
                        if (packet.open > order.trigger_price):
                            order.fill_price = order.trigger_price
                            self.post_filled_order_checks(order, packet)
                    if order.order_type in {Order.AGGRESSIVE, Order.LIQUIDATE}:
                        # if packet.o <= order.price:
                        # ON_OPEN
                        if (FILL_TYPE == "ON_OPEN"):
                            order.fill_price = packet.open  # filling at open
                        elif (FILL_TYPE == "ON_CLOSE"):
                            order.fill_price = packet.open 
                        elif (FILL_TYPE == "ON_HIGH"):
                            order.fill_price = packet.high
                        elif (FILL_TYPE == "ON_LOW"):
                            order.fill_price = packet.low
                        elif (FILL_TYPE == "ON_VWAP"):
                            order.fill_price = packet.VWAP/100
                        # print("filling order", order.price, "at price", packet.open)
                        self.post_filled_order_checks(order, packet)
                    elif order.order_type == Order.LIMIT:
                        if packet.low <= order.price:
                            order.fill_price = order.price
                            self.post_filled_order_checks(order, packet)
                elif order.side == Order.SELL:
                    # SL order for buy will be a sell order with low sl price
                    # SL order for sell will be a buy order with high price
                    if order.order_type == Order.SL_LIMIT:
                        if (packet.open < order.trigger_price):
                            order.fill_price = order.trigger_price
                            self.post_filled_order_checks(order, packet)
                        
                    if order.order_type in {Order.AGGRESSIVE, Order.LIQUIDATE}:
                        # if packet.o >= order.price:
                        if (FILL_TYPE == "ON_OPEN"):
                            order.fill_price = packet.open  # filling at open
                        elif (FILL_TYPE == "ON_CLOSE"):
                            order.fill_price = packet.open 
                        elif (FILL_TYPE == "ON_HIGH"):
                            order.fill_price = packet.high
                        elif (FILL_TYPE == "ON_LOW"):
                            order.fill_price = packet.low
                        elif (FILL_TYPE == "ON_VWAP"):
                            order.fill_price = packet.VWAP/100
                        self.post_filled_order_checks(order, packet)
                    elif order.order_type == Order.LIMIT:
                        # if packet.h >= order.price and packet.l >= order.price:
                        if packet.high >= order.price:

                            order.fill_price = order.price
                            self.post_filled_order_checks(order, packet)
