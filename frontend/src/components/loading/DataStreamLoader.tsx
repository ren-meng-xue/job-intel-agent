"use client";

interface Props {
  label?: string;
  particleCount?: number;
}

export default function DataStreamLoader({ label, particleCount = 8 }: Props) {
  return (
    <div className="flex flex-col items-center gap-3 py-3">
      {/* 粒子流轨道 */}
      <div className="particle-track w-48 h-1 rounded-full bg-gray-100 relative overflow-hidden">
        <div className="absolute inset-0 rounded-full bg-gradient-to-r from-blue-100 via-blue-200 to-blue-100" />
        {Array.from({ length: particleCount }).map((_, i) => (
          <div
            key={i}
            className="particle"
            style={{
              top: "50%",
              left: "50%",
              marginTop: -2,
              marginLeft: -2,
              animationDelay: `${i * 0.22}s`,
            }}
          />
        ))}
      </div>

      {label && (
        <p className="text-sm text-gray-500 flex items-center gap-1">
          {label}
          <span className="cursor-blink" />
        </p>
      )}
    </div>
  );
}
