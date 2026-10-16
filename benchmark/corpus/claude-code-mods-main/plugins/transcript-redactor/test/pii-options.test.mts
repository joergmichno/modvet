import assert from 'node:assert/strict'

for (const relativePath of ['../hooks/detect.ts', '../../secret-box/hooks/detect.ts']) {
  const detector = await import(new URL(relativePath, import.meta.url).href)
  const config = detector.makeConfig({ pii: true, hideEmails: false })
  const address = 'contact me at dana.whitfield@northwind-labs.io'
  assert.equal(detector.scrubPii(address, config), address, 'hideEmails off must keep email addresses')
  for (const ip of ['8.8.8.8', '91.198.174.192', '2606:4700:0000:0000:0000:0000:0000:1111']) {
    const text = `origin ${ip} hit the worker`
    const hidden = detector.scrubPii(text, config)
    assert.notEqual(hidden, text, 'hideEmails off must still hide public IPs')
    assert.match(hidden, /\[REDACTED-IP-[0-9a-f]{8}\]/)
    assert.equal(detector.restore(hidden), text)
    assert.equal(detector.scrubPii(text, detector.makeConfig({ allow: ip })), text)
    const tag = hidden.match(/\[REDACTED-IP-[0-9a-f]{8}\]/)[0]
    assert.equal(detector.restore(detector.escapeLiteralTags(tag)), tag)
  }
  for (const ip of ['127.0.0.1', '10.0.0.1', '192.168.1.1', '172.16.0.1', '192.0.2.1']) {
    assert.equal(detector.scrubPii(ip, config), ip)
    assert.notEqual(detector.scrubPii(ip, detector.makeConfig({ redactPrivateIps: true })), ip)
  }
  for (const text of ['999.1.2.3', '1.2.3.4.5', '1x2x3x4']) {
    assert.equal(detector.scrubPii(text, config), text)
  }
  assert.notEqual(detector.scrubPii(address, detector.makeConfig({ pii: true })), address)
  assert.equal(detector.makeConfig({}).pii, false)
  assert.equal(detector.makeConfig({}).emails, true)
  console.log(`ok  ${relativePath}: optional email hiding, IP redaction, allowlist and literal protection`)
}
