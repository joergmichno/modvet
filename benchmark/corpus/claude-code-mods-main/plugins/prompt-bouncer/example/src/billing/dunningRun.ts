// Nightly: retry failed charges, up to 3 attempts over 7 days (see docs/decisions/0002)
export async function dunningRun(failed: { id: string; attempts: number }[]) {
  return failed.filter((c) => c.attempts < 3)
}
