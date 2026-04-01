# Шүдний Эмнэлэг — Facebook Messenger Bot

## Системийн бүтэц

```
agent_m/
├── main.py                  ← FastAPI webhook сервер
├── agent.py                 ← LangChain Agent
├── config.py                ← Тохиргоо
├── requirements.txt
├── .env                     ← Нууц тохиргоо (.env.example-с хуулж)
├── tools/
│   ├── calendar_tool.py     ← Google Calendar — цаг шалгах/захиалах
│   ├── sheets_tool.py       ← Google Sheets — захиалга хадгалах
│   └── telegram_tool.py     ← Telegram мэдэгдэл
├── memory/
│   └── user_memory.py       ← SQLite хэрэглэгч санах ой
└── credentials/
    └── google_service_account.json  ← Google Service Account key
```

## Тохируулах алхамууд

### 1. Python environment

```bash
python -m venv venv
# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

pip install -r requirements.txt
```

### 2. .env файл үүсгэх

```bash
cp .env.example .env
```

`.env` файлыг нээж бөглөх:

| Хувьсагч | Тайлбар |
|---|---|
| `FB_PAGE_ACCESS_TOKEN` | Facebook Page → Settings → Messaging → Access Token |
| `FB_VERIFY_TOKEN` | Өөрөө сонгосон нууц үг (webhook тохируулахад хэрэглэнэ) |
| `FB_APP_SECRET` | Facebook App → Settings → Basic → App Secret |
| `TELEGRAM_BOT_TOKEN` | @BotFather-аас авах |
| `TELEGRAM_LEAD_CHAT_ID` | Telegram group/channel ID (эсвэл өөрийнхөө chat ID) |
| `ANTHROPIC_API_KEY` | console.anthropic.com |
| `GOOGLE_CALENDAR_ID` | Google Calendar → Settings → Calendar ID |
| `GOOGLE_SHEET_ID` | Google Sheets URL-аас авах |

### 3. Google Service Account тохируулах

1. [Google Cloud Console](https://console.cloud.google.com) → New Project
2. APIs & Services → Enable:
   - Google Calendar API
   - Google Sheets API
   - Google Drive API
3. Credentials → Service Account → Create
4. JSON key файл татаж `credentials/google_service_account.json` болгон хадгалах
5. **Google Calendar** → Share → Service Account email-г нэмэх (Editor эрхтэй)
6. **Google Sheet** → Share → Service Account email-г нэмэх (Editor эрхтэй)

```bash
mkdir credentials
# google_service_account.json файлыг credentials/ хавтаст хийх
```

### 4. Telegram Bot тохируулах

```
1. Telegram дээр @BotFather олох
2. /newbot гэж илгээх → нэр өгөх
3. BOT_TOKEN авах → .env-д хийх
4. Chat ID авах:
   - Bot-оо group-д нэмэх
   - https://api.telegram.org/bot<TOKEN>/getUpdates руу хандах
   - "chat":{"id": XXXXXXX} — энэ бол TELEGRAM_LEAD_CHAT_ID
```

### 5. Facebook App тохируулах

```
1. developers.facebook.com → New App → Business
2. Messenger → Settings
3. Access Tokens → Generate Token (Page сонгоод)
4. Webhooks → New Subscription:
   - Callback URL: https://yourdomain.com/webhook
   - Verify Token: .env дэх FB_VERIFY_TOKEN
   - Subscribe to: messages, messaging_postbacks
```

### 6. Сервер ажиллуулах

```bash
# Шууд ажиллуулах
python main.py

# Эсвэл uvicorn-р
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### 7. Ngrok (локал тест хийхэд)

```bash
# Ngrok суулгасан бол
ngrok http 8000

# Гарч ирсэн URL-г Facebook Webhook Callback URL-д оруулах
# Жишээ: https://xxxx.ngrok-free.app/webhook
```

## Google Sheets хүснэгт бүтэц

Автоматаар үүснэ. Баганууд:
| ID | Огноо/Цаг | Нэр | Утас | Үйлчилгээ | Facebook PSID | Тэмдэглэл | Статус | Бүртгэсэн огноо |

## Telegram мэдэгдлийн төрлүүд

- 🦷 **Шинэ Lead** — шинэ хэрэглэгч анх мессеж илгээхэд
- ✅ **Шинэ Захиалга** — цаг баталгаажихад
- ❌ **Цуцлалт** — захиалга цуцлагдахад

## Туршилт хийх

```bash
# Health check
curl http://localhost:8000/health

# Webhook verify шалгах
curl "http://localhost:8000/webhook/?hub.mode=subscribe&hub.verify_token=YOUR_TOKEN&hub.challenge=test123"
```

## Дэмжигдэх үйлдлүүд

| Хэрэглэгчийн хүсэлт | Үйлдэл |
|---|---|
| "Цаг захиалмаар байна" | Боломжит өдрүүдийг харуулна |
| "Маргааш цаг байна уу?" | Тухайн өдрийн слотуудыг харуулна |
| "Миний захиалгууд" | Өмнөх захиалгуудыг харуулна |
| "Захиалга цуцлах" | Цуцлах процессийг эхлүүлнэ |
| "Хаана байдаг вэ?" | Хаяг, утас мэдэгдэнэ |
