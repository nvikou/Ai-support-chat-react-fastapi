import { act, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { AuthProvider, useAuth } from './AuthContext'
import type { User } from '../lib/api'

const { refreshAccessToken, apiJson, apiFetch, setAccessToken } = vi.hoisted(
  () => ({
    refreshAccessToken: vi.fn(),
    apiJson: vi.fn(),
    apiFetch: vi.fn(),
    setAccessToken: vi.fn(),
  }),
)

vi.mock('../lib/api', () => ({
  refreshAccessToken,
  apiJson,
  apiFetch,
  setAccessToken,
}))

const sampleUser: User = {
  id: 'u1',
  email: 'user@example.com',
  full_name: 'User',
  role: 'user',
}

function Probe() {
  const { user, loading, login, logout, isAdmin } = useAuth()
  return (
    <div>
      <span data-testid="loading">{String(loading)}</span>
      <span data-testid="email">{user?.email ?? 'none'}</span>
      <span data-testid="admin">{String(isAdmin)}</span>
      <button type="button" onClick={() => void login('a@b.c', 'secret')}>
        login
      </button>
      <button type="button" onClick={() => void logout()}>
        logout
      </button>
    </div>
  )
}

describe('AuthContext', () => {
  beforeEach(() => {
    refreshAccessToken.mockReset()
    apiJson.mockReset()
    apiFetch.mockReset()
    setAccessToken.mockReset()
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  it('bootstraps the session after a successful token refresh', async () => {
    refreshAccessToken.mockResolvedValue('fresh-token')
    apiJson.mockResolvedValue(sampleUser)

    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    )

    expect(screen.getByTestId('loading')).toHaveTextContent('true')

    await waitFor(() => {
      expect(screen.getByTestId('loading')).toHaveTextContent('false')
    })
    expect(screen.getByTestId('email')).toHaveTextContent('user@example.com')
    expect(refreshAccessToken).toHaveBeenCalledTimes(1)
    expect(apiJson).toHaveBeenCalledWith('/auth/me')
  })

  it('clears the user when the refresh token has expired', async () => {
    refreshAccessToken.mockResolvedValue(null)

    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    )

    await waitFor(() => {
      expect(screen.getByTestId('loading')).toHaveTextContent('false')
    })
    expect(screen.getByTestId('email')).toHaveTextContent('none')
    expect(apiJson).not.toHaveBeenCalled()
  })

  it('clears tokens when /auth/me fails after refresh', async () => {
    refreshAccessToken.mockResolvedValue('fresh-token')
    apiJson.mockRejectedValue(new Error('unauthorized'))

    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    )

    await waitFor(() => {
      expect(screen.getByTestId('loading')).toHaveTextContent('false')
    })
    expect(screen.getByTestId('email')).toHaveTextContent('none')
    expect(setAccessToken).toHaveBeenCalledWith(null)
  })

  it('stores the user after login', async () => {
    refreshAccessToken.mockResolvedValue(null)
    apiFetch.mockResolvedValue({
      ok: true,
      json: async () => ({
        access_token: 'login-token',
        user: sampleUser,
      }),
    })

    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    )

    await waitFor(() => {
      expect(screen.getByTestId('loading')).toHaveTextContent('false')
    })

    await act(async () => {
      screen.getByText('login').click()
    })

    await waitFor(() => {
      expect(screen.getByTestId('email')).toHaveTextContent('user@example.com')
    })
    expect(setAccessToken).toHaveBeenCalledWith('login-token')
  })

  it('clears the user after logout', async () => {
    refreshAccessToken.mockResolvedValue('fresh-token')
    apiJson.mockResolvedValue(sampleUser)
    apiFetch.mockResolvedValue({ ok: true, json: async () => ({}) })

    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    )

    await waitFor(() => {
      expect(screen.getByTestId('email')).toHaveTextContent('user@example.com')
    })

    await act(async () => {
      screen.getByText('logout').click()
    })

    await waitFor(() => {
      expect(screen.getByTestId('email')).toHaveTextContent('none')
    })
    expect(setAccessToken).toHaveBeenCalledWith(null)
  })
})
