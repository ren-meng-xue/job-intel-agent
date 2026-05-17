import type { PrepSuggestion } from '@/lib/types'

export default function PrepSuggestionsModule({ data }: { data: PrepSuggestion[] }) {
  return (
    <div className="bg-white rounded-2xl border border-gray-200 p-6">
      <h2 className="text-base font-bold text-gray-900 mb-3 flex items-center gap-2">
        <span className="w-6 h-6 rounded-lg bg-rose-100 text-rose-600 flex items-center justify-center text-xs font-bold">
          6
        </span>
        备战建议
      </h2>
      <ol className="space-y-2.5">
        {data.map((s, i) => (
          <li key={i} className="flex gap-3 text-sm text-gray-700">
            <span className="w-5 h-5 rounded-full bg-rose-100 text-rose-600 flex items-center justify-center text-xs flex-shrink-0 font-bold mt-0.5">
              {i + 1}
            </span>
            <span>
              <strong>{s.title}</strong> — {s.content}
            </span>
          </li>
        ))}
      </ol>
    </div>
  )
}
