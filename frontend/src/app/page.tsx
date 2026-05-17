import Link from "next/link";
import JobInputForm from "@/components/JobInputForm";

export default function Home() {
  return (
    <main className="mx-auto max-w-2xl px-4 py-16">
      <div className="mb-2 flex items-center justify-between">
        <h1 className="text-3xl font-bold text-gray-900">Job Intel Agent</h1>
        <Link
          href="/design"
          className="flex items-center gap-1.5 rounded-lg bg-blue-600 px-4 py-1.5 text-sm font-medium text-white hover:bg-blue-700 transition-colors"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
              d="M2.25 7.125C2.25 6.504 2.754 6 3.375 6h6c.621 0 1.125.504 1.125 1.125v3.75c0 .621-.504 1.125-1.125 1.125h-6a1.125 1.125 0 01-1.125-1.125v-3.75zM14.25 8.625c0-.621.504-1.125 1.125-1.125h5.25c.621 0 1.125.504 1.125 1.125v8.25c0 .621-.504 1.125-1.125 1.125h-5.25a1.125 1.125 0 01-1.125-1.125v-8.25zM3.75 16.125c0-.621.504-1.125 1.125-1.125h5.25c.621 0 1.125.504 1.125 1.125v2.25c0 .621-.504 1.125-1.125 1.125h-5.25a1.125 1.125 0 01-1.125-1.125v-2.25z" />
          </svg>
          原型
        </Link>
      </div>
      <p className="mb-8 text-gray-500">
        粘贴 JD 链接 + 上传简历，3-5 分钟生成专属面试情报报告
      </p>
      <JobInputForm />
    </main>
  );
}
