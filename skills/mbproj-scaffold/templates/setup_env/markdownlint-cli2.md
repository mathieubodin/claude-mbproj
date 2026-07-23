## markdownlint-cli2

Node-based Markdown linter. Requires **Node.js** — install the prebuilt runtime from
<https://nodejs.org/> (any OS, no build step), then install the linter globally so
`make lint` finds it on `PATH` (a bare `npx` would not):

```bash
npm install -g markdownlint-cli2
```

Shortcut for Node itself: `brew install node` (macOS) or your distro package.

Verify:

```bash
markdownlint-cli2 --version
```
