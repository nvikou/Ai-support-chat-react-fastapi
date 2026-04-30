import { useEffect, useRef, useState, useCallback } from 'react'
import { v4 as uuidv4 } from 'uuid'

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

export function useChat() {
  const [messages, setMessages] = useState<Message[]>([])
  const [status, setStatus] = useState<WsStatus>('disconnected')
  const [isTyping, setIsTyping] = useState(false)
  const [escalated, setEscalated] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)
  const sessionId = useRef(uuidv4())

  const connect = useCallback(() => {
    const wsUrl = `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}/ws/chat/${sessionId.current}`
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
      } else if (data.type === 'typing') {
        setIsTyping(true)
      } else if (data.type === 'message') {
        setIsTyping(false)
        setEscalated(data.escalated)
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
            content: 'An error occurred. Please try again.',
            timestamp: new Date(),
          },
        ])
      }
    }
  }, [])

  useEffect(() => {
    connect()
    return () => wsRef.current?.close()
  }, [connect])

  const sendMessage = useCallback((text: string) => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return
    setMessages((prev) => [
      ...prev,
      { id: uuidv4(), role: 'user', content: text, timestamp: new Date() },
    ])
    wsRef.current.send(JSON.stringify({ message: text }))
  }, [])

  return { messages, status, isTyping, escalated, sendMessage, sessionId: sessionId.current }
}
