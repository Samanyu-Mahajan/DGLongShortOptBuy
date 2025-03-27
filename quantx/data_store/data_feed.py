import datetime
import os.path
import pandas as pd

import pdb
# if build data is False
# self.mktdata = subset of all_data
# if build_data is True
# self.mktdata = self.reader() se



class DataStore:
    CM_STREAMS = [x for x in range(1,5)]
    FO_STREAMS = [x for x in range(1,19)]

    def __init__(self, start_date:str, end_date:str, data_building_date:str, data_path:str, universe:str, build_data=True, all_data=None):
        """
        start_date:str 20240604
        end_date:str 20240604
        data_building_date:str 20240603
        """
        self.start_date = datetime.datetime.strptime(start_date, "%Y%m%d")
        self.end_date = datetime.datetime.strptime(end_date, "%Y%m%d")
        self.data_building_date = datetime.datetime.strptime(data_building_date, "%Y%m%d")
        self.data_path = data_path
        self.universe = universe
        self.counter = 0
        # has ohlc as np.float 64
        self.mkt_data = None
        self.max_length = 0
        self.reader(build_data, all_data)

    def generate_all_dates_between(self):
        dates = []
        if self.start_date == self.end_date:
            dates = [self.start_date.strftime("%Y%m%d")]
        else:
            while self.start_date <= self.end_date:
                dates.append(self.start_date.strftime("%Y%m%d"))
                self.start_date += datetime.timedelta(days=1)
        return dates

    def reader(self, build_data, all_data):
        if build_data==False:
            self.mkt_data = all_data[all_data.token.isin([int(x) for x in self.universe])]
            self.max_length = self.mkt_data.shape[0]
        else:
            get_all_dates = self.generate_all_dates_between()
            mktdata_df = pd.DataFrame()
            for date in get_all_dates:
                folder_path = f"{self.data_path}/{date}"
                if os.path.exists(folder_path):
                    for i in range(1, 13):  # 1 to 12
                        file_path = f"{folder_path}/nsemd_NSEFO_{i}_{date}.csv"
                        # file_path = f"{folder_path}/nsemd_NSECM_1_{date}.csv"
                        if os.path.isfile(file_path):
                            # print("in file")
                            data = pd.read_csv(f"{file_path}", engine="pyarrow")
                            # pdb.set_trace()
                            # print(data['token'].value_counts().head(10))
                        
                            data = data[data.token.isin([int(x) for x in self.universe])]
                            # convert timestamp to datetime format limited to seconds
                            # data["timestamp"] = pd.to_datetime(data["timestamp"], unit ='ns', origin='unix')

                            # what is this?
                            data = data[data["open"] != -1]
                            data['timestamp_seconds'] = pd.to_datetime(data['timestamp'] // 10 ** 9, unit='s')
                            data['timestamp_seconds'] = data['timestamp_seconds'] + pd.DateOffset(years=10)

                            
                            data["open"] = data["open"]/100
                            data["low"] = data["low"]/100
                            data["high"] = data["high"]/100
                            data["close"] = data["close"]/100
                            data["LTP"] = data["LTP"]/100
                            data["midprice"] = data["midprice"]/100
                            data["inst"] = data["token"]
                            mktdata_df = pd.concat([mktdata_df, data])
            self.mkt_data = mktdata_df
            self.mkt_data.sort_values(by="timestamp", ascending=True, inplace=True)
            self.max_length = mktdata_df.shape[0]

    def next(self):
        current_packet = self.mkt_data.iloc[self.counter]
        self.counter += 1
        return current_packet
    



    def fetch_candle(self, instrument, from_dt, to_dt, tf):

        df = self.mkt_data

        # Filter between from_dt and to_dt
        mask = (df['inst'] == instrument) & (df['timestamp_seconds'] >= from_dt) & (df['timestamp_seconds'] < to_dt)
        df_filtered = df.loc[mask][['timestamp_seconds', 'open', 'high', 'low', 'close']]
        df_filtered = df_filtered[df_filtered['close'] != -0.01]
        df_filtered = df_filtered.set_index('timestamp_seconds')
        df_filtered.index.name = 'datetime'


        if df_filtered.empty:
            return pd.DataFrame()

        # Resample to candles
        resampled = df_filtered.resample(tf).agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last'
        }).dropna()

        resampled.reset_index(inplace=True)

        return resampled


