import { useRef, useState } from 'react'
import { Upload, FileText, Plus, Trash2, Loader2 } from 'lucide-react'
import { apiFetch } from '../lib/api'
import {
  KnowledgeDocument,
  useKnowledgeDocuments,
} from '../hooks/useKnowledgeDocuments'

type FAQEntry = { question: string; answer: string; category: string }

function statusLabel(status: string): string {
  if (status === 'pending') return 'Indexing…'
  if (status === 'failed') return 'Failed'
  return 'Indexed'
}

function statusClass(status: string): string {
  if (status === 'pending') {
    return 'bg-amber-100 text-amber-800'
  }
  if (status === 'failed') {
    return 'bg-red-100 text-red-700'
  }
  return 'bg-green-100 text-green-700'
}

function DocRow({ doc }: { doc: KnowledgeDocument }) {
  const meta =
    doc.status === 'pending'
      ? 'Queued for indexing'
      : doc.status === 'failed'
        ? (doc.error_message || 'Ingest failed')
        : `${doc.chunk_count} chunks · ${new Date(doc.uploaded_at).toLocaleDateString()}`

  return (
    <div className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg">
      <FileText className="w-4 h-4 text-brand-600 flex-shrink-0" />
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-gray-800 truncate">
          {doc.filename}
        </p>
        <p
          className={`text-xs truncate ${
            doc.status === 'failed' ? 'text-red-500' : 'text-gray-400'
          }`}
          title={doc.error_message || undefined}
        >
          {meta}
        </p>
      </div>
      <span
        className={`inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full ${statusClass(doc.status)}`}
      >
        {doc.status === 'pending' && (
          <Loader2 className="w-3 h-3 animate-spin" />
        )}
        {statusLabel(doc.status)}
      </span>
    </div>
  )
}

export default function KnowledgePage() {
  const { docs, loading, error, refresh, pending } =
    useKnowledgeDocuments()
  const [uploading, setUploading] = useState(false)
  const [uploadMessage, setUploadMessage] = useState('')
  const [faqEntries, setFaqEntries] = useState<FAQEntry[]>([
    { question: '', answer: '', category: 'general' },
  ])
  const [faqStatus, setFaqStatus] = useState('')
  const fileRef = useRef<HTMLInputElement>(null)

  const handleUpload = async (
    e: React.ChangeEvent<HTMLInputElement>,
  ) => {
    const file = e.target.files?.[0]
    if (!file) return
    setUploading(true)
    setUploadMessage('')
    const form = new FormData()
    form.append('file', file)
    try {
      const res = await apiFetch('/knowledge/upload', {
        method: 'POST',
        body: form,
      })
      const body = await res.json().catch(() => ({}))
      if (res.status === 202 || res.ok) {
        setUploadMessage(
          'Upload accepted — indexing in the background…',
        )
        await refresh()
      } else {
        const detail =
          typeof body.detail === 'string'
            ? body.detail
            : 'Upload failed'
        setUploadMessage(detail)
      }
    } catch {
      setUploadMessage('Upload failed — network error')
    } finally {
      setUploading(false)
      if (fileRef.current) fileRef.current.value = ''
    }
  }

  const addFaqRow = () =>
    setFaqEntries((p) => [
      ...p,
      { question: '', answer: '', category: 'general' },
    ])
  const removeFaqRow = (i: number) =>
    setFaqEntries((p) => p.filter((_, idx) => idx !== i))
  const updateFaq = (
    i: number,
    field: keyof FAQEntry,
    value: string,
  ) => {
    setFaqEntries((p) =>
      p.map((e, idx) => (idx === i ? { ...e, [field]: value } : e)),
    )
  }

  const saveFaq = async () => {
    const valid = faqEntries.filter((e) => e.question && e.answer)
    if (!valid.length) return
    const res = await apiFetch('/knowledge/faq', {
      method: 'POST',
      body: JSON.stringify({ entries: valid }),
    })
    const data = await res.json().catch(() => ({}))
    if (res.status === 202 || res.ok) {
      setFaqStatus(
        'FAQ accepted — indexing in the background…',
      )
      setFaqEntries([
        { question: '', answer: '', category: 'general' },
      ])
      await refresh()
    } else {
      const detail =
        typeof data.detail === 'string'
          ? data.detail
          : 'FAQ save failed'
      setFaqStatus(detail)
    }
  }

  return (
    <div className="max-w-4xl mx-auto p-6 space-y-8">
      <h1 className="text-2xl font-bold text-gray-900">Knowledge Base</h1>

      <div className="card space-y-4">
        <h2 className="font-semibold text-gray-900">Upload Documents</h2>
        <p className="text-sm text-gray-500">
          Upload PDF, text or MD files. Ingest runs in the background;
          this page refreshes every 2s while indexing is pending.
        </p>
        <div
          onClick={() => fileRef.current?.click()}
          className="border-2 border-dashed border-gray-200 rounded-xl p-8 text-center cursor-pointer hover:border-brand-400 hover:bg-brand-50 transition-colors"
        >
          <Upload className="w-8 h-8 text-gray-400 mx-auto mb-2" />
          <p className="text-sm text-gray-500">
            {uploading
              ? 'Uploading…'
              : 'Click to upload PDF, TXT or MD file'}
          </p>
          <input
            ref={fileRef}
            type="file"
            accept=".pdf,.txt,.md"
            className="hidden"
            onChange={handleUpload}
          />
        </div>

        {uploadMessage && (
          <p className="text-sm text-brand-700">{uploadMessage}</p>
        )}
        {error && (
          <p className="text-sm text-red-600">{error}</p>
        )}
        {pending && (
          <p className="text-xs text-amber-700 flex items-center gap-1.5">
            <Loader2 className="w-3 h-3 animate-spin" />
            Indexing in progress — status updates automatically
          </p>
        )}

        {loading && docs.length === 0 ? (
          <p className="text-sm text-gray-400">Loading documents…</p>
        ) : docs.length > 0 ? (
          <div className="space-y-2">
            {docs.map((doc) => (
              <DocRow key={doc.id} doc={doc} />
            ))}
          </div>
        ) : (
          <p className="text-sm text-gray-400">No documents yet.</p>
        )}
      </div>

      <div className="card space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="font-semibold text-gray-900">FAQ Builder</h2>
            <p className="text-sm text-gray-500">
              Add Q&A pairs directly to the knowledge base.
            </p>
          </div>
          <button
            onClick={addFaqRow}
            className="flex items-center gap-1.5 text-sm text-brand-600 hover:text-brand-700"
          >
            <Plus className="w-4 h-4" /> Add row
          </button>
        </div>

        <div className="space-y-3">
          {faqEntries.map((entry, i) => (
            <div
              key={i}
              className="grid grid-cols-[1fr_1fr_auto_auto] gap-2 items-start"
            >
              <input
                placeholder="Question"
                value={entry.question}
                onChange={(e) =>
                  updateFaq(i, 'question', e.target.value)
                }
                className="px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500"
              />
              <input
                placeholder="Answer"
                value={entry.answer}
                onChange={(e) =>
                  updateFaq(i, 'answer', e.target.value)
                }
                className="px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500"
              />
              <input
                placeholder="Category"
                value={entry.category}
                onChange={(e) =>
                  updateFaq(i, 'category', e.target.value)
                }
                className="px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500 w-28"
              />
              <button
                onClick={() => removeFaqRow(i)}
                className="p-2 text-gray-300 hover:text-red-400"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            </div>
          ))}
        </div>

        <div className="flex items-center gap-3">
          <button onClick={saveFaq} className="btn-primary">
            Save to Knowledge Base
          </button>
          {faqStatus && (
            <span className="text-sm text-emerald-600">{faqStatus}</span>
          )}
        </div>
      </div>
    </div>
  )
}
