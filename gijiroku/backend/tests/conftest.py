import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.auth import hash_password
from app.database import Base, get_db
from app.main import app
from app.models import User


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine(
        "sqlite+aiosqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


@pytest_asyncio.fixture
async def client(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def test_user(db_session) -> User:
    user = User(
        email="tanaka@example.com",
        password_hash=hash_password("secret-password"),
        name="田中 太郎",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
def valid_minutes_dict() -> dict:
    return {
        "kaigi_gaiyou": {
            "kaigi_mei": "週次定例会議",
            "nichiji": "2026年06月10日（水）10:00〜11:00",
            "basho": "オンライン",
            "shussekisha": ["田中", "佐藤"],
            "kessekisha": ["鈴木"],
        },
        "gidai": ["売上報告", "新製品ローンチ"],
        "giron_naiyou": [
            {
                "gidai": "売上報告",
                "youten": [{"hatsugensha": "田中", "naiyou": "前月比 110% で推移"}],
            }
        ],
        "kettei_jikou": ["ローンチ日を7月1日に決定"],
        "action_items": [
            {"no": 1, "naiyou": "プレスリリース草稿作成", "tantousha": "佐藤", "kigen": "6月20日"}
        ],
        "jikai_kaigi": {"nichiji": "2026年06月17日（水）10:00", "gidai_yotei": ["進捗確認"]},
        "horyuu_jikou": ["海外展開の時期"],
    }
