import { useEffect, useRef, useState, useCallback } from 'react'
import { v4 as uuidv4 } from 'uuid'
import { getAccessToken } from '../lib/api'

export type Message = {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  confidence?: number
  sources?: string[]
  escalated?: boolean
  escalationReason?: string
  timestamp: Date
}

type WsStatus = 'connecting' | 'connected' | 'disconnected' | 'error'

type Options = {
  sessionId?: string
  initialMessages?: Message[]
  onTitleChange?: (title: string) => void
}

export function useChat({
  sessionId: externalSessionId,
  initialMessages = [],
  onTitleChange,
}: Options = {}) {
  const [messages, setMessages] = useState<Message[]>(initialMessages)
  const [status, setStatus] = useState<WsStatus>('disconnected')
  const [isTyping, setIsTyping] = useState(false)
  const [escalated, setEscalated] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)
  const sessionId = useRef(externalSessionId || uuidv4())

  useEffect(() => {
    sessionId.current = externalSessionId || uuidv4()
    setMessages(initialMessages)
    setEscalated(false)
    setIsTyping(false)
  }, [externalSessionId, initialMessages])

  const connect = useCallback(() => {
    const token = getAccessToken()
    if (!token) {
      setStatus('error')
      return
    }

    wsRef.current?.close()

    const wsUrl =
      `${window.location.protocol === 'https:' ? 'wss' : 'ws'}` +
      `://${window.location.host}/ws/chat/${sessionId.current}` +
      `?token=${encodeURIComponent(token)}`

    setStatus('connecting')
    const ws = new WebSocket(wsUrl)
    wsRef.current = ws

    ws.onopen = () => setStatus('connected')
    ws.onclose = () => setStatus('disconnected')
    ws.onerror = () => setStatus('error')

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data)
      if (data.type === 'connected') {
        setEscalated(data.escalated)
        if (data.title) onTitleChange?.(data.title)
      } else if (data.type === 'typing') {
        setIsTyping(true)
      } else if (data.type === 'message') {
        setIsTyping(false)
        setEscalated(data.escalated)
        if (data.title) onTitleChange?.(data.title)
        setMessages((prev) => [
          ...prev,
          {
            id: uuidv4(),
            role: 'assistant',
            content: data.content,
            confidence: data.confidence,
            sources: data.sources,
            escalated: data.escalated,
            escalationReason: data.escalation_reason,
            timestamp: new Date(),
          },
        ])
      } else if (data.type === 'error') {
        setIsTyping(false)
        setMessages((prev) => [
          ...prev,
          {
            id: uuidv4(),
            role: 'system',
            content: data.content || 'An error occurred.',
            timestamp: new Date(),
          },
        ])
      }
    }
  }, [onTitleChange])

  useEffect(() => {
    connect()
    return () => wsRef.current?.close()
  }, [connect, externalSessionId])

  const sendMessage = useCallback((text: string) => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return
    setMessages((prev) => [
      ...prev,
      { id: uuidv4(), role: 'user', content: text, timestamp: new Date() },
    ])
    wsRef.current.send(JSON.stringify({ message: text }))
  }, [])

  return {
    messages,
    status,
    isTyping,
    escalated,
    sendMessage,
    sessionId: sessionId.current,
  }
}
