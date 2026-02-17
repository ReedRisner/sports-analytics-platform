# backend/app/models/player.py
from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey, Date, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class Team(Base):
    __tablename__ = "teams"

    id                  = Column(Integer, primary_key=True, index=True)
    name                = Column(String(100), nullable=False)
    abbreviation        = Column(String(5))

    # ── Team performance stats ───────────────────────────────────────────────
    pace                = Column(Float)
    offensive_rating    = Column(Float)
    defensive_rating    = Column(Float)
    points_per_game     = Column(Float)
    opp_points_per_game = Column(Float)

    # ── Win/loss record ──────────────────────────────────────────────────────
    wins                = Column(Integer, default=0)
    losses              = Column(Integer, default=0)

    # ── Defensive stats allowed by position group ────────────────────────────
    # Position groups: G (guard), GF (guard-forward), F (forward),
    #                  FC (forward-center), C (center)
    #
    # Points allowed
    pts_allowed_g       = Column(Float)
    pts_allowed_gf      = Column(Float)
    pts_allowed_f       = Column(Float)
    pts_allowed_fc      = Column(Float)
    pts_allowed_c       = Column(Float)

    # Assists allowed
    ast_allowed_g       = Column(Float)
    ast_allowed_gf      = Column(Float)
    ast_allowed_f       = Column(Float)
    ast_allowed_fc      = Column(Float)
    ast_allowed_c       = Column(Float)

    # Rebounds allowed
    reb_allowed_g       = Column(Float)
    reb_allowed_gf      = Column(Float)
    reb_allowed_f       = Column(Float)
    reb_allowed_fc      = Column(Float)
    reb_allowed_c       = Column(Float)

    # Steals allowed (opponent steals vs this team, by position)
    stl_allowed_g       = Column(Float)
    stl_allowed_gf      = Column(Float)
    stl_allowed_f       = Column(Float)
    stl_allowed_fc      = Column(Float)
    stl_allowed_c       = Column(Float)

    # Blocks allowed (opponent blocks vs this team, by position)
    blk_allowed_g       = Column(Float)
    blk_allowed_gf      = Column(Float)
    blk_allowed_f       = Column(Float)
    blk_allowed_fc      = Column(Float)
    blk_allowed_c       = Column(Float)

    # ── League ranks (1 = most allowed = easiest matchup) ───────────────────
    pts_rank_g          = Column(Integer)
    pts_rank_gf         = Column(Integer)
    pts_rank_f          = Column(Integer)
    pts_rank_fc         = Column(Integer)
    pts_rank_c          = Column(Integer)

    ast_rank_g          = Column(Integer)
    ast_rank_gf         = Column(Integer)
    ast_rank_f          = Column(Integer)
    ast_rank_fc         = Column(Integer)
    ast_rank_c          = Column(Integer)

    reb_rank_g          = Column(Integer)
    reb_rank_gf         = Column(Integer)
    reb_rank_f          = Column(Integer)
    reb_rank_fc         = Column(Integer)
    reb_rank_c          = Column(Integer)

    stl_rank_g          = Column(Integer)
    stl_rank_gf         = Column(Integer)
    stl_rank_f          = Column(Integer)
    stl_rank_fc         = Column(Integer)
    stl_rank_c          = Column(Integer)

    blk_rank_g          = Column(Integer)
    blk_rank_gf         = Column(Integer)
    blk_rank_f          = Column(Integer)
    blk_rank_fc         = Column(Integer)
    blk_rank_c          = Column(Integer)

    created_at          = Column(DateTime(timezone=True), server_default=func.now())
    players             = relationship("Player", back_populates="team")


class Player(Base):
    __tablename__ = "players"

    id            = Column(Integer, primary_key=True, index=True)
    name          = Column(String(150), nullable=False)
    team_id       = Column(Integer, ForeignKey("teams.id"))
    position      = Column(String(5))   # Raw NBA position: G, G-F, F, F-C, C, F-G, C-F
    jersey_number = Column(Integer)
    is_active     = Column(Boolean, default=True)
    created_at    = Column(DateTime(timezone=True), server_default=func.now())

    team  = relationship("Team", back_populates="players")
    stats = relationship("PlayerGameStats", back_populates="player")


class Game(Base):
    __tablename__ = "games"

    id           = Column(Integer, primary_key=True, index=True)
    nba_game_id  = Column(String(20), unique=True, index=True)
    date         = Column(Date, nullable=False)
    home_team_id = Column(Integer, ForeignKey("teams.id"))
    away_team_id = Column(Integer, ForeignKey("teams.id"))
    home_score   = Column(Integer)
    away_score   = Column(Integer)
    status       = Column(String(20), default="scheduled")


class PlayerGameStats(Base):
    __tablename__ = "player_game_stats"

    id        = Column(Integer, primary_key=True, index=True)
    player_id = Column(Integer, ForeignKey("players.id"))
    game_id   = Column(Integer, ForeignKey("games.id"))

    # ── Core stats ───────────────────────────────────────────────────────────
    minutes    = Column(Float)
    points     = Column(Integer)
    rebounds   = Column(Integer)
    assists    = Column(Integer)
    oreb       = Column(Integer)
    dreb       = Column(Integer)

    # ── Shooting ─────────────────────────────────────────────────────────────
    fgm        = Column(Integer)
    fga        = Column(Integer)
    fg_pct     = Column(Float)
    fg3m       = Column(Integer)
    fg3a       = Column(Integer)
    fg3_pct    = Column(Float)
    ftm        = Column(Integer)
    fta        = Column(Integer)
    ft_pct     = Column(Float)

    # ── Defense / other ──────────────────────────────────────────────────────
    steals     = Column(Integer)
    blocks     = Column(Integer)
    turnovers  = Column(Integer)
    plus_minus = Column(Integer)

    # ── Advanced ─────────────────────────────────────────────────────────────
    usage_rate = Column(Float)   # USG_PCT — key projection input

    # ── Combo stats ──────────────────────────────────────────────────────────
    pra        = Column(Float)
    pr         = Column(Float)
    pa         = Column(Float)
    ra         = Column(Float)

    # ── Fantasy ──────────────────────────────────────────────────────────────
    fantasy_points = Column(Float)

    player = relationship("Player", back_populates="stats")