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
| App payload | the upstream `ani-6.1.0-linux-x86_64.appimage`, declared as an [extra-data](https://docs.flatpak.org/en/latest/module-sources.html#extra-data) source: flatpak downloads it on the machine where the app is installed, verifies its sha256, and `apply_extra` unpacks and patches it there |

## Installation

### From the release

CI publishes the built bundle as a release asset:

```sh
curl -LO https://github.com/lyndon0na/animeko-flapak/releases/latest/download/animeko-6.1.0-x86_64.flatpak
flatpak install --user ./animeko-6.1.0-x86_64.flatpak
```

The bundle is a couple of hundred kilobytes: it carries the desktop metadata and
an instruction telling flatpak where to get the app. Installing it downloads the
~337 MB AppImage from the upstream GitHub release.

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

Building needs no AppImage: it is an extra-data source, so the build only uses
the runtime and the SDK. The AppImage is pulled on the machine where the app is
installed, from the upstream release URL, checked against the sha256 recorded in
the manifest.

### Export a bundle to hand to someone else

```sh
flatpak build-bundle repo animeko-6.1.0-x86_64.flatpak me.him188.ani
```

The bundle stays around a hundred kilobytes, because the app is not in it:
whoever installs it downloads the AppImage from GitHub.

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
| `--talk-name=org.kde.StatusNotifierWatcher` | System tray |
| `--own-name=org.kde.StatusNotifierItem-2-1` | The tray icon's own D-Bus name |
| `--talk-name=org.freedesktop.Notifications` | Notifications |
| `--talk-name=org.freedesktop.ScreenSaver` | Inhibit the screen saver and sleep while a video plays |

No host filesystem access is requested. Everything the app stores by default -
the media download folder, the media cache, the database and the logs - lives in
`~/.var/app/me.him188.ani/`, which the sandbox always provides. Pointing the app
at a real path therefore needs a grant too: the folder picker will happily show
you `~/Videos`, but the app cannot read or write it until you allow it.

```sh
flatpak override --user --filesystem=xdg-videos me.him188.ani
```

Use `--filesystem=home` for the whole home directory, or do the same per app in
Flatseal. The manifest lists the alternatives in a comment, in increasing order
of width.

## Files

| File | Purpose |
|---|---|
| `me.him188.ani.yaml` | Flatpak manifest (GNOME runtime 49) |
| `apply_extra` | runs at install and update time: unpacks the AppImage and patches it |
| `make-bootstrap.py` | rewrites `Ani.cfg` and generates the bootstrap jar; executed by `apply_extra`, see the [packaging notes](docs/packaging-notes.md) |
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
* The app is downloaded from GitHub when you install or update, not shipped by
  this repository. Each upstream release is therefore a fresh ~337 MB download,
  and if upstream ever deletes a release asset, new installs break until the
  sha256 in the manifest is pointed at a new one.
* App state lives in `~/.var/app/me.him188.ani/`, fully separate from a
  system-installed Animeko.
* The App ID is upstream's own `me.him188.ani`; the reasoning is in the
  [packaging notes](docs/packaging-notes.md).
* CEF aborts its unzip utility process each time Chromium's component updater
  runs, which made KDE show a crash dialog per abort. The wrapper disables core
  dumps so drkonqi stays quiet — see the
  [known issue](docs/packaging-notes.md#known-issue-cefs-unzip-utility-aborts-during-playback).

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
