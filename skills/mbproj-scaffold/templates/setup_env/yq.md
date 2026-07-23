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
