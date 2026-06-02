import { useState, useEffect } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { FiGrid, FiSearch, FiBarChart2, FiMessageCircle, FiCpu } from 'react-icons/fi'

const links = [
  { path: '/', label: 'Panel', icon: FiGrid },
  { path: '/scanner', label: 'Escáner', icon: FiSearch },
  { path: '/analyzer', label: 'Analizar', icon: FiBarChart2 },
]

export default function Navbar() {
  const location = useLocation()
  const [scrolled, setScrolled] = useState(false)
  const [chatOpen, setChatOpen] = useState(false)

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 20)
    window.addEventListener('scroll', onScroll)
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  return (
    <>
      <nav className={`fixed top-0 left-0 right-0 z-50 transition-all duration-500 ${scrolled ? 'glass shadow-lg' : 'bg-transparent'}`}>
        <div className="max-w-7xl mx-auto px-4 h-16 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-3 group">
            <div className="relative">
              <FiCpu className="text-2xl text-neon-cyan animate-pulse-glow" />
              <div className="absolute inset-0 blur-xl bg-neon-cyan/20 rounded-full" />
            </div>
            <span className="text-xl font-bold">
              <span className="text-gradient">JARVIS</span>
              <span className="text-gray-400 ml-1 text-sm hidden sm:inline">AI</span>
            </span>
          </Link>

          <div className="hidden md:flex items-center gap-1">
            {links.map(l => {
              const active = location.pathname === l.path
              return (
                <Link
                  key={l.path}
                  to={l.path}
                  className={`flex items-center gap-2 px-4 py-2 rounded-xl text-sm transition-all duration-300 ${
                    active
                      ? 'bg-neon-cyan/10 text-neon-cyan neon-glow'
                      : 'text-gray-400 hover:text-white hover:bg-white/5'
                  }`}
                >
                  <l.icon className="text-base" />
                  {l.label}
                </Link>
              )
            })}
          </div>

          <button
            onClick={() => setChatOpen(!chatOpen)}
            className="flex items-center gap-2 px-4 py-2 rounded-xl bg-neon-cyan/10 text-neon-cyan hover:bg-neon-cyan/20 transition-all duration-300 text-sm"
          >
            <FiMessageCircle />
            Chat
          </button>
        </div>
      </nav>

      {chatOpen && (
        <div className="fixed bottom-6 right-6 z-50 w-96 h-[500px] glass rounded-2xl neon-glow flex flex-col overflow-hidden animate-slide-up">
          <div className="flex items-center justify-between p-4 border-b border-white/5">
            <span className="text-sm font-semibold text-neon-cyan">JARVIS Chat</span>
            <button onClick={() => setChatOpen(false)} className="text-gray-500 hover:text-white text-lg leading-none">&times;</button>
          </div>
          <iframe
            src="http://localhost:5000"
            className="flex-1 w-full border-none bg-transparent"
            title="JARVIS Chat"
          />
        </div>
      )}
    </>
  )
}
