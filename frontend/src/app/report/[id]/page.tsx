"use client";
import { useEffect, useState, useCallback } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import type { ReportStep, ReportData } from "@/lib/types";
import { fetchReport, getJob, streamReport, confirmJob, startResearch } from "@/lib/api";
import { ApiError } from "@/lib/errors";
import StepProgress from "@/components/report/StepProgress";
import StageCard from "@/components/report/StageCard";
import JDConfirmCard from "@/components/report/JDConfirmCard";
import DirectionsCard from "@/components/report/DirectionsCard";
import ResearchingCard from "@/components/report/ResearchingCard";
import ReportView from "@/components/report/ReportView";
import { DataStreamLoader, AICoreLoader } from "@/components/loading";

const STEP_LABELS = ["JD 解析", "确认信息", "选择方向", "生成报告"];

type StepStateVal = "locked" | "active" | "done";

function stepToStates(step: ReportStep): StepStateVal[] {
  const map: Record<ReportStep, StepStateVal[]> = {
    parsing:     ["active", "locked", "locked", "locked"],
    confirm:     ["done",   "active", "locked", "locked"],
    directions:  ["done",   "done",   "active", "locked"],
    researching: ["done",   "done",   "done",   "active"],
    done:        ["done",   "done",   "done",   "done"],
  };
  return map[step];
}

interface JobInfo {
  title: string;
  company: string;
  requirements: string[];
  suggested_directions?: string[];
}

export default function ReportPage({ params }: { params: { id: string } }) {
  const reportId = params.id;
  const searchParams = useSearchParams();
  const router = useRouter();

  const [step, setStep] = useState<ReportStep>(
    (searchParams.get("step") as ReportStep) || "parsing"
  );
  const [jobInfo, setJobInfo] = useState<JobInfo>({
    title: "",
    company: "",
    requirements: [],
  });
  const [confirmedSubtitle, setConfirmedSubtitle] = useState("");
  const [selectedDirs, setSelectedDirs] = useState<string[]>([]);
  const [reportData, setReportData] = useState<ReportData | null>(null);
  const [error, setError] = useState("");
  const [jobLoading, setJobLoading] = useState(false);
  const [reportLoading, setReportLoading] = useState(false);

  function goStep(s: ReportStep) {
    setStep(s);
    router.replace(`/report/${reportId}?step=${s}`);
  }

  // SSE for parsing phase
  useEffect(() => {
    if (step !== "parsing") return;
    const es = streamReport(
      reportId,
      (e: MessageEvent) => {
        let data: Record<string, unknown> = {};
        try { data = JSON.parse(e.data); } catch { return; }

        const eventType = (data.type as string) || "";
        const eventStep = (data.step as string) || "";

        if (eventType === "error") {
          setError((data.message as string) || "JD 解析失败，请稍后重试");
          es.close();
          return;
        }

        if (
          eventType === "parsed" ||
          eventType === "hitl" ||
          eventStep === "parse_complete" ||
          eventStep === "confirm"
        ) {
          setJobInfo({
            title: (data.title as string) || "",
            company: (data.company as string) || "",
            requirements: (data.requirements as string[]) || [],
            suggested_directions: (data.suggested_directions as string[]) || [],
          });
          es.close();
          goStep("confirm");
        }
      },
      (err: ApiError) => {
        setError(err.message);
      }
    );
    return () => es.close();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reportId, step]);

  // Fetch job data when entering confirm step
  useEffect(() => {
    if (step !== "confirm") return;
    setJobLoading(true);
    getJob(reportId)
      .then((job) => {
        setJobInfo({
          title: job.title || "",
          company: job.company || "",
          requirements: job.requirements || [],
          suggested_directions: (job as { suggested_directions?: string[] }).suggested_directions || [],
        });
      })
      .catch(() => {/* keep empty */})
      .finally(() => setJobLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [step, reportId]);

  // Load report when done
  useEffect(() => {
    if (step !== "done") return;
    setError("");
    setReportLoading(true);
    fetchReport(reportId)
      .then((r) => {
        if (r.data) {
          setReportData(r.data);
        } else {
          setError("报告数据为空，请稍后重试");
        }
      })
      .catch((err) => {
        setError(err instanceof ApiError ? err.message : "报告加载失败");
      })
      .finally(() => setReportLoading(false));
  }, [step, reportId]);

  // Load selected directions when entering researching step
  useEffect(() => {
    if (step !== "researching" || selectedDirs.length > 0) return;
    getJob(reportId)
      .then((job) => {
        const dirs = (job as { selected_directions?: string[] }).selected_directions;
        if (dirs && dirs.length > 0) setSelectedDirs(dirs);
      })
      .catch(() => {/* keep empty */});
  }, [step, reportId, selectedDirs.length]);

  async function handleConfirm(data: {
    title: string;
    company: string;
    requirements: string[];
  }) {
    setError("");
    try {
      await confirmJob(reportId, data);
      setConfirmedSubtitle(`${data.title} · ${data.company}`);
      setJobInfo((prev) => ({ ...prev, ...data }));
      goStep("directions");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "确认职位信息失败");
      throw err;
    }
  }

  async function handleStartResearch(dirs: string[]) {
    setError("");
    try {
      setSelectedDirs(dirs);
      await startResearch(reportId, dirs);
      goStep("researching");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "启动调研失败");
    }
  }

  const handleResearchDone = useCallback(() => {
    goStep("done");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reportId]);

  return (
    <main className="max-w-3xl mx-auto px-4 pt-10 pb-16">
      <div className="mb-6">
        <StepProgress steps={STEP_LABELS} states={stepToStates(step)} />
      </div>

      <div className="space-y-3">
        {error && (
          <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-600">
            {error}
          </div>
        )}

        {/* 卡片 1：JD 解析 */}
        {step === "parsing" ? (
          <StageCard state="active" step={1} title={error ? "JD 解析失败" : "正在解析 JD…"}>
            {error ? (
              <p className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-600">{error}</p>
            ) : (
              <DataStreamLoader
                label="Firecrawl 抓取页面 → LLM 提取关键信息"
                particleCount={10}
              />
            )}
          </StageCard>
        ) : (
          <StageCard state="done" step={1} title="JD 解析完成" />
        )}

        {/* 卡片 2：确认职位信息 */}
        {step === "parsing" ? (
          <StageCard state="locked" step={2} title="确认职位信息（等待解析完成）" />
        ) : step === "confirm" ? (
          <StageCard state="active" step={2} title="确认职位信息" badge="需要你确认">
            {jobLoading ? (
              <div className="py-6">
                <DataStreamLoader label="正在加载职位信息…" particleCount={6} />
              </div>
            ) : (
              <JDConfirmCard
                initial={jobInfo}
                onConfirm={handleConfirm}
                onCancel={() => {}}
              />
            )}
          </StageCard>
        ) : (
          <StageCard
            state="done"
            step={2}
            title="职位信息已确认"
            subtitle={confirmedSubtitle}
          />
        )}

        {/* 卡片 3：选择调研方向 */}
        {step === "parsing" || step === "confirm" ? (
          <StageCard state="locked" step={3} title="选择调研方向（等待确认）" />
        ) : step === "directions" ? (
          <StageCard state="active" step={3} title="选择调研方向" badge="需要你选择">
            <DirectionsCard
              suggested={jobInfo.suggested_directions}
              onStart={handleStartResearch}
            />
          </StageCard>
        ) : (
          <StageCard
            state="done"
            step={3}
            title={`已选择 ${selectedDirs.length || "全部"} 个调研方向`}
          />
        )}

        {/* 卡片 4：调研 & 报告 */}
        {step === "parsing" || step === "confirm" || step === "directions" ? (
          <StageCard state="locked" step={4} title="调研 & 生成报告（等待确认）" />
        ) : step === "researching" ? (
          <StageCard state="active" step={4} title="调研 & 报告生成中">
            <ResearchingCard
              reportId={reportId}
              directions={selectedDirs}
              onDone={handleResearchDone}
            />
          </StageCard>
        ) : null}

        {/* 报告展示 */}
        {step === "done" && reportData && (
          <ReportView
            data={reportData}
            jobTitle={jobInfo.title || undefined}
            company={jobInfo.company || undefined}
            date={new Date().toISOString().slice(0, 10)}
          />
        )}
        {step === "done" && reportLoading && !reportData && (
          <div className="py-12">
            <AICoreLoader
              size="lg"
              label="报告加载中..."
              subLabel="正在获取生成的报告数据"
            />
          </div>
        )}
        {step === "done" && !reportLoading && !reportData && !error && (
          <div className="text-center py-12">
            <p className="text-gray-400 text-sm">报告数据为空</p>
            <button
              type="button"
              onClick={async () => {
                setReportLoading(true);
                setError("");
                try {
                  const r = await fetchReport(reportId);
                  if (r.data) setReportData(r.data);
                  else setError("报告数据为空，请稍后重试");
                } catch (err) {
                  setError(err instanceof ApiError ? err.message : "报告加载失败");
                } finally {
                  setReportLoading(false);
                }
              }}
              className="mt-3 text-blue-600 text-sm hover:underline"
            >
              点击重新加载
            </button>
          </div>
        )}
      </div>
    </main>
  );
}
