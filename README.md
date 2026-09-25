# Animeko Flatpak Packaging

Build configuration that repackages the official Linux AppImage as a Flatpak.

**English** | [简体中文](README.zh-CN.md) | [Packaging notes](docs/packaging-notes.md)

[![build](https://github.com/lyndon0na/animeko-flapak/actions/workflows/build.yml/badge.svg)](https://github.com/lyndon0na/animeko-flapak/actions/workflows/build.yml)

## App info

| | |
|---|---|
| Name | Animeko (Ani) |
| Version | 6.1.0 |
| App ID | `me.him188.ani` |
| Runtime | `org.gnome.Platform` 49 |
| Architecture | x86_64 |
| Upstream source | https://github.com/open-ani/animeko |
| Homepage | https://animeko.org/ |
| Build input | `ani-6.1.0-linux-x86_64.appimage`, fetched from the upstream release and verified against its sha256 |

## Installation

### From the release

CI publishes the built bundle as a release asset:

```sh
curl -LO https://github.com/lyndon0na/animeko-flapak/releases/latest/download/animeko-6.1.0-x86_64.flatpak
flatpak install --user ./animeko-6.1.0-x86_64.flatpak
```

### Build locally

```sh
# dependencies
sudo dnf install flatpak flatpak-builder      # Fedora
sudo apt install flatpak flatpak-builder      # Debian / Ubuntu

# Flathub, plus the GNOME runtime and SDK
flatpak remote-add --if-not-exists --user flathub https://flathub.org/repo/flathub.flatpakrepo
flatpak install --user flathub org.gnome.Platform//49 org.gnome.Sdk//49

# clone and build
git clone https://github.com/lyndon0na/animeko-flapak.git
cd animeko-flapak
flatpak-builder --user --install --force-clean --repo=repo build me.him188.ani.yaml
```

The manifest fetches the AppImage from the upstream release URL with a sha256
check, so nothing has to be downloaded by hand. For an offline build, swap that
source for the local `path:` form shown in the comment next to it.

### Export a bundle to hand to someone else

```sh
flatpak build-bundle repo animeko-6.1.0-x86_64.flatpak me.him188.ani
```

The bundle is ~280 MB, over GitHub's 100 MB per-file limit, so it is distributed
as a release asset rather than committed.

## Run

```sh
flatpak run me.him188.ani
```

## Uninstall

```sh
flatpak uninstall --user me.him188.ani
```

Flatpak will ask whether to delete the app data in `~/.var/app/me.him188.ani/` as
well.

## Permissions

| Permission | Purpose |
|---|---|
| `--share=network` | Online video sources, BitTorrent, danmaku and Bangumi APIs |
| `--share=ipc` | X11 shared memory |
| `--socket=x11` | JCEF forces the X11 backend; Skiko / AWT render through XWayland too |
| `--socket=wayland` | Wayland support, alongside X11 for the reason above |
| `--socket=pulseaudio` | Audio playback |
| `--device=dri` | GPU rendering and VA-API hardware decoding |
| `--filesystem=home` | Media cache and download directories are user-chosen paths that the app reads and writes directly |
| `--talk-name=org.kde.StatusNotifierWatcher` | System tray |
| `--own-name=org.kde.StatusNotifierItem-2-1` | The tray icon's own D-Bus name |
| `--talk-name=org.freedesktop.Notifications` | Notifications |

`--filesystem=home` is the broadest grant here, because the cache directory can
be anywhere. Narrow it to `xdg-videos` / `xdg-download`, or uncomment the
`/run/media` and `/media` entries in the manifest to cache onto removable drives.

## Files

| File | Purpose |
|---|---|
| `me.him188.ani.yaml` | Flatpak manifest (GNOME runtime 49) |
| `make-bootstrap.py` | rewrites `Ani.cfg` and generates the bootstrap jar, see the [packaging notes](docs/packaging-notes.md) |
| `ani-wrapper` | `/app/bin/ani` entry point |
| `me.him188.ani.desktop` | launcher entry |
| `me.him188.ani.metainfo.xml` | AppStream metadata |
| `icons/me.him188.ani-*.png` | installed icons (128 / 256 / 512) |
| `icons/appimage-icon.png` | source of those icons, taken from the AppImage's own `icon.png` |
| `.github/workflows/build.yml` | CI: builds, verifies and publishes the bundle |
| `docs/` | [Packaging notes](docs/packaging-notes.md) |
| `LICENSE.txt` | AGPL-3.0 license |

## CI

`.github/workflows/build.yml`:

* a push to `main` or a manual dispatch builds, verifies the packaged tree and
  uploads the bundle as a workflow artifact;
* a `v*` tag additionally creates a GitHub release and attaches the bundle to it.

```sh
git tag v6.1.0
git push origin v6.1.0
```

The runner is headless, so the GUI smoke test runs under Xvfb as a best-effort
step that reports without failing the build. The structural check of the packaged
tree is a gating step.

## Notes

* This is **unofficial** packaging. Upstream does not support it; please file
  issues against this repository.
* App state lives in `~/.var/app/me.him188.ani/`, fully separate from a
  system-installed Animeko.
* The App ID is upstream's own `me.him188.ani`; the reasoning is in the
  [packaging notes](docs/packaging-notes.md).

## License

The application and the icon artwork come from
[open-ani/animeko](https://github.com/open-ani/animeko) and are licensed
[AGPL-3.0](LICENSE.txt). This repository only provides the packaging
configuration.

## Links

* [Animeko homepage](https://animeko.org/)
* [Animeko source](https://github.com/open-ani/animeko)
* [Packaging notes](docs/packaging-notes.md)
* [Releases](../../releases)
