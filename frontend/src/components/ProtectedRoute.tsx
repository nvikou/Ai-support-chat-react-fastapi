import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

type Props = {
  children: React.ReactNode
  role?: 'admin'
}

export default function ProtectedRoute({ children, role }: Props) {
  const { user, loading } = useAuth()
  const location = useLocation()

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="flex flex-col items-center gap-3">
          <div className="w-10 h-10 border-4 border-brand-600 border-t-transparent rounded-full animate-spin" />
          <p className="text-sm text-gray-500">Loading...</p>
        </div>
      </div>
    )
  }

  if (!user) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  if (role === 'admin' && user.role !== 'admin') {
    return <Navigate to="/" replace />
  }

  return <>{children}</>
}
