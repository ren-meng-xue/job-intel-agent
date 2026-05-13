import ReportCard from "@/components/ReportCard";
import ProgressStream from "@/components/ProgressStream";

export default function ReportPage({ params }: { params: { id: string } }) {
  return (
    <main className="mx-auto max-w-3xl px-4 py-12">
      <ProgressStream reportId={params.id} />
      <ReportCard reportId={params.id} />
    </main>
  );
}
