type StepState = 'locked' | 'active' | 'done'

interface Props {
  steps: string[]
  states: StepState[]
}

export default function StepProgress({ steps, states }: Props) {
  return (
    <div className="flex items-center gap-0 pb-2">
      {steps.map((label, i) => {
        const s = states[i]
        const circleClass =
          s === 'done'
            ? 'bg-green-500 border-green-500 text-white'
            : s === 'active'
            ? 'bg-blue-600 border-blue-600 text-white'
            : 'bg-white border-gray-300 text-gray-400'
        const labelClass =
          s === 'locked' ? 'text-gray-400' : 'text-gray-700 font-medium'
        return (
          <div key={i} className="flex items-center">
            <div className="flex flex-col items-center">
              <div
                className={`w-8 h-8 rounded-full border-2 flex items-center justify-center text-sm font-bold ${circleClass}`}
              >
                {s === 'done' ? '✓' : i + 1}
              </div>
              <span className={`text-xs mt-1.5 text-center w-16 ${labelClass}`}>
                {label}
              </span>
            </div>
            {i < steps.length - 1 && (
              <div
                className={`h-0.5 w-16 mb-5 ${
                  s === 'done' ? 'bg-green-400' : 'bg-gray-200'
                }`}
              />
            )}
          </div>
        )
      })}
    </div>
  )
}
