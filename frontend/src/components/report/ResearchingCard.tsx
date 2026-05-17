"use client";
import { useEffect, useState, useRef } from "react";
import { streamReport, resumeJob } from "@/lib/api";
import MarkdownPreview from "../MarkdownPreview";
import { BrainwaveLoader } from "../loading";

interface DraftSection {
  heading: string;
  content: string;
}

interface PhaseState {
  key: string;
  label: string;
  status: "pending" | "running" | "done";
}

interface InterruptData {
  node: string;
  data: {
    draft_sections?: DraftSection[];
    research_analysis?: string;
  };
}

const PHASE_DEFS: { key: string; label: string; message: string }[] = [
  { key: "search", label: "搜索情报", message: "正在搜索公司背景、技术栈与市场情报..." },
  { key: "analyze", label: "分析结果", message: "正在结合 JD 与简历进行深度分析..." },
  { key: "generate_report", label: "生成报告", message: "正在起草面试情报报告各章节..." },
];

interface Props {
  reportId: string;
  directions: string[];
  onDone: () => void;
}

export default function ResearchingCard({ reportId, directions, onDone }: Props) {
  const [phases, setPhases] = useState<PhaseState[]>(
    PHASE_DEFS.map((p) => ({ key: p.key, label: p.label, status: "pending" as const }))
  );
  const [currentMsg, setCurrentMsg] = useState("正在初始化调研引擎...");
  const [interrupt, setInterrupt] = useState<InterruptData | null>(null);
  const [resuming, setResuming] = useState(false);
  const [error, setError] = useState("");
  const esRef = useRef<EventSource | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  function closeSSE() {
    esRef.current?.close();
    esRef.current = null;
  }

  useEffect(() => {
    const es = streamReport(
      reportId,
      (e) => {
        let data: {
          step?: string;
          type?: string;
          node?: string;
          message?: string;
          data?: InterruptData["data"];
        } = {};
        try {
          data = JSON.parse(e.data);
        } catch {
          return;
        }

        // 更新当前消息文案
        if (data.message) {
          setCurrentMsg(data.message);
        } else if (data.node) {
          const def = PHASE_DEFS.find((p) => p.key === data.node);
          if (def) setCurrentMsg(def.message);
        }

        // HiTL interrupt：只处理 review_draft（三个 TODO 全完成后的唯一确认点）
        if (data.type === "interrupt" && data.node === "review_draft") {
          setPhases((prev) => prev.map((p) => ({ ...p, status: "done" as const })));
          setCurrentMsg("报告草稿已生成，请确认后保存");
          setInterrupt({
            node: data.node,
            data: data.data || {},
          });
          return;
        }

        // 完成事件
        if (data.type === "completed") {
          setPhases((prev) => prev.map((p) => ({ ...p, status: "done" as const })));
          setCurrentMsg("报告生成完成！");
          setInterrupt(null);
          closeSSE();
          timerRef.current = setTimeout(() => onDone(), 600);
          return;
        }

        // 错误事件
        if (data.type === "error") {
          setError(data.message || "调研任务异常");
          closeSSE();
          return;
        }

        // 进度事件在节点「完成后」触发：当前节点标 done，预测下一个为 running
        const step = data.step || data.node || "";
        const phaseIndex = PHASE_DEFS.findIndex((p) => p.key === step);
        if (phaseIndex >= 0) {
          setPhases((prev) =>
            prev.map((p, i) => {
              if (i <= phaseIndex) return { ...p, status: "done" as const };
              if (i === phaseIndex + 1) return { ...p, status: "running" as const };
              return p;
            })
          );
        }
      },
      () => setError("SSE 连接失败，请刷新重试")
    );
    esRef.current = es;
    return () => {
      closeSSE();
      if (timerRef.current) clearTimeout(timerRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reportId]);

  async function handleResume(action: "approve" | "retry", feedback?: string) {
    setResuming(true);
    setError("");
    try {
      await resumeJob(reportId, action, feedback);
      setInterrupt(null);
      if (action === "retry") {
        setPhases(PHASE_DEFS.map((p) => ({ key: p.key, label: p.label, status: "pending" as const })));
        setCurrentMsg("正在重新搜索情报...");
      }
    } catch {
      setError("操作失败，请重试");
    } finally {
      setResuming(false);
    }
  }

  const doneCount = phases.filter((p) => p.status === "done").length;
  const runningPhase = phases.find((p) => p.status === "running");

  return (
    <div className="space-y-4 text-sm">
      {/* 进度横幅 */}
      <div className={`relative overflow-hidden rounded-xl border p-4 ${interrupt ? "bg-gradient-to-br from-green-50 to-emerald-50 border-green-200" : "bg-gradient-to-br from-blue-50 via-indigo-50 to-purple-50 border-blue-100 scan-line"}`}>
        <div className="flex items-center gap-3">
          {interrupt ? (
            <div className="w-8 h-8 rounded-full bg-green-500 flex items-center justify-center text-white text-base flex-shrink-0 shadow-sm shadow-green-200">✓</div>
          ) : (
            <BrainwaveLoader />
          )}
          <div className="flex-1 min-w-0">
            <p className={`font-semibold text-sm ${interrupt ? "text-green-800" : "text-blue-900"}`}>
              {interrupt ? "调研完成，请确认报告草稿" : "AI 正在深度调研中"}
            </p>
            <p className={`text-xs mt-0.5 truncate flex items-center gap-1 ${interrupt ? "text-green-600" : "text-blue-600"}`}>
              {currentMsg}
              {runningPhase && !interrupt && <span className="cursor-blink flex-shrink-0" />}
            </p>
          </div>
        </div>
        {doneCount > 0 && (
          <div className="mt-2 flex items-center gap-2">
            <div className={`flex-1 h-1 rounded-full overflow-hidden ${interrupt ? "bg-green-100" : "bg-blue-100"}`}>
              <div
                className={`h-full rounded-full transition-all duration-700 ease-out ${interrupt ? "bg-gradient-to-r from-green-400 to-emerald-500" : "bg-gradient-to-r from-blue-500 to-indigo-500"}`}
                style={{ width: `${Math.round((doneCount / phases.length) * 100)}%` }}
              />
            </div>
            <span className={`text-xs font-medium flex-shrink-0 ${interrupt ? "text-green-500" : "text-blue-400"}`}>
              {doneCount}/{phases.length}
            </span>
          </div>
        )}
      </div>

      {/* 阶段进度 */}
      <div className="px-1 space-y-3">
        <p className="text-xs text-gray-400 uppercase tracking-wider font-medium">
          执行阶段
        </p>
        {phases.map((phase, i) => {
          const isCurrent = phase.status === "running";
          return (
            <div
              key={phase.key}
              className={`flex items-center gap-3 transition-all duration-500 ${
                isCurrent ? "scale-[1.02]" : ""
              }`}
            >
              {/* 状态图标 */}
              {phase.status === "done" ? (
                <div className="w-5 h-5 rounded-full bg-green-500 flex items-center justify-center text-white text-[10px] flex-shrink-0 shadow-sm shadow-green-200">
                  ✓
                </div>
              ) : phase.status === "running" ? (
                <div className="relative w-5 h-5 flex items-center justify-center flex-shrink-0">
                  <div className="absolute inset-0 rounded-full border-2 border-blue-300 border-t-blue-600 animate-spin" />
                  <div className="w-2 h-2 rounded-full bg-blue-600 animate-pulse" />
                </div>
              ) : (
                <div className="w-5 h-5 rounded-full border-2 border-gray-200 flex-shrink-0" />
              )}

              {/* 阶段名称 */}
              <div className="flex-1 min-w-0">
                <span
                  className={`transition-all duration-300 ${
                    phase.status === "pending"
                      ? "text-gray-400"
                      : phase.status === "running"
                      ? "text-blue-700 font-semibold"
                      : "text-gray-700 font-medium"
                  }`}
                >
                  {i + 1}. {phase.label}
                </span>
                {isCurrent && (
                  <span className="ml-1.5 text-[10px] text-blue-400 animate-pulse">
                    进行中...
                  </span>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* 调研维度列表（静态展示，随阶段变色） */}
      {directions.length > 0 && (
        <div className="px-1 space-y-2">
          <p className="text-xs text-gray-400 uppercase tracking-wider font-medium">
            调研维度（{directions.length} 个）
          </p>
          <div className="flex flex-wrap gap-2">
            {directions.map((dir, i) => (
              <span
                key={i}
                className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs transition-colors duration-300 ${
                  runningPhase
                    ? "bg-blue-50 text-blue-700 border border-blue-200"
                    : doneCount === phases.length
                    ? "bg-green-50 text-green-700 border border-green-200"
                    : "bg-gray-50 text-gray-500 border border-gray-200"
                }`}
              >
                {dir}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* HiTL 确认面板（三个 TODO 全部完成后出现） */}
      {interrupt && (
        <div className="space-y-3 pt-2">
          <div className="bg-gradient-to-r from-amber-50 to-orange-50 border border-amber-200 rounded-xl p-4">
            <div className="flex items-center gap-2 mb-1">
              <span className="text-lg">⏸</span>
              <p className="font-semibold text-amber-800">报告草稿已就绪，请确认</p>
            </div>
            <p className="text-xs text-amber-600">
              请预览下方报告草稿，满意后点击保存；如需重新调研可点击"重新分析"
            </p>
          </div>

          {/* 报告草稿预览：优先展示 draft_sections，兜底用 research_analysis */}
          {interrupt.data.draft_sections && interrupt.data.draft_sections.length > 0 ? (
            <div className="bg-white border border-gray-200 rounded-xl p-4 max-h-[50vh] overflow-y-auto space-y-4">
              <p className="font-medium text-gray-400 text-xs uppercase tracking-wider sticky top-0 bg-white pb-2">
                报告草稿预览
              </p>
              {interrupt.data.draft_sections.map((section, i) => (
                <div key={i} className="border-b border-gray-100 pb-3 last:border-0 last:pb-0">
                  <h4 className="font-semibold text-gray-800 text-sm mb-1">
                    {section.heading}
                  </h4>
                  <MarkdownPreview content={section.content} />
                </div>
              ))}
            </div>
          ) : interrupt.data.research_analysis ? (
            <div className="bg-white border border-gray-200 rounded-xl p-4 max-h-[50vh] overflow-y-auto">
              <p className="font-medium text-gray-400 text-xs uppercase tracking-wider pb-2">
                调研分析摘要
              </p>
              <MarkdownPreview content={interrupt.data.research_analysis} />
            </div>
          ) : (
            <div className="bg-gray-50 border border-gray-200 rounded-xl p-4 text-center text-sm text-gray-400">
              报告内容加载中...
            </div>
          )}

          {error && (
            <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">{error}</p>
          )}

          {/* 操作按钮 */}
          <div className="flex gap-3">
            <button
              type="button"
              onClick={() => handleResume("retry")}
              disabled={resuming}
              className="flex-1 rounded-lg border border-gray-300 py-2.5 text-sm text-gray-600 hover:bg-gray-50 disabled:opacity-50 transition-colors"
            >
              重新分析
            </button>
            <button
              type="button"
              onClick={() => handleResume("approve")}
              disabled={resuming}
              className="flex-1 rounded-lg bg-gradient-to-r from-blue-600 to-indigo-600 py-2.5 text-sm text-white font-semibold hover:from-blue-700 hover:to-indigo-700 disabled:opacity-50 transition-all shadow-md shadow-blue-200"
            >
              {resuming ? (
                <span className="flex items-center justify-center gap-2">
                  <span className="dot-sequence">
                    <span /><span /><span />
                  </span>
                  处理中...
                </span>
              ) : (
                "确认，保存报告 →"
              )}
            </button>
          </div>
        </div>
      )}

      {/* 非 HiTL 场景错误 */}
      {error && !interrupt && (
        <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">{error}</p>
      )}
    </div>
  );
}
