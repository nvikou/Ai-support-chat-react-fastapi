import { Bot, Sparkles } from 'lucide-react'
import { Navigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

type Props = {
  children: React.ReactNode
}

export default function AuthLayout({ children }: Props) {
  const { user, loading } = useAuth()

  if (!loading && user) {
    return <Navigate to="/" replace />
  }

  return (
    <div className="min-h-screen grid lg:grid-cols-2">
      <div className="hidden lg:flex flex-col justify-between bg-gradient-to-br from-brand-600 via-brand-700 to-brand-900 text-white p-12">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-white/20 rounded-xl flex items-center justify-center backdrop-blur">
            <Bot className="w-5 h-5" />
          </div>
          <span className="font-bold text-xl">VateCon</span>
        </div>

        <div className="space-y-6">
          <div className="inline-flex items-center gap-2 bg-white/10 backdrop-blur px-4 py-2 rounded-full text-sm">
            <Sparkles className="w-4 h-4" />
            AI-powered customer support
          </div>
          <h2 className="text-4xl font-bold leading-tight">
            Your conversations,
            <br />
            always at hand.
          </h2>
          <p className="text-brand-100 text-lg max-w-md">
            Secure accounts, personal history, and intelligent assistance
            available 24/7.
          </p>
        </div>

        <p className="text-brand-200 text-sm">
          © {new Date().getFullYear()} VateCon AI Support
        </p>
      </div>

      <div className="flex items-center justify-center p-6 sm:p-12 bg-gray-50">
        <div className="w-full max-w-md">{children}</div>
      </div>
    </div>
  )
}
