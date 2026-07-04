import { useEffect, useRef, useState } from 'react'
import { Upload, FileText, Plus, Trash2 } from 'lucide-react'
import { apiFetch, apiJson } from '../lib/api'

type Doc = { id: number; filename: string; chunk_count: number; uploaded_at: string }
type FAQEntry = { question: string; answer: string; category: string }

export default function KnowledgePage() {
  const [docs, setDocs] = useState<Doc[]>([])
  const [uploading, setUploading] = useState(false)
  const [faqEntries, setFaqEntries] = useState<FAQEntry[]>([{ question: '', answer: '', category: 'general' }])
  const [faqStatus, setFaqStatus] = useState('')
  const fileRef = useRef<HTMLInputElement>(null)

  const fetchDocs = async () => {
    const data = await apiJson<Doc[]>('/knowledge/documents')
    setDocs(data)
  }

  useEffect(() => { fetchDocs() }, [])

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setUploading(true)
    const form = new FormData()
    form.append('file', file)
    try {
      const res = await apiFetch('/knowledge/upload', { method: 'POST', body: form })
      if (res.ok) fetchDocs()
      else alert('Upload failed: ' + (await res.json()).detail)
    } finally {
      setUploading(false)
    }
  }

  const addFaqRow = () => setFaqEntries((p) => [...p, { question: '', answer: '', category: 'general' }])
  const removeFaqRow = (i: number) => setFaqEntries((p) => p.filter((_, idx) => idx !== i))
  const updateFaq = (i: number, field: keyof FAQEntry, value: string) => {
    setFaqEntries((p) => p.map((e, idx) => idx === i ? { ...e, [field]: value } : e))
  }

  const saveFaq = async () => {
    const valid = faqEntries.filter((e) => e.question && e.answer)
    if (!valid.length) return
    const res = await apiFetch('/knowledge/faq', {
      method: 'POST',
      body: JSON.stringify({ entries: valid }),
    })
    const data = await res.json()
    setFaqStatus(`✓ ${data.entries_added} FAQ entries added to knowledge base`)
    setFaqEntries([{ question: '', answer: '', category: 'general' }])
  }

  return (
    <div className="max-w-4xl mx-auto p-6 space-y-8">
      <h1 className="text-2xl font-bold text-gray-900">Knowledge Base</h1>

      {/* Upload documents */}
      <div className="card space-y-4">
        <h2 className="font-semibold text-gray-900">Upload Documents</h2>
        <p className="text-sm text-gray-500">Upload PDF, text or MD files. The AI will use them to answer customer questions.</p>
        <div
          onClick={() => fileRef.current?.click()}
          className="border-2 border-dashed border-gray-200 rounded-xl p-8 text-center cursor-pointer hover:border-brand-400 hover:bg-brand-50 transition-colors"
        >
          <Upload className="w-8 h-8 text-gray-400 mx-auto mb-2" />
          <p className="text-sm text-gray-500">{uploading ? 'Uploading...' : 'Click to upload PDF, TXT or MD file'}</p>
          <input ref={fileRef} type="file" accept=".pdf,.txt,.md" className="hidden" onChange={handleUpload} />
        </div>

        {docs.length > 0 && (
          <div className="space-y-2">
            {docs.map((doc) => (
              <div key={doc.id} className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg">
                <FileText className="w-4 h-4 text-brand-600 flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-gray-800 truncate">{doc.filename}</p>
                  <p className="text-xs text-gray-400">{doc.chunk_count} chunks · {new Date(doc.uploaded_at).toLocaleDateString()}</p>
                </div>
                <span className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded-full">Indexed</span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* FAQ Builder */}
      <div className="card space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="font-semibold text-gray-900">FAQ Builder</h2>
            <p className="text-sm text-gray-500">Add Q&A pairs directly to the knowledge base.</p>
          </div>
          <button onClick={addFaqRow} className="flex items-center gap-1.5 text-sm text-brand-600 hover:text-brand-700">
            <Plus className="w-4 h-4" /> Add row
          </button>
        </div>

        <div className="space-y-3">
          {faqEntries.map((entry, i) => (
            <div key={i} className="grid grid-cols-[1fr_1fr_auto_auto] gap-2 items-start">
              <input
                placeholder="Question"
                value={entry.question}
                onChange={(e) => updateFaq(i, 'question', e.target.value)}
                className="px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500"
              />
              <input
                placeholder="Answer"
                value={entry.answer}
                onChange={(e) => updateFaq(i, 'answer', e.target.value)}
                className="px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500"
              />
              <input
                placeholder="Category"
                value={entry.category}
                onChange={(e) => updateFaq(i, 'category', e.target.value)}
                className="px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500 w-28"
              />
              <button onClick={() => removeFaqRow(i)} className="p-2 text-gray-300 hover:text-red-400">
                <Trash2 className="w-4 h-4" />
              </button>
            </div>
          ))}
        </div>

        <div className="flex items-center gap-3">
          <button onClick={saveFaq} className="btn-primary">Save to Knowledge Base</button>
          {faqStatus && <span className="text-sm text-emerald-600">{faqStatus}</span>}
        </div>
      </div>
    </div>
  )
}
