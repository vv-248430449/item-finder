# 物品位置管理器

专治丢三落四，记录物品位置、搜索、统计、借出管理、提醒。

## 版本

- **桌面版**：`item_finder.py`（tkinter + SQLite）
- **Android 版**：`main.py`（Kivy + SQLite）
- **备用版**：`item_finder_mobile.py`（Flet）

## 功能

- 增删改查物品（名称、位置、描述、照片）
- 关键词搜索（名称/位置/描述）、模糊匹配
- 常用物品置顶显示
- 自动记录最近查看的物品
- 搜索次数统计，高频查找提醒
- 自定义分类标签
- 借出记录管理
- 自定义提醒（过期、电池、维护等）

## 自动打包 APK

本项目使用 GitHub Actions 自动构建 Android APK。

### 使用方法

1. **Fork 或推送本仓库到 GitHub**
2. **进入 Actions 页面**，找到 "Build Android APK" 工作流
3. **点击 "Run workflow"** 手动触发构建
4. **等待约 10-15 分钟**（首次构建会下载 Android SDK/NDK，较慢）
5. **在 Artifacts 或 Release 页面下载 APK**

### 构建触发条件

- 推送到 `main` 或 `master` 分支
- 手动触发（workflow_dispatch）

## 本地开发

### 桌面版

```bash
python item_finder.py
```

### Kivy 版（测试）

```bash
pip install kivy
python item_finder_kivy.py
```

### 打包（需要 Linux 环境）

```bash
pip install buildozer
buildozer android debug
```

## 数据库

三个版本共用同一个 `items.db`（SQLite），数据完全互通。
