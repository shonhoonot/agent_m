import type { Metadata } from "next";
import { Noto_Sans_JP } from "next/font/google";
import "./globals.css";

const notoSansJP = Noto_Sans_JP({ subsets: ["latin"], weight: ["400", "500", "700"] });

export const metadata: Metadata = {
  title: "議事録 AI Agent",
  description: "会議音声から議事録を自動生成",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ja">
      <body className={notoSansJP.className}>
        <header className="border-b border-slate-200 bg-navy-900">
          <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-3">
            <a href="/meetings" className="text-lg font-bold text-white">
              📝 議事録 AI Agent
            </a>
            <nav className="flex gap-4 text-sm text-slate-300">
              <a href="/meetings" className="hover:text-white">会議一覧</a>
              <a href="/meetings/new" className="hover:text-white">新規作成</a>
            </nav>
          </div>
        </header>
        <main className="mx-auto max-w-5xl px-4 py-8">{children}</main>
      </body>
    </html>
  );
}
