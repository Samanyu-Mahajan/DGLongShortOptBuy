import time
import pandas as pd
import os, django, sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "trade_feed.settings")
django.setup()
import datetime
from trade_app.models import *
from config import DATA_LOC
from django.db.models import F, Q


class UNIV_TYPE:
    VOL_BASED = "VOL_BASED"
    GAINER_LOSER_BASED = "GAINER_LOSER_BASED"
    MIXED = "GAINER_LOSER_VOL_BASED"


class DataFeed:

    @staticmethod
    def generate_universe(start_date, univ_type=UNIV_TYPE.VOL_BASED, index="NIFTY 500"):
        # inst_list = list()
        # if univ_type in {UNIV_TYPE.VOL_BASED, UNIV_TYPE.MIXED}:
        #     volatility_based = Prices.objects.filter(date=start_date, inst__index__name_idx=index).values_list(
        #         "inst__name_inst", flat=True).order_by("-volatility", "-mddv")
        #     inst_list = list(volatility_based)[0:30]
        # if univ_type in {UNIV_TYPE.GAINER_LOSER_BASED, UNIV_TYPE.MIXED}:
        #     prices_data = Prices.objects.filter(date=start_date, inst__index__name_idx=index).annotate(
        #         return_i=((F("c") - F("prev_close")) / F("prev_close")) * 100).values_list("inst__name_inst",
        #                                                                                    "return_i").order_by(
        #         "-return_i", "-mddv")
        #     top_10 = prices_data.values_list("inst__name_inst", flat=True)[0:10]
        #     below_10 = prices_data.order_by("return_i", "-mddv").values_list("inst__name_inst", flat=True)[0:10]
        #     inst_list += list(top_10) + list(below_10)

        # return inst_list
        # return [Instrument.objects.filter(index__name_idx="NIFTY").values_list("name_inst", flat=True)]
        all_FO = ["CUB", "ICICIBANK", "SHREECEM", "LALPATHLAB", "COLPAL", "BHARTIARTL", "INFY", "JKCEMENT", "INDIAMART",
                  "NESTLEIND", "MPHASIS", "TECHM", "PETRONET", "COFORGE", "ITC", "ULTRACEMCO", "BALKRISIND",
                  "HINDUNILVR", "WIPRO", "ABBOTINDIA", "SUNPHARMA", "DRREDDY", "PEL", "CONCOR", "SUNTV", "MARICO",
                  "GNFC", "ALKEM", "SBILIFE", "HDFCBANK", "PIDILITIND", "AUROPHARMA", "CIPLA", "BRITANNIA", "LUPIN",
                  "ADANIPORTS", "RAMCOCEM", "TITAN", "PAGEIND", "CUMMINSIND", "VOLTAS", "GODREJCP", "EICHERMOT", "LTIM",
                  "HCLTECH", "JUBLFOOD", "IDEA", "AXISBANK", "CHAMBLFERT", "ABB", "BAJAJ-AUTO", "HEROMOTOCO",
                  "APOLLOHOSP", "ASIANPAINT", "MRF", "TRENT", "DALBHARAT", "INDIGO", "KOTAKBANK", "UNITDSPR", "UBL",
                  "BAJFINANCE", "TORNTPHARM", "TCS", "DABUR", "IPCALAB", "CROMPTON", "PERSISTENT", "ZYDUSLIFE", "LTTS",
                  "SHRIRAMFIN", "MUTHOOTFIN", "DIVISLAB", "JSWSTEEL", "PIIND", "TATACONSUM", "ICICIGI", "RELIANCE",
                  "CHOLAFIN", "MFSL", "ESCORTS", "SYNGENE", "METROPOLIS", "HDFCAMC", "GLENMARK", "BAJAJFINSV",
                  "GUJGASLTD", "LT", "MARUTI", "SBICARD", "FEDERALBNK", "BOSCHLTD", "ONGC", "NTPC", "MGL", "OBEROIRLTY",
                  "IGL", "INDUSTOWER", "ATUL", "GRASIM", "HAVELLS", "AMBUJACEM", "HDFCLIFE", "ACC", "ASHOKLEY",
                  "COROMANDEL", "BATAINDIA", "ICICIPRULI", "BHARATFORG", "POWERGRID", "INDUSINDBK", "APOLLOTYRE",
                  "M&MFIN", "HINDALCO", "TATAMOTORS", "BPCL", "NAVINFLUOR", "OFSS", "TVSMOTOR", "UPL", "SBIN",
                  "POLYCAB", "TATACOMM", "MOTHERSON", "IDFCFIRSTB", "MCX", "TATASTEEL", "VEDL", "IOC", "PVRINOX",
                  "CANFINHOME", "GMRINFRA", "DIXON", "HINDPETRO", "IRCTC", "ASTRAL", "SIEMENS", "BERGEPAINT",
                  "LICHSGFIN", "INDHOTEL", "GAIL", "BIOCON", "BSOFT", "COALINDIA", "LAURUSLABS", "SAIL", "M&M", "BEL",
                  "NAUKRI", "ABCAPITAL", "TATACHEM", "ADANIENT", "AUBANK", "TATAPOWER", "JINDALSTEL", "NATIONALUM",
                  "GODREJPROP", "IEX", "AARTIIND", "SRF", "NMDC", "DEEPAKNTR", "RECLTD", "PFC", "HAL", "BALRAMCHIN",
                  "BANKBARODA", "MANAPPURAM", "RBLBANK", "ABFRL", "DLF", "EXIDEIND", "CANBK", "GRANULES", "BHEL",
                  "BANDHANBNK", "HINDCOPPER", "LTF", "PNB"]

        return Instrument.objects.filter(name_inst__in=all_FO).values_list("name_inst", flat=True).distinct()

    @staticmethod
    def get_all_possible_dates(year):
        return list(TickData.objects.filter(inst__name_inst="RELIANCE",
                                            timestamp__date__year = year).values_list(
            "timestamp__date", flat=True).distinct())

        # dates = Prices.objects.filter(date__year=year).order_by("date").values_list("date", flat=True).distinct()
        # previous_year_last_date = Prices.objects.filter(date__year=year-1).latest("date").date
        # return [str(previous_year_last_date)] + list(dates)

    def __init__(self, universe: list, start_date: datetime.date, end_date: datetime.date,
                 data_building_date: datetime.date):
        self.universe = universe
        self.start_date = start_date
        self.end_date = end_date
        self.data_building_date = data_building_date
        self.counter = 0

    def fetch_series(self):
        start_time = time.time()
        time_series_one_day = TickData.objects.filter(timestamp__date__gte=self.data_building_date,
                                                      timestamp__date__lte=self.end_date,
                                                      inst__name_inst__in=self.universe).order_by("timestamp"
                                                                                                  ).values_list(
            "timestamp", flat=True).distinct()
        return time_series_one_day

    def fetch_data(self, timestamp):
        self.data = TickData.objects.filter(timestamp=timestamp,
                                            inst__name_inst__in=self.universe)
        return self.data

    def __next__(self, timestamp):
        try:
            # current_packet = self.data[self.counter]
            # self.counter +=1
            # return current_packet
            return self.fetch_data(timestamp)
        except Exception as e:
            print("End of Data")
            return None
