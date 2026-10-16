export type Mode = 'observe' | 'block' | 'steer'

export type Skill = { name: string; description: string; body: string }

export type Ranked = { name: string; probability: number }

export type Verdict = {
  text: string
  gate: number
  ranked: Ranked[]
  fits: Record<string, number>
  winner: string | null
  ms: number
}

declare module 'claude-code' {
  interface PluginState {
    'jev-skill-suggestion': {
      mode: Mode
      enabled: boolean
      disabled: string[]
      roster: Skill[]
      verdict: Verdict | null
      status: string
    }
  }
}
