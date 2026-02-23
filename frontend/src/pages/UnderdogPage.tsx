import DfsBookPage from './DfsBookPage'

export default function UnderdogPage() {
  return (
    <DfsBookPage
      title="Underdog"
      sportsbook="underdog"
      description="Best Underdog Fantasy lines to take, including adjusted alternate lines and streak-driven opportunities."
      notes={[
        'Adjusted Underdog lines from alternate multipliers are included in full.',
        'Adjusted Underdog lines are OVER-only recommendations: lower lines are goblins (sorted by longest streaks) and higher lines are demons.',
      ]}
    />
  )
}
