"use client";

import { useMemo } from "react";

type MdNode =
  | { type: "h1"; text: string }
  | { type: "h2"; text: string }
  | { type: "h3"; text: string }
  | { type: "p"; text: string }
  | { type: "li"; text: string }
  | { type: "hr" };

function parseMarkdown(raw: string): MdNode[] {
  const nodes: MdNode[] = [];
  const lines = raw.split("\n");

  for (let i = 0; i < lines.length; i++) {
    const trimmed = lines[i].trim();
    if (!trimmed) continue;

    if (trimmed.startsWith("### ")) {
      nodes.push({ type: "h3", text: trimmed.slice(4) });
    } else if (trimmed.startsWith("## ")) {
      nodes.push({ type: "h2", text: trimmed.slice(3) });
    } else if (trimmed.startsWith("# ")) {
      nodes.push({ type: "h1", text: trimmed.slice(2) });
    } else if (trimmed.startsWith("- ")) {
      nodes.push({ type: "li", text: trimmed.slice(2) });
    } else if (trimmed === "---" || trimmed === "***") {
      nodes.push({ type: "hr" });
    } else {
      const paragraphLines = [trimmed];
      while (
        i + 1 < lines.length &&
        lines[i + 1].trim() &&
        !lines[i + 1].trim().startsWith("#") &&
        !lines[i + 1].trim().startsWith("- ")
      ) {
        i++;
        paragraphLines.push(lines[i].trim());
      }
      nodes.push({ type: "p", text: paragraphLines.join(" ") });
    }
  }
  return nodes;
}

interface InlinePart {
  text: string;
  bold?: boolean;
  code?: boolean;
}

function parseInline(text: string): InlinePart[] {
  const parts: InlinePart[] = [];
  const regex = /(\*\*(.+?)\*\*)|(`([^`]+)`)|([^*`]+)/g;
  let match: RegExpExecArray | null;
  while ((match = regex.exec(text)) !== null) {
    if (match[1]) {
      parts.push({ text: match[2], bold: true });
    } else if (match[3]) {
      parts.push({ text: match[4], code: true });
    } else if (match[5]) {
      parts.push({ text: match[5] });
    }
  }
  return parts.length > 0 ? parts : [{ text }];
}

function InlineText({ parts, baseKey }: { parts: InlinePart[]; baseKey: string }) {
  return (
    <>
      {parts.map((p, i) => {
        if (p.bold) {
          return (
            <strong key={`${baseKey}-b-${i}`} className="font-semibold text-gray-800">
              {p.text}
            </strong>
          );
        }
        if (p.code) {
          return (
            <code key={`${baseKey}-c-${i}`} className="bg-gray-100 text-blue-600 px-1 py-0.5 rounded text-xs">
              {p.text}
            </code>
          );
        }
        return <span key={`${baseKey}-t-${i}`}>{p.text}</span>;
      })}
    </>
  );
}

interface Props {
  content: string;
  className?: string;
}

export default function MarkdownPreview({ content, className = "" }: Props) {
  const nodes = useMemo(() => parseMarkdown(content), [content]);

  if (nodes.length === 0) {
    return <p className="text-sm text-gray-400 italic">暂无内容</p>;
  }

  return (
    <div className={`text-sm leading-relaxed ${className}`}>
      {nodes.map((node, i) => {
        const key = `md-${i}`;
        switch (node.type) {
          case "h1":
            return (
              <h2 key={key} className="text-lg font-bold text-gray-900 mt-4 mb-2">
                {node.text}
              </h2>
            );
          case "h2":
            return (
              <h3 key={key} className="text-base font-bold text-gray-800 mt-3 mb-1.5">
                {node.text}
              </h3>
            );
          case "h3":
            return (
              <h4 key={key} className="text-sm font-semibold text-gray-800 mt-2 mb-1">
                {node.text}
              </h4>
            );
          case "p":
            return (
              <p key={key} className="text-gray-600 text-sm mb-1.5">
                <InlineText parts={parseInline(node.text)} baseKey={key} />
              </p>
            );
          case "li":
            return (
              <div key={key} className="flex items-start gap-2 ml-2 mb-0.5">
                <span className="text-blue-400 mt-0.5 flex-shrink-0">•</span>
                <span className="text-gray-600 text-sm">
                  <InlineText parts={parseInline(node.text)} baseKey={key} />
                </span>
              </div>
            );
          case "hr":
            return <hr key={key} className="my-3 border-gray-100" />;
          default:
            return null;
        }
      })}
    </div>
  );
}
