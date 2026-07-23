# Environment Setup

Tooling required to develop on **claude-mbproj**. Run `make check-dev-env` to verify.

<!-- >>> mbproj:managed (do not edit) >>> -->
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

## jq

JSON processor. Standalone binary — no build step.

```bash
sudo curl -Lo /usr/local/bin/jq \
  https://github.com/jqlang/jq/releases/latest/download/jq-linux-amd64
sudo chmod +x /usr/local/bin/jq
```

Other platforms: pick the matching asset from <https://jqlang.github.io/jq/download/>.
Shortcuts: `sudo apt-get install jq` (Debian/Ubuntu) or `brew install jq` (macOS).

Verify:

```bash
jq --version
```

## yq

YAML processor. Use **mikefarah's `yq`** — a standalone Go binary. Do **not** install
the similarly named Python `yq` (kislyuk): its syntax differs and it will break
`make lint`.

```bash
sudo curl -Lo /usr/local/bin/yq \
  https://github.com/mikefarah/yq/releases/latest/download/yq_linux_amd64
sudo chmod +x /usr/local/bin/yq
```

Other platforms and options: <https://github.com/mikefarah/yq/#install>.
Shortcut on macOS: `brew install yq`.

Verify (the version line must reference `github.com/mikefarah/yq`):

```bash
yq --version
```

## shellcheck

Shell-script linter. Standalone prebuilt binary — no build step.

```bash
curl -L https://github.com/koalaman/shellcheck/releases/download/stable/shellcheck-stable.linux.x86_64.tar.xz \
  | tar -xJf -
sudo mv shellcheck-stable/shellcheck /usr/local/bin/
```

Other platforms: <https://github.com/koalaman/shellcheck/releases>.
Shortcuts: `sudo apt-get install shellcheck` (Debian/Ubuntu) or `brew install shellcheck` (macOS).

Verify:

```bash
shellcheck --version
```
<!-- <<< mbproj:managed <<< -->
