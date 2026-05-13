"use client";

import { useState } from "react";
import ResumeUpload from "./ResumeUpload";
import HumanInLoopDialog from "./HumanInLoopDialog";
import { createJob, uploadResume } from "@/lib/api";

export default function JobInputForm() {
  const [url, setUrl] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [pendingJob, setPendingJob] = useState<{ id: string } | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!url) return;
    setLoading(true);
    try {
      const job = await createJob(url);
      if (file) await uploadResume(file);
      setPendingJob(job);
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <form onSubmit={handleSubmit} className="space-y-4">
        <input
          type="url"
          placeholder="粘贴 JD 链接（Boss / 拉勾 / 猎聘）"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          className="w-full rounded-lg border border-gray-300 px-4 py-3 focus:outline-none focus:ring-2 focus:ring-blue-500"
          required
        />
        <ResumeUpload onFileSelect={setFile} />
        <button
          type="submit"
          disabled={loading}
          className="w-full rounded-lg bg-blue-600 px-6 py-3 text-white font-semibold hover:bg-blue-700 disabled:opacity-50"
        >
          {loading ? "解析中..." : "开始分析"}
        </button>
      </form>
      {pendingJob && (
        <HumanInLoopDialog jobId={pendingJob.id} onClose={() => setPendingJob(null)} />
      )}
    </>
  );
}
