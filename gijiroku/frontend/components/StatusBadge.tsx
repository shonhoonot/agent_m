import { MeetingStatus, STATUS_LABELS } from "@/lib/api";

const COLORS: Record<MeetingStatus, string> = {
  draft: "bg-slate-100 text-slate-600",
  uploaded: "bg-blue-50 text-blue-700",
  transcribing: "bg-amber-50 text-amber-700",
  generating: "bg-amber-50 text-amber-700",
  ready: "bg-emerald-50 text-emerald-700",
  published: "bg-navy-100 text-navy-700",
  failed: "bg-red-50 text-red-700",
};

export default function StatusBadge({ status }: { status: MeetingStatus }) {
  return (
    <span className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-medium ${COLORS[status]}`}>
      {STATUS_LABELS[status]}
    </span>
  );
}
