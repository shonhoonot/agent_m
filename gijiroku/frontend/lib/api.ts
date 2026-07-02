export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type MeetingStatus =
  | "draft"
  | "uploaded"
  | "transcribing"
  | "generating"
  | "ready"
  | "published"
  | "failed";

export const STATUS_LABELS: Record<MeetingStatus, string> = {
  draft: "下書き",
  uploaded: "アップロード済み",
  transcribing: "文字起こし中",
  generating: "議事録生成中",
  ready: "確認待ち",
  published: "公開済み",
  failed: "失敗",
};

export const PROCESSING_STATUSES: MeetingStatus[] = [
  "uploaded",
  "transcribing",
  "generating",
];

export interface Youten {
  hatsugensha: string;
  naiyou: string;
}

export interface GironNaiyou {
  gidai: string;
  youten: Youten[];
}

export interface ActionItem {
  no: number;
  naiyou: string;
  tantousha: string;
  kigen: string;
}

export interface MinutesContent {
  kaigi_gaiyou: {
    kaigi_mei: string;
    nichiji: string;
    basho: string;
    shussekisha: string[];
    kessekisha: string[];
  };
  gidai: string[];
  giron_naiyou: GironNaiyou[];
  kettei_jikou: string[];
  action_items: ActionItem[];
  jikai_kaigi: { nichiji: string; gidai_yotei: string[] };
  horyuu_jikou: string[];
}

export interface Meeting {
  id: string;
  title: string;
  meeting_date: string | null;
  location: string | null;
  attendees: string[] | null;
  absentees: string[] | null;
  status: MeetingStatus;
  error_detail: string | null;
  created_at: string;
  published_at: string | null;
}

export interface MeetingDetail extends Meeting {
  transcript_raw: string | null;
  transcript_cleaned: string | null;
  minutes: MinutesContent | null;
  minutes_version: number | null;
  action_items: {
    no: number;
    content: string;
    assignee: string;
    due_date: string;
    done: boolean;
  }[];
}

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("gijiroku_token");
}

export function setToken(token: string) {
  localStorage.setItem("gijiroku_token", token);
}

export function clearToken() {
  localStorage.removeItem("gijiroku_token");
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    ...(options.body && !(options.body instanceof FormData)
      ? { "Content-Type": "application/json" }
      : {}),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...((options.headers as Record<string, string>) ?? {}),
  };
  const resp = await fetch(`${API_BASE}${path}`, { ...options, headers });
  if (resp.status === 401 && typeof window !== "undefined") {
    clearToken();
    window.location.href = "/login";
    throw new ApiError(401, "認証が切れました。再度ログインしてください。");
  }
  if (!resp.ok) {
    let detail = "エラーが発生しました。";
    try {
      const data = await resp.json();
      if (typeof data.detail === "string") detail = data.detail;
    } catch {
      /* JSON 以外のレスポンスは既定メッセージ */
    }
    throw new ApiError(resp.status, detail);
  }
  return resp.json() as Promise<T>;
}

export async function downloadExport(meetingId: string, format: "docx" | "md") {
  const token = getToken();
  const resp = await fetch(`${API_BASE}/api/meetings/${meetingId}/export?format=${format}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!resp.ok) throw new ApiError(resp.status, "ダウンロードに失敗しました。");
  const blob = await resp.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `gijiroku_${meetingId}.${format}`;
  a.click();
  URL.revokeObjectURL(url);
}
