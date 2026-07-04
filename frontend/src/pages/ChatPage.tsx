import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import {
  Send,
  AlertTriangle,
  Wifi,
  WifiOff,
  Bot,
  User,
  Plus,
  MessageSquare,
} from 'lucide-react'
import { useChat, type Message } from '../hooks/useChat'
import { apiJson } from '../lib/api'
import clsx from 'clsx'

type ConversationItem = {
  id: string
  session_id: string
  title: string
  status: string
  escalated: boolean
  message_count: number
  updated_at: string
}

type ApiMessage = {
  id: number
  role: string
  content: string
  confidence_score: number | null
  sources: string | null
  created_at: string
}

function ConfidenceBadge({ score }: { score: number }) {
  const pct = Math.round(score * 100)
  const color =
    score >= 0.8
      ? 'text-green-600 bg-green-50'
      : score >= 0.6
        ? 'text-yellow-600 bg-yellow-50'
        : 'text-red-600 bg-red-50'
  return (
    <span className={clsx('text-xs font-medium px-2 py-0.5 rounded-full', color)}>
      {pct}% confidence
    </span>
  )
}

function ChatMessage({ msg }: { msg: Message }) {
  const isUser = msg.role === 'user'
  const isSystem = msg.role === 'system'

  if (isSystem) {
    return (
      <div className="flex justify-center my-2">
        <span className="text-xs text-gray-400 bg-gray-100 px-3 py-1 rounded-full">
          {msg.content}
        </span>
      </div>
    )
  }

  return (
    <div className={clsx('flex gap-3 my-3', isUser && 'flex-row-reverse')}>
      <div
        className={clsx(
          'w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0',
          isUser ? 'bg-brand-600' : 'bg-gray-200',
        )}
      >
        {isUser ? (
          <User className="w-4 h-4 text-white" />
        ) : (
          <Bot className="w-4 h-4 text-gray-600" />
        )}
      </div>
      <div
        className={clsx(
          'max-w-[75%] space-y-1',
          isUser && 'items-end flex flex-col',
        )}
      >
        <div
          className={clsx(
            'px-4 py-3 rounded-2xl text-sm leading-relaxed',
            isUser
              ? 'bg-brand-600 text-white rounded-tr-sm'
              : 'bg-white border border-gray-100 text-gray-800 rounded-tl-sm shadow-sm',
          )}
        >
          {msg.content}
        </div>
        {!isUser && (
          <div className="flex items-center gap-2 flex-wrap">
            {msg.confidence !== undefined && (
              <ConfidenceBadge score={msg.confidence} />
            )}
            {msg.sources && msg.sources.length > 0 && (
              <span className="text-xs text-gray-400">
                Sources: {msg.sources.join(', ')}
              </span>
            )}
          </div>
        )}
        {msg.escalated && msg.escalationReason && (
          <div className="flex items-center gap-1.5 text-xs text-amber-600 bg-amber-50 border border-amber-200 px-3 py-1.5 rounded-lg">
            <AlertTriangle className="w-3 h-3" />
            <span>{msg.escalationReason}</span>
          </div>
        )}
      </div>
    </div>
  )
}

function TypingIndicator() {
  return (
    <div className="flex gap-3 my-3">
      <div className="w-8 h-8 rounded-full bg-gray-200 flex items-center justify-center">
        <Bot className="w-4 h-4 text-gray-600" />
      </div>
      <div className="bg-white border border-gray-100 rounded-2xl rounded-tl-sm px-4 py-3 shadow-sm flex items-center gap-1">
        <span className="typing-dot w-1.5 h-1.5 bg-gray-400 rounded-full block" />
        <span className="typing-dot w-1.5 h-1.5 bg-gray-400 rounded-full block" />
        <span className="typing-dot w-1.5 h-1.5 bg-gray-400 rounded-full block" />
      </div>
    </div>
  )
}

function mapApiMessages(rows: ApiMessage[]): Message[] {
  return rows.map((m) => ({
    id: String(m.id),
    role: m.role as Message['role'],
    content: m.content,
    confidence: m.confidence_score ?? undefined,
    sources: m.sources ? JSON.parse(m.sources) : undefined,
    timestamp: new Date(m.created_at),
  }))
}

export default function ChatPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const navigate = useNavigate()
  const sessionParam = searchParams.get('session')
  const [sessionId, setSessionId] = useState(sessionParam || '')
  const [initialMessages, setInitialMessages] = useState<Message[]>([])
  const [conversations, setConversations] = useState<ConversationItem[]>([])
  const [loadingHistory, setLoadingHistory] = useState(!!sessionParam)
  const creatingSession = useRef(false)

  const loadConversations = useCallback(async () => {
    const data = await apiJson<ConversationItem[]>('/me/conversations')
    setConversations(data)
  }, [])

  useEffect(() => {
    loadConversations()
  }, [loadConversations])

  useEffect(() => {
    if (sessionParam || creatingSession.current) return
    creatingSession.current = true
    apiJson<{ session_id: string }>('/me/conversations', { method: 'POST' })
      .then((data) => {
        setSearchParams({ session: data.session_id })
        loadConversations()
      })
      .catch(() => {
        creatingSession.current = false
      })
  }, [sessionParam, setSearchParams, loadConversations])

  useEffect(() => {
    if (!sessionParam) {
      setSessionId('')
      setInitialMessages([])
      setLoadingHistory(false)
      return
    }

    const conv = conversations.find((c) => c.session_id === sessionParam)
    if (!conv) {
      setSessionId(sessionParam)
      setInitialMessages([])
      setLoadingHistory(false)
      return
    }

    setLoadingHistory(true)
    apiJson<ApiMessage[]>(`/me/conversations/${conv.id}/messages`)
      .then((rows) => {
        setSessionId(sessionParam)
        setInitialMessages(mapApiMessages(rows))
      })
      .finally(() => setLoadingHistory(false))
  }, [sessionParam, conversations])

  const handleTitleChange = useCallback(() => {
    loadConversations()
  }, [loadConversations])

  const { messages, status, isTyping, escalated, sendMessage } = useChat({
    sessionId: sessionId || undefined,
    initialMessages,
    onTitleChange: handleTitleChange,
  })

  const [input, setInput] = useState('')
  const bottomRef = useCallback((node: HTMLDivElement | null) => {
    node?.scrollIntoView({ behavior: 'smooth' })
  }, [])

  useEffect(() => {
    document.getElementById('chat-bottom')?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isTyping])

  const handleSend = () => {
    const text = input.trim()
    if (!text || status !== 'connected') return
    sendMessage(text)
    setInput('')
  }

  const startNewChat = async () => {
    const data = await apiJson<{ session_id: string }>(
      '/me/conversations',
      { method: 'POST' },
    )
    setSearchParams({ session: data.session_id })
    await loadConversations()
  }

  const openConversation = (sid: string) => {
    setSearchParams({ session: sid })
  }

  if (loadingHistory) {
    return (
      <div className="h-[calc(100vh-73px)] flex items-center justify-center">
        <div className="w-8 h-8 border-4 border-brand-600 border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  return (
    <div className="max-w-6xl mx-auto h-[calc(100vh-73px)] flex">
      {/* Sidebar */}
      <aside className="hidden md:flex w-72 flex-col border-r border-gray-200 bg-white">
        <div className="p-4 border-b border-gray-100">
          <button
            onClick={startNewChat}
            className="btn-primary w-full flex items-center justify-center gap-2"
          >
            <Plus className="w-4 h-4" />
            New conversation
          </button>
        </div>
        <div className="flex-1 overflow-y-auto p-2 space-y-1">
          {conversations.length === 0 && (
            <p className="text-xs text-gray-400 text-center py-8 px-4">
              No conversations yet. Start a new one!
            </p>
          )}
          {conversations.map((conv) => (
            <button
              key={conv.id}
              onClick={() => openConversation(conv.session_id)}
              className={clsx(
                'w-full text-left p-3 rounded-xl transition-colors',
                sessionParam === conv.session_id
                  ? 'bg-brand-50 border border-brand-100'
                  : 'hover:bg-gray-50',
              )}
            >
              <p className="text-sm font-medium text-gray-800 truncate">
                {conv.title}
              </p>
              <div className="flex items-center justify-between mt-1">
                <span className="text-xs text-gray-400">
                  {new Date(conv.updated_at).toLocaleDateString()}
                </span>
                <span
                  className={clsx('text-xs px-1.5 py-0.5 rounded-full', {
                    'bg-emerald-100 text-emerald-700':
                      conv.status === 'resolved',
                    'bg-amber-100 text-amber-700':
                      conv.status === 'escalated',
                    'bg-blue-100 text-blue-700': conv.status === 'active',
                  })}
                >
                  {conv.status}
                </span>
              </div>
            </button>
          ))}
        </div>
        <div className="p-3 border-t border-gray-100">
          <button
            onClick={() => navigate('/history')}
            className="w-full text-sm text-brand-600 hover:text-brand-700 flex items-center justify-center gap-1.5 py-2"
          >
            <MessageSquare className="w-4 h-4" />
            View all history
          </button>
        </div>
      </aside>

      {/* Chat area */}
      <div className="flex-1 flex flex-col p-4 gap-4 min-w-0">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            {status === 'connected' ? (
              <>
                <Wifi className="w-4 h-4 text-green-500" />
                <span className="text-sm text-green-600">Connected</span>
              </>
            ) : (
              <>
                <WifiOff className="w-4 h-4 text-red-400" />
                <span className="text-sm text-red-500 capitalize">{status}</span>
              </>
            )}
          </div>
          <button
            onClick={startNewChat}
            className="md:hidden btn-primary text-sm flex items-center gap-1.5 px-3 py-1.5"
          >
            <Plus className="w-4 h-4" /> New
          </button>
          {escalated && (
            <div className="flex items-center gap-1.5 text-sm text-amber-600 bg-amber-50 border border-amber-200 px-3 py-1 rounded-full">
              <AlertTriangle className="w-3.5 h-3.5" />
              Escalated to human agent
            </div>
          )}
        </div>

        <div className="flex-1 overflow-y-auto chat-messages bg-gray-50 rounded-xl p-4 border border-gray-100">
          {messages.length === 0 && (
            <div className="h-full flex flex-col items-center justify-center text-center gap-4">
              <div className="w-16 h-16 bg-brand-100 rounded-2xl flex items-center justify-center">
                <Bot className="w-8 h-8 text-brand-600" />
              </div>
              <div>
                <h2 className="font-semibold text-gray-700 text-lg">
                  AI Support Agent
                </h2>
                <p className="text-gray-400 text-sm mt-1">
                  How can I help you today?
                </p>
              </div>
            </div>
          )}
          {messages.map((msg) => (
            <ChatMessage key={msg.id} msg={msg} />
          ))}
          {isTyping && <TypingIndicator />}
          <div id="chat-bottom" ref={bottomRef} />
        </div>

        <div className="flex gap-3">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && handleSend()}
            placeholder="Type your message..."
            className="flex-1 px-4 py-3 rounded-xl border border-gray-200 bg-white focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent text-sm"
            disabled={status !== 'connected'}
          />
          <button
            onClick={handleSend}
            disabled={!input.trim() || status !== 'connected'}
            className="btn-primary flex items-center gap-2 px-5"
          >
            <Send className="w-4 h-4" />
            Send
          </button>
        </div>
      </div>
    </div>
  )
}
