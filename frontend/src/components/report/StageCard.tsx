interface Props {
  state: 'locked' | 'active' | 'done'
  step: number
  title: string
  subtitle?: string
  badge?: string
  children?: React.ReactNode
}

export default function StageCard({
  state,
  step,
  title,
  subtitle,
  badge,
  children,
}: Props) {
  if (state === 'locked') {
    return (
      <div className="bg-gray-50 rounded-2xl border border-gray-200 p-5 opacity-50">
        <div className="flex items-center gap-3">
          <div className="w-6 h-6 rounded-full bg-gray-200 flex items-center justify-center text-gray-400 text-xs">
            🔒
          </div>
          <p className="text-gray-400 font-medium">{title}</p>
        </div>
      </div>
    )
  }
  if (state === 'done') {
    return (
      <div className="bg-green-50 rounded-2xl border border-green-200 p-4">
        <div className="flex items-center gap-3">
          <div className="w-7 h-7 rounded-full bg-green-500 flex items-center justify-center text-white text-sm">
            ✓
          </div>
          <div>
            <p className="font-semibold text-green-700 text-sm">{title}</p>
            {subtitle && (
              <p className="text-xs text-green-500">{subtitle}</p>
            )}
          </div>
        </div>
      </div>
    )
  }
  // active
  return (
    <div className="bg-white rounded-2xl border-2 border-blue-400 p-5 shadow-md animate-unlock">
      <div className="flex items-center gap-3 mb-4">
        <div className="w-7 h-7 rounded-full bg-blue-600 flex items-center justify-center text-white text-sm font-bold">
          {step}
        </div>
        <p className="font-semibold text-gray-800">{title}</p>
        {badge && (
          <span className="ml-auto text-xs bg-blue-100 text-blue-600 px-2 py-0.5 rounded-full">
            {badge}
          </span>
        )}
      </div>
      {children}
    </div>
  )
}
