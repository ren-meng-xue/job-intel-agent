import type { SalaryRange } from '@/lib/types'

function fmt(n: number) {
  return n >= 1000 ? `${(n / 1000).toFixed(0)}K` : `${n}`
}

export default function SalaryModule({ data }: { data: SalaryRange }) {
  const range = data.market_max - data.market_min || 1
  const medianPos = Math.min(90, Math.max(10, ((data.median - data.market_min) / range) * 100))
  const myPos = Math.min(85, Math.max(5, ((data.suggested_min - data.market_min) / range) * 100))

  return (
    <div className="bg-white rounded-2xl border border-gray-200 p-6">
      <h2 className="text-base font-bold text-gray-900 mb-4 flex items-center gap-2">
        <span className="w-6 h-6 rounded-lg bg-teal-100 text-teal-600 flex items-center justify-center text-xs font-bold">
          5
        </span>
        薪资参考区间
      </h2>
      {data.market_min === 0 && data.market_max === 0 ? (
        <p className="text-sm text-gray-400">暂无薪资数据</p>
      ) : (
        <>
          <div className="mb-2 flex justify-between text-xs text-gray-400">
            <span>{fmt(data.market_min)}</span>
            <span>{fmt(data.median)}</span>
            <span>{fmt(data.market_max)}+</span>
          </div>
          <div className="relative h-5 bg-gray-100 rounded-full overflow-hidden mb-1">
            <div className="absolute top-0 h-full bg-teal-100 rounded-full" style={{ left: '0%', width: '80%' }} />
            <div className="absolute top-0 h-full w-0.5 bg-teal-500" style={{ left: `${medianPos}%` }} />
            <div
              className="absolute top-1/2 -translate-y-1/2 w-4 h-4 rounded-full bg-blue-600 border-2 border-white shadow"
              style={{ left: `${myPos}%` }}
            />
          </div>
          <div className="mt-5 flex flex-wrap gap-4 text-sm text-gray-600">
            <div className="flex items-center gap-1.5">
              <span className="w-3 h-3 rounded-full bg-teal-400" />
              市场区间：{fmt(data.market_min)}–{fmt(data.market_max)} / 月
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-3 h-3 rounded-full bg-teal-600" />
              中位数：约 {fmt(data.median)}
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-3 h-3 rounded-full bg-blue-600" />
              建议报价：{fmt(data.suggested_min)}–{fmt(data.suggested_max)}
            </div>
          </div>
        </>
      )}
    </div>
  )
}
