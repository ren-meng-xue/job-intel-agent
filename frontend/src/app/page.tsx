import JobInputForm from "@/components/JobInputForm";

export default function Home() {
  return (
    <main className="mx-auto max-w-2xl px-4 py-16">
      <h1 className="mb-2 text-3xl font-bold text-gray-900">Job Intel Agent</h1>
      <p className="mb-8 text-gray-500">
        粘贴 JD 链接 + 上传简历，3-5 分钟生成专属面试情报报告
      </p>
      <JobInputForm />
    </main>
  );
}
