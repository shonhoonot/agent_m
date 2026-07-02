"use client";

import { useCallback, useEffect, useState } from "react";
import StatusBadge from "@/components/StatusBadge";
import { api, Meeting } from "@/lib/api";

interface MeetingList {
  items: Meeting[];
  total: number;
  page: number;
  page_size: number;
}

export default function MeetingsPage() {
  const [data, setData] = useState<MeetingList | null>(null);
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const params = new URLSearchParams({ page: String(page), page_size: "20" });
      if (q) params.set("q", q);
      setData(await api<MeetingList>(`/api/meetings?${params}`));
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "読み込みに失敗しました。");
    }
  }, [page, q]);

  useEffect(() => {
    load();
  }, [load]);

  const totalPages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-bold text-navy-900">会議一覧</h1>
        <a href="/meetings/new" className="btn-primary">＋ 新規作成</a>
      </div>

      <form
        className="mb-4 flex gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          setPage(1);
          load();
        }}
      >
        <input
          className="input max-w-xs"
          placeholder="会議名・日時で検索"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
        <button type="submit" className="btn-secondary">検索</button>
      </form>

      {error && <p className="mb-4 text-sm text-red-600">{error}</p>}

      <div className="overflow-hidden rounded-lg border border-slate-200">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-slate-600">
            <tr>
              <th className="px-4 py-3 font-medium">会議名</th>
              <th className="px-4 py-3 font-medium">日時</th>
              <th className="px-4 py-3 font-medium">ステータス</th>
              <th className="px-4 py-3 font-medium">操作</th>
            </tr>
          </thead>
          <tbody>
            {data?.items.map((m) => (
              <tr key={m.id} className="border-t border-slate-100 hover:bg-slate-50">
                <td className="px-4 py-3 font-medium text-navy-800">{m.title}</td>
                <td className="px-4 py-3 text-slate-600">{m.meeting_date ?? "—"}</td>
                <td className="px-4 py-3"><StatusBadge status={m.status} /></td>
                <td className="px-4 py-3">
                  <a href={`/meetings/${m.id}`} className="text-navy-600 hover:underline">
                    詳細
                  </a>
                </td>
              </tr>
            ))}
            {data && data.items.length === 0 && (
              <tr>
                <td colSpan={4} className="px-4 py-8 text-center text-slate-400">
                  会議がありません。「新規作成」から始めてください。
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="mt-4 flex items-center justify-end gap-3 text-sm text-slate-600">
        <button
          className="btn-secondary"
          disabled={page <= 1}
          onClick={() => setPage((p) => p - 1)}
        >
          前へ
        </button>
        <span>{page} / {totalPages}</span>
        <button
          className="btn-secondary"
          disabled={page >= totalPages}
          onClick={() => setPage((p) => p + 1)}
        >
          次へ
        </button>
      </div>
    </div>
  );
}
