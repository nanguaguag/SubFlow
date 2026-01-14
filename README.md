# SubFlow 字幕生成工作流 —— 一键为你的番剧/歌词生成字幕

这是一个专为**二次元内容**设计的自动化字幕生成工具。它利用 **OpenAI Whisper** 进行高精度语音转写，并结合 **LLM (GPT-4o)** 进行符合语境的动漫风格翻译。

✨ **最新更新**：新增 **歌曲逐字歌词/卡拉OK模式**，支持生成 Word-level Lyrics

## ✨ 主要功能 (Features)

### 🌸 1. 动漫/剧集模式 (Anime Mode)

* **高精度转写**：使用 Whisper 模型生成带有时间戳的日语字幕。
* **智能切分**：基于语义和标点自动合并过碎的片段，优化阅读体验。
* **AI 翻译**：使用 LLM (GPT-4o-mini 等) 进行日中翻译，支持**上下文记忆**，确保人称和术语连贯。
* **多格式导出**：
    * `.srt` (标准外挂字幕)
    * `.ass` (带样式的双语字幕，默认仿宋体/黑体)

### 🎵 2. 歌曲逐字歌词模式 (Song Mode)

* **逐字时间戳**：精确到词/字级别的对齐，适合制作 MV 或卡拉OK。
* **格式转换**：自动将输入音频转换为 `.m4a` 格式。
* **特效导出**：
* **Enhanced LRC** (`.lrc`): 包含 `<mm:ss.xx>` 逐字时间标签，兼容现代播放器。
* **Karaoke ASS** (`.ass`): 包含 `{\k}` 特效标签，播放时带有卡拉OK变色效果。

---

## 🛠️ 安装指南 (Installation)

### 1. 前置依赖

确保你的电脑上安装了 **FFmpeg**（音频转换和处理必须）。

* **Windows**: [下载编译好的 exe](https://www.gyan.dev/ffmpeg/builds/) 并配置环境变量。
* **Mac**: `brew install ffmpeg`
* **Linux**: `sudo apt install ffmpeg`

### 2. 安装 Python 库

建议使用 Conda 或 venv 创建虚拟环境，然后安装依赖：

```bash
# 基础依赖
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118  # 如果有N卡，建议安装CUDA版
pip install openai-whisper
pip install openai
```

*(注意：如果需要在 GPU 上运行 Whisper，请确保安装了对应 CUDA 版本的 PyTorch)*

### 3. 项目结构

请确保文件目录结构如下：

```text
Project/
├── anime_sub_gen.py       # 主程序入口
└── subtitle/              # 核心模块包
    ├── __init__.py        # 空文件即可
    ├── subtitle_core.py   # 对话字幕处理逻辑
    ├── music_core.py      # 歌曲字幕处理逻辑
    └── translator.py      # LLM 翻译模块

```

---

## 🚀 快速开始 (Usage)

### 🌸 场景 A：生成动漫字幕 (带翻译)

适用于番剧、广播剧、生肉视频。

```bash
# 基本用法：转写 + 翻译 + 双语字幕
python anime_sub_gen.py "D:/Video/anime_ep01.mp4" --translate --api_key "sk-xxxx"

# 指定模型和风格
python anime_sub_gen.py "input.mp4" \
    --model medium \
    --translate \
    --gpt_model gpt-4o-mini \
    --sub_style bilingual

```

**常用参数：**

* `--translate`: 开启翻译功能（需要 API Key）。
* `--sub_style`: 字幕样式。`bilingual` (双语), `zh` (仅中文), `jp` (仅日文)。
* `--max_gap`: 如果两句话间隔小于此秒数（默认 0.25），则合并为一句。

---

### 🎵 场景 B：生成歌曲字幕 (逐字歌词)

适用于提取歌曲歌词、制作 AMV 字幕。

```bash
# 开启歌曲模式
python anime_sub_gen.py "D:/Music/opening_theme.mp3" --mode song --model large-v2

```

**输出文件：**

1. `opening_theme.lrc` (逐字 LRC):
```lrc
[00:14.53]最[00:15.35]高[00:15.93]の[00:18.48]思[00:18.94]い[00:19.28]出[00:19.67]を[00:22.42]
```

2. `opening_theme.lrc` (增强型 LRC):
```lrc
[00:14.53]<00:14.53>最<00:15.35>高<00:15.93>の<00:18.48>思<00:18.94>い<00:19.28>出<00:19.67>を
```

3. `opening_theme_k.ass` (ASS):
```ass
Dialogue: 0,0:00:14.54,0:00:22.42,Karaoke,,0,0,0,,{\k82}最{\k58}高{\k254}の{\k46}思{\k33}い{\k39}出{\k274}を
```

---

## ⚙️ 参数详解 (Parameters)

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `input` | (必填) | 输入视频或音频文件路径 |
| `--mode` | `anime` | **`anime`**: 对话模式 (合并短句，支持翻译)<br>**`song`**: 歌曲模式 (逐字时间戳，LRC/Karaoke) |
| `-m`, `--model` | `medium` | Whisper 模型大小 (tiny/base/small/medium/large/turbo) |
| `--translate` | `False` | 是否启用 LLM 翻译 (仅 Anime 模式有效) |
| `--api_key` | `None` | OpenAI API Key (也可通过环境变量 `OPENAI_API_KEY` 设置) |
| `--base_url` | `None` | 自定义 API Base URL (用于第三方中转) |
| `--gpt_model` | `gpt-4o-mini` | 翻译使用的模型名称 |
| `--sub_style` | `bilingual` | 字幕显示风格: `bilingual`, `zh`, `jp` |
| `--out_dir` | 源文件目录 | 输出文件的保存位置 |

---

## 📝 常见问题 (FAQ)

**Q: 第一次运行非常慢？**
A: 第一次运行时 Whisper 需要下载模型权重（medium 模型约 1.5GB，large 约 3GB）。

**Q: 歌曲模式支持翻译吗？**
A: 目前歌曲模式仅支持提取日文逐字歌词。由于歌词翻译需要严格的音节对齐和意境处理，自动翻译功能正在开发中 (Coming Soon)。

**Q: 如何获得更好的卡拉OK效果？**
A: 建议在歌曲模式下使用 `--model large-v2` 或 `large-v3`，大模型对歌词的逐字对齐（Word timestamp）更加精准。
