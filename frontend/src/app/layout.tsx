import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Job Intel Agent",
  description: "AI 驱动的求职情报助手",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="zh">
      <body className="min-h-screen bg-gray-50">{children}</body>
    </html>
  );
}
