# subtitle_core.py
import re
import math
from dataclasses import dataclass
from typing import List, Dict, Optional, Protocol

# ==========================================
# 1. 基础数据结构
# ==========================================


@dataclass
class SubtitleEvent:
    """
    表示单条字幕事件。
    预留了 translation 字段，方便未来接入日翻中。
    """
    start: float
    end: float
    text: str          # 原文 (日语)
    translation: str = ""  # 译文 (中文，未来使用)

    # 新增：控制输出模式 'bilingual' | 'zh' | 'jp'
    # 默认双语
    render_mode: str = "bilingual"

    @property
    def duration(self) -> float:
        return self.end - self.start

    @property
    def content(self) -> str:
        """根据模式决定输出内容"""
        # 如果没有翻译，回退到原文
        if not self.translation:
            return self.text

        if self.render_mode == "bilingual":
            # 常见格式：中文在上，日文在下（或者反过来，看你喜好）
            # ASS/SRT 中 \n 是换行
            return f"{self.translation}\n{self.text}"
        elif self.render_mode == "zh":
            return self.translation
        elif self.render_mode == "jp":
            return self.text

        return f"{self.translation}\n{self.text}"

# ==========================================
# 2. 文本处理工具 (纯函数)
# ==========================================


class TextUtils:
    """处理文本清洗、换行、标点优化"""

    _JP_SPACE = "\u3000"

    @staticmethod
    def clean(text: str) -> str:
        text = text.strip().replace(TextUtils._JP_SPACE, " ")
        return re.sub(r"\s+", " ", text)

    @staticmethod
    def format_ja_spacing(text: str) -> str:
        """日语优化：在句号/逗号后加空格，防止字幕太挤"""
        text = TextUtils.clean(text)
        if not text:
            return ""
        # 标点后加空格
        text = re.sub(r"([。！？!?…])\s*", r"\1 ", text)
        text = re.sub(r"([、，,；;：:])\s*", r"\1 ", text)
        return re.sub(r"\s+", " ", text).strip()

    @staticmethod
    def smart_wrap(text: str, max_chars: int = 18, max_lines: int = 2) -> str:
        """
        智能换行：优先在标点处折行
        """
        text = TextUtils.clean(text)
        if len(text) <= max_chars:
            return text

        lines = []
        remaining = text

        # 简单标点优先级
        punct_priority = "，,。.!?！？；;、… "

        for _ in range(max_lines - 1):
            if len(remaining) <= max_chars:
                break

            # 搜索最佳切分点（在 max_chars 附近的标点）
            cut_point = max_chars
            search_window = remaining[:max_chars + 2]  # 稍微多看一点

            best_idx = -1
            for p in punct_priority:
                idx = search_window.rfind(p)
                # 只有当标点位于行中间偏后位置时才切分，避免第一字就是标点
                if idx > max_chars // 2:
                    best_idx = idx + 1
                    break

            if best_idx != -1:
                cut_point = best_idx

            lines.append(remaining[:cut_point].strip())
            remaining = remaining[cut_point:].strip()

        lines.append(remaining)
        return "\n".join(lines)

# ==========================================
# 3. Whisper 结果处理器 (后处理)
# ==========================================


class WhisperPostProcessor:
    """将 Whisper 的原始 result(dict) 转换为标准的 List[SubtitleEvent]"""

    def __init__(self, use_word_timestamps: bool = True):
        self.use_word_timestamps = use_word_timestamps

    def process(self, result: dict, split_gap: float = 0.3) -> List[SubtitleEvent]:
        """
        split_gap 参数: 控制多大的静音就算断句，传入 => gap_threshold
        """
        raw_segments = result.get("segments", [])
        events = []

        for seg in raw_segments:
            # 策略：如果有 word timestamps，则进行更细粒度的切分
            if self.use_word_timestamps and "words" in seg:
                # 传入 split_gap
                events.extend(self._split_by_words(
                    seg["words"], gap_threshold=split_gap))
            else:
                # 回退到 Segment 级别
                text = TextUtils.format_ja_spacing(seg["text"])
                if text:
                    events.append(SubtitleEvent(
                        seg["start"], seg["end"], text))

        return events

    def _split_by_words(self, words: List[Dict], gap_threshold: float) -> List[SubtitleEvent]:
        """核心切分逻辑：根据词间距和标点切分"""
        output = []
        buffer = []

        # 句末标点：遇到这些必须切
        sent_end_punct = set("。！？!?…")
        # 句中标点：遇到这些，如果后面还有静音，也建议切（可选）
        mid_punct = set("、，,")

        def commit_buffer():
            if not buffer:
                return
            start = buffer[0]["start"]
            end = buffer[-1]["end"]
            # 拼接单词
            text = "".join(w["word"] for w in buffer)
            text = TextUtils.format_ja_spacing(text)
            if text:
                output.append(SubtitleEvent(float(start), float(end), text))
            buffer.clear()

        last_end = None

        for w in words:
            start = float(w["start"])
            end = float(w["end"])
            word_text = w["word"]

            if last_end is not None:
                gap = start - last_end

                # --- 调试打印 ---
                # 如果 gap 比较大，或者包含了特定的词，打印出来看看
                if gap >= gap_threshold:
                    print(f"🔍 词间距检测: '{buffer[-1]['word']}' "
                          "-> '{word_text}' | Gap: {gap:.3f}s | "
                          "阈值: {gap_threshold}s")
                    commit_buffer()
                # ----------------

            # --- 切分逻辑核心 ---

            should_split = False

            # 1. 检查静音 Gap (物理切分)
            if last_end is not None:
                if (start - last_end) >= gap_threshold:
                    should_split = True

            # 2. 检查上一词的结尾标点 (语义切分)
            # 如果 buffer 里的上一个词带有句号，不管静音多短，都得切
            if buffer:
                last_word_text = buffer[-1]["word"]
                if any(p in last_word_text for p in sent_end_punct):
                    should_split = True

            if should_split:
                commit_buffer()

            buffer.append(w)
            last_end = end

        commit_buffer()  # 提交剩余
        return output

    @staticmethod
    def merge_nearby(events: List[SubtitleEvent], max_gap: float = 0.1, max_dur: float = 7.0) -> List[SubtitleEvent]:
        """合并过碎的字幕"""
        if not events:
            return []
        merged = []
        current = events[0]

        for next_ev in events[1:]:
            gap = next_ev.start - current.end
            combined_dur = next_ev.end - current.start

            if gap <= max_gap and combined_dur <= max_dur:
                # 合并
                new_text = (current.text + " " +
                            next_ev.text).replace("  ", " ")
                current = SubtitleEvent(
                    current.start, next_ev.end, new_text.strip())
            else:
                merged.append(current)
                current = next_ev

        merged.append(current)
        return merged

# ==========================================
# 4. 导出器 (Strategy Pattern)
# ==========================================


class SubtitleExporter(Protocol):
    def export(self, events: List[SubtitleEvent], path: str, **kwargs): ...


class TimeFormatter:
    @staticmethod
    def to_srt(t: float) -> str:
        """HH:MM:SS,mmm"""
        ms = int(round(t * 1000))
        s, ms = divmod(ms, 1000)
        m, s = divmod(s, 60)
        h, m = divmod(m, 60)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    @staticmethod
    def to_ass(t: float) -> str:
        """H:MM:SS.cc"""
        cs = int(round(t * 100))
        s, cs = divmod(cs, 100)
        m, s = divmod(s, 60)
        h, m = divmod(m, 60)
        return f"{h:d}:{m:02d}:{s:02d}.{cs:02d}"


class SRTExporter:
    def export(self, events: List[SubtitleEvent], path: str, max_chars: int = 18):
        with open(path, "w", encoding="utf-8") as f:
            for i, ev in enumerate(events, 1):
                # 使用 ev.content，如果未来有翻译，这里会自动包含
                text = TextUtils.smart_wrap(ev.content, max_chars=max_chars)
                if not text:
                    continue

                f.write(f"{i}\n")
                f.write(
                    f"{TimeFormatter.to_srt(ev.start)} --> {TimeFormatter.to_srt(ev.end)}\n")
                f.write(text + "\n\n")


class ASSExporter:
    """提供基础的 ASS 样式"""
    TEMPLATE = """[Script Info]
ScriptType: v4.00+
PlayResX: {res_x}
PlayResY: {res_y}

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, BorderStyle, Outline, Shadow, Alignment, MarginV
Style: Default,{font},{size},&H00FFFFFF,&H00000000,&H80000000,0,1,2,0,2,20

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    def export(self, events: List[SubtitleEvent], path: str,
               res_x=1920, res_y=1080, font="Noto Sans CJK SC", size=54, max_chars=18):

        header = self.TEMPLATE.format(
            res_x=res_x, res_y=res_y, font=font, size=size)

        with open(path, "w", encoding="utf-8") as f:
            f.write(header)
            for ev in events:
                text = TextUtils.smart_wrap(ev.content, max_chars=max_chars)
                if not text:
                    continue

                # ASS 转义
                text = text.replace("\n", r"\N").replace(
                    "{", r"\{").replace("}", r"\}")

                start_t = TimeFormatter.to_ass(ev.start)
                end_t = TimeFormatter.to_ass(ev.end)

                f.write(
                    f"Dialogue: 0,{start_t},{end_t},Default,,0,0,0,,{text}\n")
