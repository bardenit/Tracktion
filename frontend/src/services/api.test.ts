import { beforeEach, describe, expect, it, vi } from 'vitest'

const requestUse = vi.fn()
const responseUse = vi.fn()
const axiosClient = Object.assign(vi.fn(), {
  delete: vi.fn(),
  get: vi.fn(),
  interceptors: {
    request: { use: requestUse },
    response: { use: responseUse },
  },
  post: vi.fn(),
  put: vi.fn(),
})

vi.mock('axios', () => ({
  default: { create: () => axiosClient },
}))

describe('apiClient test isolation', () => {
  beforeEach(() => {
    vi.resetModules()
  })

  it('clears authentication tokens and invokes logout notification', async () => {
    localStorage.setItem('accessToken', 'access')
    localStorage.setItem('refreshToken', 'refresh')
    const { apiClient } = await import('./api')
    const onLogout = vi.fn()
    apiClient.setOnLogout(onLogout)

    apiClient.logout()

    expect(localStorage.getItem('accessToken')).toBeNull()
    expect(localStorage.getItem('refreshToken')).toBeNull()
    expect(onLogout).toHaveBeenCalledOnce()
  })
})
