-- =============================================
-- Шүдний Эмнэлэг Bot — Supabase Migration
-- Supabase Dashboard → SQL Editor дээр ажиллуулна
-- =============================================

-- 1. Хэрэглэгчийн профайл
CREATE TABLE IF NOT EXISTS user_profiles (
    psid                TEXT PRIMARY KEY,
    name                TEXT DEFAULT '',
    phone               TEXT DEFAULT '',
    last_service        TEXT DEFAULT '',
    appointment_count   INTEGER DEFAULT 0,
    is_new_lead         BOOLEAN DEFAULT TRUE,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

-- 2. Яриаг хадгалах хүснэгт
CREATE TABLE IF NOT EXISTS conversation_messages (
    id          BIGSERIAL PRIMARY KEY,
    psid        TEXT NOT NULL,
    role        TEXT NOT NULL CHECK (role IN ('human', 'assistant')),
    content     TEXT NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_conv_psid_created
    ON conversation_messages (psid, created_at DESC);

-- 3. Цаг захиалга
CREATE TABLE IF NOT EXISTS appointments (
    id              BIGSERIAL PRIMARY KEY,
    patient_name    TEXT NOT NULL,
    patient_phone   TEXT NOT NULL,
    date_str        TEXT NOT NULL,   -- YYYY-MM-DD
    time_str        TEXT NOT NULL,   -- HH:MM
    service_type    TEXT DEFAULT 'Шүдний үзлэг',
    facebook_psid   TEXT DEFAULT '',
    notes           TEXT DEFAULT '',
    status          TEXT DEFAULT 'Баталгаажсан'
                        CHECK (status IN ('Баталгаажсан', 'Цуцлагдсан', 'Дууссан')),
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Нэг цаганд нэг л захиалга байх (цуцлагдаагүй)
CREATE UNIQUE INDEX IF NOT EXISTS idx_apt_date_time_active
    ON appointments (date_str, time_str)
    WHERE status != 'Цуцлагдсан';

CREATE INDEX IF NOT EXISTS idx_apt_psid ON appointments (facebook_psid);
CREATE INDEX IF NOT EXISTS idx_apt_date  ON appointments (date_str);

-- 4. Row Level Security
ALTER TABLE user_profiles         ENABLE ROW LEVEL SECURITY;
ALTER TABLE conversation_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE appointments          ENABLE ROW LEVEL SECURITY;

-- Service role бүх үйлдэл хийх боломжтой
DROP POLICY IF EXISTS "service_all_user_profiles" ON user_profiles;
CREATE POLICY "service_all_user_profiles"
    ON user_profiles FOR ALL USING (auth.role() = 'service_role');

DROP POLICY IF EXISTS "service_all_conv_messages" ON conversation_messages;
CREATE POLICY "service_all_conv_messages"
    ON conversation_messages FOR ALL USING (auth.role() = 'service_role');

DROP POLICY IF EXISTS "service_all_appointments" ON appointments;
CREATE POLICY "service_all_appointments"
    ON appointments FOR ALL USING (auth.role() = 'service_role');

-- 5. updated_at автоматаар шинэчлэх
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_user_profiles_updated_at ON user_profiles;
CREATE TRIGGER trg_user_profiles_updated_at
    BEFORE UPDATE ON user_profiles
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
