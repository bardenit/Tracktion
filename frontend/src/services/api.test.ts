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

  it('keeps queues isolated by authenticated user and quarantines legacy entries', async () => {
    localStorage.setItem('tracktion-offline-fuel', JSON.stringify([{ vehicleId: 1, payload: {}, queuedAt: 'old' }]))
    const { apiClient } = await import('./api')
    apiClient.setAuthenticatedUser(1)
    apiClient.queueFuelEntry(3, { partial_fillup: true, missed_fillup: true })
    apiClient.setAuthenticatedUser(2)

    expect(apiClient.getOfflineFuelQueue()).toEqual([])
    expect(localStorage.getItem('tracktion-offline-fuel:quarantine')).not.toBeNull()

    apiClient.setAuthenticatedUser(1)
    expect(apiClient.getOfflineFuelQueue()[0].payload).toMatchObject({ partial_fillup: true, missed_fillup: true })
  })

  it('retains retryable failures and keeps validation failures visible', async () => {
    const { apiClient } = await import('./api')
    apiClient.setAuthenticatedUser(1)
    apiClient.queueFuelEntry(3, { date: '2026-08-01', mileage: 10, gallons: 1, cost: 4 })
    apiClient.queueFuelEntry(3, { date: '2026-08-02', mileage: 20, gallons: 1, cost: 4 })
    axiosClient.post
      .mockRejectedValueOnce({ response: { status: 503 } })
      .mockRejectedValueOnce({ response: { status: 422, data: { detail: 'bad mileage' } } })

    const result = await apiClient.syncOfflineFuelEntries()

    expect(result).toEqual({ synced: 0, conflicts: 1, remaining: 2 })
    expect(apiClient.getOfflineFuelQueue().map((item) => item.status)).toEqual(['pending', 'conflict'])
    expect(apiClient.getOfflineFuelQueue()[1].conflictReason).toContain('bad mileage')
  })

  it('coalesces duplicate deletes while a request is pending', async () => {
    const { apiClient } = await import('./api')
    let resolve!: () => void
    const request = vi.fn(() => new Promise<void>((done) => { resolve = done }))
    const first = apiClient.deleteOnce('fuel:1', request)
    const second = apiClient.deleteOnce('fuel:1', request)
    expect(request).toHaveBeenCalledOnce()
    expect(second).toBe(first)
    resolve()
    await first
  })

  it('sends one typed batch request with the import operation id', async () => {
    axiosClient.post.mockResolvedValue({ data: { operation_id: 'id', imported_count: 1 } })
    const { apiClient } = await import('./api')
    await apiClient.importFuelEntries(7, 'id', [{ date: '2026-08-01', mileage: 1, gallons: 1, cost: 3, missed_fillup: false, partial_fillup: true }])
    expect(axiosClient.post).toHaveBeenCalledWith('/fuel/7/entries/bulk', expect.objectContaining({ operation_id: 'id' }))
  })
})
