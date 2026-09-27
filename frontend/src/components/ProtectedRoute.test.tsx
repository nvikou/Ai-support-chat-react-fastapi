import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import ProtectedRoute from './ProtectedRoute'
import type { User } from '../lib/api'

const useAuth = vi.fn()

vi.mock('../context/AuthContext', () => ({
  useAuth: () => useAuth(),
}))

function renderWithAuth(
  auth: { user: User | null; loading: boolean },
  role?: 'admin',
) {
  useAuth.mockReturnValue(auth)
  return render(
    <MemoryRouter initialEntries={['/secret']}>
      <Routes>
        <Route
          path="/secret"
          element={
            <ProtectedRoute role={role}>
              <div>Secret content</div>
            </ProtectedRoute>
          }
        />
        <Route path="/login" element={<div>Login page</div>} />
        <Route path="/" element={<div>Home page</div>} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('ProtectedRoute', () => {
  it('shows a loading state while auth is unresolved', () => {
    renderWithAuth({ user: null, loading: true })
    expect(screen.getByText('Loading...')).toBeInTheDocument()
  })

  it('redirects anonymous users to login', () => {
    renderWithAuth({ user: null, loading: false })
    expect(screen.getByText('Login page')).toBeInTheDocument()
    expect(screen.queryByText('Secret content')).not.toBeInTheDocument()
  })

  it('renders children for authenticated users', () => {
    renderWithAuth({
      user: {
        id: 'u1',
        email: 'u@example.com',
        full_name: null,
        role: 'user',
      },
      loading: false,
    })
    expect(screen.getByText('Secret content')).toBeInTheDocument()
  })

  it('redirects non-admins away from admin routes', () => {
    renderWithAuth(
      {
        user: {
          id: 'u1',
          email: 'u@example.com',
          full_name: null,
          role: 'user',
        },
        loading: false,
      },
      'admin',
    )
    expect(screen.getByText('Home page')).toBeInTheDocument()
    expect(screen.queryByText('Secret content')).not.toBeInTheDocument()
  })

  it('allows admins on admin routes', () => {
    renderWithAuth(
      {
        user: {
          id: 'a1',
          email: 'admin@example.com',
          full_name: 'Admin',
          role: 'admin',
        },
        loading: false,
      },
      'admin',
    )
    expect(screen.getByText('Secret content')).toBeInTheDocument()
  })
})
