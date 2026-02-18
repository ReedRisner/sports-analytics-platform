// Stat explanations for tooltips
export const STAT_EXPLANATIONS = {
  // Basic Stats
  projected: "Our model's prediction for this game based on recent performance, matchup, and various adjustments. Higher is better for OVER bets.",
  
  season_avg: "Player's average for this stat across all games this season. Shows overall consistency and baseline performance.",
  
  l5_avg: "Average over the last 5 games. Shows recent form and current hot/cold streaks. More weight than season average.",
  
  l10_avg: "Average over the last 10 games. Balances recent form with longer-term consistency.",
  
  floor: "Conservative estimate - the low end of expected performance (15th percentile). Useful for risk assessment.",
  
  ceiling: "Optimistic estimate - the high end of expected performance (85th percentile). Shows upside potential.",
  
  std_dev: "Standard deviation - measures consistency. Lower = more consistent/predictable. Higher = more volatile/boom-or-bust.",
  
  games_played: "Number of games played this season. More games = more reliable averages.",
  
  // Betting Terms
  edge: "Our advantage over the sportsbook line. Positive edge = value bet. Higher percentage = stronger bet. Look for 5%+ edges.",
  
  line: "The sportsbook's number you're betting over/under. This is what you're trying to beat.",
  
  over_prob: "Probability of going OVER the line based on our projection and variance. 60%+ is strong.",
  
  under_prob: "Probability of going UNDER the line. 60%+ is strong for under bets.",
  
  recommendation: "Our betting suggestion: OVER (bet over), UNDER (bet under), or PASS (no value/too risky).",
  
  // Monte Carlo
  expected_value: "Average profit/loss per $100 bet over thousands of simulations. Positive EV = profitable long-term.",
  
  kelly_criterion: "Optimal bet size as % of bankroll for maximum long-term growth. Conservative: use 25-50% of this number.",
  
  confidence_intervals: "Range where the actual result will likely fall. 68% = 2/3 of the time, 95% = 19/20 times.",
  
  // Matchup
  matchup_grade: "Quality of matchup against opponent. Elite/Good = favorable, Tough/Lockdown = difficult.",
  
  pace_factor: "How fast the opponent plays. Higher = more possessions = more opportunities for stats.",
  
  matchup_factor: "Overall matchup quality multiplier. Above 1.0 = favorable, below 1.0 = unfavorable.",
  
  defense_rank: "Opponent's defensive ranking for this stat. Lower rank (1-10) = easier matchup, higher (20-30) = tougher.",
  
  // Adjustments
  home_factor: "Home court advantage multiplier. Players typically perform ~3% better at home.",
  
  rest_factor: "Rest/fatigue adjustment. Back-to-backs and 3-in-4 reduce performance (~5%).",
  
  form_factor: "Hot/cold streak multiplier. Based on last 3-5 games vs season average. Above 1.0 = hot streak.",
  
  opp_strength: "Opponent defensive strength. Above 1.0 = weak defense (easier), below 1.0 = strong defense (harder).",
  
  back_to_back: "Playing on consecutive nights. Typically reduces performance by 5-10%, especially for older players.",
  
  // Chart Terms
  hit_rate: "Percentage of games where player went OVER the line. 60%+ is strong, 70%+ is excellent.",
  
  average_line: "The gray dashed line showing the player's average performance for context.",
  
  betting_line: "The blue solid line showing the sportsbook's over/under number you're betting against.",
  
  projection_bar: "The gray bar at the end showing our prediction for the next game.",
}