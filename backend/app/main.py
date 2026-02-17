# backend/app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import engine, Base
from app.models import player  # Import models so tables get created

# Import routers
from app.routers import players, games, projections

# Create all tables automatically on startup
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Sports Analytics API",
    version="2.0.0",
    description="NBA Props Analytics Engine — Phase 2"
)

# Allow React frontend to talk to this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite default port
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(players.router)
app.include_router(games.router)
app.include_router(projections.router)


@app.get("/health")
def health_check():
    return {"status": "online", "version": "2.0.0"}