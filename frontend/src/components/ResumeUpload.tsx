"use client";

import { useRef, useState } from "react";

interface Props {
  onFileSelect: (file: File | null) => void;
}

export default function ResumeUpload({ onFileSelect }: Props) {
  const ref = useRef<HTMLInputElement>(null);
  const [resumeFile, setResumeFile] = useState<File | null>(null);

  function handleFile(file: File | undefined) {
    if (!file) return;
    setResumeFile(file);
    onFileSelect(file);
  }

  return (
    <div
      className="rounded-xl border-2 border-dashed border-gray-300 bg-white px-6 py-8 text-center cursor-pointer hover:border-blue-400 hover:bg-blue-50 transition-all group"
      onClick={() => ref.current?.click()}
      onDragOver={(e) => e.preventDefault()}
      onDrop={(e) => {
        e.preventDefault();
        handleFile(e.dataTransfer.files[0]);
      }}
    >
      <div className="text-3xl mb-2">📄</div>
      <p className="text-gray-500 text-sm group-hover:text-blue-600">
        {resumeFile ? resumeFile.name : "点击或拖拽上传简历（PDF / DOCX，可选）"}
      </p>
      <p className="text-gray-400 text-xs mt-1">上传后 AI 将生成个性化面试题预测</p>
      <input
        ref={ref}
        type="file"
        accept=".pdf,.docx"
        className="hidden"
        onChange={(e) => handleFile(e.target.files?.[0])}
      />
    </div>
  );
}
