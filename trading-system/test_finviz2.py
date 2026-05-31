import requests
from bs4 import BeautifulSoup

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
    'Referer': 'https://finviz.com/',
}

r = requests.get('https://finviz.com/quote.ashx?t=AAPL', headers=headers, timeout=10)
soup = BeautifulSoup(r.text, 'lxml')

# 1) Fundamentals
tables = soup.find_all('table', class_='snapshot-table2')
if tables:
    tds = tables[0].find_all('td')
    fund = {}
    for i in range(0, len(tds) - 1, 2):
        key = tds[i].get_text(strip=True) if tds[i] else ''
        val = tds[i+1].get_text(strip=True) if tds[i+1] else ''
        if key and val:
            fund[key] = val
    print('=== FUNDAMENTALS (%d keys) ===' % len(fund))
    for k, v in list(fund.items())[:25]:
        print('  %s: %s' % (k, v))

# 2) Signals/Patterns - look for the signal table
tables2 = soup.find_all('table')
for tbl in tables2:
    cls = tbl.get('class', [])
    if any('signal' in str(c).lower() for c in cls):
        print('\n=== SIGNAL TABLE ===')
        rows = tbl.find_all('tr')
        for r in rows[:10]:
            print('  %s' % r.get_text(strip=True)[:100])

# 3) Look for pattern-specific content
print('\n=== PATTERNS ===')
for tag in soup.find_all(['a', 'span', 'div']):
    text = tag.get_text(strip=True)
    if text and any(p in text.lower() for p in ['pattern', 'signal', 'wedge', 'flag', 'triangle', 'channel']):
        if len(text) < 60:
            print('  %s: %s' % (tag.name, text))

# 4) Inside rows
print('\n=== INSIDE ROWS ===')
rows = soup.find_all('tr', class_='styled-row')
for r in rows[:5]:
    tds = r.find_all('td')
    print('  %s' % ' | '.join(td.get_text(strip=True)[:20] for td in tds[:6]))
