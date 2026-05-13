"use client";

import { useRef } from "react";

interface Props {
  onFileSelect: (file: File | null) => void;
}

export default function ResumeUpload({ onFileSelect }: Props) {
  const ref = useRef<HTMLInputElement>(null);

  return (
    <div
      onClick={() => ref.current?.click()}
      className="cursor-pointer rounded-lg border-2 border-dashed border-gray-300 p-6 text-center hover:border-blue-400"
    >
      <input
        ref={ref}
        type="file"
        accept=".pdf,.docx"
        className="hidden"
        onChange={(e) => onFileSelect(e.target.files?.[0] ?? null)}
      />
      <p className="text-gray-500">点击上传简历（PDF / DOCX，可选）</p>
    </div>
  );
}
