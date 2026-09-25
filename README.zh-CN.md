# Animeko Flatpak 打包

把官方 `ani-6.1.0-linux-x86_64.appimage` 重新打包成运行在 GNOME runtime 上的 Flatpak。

[English](README.md) | **简体中文**

## 为什么不能只是「解包 AppImage」

这个 AppImage 是 jpackage 生成的 app-image（JetBrains Runtime 21）。它的原生启动器会读取
`usr/lib/app/Ani.cfg`，把 274 行 `app.classpath` 里的 `$APPDIR` 宏展开，再把结果交给 JVM。

展开后的 classpath 约 **37 KB**，而启动器的 `JvmlLauncherData` 缓冲区处理撑不住这个长度。
直接按原样运行官方 AppImage：

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

所以 JVM 根本没机会启动。这跟具体机器无关：空环境、隔离 `$HOME`、很短的路径、
直接从 SquashFS 挂载，都能复现。

### 修复方式

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

改由 JVM 自己的类加载器去解析这些 jar，启动器那边缓冲区就只剩很小一段
（日志变成 `Need 1477 bytes`），同时**保留了上游的 jar 顺序**——这点很重要，
因为有几个库同时存在两个版本，classpath 上靠前的那个生效。

修复后实测：应用正常启动，`Anitorrent is loaded`、`FFmpegKit is loaded`、
`mediampv is loaded`、Anime4K 着色器从 `resources/anime4k` 正常加载、
`JCEF is initialized`，Compose 界面正常渲染。

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

另外还核对过：`Ani`、`libskiko`、`libmediampv`、`libanitorrent`、`libcef`、`libjvm`、`libmpv`
在沙箱内的**所有**动态库依赖都能解析，零缺失；应用能自行长时间驻留（启动后无崩溃、无 fatal 日志）。

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

Flatpak 的 app-id 用的是 `me.him188.ani`，也就是**上游自己在用的应用 ID**：

| 位置 | 值 |
|---|---|
| Android `applicationId`（`app/android/build.gradle.kts`） | `me.him188.ani` |
| macOS `CFBundleURLName` / URL scheme | `me.him188.ani` / `ani` |
| Java 包名根（主类 `me.him188.ani.app.desktop.AniDesktop`） | `me.him188.ani` |
| 数据目录（`ProjectDirectories.from("me", "Him188", "Ani")`） | `~/.local/share/ani` |

`open-ani/animeko` 是 GitHub 组织名与仓库名，本身不携带反向域名，所以不能直接当 app-id。
上游确实另外持有 `animeko.org` / `openani.org`；如果更希望贴合项目名，把 `me.him188.ani`
全局替换成 `org.openani.Animeko` 即可（app-id、各文件名、图标名、metainfo 的 `<id>`），
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

于是 jpackage 回退到 Compose Multiplatform 的默认图标，AppImage 里带的
`usr/lib/Ani.png` 其实是 **Kotlin 的 logo**，不是 Animeko 的（直接用它会让启动器里出现一个
Kotlin 图标）。

这里改为从上游取真图标：`app/desktop/icons/` 下的 `a_1024x1024_rounded.ico` 和
`a_512x512.icns` 内部都是 PNG，其中 `.icns` 里有一张 1024×1024，解出来存为
`icons/upstream-a_1024.png`，再缩放成实际安装的几档尺寸。这与应用自己给窗口和托盘渲染的
是同一张图——`desktop-6.1.0.jar` 里的
`composeResources/me.him188.ani.desktop.generated.resources/drawable/a_round.png`。

## 构建

```sh
flatpak install flathub org.gnome.Sdk//49        # 构建工具链
flatpak-builder --user --install --force-clean --repo=repo build me.him188.ani.yaml
```

运行：

```sh
flatpak run me.him188.ani
```

导出可分发的 bundle：

```sh
flatpak build-bundle repo animeko-6.1.0.flatpak me.him188.ani
flatpak install --user animeko-6.1.0.flatpak
```

manifest 里 AppImage 用的是官方 release 的 URL（带 sha256 校验），所以**不需要预先下载**。
要离线构建的话，把那条 source 换成注释里给的本地 `path:` 形式即可。

## 沙箱说明

* **必须给 X11。** JCEF 硬编码了 `--ozone-platform=x11`（Chromium 的 Wayland 后端会让
  CEF 浏览器进程在到达 INITIALIZED 之前就崩溃），Skiko/AWT 也是走 XWayland 渲染。
  所以 manifest 同时要了 `--socket=x11` 和 `--socket=wayland`，而不是常见的
  `--socket=fallback-x11`。

* **JCEF 能用，但用不了 Chromium 自带的沙箱。** Chromium 的沙箱要么依赖 setuid 的
  `chrome-sandbox`（在 Flatpak 里不可能），要么依赖非特权 user namespace，而后者被
  Flatpak 的 seccomp 策略禁掉了：

  ```
  $ flatpak run --command=sh org.gnome.Platform//49 -c 'unshare -U true'
  unshare: unshare failed: Operation not permitted
  ```

  CEF 会自己检测到这一点，然后给它的 helper 进程加上 `--no-sandbox` 降级运行——
  在进程列表里就能看到：

  ```
  /app/ani/usr/lib/runtime/lib/jcef_helper --type=gpu-process --no-sandbox ...
  ```

  因此 JCEF 仍能到达 `INITIALIZED`，用于 Bangumi 登录的内置浏览器照常可用。
  这里没有做任何 hack：包装脚本不会强制 `--no-sandbox`。渲染进程失去了它自己的内层沙箱，
  但仍然被 Flatpak 的沙箱约束着。

* **托盘图标。** Compose 的托盘组件（`libLinuxTray.so`，基于 sd-bus）注册的 bus 名是
  `org.kde.StatusNotifierItem-<pid>-1`。Flatpak 无法用通配符表达这种带连字符的名字，
  但沙箱里应用的 PID 固定是 2，所以 `--own-name=org.kde.StatusNotifierItem-2-1` 正好覆盖。
  已在沙箱内验证：

  ```
  $ flatpak run --command=gdbus me.him188.ani call --session \
      --dest org.freedesktop.DBus --object-path /org/freedesktop/DBus \
      --method org.freedesktop.DBus.RequestName org.kde.StatusNotifierItem-2-1 0
  (uint32 1,)          # PRIMARY_OWNER
  ```

  托盘是**懒加载**的：只有窗口被隐藏到托盘后才会创建，所以启动时看不到图标。

* **文件系统权限**给的是 `--filesystem=home`，因为媒体缓存目录和下载目录是用户自选的路径，
  应用是直接按路径读写的（而不是通过 portal 拿 fd）。想收紧沙箱就把它改成
  `xdg-videos`/`xdg-download`；想把缓存放到移动硬盘就取消注释 `/run/media` 和 `/media`。

* 应用状态放在 `~/.var/app/me.him188.ani/`（`data/ani`、`cache/ani`），与系统里安装的
  Animeko 完全隔离。

## 仓库文件

| 文件 | 用途 |
|---|---|
| `me.him188.ani.yaml` | Flatpak manifest（GNOME runtime 49） |
| `make-bootstrap.py` | 改写 `Ani.cfg`，生成引导 jar |
| `ani-wrapper` | `/app/bin/ani` 入口脚本 |
| `me.him188.ani.desktop` | 桌面入口 |
| `me.him188.ani.metainfo.xml` | AppStream 元数据 |
| `icons/me.him188.ani-*.png` | 实际安装的图标，由上游 1024×1024 素材缩放而来 |
| `icons/upstream-a_1024.png` | 该素材，从上游 `a_512x512.icns` 解出 |
| `LICENSE.txt` | 上游 AGPL-3.0 许可证 |

## 许可

应用程序本身以及本文仓库中使用的图标素材均来自
[open-ani/animeko](https://github.com/open-ani/animeko)，采用
[AGPL-3.0](LICENSE.txt) 许可。本仓库只是把它重新打包成 Flatpak。
