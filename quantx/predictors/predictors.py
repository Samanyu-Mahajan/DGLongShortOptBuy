import pandas as pd
import numpy as np
import pdb
TIME = 'timestamp'
HIGH = 'high'
LOW = 'low'
CLOSE = 'close'
OPEN = 'open'
HIGH_1 = HIGH+'_1'
LOW_1 = LOW+'_1'
HIGH_INT = HIGH+'_int'
LOW_INT = LOW+'_int'
LONG = 'long'
SHORT = 'short'


def wwma(data, window):
    return data.ewm(alpha=1 / window, adjust=True, ignore_na=True).mean()


# TR=max(HIGH−LOW,∣HIGH−PREV_CLOSE∣,∣LOW−PREV_CLOSE∣)
# ATR = average TR

def atr(data, window=14):
    '''
        expects data -> dataframe with columns HIGH, LOW, 'close'
    '''
    df = data.copy()
    high = data[HIGH]
    low = data[LOW]
    close = data[CLOSE]
    df['term0'] = np.abs(high - low)
    # high - prev_close
    df['term1'] = np.abs(high - close.shift())
    df['term2'] = np.abs(low - close.shift())
    tr = df[['term0', 'term1', 'term2']].max(axis=1)
    # atr = wwma(tr, window)
    # pdb.set_trace()

    atr = np.zeros(len(df[CLOSE]))

    atr[0] = tr.iloc[0]
    # average of first i values uptil window
    for i in range(1, window):
        atr[i] = (atr[i - 1] * (i) + tr.iloc[i]) / float(i + 1)

    # some weighted average
    for i in range(window, len(atr)):
        atr[i] = (atr[i - 1] * (window - 1) + tr.iloc[i]) / float(window)
    return atr


def sma(data, column, window):
    df = data.copy()
    return df[column].rolling(window=window, min_periods=1).mean()


def price_in_interval(data, interval, high=True):
    df = data.copy()
    if high:
        price_type = np.max
        col = HIGH
    else:
        price_type = np.min
        col = LOW

    vals = list()
    data_vals = df[col].to_numpy()

    for i in range(len(data_vals)):
        # for high, max of highs of [i-intervals+1] to i
        # for low, the min of lows of [i-intervals+1] to i
        value = price_type(data_vals[max(0, i - interval+1):i+1])
        vals.append(value)

    return pd.Series(vals)


def halftrend_brute(data, atrlen=14, amplitude=2, deviation=2):
    df = data.copy()
    len_data = len(data)
    df[LOW_1] = df[LOW].shift()
    # low_1 is one row shifted below
    # low LOW_1
    # 5   nan coverted to 5
    # 6   5
    # 7   6
    # where low1 is nan replace it by low
    df.loc[df[LOW_1].isnull(), LOW_1] = df.loc[df[LOW_1].isnull(), LOW]

    df[HIGH_1] = df[HIGH].shift()
    df.loc[df[HIGH_1].isnull(), HIGH_1] = df.loc[df[HIGH_1].isnull(), HIGH]
    # pdb.set_trace()

    atr_2 = atr(data, window=atrlen)
    dev = 0.5 * deviation * atr_2
    high_ma = sma(data, HIGH, window=amplitude)
    low_ma = sma(data, LOW, window=amplitude)
    # high interval, low interval
    df[HIGH_INT] = price_in_interval(data, amplitude, True)
    df[LOW_INT] = price_in_interval(data, amplitude, False)
    pdb.set_trace()
    df["half_trend"], df["atr_up"], df["atr_down"], df["half_trend_value"] = 0.0, 0.0, 0.0, 0.0
    # trend = 0 long, = 1 short
    down, prev_down = 0.0, 0.0
    up, prev_up = 0.0, 0.0
    trend, prev_trend = 0.0, 0.0
    next_trend = 0.0
    atr_high, atr_low = 0, 0
    max_low_price = df.loc[0, LOW_1]
    min_high_price = df.loc[0, HIGH_1]

    for idx, row in df.iterrows():
        low_price = row[LOW_INT]
        high_price = row[HIGH_INT]

        if next_trend == 1:
            max_low_price = max(low_price, max_low_price)
            if high_ma[idx] < max_low_price and row[CLOSE] < row[LOW_1]:
                trend = 1
                next_trend = 0
                min_high_price = high_price
        else:
            min_high_price = min(high_price, min_high_price)
            if low_ma[idx] > min_high_price and row[CLOSE] > row[HIGH_1]:
                trend = 0
                next_trend = 1
                max_low_price = low_price

        if trend == 0:
            if prev_trend != 0:
                up = prev_down
            else:
                up = max(max_low_price, prev_up)
            atr_high = up + dev[idx]
            atr_low = up - dev[idx]
            # halftrend_output.append([row[TIME], atr_high, up, atr_low, LONG])
            df.at[idx, "half_trend"], df.at[idx, "atr_up"], \
                df.at[idx, "atr_down"], df.at[idx, "half_trend_value"] = LONG, atr_high, atr_low, up
        else:
            if prev_trend != 1:
                down = prev_up
            else:
                down = min(min_high_price, prev_down)
            atr_high = down + dev[idx]
            atr_low = down - dev[idx]
            # halftrend_output.append([row[TIME], atr_high, down, atr_low, SHORT])
            df.at[idx, "half_trend"], df.at[idx, "atr_up"], \
                df.at[idx, "atr_down"], df.at[idx, "half_trend_value"] = SHORT, atr_high, atr_low, down
        prev_down = down
        prev_up = up
        prev_trend = trend
    return df


# def halftrend_brute(data, atrlen=100, amplitude=2, deviation=2):
#     df = data.copy()
#     len_data = len(data)
#
#     df[LOW_1] = df[LOW].shift()
#     df.loc[df[LOW_1].isnull(), LOW_1] = df.loc[df[LOW_1].isnull(), LOW]
#     df[HIGH_1] = df[HIGH].shift()
#     df.loc[df[HIGH_1].isnull(), HIGH_1] = df.loc[df[HIGH_1].isnull(), HIGH]
#
#     atr_2 = atr(data, window=atrlen)
#     dev = deviation * atr_2
#     high_ma = sma(data, HIGH, window=amplitude)
#     low_ma = sma(data, LOW, window=amplitude)
#     df[HIGH_INT] = price_in_interval(data, amplitude, True)
#     df[LOW_INT] = price_in_interval(data, amplitude, False)
#
#     halftrend_output = list()
#     # trend = 0 long, = 1 short
#     down, prev_down = 0, 0
#     up, prev_up = 0, 0
#     trend, prev_trend = 0, 0
#     next_trend = 0
#     atr_high, atr_low = 0, 0
#     max_low_price = df.loc[0, LOW_1]
#     min_high_price = df.loc[0, HIGH_1]
#
#     for idx, row in df.iterrows():
#         low_price = row[LOW_INT]
#         high_price = row[HIGH_INT]
#
#         if next_trend == 1:
#             max_low_price = max(low_price, max_low_price)
#             if high_ma[idx] < max_low_price and row[CLOSE] < row[LOW_1]:
#                 trend = 1
#                 next_trend = 0
#                 min_high_price = high_price
#         else:
#             min_high_price = min(high_price, min_high_price)
#             if low_ma[idx] < min_high_price and row[CLOSE] > row[HIGH_1]:
#                 trend = 0
#                 next_trend = 1
#                 max_low_price = low_price
#
#         if trend == 0:
#             if prev_trend != 0:
#                 up = prev_down
#             else:
#                 up = max(max_low_price, prev_up)
#             atr_high = up + dev[idx]
#             atr_low = up - dev[idx]
#             halftrend_output.append([row[TIME], atr_high, up, atr_low, LONG])
#         else:
#             if prev_trend != 1:
#                 down = prev_up
#             else:
#                 down = min(min_high_price, prev_down)
#             atr_high = down + dev[idx]
#             atr_low = down - dev[idx]
#             halftrend_output.append([row[TIME], atr_high, down, atr_low, SHORT])
#
#         prev_down = down
#         prev_up = up
#         prev_trend = trend
#
#     return halftrend_output


def adx(data, period=14):
    return dmi(data, period, True)


def dmi(data, period=14, only_adx=False):
    '''
    data -> df of high low open close ...
    '''
    # dm_p = data[HIGH].diff()
    # dm_m = data[HIGH].diff()
    # dm_p[dm_p < 0] = 0
    # dm_m[dm_m > 0] = 0
    #
    # # atr parts
    # part1 = data[HIGH] - data[LOW]
    # part2 = (data[HIGH] - data[CLOSE].shift(1)).abs()
    # part3 = (data[LOW] - data[CLOSE].shift(1)).abs()
    # atr_parts = [part1, part2, part3]
    # tr = pd.concat(atr_parts, axis=1, join='inner').max(axis=1)
    # atr = tr.rolling(window=period, min_periods=1).mean()
    # di_plus = (100 * (dm_p.ewm(alpha=1/period).mean()/atr))
    # di_minus = (100 * (dm_m.ewm(alpha=1/period).mean()/atr)).abs()
    # dx = ((di_plus-di_minus).abs()/(di_plus+di_minus).abs())*100
    # adx = ((dx.shift(1)*(period-1)) + dx)/period
    # if only_adx:
    #     return adx
    # adx_smooth = adx.ewm(alpha=1/period).mean()
    # data["di_plus"] = di_plus
    # data["di_minus"] = di_minus
    # data["adx_smooth"] = adx_smooth
    # return data

    # finds the difference between current row and prev row
    # finds the difference between current row and prev row
    df = pd.DataFrame(data)
#    df = data
    df['atr'] = np.nan

    part1 = data[HIGH] - data[LOW]
    part2 = (data[HIGH] - data[CLOSE].shift(1)).abs()
    part3 = (data[LOW] - data[CLOSE].shift(1)).abs()
    atr_parts = [part1, part2, part3]
    tr = pd.concat(atr_parts, axis=1, join='inner').max(axis=1)
    df['atr'] = tr.ewm(alpha = 1/14, adjust = True).mean()
    # high_t - high_t-1
    # low_t-1 - low_t
    df['high'] = data[HIGH] - data[HIGH].shift(1)
    df['low'] = -(data[LOW] - data[LOW].shift(1))

    df['plus'] = np.where((df['high'] > df['low']) & (df['high'] > 0), df['high'], 0.)
    df['minus'] = np.where((df['low'] > df['high']) & (df['low'] > 0), df['low'], 0.)


    df['di_plus'] = 100 * (df['plus'].ewm(alpha=1/14, adjust = True).mean() / df['atr'])
    df['di_minus'] = 100 * (df['minus'].ewm(alpha=1/14, adjust = True).mean() / df['atr'])

    df['sum'] = 100 * np.abs(df['di_plus'] - df['di_minus']) / (df['di_plus'] + df['di_minus'])

    df['adx'] = df['sum'].ewm(alpha=1/14, adjust = False).mean()
    data["di_plus"] = df['di_plus']
    data["di_minus"] = df['di_minus']
    data["adx_smooth"] = df['adx']

#    df = df[['timestamp', 'adx', 'di_plus', 'di_minus', 'atr']]
#    df = df[['Date', 'adx', 'di_plus', 'di_minus', 'atr']]
    return (data)

def CWA2sigma(df):
    df['SMA'] = df['close'].rolling(window=50).mean()
    df['SD'] = df['close'].rolling(window=50).std()
    df['UB'] = df['SMA'] + 2 * df['SD']
    df['LB'] = df['SMA'] - 2 * df['SD']
    # df['signal'] = df[''] > 1
    return df
