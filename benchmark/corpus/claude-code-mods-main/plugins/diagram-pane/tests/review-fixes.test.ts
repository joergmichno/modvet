import { expect, mock, test } from 'claude-code/testing'
import { parseMermaid } from '../hooks/draw.js'
import { toMermaid } from '../hooks/graph.js'
import { fileName } from '../hooks/register.js'

// One test per finding of the PR #11 review

const USAGE = { input_tokens: 1, output_tokens: 1, cache_creation_input_tokens: 0, cache_read_input_tokens: 0 }
const PIN = 'Here is the flow:\n\n```mermaid\nflowchart TD\n  A[Cart] --> B[Pay]\n```\n'
const MAP = `flowchart TD
  web[web.tf] --> net
  subgraph net [network.tf]
    vpc[VPC] --> sub[Subnets]
  end`

type Answer = { deny?: string; result?: unknown }
const call = async ($: any, input: Record<string, unknown>) => (await $.tool.call(input as never)) as Answer
const get = async ($: any) => String((await call($, { tool: 'mcp__diagram-pane__diagram_get' })).result)
const set = ($: any, input: Record<string, unknown>) => call($, { tool: 'mcp__diagram-pane__diagram_set', ...input })

function world(on: any, messages: () => unknown[] = () => [
  { role: 'user', text: 'explain checkout', toolUses: [] },
  { role: 'assistant', text: PIN, toolUses: [] },
]) {
  mock.store(on)
  mock.env(on, {})
  mock.clock(on)
  on('session.id', () => ({ value: 's1' }))
  on('ui.panes', () => ({ value: [{ id: 'diagrams', title: 'Diagrams', isPlaced: true }] }))
  on('session.messages', () => ({ value: messages() }))
}

const mount = ($: any) => $.ui.mount({
  plugin: 'diagram-pane', surface: 'terminal', component: 'Pane', requestId: 'diagrams',
  props: { title: 'Diagrams', isFocused: true, bodyColumns: 60, placement: 'dock' } as never,
})

test('the change field has a c key and says how the pane takes the keys', async ($, on) => {
  // Where the focus lands is the engine's: checked live, not here (the kit has no ui.focus)
  world(on)
  await set($, { target: 'map', mermaid: MAP, title: 'infra' })
  const ui = await mount($)
  await ui.press({ key: 'node:net' } as never)
  expect((await ui.find({ key: 'change' }))?.text).toContain('type a change')
  expect((await ui.find({ type: 'Input' } as never))?.key).toBe('edit-map-net')
  expect(await ui.find({ type: 'Text', text: /ctrl\+x tab/ } as never)).toBeDefined()
  await ui.press({ key: 'change' } as never)
  expect(await ui.find({ type: 'Text', text: /Work map › network\.tf/ } as never)).toBeDefined()
})

test('a hand edit made while the map fork runs is not overwritten', async ($, on) => {
  // Enough turns for a catch-up fork, and no map yet
  const turns = Array.from({ length: 4 }, (_, i) => [
    { role: 'user', text: 'step ' + i, toolUses: [] },
    { role: 'assistant', text: 'ok', toolUses: [] },
  ]).flat()
  world(on, () => turns)
  let release = () => {}
  const held = new Promise<void>(r => (release = r))
  let started = () => {}
  const forking = new Promise<void>(r => (started = r))
  on('model.fork', async () => {
    started()
    await held
    const map = { title: 'stale fork map', nodes: [{ id: 'old', label: 'old work', kind: 'file' }], edges: [] }
    return { value: { isAnswered: true, text: JSON.stringify(map), usage: USAGE } } as never
  })
  const late = get($)
  await forking
  expect((await set($, { target: 'map', mermaid: MAP, title: 'infra' })).deny).toBe(undefined)
  release()
  await late
  const got = await get($)
  expect(got).toContain('## map: "infra"')
  expect(got).not.toContain('stale fork map')
})

test('a link to the enclosing subgraph does not lose the branch', async () => {
  const g = parseMermaid('flowchart TD\n U --> X\n subgraph Outer [Outer box]\n subgraph Inner [Inner box]\n a --> Outer\n end\n end')!
  expect(g.nodes.map(n => n.id)).toEqual(['U', 'X', 'Outer'])
  expect(g.nodes[2].sub!.nodes.map(n => n.id)).toEqual(['Inner'])
  expect(g.nodes[2].sub!.nodes[0].sub!.nodes.map(n => n.id)).toEqual(['a'])
})

test('a subgraph label with brackets reads back as the same box', async () => {
  const g = {
    nodes: [{ id: 'S', label: 'arr[0] store', box: 'round', sub: { nodes: [{ id: 'k', label: 'key', box: 'single' }], edges: [] } }],
    edges: [],
  }
  const back = parseMermaid(toMermaid(g as never))!
  expect(back.nodes.map(n => [n.id, n.label])).toEqual([['S', 'arr[0] store']])
  expect(back.nodes[0].sub!.nodes[0].id).toBe('k')
})

test('a typed change takes the chart, not the word graph in the prose before it', async ($, on) => {
  world(on)
  on('model.fork', () => ({ value: { isAnswered: true, text: 'Here is the updated graph:\nflowchart TD\n  vpc[VPC] --> sub[Subnets]\n  sub --> nat[NAT]', usage: USAGE } }) as never)
  await set($, { target: 'map', mermaid: MAP, title: 'infra' })
  const ui = await mount($)
  await ui.press({ key: 'node:net' } as never)
  await ui.input({ key: 'edit-map-net', text: 'add a NAT' } as never)
  expect(await ui.find({ key: 'node:nat' })).toBeDefined()
  expect(await ui.find({ key: 'node:flowchart' })).toBe(undefined)
  expect(await ui.find({ key: 'node:graph' })).toBe(undefined)
})

test('boxes past the ninth still get a Button', async ($, on) => {
  world(on)
  const lines = Array.from({ length: 12 }, (_, i) => `  n${i + 1}[Box ${i + 1}]`).join('\n')
  await set($, { target: 'map', mermaid: 'flowchart TD\n' + lines, title: 'big' })
  const ui = await mount($)
  expect(await ui.find({ key: 'node:n12' })).toBeDefined()
  await ui.press({ key: 'node:n12' } as never)
  expect(await ui.find({ type: 'Text', text: /Work map › Box 12/ } as never)).toBeDefined()
})

test('pins on the home view are drawn without numbers', async ($, on) => {
  world(on)
  await get($) // pins the transcript's diagram
  const ui = await mount($)
  expect(await ui.find({ type: 'Text', text: /Cart/ } as never)).toBeDefined()
  expect(await ui.find({ type: 'Text', text: /\d·Cart/ } as never)).toBe(undefined)
})

test('a box added on top never shares an id with a box inside a detail', async ($, on) => {
  world(on)
  await set($, { target: 'map', mermaid: MAP, title: 'infra' })
  await set($, { target: 'map', ops: [{ op: 'add_node', id: 'vpc', label: 'Peer VPC' }] })
  const got = await get($)
  expect(got.match(/^\s*vpc\[/gm)?.length).toBe(1)
  expect(got).toContain('net_vpc["VPC"]')
  expect(parseMermaid(got.split('```mermaid\n')[1].split('```')[0])!.nodes.map(n => n.id)).toEqual(['web', 'net', 'vpc'])
})

test('a title alone, or removing every box, leaves no empty detail', async ($, on) => {
  world(on)
  await set($, { target: 'map', mermaid: MAP, title: 'infra' })
  expect((await set($, { target: 'map', path: ['web'], title: 'renamed' })).deny).toBe(undefined)
  await set($, { target: 'map', path: ['net'], ops: [{ op: 'remove_node', id: 'vpc' }, { op: 'remove_node', id: 'sub' }] })
  const got = await get($)
  expect(got).toContain('## map: "renamed"')
  expect(got).not.toContain('subgraph')
  const ui = await mount($)
  await ui.press({ key: 'top' } as never)
  const web = await ui.find({ key: 'node:web' })
  const net = await ui.find({ key: 'node:net' })
  expect(web?.text).toContain('web.tf')
  expect(net?.text).toContain('network.tf')
  expect(web?.text).not.toContain('▸')
  expect(net?.text).not.toContain('▸')
})

test("a pin's change field keeps its key when a new diagram is pinned", async ($, on) => {
  let messages: unknown[] = [
    { role: 'user', text: 'explain checkout', toolUses: [] },
    { role: 'assistant', text: PIN, toolUses: [] },
  ]
  world(on, () => messages)
  await get($)
  const ui = await mount($)
  await ui.press({ key: 'pin:0' } as never)
  const before = (await ui.find({ type: 'Input' } as never))?.key
  messages = [...messages,
    { role: 'user', text: 'and refunds', toolUses: [] },
    { role: 'assistant', text: 'Refunds:\n\n```mermaid\nflowchart TD\n  R[Refund] --> S[Stripe]\n```\n', toolUses: [] }]
  // Any change redraws the pane; the pin the person is on is now the second one
  await set($, { target: 'view', title: 'checkout' })
  expect(String((await call($, { tool: 'mcp__diagram-pane__diagram_get' })).result)).toContain('## pin:2: "checkout"')
  expect(before).toBeDefined()
  expect((await ui.find({ type: 'Input' } as never))?.key).toBe(before)
})

test('a file name is the part after the last / or \\', async () => {
  expect(fileName('/w/proj/src/app.ts')).toBe('app.ts')
  expect(fileName('C:\\proj\\src\\app.ts')).toBe('app.ts')
  expect(fileName('C:\\proj/src\\app.ts')).toBe('app.ts')
  expect(fileName(undefined)).toBe('')
})
