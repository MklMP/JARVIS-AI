import sys; sys.path.insert(0, '.')
import yfinance as yf
from utils.indicators import add_all_indicators
from strategies.micro_strategies import ALL_MICRO_STRATEGIES
from strategies.composite import CompositeOrchestrator

# Fetch more data (1 year)
df = yf.download('AAPL', period='1y', interval='1d', progress=False)
df.columns = [str(c[0]).lower() for c in df.columns]
print(f"Datos: {len(df)} velas diarias")

# Add indicators
df = add_all_indicators(df)
df = df.dropna()
print(f"Con indicadores: {len(df)} velas\n")

# Test each micro-strategy
signals = []
for m in ALL_MICRO_STRATEGIES:
    try:
        s = m.analyze(df)
        signals.append(s)
        if s.action.value != 'hold':
            print(f"  {s.name:30s} → {s.action.value.upper():5s} (conf: {s.confidence:.2f})")
    except Exception as e:
        print(f"  {m.name:30s} → ERROR: {e}")

buys = sum(1 for s in signals if s.action.value == 'buy')
sells = sum(1 for s in signals if s.action.value == 'sell')
holds = sum(1 for s in signals if s.action.value == 'hold')
print(f"\nResumen: {buys}↑ {sells}↓ {holds}⊙ de {len(signals)} micro-estrategias")

# Test composite orchestrator
orch = CompositeOrchestrator()
result = orch.analyze(df)
print(f"\nOrquestador compuesto:")
print(f"  Acción: {result['action']}")
print(f"  Confianza: {result['confidence']:.4f}")
print(f"  Compuestas: {result['buy_count']}↑ {result['sell_count']}↓")
for c in result['composites']:
    print(f"  {c['name']:30s}: {c['action']:5s} conf={c['confidence']:.2f} ({c['buy']}/{c['sell']}/{c['total']})")
for g, s in result.get('group_scores', {}).items():
    print(f"  Grupo {g:20s}: {s:+.3f}")
