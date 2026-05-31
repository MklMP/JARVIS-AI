import sys, json
from finvizfinance.quote import finvizfinance

stock = finvizfinance('AAPL')

print('=== SIGNALS ===')
sig = stock.ticker_signal()
if sig:
    print(json.dumps(sig, indent=2, default=str)[:2000])
else:
    print('None')

print()
print('=== FUNDAMENT (keys) ===')
fund = stock.ticker_fundament(raw=False, output_format='dict')
if fund:
    for k in list(fund.keys())[:20]:
        v = fund.get(k, '?')
        print('  %s: %s' % (k, str(v)[:60]))
else:
    print('None')

print()
print('=== NEWS ===')
news = stock.ticker_news()
if news is not None and hasattr(news, 'head'):
    print(news.head(3).to_string())
elif news:
    print(str(news)[:500])
else:
    print('None')

print()
print('=== RATINGS ===')
ratings = stock.ticker_outer_ratings()
if ratings is not None and hasattr(ratings, 'head'):
    print(ratings.head(3).to_string())
elif ratings:
    print(str(ratings)[:500])
else:
    print('None')
