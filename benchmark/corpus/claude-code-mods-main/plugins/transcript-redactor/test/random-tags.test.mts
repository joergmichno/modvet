import assert from 'node:assert/strict'

const cryptoDescriptor = Object.getOwnPropertyDescriptor(globalThis, 'crypto')
const originalRandom = Math.random

try {
  for (const relativePath of ['../hooks/detect.ts', '../../secret-box/hooks/detect.ts']) {
    let draws = 0
    Object.defineProperty(globalThis, 'crypto', {
      configurable: true,
      value: { getRandomValues: (bytes: Uint8Array) => bytes.fill(++draws <= 2 ? 1 : 2) },
    })
    const moduleUrl = new URL(relativePath, import.meta.url)
    const detector = await import(`${moduleUrl.href}?random-test`)
    const first = detector.mint('IP', '8.8.8.8')
    assert.equal(first, '[REDACTED-IP-01010101]')
    assert.equal(detector.mint('IP', '8.8.8.8'), first)
    assert.equal(draws, 1, 'repeated values must reuse their random tag')
    const second = detector.mint('IP', '91.198.174.192')
    assert.equal(second, '[REDACTED-IP-02020202]')
    assert.equal(draws, 3, 'a collision must draw a fresh tag')
    assert.equal(detector.restore(first), '8.8.8.8')
    assert.equal(detector.restore(second), '91.198.174.192')

    Object.defineProperty(globalThis, 'crypto', { configurable: true, value: undefined })
    Math.random = () => 0.5
    const fallback = await import(`${moduleUrl.href}?fallback-test`)
    const fallbackTag = fallback.mint('IP', '8.8.8.8')
    assert.equal(fallbackTag, '[REDACTED-IP-80808080]')
    assert.equal(fallback.restore(fallbackTag), '8.8.8.8')
    console.log(`ok  ${relativePath}: random bytes, stable reuse, collision retry and fallback`)
  }
} finally {
  Math.random = originalRandom
  if (cryptoDescriptor) Object.defineProperty(globalThis, 'crypto', cryptoDescriptor)
  else Reflect.deleteProperty(globalThis, 'crypto')
}
