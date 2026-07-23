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
