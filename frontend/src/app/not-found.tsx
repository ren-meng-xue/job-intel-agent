import Link from 'next/link'

export default function NotFound() {
  return (
    <main className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="text-center">
        <h1 className="text-6xl font-bold text-gray-200 mb-4">404</h1>
        <p className="text-lg text-gray-600 mb-2">页面未找到</p>
        <p className="text-sm text-gray-400 mb-8">你访问的路径不存在，请检查 URL 是否正确</p>
        <Link
          href="/"
          className="inline-block rounded-lg bg-blue-600 px-6 py-2.5 text-white font-medium hover:bg-blue-700 transition-colors"
        >
          返回首页
        </Link>
      </div>
    </main>
  )
}
