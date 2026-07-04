import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  MessageSquare,
  Clock,
  AlertTriangle,
  CheckCircle,
  ChevronRight,
} from 'lucide-react'
import { apiJson } from '../lib/api'
import clsx from 'clsx'

type ConversationItem = {
  id: string
  session_id: string
  title: string
  status: string
  escalated: boolean
  message_count: number
  created_at: string
  updated_at: string
}

export default function HistoryPage() {
  const [conversations, setConversations] = useState<ConversationItem[]>([])
  const [filter, setFilter] = useState('all')
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()

  useEffect(() => {
    const path =
      filter === 'all'
        ? '/me/conversations'
        : `/me/conversations?status=${filter}`
    apiJson<ConversationItem[]>(path)
      .then(setConversations)
      .finally(() => setLoading(false))
  }, [filter])

  const statusIcon = (status: string) => {
    if (status === 'resolved') return CheckCircle
    if (status === 'escalated') return AlertTriangle
    return MessageSquare
  }

  return (
    <div className="max-w-4xl mx-auto p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">My History</h1>
        <p className="text-gray-500 text-sm mt-1">
          All your past support conversations
        </p>
      </div>

      <div className="flex gap-1">
        {['all', 'active', 'escalated', 'resolved'].map((s) => (
          <button
            key={s}
            onClick={() => {
              setLoading(true)
              setFilter(s)
            }}
            className={clsx(
              'text-xs px-3 py-1.5 rounded-lg capitalize font-medium',
              filter === s
                ? 'bg-brand-600 text-white'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200',
            )}
          >
            {s}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="flex justify-center py-16">
          <div className="w-8 h-8 border-4 border-brand-600 border-t-transparent rounded-full animate-spin" />
        </div>
      ) : conversations.length === 0 ? (
        <div className="card text-center py-16">
          <MessageSquare className="w-12 h-12 text-gray-300 mx-auto mb-4" />
          <p className="text-gray-500">No conversations found</p>
          <button
            onClick={() => navigate('/')}
            className="btn-primary mt-4 inline-flex"
          >
            Start a conversation
          </button>
        </div>
      ) : (
        <div className="space-y-2">
          {conversations.map((conv) => {
            const Icon = statusIcon(conv.status)
            return (
              <button
                key={conv.id}
                onClick={() =>
                  navigate(`/?session=${conv.session_id}`)
                }
                className="card w-full flex items-center gap-4 hover:border-brand-200 hover:shadow-md transition-all text-left p-4"
              >
                <div
                  className={clsx(
                    'w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0',
                    conv.status === 'resolved'
                      ? 'bg-emerald-100 text-emerald-600'
                      : conv.status === 'escalated'
                        ? 'bg-amber-100 text-amber-600'
                        : 'bg-brand-100 text-brand-600',
                  )}
                >
                  <Icon className="w-5 h-5" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="font-medium text-gray-900 truncate">
                    {conv.title}
                  </p>
                  <div className="flex items-center gap-3 mt-1 text-xs text-gray-400">
                    <span className="flex items-center gap-1">
                      <Clock className="w-3 h-3" />
                      {new Date(conv.updated_at).toLocaleString()}
                    </span>
                    <span>{conv.message_count} messages</span>
                  </div>
                </div>
                <span
                  className={clsx(
                    'text-xs px-2 py-0.5 rounded-full font-medium capitalize',
                    {
                      'bg-emerald-100 text-emerald-700':
                        conv.status === 'resolved',
                      'bg-amber-100 text-amber-700':
                        conv.status === 'escalated',
                      'bg-blue-100 text-blue-700': conv.status === 'active',
                    },
                  )}
                >
                  {conv.status}
                </span>
                <ChevronRight className="w-4 h-4 text-gray-300" />
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}
