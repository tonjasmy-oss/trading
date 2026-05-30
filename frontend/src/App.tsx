import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom';
import Dashboard from './pages/Dashboard';
import Portfolio from './pages/Portfolio';
import Trades from './pages/Trades';
import Alerts from './pages/Alerts';
import Market from './pages/Market';

export default function App() {
  return (
    <BrowserRouter>
    <div className="min-h-screen bg-[#0f0f1a] text-gray-100 flex">
      {/* Sidebar */}
      <aside className="w-56 bg-[#1a1a2e] border-r border-[#2d2d44] flex flex-col">
        <div className="px-5 py-4 border-b border-[#2d2d44]">
          <h1 className="text-base font-bold text-cyan-400">📊 三省六部</h1>
          <p className="text-xs text-gray-500 mt-0.5">交易监控系统 v2.0</p>
        </div>
        <nav className="flex-1 py-3">
          {[
            { to: '/', label: 'Dashboard', icon: '📈' },
            { to: '/market', label: '行情', icon: '🌐' },
            { to: '/portfolio', label: '持仓', icon: '💼' },
            { to: '/trades', label: '交易记录', icon: '📋' },
            { to: '/alerts', label: '告警', icon: '🔔' },
          ].map(({ to, label, icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              className={({ isActive }) =>
                `flex items-center gap-2.5 px-5 py-2.5 text-sm transition-colors ${
                  isActive
                    ? 'bg-[#2d2d44] text-cyan-400 border-r-2 border-cyan-400'
                    : 'text-gray-400 hover:text-gray-200 hover:bg-[#252540]'
                }`
              }
            >
              <span>{icon}</span> {label}
            </NavLink>
          ))}
        </nav>
        <div className="px-5 py-3 border-t border-[#2d2d44]">
          <p className="text-xs text-gray-600">后端: :8081</p>
          <p className="text-xs text-gray-600">前端: :5173</p>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 overflow-auto">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/market" element={<Market />} />
          <Route path="/portfolio" element={<Portfolio />} />
          <Route path="/trades" element={<Trades />} />
          <Route path="/alerts" element={<Alerts />} />
        </Routes>
      </main>
    </div>
    </BrowserRouter>
  );
}