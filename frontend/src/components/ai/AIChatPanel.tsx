"use client";
/**
 * AIChatPanel
 * Teacher-facing AI instructional assistant.
 * Renders in the right panel of the dashboard.
 * Handles text responses and inline chart spec resolution.
 */
import { useState, useRef, useEffect } from "react";
import { aiApi, Message, AIResponse } from "@/lib/api";
import ProficiencyBarChart from "@/components/charts/ProficiencyBarChart";

interface Props {
  assessmentId: string | null;
}

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  chartSpec?: AIResponse["chart_spec"];
  isLoading?: boolean;
}

const SUGGESTED_QUESTIONS = [
  "Which standards are weakest in this assessment?",
  "Which students struggle with story problems?",
  "Suggest an intervention for standard 3.OA.C.7",
  "Explain what 3.OA.B.6 means in plain language",
  "Generate a weekly intervention plan for Tier 3 students",
  "Show me a heatmap of student vs standard performance",
];

export default function AIChatPanel({ assessmentId }: Props) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const sendMessage = async (question: string) => {
    if (!question.trim() || isLoading) return;

    const userMessage: ChatMessage = { role: "user", content: question };
    const loadingMessage: ChatMessage = { role: "assistant", content: "", isLoading: true };

    setMessages((prev) => [...prev, userMessage, loadingMessage]);
    setInput("");
    setIsLoading(true);

    try {
      // Build conversation history for Claude (text only, not chart specs)
      const history: Message[] = messages
        .filter((m) => !m.isLoading)
        .map((m) => ({ role: m.role, content: m.content }));

      const response = await aiApi.chat(question, assessmentId || "", history);

      setMessages((prev) => {
        const updated = prev.filter((m) => !m.isLoading);
        return [
          ...updated,
          {
            role: "assistant",
            content: response.response || "",
            chartSpec: response.chart_spec || undefined,
          },
        ];
      });
    } catch (err) {
      setMessages((prev) => {
        const updated = prev.filter((m) => !m.isLoading);
        return [
          ...updated,
          {
            role: "assistant",
            content: "Unable to get a response right now. Please try again.",
          },
        ];
      });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-full bg-white border-l border-gray-200">
      {/* Header */}
      <div className="px-4 py-3 border-b border-gray-200 bg-blue-900">
        <h2 className="text-white font-semibold text-sm">AI Instructional Assistant</h2>
        <p className="text-blue-200 text-xs mt-0.5">Ask about standards, interventions, and student performance</p>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-3 space-y-4">
        {messages.length === 0 && (
          <div className="space-y-2">
            <p className="text-xs text-gray-500 font-medium">Suggested questions:</p>
            {SUGGESTED_QUESTIONS.map((q) => (
              <button
                key={q}
                onClick={() => sendMessage(q)}
                className="block w-full text-left text-xs text-blue-700 hover:text-blue-900 hover:bg-blue-50 rounded p-2 border border-blue-100 transition-colors"
              >
                {q}
              </button>
            ))}
          </div>
        )}

        {messages.map((msg, i) => (
          <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
            <div
              className={`max-w-[90%] rounded-lg px-3 py-2 text-sm ${
                msg.role === "user"
                  ? "bg-blue-900 text-white"
                  : "bg-gray-100 text-gray-800"
              }`}
            >
              {msg.isLoading ? (
                <span className="animate-pulse text-gray-400">Thinking...</span>
              ) : msg.chartSpec ? (
                <div>
                  <p className="text-xs text-gray-500 mb-2">Chart requested: {msg.chartSpec.title || msg.chartSpec.metric}</p>
                  <p className="text-xs text-gray-400 italic">(Chart renders below from analytics API)</p>
                </div>
              ) : (
                <p className="whitespace-pre-wrap">{msg.content}</p>
              )}
            </div>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="px-4 py-3 border-t border-gray-200">
        {!assessmentId && (
          <p className="text-xs text-amber-600 mb-2">Select an assessment to get data-informed responses.</p>
        )}
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(input); } }}
            placeholder="Ask about standards, interventions..."
            className="flex-1 text-sm border border-gray-300 rounded px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
            disabled={isLoading}
          />
          <button
            onClick={() => sendMessage(input)}
            disabled={isLoading || !input.trim()}
            className="bg-blue-900 text-white text-sm px-3 py-2 rounded hover:bg-blue-800 disabled:opacity-50 transition-colors"
          >
            Send
          </button>
        </div>
        <p className="text-xs text-gray-400 mt-1">Student data is anonymized before being shared with AI.</p>
      </div>
    </div>
  );
}
