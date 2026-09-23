# Image MLX Lab

<img src="assets/image-mlx-lab-icon.svg" width="80" alt="Image MLX Lab icon">

> Project-wide agent/development rules: `docs/PROJECT_GUIDE.md`

Image MLX Lab 是一个面向 Apple Silicon / MLX 的本地图像生成与编辑研究工作台。当前后端是 Qwen-Image-2.1；项目命名不绑定具体模型，后续可以继续接入其他 MLX 图像模型。

当前主要测试机器：Apple M2 Max，32 GB Unified Memory。

## 快速启动

macOS 可直接双击 `Start-Image-MLX-Lab.command`。

停止使用 `Stop-Image-MLX-Lab.command`。

启动脚本会从自身所在目录定位项目，不包含个人用户绝对路径。

本项目只保存测试代码、运行时源码和结果。模型权重统一放在：

```text
$HOME/Documents/AI-Models/image/qwen-image-2.1-mlx-4bit
$HOME/Documents/AI-Models/image/qwen-image-2.1-mlx-8bit
```

支持两个 Apple Silicon 量化包：
- 4-bit：约 10 GB，优先用于 32 GB Mac 测试。
- 8-bit：约 17.6 GB，需要更多磁盘和统一内存余量。

不使用官方 BF16 全量权重；其主要组件约 33 GB，对 32 GB Mac 余量太小。

## 固定版本

- 4-bit：`ddalcu/Qwen-Image-2.1-MLX-Serve-4bit` @ `88eb1b3bb5591ed59b68a6e1a1c2d9baade73e38`
- 8-bit：`ddalcu/Qwen-Image-2.1-MLX-Serve-8bit` @ `fbda4caa0b4b1e17b5a29633e8deb600386f1eaf`
- runtime：`ddalcu/mlx-serve`
- branch：`feat/qwen-image-2.1`
- runtime commit：`c7c2cc5b3d160ecac2ad16b00d4feedfc6ce5e93`

runtime 目前仍是未正式发布的 Qwen-Image-2.1 feature branch，
所以测试工程同时固定 commit，避免分支继续变化影响复现。


## 下载和安装

虚拟环境和 mlx-serve 运行环境已经建好。

4-bit 下载 / 续传 / 校验：

```bash
cd $HOME/Documents/image-mlx-lab && .venv/bin/python scripts/setup_model.py --model qwen-image-2.1-mlx-4bit
```

8-bit 下载 / 续传 / 校验：

```bash
cd $HOME/Documents/image-mlx-lab && .venv/bin/python scripts/setup_model.py --model qwen-image-2.1-mlx-8bit
```

只重建运行环境、不下载模型：

```bash
cd $HOME/Documents/image-mlx-lab && .venv/bin/python scripts/setup_model.py --runtime-only
```

Hugging Face 本地下载支持未完成文件续传。运行时源码放在 `worktrees/mlx-serve`。

## 启动本地服务器

4-bit：

```bash
cd $HOME/Documents/image-mlx-lab && ./scripts/start_server.sh 4bit
```

8-bit：

```bash
cd $HOME/Documents/image-mlx-lab && ./scripts/start_server.sh 8bit
```

服务器只绑定 `127.0.0.1:11234`，不会向局域网开放。

## 生图

快速冒烟测试：

```bash
cd $HOME/Documents/image-mlx-lab && \
.venv/bin/python scripts/generate.py \
  --prompt "一只红狐狸站在新雪中，清晨自然光，写实摄影" \
  --size 512x512 --steps 4 --seed 42
```


正式质量测试可改成 `1024x1024`、`--steps 40`。
也可以把提示词写到 UTF-8 文件：

```bash
.venv/bin/python scripts/generate.py --prompt-file prompt.txt --steps 40
```

输出目录：

```text
results/generated/
```

文件名自动使用“提示词前缀 + 时间”：

```text
一只红狐狸站在新雪中_20260921-140501-123456.png
```

因此连续生成不会互相覆盖。

## 当前测试边界

这套 4-bit 包主要用于 Apple Silicon 上的 text-to-image 验证。
Qwen-Image-2.1 官方模型还支持原生透明图和多参考图编辑，
但这些能力不应直接用本测试包的结果代替官方 BF16 路径结论。

模型附带的许可证是 **Qwen Research License Agreement**：
研究和评估可用；商业使用需要另行取得商业许可。


## 图片库与中间结果

Workbench 的右侧图片库默认显示正式图片：

- 载入图片
- 文生图 / 图生图 / True Edit 的正式结果
- AI 局部编辑硬合成后的最终结果
- 手动编辑后“保存为新图片”的结果

旧版本留下的 Qwen 原始 `mask-edit` 整图会保留在本机 `results/intermediate/`，默认不混入正式结果。
需要研究模型原始输出时，可在右栏筛选“中间结果”或“全部（含中间结果）”。

整个 `results/` 目录都被 Git 忽略，不会上传到 GitHub。

## 可复现的 MLX 运行时

`setup_model.py --runtime-only` 会固定到项目记录的 `mlx-serve` commit，并自动检查/应用
`patches/qwen-image-2.1-true-edit-mlx.patch`，再构建本地 runtime。
模型权重仍保存在项目目录之外的 `~/Documents/AI-Models/`。
