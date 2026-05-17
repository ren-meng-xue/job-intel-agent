import type { CompanyProfile } from '@/lib/types'

export default function CompanyProfileModule({ data }: { data: CompanyProfile }) {
  return (
    <div className="bg-white rounded-2xl border border-gray-200 p-6">
      <h2 className="text-base font-bold text-gray-900 mb-3 flex items-center gap-2">
        <span className="w-6 h-6 rounded-lg bg-purple-100 text-purple-600 flex items-center justify-center text-xs font-bold">
          3
        </span>
        公司画像
      </h2>
      <p className="text-sm text-gray-600 leading-relaxed">{data.summary}</p>
      <div className="mt-3 flex flex-wrap gap-2">
        {data.tags.map((t, i) => (
          <span key={i} className="text-xs bg-purple-50 text-purple-600 px-2.5 py-1 rounded-full">
            {t}
          </span>
        ))}
      </div>
    </div>
  )
}
