"""初期ユーザー作成スクリプト（シングルテナント MVP 用）。

使い方:
    python -m scripts.create_user user@example.com password "山田 太郎"
"""
import asyncio
import sys

sys.path.insert(0, ".")

from app.auth import hash_password  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.models import User  # noqa: E402
from sqlalchemy import select  # noqa: E402


async def main(email: str, password: str, name: str) -> None:
    async with SessionLocal() as db:
        existing = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
        if existing:
            print(f"既に存在します: {email}")
            return
        db.add(User(email=email, password_hash=hash_password(password), name=name))
        await db.commit()
        print(f"ユーザーを作成しました: {email}")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print(__doc__)
        sys.exit(1)
    asyncio.run(main(sys.argv[1], sys.argv[2], sys.argv[3]))
