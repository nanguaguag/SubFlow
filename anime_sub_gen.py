import argparse
import os
import json
import whisper
import torch
from pathlib import Path
# 引入原有模块
from subtitle.translator import OpenAITranslator
from subtitle.subtitle_core import WhisperPostProcessor, SRTExporter, ASSExporter
# 引入新的音乐模块
from subtitle.music_core import AudioConverter, WhisperLyricProcessor, LRCExporter, EnhancedLRCExporter, KaraokeASSExporter

# --------------------------------------------
# 主流程
# --------------------------------------------


def main():
    p = argparse.ArgumentParser(
        description="Auto Subtitle Generator for Anime & Songs")

    p.add_argument(
        "input", help="Input audio/video file path (mp3/mp4/mkv/wav...)")

    # 模式选择
    p.add_argument("--mode", choices=["anime", "song"], default="anime",
                   help="Processing mode: 'anime' for dialogue, 'song' for karaoke lyrics")
    p.add_argument("-m", "--model", default="medium",
                   help="Whisper model: tiny/base/small/medium/large/turbo")

    # 翻译相关
    p.add_argument("-l", "--language", default="ja",
                   help="Language code, e.g. ja, en, zh")
    p.add_argument("--translate", action="store_true",
                   help="Enable JP->CN translation (Mock)")
    p.add_argument("--api_key", default=None, help="OpenAI API Key")
    p.add_argument("--base_url", default=None,
                   help="OpenAI Base URL (optional)")
    p.add_argument("--gpt_model", default="gpt-4o-mini",
                   help="LLM model name (default: gpt-4.1-mini)")  # 默认用 mini

    # 字幕样式相关
    p.add_argument("--sub_style", choices=["bilingual", "zh", "jp"], default="bilingual",
                   help="Subtitle style: bilingual (default), zh, or jp")

    # 输出相关
    p.add_argument("--out_dir", default=None, help="Output directory")
    p.add_argument("--srt", action="store_true", help="Generate .srt")
    p.add_argument("--ass", action="store_true", help="Generate .ass")

    # Whisper 转写参数
    p.add_argument("--device", default=None,
                   help="Force device: cpu or mps (default: whisper auto)")
    p.add_argument("--beam_size", type=int, default=5)
    p.add_argument("--best_of", type=int, default=5)
    p.add_argument("--temperature", type=float, default=0.0)
    p.add_argument("--no_speech_threshold", type=float, default=0.6)
    p.add_argument("--condition_on_previous_text",
                   action="store_true", default=False)
    p.add_argument("--min_gap", type=float, default=0.25,
                   help="Split segments if gap >= this seconds")
    p.add_argument("--max_gap", type=float, default=0.02,
                   help="Merge segments if gap <= this seconds")
    p.add_argument("--max_merged_duration", type=float,
                   default=7.0, help="Max duration after merging")
    p.add_argument("--max_chars", type=int, default=18,
                   help="Max chars per line")
    p.add_argument("--max_lines", type=int, default=2,
                   help="Max lines per subtitle")

    # ASS 样式
    p.add_argument("--play_res_x", type=int, default=1920)
    p.add_argument("--play_res_y", type=int, default=1080)
    p.add_argument("--font", type=str, default="Noto Sans CJK SC")
    p.add_argument("--font_size", type=int, default=54)

    args = p.parse_args()

    # 1. 路径处理 (使用 Pathlib 更优雅)
    input_path = Path(args.input)
    if not input_path.exists():
        raise FileNotFoundError(f"Input not found: {input_path}")

    out_dir = Path(args.out_dir) if args.out_dir else input_path.parent
    base_name = input_path.stem

    if args.mode not in ["song", "anime"]:
        print(f"不支持的参数: --mode {args.mode}")
        print(f"当前只支持动漫和音乐：--mode anime 或 --mode song")
        return

    # ------------------------------------------------------
    # 分支 A: 歌曲模式 (Song Mode)
    # ------------------------------------------------------
    if args.mode == "song":
        print("🎵 Entering Song/Karaoke Mode...")

        # 1. 音频转换 (转为 m4a)
        m4a_path = AudioConverter.convert_to_m4a(input_path, out_dir)

        # 2. Whisper 转写 (强制开启 word_timestamps)
        raw_json_path = out_dir / f"{base_name}_song_raw.json"

        if raw_json_path.exists():
            print("📂 Found existing raw JSON, skipping Whisper...")
            with open(raw_json_path, "r", encoding="utf-8") as f:
                result = json.load(f)
        else:
            device = "cuda" if torch.cuda.is_available() else "cpu"
            print(f"🚀 Loading Whisper model '{args.model}' on {device}...")
            model = whisper.load_model(args.model, device=device)

            print("🎙️ Transcribing song (word-level)...")
            result = model.transcribe(
                str(m4a_path),
                language=args.language,
                word_timestamps=True,  # 歌曲模式强制开启
                initial_prompt="Lyrics of a song. 歌詞。"
            )
            with open(raw_json_path, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)

        # 3. 处理为歌词行结构
        print("✂️ Processing lyrics...")
        lyric_processor = WhisperLyricProcessor()
        lyric_lines = lyric_processor.process(result)
        print(f"✅ Generated {len(lyric_lines)} lyric lines.")

        # 4. (预留) 翻译 - 暂时留空或仅做简单拷贝
        if args.translate:
            print("⚠️ Translation for song mode is not yet implemented (Coming soon).")
            # 未来在这里调用 translator，针对 LyricLine 进行翻译

        # 5. 导出文件
        print("💾 Saving song subtitles...")

        # 导出 LRC
        lrc_path = out_dir / f"{base_name}.lrc"
        LRCExporter().export(lyric_lines, str(lrc_path))
        print(f"  -> {lrc_path}")

        # 导出 Enhanced LRC
        lrc_path = out_dir / f"{base_name}_e.lrc"
        EnhancedLRCExporter().export(lyric_lines, str(lrc_path))
        print(f"  -> {lrc_path}")

        # 导出 Karaoke ASS
        ass_path = out_dir / f"{base_name}_k.ass"
        KaraokeASSExporter().export(lyric_lines, str(ass_path))
        print(f"  -> {ass_path}")

        print("✨ Song processing done!")
        return

    # ------------------------------------------------------
    # 分支 B: 动漫/对话模式 (Anime Mode - 原有逻辑)
    # ------------------------------------------------------
    # ... (保持原有的 Anime 逻辑代码不变，或者封装成函数调用) ...
    # 下面是原有逻辑的简化版，你可以直接把原有代码放在 else 块里

    # 检查是否已经有生成的 raw.json，如果有就跳过 whisper，方便调试翻译
    raw_json_path = out_dir / f"{base_name}_raw.json"

    if raw_json_path.exists():
        print("📂 Found existing raw JSON, skipping Whisper...")
        with open(raw_json_path, "r", encoding="utf-8") as f:
            result = json.load(f)
    else:
        # 2. 加载模型
        device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"🚀 Loading Whisper model '{args.model}' on {device}...")
        model = whisper.load_model(args.model, device=device)

        # 3. 执行转写 (STT)
        print("🎙️ Transcribing anime dialogue...")
        # 建议加上 initial_prompt 提示是动漫
        result = model.transcribe(
            str(input_path),
            language=args.language,
            word_timestamps=True,  # 关键：开启词级时间戳以获得更好切分
            initial_prompt="アニメの日本語字幕。常体。口語。"
        )
        # 保存中间结果
        with open(raw_json_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

    # 4. 后处理：清洗与切分
    print("✂️ Processing segments...")
    processor = WhisperPostProcessor(use_word_timestamps=True)
    events = processor.process(result, split_gap=args.min_gap)

    # # 合并过碎片段
    # # max_gap=0.02: 只有当两条字幕中间的缝隙小于 0.02 秒 时才合并（几乎是连着读）
    # events = processor.merge_nearby(events, max_gap=max_gap)
    # print(f"✅ Generated {len(events)} subtitle events.")

    # 5. 翻译模块 (LLM)
    if args.translate:
        api_key = args.api_key or os.getenv("OPENAI_API_KEY")
        if not api_key:
            print("⚠️ Warning: No API Key provided. Skipping translation.")
        else:
            print(f"🤖 Translating via {args.gpt_model}")
            print(f"→ Translation style: {args.sub_style})...")

            translator = OpenAITranslator(
                api_key=api_key,
                base_url=args.base_url,
                model=args.gpt_model
            )
            # 执行翻译
            translator.translate_events(events)

    # 6. 设置字幕显示模式
    print(f"🎨 Applying subtitle style: {args.sub_style}")
    for ev in events:
        ev.render_mode = args.sub_style

    # 7. 导出文件
    print("💾 Saving anime subtitles...")

    # 导出 SRT
    srt_path = out_dir / f"{base_name}.srt"
    SRTExporter().export(events, str(srt_path))
    print(f"💾 Saved: {srt_path}")

    # 导出 ASS
    ass_path = out_dir / f"{base_name}.ass"
    ASSExporter().export(events, str(ass_path))
    print(f"💾 Saved: {ass_path}")

    print("✨ Anime processing done!")


if __name__ == "__main__":
    main()
