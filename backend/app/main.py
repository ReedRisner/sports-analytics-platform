from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import engine, Base
from app.models import player  # Import models so tables get created

# Create all tables automatically on startup
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Sports Analytics API",
    version="1.0.0",
    description="NBA Props Analytics Engine"
)

# Allow React frontend to talk to this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite default port
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health_check():
    return {"status": "online", "version": "1.0.0"}

@app.get("/players")
def get_players():
    return {"players": [], "message": "Players endpoint working!"}