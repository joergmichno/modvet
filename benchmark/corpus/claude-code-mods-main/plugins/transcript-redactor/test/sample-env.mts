// Prints a fake .env for trying the redactor by hand. Every value is
// generated, and the keys are built from pieces so no key-shaped string
// sits in the repo (GitHub push protection rejects them).
//
//   node --experimental-strip-types test/sample-env.mts > /tmp/sample.env

const ALNUM = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'
const random = (n: number): string => Array.from({ length: n }, () => ALNUM[Math.floor(Math.random() * ALNUM.length)]).join('')

console.log(`# a generated fixture, not a live credential
ANTHROPIC_API_KEY=${'sk-' + 'ant-' + 'api03-' + random(40)}
STRIPE_SECRET_KEY=${'sk_' + 'live_' + random(32)}
DATABASE_URL=postgres://app:${random(20)}@db.internal:5432/shop
SUPPORT_EMAIL=support@shop.dev
PORT=3000
STRIPE_PRICE=price_${random(24)}`)
