import type { JobInterpretation } from '@/lib/types'

export default function JobInterpretationModule({ data }: { data: JobInterpretation }) {
  return (
    <div className="bg-white rounded-2xl border border-gray-200 p-6">
      <h2 className="text-base font-bold text-gray-900 mb-3 flex items-center gap-2">
        <span className="w-6 h-6 rounded-lg bg-blue-100 text-blue-600 flex items-center justify-center text-xs font-bold">
          1
        </span>
        职位解读
      </h2>
      <div className="flex flex-wrap gap-2 mb-3">
        {data.hard_requirements.map((r, i) => (
          <span
            key={i}
            className="text-xs px-2.5 py-1 rounded-full bg-red-50 text-red-600 border border-red-200"
          >
            {r}
          </span>
        ))}
        {data.soft_requirements.map((r, i) => (
          <span
            key={i}
            className="text-xs px-2.5 py-1 rounded-full bg-yellow-50 text-yellow-700 border border-yellow-200"
          >
            {r}
          </span>
        ))}
        {data.hidden_bonuses.map((r, i) => (
          <span
            key={i}
            className="text-xs px-2.5 py-1 rounded-full bg-gray-100 text-gray-500 border border-gray-200"
          >
            {r}
          </span>
        ))}
      </div>
      <div className="flex gap-3 text-xs mb-3">
        <span className="inline-flex items-center gap-1">
          <span className="w-3 h-3 rounded bg-red-100 border border-red-300 inline-block" />
          硬性要求
        </span>
        <span className="inline-flex items-center gap-1">
          <span className="w-3 h-3 rounded bg-yellow-100 border border-yellow-300 inline-block" />
          软性偏好
        </span>
        <span className="inline-flex items-center gap-1">
          <span className="w-3 h-3 rounded bg-gray-100 border border-gray-300 inline-block" />
          隐性加分项
        </span>
      </div>
      <p className="text-sm text-gray-600 bg-gray-50 rounded-lg p-3 leading-relaxed">
        {data.summary}
      </p>
    </div>
  )
}
