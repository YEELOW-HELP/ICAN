web: cd backend && alembic upgrade head && uvicorn app.api.main:app --host 0.0.0.0 --port $PORT
worker: cd backend && python -m app.bot.main
