import { useState, useEffect, useRef } from 'react'
import { FiSend, FiTrendingUp, FiClock, FiActivity, FiDollarSign, FiBarChart2 } from 'react-icons/fi'
import StockChart from '../components/StockChart'

const API_BASE = 'http://localhost:8080'

const quickActions = [
  { label: 'Mejor Acción', query: 'cual es la mejor accion para operar hoy', icon: FiTrendingUp },
  { label: 'RSI SPY', query: 'cual es el RSI de SPY', icon: FiActivity },
  { label: 'Análisis TSLA', query: 'analiza TSLA', icon: FiBarChart2 },
  { label: 'Mercado Hoy', query: 'como esta el mercado hoy', icon: FiDollarSign },
]

export default function Dashboard() {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [veredicto, setVeredicto] = useState(null)
  const [ws, setWs] = useState(null)
  const chatEnd = useRef(null)

  useEffect(() => {
    try {
      const socket = new WebSocket('ws://localhost:8080/ws')
      socket.onmessage = (e) => {
        try {
          const data = JSON.parse(e.data)
          if (data.type === 'veredicto') setVeredicto(data)
          else if (data.type === 'price') updatePrice(data)
        } catch { /* ignore */ }
      }
      setWs(socket)
      return () => socket.close()
    } catch { /* ignore */ }
  }, [])

  useEffect(() => { chatEnd.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages])

  const sendMessage = async (text) => {
    const q = text || input
    if (!q.trim() || loading) return
    setInput('')
    setMessages(prev => [...prev, { role: 'user', content: q }])
    setLoading(true)
    try {
      const res = await fetch(`${API_BASE}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mensaje: q }),
      })
      const json = await res.json()
      setMessages(prev => [...prev, { role: 'assistant', content: json.respuesta || '...' }])
    } catch {
      setMessages(prev => [...prev, { role: 'assistant', content: '⚠️ Error de conexión' }])
    } finally { setLoading(false) }
  }

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

        <div className="lg:col-span-2 space-y-6">
          {/* Market Overview Cards */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            {[{ label: 'SPY', val: '5,432', chg: '+0.32%', up: true },
              { label: 'QQQ', val: '18,876', chg: '+0.45%', up: true },
              { label: 'DXY', val: '104.2', chg: '-0.12%', up: false },
              { label: 'VIX', val: '14.8', chg: '-2.1%', up: false },
            ].map((m, i) => (
              <div key={i} className="glass rounded-2xl p-4 animate-slide-up" style={{ animationDelay: `${i * 0.1}s` }}>
                <div className="text-xs text-gray-500 mb-1">{m.label}</div>
                <div className="text-lg font-bold">{m.val}</div>
                <div className={`text-xs ${m.up ? 'text-green-400' : 'text-red-400'}`}>{m.chg}</div>
              </div>
            ))}
          </div>

          {/* Main Chart */}
          <div className="glass rounded-2xl p-6 neon-glow">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold flex items-center gap-2">
                <FiTrendingUp className="text-neon-cyan" /> SPY - S&P 500
              </h2>
              <div className="flex gap-2">
                {['5d', '1m', '3m'].map(p => (
                  <button key={p} className="px-3 py-1 rounded-lg text-xs bg-white/5 hover:bg-white/10 text-gray-400 hover:text-white transition-all">{p}</button>
                ))}
              </div>
            </div>
            <StockChart symbol="SPY" />
          </div>

          {/* Quick Actions */}
          <div className="flex flex-wrap gap-3">
            {quickActions.map((a, i) => (
              <button
                key={i}
                onClick={() => sendMessage(a.query)}
                className="flex items-center gap-2 px-4 py-3 rounded-xl glass glass-hover text-sm text-gray-300 hover:text-white transition-all animate-slide-up"
                style={{ animationDelay: `${i * 0.1}s` }}
              >
                <a.icon className="text-neon-cyan" /> {a.label}
              </button>
            ))}
          </div>

          {/* Veredicto Card */}
          {veredicto && (
            <div className="glass rounded-2xl p-6 border border-neon-purple/20 neon-glow">
              <h3 className="text-sm font-semibold text-neon-purple mb-3">📋 VEREDICTO FINAL</h3>
              {veredicto.symbol && (
                <div className="flex items-center justify-between mb-4">
                  <div>
                    <span className="text-2xl font-bold">{veredicto.symbol}</span>
                    <span className={`ml-3 text-lg ${veredicto.accion === 'COMPRA' ? 'text-green-400' : 'text-red-400'}`}>
                      {veredicto.accion}
                    </span>
                  </div>
                  <div className="text-right">
                    <div className="text-sm text-gray-400">Score</div>
                    <div className="text-xl font-bold text-neon-cyan">{veredicto.score}/100</div>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Chat Panel */}
        <div className="glass rounded-2xl flex flex-col h-[600px] lg:sticky lg:top-20">
          <div className="p-4 border-b border-white/5">
            <h2 className="text-sm font-semibold text-neon-cyan">JARVIS AI</h2>
          </div>
          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {messages.map((m, i) => (
              <div key={i} className={`chat-message flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                <div className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${
                  m.role === 'user'
                    ? 'bg-neon-cyan/10 text-neon-cyan border border-neon-cyan/20'
                    : 'glass text-gray-200'
                }`}>
                  {m.content}
                </div>
              </div>
            ))}
            {loading && (
              <div className="flex justify-start">
                <div className="glass rounded-2xl px-4 py-3 text-sm text-gray-400">
                  <span className="animate-pulse">JARVIS está pensando...</span>
                </div>
              </div>
            )}
            <div ref={chatEnd} />
          </div>
          <div className="p-4 border-t border-white/5">
            <div className="flex gap-2">
              <input
                value={input}
                onChange={e => setInput(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && sendMessage()}
                placeholder="Pregúntale a JARVIS..."
                className="flex-1 bg-white/5 rounded-xl px-4 py-3 text-sm text-white placeholder-gray-500 border border-white/5 focus:border-neon-cyan/50 focus:outline-none transition-all"
              />
              <button
                onClick={() => sendMessage()}
                disabled={loading}
                className="px-4 py-3 rounded-xl bg-neon-cyan/10 text-neon-cyan hover:bg-neon-cyan/20 transition-all disabled:opacity-50"
              >
                <FiSend />
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

function updatePrice(data) {
  // Future: update live prices
}
