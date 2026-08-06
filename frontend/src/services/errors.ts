import axios from 'axios'

export class ApiError extends Error {
  constructor(message: string, public readonly status?: number) { super(message) }
  get notFound() { return this.status === 404 }
}

export function normalizeApiError(error: unknown): ApiError {
  if (error instanceof ApiError) return error
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail
    const message = typeof detail === 'string' ? detail : error.message || 'Request failed'
    return new ApiError(message, error.response?.status)
  }
  return new ApiError(error instanceof Error ? error.message : 'Request failed')
}
