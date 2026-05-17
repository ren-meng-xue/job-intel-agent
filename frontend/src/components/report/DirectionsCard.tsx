"use client";
import { useState } from "react";
import { AICoreLoader } from "../loading";

const DEFAULT_DIRECTIONS = [
  { id: "公司近期动态", desc: "融资、新产品、组织变动" },
  { id: "技术栈市场评价", desc: "技术热度与前景" },
  { id: "薪资参考区间", desc: "同级别行业对比" },
  { id: "简历匹配度分析", desc: "针对你的背景个性化" },
  { id: "面试风格&题型", desc: "来自社区公开信息" },
  { id: "备战建议", desc: "针对 Gap 的具体方案" },
];

interface Props {
  suggested?: string[];
  onStart: (selected: string[]) => Promise<void>;
}

export default function DirectionsCard({ suggested, onStart }: Props) {
  const dirs = suggested?.length
    ? suggested.map((s) => ({ id: s, desc: "" }))
    : DEFAULT_DIRECTIONS;

  const [selected, setSelected] = useState<Set<string>>(
    new Set(dirs.map((d) => d.id))
  );
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  function toggle(id: string) {
    const next = new Set(selected);
    if (next.has(id)) {
      if (next.size <= 1) return;
      next.delete(id);
    } else {
      next.add(id);
    }
    setSelected(next);
  }

  async function handleStart() {
    setLoading(true);
    setError("");
    try {
      await onStart(Array.from(selected));
    } catch (err) {
      setError(err instanceof Error ? err.message : "启动调研失败，请稍后重试");
      setLoading(false);
    }
  }

  if (loading) {
    return (
      <div className="py-4">
        <AICoreLoader
          size="md"
          label="AI 正在启动调研引擎..."
          subLabel={`已选择 ${selected.size} 个方向，正在初始化搜索任务`}
        />
      </div>
    );
  }

  return (
    <div>
      <p className="text-xs text-gray-400 mb-4">默认全选，去掉不感兴趣的方向</p>
      <div className="grid grid-cols-2 gap-2.5 mb-4">
        {dirs.map((d) => {
          const on = selected.has(d.id);
          return (
            <div
              key={d.id}
              onClick={() => toggle(d.id)}
              className={`rounded-xl border-2 p-3.5 cursor-pointer transition-all select-none ${
                on
                  ? "border-blue-400 bg-blue-50 shadow-sm shadow-blue-100"
                  : "border-gray-200 bg-white hover:border-gray-300"
              }`}
            >
              <div className="flex items-center gap-2 mb-0.5">
                <div
                  className={`w-4 h-4 rounded flex items-center justify-center text-xs ${
                    on ? "bg-blue-600 text-white" : "border border-gray-300"
                  }`}
                >
                  {on ? "✓" : ""}
                </div>
                <span className="text-sm font-medium text-gray-800">{d.id}</span>
              </div>
              {d.desc && (
                <p className="text-xs text-gray-400 ml-6">{d.desc}</p>
              )}
            </div>
          );
        })}
      </div>
      {error && (
        <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600 mb-3">{error}</p>
      )}
      <button
        type="button"
        onClick={handleStart}
        disabled={loading}
        className="w-full rounded-xl bg-gradient-to-r from-blue-600 to-indigo-600 py-3 text-sm text-white font-semibold hover:from-blue-700 hover:to-indigo-700 transition-all shadow-md shadow-blue-200 disabled:opacity-50"
      >
        开始调研（已选 {selected.size} 个方向）
      </button>
    </div>
  );
}
