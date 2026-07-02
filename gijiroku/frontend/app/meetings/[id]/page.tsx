"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import StatusBadge from "@/components/StatusBadge";
import {
  api,
  downloadExport,
  MeetingDetail,
  MinutesContent,
  PROCESSING_STATUSES,
} from "@/lib/api";

const STAGE_LABELS: Record<string, string> = {
  uploaded: "処理を準備中…",
  transcribing: "文字起こし中…",
  generating: "議事録生成中…",
};

function linesToList(text: string): string[] {
  return text.split("\n").map((s) => s.trim()).filter(Boolean);
}

export default function MeetingDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [meeting, setMeeting] = useState<MeetingDetail | null>(null);
  const [draft, setDraft] = useState<MinutesContent | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [publishing, setPublishing] = useState(false);

  const load = useCallback(async () => {
    try {
      const data = await api<MeetingDetail>(`/api/meetings/${id}`);
      setMeeting(data);
      setDraft((prev) => prev ?? data.minutes);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "読み込みに失敗しました。");
    }
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  // 処理中は3秒ごとにポーリング
  useEffect(() => {
    if (!meeting || !PROCESSING_STATUSES.includes(meeting.status)) return;
    const timer = setInterval(load, 3000);
    return () => clearInterval(timer);
  }, [meeting, load]);

  async function handleSave() {
    if (!draft) return;
    setSaving(true);
    setNotice(null);
    try {
      const updated = await api<MeetingDetail>(`/api/meetings/${id}/minutes`, {
        method: "PATCH",
        body: JSON.stringify({ content: draft }),
      });
      setMeeting(updated);
      setDraft(updated.minutes);
      setNotice("保存しました。");
    } catch (err) {
      setError(err instanceof Error ? err.message : "保存に失敗しました。");
    } finally {
      setSaving(false);
    }
  }

  async function handlePublish() {
    if (!confirm("議事録を公開して Slack に送信します。公開後は編集できません。よろしいですか？")) return;
    setPublishing(true);
    setNotice(null);
    try {
      await handleSaveIfDirty();
      await api(`/api/meetings/${id}/publish`, { method: "POST" });
      await load();
      setNotice("公開し、Slack に通知しました。");
    } catch (err) {
      setError(err instanceof Error ? err.message : "公開に失敗しました。");
    } finally {
      setPublishing(false);
    }
  }

  async function handleSaveIfDirty() {
    if (draft && JSON.stringify(draft) !== JSON.stringify(meeting?.minutes)) {
      await api(`/api/meetings/${id}/minutes`, {
        method: "PATCH",
        body: JSON.stringify({ content: draft }),
      });
    }
  }

  if (error && !meeting) return <p className="text-sm text-red-600">{error}</p>;
  if (!meeting) return <p className="text-slate-400">読み込み中…</p>;

  const processing = PROCESSING_STATUSES.includes(meeting.status);
  const editable = meeting.status === "ready";
  const published = meeting.status === "published";

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-navy-900">{meeting.title}</h1>
          <p className="mt-1 text-sm text-slate-500">{meeting.meeting_date ?? ""}</p>
        </div>
        <StatusBadge status={meeting.status} />
      </div>

      {error && <p className="mb-4 text-sm text-red-600">{error}</p>}
      {notice && <p className="mb-4 text-sm text-emerald-700">{notice}</p>}

      {processing && (
        <div className="flex flex-col items-center rounded-lg border border-slate-200 py-16">
          <div className="h-10 w-10 animate-spin rounded-full border-4 border-slate-200 border-t-navy-600" />
          <p className="mt-4 font-medium text-navy-700">
            {STAGE_LABELS[meeting.status] ?? "処理中…"}
          </p>
          <p className="mt-1 text-sm text-slate-400">このページは自動的に更新されます</p>
        </div>
      )}

      {meeting.status === "failed" && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-6">
          <p className="font-medium text-red-700">処理に失敗しました</p>
          <p className="mt-1 text-sm text-red-600">{meeting.error_detail}</p>
        </div>
      )}

      {meeting.status === "draft" && (
        <div className="rounded-lg border border-slate-200 p-6 text-sm text-slate-500">
          音声または文字起こしがまだ登録されていません。
        </div>
      )}

      {(editable || published) && draft && (
        <MinutesEditor
          draft={draft}
          setDraft={setDraft}
          readOnly={published}
        />
      )}

      {(editable || published) && (
        <div className="sticky bottom-0 mt-6 flex items-center justify-end gap-3 border-t border-slate-200 bg-white py-4">
          <button className="btn-secondary" onClick={() => downloadExport(meeting.id, "md")}>
            .md ダウンロード
          </button>
          <button className="btn-secondary" onClick={() => downloadExport(meeting.id, "docx")}>
            .docx ダウンロード
          </button>
          {editable && (
            <>
              <button className="btn-secondary" onClick={handleSave} disabled={saving}>
                {saving ? "保存中…" : "下書き保存"}
              </button>
              <button className="btn-primary" onClick={handlePublish} disabled={publishing}>
                {publishing ? "公開中…" : "公開して Slack に送信"}
              </button>
            </>
          )}
        </div>
      )}
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-lg border border-slate-200 p-5">
      <h2 className="mb-3 border-l-4 border-navy-600 pl-2 text-base font-bold text-navy-800">
        {title}
      </h2>
      {children}
    </section>
  );
}

function MinutesEditor({
  draft,
  setDraft,
  readOnly,
}: {
  draft: MinutesContent;
  setDraft: (m: MinutesContent) => void;
  readOnly: boolean;
}) {
  const g = draft.kaigi_gaiyou;
  const set = (patch: Partial<MinutesContent>) => setDraft({ ...draft, ...patch });
  const ro = readOnly ? { readOnly: true, className: "input bg-slate-50" } : { className: "input" };

  return (
    <div className="space-y-5">
      <Section title="会議概要">
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="label">会議名</label>
            <input {...ro} value={g.kaigi_mei}
              onChange={(e) => set({ kaigi_gaiyou: { ...g, kaigi_mei: e.target.value } })} />
          </div>
          <div>
            <label className="label">日時</label>
            <input {...ro} value={g.nichiji}
              onChange={(e) => set({ kaigi_gaiyou: { ...g, nichiji: e.target.value } })} />
          </div>
          <div>
            <label className="label">場所</label>
            <input {...ro} value={g.basho}
              onChange={(e) => set({ kaigi_gaiyou: { ...g, basho: e.target.value } })} />
          </div>
          <div>
            <label className="label">書記</label>
            <input className="input bg-slate-50" readOnly value="AI議事録エージェント" />
          </div>
          <div>
            <label className="label">出席者（読点区切り）</label>
            <input {...ro} value={g.shussekisha.join("、")}
              onChange={(e) =>
                set({ kaigi_gaiyou: { ...g, shussekisha: e.target.value.split("、").map((s) => s.trim()).filter(Boolean) } })
              } />
          </div>
          <div>
            <label className="label">欠席者（読点区切り）</label>
            <input {...ro} value={g.kessekisha.join("、")}
              onChange={(e) =>
                set({ kaigi_gaiyou: { ...g, kessekisha: e.target.value.split("、").map((s) => s.trim()).filter(Boolean) } })
              } />
          </div>
        </div>
      </Section>

      <Section title="議題">
        <textarea {...ro} rows={3} value={draft.gidai.join("\n")}
          onChange={(e) => set({ gidai: linesToList(e.target.value) })}
          placeholder="1行に1議題" />
      </Section>

      <Section title="議論内容">
        <div className="space-y-4">
          {draft.giron_naiyou.map((topic, ti) => (
            <div key={ti} className="rounded border border-slate-100 bg-slate-50/50 p-3">
              <label className="label">議題</label>
              <input {...ro} value={topic.gidai}
                onChange={(e) => {
                  const next = [...draft.giron_naiyou];
                  next[ti] = { ...topic, gidai: e.target.value };
                  set({ giron_naiyou: next });
                }} />
              <label className="label mt-2">要点（「発言者：内容」で1行ずつ）</label>
              <textarea {...ro} rows={Math.max(3, topic.youten.length + 1)}
                value={topic.youten.map((y) => (y.hatsugensha ? `${y.hatsugensha}：${y.naiyou}` : y.naiyou)).join("\n")}
                onChange={(e) => {
                  const youten = linesToList(e.target.value).map((line) => {
                    const idx = line.indexOf("：");
                    return idx > 0
                      ? { hatsugensha: line.slice(0, idx), naiyou: line.slice(idx + 1) }
                      : { hatsugensha: "", naiyou: line };
                  });
                  const next = [...draft.giron_naiyou];
                  next[ti] = { ...topic, youten };
                  set({ giron_naiyou: next });
                }} />
            </div>
          ))}
          {!readOnly && (
            <button type="button" className="btn-secondary"
              onClick={() => set({ giron_naiyou: [...draft.giron_naiyou, { gidai: "", youten: [] }] })}>
              ＋ 議題を追加
            </button>
          )}
        </div>
      </Section>

      <Section title="決定事項">
        <textarea {...ro} rows={3} value={draft.kettei_jikou.join("\n")}
          onChange={(e) => set({ kettei_jikou: linesToList(e.target.value) })}
          placeholder="1行に1件" />
      </Section>

      <Section title="アクションアイテム">
        <table className="w-full text-sm">
          <thead className="text-left text-slate-500">
            <tr>
              <th className="w-12 pb-2">No.</th>
              <th className="pb-2">内容</th>
              <th className="w-32 pb-2">担当者</th>
              <th className="w-32 pb-2">期限</th>
              {!readOnly && <th className="w-10 pb-2" />}
            </tr>
          </thead>
          <tbody>
            {draft.action_items.map((item, i) => (
              <tr key={i}>
                <td className="pr-2 pb-2">
                  <input {...ro} type="number" value={item.no}
                    onChange={(e) => {
                      const next = [...draft.action_items];
                      next[i] = { ...item, no: Number(e.target.value) };
                      set({ action_items: next });
                    }} />
                </td>
                <td className="pr-2 pb-2">
                  <input {...ro} value={item.naiyou}
                    onChange={(e) => {
                      const next = [...draft.action_items];
                      next[i] = { ...item, naiyou: e.target.value };
                      set({ action_items: next });
                    }} />
                </td>
                <td className="pr-2 pb-2">
                  <input {...ro} value={item.tantousha}
                    onChange={(e) => {
                      const next = [...draft.action_items];
                      next[i] = { ...item, tantousha: e.target.value };
                      set({ action_items: next });
                    }} />
                </td>
                <td className="pr-2 pb-2">
                  <input {...ro} value={item.kigen}
                    onChange={(e) => {
                      const next = [...draft.action_items];
                      next[i] = { ...item, kigen: e.target.value };
                      set({ action_items: next });
                    }} />
                </td>
                {!readOnly && (
                  <td className="pb-2">
                    <button type="button" className="text-red-500 hover:text-red-700"
                      onClick={() => set({ action_items: draft.action_items.filter((_, j) => j !== i) })}>
                      ✕
                    </button>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
        {!readOnly && (
          <button type="button" className="btn-secondary mt-2"
            onClick={() =>
              set({
                action_items: [
                  ...draft.action_items,
                  { no: draft.action_items.length + 1, naiyou: "", tantousha: "未定", kigen: "未定" },
                ],
              })
            }>
            ＋ 行を追加
          </button>
        )}
      </Section>

      <Section title="次回会議">
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="label">日時</label>
            <input {...ro} value={draft.jikai_kaigi.nichiji}
              onChange={(e) => set({ jikai_kaigi: { ...draft.jikai_kaigi, nichiji: e.target.value } })} />
          </div>
          <div>
            <label className="label">議題（予定・読点区切り）</label>
            <input {...ro} value={draft.jikai_kaigi.gidai_yotei.join("、")}
              onChange={(e) =>
                set({
                  jikai_kaigi: {
                    ...draft.jikai_kaigi,
                    gidai_yotei: e.target.value.split("、").map((s) => s.trim()).filter(Boolean),
                  },
                })
              } />
          </div>
        </div>
      </Section>

      <Section title="保留・継続検討事項">
        <textarea {...ro} rows={2} value={draft.horyuu_jikou.join("\n")}
          onChange={(e) => set({ horyuu_jikou: linesToList(e.target.value) })}
          placeholder="1行に1件" />
      </Section>
    </div>
  );
}
