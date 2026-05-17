export const metadata = {
  title: 'Job Intel Agent — 设计展示',
  description: '产品草稿与 UI 原型',
}

const designs = [
  {
    title: 'UI 原型',
    description: '完整的应用界面原型，含 JD 输入、Agent 调研进度、报告展示全流程交互。',
    href: '/designs/ui-prototype.html',
    tag: 'UI Prototype',
    color: 'from-blue-500 to-indigo-600',
  },
  {
    title: 'JD 输入模式草稿',
    description: 'JD 输入界面的早期设计草稿，探索用户录入职位描述的交互方式。',
    href: '/designs/jd-input-mode-draft.html',
    tag: 'Draft',
    color: 'from-violet-500 to-purple-600',
  },
  {
    title: 'Agent 执行流程',
    description: '.claude 执行指南可视化，展示 LangGraph 多步调研 Agent 的工作流与节点设计。',
    href: '/designs/claude-workflow.html',
    tag: 'Workflow',
    color: 'from-emerald-500 to-teal-600',
  },
]

export default function DesignPage() {
  return (
    <main className="min-h-screen bg-gray-950 text-white">
      {/* Header */}
      <div className="border-b border-gray-800 bg-gray-900/60 backdrop-blur">
        <div className="mx-auto max-w-5xl px-6 py-5 flex items-center justify-between">
          <div>
            <p className="text-xs text-gray-500 uppercase tracking-widest mb-1">Job Intel Agent</p>
            <h1 className="text-xl font-semibold">设计展示</h1>
          </div>
          <a
            href="/"
            className="text-sm text-gray-400 hover:text-white transition-colors flex items-center gap-1.5"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M10.5 19.5L3 12m0 0l7.5-7.5M3 12h18" />
            </svg>
            返回应用
          </a>
        </div>
      </div>

      {/* Cards */}
      <div className="mx-auto max-w-5xl px-6 py-12">
        <p className="text-gray-400 text-sm mb-10">
          共 {designs.length} 份设计文档 · 点击卡片在新标签页中打开
        </p>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
          {designs.map((d) => (
            <a
              key={d.href}
              href={d.href}
              target="_blank"
              rel="noopener noreferrer"
              className="group relative flex flex-col rounded-2xl border border-gray-800 bg-gray-900 overflow-hidden hover:border-gray-600 transition-all duration-200 hover:-translate-y-0.5 hover:shadow-xl hover:shadow-black/40"
            >
              {/* Color bar */}
              <div className={`h-1.5 w-full bg-gradient-to-r ${d.color}`} />

              <div className="flex flex-col gap-3 p-6 flex-1">
                <span className="self-start text-[11px] font-medium px-2.5 py-0.5 rounded-full bg-gray-800 text-gray-400 tracking-wide">
                  {d.tag}
                </span>
                <h2 className="text-base font-semibold text-white group-hover:text-blue-300 transition-colors">
                  {d.title}
                </h2>
                <p className="text-sm text-gray-400 leading-relaxed flex-1">
                  {d.description}
                </p>
              </div>

              {/* Footer */}
              <div className="px-6 py-4 border-t border-gray-800 flex items-center justify-between">
                <span className="text-xs text-gray-500">在新标签页中打开</span>
                <svg
                  className="w-4 h-4 text-gray-500 group-hover:text-blue-400 transition-colors"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                    d="M13.5 6H5.25A2.25 2.25 0 003 8.25v10.5A2.25 2.25 0 005.25 21h10.5A2.25 2.25 0 0018 18.75V10.5m-10.5 6L21 3m0 0h-5.25M21 3v5.25" />
                </svg>
              </div>
            </a>
          ))}
        </div>
      </div>
    </main>
  )
}
