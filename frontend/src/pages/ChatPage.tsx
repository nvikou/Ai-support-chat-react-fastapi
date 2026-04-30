import { useEffect, useRef, useState } from 'react'
import { Send, AlertTriangle, Wifi, WifiOff, Bot, User } from 'lucide-react'
import { useChat, type Message } from '../hooks/useChat'
import clsx from 'clsx'

function ConfidenceBadge({ score }: { score: number }) {
  const pct = Math.round(score * 100)
  const color = score >= 0.8 ? 'text-green-600 bg-green-50' : score >= 0.6 ? 'text-yellow-600 bg-yellow-50' : 'text-red-600 bg-red-50'
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
        <span className="text-xs text-gray-400 bg-gray-100 px-3 py-1 rounded-full">{msg.content}</span>
      </div>
    )
  }

  return (
    <div className={clsx('flex gap-3 my-3', isUser && 'flex-row-reverse')}>
      <div className={clsx('w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0', isUser ? 'bg-brand-600' : 'bg-gray-200')}>
        {isUser ? <User className="w-4 h-4 text-white" /> : <Bot className="w-4 h-4 text-gray-600" />}
      </div>
      <div className={clsx('max-w-[75%] space-y-1', isUser && 'items-end flex flex-col')}>
        <div className={clsx('px-4 py-3 rounded-2xl text-sm leading-relaxed', isUser ? 'bg-brand-600 text-white rounded-tr-sm' : 'bg-white border border-gray-100 text-gray-800 rounded-tl-sm shadow-sm')}>
          {msg.content}
        </div>
        {!isUser && (
          <div className="flex items-center gap-2 flex-wrap">
            {msg.confidence !== undefined && <ConfidenceBadge score={msg.confidence} />}
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

export default function ChatPage() {
  const { messages, status, isTyping, escalated, sendMessage } = useChat()
  const [input, setInput] = useState('')
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isTyping])

  const handleSend = () => {
    const text = input.trim()
    if (!text || status !== 'connected') return
    sendMessage(text)
    setInput('')
  }

  return (
    <div className="max-w-3xl mx-auto h-[calc(100vh-73px)] flex flex-col p-4 gap-4">
      {/* Status bar */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {status === 'connected' ? (
            <><Wifi className="w-4 h-4 text-green-500" /><span className="text-sm text-green-600">Connected</span></>
          ) : (
            <><WifiOff className="w-4 h-4 text-red-400" /><span className="text-sm text-red-500 capitalize">{status}</span></>
          )}
        </div>
        {escalated && (
          <div className="flex items-center gap-1.5 text-sm text-amber-600 bg-amber-50 border border-amber-200 px-3 py-1 rounded-full">
            <AlertTriangle className="w-3.5 h-3.5" />
            Escalated to human agent
          </div>
        )}
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto chat-messages bg-gray-50 rounded-xl p-4 border border-gray-100">
        {messages.length === 0 && (
          <div className="h-full flex flex-col items-center justify-center text-center gap-4">
            <div className="w-16 h-16 bg-brand-100 rounded-2xl flex items-center justify-center">
              <Bot className="w-8 h-8 text-brand-600" />
            </div>
            <div>
              <h2 className="font-semibold text-gray-700 text-lg">AI Support Agent</h2>
              <p className="text-gray-400 text-sm mt-1">How can I help you today?</p>
            </div>
          </div>
        )}
        {messages.map((msg) => <ChatMessage key={msg.id} msg={msg} />)}
        {isTyping && <TypingIndicator />}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
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
  )
}
