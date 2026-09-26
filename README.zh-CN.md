# Animeko Flatpak 打包

把官方 Linux AppImage 重新打包成 Flatpak 的构建配置。

[English](README.md) ｜ **简体中文** ｜ [打包技术说明](docs/packaging-notes.zh-CN.md)

[![build](https://github.com/lyndon0na/animeko-flapak/actions/workflows/build.yml/badge.svg)](https://github.com/lyndon0na/animeko-flapak/actions/workflows/build.yml)

## 应用信息

| 项目 | 值 |
|---|---|
| 名称 | Animeko（简称 Ani） |
| 版本 | 6.1.0 |
| App ID | `me.him188.ani` |
| Runtime | `org.gnome.Platform` 49 |
| 架构 | x86_64 |
| 上游源码 | https://github.com/open-ani/animeko |
| 官网 | https://animeko.org/ |
| 应用本体 | 上游的 `ani-6.1.0-linux-x86_64.appimage`，声名为 [extra-data](https://docs.flatpak.org/en/latest/module-sources.html#extra-data) 源：flatpak 在用户机器上安装时下载并校验 sha256，再由 `apply_extra` 解包和打补丁 |

## 安装

### 方式一：从 Release 下载

CI 会把构建好的 bundle 作为 Release 附件发布：

```sh
curl -LO https://github.com/lyndon0na/animeko-flapak/releases/latest/download/animeko-6.1.0-x86_64.flatpak
flatpak install --user ./animeko-6.1.0-x86_64.flatpak
```

bundle 只有几百 KB：里面是桌面元数据和一条「去哪拿应用」的说明。安装时 flatpak 会从上游
GitHub release 下载约 337 MB 的 AppImage。

### 方式二：本地构建

```sh
# 安装依赖
sudo dnf install flatpak flatpak-builder      # Fedora
sudo apt install flatpak flatpak-builder      # Debian / Ubuntu

# 添加 Flathub 并安装 GNOME runtime 与 SDK
flatpak remote-add --if-not-exists --user flathub https://flathub.org/repo/flathub.flatpakrepo
flatpak install --user flathub org.gnome.Platform//49 org.gnome.Sdk//49

# 克隆并构建
git clone https://github.com/lyndon0na/animeko-flapak.git
cd animeko-flapak
flatpak-builder --user --install --force-clean --repo=repo build me.him188.ani.yaml
```

构建阶段不需要下载任何东西：AppImage 是 extra-data 源，构建只用 runtime 和 SDK。安装时才从
上游 release 的 URL 拉取，并按 manifest 里记录的 sha256 校验。

### 方式三：导出 bundle 给别人

```sh
flatpak build-bundle repo animeko-6.1.0-x86_64.flatpak me.him188.ani
```

bundle 只有一百多 KB，因为应用本体不在里面：安装它的人仍然会从 GitHub 下载 AppImage。

## 运行

```sh
flatpak run me.him188.ani
```

## 卸载

```sh
flatpak uninstall --user me.him188.ani
```

卸载时 flatpak 会询问是否一并删除应用数据（`~/.var/app/me.him188.ani/`）。

## 权限说明

| 权限 | 用途 |
|---|---|
| `--share=network` | 在线视频源、BitTorrent、弹幕与 Bangumi API |
| `--share=ipc` | X11 共享内存 |
| `--socket=x11` | JCEF 强制使用 X11 后端，Skiko / AWT 也走 XWayland |
| `--socket=wayland` | Wayland 支持；同时提供 X11，原因见技术说明 |
| `--socket=pulseaudio` | 音频播放 |
| `--device=dri` | GPU 渲染与 VA-API 硬件解码 |
| `--filesystem=home` | 媒体缓存与下载目录是用户自选路径，应用直接按路径读写 |
| `--talk-name=org.kde.StatusNotifierWatcher` | 系统托盘 |
| `--own-name=org.kde.StatusNotifierItem-2-1` | 托盘图标注册自己的 D-Bus 名 |
| `--talk-name=org.freedesktop.Notifications` | 通知 |
| `--talk-name=org.freedesktop.ScreenSaver` | 播放时抑制熄屏与休眠 |

`--filesystem=home` 是这份打包里最宽的一项权限，因为缓存目录可以选在任意位置。
想收紧就改成 `xdg-videos` / `xdg-download`；想把缓存放到移动硬盘，取消注释
manifest 里的 `/run/media` 与 `/media`。

## 文件说明

| 文件 | 说明 |
|---|---|
| `me.him188.ani.yaml` | Flatpak manifest（GNOME runtime 49） |
| `apply_extra` | 安装/更新时执行：解包 AppImage 并打补丁 |
| `make-bootstrap.py` | 改写 `Ani.cfg` 并生成引导 jar，由 `apply_extra` 调用，详见[技术说明](docs/packaging-notes.zh-CN.md) |
| `ani-wrapper` | `/app/bin/ani` 入口脚本 |
| `me.him188.ani.desktop` | 桌面入口 |
| `me.him188.ani.metainfo.xml` | AppStream 元数据 |
| `icons/me.him188.ani-*.png` | 安装的图标（128 / 256 / 512） |
| `icons/appimage-icon.png` | 上述图标的原始文件，取自 AppImage 自带的 `icon.png` |
| `.github/workflows/build.yml` | CI：构建、校验并发布 bundle |
| `docs/` | [打包技术说明](docs/packaging-notes.zh-CN.md) |
| `LICENSE.txt` | AGPL-3.0 许可证 |

## CI

`.github/workflows/build.yml`：

* 推送到 `main` 或手动触发：构建 → 校验产物目录 → 上传 bundle 作为 workflow artifact；
* 推送 `v*` 标签：额外创建 GitHub Release 并把 bundle 作为附件发布。

```sh
git tag v6.1.0
git push origin v6.1.0
```

Runner 没有显示器，所以 GUI 冒烟测试在 Xvfb 下尽力而为地运行（只报告，不阻断构建）；
对产物目录的结构校验是阻断性的。

## 注意事项

* 这是**非官方**打包，上游不提供支持；有问题请提到本仓库。
* 应用本体在安装或更新时从 GitHub 下载，不由本仓库分发。因此每个上游版本都是一次完整的
  约 337 MB 下载；上游若删除了某个 release 资产，新用户会装不上，直到 manifest 里的 sha256
  指向新的文件。
* 应用数据存放在 `~/.var/app/me.him188.ani/`，与系统里安装的 Animeko 完全隔离。
* App ID 沿用上游自己的 `me.him188.ani`，依据见[技术说明](docs/packaging-notes.zh-CN.md)。
* CEF 在组件更新器运行时会让 unzip 工具进程崩溃，KDE 因此每次弹一个崩溃窗口。
  wrapper 已关闭 core dump 让 drkonqi 保持安静，详见
  [已知问题](docs/packaging-notes.zh-CN.md)。

## 许可证

应用程序与图标素材来自 [open-ani/animeko](https://github.com/open-ani/animeko)，
采用 [AGPL-3.0](LICENSE.txt) 许可；本仓库仅提供打包配置。

## 相关链接

* [Animeko 官网](https://animeko.org/)
* [Animeko 源码](https://github.com/open-ani/animeko)
* [打包技术说明](docs/packaging-notes.zh-CN.md)
* [Releases](../../releases)
