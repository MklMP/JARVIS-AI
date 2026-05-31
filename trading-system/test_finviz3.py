import requests, sys
from bs4 import BeautifulSoup

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
    'Referer': 'https://finviz.com/',
}

r = requests.get('https://finviz.com/quote.ashx?t=AAPL', headers=headers, timeout=10)
soup = BeautifulSoup(r.text, 'lxml')

# 1) Fundamentals snapshot  
tables = soup.find_all('table', class_='snapshot-table2')
if tables:
    tds = tables[0].find_all('td')
    fund = {}
    for i in range(0, len(tds) - 1, 2):
        key = tds[i].get_text(strip=True) if tds[i] else ''
        val = tds[i+1].get_text(strip=True) if tds[i+1] else ''
        if key and val:
            fund[key] = val
    print('FUNDAMENTALS: %d keys' % len(fund))
    print('  P/E: %s  EPS: %s  MktCap: %s' % (fund.get('P/E',''), fund.get('EPS (ttm)',''), fund.get('Market Cap','')))
    print('  Perf Week: %s  Perf Month: %s  Perf Quarter: %s' % (fund.get('Perf Week',''), fund.get('Perf Month',''), fund.get('Perf Quarter','')))
    print('  Short Float: %s  Short Ratio: %s' % (fund.get('Short Float',''), fund.get('Short Ratio','')))
    print('  RSI: %s' % fund.get('RSI (14)','N/A'))
    print('  Volatility: %s' % fund.get('Volatility','N/A'))
    print('  SMA20: %s  SMA50: %s  SMA200: %s' % (fund.get('SMA20',''), fund.get('SMA50',''), fund.get('SMA200','')))
    print('  Change: %s' % fund.get('Change',''))

# 2) Find all distinct content to locate patterns/signals
print('\n=== ALL TABLE CLASSES ===')
for tbl in soup.find_all('table'):
    cls = tbl.get('class', [])
    rows = tbl.find_all('tr')
    if len(rows) > 1:
        txt = rows[0].get_text(strip=True)[:60]
        print('  class=%s rows=%d text="%s"' % (cls, len(rows), txt))

# 3) Search all page text for pattern keywords
print('\n=== PATTERN/CHART SIGNALS ===')
all_text = soup.get_text()
lines = all_text.split('\n')
for line in lines:
    line = line.strip()
    if not line: continue
    low = line.lower()
    if any(p in low for p in ['pattern', 'signal', 'wedge', 'flag', 'triangle', 'channel', 'trend', 'breakout', 'support', 'resistance']):
        safe = line.encode('ascii', 'replace').decode()
        print('  %s' % safe[:120])
