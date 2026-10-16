import fs from "node:fs";

// the aggregate manifest publish-r2.sh uploads next to the tarballs
const source = process.argv[2] ?? "https://terminal-browser.sh/install/latest.json";
const manifest = source.startsWith("http")
  ? await (await fetch(source)).json()
  : JSON.parse(fs.readFileSync(source, "utf8"));

const required = ["darwin-arm64", "darwin-x64", "linux-x64", "linux-arm64"];
const missing = required.filter((platform) => !manifest.platforms?.[platform]);
if (missing.length) {
  console.error(`missing manifests in ${source} for: ${missing.join(", ")}`);
  process.exit(1);
}
if (manifest.channel !== "stable") {
  console.error(`refusing to render a cask for the ${manifest.channel} channel`);
  process.exit(1);
}

const version = manifest.version.replace(/^v/, "");
const sha = (platform) => manifest.platforms[platform].sha256;

process.stdout.write(`cask "terminal-browser" do
  arch arm: "arm64", intel: "x64"
  os macos: "darwin", linux: "linux"

  version "${version}"
  sha256 arm:          "${sha("darwin-arm64")}",
         intel:        "${sha("darwin-x64")}",
         arm64_linux:  "${sha("linux-arm64")}",
         x86_64_linux: "${sha("linux-x64")}"

  url "https://terminal-browser.sh/install/dl/stable/v#{version}/terminal-browser-#{os}-#{arch}.tar.gz"
  name "terminal-browser"
  desc "Terminal-based web browser"
  homepage "https://terminal-browser.com/"

  livecheck do
    url "https://terminal-browser.sh/install/latest.json"
    strategy :json do |json|
      json["version"]&.delete_prefix("v")
    end
  end

  binary "terminal-browser/bin/terminal-browser"

  zap trash: [
    "~/.agents/skills/terminal-browser",
    "~/.cache/terminal-browser-*",
    "~/.claude/skills/terminal-browser",
    "~/.codex/skills/terminal-browser",
    "~/.cursor/skills/terminal-browser",
    "~/.gemini/skills/terminal-browser",
    "~/.local/share/terminal-browser-*",
    "~/.local/state/terminal-browser",
    "~/.local/state/terminal-browser-*",
  ]
end
`);
