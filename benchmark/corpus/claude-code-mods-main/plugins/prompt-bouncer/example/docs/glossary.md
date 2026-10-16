# Glossary

| Term | What it is | Not |
| --- | --- | --- |
| **Billing Panel** | The settings screen where a workspace owner sees their plan, card and invoices. `src/billing/BillingPanel.tsx` | "payments page", "billing page", "the money screen" |
| **Plan Switcher** | The dropdown inside the Billing Panel that changes plans. `src/billing/PlanSwitcher.tsx` | "upgrade button", "pricing thing" |
| **Invoice Draft** | An invoice that has not been sent yet. Editable. | "pending invoice", "unsent bill" |
| **Dunning Run** | The nightly job that retries failed card charges and emails the owner. `src/billing/dunningRun.ts` | "retry thing", "payment cron" |
| **Workspace** | One customer agency. Owns seats, invoices and a plan. | "account", "team", "org" |
| **Seat Ledger** | The table of who holds a paid seat in a workspace. `src/billing/seatLedger.ts` | "user list", "members table" |
