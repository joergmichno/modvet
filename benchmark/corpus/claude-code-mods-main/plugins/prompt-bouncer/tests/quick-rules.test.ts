import { expect, mock, test } from 'claude-code/testing'

// Quick mode needs no model, so each prompt is judged by the rules alone
const cases: [string, boolean][] = [
  ['fix the thing', false],
  ['fix stuff', false],
  ["it's broken again", false],
  ['Rename BillingPanel to BillingSettings', true],
  ['add a retry to src/billing/dunningRun.ts', true],
  ['fix the bug in the Billing Panel', true],
  ['!fix the thing', true],
]

for (const [text, passes] of cases) {
  test((passes ? 'lets in: ' : 'bounces: ') + text, async ($, on) => {
    // Stand in for Claude Code: a prompt that reaches the bottom entered
    on('prompt.submit', ($, e) => ({ text: e.text }))
    // A fresh session in quick mode, with nowhere to draw
    mock.env(on, {})
    on('session.messages', () => ({ value: [] }))
    on('ui.toast', () => ({ value: undefined }))
    on('ui.status', () => ({ value: undefined }))
    on('prompt.fill', ($, e) => ({ isFilled: false }))
    const r = await $.prompt.submit({ text })
    expect('drop' in r && typeof r.drop === 'string').toBe(!passes)
  })
}
