"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import ResumeUpload from "./ResumeUpload";
import { AICoreLoader, DataStreamLoader } from "./loading";
import {
  createJob,
  createJobFromImages,
  createJobFromText,
  submitRawContent,
  streamReport,
  uploadResume,
} from "@/lib/api";
import type { SSEEvent } from "@/lib/types";
import { ApiError } from "@/lib/errors";

type Tab = "url" | "text" | "image";

export default function JobInputForm() {
  const router = useRouter();

  const [url, setUrl] = useState("");
  const [resumeFile, setResumeFile] = useState<File | null>(null);
  const [resumeId, setResumeId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const [activeTab, setActiveTab] = useState<Tab>("url");
  const [isFallback, setIsFallback] = useState(false); // true = URL 失败后自动切换
  const [pendingJobId, setPendingJobId] = useState<string | null>(null);
  const [rawText, setRawText] = useState("");
  const [images, setImages] = useState<File[]>([]);
  const [imagePreviews, setImagePreviews] = useState<string[]>([]);
  const [manualLoading, setManualLoading] = useState(false);
  const [manualError, setManualError] = useState("");

  const esRef = useRef<EventSource | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    return () => {
      imagePreviews.forEach((u) => URL.revokeObjectURL(u));
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function cleanupSSE() {
    esRef.current?.close();
    esRef.current = null;
  }

  async function ensureResumeId(): Promise<string | undefined> {
    if (!resumeFile) return undefined;
    if (resumeId) return resumeId;
    const res = await uploadResume(resumeFile);
    setResumeId(res.id);
    return res.id;
  }

  function handleTabChange(tab: Tab) {
    setActiveTab(tab);
    setIsFallback(false);
    setError("");
    setManualError("");
  }

  function subscribeToJob(id: string) {
    cleanupSSE();
    const es = streamReport(
      id,
      (e: MessageEvent) => {
        try {
          const event = JSON.parse(e.data) as SSEEvent;
          if (event.type === "parsed") {
            cleanupSSE();
            router.push(`/report/${id}?step=confirm`);
          } else if (event.type === "awaiting_manual_input") {
            cleanupSSE();
            setLoading(false);
            setManualLoading(false);
            setPendingJobId(id);
            setActiveTab("text");
            setIsFallback(true);
            setError("");
          } else if (event.type === "error") {
            cleanupSSE();
            setLoading(false);
            setManualLoading(false);
            setError(event.message || "解析失败，请稍后重试");
            setManualError(event.message || "解析失败，请稍后重试");
          }
        } catch {
          // ignore malformed events
        }
      },
      (err: ApiError) => {
        setLoading(false);
        setManualLoading(false);
        setError(err.message || "连接失败，请刷新重试");
        setManualError(err.message || "连接失败，请刷新重试");
      }
    );
    esRef.current = es;
  }

  async function handleUrlSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!url) return;
    setError("");
    setLoading(true);
    try {
      const rid = await ensureResumeId();
      const job = await createJob(url, rid);
      subscribeToJob(job.id);
    } catch (err) {
      setLoading(false);
      setError(err instanceof ApiError ? err.message : "提交失败，请稍后重试");
    }
  }

  function handleImageSelect(e: React.ChangeEvent<HTMLInputElement>) {
    const incoming = Array.from(e.target.files ?? []);
    const combined = [...images, ...incoming].slice(0, 3);
    imagePreviews.forEach((u) => URL.revokeObjectURL(u));
    setImages(combined);
    setImagePreviews(combined.map((f) => URL.createObjectURL(f)));
    e.target.value = "";
  }

  function removeImage(index: number) {
    imagePreviews.forEach((u) => URL.revokeObjectURL(u));
    const next = images.filter((_, i) => i !== index);
    setImages(next);
    setImagePreviews(next.map((f) => URL.createObjectURL(f)));
  }

  async function handleManualSubmit() {
    const hasImages = images.length > 0;
    const hasText = rawText.trim().length > 0;
    if (!hasImages && !hasText) {
      setManualError("请粘贴职位描述或上传截图");
      return;
    }
    setManualError("");
    setManualLoading(true);
    try {
      const rid = await ensureResumeId();
      let id: string;

      if (hasImages) {
        const job = await createJobFromImages(images, rid);
        id = job.id;
      } else if (pendingJobId) {
        await submitRawContent(pendingJobId, rawText.trim());
        id = pendingJobId;
      } else {
        const job = await createJobFromText(rawText.trim(), rid);
        id = job.id;
      }

      subscribeToJob(id);
    } catch (err) {
      setManualLoading(false);
      setManualError(err instanceof ApiError ? err.message : "提交失败，请稍后重试");
    }
  }

  const tabs: { key: Tab; icon: string; label: string }[] = [
    { key: "url", icon: "🔗", label: "粘贴链接" },
    { key: "text", icon: "📋", label: "输入内容" },
    { key: "image", icon: "📸", label: "上传截图" },
  ];

  return (
    <div className="space-y-4">
      {/* Tab 导航栏 */}
      <div className="flex bg-gray-100 rounded-xl p-1 gap-1">
        {tabs.map(({ key, icon, label }) => (
          <button
            key={key}
            type="button"
            onClick={() => handleTabChange(key)}
            className={`flex-1 flex flex-col items-center py-2 px-1 rounded-lg text-xs font-medium transition-all ${
              activeTab === key
                ? "bg-white text-blue-600 shadow-sm"
                : "text-gray-500 hover:text-gray-700"
            }`}
          >
            <span className="text-sm mb-0.5">{icon}</span>
            {label}
          </button>
        ))}
      </div>

      {/* 粘贴链接 Tab */}
      {activeTab === "url" && (
        <div className="space-y-3">
          {loading ? (
            <div className="py-4">
              <AICoreLoader
                size="md"
                label="AI 正在解析职位描述..."
                subLabel="抓取页面信息 → LLM 提取关键字段"
              />
            </div>
          ) : (
            <form onSubmit={handleUrlSubmit} className="space-y-3">
              <input
                type="url"
                placeholder="粘贴 JD 链接（Boss直聘 / 拉勾 / 猎聘等）"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                className="w-full rounded-lg border border-gray-300 px-4 py-3 focus:outline-none focus:ring-2 focus:ring-blue-500"
                disabled={loading}
              />
              <ResumeUpload onFileSelect={setResumeFile} />
              {error && (
                <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">{error}</p>
              )}
              <button
                type="submit"
                disabled={loading || !url}
                className="w-full rounded-lg bg-gradient-to-r from-blue-600 to-indigo-600 px-6 py-3 text-white font-semibold hover:from-blue-700 hover:to-indigo-700 disabled:opacity-50 transition-all shadow-md shadow-blue-200"
              >
                开始分析
              </button>
            </form>
          )}
        </div>
      )}

      {/* 输入内容 Tab */}
      {activeTab === "text" && (
        <div className="space-y-3">
          {isFallback && (
            <div className="flex items-start gap-2 rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-800">
              <span className="mt-0.5 flex-shrink-0">⚠️</span>
              <span>未能从该链接自动提取内容，请直接粘贴职位描述文本</span>
            </div>
          )}
          {manualLoading ? (
            <div className="py-2">
              <DataStreamLoader label="正在提取职位信息…" particleCount={8} />
            </div>
          ) : (
            <div className="space-y-3">
              <textarea
                value={rawText}
                onChange={(e) => setRawText(e.target.value)}
                placeholder="将 JD 全文粘贴到此处..."
                rows={6}
                className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
              />
              <ResumeUpload onFileSelect={setResumeFile} />
              {manualError && (
                <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">{manualError}</p>
              )}
              <button
                type="button"
                onClick={handleManualSubmit}
                disabled={!rawText.trim()}
                className="w-full rounded-lg bg-gradient-to-r from-blue-600 to-indigo-600 px-6 py-3 text-white font-semibold hover:from-blue-700 hover:to-indigo-700 disabled:opacity-50 transition-all shadow-md shadow-blue-200"
              >
                开始分析
              </button>
            </div>
          )}
        </div>
      )}

      {/* 上传截图 Tab */}
      {activeTab === "image" && (
        <div className="space-y-3">
          {manualLoading ? (
            <div className="py-2">
              <DataStreamLoader label="正在提取职位信息…" particleCount={8} />
            </div>
          ) : (
            <div className="space-y-3">
              <p className="text-sm font-medium text-gray-700">上传 JD 截图（最多 3 张）</p>
              <div className="flex flex-wrap gap-2">
                {imagePreviews.map((src, i) => (
                  <div key={i} className="relative">
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img
                      src={src}
                      alt={`截图 ${i + 1}`}
                      className="h-20 w-20 rounded object-cover border border-gray-200"
                    />
                    <button
                      type="button"
                      onClick={() => removeImage(i)}
                      className="absolute -top-1 -right-1 flex h-4 w-4 items-center justify-center rounded-full bg-red-500 text-white text-xs leading-none"
                    >
                      ×
                    </button>
                  </div>
                ))}
                {images.length < 3 && (
                  <button
                    type="button"
                    onClick={() => fileInputRef.current?.click()}
                    className="flex h-20 w-20 items-center justify-center rounded border-2 border-dashed border-gray-300 text-2xl text-gray-400 hover:border-blue-400 hover:text-blue-400"
                  >
                    +
                  </button>
                )}
              </div>
              <input
                ref={fileInputRef}
                type="file"
                accept="image/*"
                multiple
                className="hidden"
                onChange={handleImageSelect}
              />
              <ResumeUpload onFileSelect={setResumeFile} />
              {manualError && (
                <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">{manualError}</p>
              )}
              <button
                type="button"
                onClick={handleManualSubmit}
                disabled={images.length === 0}
                className="w-full rounded-lg bg-gradient-to-r from-blue-600 to-indigo-600 px-6 py-3 text-white font-semibold hover:from-blue-700 hover:to-indigo-700 disabled:opacity-50 transition-all shadow-md shadow-blue-200"
              >
                开始分析
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
