if __package__ is None or __package__ == '':
    from market_data import TradeableAsset
    from broker import Broker, BrokerInterface, InteractiveBrokers
    from strategy import Strategy
    from censorship import CensoredData
else:
    from .market_data import TradeableAsset
    from .broker import Broker, BrokerInterface, InteractiveBrokers
    from .strategy import Strategy
    from .censorship import CensoredData
import pandas as pd
import abc

__all__ = ['Market']


class _TestStrategy(Strategy):
    """This is used just for the doctests."""
    def __init__(self, symbol):
        self.symbol = symbol
        self.size = 1

    def pre_open(self, dt, broker, trades, other_data):
        broker.limit_on_open('acc', price=100, size=self.size, is_buy=True, meta={'trade_id': str(self.size % 2)})

    def pre_close(self, dt, broker, trades, other_data):
        if (self.size <= 4):
            if (self.size > 1):
                broker.limit_on_close('acc', price=10, size=self.size-1, is_buy=False, meta={'trade_id': str(self.size % 2)})
        self.size += 1


class Market:
    """
    >>> import pandas as pd
    >>> prices = pd.DataFrame({'date': [pd.Timestamp('2004-08-12 00:00:00-0400', tz='America/New_York'),
    ... pd.Timestamp('2004-08-13 00:00:00-0400', tz='America/New_York'),
    ... pd.Timestamp('2004-08-16 00:00:00-0400', tz='America/New_York'),
    ... pd.Timestamp('2004-08-17 00:00:00-0400', tz='America/New_York'),
    ... pd.Timestamp('2004-08-18 00:00:00-0400', tz='America/New_York')],
    ... 'open': [17.5, 17.5, 17.54, 17.35, 8.62],
    ... 'high': [17.58, 17.51, 17.54, 17.4, 8.65],
    ... 'low': [17.5, 17.5, 17.5, 17.15, 8.5],
    ... 'close': [17.5, 17.51, 17.5, 17.34, 8.56],
    ... 'volume': [2545100, 593000, 684700, 295900, 121300],
    ... 'divCash': [0.0, 0.0, 0.0, 0.10, 0.0],
    ... 'splitFactor': [1.0, 1.0, 1.0, 1.0, 2.0]})
    >>> ta = TradeableAsset('acc', prices)
    >>> b = InteractiveBrokers(10000, {})
    >>> m = Market(prices['date'].min(), prices['date'].max(), _TestStrategy('acc'), b)

    Assets can also be added to the broker/market after creation if this is easier:
    >>> m.add_asset('acc', prices)

    Finally a backtest can be run:
    >>> m.run()

    After running the simulation, we hold the following positions:
    >>> m.broker.positions()[['price', 'size', 'symbol', 'trade_id', 'date']]
       price  size symbol trade_id                      date
    0  8.675   8.0    acc        0 2004-08-17 09:30:00-04:00
    1  8.620   5.0    acc        1 2004-08-18 09:30:00-04:00

    Note that what is reported includes all the different potential cost bases.

    Capital gains can similarly be found:
    >>> cg = m.broker.capital_gains()
    >>> cg[['open_price', 'close_price', 'size', 'open_trade_id', 'open_date', 'close_trade_id', 'close_date', 'symbol']]
       open_price  close_price  size open_trade_id                 open_date close_trade_id                close_date symbol
    0       17.50        17.51     1             1 2004-08-12 09:30:00-04:00              0 2004-08-13 16:00:00-04:00    acc
    1       17.50        17.50     2             0 2004-08-13 09:30:00-04:00              1 2004-08-16 16:00:00-04:00    acc
    2       17.54        17.34     3             1 2004-08-16 09:30:00-04:00              0 2004-08-17 16:00:00-04:00    acc

    As well as commissions that were paid.
    >>> trades = m.broker.trades()
    >>> trades[['price', 'size', 'symbol', 'date', 'trade_id', 'commission']]
       price  size symbol                      date trade_id  commission
    0  17.50     1    acc 2004-08-12 09:30:00-04:00        1      0.1750
    1  17.50     2    acc 2004-08-13 09:30:00-04:00        0      0.3500
    2  17.51    -1    acc 2004-08-13 16:00:00-04:00        0      0.1751
    3  17.54     3    acc 2004-08-16 09:30:00-04:00        1      0.5262
    4  17.50    -2    acc 2004-08-16 16:00:00-04:00        1      0.3500
    5  17.35     4    acc 2004-08-17 09:30:00-04:00        0      0.6940
    6  17.34    -3    acc 2004-08-17 16:00:00-04:00        0      0.5202
    7   8.62     5    acc 2004-08-18 09:30:00-04:00        1      0.4310


    Accounting identities that should remain true:

    >>> div = m.broker.dividends()

    >>> abs(m.broker.cash() - 9883.9885) < 1e-6
    True
    >>> cap_gain = ((cg['close_price'] - cg['open_price'])*cg['size']).sum()
    >>> cap_gain
    -0.5899999999999963

    >>> trades = m.broker.trades()
    >>> trades[['price', 'size', 'symbol', 'date', 'trade_id']]
       price  size symbol                      date trade_id
    0  17.50     1    acc 2004-08-12 09:30:00-04:00        1
    1  17.50     2    acc 2004-08-13 09:30:00-04:00        0
    2  17.51    -1    acc 2004-08-13 16:00:00-04:00        0
    3  17.54     3    acc 2004-08-16 09:30:00-04:00        1
    4  17.50    -2    acc 2004-08-16 16:00:00-04:00        1
    5  17.35     4    acc 2004-08-17 09:30:00-04:00        0
    6  17.34    -3    acc 2004-08-17 16:00:00-04:00        0
    7   8.62     5    acc 2004-08-18 09:30:00-04:00        1

    >>> div = m.broker.dividends()
    >>> div
         stock_acquisition_date  shares symbol trade_id  div_per_share  amount    ex_date
    0 2004-08-16 09:30:00-04:00       3    acc        1            0.1     0.3 2004-08-17

    Accounting identity: initial_cash = cash + gain/loss from trades + commissions - dividends
    >>> initial_cash = m.broker.cash() + (trades['price']*trades['size']).sum() + trades['commission'].sum() - div['amount'].sum()   # This should add up to 10000.0, but fuck floating point
    >>> abs(initial_cash - 10000) < 1e-6
    True
    """
    def __init__(self, start_date, end_date, strategy, broker, other_data=None):
        self.start_date = start_date
        self.end_date = end_date
        self.strategy = strategy
        self.broker = broker
        if other_data is None:
            self.other_data = CensoredData()
        elif isinstance(other_data, CensoredData):
            self.other_data = other_data
        else:
            raise ValueError("other_data argument must be an instance of CensoredData. You passed in a " + str(type(other_data)))

    def set_strategy(self, strategy):
        self.strategy = strategy

    def add_asset(self, symbol, asset):
        self.broker.add_asset(symbol, asset)

    def add_data(self, name, data, censor_on_index=True, censor_column=None):
        self.other_data.add_data(name, data, censor_on_index=censor_on_index, censor_column=censor_column)

    def strategy_log(self, name):
        return self.strategy.get_log(name)

    def run(self):
        dt = self.start_date
        bi = BrokerInterface(self.broker, dt, after_open=False)
        while (dt <= self.end_date):
            if (not self.broker.trading_day(dt)):  # Some days are holidates, and there is no data present.
                dt = dt + pd.offsets.BDay()
                continue
            bi.set_date(dt, False)
            self.other_data.set_date(dt)

            trades = bi.get_unreported_items()
            self.strategy.pre_open(dt, bi, trades, self.other_data)

            bi.set_date(dt, True)
            trades = bi.get_unreported_items()
            self.strategy.pre_close(dt, bi, trades, self.other_data)
            dt = dt + pd.offsets.BDay()
            self.broker.record_strategy_values(dt)



if __name__ == '__main__':
    import sys
    sys.path.append('.')
    import doctest
    doctest.testmod()
