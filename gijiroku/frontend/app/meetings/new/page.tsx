"use client";

import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { api, API_BASE, getToken, Meeting } from "@/lib/api";

export default function NewMeetingPage() {
  const router = useRouter();
  const [title, setTitle] = useState("");
  const [meetingDate, setMeetingDate] = useState("");
  const [location, setLocation] = useState("");
  const [attendees, setAttendees] = useState("");
  const [absentees, setAbsentees] = useState("");
  const [mode, setMode] = useState<"audio" | "transcript">("audio");
  const [file, setFile] = useState<File | null>(null);
  const [transcript, setTranscript] = useState("");
  const [dragOver, setDragOver] = useState(false);
  const [progress, setProgress] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);

  function pickFile(f: File | undefined) {
    if (!f) return;
    const ok = [".mp3", ".m4a", ".wav"].some((ext) => f.name.toLowerCase().endsWith(ext));
    if (!ok) {
      setError("対応形式は .mp3 / .m4a / .wav のみです。");
      return;
    }
    if (f.size > 200 * 1024 * 1024) {
      setError("ファイルサイズの上限は 200MB です。");
      return;
    }
    setError(null);
    setFile(f);
  }

  function uploadWithProgress(meetingId: string, f: File): Promise<void> {
    // fetch では進捗が取れないため XHR でアップロード
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open("POST", `${API_BASE}/api/meetings/${meetingId}/audio`);
      const token = getToken();
      if (token) xhr.setRequestHeader("Authorization", `Bearer ${token}`);
      xhr.upload.onprogress = (e) => {
        if (e.lengthComputable) setProgress(Math.round((e.loaded / e.total) * 100));
      };
      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) resolve();
        else {
          try {
            reject(new Error(JSON.parse(xhr.responseText).detail ?? "アップロードに失敗しました。"));
          } catch {
            reject(new Error("アップロードに失敗しました。"));
          }
        }
      };
      xhr.onerror = () => reject(new Error("ネットワークエラーが発生しました。"));
      const form = new FormData();
      form.append("file", f);
      xhr.send(form);
    });
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (mode === "audio" && !file) {
      setError("音声ファイルを選択してください。");
      return;
    }
    if (mode === "transcript" && !transcript.trim()) {
      setError("文字起こしテキストを入力してください。");
      return;
    }
    setSubmitting(true);
    try {
      const meeting = await api<Meeting>("/api/meetings", {
        method: "POST",
        body: JSON.stringify({
          title,
          meeting_date: meetingDate || null,
          location: location || null,
          attendees: attendees.split(/[、,]/).map((s) => s.trim()).filter(Boolean),
          absentees: absentees.split(/[、,]/).map((s) => s.trim()).filter(Boolean),
        }),
      });
      if (mode === "audio" && file) {
        setProgress(0);
        await uploadWithProgress(meeting.id, file);
      } else {
        await api(`/api/meetings/${meeting.id}/transcript`, {
          method: "POST",
          body: JSON.stringify({ text: transcript }),
        });
      }
      router.push(`/meetings/${meeting.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "作成に失敗しました。");
      setSubmitting(false);
      setProgress(null);
    }
  }

  return (
    <div className="mx-auto max-w-2xl">
      <h1 className="mb-6 text-2xl font-bold text-navy-900">会議の新規作成</h1>
      <form onSubmit={handleSubmit} className="space-y-5">
        <div>
          <label className="label">会議名 *</label>
          <input className="input" required value={title} onChange={(e) => setTitle(e.target.value)} />
        </div>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="label">日時</label>
            <input
              className="input"
              placeholder="2026年06月10日（水）10:00〜11:00"
              value={meetingDate}
              onChange={(e) => setMeetingDate(e.target.value)}
            />
          </div>
          <div>
            <label className="label">場所</label>
            <input
              className="input"
              placeholder="第1会議室 / オンライン"
              value={location}
              onChange={(e) => setLocation(e.target.value)}
            />
          </div>
        </div>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="label">出席者（読点区切り）</label>
            <input className="input" placeholder="田中、佐藤、鈴木" value={attendees} onChange={(e) => setAttendees(e.target.value)} />
          </div>
          <div>
            <label className="label">欠席者（読点区切り）</label>
            <input className="input" value={absentees} onChange={(e) => setAbsentees(e.target.value)} />
          </div>
        </div>

        <div className="flex gap-4 border-b border-slate-200 pb-2 text-sm">
          <button
            type="button"
            className={mode === "audio" ? "font-bold text-navy-700" : "text-slate-500"}
            onClick={() => setMode("audio")}
          >
            音声をアップロード
          </button>
          <button
            type="button"
            className={mode === "transcript" ? "font-bold text-navy-700" : "text-slate-500"}
            onClick={() => setMode("transcript")}
          >
            文字起こしを貼り付け
          </button>
        </div>

        {mode === "audio" ? (
          <div
            className={`flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed px-6 py-10 text-center text-sm ${
              dragOver ? "border-navy-600 bg-navy-50" : "border-slate-300"
            }`}
            onClick={() => fileInput.current?.click()}
            onDragOver={(e) => {
              e.preventDefault();
              setDragOver(true);
            }}
            onDragLeave={() => setDragOver(false)}
            onDrop={(e) => {
              e.preventDefault();
              setDragOver(false);
              pickFile(e.dataTransfer.files[0]);
            }}
          >
            <input
              ref={fileInput}
              type="file"
              accept=".mp3,.m4a,.wav"
              className="hidden"
              onChange={(e) => pickFile(e.target.files?.[0])}
            />
            {file ? (
              <p className="font-medium text-navy-700">
                {file.name}（{(file.size / 1024 / 1024).toFixed(1)} MB）
              </p>
            ) : (
              <>
                <p className="font-medium text-slate-600">
                  音声ファイルをドラッグ＆ドロップ、またはクリックして選択
                </p>
                <p className="mt-1 text-slate-400">.mp3 / .m4a / .wav（最大 200MB）</p>
              </>
            )}
          </div>
        ) : (
          <textarea
            className="input min-h-48"
            placeholder="会議の文字起こしテキストを貼り付けてください"
            value={transcript}
            onChange={(e) => setTranscript(e.target.value)}
          />
        )}

        {progress !== null && (
          <div>
            <div className="h-2 overflow-hidden rounded bg-slate-100">
              <div className="h-full bg-navy-600 transition-all" style={{ width: `${progress}%` }} />
            </div>
            <p className="mt-1 text-right text-xs text-slate-500">{progress}%</p>
          </div>
        )}

        {error && <p className="text-sm text-red-600">{error}</p>}

        <button type="submit" className="btn-primary w-full" disabled={submitting}>
          {submitting ? "処理を開始しています…" : "作成して処理を開始"}
        </button>
      </form>
    </div>
  );
}
