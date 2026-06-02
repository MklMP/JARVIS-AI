import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, Area, AreaChart } from 'recharts'
import { useState, useEffect } from 'react'

const API_BASE = 'http://localhost:8080'

export default function StockChart({ symbol = 'SPY', height = 300 }) {
  const [data, setData] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchData = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/history/${symbol}?period=5d&interval=5m`)
        const json = await res.json()
        if (json.ok && json.data?.length > 0) {
          setData(json.data.map(d => ({
            time: new Date(d.time).toLocaleTimeString('es', { hour: '2-digit', minute: '2-digit' }),
            price: d.close,
          })))
        }
      } catch { /* ignore */ } finally { setLoading(false) }
    }
    fetchData()
    const interval = setInterval(fetchData, 30000)
    return () => clearInterval(interval)
  }, [symbol])

  if (loading) return <div className="h-[300px] flex items-center justify-center text-gray-500 text-sm">Cargando gráfico...</div>
  if (!data.length) return <div className="h-[300px] flex items-center justify-center text-gray-500 text-sm">Sin datos</div>

  const prices = data.map(d => d.price)
  const min = Math.min(...prices)
  const max = Math.max(...prices)
  const green = prices[0] <= prices[prices.length - 1]

  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data}>
        <defs>
          <linearGradient id={`grad-${symbol}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={green ? '#22c55e' : '#ef4444'} stopOpacity={0.3} />
            <stop offset="100%" stopColor={green ? '#22c55e' : '#ef4444'} stopOpacity={0} />
          </linearGradient>
        </defs>
        <XAxis dataKey="time" axisLine={false} tickLine={false} tick={{ fill: '#4a5568', fontSize: 10 }} />
        <YAxis domain={[min * 0.999, max * 1.001]} axisLine={false} tickLine={false} tick={{ fill: '#4a5568', fontSize: 10 }} width={60} />
        <Tooltip
          contentStyle={{ background: 'rgba(18,18,26,0.9)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 12, backdropFilter: 'blur(20px)', color: '#e2e8f0' }}
          labelStyle={{ color: '#00d4ff' }}
        />
        <Area type="monotone" dataKey="price" stroke={green ? '#22c55e' : '#ef4444'} strokeWidth={2} fill={`url(#grad-${symbol})`} dot={false} />
      </AreaChart>
    </ResponsiveContainer>
  )
}
