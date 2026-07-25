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

## commitlint

Validates commit messages against Conventional Commits, run by prek at the
`commit-msg` stage. Node-based (like `markdownlint-cli2`) — install Node.js first
(see [markdownlint-cli2](#markdownlint-cli2)), then:

```bash
npm install -g @commitlint/cli @commitlint/config-conventional
```

The rules live in the versioned `commitlint.config.js`.

Verify:

```bash
commitlint --version
```

## prek

Fast, standalone git-hook manager (Rust, no Python). Install the prebuilt binary
(no build step); other options at <https://github.com/j178/prek#installation>:

```bash
curl --proto '=https' --tlsv1.2 -LsSf \
  https://github.com/j178/prek/releases/latest/download/prek-installer.sh | sh
```

Verify:

```bash
prek --version
```

## Git hooks

Hooks are declared in `prek.toml`: the `pre-commit` stage runs `make lint`, the
`commit-msg` stage runs `commitlint`. Activate the shims once per clone:

```bash
make install-hooks
```

`make install-hooks` also works when a global `core.hooksPath` is set (e.g. a
token-tracking hooks directory): it scopes the path to `.git/hooks` for the install,
then restores it so any global delegation keeps running.

## git-cliff

Generates `CHANGELOG.md` from the conventional commit history (run via
`make changelog`). Standalone Rust binary, no build step — download the prebuilt
binary for your platform onto your `PATH`; full options at
<https://github.com/orhun/git-cliff#installation>:

```bash
# Linux x86_64 — latest release binary into a directory on your PATH
URL=$(curl -s https://api.github.com/repos/orhun/git-cliff/releases/latest \
  | grep -o 'https://[^"]*x86_64-unknown-linux-gnu\.tar\.gz' | head -1)
curl -sL "$URL" | tar -xz -C /tmp
install -m755 /tmp/git-cliff-*/git-cliff ~/.cargo/bin/git-cliff
```

Verify:

```bash
git-cliff --version
```
<!-- <<< mbproj:managed <<< -->

## Python

Only needed to work **on this plugin** (the scaffolding engine); projects scaffolded by it do
not need Python. Version **3.11 or newer** is required — the engine reads the manifest with
the standard-library `tomllib` module, added in 3.11.

Most systems ship a recent Python 3; official installers for any OS are at
<https://www.python.org/downloads/>. Shortcuts: `sudo apt-get install python3`
(Debian/Ubuntu) or `brew install python` (macOS).

Verify:

```bash
python3 --version
```
