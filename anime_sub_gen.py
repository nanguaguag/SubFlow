import argparse
import os
import json
import whisper
import torch
from pathlib import Path
from subtitle.translator import OpenAITranslator
from subtitle.subtitle_core import WhisperPostProcessor, SRTExporter, ASSExporter

# --------------------------------------------
# 主流程
# --------------------------------------------


def main():
    p = argparse.ArgumentParser(
        description="Auto Anime Subtitle Generator -> generate SRT/ASS subtitles (anime-friendly basic formatting)"
    )
    p.add_argument(
        "input", help="Input audio/video file path (mp3/mp4/mkv/wav...)")
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
    p.add_argument("--max_gap", type=float, default=0.25,
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
        print("🎙️ Transcribing audio...")
        # 建议加上 initial_prompt 提示是动漫
        result = model.transcribe(
            str(input_path),
            language="ja",
            word_timestamps=True,  # 关键：开启词级时间戳以获得更好切分
            beam_size=5,
            initial_prompt="アニメの日本語字幕。常体。口語。"
        )
        # 保存中间结果
        with open(raw_json_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

    # 4. 后处理：清洗与切分
    print("✂️ Processing segments...")
    processor = WhisperPostProcessor(use_word_timestamps=True)
    events = processor.process(result, split_gap=0.25)

    # # 合并过碎片段
    # max_gap=0.1: 只有当两条字幕中间的缝隙小于 0.1秒 时才合并（几乎是连着读）
    # events = processor.merge_nearby(events, max_gap=0.1)
    # print(f"✅ Generated {len(events)} subtitle events.")

    # 5. 翻译模块 (LLM)
    if args.translate:
        api_key = args.api_key or os.getenv("OPENAI_API_KEY")
        if not api_key:
            print("⚠️ Warning: No API Key provided. Skipping translation.")
        else:
            print(
                f"🤖 Translating via {args.gpt_model} (Style: {args.sub_style})...")
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
    print("💾 Saving files...")

    # 导出 SRT
    srt_path = out_dir / f"{base_name}.srt"
    SRTExporter().export(events, str(srt_path))
    print(f"💾 Saved: {srt_path}")

    # 导出 ASS
    ass_path = out_dir / f"{base_name}.ass"
    ASSExporter().export(events, str(ass_path))
    print(f"💾 Saved: {ass_path}")

    print("✨ All done!")
if __name__ == "__main__":
    main()
