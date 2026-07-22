#!/usr/bin/env python3
"""SiliconFlow ASR (FunAudioLLM/SenseVoiceSmall) → SRT.

Transcribes audio via the SiliconFlow audio/transcriptions endpoint.
Splits audio into fixed-size chunks, transcribes each chunk, and assembles
an SRT with chunk-level timestamps. Streams each chunk's result to SRT so
progress is visible via `wc -l sources/subtitles.srt`.

Usage:
    python3 api_transcribe.py sources/audio.wav sources/subtitles.srt
    python3 api_transcribe.py sources/audio.wav sources/subtitles.srt 300
    python3 api_transcribe.py sources/audio.wav sources/subtitles.srt 600 --compress

API key resolution (in order):
    1. SILICONFLOW_API_KEY environment variable
    2. <git repo root>/.config/video-render-pdf/siliconflow_key
    3. ~/.config/video-render-pdf/siliconflow_key
    4. ./.config/siliconflow_key (legacy)

Chunk size guidance:
  - < 30 min → 180s (3 min) chunks — fine timestamps for slides
  - 30-90 min → 300s (5 min) default, good balance
  - > 90 min → 600s (10 min) — fewer API calls, still acceptable for talking-head
  Auto-calculation: min(10, max(3, duration_sec // 20)) minutes.
"""

import argparse
import json
import os
import sys
import time
import subprocess
import urllib.request
import urllib.error
from pathlib import Path

# Allow running the script from any working directory.
_SKILL_ROOT = Path(__file__).resolve().parent.parent
if str(_SKILL_ROOT) not in sys.path:
    sys.path.insert(0, str(_SKILL_ROOT))

from config import load_siliconflow_key

API_URL = "https://api.siliconflow.cn/v1/audio/transcriptions"
MODEL = "FunAudioLLM/SenseVoiceSmall"


def get_duration(audio_path: str) -> float:
    return float(
        subprocess.check_output(
            [
                "ffprobe",
                "-v", "quiet",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                audio_path,
            ]
        )
        .decode()
        .strip()
    )


def split_audio(audio_path: str, chunk_sec: int, temp_dir: str) -> list[tuple[float, str]]:
    """Return [(start_sec, chunk_file_path), ...]."""
    total = get_duration(audio_path)
    chunks = []
    t = 0.0
    i = 0
    while t < total - 0.5:
        seg = os.path.join(temp_dir, f"_chunk_{i:04d}.wav")
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-i", audio_path,
                "-ss", str(t),
                "-t", str(chunk_sec),
                "-ac", "1",
                "-ar", "16000",
                seg,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
        )
        chunks.append((t, seg))
        t += chunk_sec
        i += 1
    return chunks


def compress_audio(audio_path: str, temp_dir: str) -> str:
    """Compress audio to 32kbps mono MP3 to reduce upload size (~1/8 of WAV)."""
    out = os.path.join(temp_dir, "_compressed.mp3")
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-i", audio_path,
            "-ac", "1",
            "-ar", "16000",
            "-b:a", "32k",
            out,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=True,
    )
    return out


def fmt_ts(ts: float) -> str:
    h = int(ts // 3600)
    m = int((ts % 3600) // 60)
    s = int(ts % 60)
    ms = int((ts - int(ts)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def transcribe_chunk(seg_path: str, api_key: str) -> str | None:
    """Call SenseVoiceSmall API. Returns text or None on failure."""
    boundary = "----bilibili_render_pdf_boundary"
    with open(seg_path, "rb") as f:
        data = f.read()

    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="model"\r\n\r\n{MODEL}\r\n'
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="chunk.wav"\r\n'
        f"Content-Type: audio/wav\r\n\r\n"
    ).encode("utf-8") + data + f"\r\n--{boundary}--\r\n".encode("utf-8")

    req = urllib.request.Request(
        API_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            return result.get("text", "").strip()
    except urllib.error.HTTPError as e:
        body_text = e.read().decode("utf-8", errors="replace")[:200]
        raise RuntimeError(f"HTTP {e.code}: {body_text}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"Network error: {e.reason}")


def main():
    parser = argparse.ArgumentParser(
        description="SiliconFlow ASR → SRT via SenseVoiceSmall"
    )
    parser.add_argument("audio", help="Input audio file (WAV recommended)")
    parser.add_argument("srt", help="Output SRT file")
    parser.add_argument(
        "chunk_sec",
        nargs="?",
        type=int,
        default=None,
        help="Chunk size in seconds (auto if omitted: 3-10 min based on duration)",
    )
    parser.add_argument(
        "--compress",
        action="store_true",
        help="Compress audio to 32kbps MP3 before transcribing (reduces upload ~8x)",
    )
    args = parser.parse_args()

    api_key = load_siliconflow_key()

    # Determine chunk size
    if args.chunk_sec:
        chunk_sec = args.chunk_sec
    else:
        duration = get_duration(args.audio)
        # min(10, max(3, duration // 20)) minutes
        chunk_min = min(10, max(3, int(duration // 20)))
        chunk_sec = chunk_min * 60
        print(
            f"Duration: {duration:.0f}s → auto chunk size: {chunk_min} min ({chunk_sec}s)",
            flush=True,
        )

    temp_dir = os.path.dirname(os.path.abspath(args.srt))
    os.makedirs(temp_dir, exist_ok=True)

    # Optionally compress before splitting
    audio_source = args.audio
    if args.compress:
        print("Compressing audio to 32kbps MP3...", flush=True)
        audio_source = compress_audio(args.audio, temp_dir)

    print(
        f"Splitting {audio_source} into {chunk_sec}s chunks...", flush=True
    )
    chunks = split_audio(audio_source, chunk_sec, temp_dir)
    print(f"{len(chunks)} chunks total.", flush=True)

    start = time.time()
    total_duration = get_duration(args.audio)

    with open(args.srt, "w", encoding="utf-8") as f_srt:
        for idx, (t0, seg) in enumerate(chunks, 1):
            text = None
            for attempt in range(3):
                try:
                    text = transcribe_chunk(seg, api_key)
                    break
                except Exception as e:
                    print(
                        f"  chunk {idx}/{len(chunks)} attempt {attempt+1}/3 failed: {e}",
                        flush=True,
                    )
                    time.sleep(min(2 ** attempt, 8))  # backoff: 1s, 2s, 4s
            if text is None:
                print(
                    f"  chunk {idx}/{len(chunks)} FAILED after 3 retries, skipping",
                    flush=True,
                )
                try:
                    os.remove(seg)
                except OSError:
                    pass
                continue

            t1 = min(t0 + chunk_sec, total_duration)
            f_srt.write(
                f"{idx}\n{fmt_ts(t0)} --> {fmt_ts(t1)}\n{text}\n\n"
            )
            f_srt.flush()

            try:
                os.remove(seg)
            except OSError:
                pass

            if idx % 5 == 0 or idx == len(chunks):
                elapsed = time.time() - start
                print(
                    f"  {idx}/{len(chunks)} chunks done, {elapsed:.0f}s elapsed",
                    flush=True,
                )

    elapsed = time.time() - start
    print(f"Done: {len(chunks)} chunks in {elapsed:.1f}s → {args.srt}", flush=True)


if __name__ == "__main__":
    main()
