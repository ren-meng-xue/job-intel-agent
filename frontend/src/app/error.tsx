'use client'

import { useEffect } from 'react'

export default function ErrorPage({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  useEffect(() => {
    console.error('Unhandled page error:', error)
  }, [error])

  return (
    <main className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="text-center max-w-md">
        <h1 className="text-4xl font-bold text-gray-200 mb-4">出错了</h1>
        <p className="text-gray-600 mb-2">页面遇到了未预期的错误</p>
        <p className="text-xs text-gray-400 mb-8 font-mono break-all">
          {error.message || '未知错误'}
        </p>
        <button
          onClick={reset}
          className="inline-block rounded-lg bg-blue-600 px-6 py-2.5 text-white font-medium hover:bg-blue-700 transition-colors"
        >
          重试
        </button>
      </div>
    </main>
  )
}
