# Animeko Flatpak 打包

把官方 `ani-6.1.0-linux-x86_64.appimage` 重新打包成运行在 GNOME runtime 上的 Flatpak。

[English](README.md) | **简体中文**

## 为什么 AppImage 原样无法启动

这个 AppImage 是 jpackage 生成的 app-image（JetBrains Runtime 21）。它的原生启动器会读取
`usr/lib/app/Ani.cfg`，把 274 行 `app.classpath` 里的 `$APPDIR` 宏展开，再把结果交给 JVM。

展开后的 classpath 约 37 KB，超出了启动器 `JvmlLauncherData` 缓冲区的处理能力。
原样运行官方 AppImage：

```
$ JPACKAGE_DEBUG=true ./ani-6.1.0-linux-x86_64.appimage
[TRACE] JvmLauncher.cpp:318: Need 38457 bytes for JvmlLauncherData buffer
[TRACE] JvmLauncher.cpp:315: Initialized 38457 bytes at 0x56268b98d870 address
[21575]: jli arg[0]: [.../usr/bin/Ani]
[21575]: jli arg[1]: [-classpath]
[21575]: jli arg[2]: [.../core-common-2.2.0-2212d240dfe1e8a7598ee117ccc316d]
[21575]: jli arg[3]: []          <- 从这一条开始，所有参数都是空的
...
[21575]: jli arg[19]: []
[21575]:                          <- 死在这里
Segmentation fault (core dumped)     # 退出码 139
```

与真实 classpath 对比实测：

| | 字节数 |
|---|---|
| 展开后的 classpath（274 个 jar） | 37074 |
| 实际写入后被截断 | **5306** |

274 条里只有前 39 条写了进去；而同一个缓冲区中紧跟在字符串之后的环境变量指针数组，
被路径数据覆盖了。于是 `jvmLauncherStartJvm()` 拿着一个野指针去调 `setenv()`：

```
(gdb) run
Program received signal SIGSEGV, Segmentation fault.
0x00007ffff7db8291 in setenv () from /lib64/libc.so.6
#0  setenv ()
#1 jvmLauncherStartJvm ()
#2 main ()
$rdi = 0xfffffffffffc97b0     <- 非法的 name 参数
```

JVM 完全没有机会启动。该崩溃在空环境、隔离 `$HOME`、很短路径、直接从 SquashFS 挂载的情况下
均可复现，因此是 AppImage 自身的问题，与具体机器无关。

### 本包的绕过方式

`make-bootstrap.py` 改写 `Ani.cfg`，让启动器永远只看到一个 classpath 条目，
把真正的 jar 清单搬到 manifest 的 `Class-Path` 属性里：

```
app.classpath=$APPDIR/animeko-bootstrap.jar
```

这个引导 jar 里只有 `META-INF/MANIFEST.MF`：

```
Manifest-Version: 1.0
Class-Path: desktop-6.1.0.jar ComposeNativeTray-jvm-5ae5e328b757486c3993
 dc64b8be7a5.jar aboutlibraries-compose-jvm-9cd3d26643d8633a3b84932014c4c7c4.jar
 ...
Main-Class: me.him188.ani.app.desktop.AniDesktop
```

改由 JVM 自己的类加载器去解析这些 jar，启动器那边的缓冲区就只剩很小一段
（日志变成 `Need 1477 bytes`），同时保留了上游的 jar 顺序。顺序在这里是有意义的：
有几个库同时存在两个版本，classpath 上靠前的那个生效。

## 实测结果

```
Ani started. platform: Linux x86_64, version: 6.1.0, isDebug: false
dataDir: file://~/.var/app/me.him188.ani/data/ani
Anitorrent is loaded.          <- 自带 libtorrent，GLIBC_2.38 符号可解析
FFmpegKit is loaded.           <- 自带 FFmpeg
mediampv is loaded.            <- 自带 libmpv
JCEF is initialized.           <- 内置浏览器
Using bundled video enhancement shaders from /app/ani/usr/lib/app/resources/anime4k
```

`Ani`、`libskiko`、`libmediampv`、`libanitorrent`、`libcef`、`libjvm`、`libmpv`
在沙箱内的所有动态库依赖都能解析，零缺失；应用能自行长时间驻留，启动后无崩溃、无 fatal 日志。

## 目录布局

```
/app/ani/                 解包后的 AppImage 目录树（usr/bin/Ani、usr/lib/...）
/app/ani/usr/lib/app/     jpackage 应用目录：Ani.cfg、各种 jar、native/、resources/
/app/ani/usr/lib/app/animeko-bootstrap.jar
/app/bin/ani              包装脚本（Flatpak 的 command）
```

应用所有路径都相对于 `usr/lib/app` 解析，所以这棵树与 AppImage 保持逐字节一致，
只改了 `Ani.cfg` 并新增了引导 jar。

## 应用 ID

Flatpak 的 app-id 用的是 `me.him188.ani`，取自上游为这个应用已经在使用的 application id：

| 位置 | 值 |
|---|---|
| Android `applicationId`（`app/android/build.gradle.kts`） | `me.him188.ani` |
| macOS `CFBundleURLName` / URL scheme | `me.him188.ani` / `ani` |
| Java 包名根（主类 `me.him188.ani.app.desktop.AniDesktop`） | `me.him188.ani` |
| 数据目录（`ProjectDirectories.from("me", "Him188", "Ani")`） | `~/.local/share/ani` |

Flatpak 的 app-id 采用反向域名，而 `open-ani/animeko` 是 GitHub 组织名与仓库名，
本身不携带域名。上游另外持有 `animeko.org` 与 `openani.org`；若要改用其中之一，
把 `me.him188.ani` 全局替换掉即可（app-id、各文件名、图标名、metainfo 的 `<id>`），
沙箱数据目录会随之变为 `~/.var/app/org.openani.Animeko/`。

## 图标

上游在 `app/desktop/build.gradle.kts` 里把 Linux 的图标设置注释掉了：

```kotlin
linux {
    shortcut = true
    packageName = "animeko"
//    iconFile.set(file("icons/a_1024x1024_rounded.ico"))
}
```

于是 jpackage 回退到 Compose Multiplatform 的默认图标，`usr/lib/Ani.png`（1024×1024）
是 Kotlin 的 logo。

真正的 Animeko 图标在 AppImage 中的另一个位置。包里包含的图片文件是：

```
icon.png                                   # .DirIcon，512x512，应用图标
usr/lib/Ani.png                            # jpackage 图标槽，Kotlin 默认图
usr/lib/app/resources/icon.png             # 与根目录 icon.png 同一文件
usr/lib/app/desktop-6.1.0.jar
  └── composeResources/.../drawable/a_round.png   # 应用窗口/托盘自画的图标，192x192
```

本包安装的是根目录的 `icon.png`：512×512 那一档是它的原文件（md5 相同），
128/256 是它的 Lanczos 缩放。`icons/appimage-icon.png` 保留了一份原始文件，
这样不必解包 780 MB 的 AppImage 也能复现和核对：

```sh
magick icons/appimage-icon.png -filter Lanczos -resize 256x256 icons/me.him188.ani-256.png
```

上游 `app/desktop/icons/a_512x512.icns` 里是同一个 logo 的 1024×1024 版本，
但带 macOS 的安全区留白，放到 Linux 桌面上会明显偏小。

## 构建

```sh
flatpak install flathub org.gnome.Sdk//49        # 构建工具链
flatpak-builder --user --install --force-clean --repo=repo build me.him188.ani.yaml
```

运行：

```sh
flatpak run me.him188.ani
```

manifest 里 AppImage 用的是官方 release 的 URL（带 sha256 校验），无需预先下载。
要离线构建的话，把那条 source 换成注释里给出的本地 `path:` 形式即可。

导出可分发的 bundle：

```sh
flatpak build-bundle repo animeko-6.1.0.flatpak me.him188.ani
flatpak install --user animeko-6.1.0.flatpak
```

bundle 约 280 MB，超过 GitHub 单文件 100 MB 的限制，请作为 release 附件发布，
不要提交进仓库。

## 沙箱说明

* **必须给 X11。** JCEF 硬编码了 `--ozone-platform=x11`（Chromium 的 Wayland 后端会让
  CEF 浏览器进程在到达 INITIALIZED 之前就崩溃），Skiko/AWT 也是走 XWayland 渲染。
  所以 manifest 同时要了 `--socket=x11` 和 `--socket=wayland`，而不是常见的
  `--socket=fallback-x11`。

* **JCEF 在没有 Chromium 自带沙箱的情况下运行。** Chromium 的沙箱要么依赖 setuid 的
  `chrome-sandbox`（在 Flatpak 里不可能），要么依赖非特权 user namespace，而后者被
  Flatpak 的 seccomp 策略禁掉了：

  ```
  $ flatpak run --command=sh org.gnome.Platform//49 -c 'unshare -U true'
  unshare: unshare failed: Operation not permitted
  ```

  CEF 会自行检测到这一点，并给它的 helper 进程加上 `--no-sandbox` 降级运行，
  在进程列表里可以看到：

  ```
  /app/ani/usr/lib/runtime/lib/jcef_helper --type=gpu-process --no-sandbox ...
  ```

  因此 JCEF 仍能到达 `INITIALIZED`，用于 Bangumi 登录的内置浏览器可正常工作。
  包装脚本并不传 `--no-sandbox`，这是 CEF 自身的降级行为。渲染进程失去了它自己的
  内层沙箱，但仍然受 Flatpak 沙箱约束。

* **托盘图标。** Compose 的托盘组件（`libLinuxTray.so`，基于 sd-bus）注册的 bus 名是
  `org.kde.StatusNotifierItem-<pid>-1`。Flatpak 无法用通配符表达这种带连字符的名字，
  但沙箱里应用的 PID 固定是 2，所以 `--own-name=org.kde.StatusNotifierItem-2-1` 正好覆盖。
  在沙箱内确认：

  ```
  $ flatpak run --command=gdbus me.him188.ani call --session \
      --dest org.freedesktop.DBus --object-path /org/freedesktop/DBus \
      --method org.freedesktop.DBus.RequestName org.kde.StatusNotifierItem-2-1 0
  (uint32 1,)          # PRIMARY_OWNER
  ```

  托盘是懒加载的：只有窗口被隐藏到托盘后才会创建，所以启动时看不到图标。

* **文件系统权限**给的是 `--filesystem=home`，因为媒体缓存目录和下载目录是用户自选的路径，
  应用直接按路径读写（而不是通过 portal 拿 fd）。想收紧沙箱就把它改成
  `xdg-videos`/`xdg-download`；想把缓存放到移动硬盘就取消注释 `/run/media` 和 `/media`。

* 应用状态放在 `~/.var/app/me.him188.ani/`（`data/ani`、`cache/ani`），
  与系统里安装的 Animeko 完全隔离。

## 仓库文件

| 文件 | 用途 |
|---|---|
| `me.him188.ani.yaml` | Flatpak manifest（GNOME runtime 49） |
| `make-bootstrap.py` | 改写 `Ani.cfg`，生成引导 jar |
| `ani-wrapper` | `/app/bin/ani` 入口脚本 |
| `me.him188.ani.desktop` | 桌面入口 |
| `me.him188.ani.metainfo.xml` | AppStream 元数据 |
| `icons/me.him188.ani-*.png` | 实际安装的图标；512×512 是 AppImage 自带 `icon.png` 的原文件，128/256 为其缩放 |
| `icons/appimage-icon.png` | 该原始文件，保留以便复现图标生成过程 |
| `LICENSE.txt` | 上游 AGPL-3.0 许可证 |

## 许可

应用程序本身以及本文仓库中使用的图标素材均来自
[open-ani/animeko](https://github.com/open-ani/animeko)，采用
[AGPL-3.0](LICENSE.txt) 许可。本仓库只是把它重新打包成 Flatpak。
