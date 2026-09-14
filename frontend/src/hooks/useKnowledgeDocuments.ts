import { useCallback, useEffect, useRef, useState } from 'react'
import { apiJson } from '../lib/api'

/** How often to re-fetch while any document is still ingesting. */
export const KNOWLEDGE_POLL_MS = 2000

export type KnowledgeDocStatus = 'pending' | 'indexed' | 'failed'

export type KnowledgeDocument = {
  id: number
  filename: string
  chunk_count: number
  status: KnowledgeDocStatus | string
  error_message: string | null
  uploaded_at: string
}

export function hasPendingIngest(
  docs: KnowledgeDocument[],
): boolean {
  return docs.some((doc) => doc.status === 'pending')
}

type Options = {
  /** Poll interval while ingest is pending (default 2s). */
  pollIntervalMs?: number
}

/**
 * Lists knowledge documents and polls only while ingest is in flight.
 *
 * Why conditional polling: a fixed timer would hammer `/documents`
 * forever. Why pause on hidden tabs: BackgroundTasks still run on
 * the server; the UI does not need to wake a background browser tab.
 */
export function useKnowledgeDocuments(options: Options = {}) {
  const pollIntervalMs = options.pollIntervalMs ?? KNOWLEDGE_POLL_MS
  const [docs, setDocs] = useState<KnowledgeDocument[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const inFlightRef = useRef(false)
  const mountedRef = useRef(true)

  useEffect(() => {
    mountedRef.current = true
    return () => {
      mountedRef.current = false
    }
  }, [])

  const refresh = useCallback(async (): Promise<
    KnowledgeDocument[] | null
  > => {
    if (inFlightRef.current) return null
    inFlightRef.current = true
    try {
      const data = await apiJson<KnowledgeDocument[]>(
        '/knowledge/documents',
      )
      if (mountedRef.current) {
        setDocs(data)
        setError(null)
      }
      return data
    } catch (err) {
      if (mountedRef.current) {
        setError(
          err instanceof Error ? err.message : 'Failed to load documents',
        )
      }
      return null
    } finally {
      inFlightRef.current = false
      if (mountedRef.current) setLoading(false)
    }
  }, [])

  useEffect(() => {
    void refresh()
  }, [refresh])

  const pending = hasPendingIngest(docs)

  useEffect(() => {
    if (!pending) return

    const tick = () => {
      if (document.hidden) return
      void refresh()
    }

    const id = window.setInterval(tick, pollIntervalMs)
    const onVisibility = () => {
      if (!document.hidden) tick()
    }
    document.addEventListener('visibilitychange', onVisibility)

    return () => {
      window.clearInterval(id)
      document.removeEventListener(
        'visibilitychange',
        onVisibility,
      )
    }
  }, [pending, pollIntervalMs, refresh])

  return { docs, loading, error, refresh, pending }
}
