import { Routes, Route, NavLink } from 'react-router-dom'
import { Bot, LayoutDashboard, BookOpen } from 'lucide-react'
import ChatPage from './pages/ChatPage'
import AdminPage from './pages/AdminPage'
import KnowledgePage from './pages/KnowledgePage'

export default function App() {
  return (
    <div className="min-h-screen flex flex-col">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between shadow-sm">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 bg-brand-600 rounded-lg flex items-center justify-center">
            <Bot className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="font-bold text-gray-900 text-lg leading-none">VateCon</h1>
            <p className="text-xs text-gray-500">AI Support Agent</p>
          </div>
        </div>
        <nav className="flex items-center gap-1">
          <NavLink
            to="/"
            className={({ isActive }) =>
              `flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                isActive ? 'bg-brand-50 text-brand-700' : 'text-gray-600 hover:bg-gray-100'
              }`
            }
          >
            <Bot className="w-4 h-4" /> Chat
          </NavLink>
          <NavLink
            to="/admin"
            className={({ isActive }) =>
              `flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                isActive ? 'bg-brand-50 text-brand-700' : 'text-gray-600 hover:bg-gray-100'
              }`
            }
          >
            <LayoutDashboard className="w-4 h-4" /> Dashboard
          </NavLink>
          <NavLink
            to="/knowledge"
            className={({ isActive }) =>
              `flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                isActive ? 'bg-brand-50 text-brand-700' : 'text-gray-600 hover:bg-gray-100'
              }`
            }
          >
            <BookOpen className="w-4 h-4" /> Knowledge Base
          </NavLink>
        </nav>
      </header>

      {/* Main content */}
      <main className="flex-1">
        <Routes>
          <Route path="/" element={<ChatPage />} />
          <Route path="/admin" element={<AdminPage />} />
          <Route path="/knowledge" element={<KnowledgePage />} />
        </Routes>
      </main>
    </div>
  )
}
