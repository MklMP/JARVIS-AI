class PineScriptGenerator:
    def __init__(self, webhook_url: str = "http://localhost:8080/webhook/tradingview"):
        self.webhook_url = webhook_url

    def generate_master_script(self, symbols: list = None) -> str:
        if symbols is None:
            symbols = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA']

        symbol_filter = ' or '.join([f'syminfo.ticker == "{s}"' for s in symbols])

        return f'''//@version=5
indicator("QuantumTrade Master Signal", overlay=true, format=format.price)

// === Inputs ===
webhook_url = "{self.webhook_url}"

// === SMA Crossover ===
fast_sma = input.int(9, "Fast SMA")
slow_sma = input.int(21, "Slow SMA")
sma_fast = ta.sma(close, fast_sma)
sma_slow = ta.sma(close, slow_sma)
sma_buy = ta.crossover(sma_fast, sma_slow)
sma_sell = ta.crossunder(sma_fast, sma_slow)

// === RSI ===
rsi_len = input.int(14, "RSI Length")
rsi_ob = input.int(70, "RSI Overbought")
rsi_os = input.int(30, "RSI Oversold")
rsi_val = ta.rsi(close, rsi_len)
rsi_buy = ta.crossover(rsi_val, rsi_os)
rsi_sell = ta.crossunder(rsi_val, rsi_ob)

// === MACD ===
[macd_line, signal_line, hist] = ta.macd(close, 12, 26, 9)
macd_buy = ta.crossover(macd_line, signal_line)
macd_sell = ta.crossunder(macd_line, signal_line)

// === Bollinger Bands ===
bb_len = input.int(20, "BB Length")
bb_mult = input.float(2.0, "BB StdDev")
[bb_upper, bb_mid, bb_lower] = ta.bb(close, bb_len, bb_mult)
bb_buy = ta.crossover(close, bb_lower)
bb_sell = ta.crossunder(close, bb_upper)

// === Stochastic RSI ===
stoch_k = ta.stoch(close, high, low, 14)
stoch_d = ta.sma(stoch_k, 3)
stoch_buy = ta.crossover(stoch_k, stoch_d) and stoch_k < 20
stoch_sell = ta.crossunder(stoch_k, stoch_d) and stoch_k > 80

// === ADX ===
adx_val = ta.adx(high, low, close, 14)
adx_strong = adx_val > 25

// === EMA Trend ===
ema_9 = ta.ema(close, 9)
ema_21 = ta.ema(close, 21)
ema_50 = ta.ema(close, 50)
ema_bullish = ema_9 > ema_21 and ema_21 > ema_50
ema_bearish = ema_9 < ema_21 and ema_21 < ema_50

// === Ichimoku ===
tenkan = (ta.highest(high, 9) + ta.lowest(low, 9)) / 2
kijun = (ta.highest(high, 26) + ta.lowest(low, 26)) / 2
span_a = (tenkan + kijun) / 2
span_b = (ta.highest(high, 52) + ta.lowest(low, 52)) / 2
cloud_bullish = close > span_a and close > span_b
cloud_bearish = close < span_a and close < span_b

// === Volume ===
vol_sma = ta.sma(volume, 20)
vol_surge = volume > vol_sma * 1.5

// === Combined Signal ===
buy_signal = (
    (sma_buy ? 2 : 0) +
    (rsi_buy ? 2 : 0) +
    (macd_buy ? 2 : 0) +
    (bb_buy ? 1 : 0) +
    (stoch_buy ? 2 : 0) +
    (ema_bullish ? 1 : 0) +
    (cloud_bullish ? 1 : 0)
)

sell_signal = (
    (sma_sell ? 2 : 0) +
    (rsi_sell ? 2 : 0) +
    (macd_sell ? 2 : 0) +
    (bb_sell ? 1 : 0) +
    (stoch_sell ? 2 : 0) +
    (ema_bearish ? 1 : 0) +
    (cloud_bearish ? 1 : 0)
)

buy_confidence = buy_signal / 11.0
sell_confidence = sell_signal / 11.0

// === Alerts ===
if buy_signal >= 3 and ({symbol_filter})
    alert(message='{{"action":"buy","symbol":"' + syminfo.ticker + '","price":"' + str(close) + '","confidence":"' + str(buy_confidence) + '","strategies":' + str(buy_signal) + ',"timestamp":"' + str(timenow) + '"}', freq=alert.freq_once_per_bar_close)

if sell_signal >= 3 and ({symbol_filter})
    alert(message='{{"action":"sell","symbol":"' + syminfo.ticker + '","price":"' + str(close) + '","confidence":"' + str(sell_confidence) + '","strategies":' + str(sell_signal) + ',"timestamp":"' + str(timenow) + '"}', freq=alert.freq_once_per_bar_close)

// === Visuals ===
plotshape(buy_signal >= 3 and ({symbol_filter}), style=shape.triangleup, location=location.belowbar, color=color.green, size=size.small)
plotshape(sell_signal >= 3 and ({symbol_filter}), style=shape.triangledown, location=location.abovebar, color=color.red, size=size.small)

// === EMAs ===
plot(ema_9, "EMA 9", color.blue, 1)
plot(ema_21, "EMA 21", color.orange, 1)
plot(ema_50, "EMA 50", color.purple, 1)

// === BB ===
plot(bb_upper, "BB Upper", color.gray)
plot(bb_mid, "BB Mid", color.gray)
plot(bb_lower, "BB Lower", color.gray)
'''

    def generate_strategy_script(self, strategy_name: str) -> str:
        scripts = {
            'sma_crossover': self._sma_crossover_script(),
            'rsi_divergence': self._rsi_divergence_script(),
            'macd_confirmation': self._macd_confirmation_script(),
            'bb_squeeze': self._bb_squeeze_script(),
        }
        return scripts.get(strategy_name, self._sma_crossover_script())

    def _sma_crossover_script(self) -> str:
        return '''//@version=5
indicator("SMA Crossover Strategy", overlay=true)
fast = input.int(9, "Fast SMA")
slow = input.int(21, "Slow SMA")
sma_fast = ta.sma(close, fast)
sma_slow = ta.sma(close, slow)
plot(sma_fast, "Fast", color.blue)
plot(sma_slow, "Slow", color.red)
plotshape(ta.crossover(sma_fast, sma_slow), style=shape.triangleup, location=location.belowbar, color=color.green)
plotshape(ta.crossunder(sma_fast, sma_slow), style=shape.triangledown, location=location.abovebar, color=color.red)
'''

    def _rsi_divergence_script(self) -> str:
        return '''//@version=5
indicator("RSI Divergence", overlay=false)
rsi_len = input.int(14, "RSI Length")
rsi_val = ta.rsi(close, rsi_len)
ob = input.int(70, "Overbought")
os = input.int(30, "Oversold")
hline(ob, "OB", color.red)
hline(os, "OS", color.green)
plot(rsi_val, "RSI", color.purple)
'''

    def _macd_confirmation_script(self) -> str:
        return '''//@version=5
indicator("MACD Confirmation", overlay=false)
[macd, signal, hist] = ta.macd(close, 12, 26, 9)
plot(macd, "MACD", color.blue)
plot(signal, "Signal", color.orange)
hline(0, "Zero", color.gray)
plot(hist, "Histogram", color.navy, style=plot.style_histogram)
'''

    def _bb_squeeze_script(self) -> str:
        return '''//@version=5
indicator("BB Squeeze", overlay=true)
len = input.int(20, "Length")
mult = input.float(2.0, "StdDev")
[upper, mid, lower] = ta.bb(close, len, mult)
bb_width = (upper - lower) / mid
squeeze = bb_width < ta.sma(bb_width, 50)
plot(upper, "Upper", color.gray)
plot(mid, "Mid", color.gray)
plot(lower, "Lower", color.gray)
bgcolor(squeeze ? color.new(color.yellow, 90) : na)
'''
