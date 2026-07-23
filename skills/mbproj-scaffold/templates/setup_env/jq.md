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
