"use client";

import { useEffect, useState } from "react";
import type { Report } from "@/lib/types";

interface Props {
  reportId: string;
}

const MODULES = [
  { key: "jobAnalysis", label: "职位解读" },
  { key: "resumeMatch", label: "简历匹配度" },
  { key: "companyProfile", label: "公司画像" },
  { key: "interviewQuestions", label: "面试题预测" },
  { key: "salaryRange", label: "薪资参考" },
  { key: "prepAdvice", label: "备战建议" },
] as const;

export default function ReportCard({ reportId }: Props) {
  const [report, setReport] = useState<Report | null>(null);

  useEffect(() => {
    // TODO: 轮询或监听 ProgressStream done 事件后 GET /reports/:id ⚠️ 风险：状态同步需与 SSE 事件对齐
    void reportId;
  }, [reportId]);

  if (!report?.content) return null;

  return (
    <div className="space-y-6">
      {MODULES.map(({ key, label }) => (
        <section key={key} className="rounded-xl border border-gray-200 p-6">
          <h2 className="mb-3 text-lg font-semibold text-gray-800">{label}</h2>
          <div className="text-gray-700 whitespace-pre-wrap">
            {Array.isArray(report.content![key])
              ? (report.content![key] as string[]).join("\n")
              : String(report.content![key])}
          </div>
        </section>
      ))}
    </div>
  );
}
