import os
from dotenv import load_dotenv

load_dotenv()

# Facebook
FB_PAGE_ACCESS_TOKEN = os.getenv("FB_PAGE_ACCESS_TOKEN", "")
FB_VERIFY_TOKEN = os.getenv("FB_VERIFY_TOKEN", "my_verify_token")
FB_APP_SECRET = os.getenv("FB_APP_SECRET", "")

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_LEAD_CHAT_ID = os.getenv("TELEGRAM_LEAD_CHAT_ID", "")

# Anthropic
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")

# Clinic
CLINIC_NAME = os.getenv("CLINIC_NAME", "Шүдний Эмнэлэг")
CLINIC_PHONE = os.getenv("CLINIC_PHONE", "+976-9999-9999")
CLINIC_ADDRESS = os.getenv("CLINIC_ADDRESS", "Улаанбаатар")
CLINIC_WORKING_HOURS_START = os.getenv("CLINIC_WORKING_HOURS_START", "09:00")
CLINIC_WORKING_HOURS_END = os.getenv("CLINIC_WORKING_HOURS_END", "18:00")
CLINIC_SLOT_DURATION_MINUTES = int(os.getenv("CLINIC_SLOT_DURATION_MINUTES", "30"))

PORT = int(os.getenv("PORT", "8000"))
