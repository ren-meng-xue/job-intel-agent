'use client'
import { useState } from 'react'
import type { InterviewQA } from '@/lib/types'

export default function InterviewQAModule({ data }: { data: InterviewQA[] }) {
  const [open, setOpen] = useState<number | null>(null)
  return (
    <div className="bg-white rounded-2xl border border-gray-200 p-6">
      <h2 className="text-base font-bold text-gray-900 mb-3 flex items-center gap-2">
        <span className="w-6 h-6 rounded-lg bg-yellow-100 text-yellow-600 flex items-center justify-center text-xs font-bold">
          4
        </span>
        个性化面试题预测
      </h2>
      <div className="space-y-2">
        {data.map((qa, i) => (
          <div key={i} className="rounded-xl border border-gray-100 overflow-hidden">
            <button
              onClick={() => setOpen(open === i ? null : i)}
              className="w-full flex items-center gap-3 p-3.5 text-left hover:bg-gray-50 transition-colors"
            >
              <span className="w-5 h-5 rounded-full bg-yellow-100 text-yellow-700 flex items-center justify-center text-xs flex-shrink-0 font-bold">
                Q
              </span>
              <span className="text-sm text-gray-700 flex-1">{qa.question}</span>
              <span
                className={`text-gray-400 transition-transform ${open === i ? 'rotate-180' : ''}`}
              >
                ▾
              </span>
            </button>
            {open === i && (
              <div className="px-4 pb-4 pt-3 text-sm text-gray-500 bg-gray-50 border-t border-gray-100 leading-relaxed">
                💡 <strong className="text-gray-700">答题思路：</strong>
                {qa.tip}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
