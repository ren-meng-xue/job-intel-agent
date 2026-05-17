"use client";

interface Props {
  size?: "sm" | "md" | "lg";
  label?: string;
  subLabel?: string;
}

const SIZE_MAP = {
  sm: { core: "w-6 h-6", ring: "w-10 h-10", ringBorder: "border", text: "text-xs" },
  md: { core: "w-10 h-10", ring: "w-16 h-16", ringBorder: "border-2", text: "text-sm" },
  lg: { core: "w-14 h-14", ring: "w-24 h-24", ringBorder: "border-2", text: "text-sm" },
};

export default function AICoreLoader({ size = "md", label, subLabel }: Props) {
  const s = SIZE_MAP[size];

  return (
    <div className="flex flex-col items-center gap-3 py-4">
      <div className="relative flex items-center justify-center" style={{ width: s.ring, height: s.ring }}>
        {/* 外环轨道 */}
        <div
          className={`absolute inset-0 rounded-full ${s.ringBorder} border-blue-400/30 orbit-ring-1`}
          style={{
            borderStyle: "dashed",
            borderTopColor: "rgba(96,165,250,0.6)",
            borderRightColor: "rgba(129,140,248,0.3)",
          }}
        />
        {/* 内环轨道 */}
        <div
          className={`absolute rounded-full ${s.ringBorder} border-purple-400/25 orbit-ring-2`}
          style={{
            width: `calc(${s.ring} * 0.72)`,
            height: `calc(${s.ring} * 0.72)`,
            borderStyle: "dashed",
            borderBottomColor: "rgba(167,139,250,0.5)",
          }}
        />
        {/* 中央能量球 */}
        <div className={`${s.core} rounded-full neural-core bg-gradient-to-br from-blue-500 to-indigo-600 relative`}>
          {/* 能量波纹 */}
          <div className="energy-ripple" />
          <div className="energy-ripple" />
          {/* 高光 */}
          <div className="absolute top-1 left-1.5 w-2 h-2 rounded-full bg-white/60" style={{ filter: "blur(1px)" }} />
        </div>
      </div>

      {label && (
        <div className="text-center">
          <p className={`font-semibold text-gray-700 ${s.text}`}>{label}</p>
          {subLabel && (
            <p className="text-xs text-gray-400 mt-0.5">{subLabel}</p>
          )}
        </div>
      )}
    </div>
  );
}
