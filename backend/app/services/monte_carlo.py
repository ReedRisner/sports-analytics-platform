# backend/app/services/monte_carlo.py
"""
Monte Carlo simulation engine for player prop projections.

Runs 10,000 simulations per prop to generate:
- Full probability distribution
- Percentile bands (10th, 25th, 50th, 75th, 90th)
- Hit rate vs sportsbook line
- Expected value calculation
"""

import numpy as np
from typing import Tuple, Optional
import logging

logger = logging.getLogger(__name__)


def simulate_stat_distribution(
    mean: float,
    std_dev: float,
    n_simulations: int = 10000,
    min_value: float = 0.0,
    max_value: Optional[float] = None,
) -> dict:
    """
    Run Monte Carlo simulation for a player stat projection.
    
    Args:
        mean: Projected stat value
        std_dev: Historical standard deviation
        n_simulations: Number of simulations to run (default 10k)
        min_value: Floor value (stats can't be negative)
        max_value: Optional ceiling (e.g. minutes can't exceed 48)
    
    Returns:
        dict with simulations, percentiles, expected_value, std_dev
    """
    if std_dev <= 0:
        return {
            'simulations': [mean] * n_simulations,
            'percentiles': {p: round(mean, 2) for p in [10, 25, 50, 75, 90]},
            'expected_value': round(mean, 2),
            'std_dev': 0.0,
        }
    
    # Generate normal distribution
    sims = np.random.normal(mean, std_dev, n_simulations)
    
    # Apply constraints
    sims = np.maximum(sims, min_value)
    if max_value is not None:
        sims = np.minimum(sims, max_value)
    
    # Calculate percentiles
    percentiles = {
        10: float(np.percentile(sims, 10)),
        25: float(np.percentile(sims, 25)),
        50: float(np.percentile(sims, 50)),
        75: float(np.percentile(sims, 75)),
        90: float(np.percentile(sims, 90)),
    }
    
    return {
        'simulations': sims.tolist(),
        'percentiles': {k: round(v, 2) for k, v in percentiles.items()},
        'expected_value': round(float(np.mean(sims)), 2),
        'std_dev': round(float(np.std(sims)), 2),
    }


def calculate_hit_probability(
    mean: float,
    std_dev: float,
    line: float,
    n_simulations: int = 10000,
) -> Tuple[float, float]:
    """
    Calculate probability of hitting over/under via Monte Carlo.
    More robust than Z-score for skewed distributions.
    
    Returns: (over_probability, under_probability)
    """
    if std_dev <= 0:
        return (1.0, 0.0) if mean > line else (0.0, 1.0)
    
    sims = np.random.normal(mean, std_dev, n_simulations)
    sims = np.maximum(sims, 0)
    
    over_count = np.sum(sims > line)
    over_prob = over_count / n_simulations
    
    return round(over_prob, 4), round(1 - over_prob, 4)


def calculate_expected_value(
    over_prob: float,
    over_odds: int,
    under_prob: float,
    under_odds: int,
) -> dict:
    """
    Calculate expected value (EV) for both sides of a prop bet.
    
    EV = (Probability of Win × Payout) - (Probability of Loss × Stake)
    
    Returns:
        dict with over_ev, under_ev, best_bet, kelly_fraction
    """
    def american_to_decimal(odds: int) -> float:
        if odds > 0:
            return (odds / 100) + 1
        else:
            return (100 / abs(odds)) + 1
    
    over_decimal = american_to_decimal(over_odds)
    under_decimal = american_to_decimal(under_odds)
    
    # Calculate EV per $1 bet
    over_ev = (over_prob * (over_decimal - 1)) - ((1 - over_prob) * 1)
    under_ev = (under_prob * (under_decimal - 1)) - ((1 - under_prob) * 1)
    
    # Determine best bet
    if over_ev > 0 and over_ev > under_ev:
        best_bet = 'over'
    elif under_ev > 0:
        best_bet = 'under'
    else:
        best_bet = 'pass'
    
    # Kelly Criterion: f* = (p × b - q) / b
    kelly_over = 0.0
    kelly_under = 0.0
    
    if over_ev > 0:
        b_over = over_decimal - 1
        kelly_over = max(0, (over_prob * b_over - (1 - over_prob)) / b_over)
    
    if under_ev > 0:
        b_under = under_decimal - 1
        kelly_under = max(0, (under_prob * b_under - (1 - under_prob)) / b_under)
    
    kelly_fraction = max(kelly_over, kelly_under)
    
    return {
        'over_ev': round(over_ev * 100, 2),
        'under_ev': round(under_ev * 100, 2),
        'best_bet': best_bet,
        'kelly_fraction': round(kelly_fraction, 4),
    }


def generate_confidence_intervals(
    mean: float,
    std_dev: float,
    confidence_levels: list = None,
) -> dict:
    """Generate confidence intervals for a projection."""
    from scipy import stats
    
    if confidence_levels is None:
        confidence_levels = [0.68, 0.80, 0.90, 0.95]
    
    intervals = {}
    for level in confidence_levels:
        z_score = stats.norm.ppf((1 + level) / 2)
        lower = max(0, mean - (z_score * std_dev))
        upper = mean + (z_score * std_dev)
        
        intervals[f"{int(level * 100)}%"] = (
            round(lower, 2),
            round(upper, 2)
        )
    
    return intervals