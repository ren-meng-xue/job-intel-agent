"use client";

interface Props {
  label?: string;
  dotCount?: number;
}

export default function DotSequence({ label, dotCount = 4 }: Props) {
  return (
    <div className="flex items-center gap-2">
      <div className="dot-sequence">
        {Array.from({ length: dotCount }).map((_, i) => (
          <span key={i} />
        ))}
      </div>
      {label && <span className="text-xs text-gray-400">{label}</span>}
    </div>
  );
}
