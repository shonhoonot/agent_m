# 議事録 AI Agent / Japanese Meeting Minutes AI

会議の音声録音から、日本のビジネス慣例に沿ったプロフェッショナルな議事録を自動生成する SaaS ツールです。アクションアイテム抽出と Slack 配信に対応しています。

A SaaS tool that converts meeting audio recordings into professional Japanese meeting minutes (議事録), with action item extraction and Slack distribution.

---

## アーキテクチャ / Architecture

```mermaid
flowchart LR
    subgraph Frontend["Next.js 14 (App Router)"]
        UI["日本語 UI<br/>ログイン / 会議一覧 / 編集"]
    end

    subgraph Backend["FastAPI (Python 3.12, async)"]
        API["REST API + JWT 認証"]
        PIPE["非同期パイプライン<br/>(BackgroundTasks)"]
        SM["ステータス状態遷移<br/>uploaded→transcribing→<br/>generating→ready→published"]
    end

    subgraph External["External APIs"]
        WHISPER["OpenAI Whisper API<br/>(whisper-1, ja)"]
        CLAUDE["Anthropic Claude API<br/>Pass1: クリーンアップ<br/>Pass2: 議事録 JSON (構造化出力)"]
        SLACK["Slack Incoming Webhook"]
    end

    DB[("PostgreSQL<br/>SQLAlchemy 2.0 async<br/>Alembic")]

    UI -->|"音声 / 文字起こし"| API
    API --> PIPE
    PIPE -->|"25MB超は分割"| WHISPER
    PIPE --> CLAUDE
    API --> DB
    PIPE --> DB
    API -->|"公開時"| SLACK
    UI <-->|"3秒ポーリング"| API
```

### 処理フロー / Processing Flow

1. ログイン → 音声アップロード（`.mp3` / `.m4a` / `.wav`、最大 200MB）または文字起こし貼り付け
2. 25MB 超の音声は自動分割し Whisper API（`language="ja"`）で文字起こし
3. Claude が 2 パスで処理:
   - **Pass 1**: 誤変換修正・フィラー除去・話者ラベル付け
   - **Pass 2**: 構造化出力（JSON Schema 強制）で正式な議事録 JSON を生成
4. Web UI で確認・編集 → 「公開して Slack に送信」
5. `.docx` / `.md` でダウンロード可能

---

## セットアップ / Setup

### ローカル開発（Docker Compose）/ Local Development

```bash
cd gijiroku
cp .env.example .env   # API キー等を設定 / fill in your API keys
docker compose up --build
```

- Frontend: http://localhost:3000
- Backend API (OpenAPI docs): http://localhost:8000/docs

初期ユーザーの作成 / Create the first user:

```bash
docker compose exec backend python -m scripts.create_user admin@example.com yourpassword "管理者"
```

### 手動セットアップ / Manual Setup

**Backend** (Python 3.12, requires `ffmpeg` for audio chunking):

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
export DATABASE_URL=postgresql+asyncpg://gijiroku:gijiroku@localhost:5432/gijiroku
alembic upgrade head
python -m scripts.create_user admin@example.com yourpassword "管理者"
uvicorn app.main:app --reload
```

**Frontend** (Node 20+):

```bash
cd frontend
npm install
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
```

### テスト / Tests

```bash
cd backend
python -m pytest
```

---

## 環境変数 / Environment Variables

| 変数 / Variable | 説明 / Description |
|---|---|
| `ANTHROPIC_API_KEY` | Anthropic Claude API キー |
| `OPENAI_API_KEY` | OpenAI（Whisper）API キー |
| `DATABASE_URL` | `postgresql+asyncpg://user:pass@host:5432/db` |
| `SLACK_WEBHOOK_URL` | Slack Incoming Webhook URL |
| `JWT_SECRET` | JWT 署名シークレット（32文字以上推奨） |
| `ANTHROPIC_MODEL` | 既定: `claude-sonnet-4-6`（注: 仕様の `claude-sonnet-4-20250514` は 2026-06-15 に廃止のため後継モデルを既定とした） |
| `APP_BASE_URL` | Slack 通知に載せるフロントエンドの URL |
| `CORS_ORIGINS` | 許可するオリジン（カンマ区切り） |

---

## Azure Container Apps へのデプロイ / Deploy to Azure Container Apps

前提 / Prerequisites: `az login` 済み、PostgreSQL（例: Azure Database for PostgreSQL Flexible Server）作成済み。

```bash
cd gijiroku
export ANTHROPIC_API_KEY=sk-ant-...
export OPENAI_API_KEY=sk-...
export DATABASE_URL=postgresql+asyncpg://...
export JWT_SECRET=$(openssl rand -hex 32)
export SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...

bash deploy/azure-deploy.sh
```

スクリプトは `az acr build` で両イメージをビルドし、Container Apps（external ingress、シークレットは Container Apps secrets 管理）へデプロイします。初回実行後、出力されたバックエンド URL を `NEXT_PUBLIC_API_URL` に設定して再実行し、フロントエンドのビルドに埋め込んでください。

The script builds both images with `az acr build` and deploys them to Azure Container Apps with secrets stored as Container Apps secrets. After the first run, re-run with `NEXT_PUBLIC_API_URL` set to the printed backend URL so it gets baked into the frontend build.

---

## API エンドポイント / API Endpoints

```
POST   /api/auth/login                    # ログイン → JWT
POST   /api/meetings                      # 会議作成
POST   /api/meetings/{id}/audio           # 音声アップロード → 非同期パイプライン開始
POST   /api/meetings/{id}/transcript      # 文字起こし直接登録（Whisper スキップ）
GET    /api/meetings/{id}                 # ステータス + 結果（ポーリング用）
PATCH  /api/meetings/{id}/minutes         # 編集内容の保存（バージョン管理）
POST   /api/meetings/{id}/publish         # 公開 + Slack 通知 + ロック
GET    /api/meetings                      # 一覧（ページネーション・検索）
GET    /api/meetings/{id}/export?format=docx|md
```

ステータス遷移 / Status states:
`draft → uploaded → transcribing → generating → ready → published`（+ `failed`、文字起こし貼り付け時は `draft → generating`）

---

## プロジェクト構成 / Project Layout

```
gijiroku/
├── backend/            # FastAPI + SQLAlchemy 2.0 async + Alembic
│   ├── app/
│   │   ├── routers/    # auth, meetings
│   │   ├── services/   # transcription, minutes, pipeline, slack, export
│   │   └── ...         # config, models, schemas, auth, state_machine
│   ├── alembic/        # マイグレーション
│   ├── scripts/        # create_user
│   └── tests/          # pytest (16 tests)
├── frontend/           # Next.js 14 App Router + Tailwind（日本語 UI）
├── deploy/             # Azure Container Apps デプロイスクリプト
└── docker-compose.yml  # ローカル開発（app + postgres）
```
