"use client";

import { useEffect, useState } from "react";
import { streamReport } from "@/lib/api";
import type { SSEEvent } from "@/lib/types";

interface Props {
  reportId: string;
}

export default function ProgressStream({ reportId }: Props) {
  const [messages, setMessages] = useState<string[]>([]);
  const [done, setDone] = useState(false);

  useEffect(() => {
    const es = streamReport(reportId, (e: MessageEvent) => {
      const event: SSEEvent = JSON.parse(e.data);
      setMessages((prev) => [...prev, event.message]);
      if (event.type === "done" || event.type === "error") {
        setDone(true);
        es.close();
      }
    });
    return () => es.close();
  }, [reportId]);

  if (done) return null;

  return (
    <div className="mb-6 rounded-lg bg-blue-50 p-4 text-sm text-blue-800 space-y-1">
      {messages.map((m, i) => (
        <p key={i}>⏳ {m}</p>
      ))}
      {!messages.length && <p>正在连接调研进度...</p>}
    </div>
  );
}
