import { useEffect, useState, type ElementType } from 'react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import { MessageSquare, AlertTriangle, CheckCircle, TrendingUp, Eye, Check, Users } from 'lucide-react'
import { apiFetch, apiJson } from '../lib/api'
import clsx from 'clsx'

type Stats = {
  total_conversations: number
  escalated: number
  resolved: number
  today: number
  ai_resolution_rate: number
  total_users: number
}

type Conversation = {
  id: string
  session_id: string
  title: string | null
  customer_name: string | null
  customer_email: string | null
  user_id: string | null
  user_name: string | null
  user_email: string | null
  status: string
  escalated: boolean
  escalation_reason: string | null
  created_at: string
  updated_at: string
}

type Message = {
  id: number
  role: string
  content: string
  confidence_score: number | null
  sources: string | null
  created_at: string
}

function StatCard({ label, value, icon: Icon, color }: { label: string; value: string | number; icon: ElementType; color: string }) {
  return (
    <div className="card flex items-center gap-4">
      <div className={clsx('w-12 h-12 rounded-xl flex items-center justify-center', color)}>
        <Icon className="w-6 h-6 text-white" />
      </div>
      <div>
        <p className="text-2xl font-bold text-gray-900">{value}</p>
        <p className="text-sm text-gray-500">{label}</p>
      </div>
    </div>
  )
}

export default function AdminPage() {
  const [stats, setStats] = useState<Stats | null>(null)
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [selectedConv, setSelectedConv] = useState<string | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [filter, setFilter] = useState<string>('all')

  const fetchData = async () => {
    const [statsRes, convsRes] = await Promise.all([
      apiFetch('/admin/stats'),
      apiFetch(`/admin/conversations${filter !== 'all' ? `?status=${filter}` : ''}`),
    ])
    setStats(await statsRes.json())
    setConversations(await convsRes.json())
  }

  useEffect(() => { fetchData() }, [filter])

  const viewMessages = async (id: string) => {
    setSelectedConv(id)
    const res = await apiFetch(`/admin/conversations/${id}/messages`)
    setMessages(await res.json())
  }

  const resolve = async (id: string) => {
    await apiFetch(`/admin/conversations/${id}/resolve`, { method: 'PATCH' })
    fetchData()
  }

  const chartData = stats
    ? [
        { name: 'AI Resolved', value: stats.total_conversations - stats.escalated, fill: '#4f6ef7' },
        { name: 'Escalated', value: stats.escalated, fill: '#f59e0b' },
        { name: 'Resolved', value: stats.resolved, fill: '#10b981' },
      ]
    : []

  return (
    <div className="max-w-7xl mx-auto p-6 space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">Admin Dashboard</h1>

      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
          <StatCard label="Total Conversations" value={stats.total_conversations} icon={MessageSquare} color="bg-brand-600" />
          <StatCard label="Today" value={stats.today} icon={TrendingUp} color="bg-indigo-500" />
          <StatCard label="Escalated" value={stats.escalated} icon={AlertTriangle} color="bg-amber-500" />
          <StatCard label="AI Resolution Rate" value={`${stats.ai_resolution_rate}%`} icon={CheckCircle} color="bg-emerald-500" />
          <StatCard label="Registered Users" value={stats.total_users} icon={Users} color="bg-violet-500" />
        </div>
      )}

      <div className="grid lg:grid-cols-3 gap-6">
        {/* Chart */}
        <div className="card">
          <h2 className="font-semibold text-gray-900 mb-4">Overview</h2>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={chartData}>
              <XAxis dataKey="name" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip />
              <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                {chartData.map((entry, index) => (
                  <Cell key={index} fill={entry.fill} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Conversations list */}
        <div className="card lg:col-span-2">
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-semibold text-gray-900">Conversations</h2>
            <div className="flex gap-1">
              {['all', 'active', 'escalated', 'resolved'].map((s) => (
                <button
                  key={s}
                  onClick={() => setFilter(s)}
                  className={clsx('text-xs px-3 py-1 rounded-lg capitalize', filter === s ? 'bg-brand-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200')}
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
          <div className="space-y-2 max-h-64 overflow-y-auto">
            {conversations.map((conv) => (
              <div key={conv.id} className="flex items-center justify-between p-3 rounded-lg bg-gray-50 hover:bg-gray-100 transition-colors">
                <div className="min-w-0">
                  <p className="text-sm font-medium text-gray-800 truncate">
                    {conv.title || conv.customer_name || conv.user_name || conv.session_id.slice(0, 8) + '...'}
                  </p>
                  <p className="text-xs text-gray-400">
                    {conv.user_email || conv.customer_email || 'Anonymous'} · {new Date(conv.updated_at).toLocaleString()}
                  </p>
                </div>
                <div className="flex items-center gap-2 ml-2">
                  <span className={clsx('text-xs px-2 py-0.5 rounded-full font-medium', {
                    'bg-emerald-100 text-emerald-700': conv.status === 'resolved',
                    'bg-amber-100 text-amber-700': conv.status === 'escalated',
                    'bg-blue-100 text-blue-700': conv.status === 'active',
                  })}>
                    {conv.status}
                  </span>
                  <button onClick={() => viewMessages(conv.id)} className="p-1 hover:bg-white rounded text-gray-400 hover:text-brand-600">
                    <Eye className="w-4 h-4" />
                  </button>
                  {conv.status !== 'resolved' && (
                    <button onClick={() => resolve(conv.id)} className="p-1 hover:bg-white rounded text-gray-400 hover:text-emerald-600">
                      <Check className="w-4 h-4" />
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Message viewer */}
      {selectedConv && (
        <div className="card">
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-semibold text-gray-900">Conversation Messages</h2>
            <button onClick={() => setSelectedConv(null)} className="text-sm text-gray-400 hover:text-gray-600">Close</button>
          </div>
          <div className="space-y-3 max-h-96 overflow-y-auto">
            {messages.map((msg) => (
              <div key={msg.id} className={clsx('flex gap-3', msg.role === 'user' && 'flex-row-reverse')}>
                <div className={clsx('px-4 py-2 rounded-xl text-sm max-w-[70%]', msg.role === 'user' ? 'bg-brand-600 text-white' : 'bg-gray-100 text-gray-800')}>
                  <p>{msg.content}</p>
                  {msg.confidence_score !== null && (
                    <p className="text-xs mt-1 opacity-70">Confidence: {Math.round(msg.confidence_score * 100)}%</p>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
