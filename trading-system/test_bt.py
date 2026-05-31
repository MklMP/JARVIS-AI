from backtesting.data_provider import DataProvider
dp = DataProvider()
df = dp.fetch('AAPL', interval='1d', start='2023-06-01', end='2024-06-01')
print('Rows:', len(df) if df is not None else 'None')
if df is not None:
    print('First:', df.index[0], 'Last:', df.index[-1])
