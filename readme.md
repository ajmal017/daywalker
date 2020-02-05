# Daywalker backtesting framework

Daywalker is a stock market backtesting framework. I wrote it mainly for my own personal use because I was unsatisfied with existing frameworks.

There's a lot of frameworks like these, so let me outline my design goals/methodology explicitly.

- I want to do as much of my analysis as possible in Python/`pandas`/`numpy`.
- I only trade daily (*no intraday*), almost 100% limit-on-open and limit-on-close. Many backtesting frameworks don't support the opening auction.
- My strategies run on a wide range of stocks and use alternative data sources. Providing a censored view of many symbols is important to me. The view should be in `pandas`.
- Transaction costs, dividends, and taxes need to be tracked properly.
- I want to easily add tracking information and useful statistics to my trades and get this out at the end.

Here are a couple of novelties of this framework, which make up a significant chunk of the reason I built it.

### Cost basis, sources of funds and taxes

Taxes matter a lot. There are a number of trading strategies that sacrifice a little alpha in order to minimize taxes, and justifiably so. Tax loss harvesting, as practiced by assorted robo-advisors (e.g. Wealthfront) is a good example.

In order to measure taxes, the source of income must be tracked. Dividends are treated differently from long and short term capital gains, for example.

For this reason, Daywalker tracks the cost-basis of every purchase you make.

For example, suppose you buy 100@25 of X at 100 on Jan 1, 1990 and another 100@30 shares on June 1, 1990. On Jan 10, 1991, you sell 150@35. The result, in terms of capital gains, is:
- A long term capital gain of `100 * (35 - 25) = 1000`.
- A short term capital gain of `50 x (35 - 30) = 250`.

The $1000 cap gain is taxed at a low rate (in the US), while the $250 cap gain is taxed at a much higher rate. It might be a worthwhile improvement to the strategy to sell only the 100@35 to minimize capital gains.

### Tracking information/trade metadata

The tracking information is an important piece here that I want to explain further. Suppose I am running a long/short strategy of the following nature - when an event occurs, I will open both a long and a short.

The way this works in daywalker is as follows. Inside my `Strategy` object, I will enter trades in the following manner:

    def pre_open(self, dt, broker, trades, commissions):
        story = get_wallstreetbets_recommendation(dt)
        story_score = get_story_score(story)
        if story_score > self.threshold:
            long_symbol, short_symbol = get_symbols_from_story(story)

            broker.limit_on_open(long_symbol, price=..., size=..., is_buy=True, meta={ 'trade_story_id': story.id })
            broker.limit_on_open(short_symbol, price=..., size=..., is_buy=False, meta={ 'trade_story_id': story.id })

The key observation here is that what's important to me is the P&L of the combined long/short position. One metric I will want to track is the Sharpe ratio of my strategy, computed as the average *over individual long/short trades* (rather than over time).

After we run the simulation we can use the metadata to track our trades. If we call the function `m.broker.capital_gains()` (I'll discuss later on how to get here), we will get a dataframe that looks like this:

       open_price  close_price  size open_trade_story_id                  open_date close_trade_id                close_date    symbol
    0       17.50        17.51     1             1        2004-08-12 09:30:00-04:00              0 2004-08-13 16:00:00-04:00    "long_symbol"
    1       17.50        17.50     2             1        2004-08-13 09:30:00-04:00              1 2004-08-16 16:00:00-04:00    "short_symbol"
    2       17.54        17.34     3             2        2004-08-16 09:30:00-04:00              0 2004-08-17 16:00:00-04:00    "another_long_symbol_from_a_diff_event"
    ...

We can now take our `cap_gains` dataframe and do `cap_gains.groupby('open_trade_story_id')` to do an analysis on the level of an individual story (where each story triggered multiple trades). This makes it easy to analyze our capital gains from the *combined long/short* position.

## Tutorial

To begin with, we will need some market data. Daywalker does not include market data.

    >>> import pandas as pd
    >>> from daywalker import TradeableAsset, Strategy, Market
    >>> from daywalker.broker import InteractiveBrokers

    >>> prices = pd.DataFrame({'date': [pd.Timestamp('2004-08-12 00:00:00-0400', tz='America/New_York'),
    ... pd.Timestamp('2004-08-13 00:00:00-0400', tz='America/New_York'),
    ... pd.Timestamp('2004-08-16 00:00:00-0400', tz='America/New_York'),
    ... pd.Timestamp('2004-08-17 00:00:00-0400', tz='America/New_York'),
    ... pd.Timestamp('2004-08-18 00:00:00-0400', tz='America/New_York')],
    ... 'open': [17.5, 17.5, 17.54, 17.35, 17.25],
    ... 'high': [17.58, 17.51, 17.54, 17.4, 17.29],
    ... 'low': [17.5, 17.5, 17.5, 17.15, 17.0],
    ... 'close': [17.5, 17.51, 17.5, 17.34, 17.11],
    ... 'volume': [2545100, 593000, 684700, 295900, 121300],
    ... 'divCash': [0.0, 0.0, 0.0, 0.0, 0.0],
    ... 'splitFactor': [1.0, 1.0, 1.0, 1.0, 1.0]})

Once you have market data, it simply needs to be brought to the above format. Then it should be wrapped in a `TradeableAsset` and given a symbol:

    >>> ta = TradeableAsset('acc', prices)

A `TradeableAsset` represents a symbol that can be bought or sold. It also provides a time-censored view of itself. For example, on 2004-08-17, after the open, we can see the open price for 2004-08-17:

    >>> history, open_price = ta.get_censored(pd.Timestamp('2004-08-17'), after_open=True)
    >>> open_price
    17.35

We can also see the history up to (and including) 2004-08-16.

    # Note that we are doing this weird printing of a CSV because
    # for some reason, doctests is failing even though exact strings seem to match. WTF.

    >>> print(history[['open', 'high', 'low', 'close', 'volume', 'divCash', 'splitFactor']].to_csv(None))
    date,open,high,low,close,volume,divCash,splitFactor
    2004-08-12,17.5,17.58,17.5,17.5,2545100,0.0,1.0
    2004-08-13,17.5,17.51,17.5,17.51,593000,0.0,1.0
    2004-08-16,17.54,17.54,17.5,17.5,684700,0.0,1.0
    <BLANKLINE>
    >>>

The next step in running a backtest is getting a `Broker`. I use Interactive Brokers.

    >>> from daywalker.broker import InteractiveBrokers
    >>> broker = InteractiveBrokers(10000, assets={'acc': ta})

This broker is initialized with $10,000 in our account and `acc` as the only tradeable asset.

    >>> from daywalker.market import _TestStrategy  # _TestStrategy is a test-only strategy
    >>> m = Market(prices['date'].min(), prices['date'].max(), strategy=_TestStrategy('acc'), broker=broker)
    >>> m.run()

At the end of the backtest, we hold these positions:

    >>> m.broker.positions()[['price', 'size', 'symbol', 'trade_id', 'date']]
       price  size symbol trade_id                      date
    0  17.35     4    acc        0 2004-08-17 09:30:00-04:00
    1  17.25     5    acc        1 2004-08-18 09:30:00-04:00

The following capital gains were achieved:

    >>> cg = m.broker.capital_gains()
    >>> cg[['open_price', 'close_price', 'size', 'open_trade_id', 'open_date', 'close_trade_id', 'close_date', 'symbol']]
       open_price  close_price  size open_trade_id                 open_date close_trade_id                close_date symbol
    0       17.50        17.51     1             1 2004-08-12 09:30:00-04:00              0 2004-08-13 16:00:00-04:00    acc
    1       17.50        17.50     2             0 2004-08-13 09:30:00-04:00              1 2004-08-16 16:00:00-04:00    acc
    2       17.54        17.34     3             1 2004-08-16 09:30:00-04:00              0 2004-08-17 16:00:00-04:00    acc

And the following commissions were paid, as per the InteractiveBrokers schedule:

    >>> commissions = m.broker.commissions()
    >>> commissions[['price', 'size', 'symbol', 'date', 'trade_id', 'commission']]
       price  size symbol                      date trade_id  commission
    0  17.50     1    acc 2004-08-12 09:30:00-04:00        1      0.1750
    1  17.50     2    acc 2004-08-13 09:30:00-04:00        0      0.3500
    2  17.51    -1    acc 2004-08-13 16:00:00-04:00        0      0.1751
    3  17.54     3    acc 2004-08-16 09:30:00-04:00        1      0.5262
    4  17.50    -2    acc 2004-08-16 16:00:00-04:00        1      0.3500
    5  17.35     4    acc 2004-08-17 09:30:00-04:00        0      0.6940
    6  17.34    -3    acc 2004-08-17 16:00:00-04:00        0      0.5202
    7  17.25     5    acc 2004-08-18 09:30:00-04:00        1      0.8625

### Building a strategy

A strategy is a very simple class. Lets build a strategy which attempts to buy a stock, at the open, whenever the price is less than 5% of the moving average over the past few days.

    class Strategy(metaclass=abc.ABCMeta):
        @abc.abstractmethod
        def pre_open(self, dt, broker, trades, commissions):
            pass

        @abc.abstractmethod
        def pre_close(self, dt, broker, trades, commissions):
            pass
