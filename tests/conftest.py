import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ.setdefault('BOT_TOKEN', 'test-bot-token')
os.environ.setdefault('DB_CONNECTION_STRING', 'postgresql+asyncpg://postgres:postgres@localhost:5432/framed_bot_test')
os.environ.setdefault('ADMIN_USER_ID', '1')
