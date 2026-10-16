export type Change = { name: string; kind: 'added' | 'updated' | 'deleted'; added: number; removed: number }

export type Run = {
  id: string
  at: number
  status: 'classifying' | 'skipped' | 'forking' | 'done' | 'failed'
  reason?: string
  changes: Change[]
}

declare module 'claude-code' {
  interface PluginState {
    'memory-fork': { runs: Run[]; dismissed: string | null }
  }
}
