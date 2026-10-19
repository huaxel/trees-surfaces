# Tailnet datastore (local sharing, not publication)

Machine-local working files in this project are sometimes needed on the
operator's other machines: the exploration outbox, and the re-downloadable
caches (notably the UrbClim archive cache) that are slow to refetch. Copying
them over chat or re-downloading per machine is wasteful; publishing them is
wrong (unresolved-licence derivatives must never be redistributed). The middle
path is a read-only file server bound to the machine's Tailscale address, so
only tailnet members can reach it and the traffic is WireGuard-encrypted.

## Layout

The server roots at a store directory outside any repository, with one
subdirectory per project, so other repositories can opt in without touching
this one:

- `trees-surfaces/exploration-2026-10-19/` — probe outputs, the heritage-heat
  proposal draft, class mappings, land-cover extracts and retrieval evidence.
  The same content is reachable from this checkout at
  `.cache/exploration-2026-10-19/`, which is a symlink into the store; that
  path is gitignored either way.
- `trees-surfaces/urbclim-cache/` — a symlink to this checkout's
  `.cache/urbclim/`, served so a second machine need not re-download the
  annual NetCDF files. The canonical copy stays where the refresh workflow
  expects it; the store only links to it.
- A small readme file at the store root states the one rule: contents are working
  files, and anything marked local-only stays within these machines.

To add another repository later: create its subdirectory and drop files in.
No server change is needed.

## Serve

On the machine holding the files, with Tailscale up:

```bash
STORE="$HOME/tailnet-store"  # convention; any outside-a-repo path works
nohup python3 -m http.server 8123 --bind "$(tailscale ip -4)" \
  --directory "$STORE" > "$STORE/serve-8123.log" 2>&1 &
```

The server implements GET/HEAD only, so it is physically read-only, and the
bind means it never listens on LAN or public interfaces.

## Pull

From any other tailnet machine (address from `tailscale ip -4` on the host;
port 8123 is the convention, not a contract):

```bash
HOST="http://<tailscale-ip>:8123"
curl "$HOST/trees-surfaces/"
wget -r --no-parent -nH --cut-dirs=1 "$HOST/trees-surfaces/exploration-2026-10-19/"
```

## Limits

- The server is started by hand and survives SSH logout, but not reboot.
  A `systemd --user` unit is the follow-up if the datastore should persist
  across restarts.
- Nothing served here changes any licence: sharing within the operator's
  own machines is not redistribution, and no served file may be committed
  or published elsewhere on the strength of being served.
- The store holds no secrets and grants no access beyond what tailnet
  membership already implies; do not put credentials in it.
