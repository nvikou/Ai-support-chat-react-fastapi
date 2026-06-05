import { useEffect, useState } from 'react'
import { Users, Shield, UserCheck, UserX } from 'lucide-react'
import { apiFetch, apiJson } from '../lib/api'
import clsx from 'clsx'

type UserRow = {
  id: string
  email: string
  full_name: string | null
  role: string
  is_active: boolean
  conversation_count: number
  last_login_at: string | null
  created_at: string
}

export default function AdminUsersPage() {
  const [users, setUsers] = useState<UserRow[]>([])
  const [loading, setLoading] = useState(true)

  const fetchUsers = async () => {
    const data = await apiJson<UserRow[]>('/admin/users')
    setUsers(data)
    setLoading(false)
  }

  useEffect(() => {
    fetchUsers()
  }, [])

  const toggleActive = async (id: string) => {
    await apiFetch(`/admin/users/${id}/toggle-active`, { method: 'PATCH' })
    fetchUsers()
  }

  return (
    <div className="max-w-5xl mx-auto p-6 space-y-6">
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 bg-violet-100 rounded-xl flex items-center justify-center">
          <Users className="w-5 h-5 text-violet-600" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Users</h1>
          <p className="text-sm text-gray-500">
            Manage registered accounts
          </p>
        </div>
      </div>

      {loading ? (
        <div className="flex justify-center py-16">
          <div className="w-8 h-8 border-4 border-brand-600 border-t-transparent rounded-full animate-spin" />
        </div>
      ) : (
        <div className="card overflow-hidden p-0">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-100">
              <tr>
                <th className="text-left px-4 py-3 font-medium text-gray-600">
                  User
                </th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">
                  Role
                </th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">
                  Conversations
                </th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">
                  Last login
                </th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">
                  Status
                </th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {users.map((u) => (
                <tr key={u.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3">
                    <p className="font-medium text-gray-900">
                      {u.full_name || '—'}
                    </p>
                    <p className="text-xs text-gray-400">{u.email}</p>
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={clsx(
                        'inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full font-medium',
                        u.role === 'admin'
                          ? 'bg-violet-100 text-violet-700'
                          : 'bg-gray-100 text-gray-600',
                      )}
                    >
                      {u.role === 'admin' && (
                        <Shield className="w-3 h-3" />
                      )}
                      {u.role}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-gray-600">
                    {u.conversation_count}
                  </td>
                  <td className="px-4 py-3 text-gray-400 text-xs">
                    {u.last_login_at
                      ? new Date(u.last_login_at).toLocaleString()
                      : 'Never'}
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={clsx(
                        'text-xs px-2 py-0.5 rounded-full font-medium',
                        u.is_active
                          ? 'bg-emerald-100 text-emerald-700'
                          : 'bg-red-100 text-red-700',
                      )}
                    >
                      {u.is_active ? 'Active' : 'Disabled'}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    {u.role !== 'admin' && (
                      <button
                        onClick={() => toggleActive(u.id)}
                        className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-400 hover:text-gray-600"
                        title={u.is_active ? 'Disable user' : 'Enable user'}
                      >
                        {u.is_active ? (
                          <UserX className="w-4 h-4" />
                        ) : (
                          <UserCheck className="w-4 h-4" />
                        )}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
