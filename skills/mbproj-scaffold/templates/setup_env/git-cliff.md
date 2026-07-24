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
