#!/usr/bin/env python3
"""Move Animeko's jpackage classpath into a manifest Class-Path attribute.

The AppImage's jpackage launcher (JetBrains Runtime 21) builds its
JvmlLauncherData buffer from the launcher config. With Animeko's 274 classpath
entries the expanded classpath is about 37 KB, and the launcher ends up writing
only the first ~5.3 KB of it before clobbering its own environment-variable
pointer array. The corruption makes setenv() dereference an invalid pointer and
the process dies with SIGSEGV exit code 139 before the JVM is ever started.

Listing the same jars in a manifest Class-Path attribute keeps the launcher's
own classpath string at a single short entry, which avoids the bug entirely and
preserves the upstream jar ordering.

Usage: make-bootstrap.py <app-dir>
"""

import os
import sys
import zipfile

MAIN_CLASS = "me.him188.ani.app.desktop.AniDesktop"
BOOTSTRAP_JAR = "animeko-bootstrap.jar"


def manifest_attribute(name: str, value: str) -> list[str]:
    """Wrap a manifest attribute the way java.util.jar.Manifest expects."""
    prefix = f"{name}: "
    lines = [prefix + value[: 72 - len(prefix)]]
    value = value[72 - len(prefix) :]
    while value:
        lines.append(" " + value[:71])
        value = value[71:]
    return lines


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__.strip(), file=sys.stderr)
        return 2

    app_dir = os.path.abspath(sys.argv[1])
    cfg_path = os.path.join(app_dir, "Ani.cfg")
    if not os.path.isfile(cfg_path):
        print(f"error: {cfg_path} not found", file=sys.stderr)
        return 1

    with open(cfg_path) as f:
        lines = f.read().split("\n")

    # Keep the upstream ordering: a couple of jars ship two versions and the
    # first entry on the classpath wins.
    entries = []
    for line in lines:
        if not line.startswith("app.classpath="):
            continue
        path = line.split("=", 1)[1].replace("$APPDIR", app_dir)
        if os.path.exists(path):
            entries.append(os.path.basename(path))
        else:
            print(f"warning: dropping missing classpath entry {path}", file=sys.stderr)

    if not entries:
        print("error: no classpath entries found in Ani.cfg", file=sys.stderr)
        return 1

    manifest = ["Manifest-Version: 1.0"]
    manifest += manifest_attribute("Class-Path", " ".join(entries))
    manifest.append(f"Main-Class: {MAIN_CLASS}")
    manifest.append("")

    bootstrap_path = os.path.join(app_dir, BOOTSTRAP_JAR)
    with zipfile.ZipFile(bootstrap_path, "w", zipfile.ZIP_STORED) as archive:
        archive.writestr("META-INF/MANIFEST.MF", "\r\n".join(manifest).encode())

    rewritten, replaced = [], False
    for line in lines:
        if line.startswith("app.classpath="):
            if not replaced:
                rewritten.append(f"app.classpath=$APPDIR/{BOOTSTRAP_JAR}")
                replaced = True
            continue
        rewritten.append(line)

    with open(cfg_path, "w") as f:
        f.write("\n".join(rewritten))

    print(f"bootstrap jar: {len(entries)} jars listed, config points at {BOOTSTRAP_JAR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
