import type { ResumeMatch } from '@/lib/types'

export default function ResumeMatchModule({ data }: { data: ResumeMatch }) {
  return (
    <div className="bg-white rounded-2xl border border-gray-200 p-6">
      <h2 className="text-base font-bold text-gray-900 mb-4 flex items-center gap-2">
        <span className="w-6 h-6 rounded-lg bg-green-100 text-green-600 flex items-center justify-center text-xs font-bold">
          2
        </span>
        简历匹配度分析
      </h2>
      <div className="grid grid-cols-2 gap-4">
        <div>
          <p className="text-xs font-semibold text-green-600 uppercase tracking-wide mb-2">
            ✅ 优势匹配
          </p>
          <ul className="space-y-2">
            {data.strengths.map((s, i) => (
              <li key={i} className="text-sm bg-green-50 rounded-lg px-3 py-2 text-gray-700">
                {s}
              </li>
            ))}
          </ul>
        </div>
        <div>
          <p className="text-xs font-semibold text-orange-500 uppercase tracking-wide mb-2">
            ⚠️ 待补强 Gap
          </p>
          <ul className="space-y-2">
            {data.gaps.map((g, i) => (
              <li key={i} className="text-sm bg-orange-50 rounded-lg px-3 py-2 text-gray-700">
                {g}
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  )
}
