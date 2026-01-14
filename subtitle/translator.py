import os
from typing import List
from subtitle.subtitle_core import SubtitleEvent
from subtitle.music_core import LyricLine
from openai import OpenAI
import time


class OpenAITranslator:
    def __init__(self, api_key: str, base_url: str = "", model: str = "gpt-4o-mini"):
        # 如果没有传参，尝试从环境变量读取
        self.client = OpenAI(
            api_key=api_key or os.getenv("OPENAI_API_KEY"),
            base_url=base_url or os.getenv("OPENAI_BASE_URL")
        )
        self.model = model
        self.history_window = 5  # 前文窗口大小
        self.future_window = 5   # 后文窗口大小

    def translate_LyricLine(self, lines: List[LyricLine]):
        """
        串行翻译所有歌词行，直接修改 lines 对象中的 translation 属性, 不需要上下文
        """
        total = len(lines)
        print(f"🚀 Start translating {total} lyric lines using {self.model}...")
        for i, current_line in enumerate(lines):
            # 1. 构建 Prompt
            system_prompt = (
                "你是一位专业的歌词翻译人员。你的任务是将日语歌词翻译成流畅、符合语境的简体中文。\n"
                "要求：\n"
                "1. 只输出翻译后的中文文本，不要包含任何解释、标点之外的符号。\n"
                "2. 翻译风格适合歌曲歌词。\n"
                "重要规则：\n"
                "1. 如果当前行只是助词（如「は」「が」）或无法独立翻译，请输出空字符串或等待连接词。\n"
            )

            prompt = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"JP: {current_line.text}"}
            ]

            # 2. 调用 API
            try:
                # 简单的重试机制
                translation: str = self._call_llm_with_retry(prompt)
                current_line.translation = translation

                # 打印进度
                print(f"[{i+1}/{total}] {current_line.text} -> {translation}")

            except Exception as e:
                print(f"❌ Error at line {i+1}: {e}")
                current_line.translation = "Translation Error"

    def translate_subtitle(self, events: List[SubtitleEvent]):
        """
        串行翻译所有事件，直接修改 events 对象中的 translation 属性
        """
        total = len(events)
        print(f"🚀 Start translating {total} lines using {self.model}...")

        for i, current_event in enumerate(events):
            # 1. 构建 Prompt
            prompt = self._build_prompt(events, i)

            # 2. 调用 API
            try:
                # 简单的重试机制
                translation = self._call_llm_with_retry(prompt)
                current_event.translation = translation

                # 打印进度
                print(f"[{i+1}/{total}] {current_event.text} -> {translation}")

            except Exception as e:
                print(f"❌ Error at line {i+1}: {e}")
                current_event.translation = "Translation Error"

    def _build_prompt(self, events: List[SubtitleEvent], current_idx: int) -> List[dict]:
        """
        构建包含前后文的翻译提示
        """
        # 获取前文 (已翻译的)
        start_prev = max(0, current_idx - self.history_window)
        prev_lines = events[start_prev: current_idx]

        # 获取后文 (未翻译的)
        end_next = min(len(events), current_idx + 1 + self.future_window)
        next_lines = events[current_idx + 1: end_next]

        # 构建上下文文本块
        context_str = ""

        if prev_lines:
            context_str += "--- Previous Context ---\n"
            for ev in prev_lines:
                # 格式: 原文 (译文)
                trans = ev.translation if ev.translation else "(无译文)"
                context_str += f"JP: {ev.text}\nCN: {trans}\n"

        context_str += "\n--- Current Line ---\n"
        context_str += f"JP: {events[current_idx].text}\n"

        if next_lines:
            context_str += "\n--- Future Context ---\n"
            for ev in next_lines:
                context_str += f"JP: {ev.text}\n"

        system_prompt = (
            "你是一位专业的字幕翻译人员。你的任务是将当前的日语字幕翻译成流畅、符合语境的简体中文。\n"
            "任务：将[Current Line]的日语翻译成中文。\n"
            "要求：\n"
            "1. 只输出翻译后的中文文本，不要包含任何解释、标点之外的符号。\n"
            "2. 参考[Previous Context]保持人称和术语一致。\n"
            "3. 参考[Future Context]理解这句话在说什么。\n"
            "4. 风格要口语化，适合动漫字幕。\n"
            "重要规则：\n"
            "1. [Current Line] 可能只是一个句子的一半（碎片）。\n"
            "2. 如果它是碎片，请只翻译这个碎片对应的含义，不要为了通顺而补全整个句子！\n"
            "3. 绝对不要把 [Future Context] 中的内容提前翻译到当前行。\n"
            "4. 如果当前行只是助词（如「は」「が」）或无法独立翻译，请输出空字符串或等待连接词。\n"
            "5. 参考 [Previous Context] 保持连贯性，但严禁重复翻译前文已有的内容。"
        )

        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": context_str}
        ]

    def _call_llm_with_retry(self, messages, retries=3) -> str:
        for attempt in range(retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=0.3,  # 低温度保证稳定性
                )
                result = response.choices[0].message.content
                if result:
                    return result
            except Exception as e:
                if attempt == retries - 1:
                    raise e
                time.sleep(2)

        raise RuntimeError("Failed to get a valid response from LLM.")
