import DfsBookPage from './DfsBookPage'

export default function PrizePicksPage() {
  return (
    <DfsBookPage
      title="PrizePicks"
      sportsbook="prizepicks"
      description="Best PrizePicks lines, streak-based props, and top-value picks from today's board."
      notes={[
        'Demons and goblins are pulled from adjusted alternate markets.',
        'Adjusted PrizePicks lines are OVER-only recommendations: goblins are below the standard line and demons are above it.',
      ]}
    />
  )
}
