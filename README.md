# SubFlow 字幕生成工作流 —— 一键为你的番剧生成字幕

## 使用方法

### 0）克隆本仓库

```bash
git clone https://github.com/nanguaguag/subflow.git
```

### 1）安装依赖

```bash
brew install ffmpeg
python3 -m venv subflow
cd subflow
source ./bin/activate
pip install -U openai-whisper openai
```

### 2）生成番剧字幕（默认同时输出 srt + ass）

```bash
python anime_sub_gen.py your_video.mkv -m medium -l ja
```

会得到：

* `your_video.srt`
* `your_video.ass`

### 3）只输出 SRT 或 ASS

```bash
python anime_sub_gen.py audio.mp3 -m medium -l ja --srt
python anime_sub_gen.py audio.mp3 -m medium -l ja --ass
```

### 4）强制用 MPS

```bash
python anime_sub_gen.py audio.mp3 -m medium -l ja --device mps
```

