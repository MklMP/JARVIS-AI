import { useState, useEffect } from 'react'
import { FiSearch, FiFilter, FiRefreshCw, FiTrendingUp, FiTrendingDown, FiInfo } from 'react-icons/fi'

const API_BASE = 'http://localhost:8080'

export default function Scanner() {
  const [resultados, setResultados] = useState([])
  const [loading, setLoading] = useState(false)
  const [filtros, setFiltros] = useState({ minScore: 0, soloAlcistas: false, soloBajistas: false })

  const escanear = async () => {
    setLoading(true)
    try {
      const res = await fetch(`${API_BASE}/api/scanner?min_score=${filtros.minScore}`)
      const json = await res.json()
      setResultados(json.resultados || [])
    } catch { setResultados([]) } finally { setLoading(false) }
  }

  useEffect(() => { escanear() }, [])

  const filtrados = resultados.filter(r => {
    const score = r.score || 0
    if (filtros.soloAlcistas && score < 0) return false
    if (filtros.soloBajistas && score > 0) return false
    return score >= filtros.minScore
  })

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold text-gradient">Escáner de Mercado</h1>
          <p className="text-gray-500 text-sm mt-1">Detección de oportunidades en tiempo real</p>
        </div>
        <button
          onClick={escanear}
          disabled={loading}
          className="flex items-center gap-2 px-6 py-3 rounded-xl bg-neon-cyan/10 text-neon-cyan hover:bg-neon-cyan/20 transition-all disabled:opacity-50"
        >
          <FiRefreshCw className={`${loading ? 'animate-spin' : ''}`} /> Escanear
        </button>
      </div>

      {/* Filtros */}
      <div className="glass rounded-2xl p-6 mb-6">
        <div className="flex items-center gap-2 mb-4">
          <FiFilter className="text-neon-cyan" />
          <h2 className="text-sm font-semibold">Filtros</h2>
        </div>
        <div className="flex flex-wrap gap-4 items-center">
          <div className="flex items-center gap-2">
            <span className="text-xs text-gray-400">Score mínimo:</span>
            <select
              value={filtros.minScore}
              onChange={e => setFiltros({ ...filtros, minScore: Number(e.target.value) })}
              className="bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm text-white"
            >
              {[0, 2, 4, 6, 8].map(v => <option key={v} value={v}>{v}+</option>)}
            </select>
          </div>
          <label className="flex items-center gap-2 text-sm text-gray-400 cursor-pointer">
            <input type="checkbox" checked={filtros.soloAlcistas} onChange={e => setFiltros({...filtros, soloAlcistas: e.target.checked, soloBajistas: false})}
              className="accent-neon-cyan" />
            <FiTrendingUp className="text-green-400" /> Solo Alcistas
          </label>
          <label className="flex items-center gap-2 text-sm text-gray-400 cursor-pointer">
            <input type="checkbox" checked={filtros.soloBajistas} onChange={e => setFiltros({...filtros, soloBajistas: e.target.checked, soloAlcistas: false})}
              className="accent-neon-cyan" />
            <FiTrendingDown className="text-red-400" /> Solo Bajistas
          </label>
        </div>
      </div>

      {/* Resultados */}
      <div className="space-y-4">
        {loading && (
          <div className="text-center py-20">
            <FiSearch className="text-4xl text-neon-cyan mx-auto mb-4 animate-pulse" />
            <p className="text-gray-500">Escaneando mercado...</p>
          </div>
        )}

        {!loading && filtrados.length === 0 && (
          <div className="text-center py-20">
            <FiInfo className="text-4xl text-gray-600 mx-auto mb-4" />
            <p className="text-gray-500">No se encontraron oportunidades con los filtros actuales</p>
          </div>
        )}

        {filtrados.map((r, i) => {
          const score = r.score || 0
          const alcista = score > 0
          return (
            <div key={i} className="glass rounded-2xl p-6 glass-hover animate-slide-up" style={{ animationDelay: `${i * 0.05}s` }}>
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-4">
                  <div className={`w-12 h-12 rounded-xl flex items-center justify-center text-lg font-bold ${alcista ? 'bg-green-500/10 text-green-400' : 'bg-red-500/10 text-red-400'}`}>
                    {r.symbol}
                  </div>
                  <div>
                    <h3 className="font-semibold">{r.nombre || r.symbol}</h3>
                    <div className="flex items-center gap-3 mt-1">
                      <span className="text-lg font-bold">${r.precio?.toFixed(2) || '-'}</span>
                      <span className={`text-sm ${alcista ? 'text-green-400' : 'text-red-400'}`}>
                        {alcista ? '+' : ''}{r.cambio_pct?.toFixed(2) || 0}%
                      </span>
                    </div>
                  </div>
                </div>
                <div className="text-right">
                  <div className="text-xs text-gray-500">Score</div>
                  <div className={`text-xl font-bold ${Math.abs(score) >= 7 ? 'text-neon-cyan' : Math.abs(score) >= 4 ? 'text-neon-gold' : 'text-gray-400'}`}>
                    {Math.abs(score)}/10
                  </div>
                </div>
              </div>

              {r.indicadores && (
                <div className="flex flex-wrap gap-3 mt-4 pt-4 border-t border-white/5">
                  {Object.entries(r.indicadores).slice(0, 5).map(([k, v]) => (
                    <div key={k} className="px-3 py-1.5 rounded-lg bg-white/5 text-xs text-gray-400">
                      {k}: <span className="text-white font-medium">{typeof v === 'number' ? v.toFixed(1) : v}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
