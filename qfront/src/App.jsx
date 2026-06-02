import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Navbar from './components/Navbar'
import ThreeBackground from './components/ThreeBackground'
import Dashboard from './pages/Dashboard'
import Scanner from './pages/Scanner'
import Analyzer from './pages/Analyzer'

export default function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-dark-bg relative">
        <ThreeBackground />
        <Navbar />
        <main className="relative z-10 pt-16">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/scanner" element={<Scanner />} />
            <Route path="/analyzer" element={<Analyzer />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}
