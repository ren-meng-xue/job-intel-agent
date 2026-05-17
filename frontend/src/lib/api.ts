import { ApiError, parseApiError } from './errors'
import { getAccessToken, clearSession } from './session'
import { http } from './http'
import type { ReportResponse } from './types'

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8001/api/v1'

async function checkOk(res: Response): Promise<Response> {
  if (!res.ok) throw await parseApiError(res)
  return res
}

export async function createJob(url: string, resumeId?: string): Promise<{ id: string }> {
  const res = await checkOk(
    await http('/jobs/', { method: 'POST', body: JSON.stringify({ url, resume_id: resumeId ?? null }) })
  )
  return res.json() as Promise<{ id: string }>
}

export async function uploadResume(file: File): Promise<{ id: string }> {
  const form = new FormData()
  form.append('file', file)
  const res = await checkOk(await http('/resume/', { method: 'POST', body: form }))
  return res.json() as Promise<{ id: string }>
}

export async function getResume(): Promise<{ id: string; status: string }> {
  const res = await checkOk(await http('/resume/'))
  return res.json() as Promise<{ id: string; status: string }>
}

export async function createJobFromText(rawContent: string, resumeId?: string): Promise<{ id: string }> {
  const res = await checkOk(
    await http('/jobs/from-text', {
      method: 'POST',
      body: JSON.stringify({ raw_content: rawContent, resume_id: resumeId ?? null }),
    })
  )
  return res.json() as Promise<{ id: string }>
}

export async function createJobFromImages(images: File[], resumeId?: string): Promise<{ id: string }> {
  const form = new FormData()
  for (const img of images) form.append('images', img)
  if (resumeId) form.append('resume_id', resumeId)
  const res = await checkOk(await http('/jobs/from-images', { method: 'POST', body: form }))
  return res.json() as Promise<{ id: string }>
}

export async function submitRawContent(jobId: string, rawContent: string): Promise<void> {
  await checkOk(
    await http(`/jobs/${jobId}/raw-content`, {
      method: 'POST',
      body: JSON.stringify({ raw_content: rawContent }),
    })
  )
}

export async function confirmJob(
  jobId: string,
  data: { title: string; company: string; requirements: string[] }
): Promise<void> {
  await checkOk(
    await http(`/jobs/${jobId}/confirm`, {
      method: 'POST',
      body: JSON.stringify(data),
    })
  )
}

export async function startResearch(
  jobId: string,
  selectedDirections: string[]
): Promise<void> {
  await checkOk(
    await http(`/jobs/${jobId}/start`, {
      method: 'POST',
      body: JSON.stringify({ selected_directions: selectedDirections }),
    })
  )
}

export function streamReport(
  reportId: string,
  onEvent: (e: MessageEvent) => void,
  onError?: (error: ApiError) => void
): EventSource {
  const token = getAccessToken()
  const url = new URL(`${BASE_URL}/reports/${reportId}/stream`)
  if (token) url.searchParams.set('token', token)

  const es = new EventSource(url.toString())
  es.onmessage = onEvent
  es.onerror = () => {
    // readyState: 0=CONNECTING(网络不通), 2=CLOSED(服务端正常关闭或拒绝)
    es.close()
    if (onError) {
      onError(new ApiError(0, {
        code: 'INTERNAL_ERROR',
        message: es.readyState === EventSource.CONNECTING
          ? 'SSE 连接失败，请检查网络'
          : '服务端连接中断，可能报告不存在或已过期',
      }))
    }
  }
  return es
}

export async function fetchReport(reportId: string): Promise<ReportResponse> {
  const res = await checkOk(await http(`/reports/${reportId}`))
  return res.json()
}

export async function getJob(jobId: string): Promise<{
  id: string
  title?: string
  company?: string
  requirements?: string[]
  suggested_directions?: string[]
  status: string
}> {
  const res = await checkOk(await http(`/jobs/${jobId}`))
  return res.json()
}

export async function resumeJob(
  jobId: string,
  action: 'approve' | 'retry',
  feedback?: string
): Promise<void> {
  await checkOk(
    await http(`/jobs/${jobId}/resume`, {
      method: 'POST',
      body: JSON.stringify({ action, feedback: feedback ?? null, edits: null }),
    })
  )
}
