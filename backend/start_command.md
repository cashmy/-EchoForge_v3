$env:ECHOFORGE_CONFIG_PROFILE = "dev"
$env:DATABASE_URL = "postgresql+psycopg://postgres:LuckySebeka@localhost:5432/echo_forge"   
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8081 --reload
