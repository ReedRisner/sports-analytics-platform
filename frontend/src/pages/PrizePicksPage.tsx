import DfsBookPage from './DfsBookPage'

export default function PrizePicksPage() {
  return (
    <DfsBookPage
      title="PrizePicks"
      sportsbook="prizepicks"
      description="Best PrizePicks lines, streak-based props, and top-value picks from today's board."
      notes={[
        'Demons and goblins are included under alternate markets (e.g. player_points_alternate).',
        'Goblins are treated as default odds lines, while demons are normalized to even odds (+100).',
      ]}
    />
  )
}
