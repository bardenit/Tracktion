import { beforeEach, describe, expect, it, vi } from 'vitest'

const requestUse = vi.fn()
const responseUse = vi.fn()
const refreshPost = vi.fn()
let createCount = 0
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
  default: { create: vi.fn(() => (++createCount % 2 === 1 ? axiosClient : { post: refreshPost })) },
}))

describe('apiClient test isolation', () => {
  beforeEach(() => {
    vi.resetModules()
    vi.clearAllMocks()
    createCount = 0
    refreshPost.mockResolvedValue({ data: {} })
  })

  it('uses one interceptor-free refresh for concurrent unauthorized requests', async () => {
    localStorage.setItem('accessToken', 'expired')
    localStorage.setItem('refreshToken', 'refresh')
    refreshPost.mockResolvedValue({ data: { access_token: 'new-access', refresh_token: 'new-refresh' } })
    axiosClient.mockResolvedValue({ data: 'ok' })
    await import('./api')
    const rejected = responseUse.mock.calls[0][1]
    const results = await Promise.all(Array.from({ length: 20 }, () => rejected({
      response: { status: 401 }, config: { headers: {} },
    })))

    expect(refreshPost).toHaveBeenCalledOnce()
    expect(results).toHaveLength(20)
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
