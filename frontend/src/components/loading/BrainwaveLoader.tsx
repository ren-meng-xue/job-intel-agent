"use client";

interface Props {
  label?: string;
  barCount?: number;
}

export default function BrainwaveLoader({ label, barCount = 7 }: Props) {
  return (
    <div className="flex flex-col items-center gap-3 py-2">
      <div className="flex items-end gap-[2px] h-8">
        {Array.from({ length: barCount }).map((_, i) => (
          <div
            key={i}
            className="brainwave-bar"
            style={{
              width: 3,
              height: `${12 + Math.sin((i / barCount) * Math.PI) * 16}px`,
              animationDelay: `${i * 0.1}s`,
            }}
          />
        ))}
      </div>
      {label && (
        <p className="text-xs text-gray-400 flex items-center gap-1">
          {label}
          <span className="cursor-blink" />
        </p>
      )}
    </div>
  );
}
