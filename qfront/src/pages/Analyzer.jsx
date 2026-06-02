import { useState } from 'react'
import { FiBarChart2, FiTrendingUp, FiTrendingDown, FiActivity, FiClock, FiZap } from 'react-icons/fi'
import StockChart from '../components/StockChart'

const API_BASE = 'http://localhost:8080'

const timeframes = [
  { label: '1min', value: '1m' },
  { label: '5min', value: '5m' },
  { label: '15min', value: '15m' },
  { label: '1h', value: '1h' },
  { label: '4h', value: '4h' },
  { label: '1d', value: '1d' },
]

const strategies = [
  { label: 'Bollinger Bands', value: 'bollinger' },
  { label: 'RSI + MACD', value: 'rsi_macd' },
  { label: 'Soporte/Resistencia', value: 'soporte_resistencia' },
  { label: 'The TradingWay', value: 'sardinas' },
  { label: 'Full Analysis', value: 'completo' },
]

export default function Analyzer() {
  const [symbol, setSymbol] = useState('SPY')
  const [tf, setTf] = useState('1d')
  const [strategy, setStrategy] = useState('completo')
  const [analisis, setAnalisis] = useState(null)
  const [loading, setLoading] = useState(false)

  const runAnalysis = async () => {
    setLoading(true)
    setAnalisis(null)
    try {
      const res = await fetch(`${API_BASE}/api/analyze?symbol=${symbol}&timeframe=${tf}&strategy=${strategy}`)
      const json = await res.json()
      setAnalisis(json)
    } catch {
      setAnalisis({ error: 'Error al conectar con el servidor' })
    } finally { setLoading(false) }
  }

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gradient">Analizador Multi-Timeframe</h1>
        <p className="text-gray-500 text-sm mt-1">Análisis técnico profundo con estrategias cuantitativas</p>
      </div>

      {/* Controls */}
      <div className="glass rounded-2xl p-6 mb-6">
        <div className="flex flex-wrap gap-4 items-end">
          <div>
            <label className="text-xs text-gray-500 mb-1 block">Símbolo</label>
            <input
              value={symbol}
              onChange={e => setSymbol(e.target.value.toUpperCase())}
              className="bg-white/5 border border-white/10 rounded-xl px-4 py-2.5 text-sm text-white w-24 uppercase"
              placeholder="SPY"
            />
          </div>
          <div>
            <label className="text-xs text-gray-500 mb-1 block">Timeframe</label>
            <div className="flex gap-1">
              {timeframes.map(t => (
                <button
                  key={t.value}
                  onClick={() => setTf(t.value)}
                  className={`px-3 py-2 rounded-lg text-xs transition-all ${
                    tf === t.value
                      ? 'bg-neon-cyan/20 text-neon-cyan border border-neon-cyan/30'
                      : 'bg-white/5 text-gray-400 hover:bg-white/10'
                  }`}
                >
                  {t.label}
                </button>
              ))}
            </div>
          </div>
          <div>
            <label className="text-xs text-gray-500 mb-1 block">Estrategia</label>
            <select
              value={strategy}
              onChange={e => setStrategy(e.target.value)}
              className="bg-white/5 border border-white/10 rounded-xl px-4 py-2.5 text-sm text-white"
            >
              {strategies.map(s => (
                <option key={s.value} value={s.value}>{s.label}</option>
              ))}
            </select>
          </div>
          <button
            onClick={runAnalysis}
            disabled={loading}
            className="px-6 py-2.5 rounded-xl bg-neon-cyan/10 text-neon-cyan hover:bg-neon-cyan/20 transition-all flex items-center gap-2 text-sm disabled:opacity-50"
          >
            <FiZap className={loading ? 'animate-spin' : ''} /> Analizar
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Chart */}
        <div className="lg:col-span-2 glass rounded-2xl p-6 neon-glow">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold flex items-center gap-2">
              <FiBarChart2 className="text-neon-cyan" /> {symbol} · {tf.toUpperCase()}
            </h2>
          </div>
          <StockChart symbol={symbol} height={350} />
        </div>

        {/* Analysis Panel */}
        <div className="glass rounded-2xl p-6 space-y-4">
          <h2 className="text-sm font-semibold text-neon-purple flex items-center gap-2">
            <FiActivity /> Resultados
          </h2>

          {loading && (
            <div className="text-center py-10">
              <FiClock className="text-3xl text-neon-cyan mx-auto mb-3 animate-pulse" />
              <p className="text-sm text-gray-500">Analizando {symbol}...</p>
            </div>
          )}

          {analisis && !loading && (
            <div className="space-y-4 animate-fade-in">
              {analisis.score !== undefined && (
                <div className="text-center">
                  <div className="text-xs text-gray-500 mb-1">Score</div>
                  <div className={`text-4xl font-bold ${analisis.score >= 60 ? 'text-green-400' : analisis.score >= 40 ? 'text-neon-gold' : 'text-red-400'}`}>
                    {analisis.score}/100
                  </div>
                </div>
              )}

              {analisis.accion && (
                <div className={`px-4 py-3 rounded-xl text-center text-sm font-semibold ${
                  analisis.accion === 'COMPRA' ? 'bg-green-500/10 text-green-400 border border-green-500/20' :
                  analisis.accion === 'VENTA' ? 'bg-red-500/10 text-red-400 border border-red-500/20' :
                  'bg-neon-gold/10 text-neon-gold border border-neon-gold/20'
                }`}>
                  <FiTrendingUp className="inline mr-1" />
                  {analisis.accion}
                </div>
              )}

              {analisis.indicadores && Object.entries(analisis.indicadores).slice(0, 8).map(([k, v]) => (
                <div key={k} className="flex items-center justify-between py-2 border-b border-white/5 last:border-0">
                  <span className="text-xs text-gray-400">{k}</span>
                  <span className="text-xs text-white font-medium">{typeof v === 'number' ? v.toFixed(2) : String(v)}</span>
                </div>
              ))}

              {analisis.analisis && (
                <div className="pt-3 border-t border-white/5">
                  <div className="text-xs text-gray-400 mb-2">Análisis</div>
                  <p className="text-sm text-gray-200 leading-relaxed">{analisis.analisis}</p>
                </div>
              )}

              {!analisis.score && !analisis.accion && !analisis.indicadores && !analisis.analisis && !analisis.error && (
                <p className="text-sm text-gray-500">Selecciona un símbolo y estrategia para comenzar</p>
              )}
            </div>
          )}

          {!loading && !analisis && (
            <p className="text-sm text-gray-500">Selecciona un símbolo y estrategia para comenzar</p>
          )}
        </div>
      </div>
    </div>
  )
}
