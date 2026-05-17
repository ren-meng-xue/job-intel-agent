"use client";
import { useRef, useState, useCallback } from "react";
import type { ReportData } from "@/lib/types";
import JobInterpretationModule from "./modules/JobInterpretationModule";
import ResumeMatchModule from "./modules/ResumeMatchModule";
import CompanyProfileModule from "./modules/CompanyProfileModule";
import InterviewQAModule from "./modules/InterviewQAModule";
import SalaryModule from "./modules/SalaryModule";
import PrepSuggestionsModule from "./modules/PrepSuggestionsModule";

interface Props {
  data: ReportData;
  jobTitle?: string;
  company?: string;
  date?: string;
}

export default function ReportView({ data, jobTitle, company, date }: Props) {
  const contentRef = useRef<HTMLDivElement>(null);
  const [downloading, setDownloading] = useState(false);

  const handleDownloadPdf = useCallback(async () => {
    if (!contentRef.current) return;
    setDownloading(true);
    try {
      const html2canvas = (await import("html2canvas")).default;
      const { jsPDF } = await import("jspdf");

      const el = contentRef.current;
      const canvas = await html2canvas(el, {
        scale: 2,
        useCORS: true,
        backgroundColor: "#ffffff",
      });

      const imgData = canvas.toDataURL("image/png");
      const imgWidth = 210; // A4 mm
      const pageHeight = 297; // A4 mm
      const imgHeight = (canvas.height * imgWidth) / canvas.width;

      const pdf = new jsPDF("p", "mm", "a4");
      let heightLeft = imgHeight;
      let position = 0;

      pdf.addImage(imgData, "PNG", 0, position, imgWidth, imgHeight);
      heightLeft -= pageHeight;

      while (heightLeft > 0) {
        position = -(imgHeight - heightLeft);
        pdf.addPage();
        pdf.addImage(imgData, "PNG", 0, position, imgWidth, imgHeight);
        heightLeft -= pageHeight;
      }

      const filename = [
        "面试情报报告",
        company,
        jobTitle,
        date || new Date().toISOString().slice(0, 10),
      ]
        .filter(Boolean)
        .join("_")
        .replace(/\s+/g, "_");

      pdf.save(`${filename}.pdf`);
    } catch (err) {
      console.error("PDF generation failed:", err);
    } finally {
      setDownloading(false);
    }
  }, [jobTitle, company, date]);

  return (
    <div className="space-y-3 pb-20">
      {/* 顶部操作栏 */}
      <div className="flex items-center justify-between p-3 bg-green-50 rounded-xl border border-green-200 mb-2">
        <div className="flex items-center gap-2 min-w-0">
          <span className="text-green-600 font-semibold text-sm flex-shrink-0">✅ 报告已生成</span>
          {jobTitle && company && (
            <span className="text-green-500 text-xs truncate">
              {jobTitle} · {company}
              {date && ` · ${date}`}
            </span>
          )}
        </div>
        <button
          type="button"
          onClick={handleDownloadPdf}
          disabled={downloading}
          className="flex-shrink-0 ml-3 inline-flex items-center gap-1.5 rounded-lg bg-white border border-green-300 px-3 py-1.5 text-xs font-medium text-green-700 hover:bg-green-100 disabled:opacity-50 transition-colors"
        >
          {downloading ? (
            <>
              <span className="inline-block w-3.5 h-3.5 rounded-full border-2 border-green-400 border-t-transparent animate-spin" />
              生成中...
            </>
          ) : (
            <>
              <svg
                xmlns="http://www.w3.org/2000/svg"
                viewBox="0 0 20 20"
                fill="currentColor"
                className="w-4 h-4"
              >
                <path d="M10.75 2.75a.75.75 0 00-1.5 0v8.614L6.295 8.235a.75.75 0 10-1.09 1.03l4.25 4.5a.75.75 0 001.09 0l4.25-4.5a.75.75 0 00-1.09-1.03l-2.955 3.129V2.75z" />
                <path d="M3.5 12.75a.75.75 0 00-1.5 0v2.5A2.75 2.75 0 004.75 18h10.5A2.75 2.75 0 0018 15.25v-2.5a.75.75 0 00-1.5 0v2.5c0 .69-.56 1.25-1.25 1.25H4.75c-.69 0-1.25-.56-1.25-1.25v-2.5z" />
              </svg>
              下载 PDF
            </>
          )}
        </button>
      </div>

      {/* 报告内容（PDF 截图区域） */}
      <div ref={contentRef} className="space-y-3">
        <JobInterpretationModule data={data.job_interpretation} />
        <ResumeMatchModule data={data.resume_match} />
        <CompanyProfileModule data={data.company_profile} />
        <InterviewQAModule data={data.interview_qa} />
        <SalaryModule data={data.salary_range} />
        <PrepSuggestionsModule data={data.prep_suggestions} />
      </div>
    </div>
  );
}
