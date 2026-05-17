"use client";
import { useState } from "react";
import { AICoreLoader } from "../loading";

interface JDData {
  title: string;
  company: string;
  requirements: string[];
}

interface Props {
  initial: JDData;
  onConfirm: (data: JDData) => Promise<void>;
  onCancel: () => void;
}

export default function JDConfirmCard({ initial, onConfirm, onCancel }: Props) {
  const [title, setTitle] = useState(initial.title);
  const [company, setCompany] = useState(initial.company);
  const [reqs, setReqs] = useState<string[]>(initial.requirements);
  const [tagInput, setTagInput] = useState("");
  const [loading, setLoading] = useState(false);

  function addTag(val: string) {
    const v = val.trim();
    if (v && !reqs.includes(v)) setReqs([...reqs, v]);
  }

  async function handleConfirm() {
    setLoading(true);
    try {
      await onConfirm({ title, company, requirements: reqs });
    } finally {
      setLoading(false);
    }
  }

  if (loading) {
    return (
      <div className="py-6">
        <AICoreLoader
          size="md"
          label="AI 正在分析职位方向..."
          subLabel="根据 JD 信息生成调研建议"
        />
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div>
        <label className="text-xs text-gray-500 font-medium mb-1 block">
          职位名称
        </label>
        <input
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm text-gray-800 focus:outline-none focus:ring-2 focus:ring-blue-400"
        />
      </div>
      <div>
        <label className="text-xs text-gray-500 font-medium mb-1 block">
          公司名称
        </label>
        <input
          value={company}
          onChange={(e) => setCompany(e.target.value)}
          className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm text-gray-800 focus:outline-none focus:ring-2 focus:ring-blue-400"
        />
      </div>
      <div>
        <label className="text-xs text-gray-500 font-medium mb-1 block">
          核心要求
          <span className="text-gray-400 font-normal ml-1">
            （点击标签可删除，回车添加）
          </span>
        </label>
        <div className="flex flex-wrap gap-2 p-2 border border-gray-200 rounded-lg min-h-[44px] focus-within:ring-2 focus-within:ring-blue-400">
          {reqs.map((r, i) => (
            <span
              key={i}
              onClick={() => setReqs(reqs.filter((_, j) => j !== i))}
              className="inline-flex items-center gap-1 bg-blue-50 text-blue-700 text-xs px-2.5 py-1 rounded-full cursor-pointer hover:bg-red-50 hover:text-red-600 transition-colors"
            >
              {r} <span>×</span>
            </span>
          ))}
          <input
            value={tagInput}
            onChange={(e) => setTagInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                addTag(tagInput);
                setTagInput("");
              }
            }}
            placeholder="回车添加…"
            className="text-xs outline-none flex-1 min-w-[80px] px-1"
          />
        </div>
      </div>
      <div className="flex gap-3 mt-4">
        <button
          type="button"
          onClick={onCancel}
          className="flex-1 rounded-lg border border-gray-300 py-2.5 text-sm text-gray-600 hover:bg-gray-50 transition-colors"
        >
          取消
        </button>
        <button
          type="button"
          onClick={handleConfirm}
          className="flex-1 rounded-lg bg-blue-600 py-2.5 text-sm text-white font-semibold hover:bg-blue-700 transition-colors"
        >
          确认，开始调研 →
        </button>
      </div>
    </div>
  );
}
