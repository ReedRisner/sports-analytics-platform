# backend/app/models/projections.py
"""
Models for storing projection history and grading results.
"""

from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class ProjectionHistory(Base):
    """
    Stores every projection we make before the game starts.
    """
    __tablename__ = "projection_history"
    
    id = Column(Integer, primary_key=True, index=True)
    player_id = Column(Integer, ForeignKey("players.id"), nullable=False)
    game_id = Column(Integer, ForeignKey("games.id"), nullable=False)
    stat_type = Column(String(20), nullable=False)
    
    projected_value = Column(Float, nullable=False)
    season_avg = Column(Float)
    l5_avg = Column(Float)
    l10_avg = Column(Float)
    std_dev = Column(Float)
    floor = Column(Float)
    ceiling = Column(Float)
    
    opp_team_id = Column(Integer, ForeignKey("teams.id"))
    pace_factor = Column(Float)
    matchup_factor = Column(Float)
    home_factor = Column(Float)
    rest_factor = Column(Float)
    blowout_factor = Column(Float)
    
    line_value = Column(Float)
    sportsbook = Column(String(50))
    edge_pct = Column(Float)
    over_prob = Column(Float)
    under_prob = Column(Float)
    recommendation = Column(String(10))
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    result = relationship("ProjectionResult", back_populates="projection", uselist=False)


class ProjectionResult(Base):
    """
    Stores the actual outcome of a projection after the game finishes.
    """
    __tablename__ = "projection_results"
    
    id = Column(Integer, primary_key=True, index=True)
    projection_id = Column(Integer, ForeignKey("projection_history.id"), nullable=False)
    player_id = Column(Integer, ForeignKey("players.id"), nullable=False)
    game_id = Column(Integer, ForeignKey("games.id"), nullable=False)
    stat_type = Column(String(20), nullable=False)
    
    projected_value = Column(Float, nullable=False)
    actual_value = Column(Float, nullable=False)
    error = Column(Float)
    abs_error = Column(Float)
    pct_error = Column(Float)
    
    line_value = Column(Float)
    over_hit = Column(Boolean)
    under_hit = Column(Boolean)
    
    recommendation = Column(String(10))
    bet_result = Column(String(10))
    edge_pct = Column(Float)
    
    graded_at = Column(DateTime(timezone=True), server_default=func.now())
    
    projection = relationship("ProjectionHistory", back_populates="result")