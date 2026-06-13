"use client";

import { useMemo, useRef, useState } from "react";
import { Bot, ChevronDown, ChevronUp, Loader2, MessageSquare, Send, UserRound } from "lucide-react";
import { chatWithProject } from "@/lib/api";
import type { ChatMessage, ReportJsonResponse } from "@/types/contracts";
import { useApp } from "@/contexts/AppContext";

interface ProjectChatPanelProps {
  jobId: string | null;
  repoPath?: string | null;
  report?: ReportJsonResponse | null;
}

const SUGGESTIONS = [
  "이 프로젝트에서 팀원이 먼저 봐야 할 파일은?",
  "현재 가장 위험한 수정 포인트를 알려줘",
  "프론트엔드와 백엔드 작업을 어떻게 나누면 좋아?",
];

export function ProjectChatPanel({ jobId, repoPath, report }: ProjectChatPanelProps) {
  const [collapsed, setCollapsed] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      role: "assistant",
      content:
        "분석된 프로젝트에 대해 물어보세요. 리포트가 생성되면 요약, 위험 파일, 추천 작업을 바탕으로 답변합니다.",
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLTextAreaElement | null>(null);

  const { theme } = useApp();
  const isDark = theme === "dark";

  const canAsk = Boolean(jobId || repoPath);
  const contextLabel = useMemo(() => {
    if (repoPath) return repoPath.replace(/^https:\/\/github\.com\//, "");
    if (jobId) return `Job ${jobId.slice(0, 8)}`;
    return "분석 대기 중";
  }, [jobId, repoPath]);

  const submit = async (text?: string) => {
    const question = (text ?? input).trim();
    if (!question || loading || !canAsk) return;

    const nextMessages: ChatMessage[] = [...messages, { role: "user", content: question }];
    setMessages(nextMessages);
    setInput("");
    setError(null);
    setLoading(true);

    try {
      const response = await chatWithProject({
        message: question,
        job_id: jobId,
        repo_path: repoPath,
        messages: messages.filter((msg) => msg.role === "user" || msg.role === "assistant"),
      });
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: response.answer,
        },
      ]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "채팅 응답을 가져오지 못했습니다.");
    } finally {
      setLoading(false);
      inputRef.current?.focus();
    }
  };

  const panelClass = isDark ? "bg-zinc-900/70 border-zinc-800" : "bg-white border-zinc-200 shadow-sm";
  const titleClass = isDark ? "text-white" : "text-zinc-900";
  const mutedClass = isDark ? "text-zinc-500" : "text-zinc-500";
  const messageAssistantClass = isDark
    ? "bg-zinc-800/70 text-zinc-200 border-zinc-700"
    : "bg-zinc-100 text-zinc-700 border-zinc-200";
  const messageUserClass = isDark
    ? "bg-blue-500/15 text-blue-100 border-blue-500/30"
    : "bg-blue-50 text-blue-900 border-blue-200";
  const inputClass = isDark
    ? "bg-zinc-950 border-zinc-800 text-white placeholder:text-zinc-600 focus:border-blue-500"
    : "bg-white border-zinc-300 text-zinc-900 placeholder:text-zinc-400 focus:border-blue-500";

  return (
    <aside className={`border rounded-2xl overflow-hidden flex flex-col xl:sticky xl:top-4 ${collapsed ? "min-h-0" : "h-[calc(100vh-96px)] max-h-[760px] min-h-[520px]"} ${panelClass}`}>
      <div className={`px-4 py-3 border-b ${isDark ? "border-zinc-800" : "border-zinc-200"}`}>
        <div className="flex items-center justify-between gap-2">
          <div className="flex min-w-0 items-center gap-2">
            <div className="h-8 w-8 shrink-0 rounded-lg bg-blue-500/10 border border-blue-500/20 flex items-center justify-center">
              {collapsed ? <MessageSquare className="h-4 w-4 text-blue-400" /> : <Bot className="h-4 w-4 text-blue-400" />}
            </div>
            <div className="min-w-0">
              <h2 className={`text-sm font-semibold ${titleClass}`}>Project Copilot</h2>
              <p className={`truncate text-[10px] ${mutedClass}`}>{contextLabel}</p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => setCollapsed((value) => !value)}
            className={`rounded-lg border p-1.5 transition-colors ${
              isDark
                ? "border-zinc-700 text-zinc-400 hover:text-white"
                : "border-zinc-200 text-zinc-500 hover:text-zinc-900"
            }`}
            aria-label={collapsed ? "채팅 펼치기" : "채팅 접기"}
          >
            {collapsed ? <ChevronDown className="h-4 w-4" /> : <ChevronUp className="h-4 w-4" />}
          </button>
        </div>
      </div>

      {!collapsed && (
        <>
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-3">
        {!report && (
          <div className={`rounded-xl border p-3 text-[11px] leading-relaxed ${
            isDark ? "border-yellow-500/20 bg-yellow-500/10 text-yellow-200" : "border-yellow-200 bg-yellow-50 text-yellow-800"
          }`}>
            분석 리포트가 아직 없으면 repo URL과 job 상태만 사용합니다. 분석 완료 후 더 정확한 답변을 받을 수 있습니다.
          </div>
        )}

        {messages.map((msg, index) => {
          const isUser = msg.role === "user";
          const Icon = isUser ? UserRound : Bot;
          return (
            <div key={`${msg.role}-${index}`} className={`flex gap-2 ${isUser ? "justify-end" : "justify-start"}`}>
              {!isUser && (
                <div className="mt-1 h-6 w-6 shrink-0 rounded-md bg-blue-500/10 flex items-center justify-center">
                  <Icon className="h-3.5 w-3.5 text-blue-400" />
                </div>
              )}
              <div
                className={`max-w-[88%] whitespace-pre-wrap rounded-2xl border px-3 py-2 text-xs leading-relaxed ${
                  isUser ? messageUserClass : messageAssistantClass
                }`}
              >
                {msg.content}
              </div>
            </div>
          );
        })}

        {loading && (
          <div className="flex items-center gap-2 text-[11px] text-zinc-500">
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
            프로젝트 컨텍스트로 답변을 생성하는 중...
          </div>
        )}
      </div>

      <div className={`border-t p-4 space-y-3 ${isDark ? "border-zinc-800" : "border-zinc-200"}`}>
        <div className="flex flex-wrap gap-1.5">
          {SUGGESTIONS.map((suggestion) => (
            <button
              key={suggestion}
              type="button"
              disabled={!canAsk || loading}
              onClick={() => submit(suggestion)}
              className={`rounded-full border px-2.5 py-1 text-[10px] transition-colors disabled:opacity-40 ${
                isDark
                  ? "border-zinc-700 text-zinc-400 hover:border-blue-500/50 hover:text-blue-300"
                  : "border-zinc-200 text-zinc-500 hover:border-blue-300 hover:text-blue-700"
              }`}
            >
              {suggestion}
            </button>
          ))}
        </div>

        {error && <p className="text-[11px] font-medium text-red-500">{error}</p>}

        <form
          onSubmit={(event) => {
            event.preventDefault();
            void submit();
          }}
          className="flex gap-2"
        >
          <textarea
            ref={inputRef}
            value={input}
            onChange={(event) => setInput(event.target.value)}
            disabled={!canAsk || loading}
            rows={2}
            placeholder={canAsk ? "이 프로젝트에 대해 질문하기..." : "먼저 분석을 시작하세요"}
            className={`min-h-[48px] flex-1 resize-none rounded-xl border px-3 py-2 text-xs outline-none transition-colors disabled:opacity-50 ${inputClass}`}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                void submit();
              }
            }}
          />
          <button
            type="submit"
            disabled={!canAsk || loading || !input.trim()}
            className="h-12 w-12 shrink-0 rounded-xl bg-blue-500 text-white flex items-center justify-center transition-colors hover:bg-blue-400 disabled:bg-zinc-700 disabled:text-zinc-500"
          >
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
          </button>
        </form>
      </div>
        </>
      )}
    </aside>
  );
}
