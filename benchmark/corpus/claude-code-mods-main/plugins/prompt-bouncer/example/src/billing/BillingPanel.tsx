import { PlanSwitcher } from './PlanSwitcher'

export function BillingPanel({ workspace }: { workspace: { plan: string; cardLast4: string } }) {
  return (
    <section>
      <h2>Billing</h2>
      <p>Card ending {workspace.cardLast4}</p>
      <PlanSwitcher current={workspace.plan} />
    </section>
  )
}
