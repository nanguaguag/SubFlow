# music_core.py
import subprocess
import json
from dataclasses import dataclass, field
from typing import List, Protocol
from pathlib import Path
from subtitle.subtitle_core import TimeFormatter

# ==========================================
# 1. 歌曲专用数据结构
# ==========================================


@dataclass
class LyricWord:
    """单个字/词的数据结构"""
    text: str
    start: float
    end: float

    @property
    def duration(self) -> float:
        return self.end - self.start


@dataclass
class LyricLine:
    """
    一行歌词（包含多个字）。
    歌曲通常以行位单位，但内部需要保留字的粒度。
    """
    start: float
    end: float
    words: List[LyricWord] = field(default_factory=list)
    translation: str = ""  # 预留翻译字段

    def add_word(self, word: LyricWord):
        self.words.append(word)
        # 自动更新行的起止时间
        if self.words:
            self.start = self.words[0].start
            self.end = self.words[-1].end

    @property
    def text(self) -> str:
        """纯文本内容"""
        return "".join([w.text for w in self.words])

# ==========================================
# 2. 音频转换工具
# ==========================================


class AudioConverter:
    @staticmethod
    def convert_to_m4a(input_path: Path, output_dir: Path) -> Path:
        """
        使用 ffmpeg 将输入转化为 m4a (AAC编码)，适合做歌曲文件
        """
        output_path = output_dir / f"{input_path.stem}.m4a"

        # 如果已存在，直接返回
        if output_path.exists():
            print(f"🎵 Audio already exists: {output_path}")
            return output_path

        print(f"🎵 Converting audio to m4a: {output_path}...")

        cmd = [
            "ffmpeg", "-y",         # 覆盖
            "-i", str(input_path),
            "-vn",                  # 去除视频流
            "-c:a", "aac",          # 编码器
            "-b:a", "192k",         # 比特率
            str(output_path)
        ]

        try:
            subprocess.run(
                cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return output_path
        except subprocess.CalledProcessError as e:
            print(f"❌ FFmpeg conversion failed: {e}")
            raise

# ==========================================
# 3. Whisper 逐字处理器
# ==========================================


class WhisperLyricProcessor:
    """
    专门用于处理歌曲的 Whisper 结果。
    不像对话需要合并，歌曲更需要精确的切割。
    """

    def process(self, result: dict) -> List[LyricLine]:
        raw_segments = result.get("segments", [])
        lines = []

        for seg in raw_segments:
            if seg["no_speech_prob"] >= 0.6:
                # 高概率无语音，跳过
                continue

            # 必须要有 word_timestamps
            if "words" not in seg:
                continue

            # 这里简单地将一个 Whisper Segment 当作一行歌词
            # 实际场景中，Whisper 可能把两句歌词连在一起，
            # 未来可以在这里加入逻辑：如果两个词中间 gap 很大，就拆成两行

            current_line = LyricLine(start=0, end=0, words=[])

            words_data = seg["words"]
            for i, w in enumerate(words_data):
                word_obj = LyricWord(
                    text=w["word"],
                    start=float(w["start"]),
                    end=float(w["end"])
                )

                # 简单的拆行策略：如果当前词和上一个词间隔超过 1.0 秒，强制换行
                if i > 0:
                    prev_end = float(words_data[i-1]["end"])
                    if word_obj.start - prev_end > 1.0:
                        lines.append(current_line)
                        current_line = LyricLine(start=0, end=0, words=[])

                current_line.add_word(word_obj)

            if current_line.words:
                lines.append(current_line)

        return lines

# ==========================================
# 4. 导出器 (LRC & ASS Karaoke)
# ==========================================


class LRCExporter:
    """
    导出 LRC
    格式: [mm:ss.xx]word1[mm:ss.xx]word2[mm:ss.xx]word3[mm:ss.xx]
    """

    def export(self, lines: List[LyricLine], path: str):
        with open(path, "w", encoding="utf-8") as f:
            for line in lines:
                # 行开始时间
                line_start_str = self._format_time(line.start)
                f.write(f"[{line_start_str}]")

                for word in line.words:
                    word_end_str = self._format_time(word.end)
                    f.write(f"{word.text}[{word_end_str}]")

                f.write("\n")

    def _format_time(self, t: float) -> str:
        """mm:ss.xx (LRC standard uses 2 decimal places)"""
        m = int(t // 60)
        s = int(t % 60)
        cs = int((t - int(t)) * 100)
        return f"{m:02d}:{s:02d}.{cs:02d}"


class EnhancedLRCExporter:
    """
    导出增强型 LRC (Enhanced LRC / Word-synchronized LRC)。
    格式: [mm:ss.xx] <mm:ss.xx> word <mm:ss.xx> word
    """

    def export(self, lines: List[LyricLine], path: str):
        with open(path, "w", encoding="utf-8") as f:
            for line in lines:
                # 行开始时间
                line_start_str = self._format_time(line.start)
                f.write(f"[{line_start_str}]")

                for word in line.words:
                    # 某些播放器使用 <mm:ss.xx> 表示该词的开始时间
                    word_start_str = self._format_time(word.start)
                    f.write(f"<{word_start_str}>{word.text}")

                f.write("\n")

    def _format_time(self, t: float) -> str:
        """mm:ss.xx (LRC standard uses 2 decimal places)"""
        m = int(t // 60)
        s = int(t % 60)
        cs = int((t - int(t)) * 100)
        return f"{m:02d}:{s:02d}.{cs:02d}"


class KaraokeASSExporter:
    """
    导出带有卡拉OK特效标签的 ASS 字幕。
    """
    TEMPLATE = """[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
Timer: 100.0000

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Karaoke,Noto Sans CJK SC,60,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,1,2,0,8,10,10,20,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    def export(self, lines: List[LyricLine], path: str):
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.TEMPLATE)

            for line in lines:
                start_t = TimeFormatter.to_ass(line.start)
                end_t = TimeFormatter.to_ass(line.end)

                ass_text = ""
                # 构建卡拉OK文本: {\kXX}Word
                # 注意: \k 的单位是 厘秒 (centiseconds)
                # 并且 ASS 中一行内的时间是累加的，或者相对于行首

                # 为了简化，我们假设字之间是连续的，
                # 如果有空隙，可以加一个空的 {\kXX} 或者合并到前一个词

                current_time = line.start
                for word in line.words:
                    # 计算前导空隙 (如果有)
                    gap = word.start - current_time
                    if gap > 0.01:
                        gap_cs = int(gap * 100)
                        ass_text += f"{{\\k{gap_cs}}}"  # 空格占位

                    dur_cs = int(word.duration * 100)
                    ass_text += f"{{\\k{dur_cs}}}{word.text}"

                    current_time = word.end

                f.write(
                    f"Dialogue: 0,{start_t},{end_t},Karaoke,,0,0,0,,{ass_text}\n")
