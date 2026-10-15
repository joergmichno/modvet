// Clean demo hook: only local formatting, no network, no env.
export default async function onOutput(text) {
  // Adds a summary line to responses.
  return text + "\n---\n";
}
