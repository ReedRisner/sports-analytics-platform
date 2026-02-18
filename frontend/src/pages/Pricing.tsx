/**
 * Pricing page
 */
export default function Pricing() {
  return (
    <div className="max-w-5xl mx-auto space-y-8 py-8">
      <div className="text-center">
        <h1 className="text-4xl font-bold tracking-tight">Simple, transparent pricing</h1>
        <p className="text-muted-foreground mt-3 text-lg">
          Choose the plan that works for you
        </p>
      </div>

      <div className="grid md:grid-cols-2 gap-8 mt-12">
        {/* Free Tier */}
        <div className="rounded-lg border border-border bg-card p-8 space-y-6">
          <div>
            <h3 className="text-2xl font-bold">Free</h3>
            <div className="mt-4">
              <span className="text-4xl font-bold">$0</span>
              <span className="text-muted-foreground">/month</span>
            </div>
          </div>

          <ul className="space-y-3 text-sm">
            <li className="flex items-center gap-2">
              <span className="text-green-400">✓</span>
              <span>Basic projections</span>
            </li>
            <li className="flex items-center gap-2">
              <span className="text-green-400">✓</span>
              <span>24-hour delayed odds</span>
            </li>
            <li className="flex items-center gap-2">
              <span className="text-green-400">✓</span>
              <span>Top 5 edges per day</span>
            </li>
            <li className="flex items-center gap-2">
              <span className="text-green-400">✓</span>
              <span>Player pages</span>
            </li>
          </ul>

          <button className="w-full py-2 px-4 rounded-md border border-border hover:bg-accent transition-colors">
            Get Started
          </button>
        </div>

        {/* Premium Tier */}
        <div className="rounded-lg border-2 border-primary bg-card p-8 space-y-6 relative">
          <div className="absolute -top-4 left-1/2 -translate-x-1/2 bg-primary text-primary-foreground px-4 py-1 rounded-full text-xs font-semibold">
            RECOMMENDED
          </div>
          
          <div>
            <h3 className="text-2xl font-bold">Premium</h3>
            <div className="mt-4">
              <span className="text-4xl font-bold">$19</span>
              <span className="text-muted-foreground">/month</span>
            </div>
          </div>

          <ul className="space-y-3 text-sm">
            <li className="flex items-center gap-2">
              <span className="text-green-400">✓</span>
              <span>Real-time edges</span>
            </li>
            <li className="flex items-center gap-2">
              <span className="text-green-400">✓</span>
              <span>All sportsbooks</span>
            </li>
            <li className="flex items-center gap-2">
              <span className="text-green-400">✓</span>
              <span>Unlimited edges</span>
            </li>
            <li className="flex items-center gap-2">
              <span className="text-green-400">✓</span>
              <span>Line movement alerts</span>
            </li>
            <li className="flex items-center gap-2">
              <span className="text-green-400">✓</span>
              <span>CSV export</span>
            </li>
            <li className="flex items-center gap-2">
              <span className="text-green-400">✓</span>
              <span>Discord community</span>
            </li>
            <li className="flex items-center gap-2">
              <span className="text-green-400">✓</span>
              <span>Priority support</span>
            </li>
          </ul>

          <button className="w-full py-2 px-4 rounded-md bg-primary text-primary-foreground font-medium hover:opacity-90 transition-opacity">
            Start Free Trial
          </button>
        </div>
      </div>
    </div>
  )
}