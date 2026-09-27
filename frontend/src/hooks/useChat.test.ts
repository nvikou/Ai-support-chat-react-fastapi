import { act, renderHook, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { useChat } from './useChat'

const { getAccessToken, apiJson } = vi.hoisted(() => ({
  getAccessToken: vi.fn(),
  apiJson: vi.fn(),
}))

vi.mock('../lib/api', () => ({
  getAccessToken,
  apiJson,
}))

class MockWebSocket {
  static CONNECTING = 0
  static OPEN = 1
  static CLOSING = 2
  static CLOSED = 3
  static instances: MockWebSocket[] = []

  url: string
  readyState = MockWebSocket.CONNECTING
  onopen: ((ev: Event) => void) | null = null
  onclose: ((ev: CloseEvent) => void) | null = null
  onerror: ((ev: Event) => void) | null = null
  onmessage: ((ev: MessageEvent) => void) | null = null
  sent: string[] = []

  constructor(url: string) {
    this.url = url
    MockWebSocket.instances.push(this)
  }

  close() {
    this.readyState = MockWebSocket.CLOSED
    this.onclose?.(new CloseEvent('close'))
  }

  send(data: string) {
    this.sent.push(data)
  }

  simulateOpen() {
    this.readyState = MockWebSocket.OPEN
    this.onopen?.(new Event('open'))
  }

  simulateError() {
    this.onerror?.(new Event('error'))
  }
}

describe('useChat', () => {
  beforeEach(() => {
    MockWebSocket.instances = []
    vi.stubGlobal('WebSocket', MockWebSocket)
    getAccessToken.mockReturnValue('access-token')
    apiJson.mockResolvedValue({ ticket: 'ws-ticket', expires_in: 60 })
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.clearAllMocks()
  })

  it('connects with a one-time ticket on mount', async () => {
    const { result } = renderHook(() => useChat({ sessionId: 'sess-1' }))

    await waitFor(() => {
      expect(result.current.status).toBe('connecting')
    })
    expect(apiJson).toHaveBeenCalledWith('/auth/ws-ticket', {
      method: 'POST',
    })

    await waitFor(() => {
      expect(MockWebSocket.instances).toHaveLength(1)
    })
    expect(MockWebSocket.instances[0].url).toContain(
      '/ws/chat/sess-1?ticket=ws-ticket',
    )
    expect(MockWebSocket.instances[0].url).not.toContain('access-token')

    act(() => {
      MockWebSocket.instances[0].simulateOpen()
    })
    await waitFor(() => {
      expect(result.current.status).toBe('connected')
    })
  })

  it('sets error when the access token is missing', async () => {
    getAccessToken.mockReturnValue(null)

    const { result } = renderHook(() => useChat())

    await waitFor(() => {
      expect(result.current.status).toBe('error')
    })
    expect(apiJson).not.toHaveBeenCalled()
    expect(MockWebSocket.instances).toHaveLength(0)
  })

  it('sets error when the ws ticket request fails', async () => {
    apiJson.mockRejectedValue(new Error('ticket denied'))

    const { result } = renderHook(() => useChat({ sessionId: 'sess-2' }))

    await waitFor(() => {
      expect(result.current.status).toBe('error')
    })
    expect(MockWebSocket.instances).toHaveLength(0)
  })

  it('sets error when the websocket errors', async () => {
    const { result } = renderHook(() => useChat({ sessionId: 'sess-3' }))

    await waitFor(() => {
      expect(MockWebSocket.instances).toHaveLength(1)
    })
    act(() => {
      MockWebSocket.instances[0].simulateError()
    })
    await waitFor(() => {
      expect(result.current.status).toBe('error')
    })
  })

  it('reconnects when the session id changes', async () => {
    const { result, rerender } = renderHook(
      ({ sessionId }: { sessionId: string }) => useChat({ sessionId }),
      { initialProps: { sessionId: 'sess-a' } },
    )

    await waitFor(() => {
      expect(MockWebSocket.instances).toHaveLength(1)
    })
    const first = MockWebSocket.instances[0]
    act(() => {
      first.simulateOpen()
    })

    rerender({ sessionId: 'sess-b' })

    await waitFor(() => {
      expect(MockWebSocket.instances.length).toBeGreaterThanOrEqual(2)
    })
    const latest = MockWebSocket.instances[MockWebSocket.instances.length - 1]!
    expect(latest.url).toContain('/ws/chat/sess-b?ticket=ws-ticket')
    expect(first.readyState).toBe(MockWebSocket.CLOSED)
    expect(result.current.status).toBe('connecting')
  })
})
