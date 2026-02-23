import DfsBookPage from './DfsBookPage'

export default function UnderdogPage() {
  return (
    <DfsBookPage
      title="Underdog"
      sportsbook="underdog"
      description="Best Underdog Fantasy lines to take, including adjusted alternate lines and streak-driven opportunities."
      notes={[
        'Selections with non-default multipliers (not x1) are included in alternate markets.',
        'Adjusted lines can surface additional over/under streak value when standard lines are thin.',
      ]}
    />
  )
}
