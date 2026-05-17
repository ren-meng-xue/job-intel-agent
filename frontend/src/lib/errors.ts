import type { ErrorCode, ErrorResponseBody } from './types'

export class ApiError extends Error {
  code: ErrorCode
  status: number
  detail: Record<string, unknown> | null

  constructor(status: number, body: ErrorResponseBody) {
    super(body.message)
    this.name = 'ApiError'
    this.code = body.code
    this.status = status
    this.detail = body.detail ?? null
  }

  get isAuthError(): boolean {
    return this.code.startsWith('AUTH_')
  }

  get isNotFound(): boolean {
    return this.code === 'NOT_FOUND'
  }
}

export async function parseApiError(res: Response): Promise<ApiError> {
  let body: ErrorResponseBody = {
    code: 'INTERNAL_ERROR',
    message: `请求失败 (${res.status})`,
  }
  try {
    const json = await res.json()
    if (json.code && json.message) {
      body = json as ErrorResponseBody
    } else if (json.detail) {
      body.message = typeof json.detail === 'string' ? json.detail : JSON.stringify(json.detail)
    }
  } catch {
    // 无法解析 JSON 时使用默认 body
  }
  return new ApiError(res.status, body)
}
