"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

interface Props {
  jobId: string;
  onClose: () => void;
}

export default function HumanInLoopDialog({ jobId, onClose }: Props) {
  const router = useRouter();
  const [confirmed, setConfirmed] = useState(false);

  function handleConfirm() {
    setConfirmed(true);
    onClose();
    router.push(`/report/${jobId}`);
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="w-full max-w-md rounded-2xl bg-white p-8 shadow-xl">
        <h2 className="mb-4 text-xl font-bold">确认职位信息</h2>
        <p className="mb-6 text-gray-500">
          AI 已解析 JD，请确认职位名称和公司名称无误后开始调研。
        </p>
        {/*
         * TODO: 展示 API 返回的职位名 / 公司名 / 核心要求供用户确认
         * ⚠️ 风险：Human-in-the-Loop 节点一，不可跳过（产品核心价值）
         */}
        <div className="flex gap-3">
          <button
            onClick={onClose}
            className="flex-1 rounded-lg border border-gray-300 py-2 text-gray-700 hover:bg-gray-50"
          >
            取消
          </button>
          <button
            onClick={handleConfirm}
            disabled={confirmed}
            className="flex-1 rounded-lg bg-blue-600 py-2 text-white font-semibold hover:bg-blue-700 disabled:opacity-50"
          >
            确认，开始调研
          </button>
        </div>
      </div>
    </div>
  );
}
