/**
 * API client with automatic JWT injection and refresh token rotation.
 * All requests are scoped to the authenticated user's tenant automatically.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

let accessToken: string | null = null;

export function setAccessToken(token: string) {
  accessToken = token;
}

export function clearAccessToken() {
  accessToken = null;
}

interface FetchOptions extends RequestInit {
  skipAuth?: boolean;
}

async function refreshAccessToken(): Promise<string | null> {
  try {
    const res = await fetch(`${API_BASE}/auth/refresh`, {
      method: "POST",
      credentials: "include", // Send refresh_token cookie
    });
    if (!res.ok) return null;
    const data = await res.json();
    setAccessToken(data.access_token);
    return data.access_token;
  } catch {
    return null;
  }
}

export async function apiFetch<T = unknown>(
  path: string,
  options: FetchOptions = {}
): Promise<T> {
  const { skipAuth = false, ...fetchOptions } = options;

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(fetchOptions.headers as Record<string, string>),
  };

  if (!skipAuth && accessToken) {
    headers["Authorization"] = `Bearer ${accessToken}`;
  }

  let response = await fetch(`${API_BASE}${path}`, {
    ...fetchOptions,
    headers,
    credentials: "include",
  });

  // If 401, attempt token refresh once
  if (response.status === 401 && !skipAuth) {
    const newToken = await refreshAccessToken();
    if (newToken) {
      headers["Authorization"] = `Bearer ${newToken}`;
      response = await fetch(`${API_BASE}${path}`, {
        ...fetchOptions,
        headers,
        credentials: "include",
      });
    } else {
      // Refresh failed - redirect to login
      if (typeof window !== "undefined") {
        window.location.href = "/login";
      }
      throw new Error("Session expired");
    }
  }

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Unknown error" }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json() as Promise<T>;
}

// ── Analytics API ────────────────────────────────────────────────────────────
export const analyticsApi = {
  proficiencyByStandard: (assessmentId: string) =>
    apiFetch<ChartResponse>(`/analytics/proficiency_by_standard?assessment_id=${assessmentId}`),

  studentHeatmap: (assessmentId: string) =>
    apiFetch<ChartResponse>(`/analytics/student_heatmap?assessment_id=${assessmentId}`),

  storyProblemAnalysis: (assessmentId: string) =>
    apiFetch<ChartResponse>(`/analytics/story_problem_analysis?assessment_id=${assessmentId}`),

  progressOverTime: (classroomId: string) =>
    apiFetch<ChartResponse>(`/analytics/progress_over_time?classroom_id=${classroomId}`),

  interventionGroups: (assessmentId: string) =>
    apiFetch<ChartResponse>(`/analytics/intervention_groups?assessment_id=${assessmentId}`),
};

// ── Assessment API ────────────────────────────────────────────────────────────
export const assessmentApi = {
  list: () => apiFetch<Assessment[]>("/assessments"),

  upload: async (mathFile: File, metadataFile: File, classroomId: string) => {
    const formData = new FormData();
    formData.append("math_csv", mathFile);
    formData.append("metadata_csv", metadataFile);
    formData.append("classroom_id", classroomId);

    const headers: Record<string, string> = {};
    if (accessToken) headers["Authorization"] = `Bearer ${accessToken}`;

    const res = await fetch(`${API_BASE}/assessments/upload/math`, {
      method: "POST",
      headers,
      body: formData,
      credentials: "include",
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Upload failed");
    }
    return res.json();
  },
};

// ── AI API ────────────────────────────────────────────────────────────────────
export const aiApi = {
  chat: (question: string, assessmentId: string, conversationHistory: Message[]) =>
    apiFetch<AIResponse>("/ai/chat", {
      method: "POST",
      body: JSON.stringify({ question, assessment_id: assessmentId, conversation_history: conversationHistory }),
    }),
};

// ── Types ─────────────────────────────────────────────────────────────────────
export interface ChartResponse {
  data: unknown[];
  chart_type: string;
  suppressed?: boolean;
}

export interface Assessment {
  id: string;
  name: string;
  assessment_type: "math" | "literacy";
  unit?: string;
  week_of?: string;
  classroom_id: string;
}

export interface AIResponse {
  response: string | null;
  chart_spec: {
    chart_type: string;
    metric: string;
    group_by: string;
    color_metric: string;
    title?: string;
  } | null;
}

export interface Message {
  role: "user" | "assistant";
  content: string;
}
