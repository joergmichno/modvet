import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { redactSecrets, redactObject } from "../src/secrets.mjs";

const R = "[REDACTED]";

describe("redactSecrets", () => {
  it("redacts sk- API keys", () => {
    const input = "key is sk-abc123def456ghi789jkl012mno";
    assert.equal(redactSecrets(input), `key is ${R}`);
  });

  it("redacts sk-ant- Anthropic keys", () => {
    const input = "sk-ant-api03-abcdefghijklmnopqrstuvwxyz";
    assert.equal(redactSecrets(input), R);
  });

  it("redacts key- prefixed secrets", () => {
    const input = "use key-abcdefghijklmnopqrstuvwxyz here";
    assert.equal(redactSecrets(input), `use ${R} here`);
  });

  it("redacts AWS access key IDs", () => {
    const input = "aws key: AKIAIOSFODNN7EXAMPLE";
    assert.equal(redactSecrets(input), `aws key: ${R}`);
  });

  it("redacts Bearer tokens", () => {
    const input = "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6Ik";
    assert.equal(redactSecrets(input), `Authorization: ${R}`);
  });

  it("redacts JWT tokens", () => {
    const jwt =
      "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c";
    assert.equal(redactSecrets(`token: ${jwt}`), `token: ${R}`);
  });

  it("redacts connection strings", () => {
    assert.equal(
      redactSecrets("mongodb://user:pass@host:27017/db"),
      R,
    );
    assert.equal(
      redactSecrets("postgres://admin:secret@localhost/mydb"),
      R,
    );
  });

  it("redacts generic key=value secrets", () => {
    assert.equal(
      redactSecrets("api_key=supersecretvalue123"),
      R,
    );
    assert.match(
      redactSecrets('auth_token: "abcdefghijklmnop"'),
      /\[REDACTED\]/,
    );
    assert.equal(
      redactSecrets("secret_key = my_very_secret_val"),
      R,
    );
  });

  it("redacts env var patterns", () => {
    assert.equal(
      redactSecrets("PASSWORD=hunter2"),
      R,
    );
    assert.equal(
      redactSecrets("TOKEN=abc123xyz"),
      R,
    );
  });

  it("redacts private keys", () => {
    const pem = `-----BEGIN RSA PRIVATE KEY-----
MIIEowIBAAKCAQEA0Z3VS5JJcds3xfn/ygWyF...
-----END RSA PRIVATE KEY-----`;
    assert.equal(redactSecrets(pem), R);
  });

  it("redacts long hex tokens", () => {
    const hex = "a]" + "b".repeat(40) + "[z";
    const result = redactSecrets(hex);
    assert.match(result, /\[REDACTED\]/);
  });

  it("leaves normal text unchanged", () => {
    const text = "Hello, this is a normal message with no secrets.";
    assert.equal(redactSecrets(text), text);
  });

  it("leaves short hex strings unchanged", () => {
    const text = "commit abc123 is good";
    assert.equal(redactSecrets(text), text);
  });

  it("handles non-string input gracefully", () => {
    assert.equal(redactSecrets(42), 42);
    assert.equal(redactSecrets(null), null);
    assert.equal(redactSecrets(undefined), undefined);
  });
});

describe("redactObject", () => {
  it("redacts strings in nested objects", () => {
    const obj = {
      command: "curl -H 'Authorization: Bearer eyJhbGciOiJIUzIeyJzdWIiOiIxMjM0eyJhbGciOiJI'",
      nested: {
        key: "sk-abcdefghijklmnopqrstuvwxyz",
        safe: "hello",
      },
    };
    const result = redactObject(obj);
    assert.match(result.command, /\[REDACTED\]/);
    assert.equal(result.nested.key, R);
    assert.equal(result.nested.safe, "hello");
  });

  it("redacts strings in arrays", () => {
    const arr = ["safe", "PASSWORD=hunter2", 42];
    const result = redactObject(arr);
    assert.equal(result[0], "safe");
    assert.equal(result[1], R);
    assert.equal(result[2], 42);
  });

  it("handles null and primitives", () => {
    assert.equal(redactObject(null), null);
    assert.equal(redactObject(42), 42);
    assert.equal(redactObject(true), true);
  });
});
