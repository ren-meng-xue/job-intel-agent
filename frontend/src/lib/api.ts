import { http } from './http'

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000/api/v1'

export async function createJob(url: string): Promise<{ id: string }> {
  const res = await http('/jobs', {
    method: 'POST',
    body: JSON.stringify({ url }),
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json() as Promise<{ id: string }>
}

export async function uploadResume(file: File): Promise<{ id: string }> {
  const form = new FormData()
  form.append('file', file)
  const res = await http('/resume', { method: 'POST', body: form })
  if (!res.ok) throw new Error(await res.text())
  return res.json() as Promise<{ id: string }>
}

// EventSource 不支持自定义 header，token 由后续 Phase 处理
export function streamReport(
  reportId: string,
  onEvent: (e: MessageEvent) => void
): EventSource {
  const es = new EventSource(`${BASE_URL}/reports/${reportId}/stream`)
  es.onmessage = onEvent
  return es
}
