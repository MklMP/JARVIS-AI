import urllib.request, json
r = urllib.request.urlopen('http://localhost:8080/api/estrategias', timeout=5)
d = json.loads(r.read())
print('Count:', d['composite_count'])
for c in d['composites']:
    print(' ', c['name'], ':', c['micro_count'], 'micros')
