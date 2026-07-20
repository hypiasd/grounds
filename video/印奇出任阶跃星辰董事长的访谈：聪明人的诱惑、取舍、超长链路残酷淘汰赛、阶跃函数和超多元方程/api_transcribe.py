#!/usr/bin/env python3
"""SiliconFlow ASR (FunAudioLLM/SenseVoiceSmall) -> SRT.

Splits audio into fixed-size chunks, transcribes each via the SiliconFlow
audio/transcriptions endpoint, and assembles an SRT with chunk-level
timestamps. Streams each chunk's result to SRT and flushes so progress is
visible via `wc -l`.
"""
import os
import sys
import time
import subprocess
import json
import urllib.request
import urllib.error

API_URL = "https://api.siliconflow.cn/v1/audio/transcriptions"
MODEL = "FunAudioLLM/SenseVoiceSmall"

KEY_PATH = os.path.expanduser("~/.config/bilibili-render-pdf/siliconflow_key")
with open(KEY_PATH) as f:
    API_KEY = f.read().strip()

audio_path = sys.argv[1]   # sources/audio.wav
srt_path = sys.argv[2]     # sources/subtitles.srt
chunk_sec = int(sys.argv[3]) if len(sys.argv) > 3 else 300  # 5 min chunks


def fmt(ts):
    h = int(ts // 3600); m = int((ts % 3600) // 60)
    s = int(ts % 60); ms = int((ts - int(ts)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def split_audio(path, chunk_sec):
    """Return list of (start_sec, chunk_wav_path)."""
    total = float(subprocess.check_output(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", path]).decode().strip())
    chunks = []
    i = 0
    t = 0.0
    while t < total - 1:
        seg = os.path.join("sources", f"_chunk_{i:03d}.wav")
        subprocess.run(
            ["ffmpeg", "-y", "-i", path, "-ss", str(t), "-t", str(chunk_sec),
             "-ac", "1", "-ar", "16000", seg],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        chunks.append((t, seg))
        t += chunk_sec
        i += 1
    return chunks


def transcribe_chunk(seg_path):
    import urllib.request as ur
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
    req = ur.Request(
        API_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
        method="POST",
    )
    with ur.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read().decode("utf-8"))["text"]


print(f"Splitting {audio_path} into {chunk_sec}s chunks...", flush=True)
chunks = split_audio(audio_path, chunk_sec)
print(f"{len(chunks)} chunks total.", flush=True)

start = time.time()
with open(srt_path, "w", encoding="utf-8") as f:
    for idx, (t0, seg) in enumerate(chunks, 1):
        text = None
        for attempt in range(3):
            try:
                text = transcribe_chunk(seg)
                break
            except Exception as e:
                print(f"  chunk {idx} attempt {attempt+1} failed: {e}", flush=True)
                time.sleep(2 * (attempt + 1))
        if text is None:
            print(f"  chunk {idx} FAILED after retries, skipping", flush=True)
            os.remove(seg)
            continue
        t1 = min(t0 + chunk_sec, 7204.41)
        f.write(f"{idx}\n{fmt(t0)} --> {fmt(t1)}\n{text.strip()}\n\n")
        f.flush()
        os.remove(seg)
        if idx % 5 == 0:
            print(f"  {idx}/{len(chunks)} chunks done, {time.time()-start:.0f}s elapsed",
                  flush=True)

print(f"Done: SRT written to {srt_path}", flush=True)
