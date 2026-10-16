import assert from 'node:assert/strict'

const unkeyed = (text: string): string => {
  let hash = 0x811c9dc5
  for (let index = 0; index < text.length; index++) {
    hash ^= text.charCodeAt(index)
    hash = Math.imul(hash, 0x01000193) >>> 0
  }
  return hash.toString(16).padStart(8, '0')
}

for (const relativePath of ['../hooks/detect.ts', '../../secret-box/hooks/detect.ts']) {
  const moduleUrl = new URL(relativePath, import.meta.url)
  const current = await import(moduleUrl.href)
  const next = await import(`${moduleUrl.href}?session=2`)
  const currentConfig = current.makeConfig({ pii: true })
  const nextConfig = next.makeConfig({ pii: true })
  const addresses = ['dana.whitfield@northwind-labs.io', 'lee.morgan@northwind-labs.io', '91.198.174.192', '8.8.8.8']
  const currentTags = addresses.map(address => current.scrubPii(address, currentConfig))
  const nextTags = addresses.map(address => next.scrubPii(address, nextConfig))

  for (const [index, address] of addresses.entries()) {
    assert.match(currentTags[index], /^\[REDACTED-(?:EMAIL|IP)-[0-9a-f]{8}\]$/)
    assert.match(nextTags[index], /^\[REDACTED-(?:EMAIL|IP)-[0-9a-f]{8}\]$/)
    assert.ok(!currentTags[index].includes(unkeyed(address)), `GUESSABLE: ${relativePath} uses the bare hash of its value`)
    assert.equal(current.scrubPii(address, currentConfig), currentTags[index])
    assert.equal(current.restore(currentTags[index]), address)
    assert.equal(next.restore(nextTags[index]), address)
  }

  assert.notDeepEqual(currentTags, nextTags, `${relativePath}: tags must not be linkable across sessions`)
  assert.notEqual(currentTags[2], nextTags[2], `LINKABLE: ${relativePath} uses the same IP tag in a new session`)
  console.log(`ok  ${relativePath}: stable within a session, private across sessions, round trips clean`)
}
