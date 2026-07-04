import { LogOut, Shield } from 'lucide-react'
import { useAuth } from '../context/AuthContext'

export default function UserMenu() {
  const { user, logout, isAdmin } = useAuth()

  if (!user) return null

  const initials = (user.full_name || user.email)
    .split(' ')
    .map((w) => w[0])
    .join('')
    .slice(0, 2)
    .toUpperCase()

  return (
    <div className="flex items-center gap-3">
      {isAdmin && (
        <span className="hidden sm:inline-flex items-center gap-1 text-xs font-medium bg-violet-100 text-violet-700 px-2.5 py-1 rounded-full">
          <Shield className="w-3 h-3" />
          Admin
        </span>
      )}
      <div className="flex items-center gap-2 pl-3 border-l border-gray-200">
        <div className="w-8 h-8 rounded-full bg-brand-600 text-white text-xs font-bold flex items-center justify-center">
          {initials}
        </div>
        <div className="hidden sm:block">
          <p className="text-sm font-medium text-gray-900 leading-none">
            {user.full_name || user.email.split('@')[0]}
          </p>
          <p className="text-xs text-gray-400 mt-0.5">{user.email}</p>
        </div>
        <button
          onClick={() => logout()}
          className="p-2 rounded-lg text-gray-400 hover:text-red-500 hover:bg-red-50 transition-colors"
          title="Sign out"
        >
          <LogOut className="w-4 h-4" />
        </button>
      </div>
    </div>
  )
}
