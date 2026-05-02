import asyncio
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
import resend
from unittest.mock import MagicMock

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import text
from app.main import app, limiter
from app.models import Base
from app.dependencies import get_db
import uuid

# Disable rate limiting for tests by generating a unique IP per request
def mock_get_remote_address(*args, **kwargs):
    return str(uuid.uuid4())

limiter.key_func = mock_get_remote_address

# Use a test database on the same postgres container
TEST_DATABASE_URL = "postgresql+asyncpg://mediapp_user:mediapp_pass@db:5432/mediapp_test"

from sqlalchemy.pool import NullPool

# Create a test engine
test_engine = create_async_engine(TEST_DATABASE_URL, echo=False, poolclass=NullPool)
TestingSessionLocal = async_sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=test_engine)



@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_test_db():
    """Create the test database, run migrations/create tables, and drop after."""
    # First, create the database if it doesn't exist. We need to connect to the default DB.
    default_engine = create_async_engine("postgresql+asyncpg://mediapp_user:mediapp_pass@db:5432/mediapp_db", isolation_level="AUTOCOMMIT")
    async with default_engine.connect() as conn:
        try:
            await conn.execute(text("CREATE DATABASE mediapp_test"))
        except Exception:
            pass # DB already exists
    await default_engine.dispose()

    # Now create the tables
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
        
    yield
    
    # Drop tables after tests
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await test_engine.dispose()

@pytest_asyncio.fixture
async def db_session():
    """Provide a database session for a single test."""
    async with TestingSessionLocal() as session:
        yield session

@pytest_asyncio.fixture
async def async_client():
    """Provide an HTTP client that uses the test database."""
    # Override the dependency to yield a new session per request
    async def override_get_db():
        async with TestingSessionLocal() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()

@pytest.fixture(autouse=True)
def mock_resend(monkeypatch):
    """Mock resend.Emails.send to prevent sending actual emails during tests."""
    mock_send = MagicMock()
    mock_send.return_value = {"id": "re_mocked_id"}
    monkeypatch.setattr(resend.Emails, "send", mock_send)
    return mock_send
