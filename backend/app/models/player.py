# backend/app/models/player.py
from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey, Date, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class Team(Base):
    __tablename__ = "teams"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    abbreviation = Column(String(5))
    pace = Column(Float)
    offensive_rating = Column(Float)
    defensive_rating = Column(Float)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    players = relationship("Player", back_populates="team")


class Player(Base):
    __tablename__ = "players"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=False)
    team_id = Column(Integer, ForeignKey("teams.id"))
    position = Column(String(5))
    jersey_number = Column(Integer)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    team = relationship("Team", back_populates="players")
    stats = relationship("PlayerGameStats", back_populates="player")


class Game(Base):
    __tablename__ = "games"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, nullable=False)
    home_team_id = Column(Integer, ForeignKey("teams.id"))
    away_team_id = Column(Integer, ForeignKey("teams.id"))
    home_score = Column(Integer)
    away_score = Column(Integer)
    status = Column(String(20), default="scheduled")


class PlayerGameStats(Base):
    __tablename__ = "player_game_stats"

    id = Column(Integer, primary_key=True, index=True)
    player_id = Column(Integer, ForeignKey("players.id"))
    game_id = Column(Integer, ForeignKey("games.id"))

    # ── Core stats ──────────────────────────────────────────
    minutes = Column(Float)
    points = Column(Integer)
    rebounds = Column(Integer)
    assists = Column(Integer)

    # ── Three-point shooting ─────────────────────────────────
    fg3m = Column(Integer)           # 3-pointers made
    fg3a = Column(Integer)           # 3-pointers attempted
    fg3_pct = Column(Float)          # 3-point percentage (0.0 – 1.0)

    # ── Combo stats (stored for fast querying) ───────────────
    pra = Column(Float)              # points + rebounds + assists
    pr = Column(Float)               # points + rebounds
    pa = Column(Float)               # points + assists
    ra = Column(Float)               # rebounds + assists

    # ── Advanced metrics ────────────────────────────────────
    usage_rate = Column(Float)
    true_shooting_pct = Column(Float)
    fantasy_points = Column(Float)

    player = relationship("Player", back_populates="stats")