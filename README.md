# Animeko as a Flatpak

Repackages the official `ani-6.1.0-linux-x86_64.appimage` into a Flatpak that
runs on the GNOME runtime.

**English** | [简体中文](README.zh-CN.md)

## Why this needs more than "unpack the AppImage"

The AppImage is a jpackage app-image (JetBrains Runtime 21). Its native launcher
reads `usr/lib/app/Ani.cfg`, expands the `$APPDIR` macro in the 274
`app.classpath` lines and hands the result to the JVM.

That classpath is about **37 KB** once expanded, and the launcher's
`JvmlLauncherData` buffer handling does not survive it. Running the AppImage as
shipped:

```
$ JPACKAGE_DEBUG=true ./ani-6.1.0-linux-x86_64.appimage
[TRACE] JvmLauncher.cpp:318: Need 38457 bytes for JvmlLauncherData buffer
[TRACE] JvmLauncher.cpp:315: Initialized 38457 bytes at 0x56268b98d870 address
[21575]: jli arg[0]: [.../usr/bin/Ani]
[21575]: jli arg[1]: [-classpath]
[21575]: jli arg[2]: [.../core-common-2.2.0-2212d240dfe1e8a7598ee117ccc316d]
[21575]: jli arg[3]: []          <- every remaining argument is empty
...
[21575]: jli arg[19]: []
[21575]:                          <- dies here
Segmentation fault (core dumped)     # exit 139
```

Measured against the real classpath:

| | bytes |
|---|---|
| expanded classpath (274 jars) | 37074 |
| actually written before the truncation | **5306** |

Only the first 39 of 274 entries make it in, and the environment-variable
pointer array that follows the strings in the same buffer gets overwritten with
path data. `jvmLauncherStartJvm()` then calls `setenv()` with a garbage `name`
pointer:

```
(gdb) run
Program received signal SIGSEGV, Segmentation fault.
0x00007ffff7db8291 in setenv () from /lib64/libc.so.6
#0  setenv ()
#1 jvmLauncherStartJvm ()
#2 main ()
$rdi = 0xfffffffffffc97b0     <- invalid `name` argument
```

So the JVM never starts. This is not host specific: it reproduces with an empty
environment, an isolated `$HOME`, from a short path and from the SquashFS mount.

### The fix

`make-bootstrap.py` rewrites `Ani.cfg` so the launcher only ever sees a single
classpath entry, and moves the jar list into a `Class-Path` manifest attribute:

```
app.classpath=$APPDIR/animeko-bootstrap.jar
```

The bootstrap jar contains nothing but `META-INF/MANIFEST.MF`:

```
Manifest-Version: 1.0
Class-Path: desktop-6.1.0.jar ComposeNativeTray-jvm-5ae5e328b757486c3993
 dc64b8be7a5.jar aboutlibraries-compose-jvm-9cd3d26643d8633a3b84932014c4c7c4.jar
 ...
Main-Class: me.him188.ani.app.desktop.AniDesktop
```

The JVM's class loader resolves the listed jars itself, so the launcher's own
buffer stays tiny (`Need 1477 bytes`) and the upstream jar order is preserved —
which matters, because a few libraries ship two versions and the first entry on
the classpath wins.

Verified after the fix: the app starts, `Anitorrent is loaded`,
`FFmpegKit is loaded`, `mediampv is loaded`, the Anime4K shaders resolve from
`resources/anime4k`, `JCEF is initialized`, and the Compose UI renders.

## Verified

```
Ani started. platform: Linux x86_64, version: 6.1.0, isDebug: false
dataDir: file://~/.var/app/me.him188.ani/data/ani
Anitorrent is loaded.          <- bundled libtorrent, GLIBC_2.38 symbols resolved
FFmpegKit is loaded.           <- bundled FFmpeg
mediampv is loaded.            <- bundled libmpv
JCEF is initialized.           <- in-app browser
Using bundled video enhancement shaders from /app/ani/usr/lib/app/resources/anime4k
```

Also checked: every shared library dependency of `Ani`, `libskiko`,
`libmediampv`, `libanitorrent`, `libcef`, `libjvm` and `libmpv` resolves inside
the sandbox with nothing missing, and the app stays up on its own (no crash
after startup, no fatal log lines).

## Layout

```
/app/ani/                 unpacked AppImage tree (usr/bin/Ani, usr/lib/...)
/app/ani/usr/lib/app/     jpackage application dir: Ani.cfg, jars, native/,
                          resources/
/app/ani/usr/lib/app/animeko-bootstrap.jar
/app/bin/ani              wrapper script (the Flatpak command)
```

The app resolves everything relative to `usr/lib/app`, so the tree is kept
byte-for-byte identical to the AppImage apart from `Ani.cfg` and the new
bootstrap jar.

## App id

The Flatpak id is `me.him188.ani`, which is upstream's own application id:

| where | value |
|---|---|
| Android `applicationId` (`app/android/build.gradle.kts`) | `me.him188.ani` |
| macOS `CFBundleURLName` / URL scheme | `me.him188.ani` / `ani` |
| Java package root (main class `me.him188.ani.app.desktop.AniDesktop`) | `me.him188.ani` |
| Data dir (`ProjectDirectories.from("me", "Him188", "Ani")`) | `~/.local/share/ani` |

`open-ani/animeko` is the GitHub org and repository name and carries no
reverse-DNS domain, so it cannot be used directly. Upstream also owns
`animeko.org` / `openani.org`; if you would rather match the project name,
replace `me.him188.ani` with `org.openani.Animeko` throughout (app-id, file
names, icon names, the metainfo `<id>`) — the sandbox data directory then
becomes `~/.var/app/org.openani.Animeko/`.

## Icon

Upstream leaves `iconFile` commented out for Linux in
`app/desktop/build.gradle.kts`:

```kotlin
linux {
    shortcut = true
    packageName = "animeko"
//    iconFile.set(file("icons/a_1024x1024_rounded.ico"))
}
```

so jpackage falls back to Compose Multiplatform's default icon for its icon slot,
and `usr/lib/Ani.png` (1024×1024) really is the **Kotlin logo**. That file is not
used.

The AppImage still carries the real Animeko icon at its root, as `icon.png` —
which `.DirIcon` points at — at 512×512, with a second copy at
`usr/lib/app/resources/icon.png`:

```
icon.png                                   # .DirIcon, 512x512, the real logo
usr/lib/Ani.png                            # jpackage icon slot - Kotlin default
usr/lib/app/desktop-6.1.0.jar
  └── composeResources/.../drawable/a_round.png   # in-app window/tray icon, 192x192
```

That root `icon.png` is what this package installs: the 512×512 entry is that
file verbatim (same md5) and 128/256 are Lanczos downscales of it.
`icons/appimage-icon.png` is a copy of that source so the derivation can be
reproduced and checked without unpacking 780 MB of AppImage:

```sh
magick icons/appimage-icon.png -filter Lanczos -resize 256x256 icons/me.him188.ani-256.png
```

(Upstream's `app/desktop/icons/a_512x512.icns` holds the same logo with macOS's
larger safe-area padding, so it renders noticeably smaller on a Linux desktop and
is not used.)

## Building

```sh
flatpak install flathub org.gnome.Sdk//49        # build toolchain
flatpak-builder --user --install --force-clean --repo=repo build me.him188.ani.yaml
```

Run it:

```sh
flatpak run me.him188.ani
```

The manifest pulls the AppImage from the upstream release URL with a sha256
check, so there is nothing to download by hand. For an offline build, swap that
source for the local `path:` form shown in the comment next to it.

Produce a distributable bundle:

```sh
flatpak build-bundle repo animeko-6.1.0.flatpak me.him188.ani
flatpak install --user animeko-6.1.0.flatpak
```

The bundle is ~280 MB, over GitHub's 100 MB per-file limit, so publish it as a
release asset rather than committing it.

## Sandbox notes

* **X11 is required.** JCEF hardcodes `--ozone-platform=x11` because Chromium's
  Wayland backend crashes the CEF browser process before it reaches the
  INITIALIZED state, and Skiko/AWT also render through XWayland. That is why
  the manifest asks for both `--socket=x11` and `--socket=wayland` instead of
  the usual `--socket=fallback-x11`.

* **JCEF works, but without Chromium's own sandbox.** Chromium's sandbox needs
  either a setuid `chrome-sandbox` (impossible in Flatpak) or unprivileged user
  namespaces, which Flatpak's seccomp policy blocks:

  ```
  $ flatpak run --command=sh org.gnome.Platform//49 -c 'unshare -U true'
  unshare: unshare failed: Operation not permitted
  ```

  CEF detects this and falls back to running its helper processes with
  `--no-sandbox` on its own — visible in the process list:

  ```
  /app/ani/usr/lib/runtime/lib/jcef_helper --type=gpu-process --no-sandbox ...
  ```

  JCEF therefore reaches `INITIALIZED` and the in-app browser used for Bangumi
  login keeps working. Nothing is patched for this: no `--no-sandbox` is forced
  by the wrapper. The renderer loses its inner sandbox, but it is still confined
  by Flatpak's own sandbox.

* **Tray icon.** Compose's tray helper (`libLinuxTray.so`, sd-bus based)
  registers `org.kde.StatusNotifierItem-<pid>-1`. Flatpak cannot express a
  wildcard for that hyphenated name, but the sandbox always runs the app as
  PID 2, so `--own-name=org.kde.StatusNotifierItem-2-1` covers it. Verified from
  inside the sandbox:

  ```
  $ flatpak run --command=gdbus me.him188.ani call --session \
      --dest org.freedesktop.DBus --object-path /org/freedesktop/DBus \
      --method org.freedesktop.DBus.RequestName org.kde.StatusNotifierItem-2-1 0
  (uint32 1,)          # PRIMARY_OWNER
  ```

  The tray is only created once the window is hidden to the tray, so nothing
  appears at startup.

* **Filesystem access** is `--filesystem=home` because the media cache and
  download directories are user-chosen paths that the app writes to directly.
  Narrow it to `xdg-videos`/`xdg-download` in the manifest if you want a tighter
  sandbox, and uncomment the `/run/media` and `/media` entries to cache onto
  removable drives.

* Per-app state lives in `~/.var/app/me.him188.ani/` (`data/ani`,
  `cache/ani`), so it is fully separate from a system-installed Animeko.

## Files

| file | purpose |
|---|---|
| `me.him188.ani.yaml` | Flatpak manifest (GNOME runtime 49) |
| `make-bootstrap.py` | rewrites `Ani.cfg`, generates the bootstrap jar |
| `ani-wrapper` | `/app/bin/ani` entry point |
| `me.him188.ani.desktop` | launcher entry |
| `me.him188.ani.metainfo.xml` | AppStream metadata |
| `icons/me.him188.ani-*.png` | shipped icons; 512×512 is the AppImage's `icon.png` verbatim, 128/256 are downscales |
| `icons/appimage-icon.png` | that source file, kept so the derivation is reproducible |
| `README.zh-CN.md` | this document in Simplified Chinese |
| `LICENSE.txt` | upstream's AGPL-3.0 license |

## License

The application and the icon artwork in this repository come from
[open-ani/animeko](https://github.com/open-ani/animeko) and are licensed
[AGPL-3.0](LICENSE.txt). This repository only repackages it as a Flatpak.
