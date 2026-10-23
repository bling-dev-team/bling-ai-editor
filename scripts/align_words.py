#!/usr/bin/env python3
"""Force-align a KNOWN transcript to the waveform, for word times you can trust.

Groq gives the best TEXT (and it is fast), but its word onsets are inferred, not measured, they
can run late at a phrase restart by a quarter second or more. Forced alignment is the opposite:
it takes the text as given and finds, from the audio itself, where each phoneme actually occurs.
So: **text from Groq, timing from the waveform.**

This uses WhisperX's wav2vec2 aligner ONLY, no Whisper transcription pass, so it is fast (the
model downloads once and is cached by torch). It is a different component from the
Whisper ASR whose transcripts we stopped using.
"""
from __future__ import annotations

import argparse, json, subprocess, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import get, path as cfg_path  # noqa: E402

VENV = cfg_path("transcription.whisperx_python") or Path(sys.executable)


def main():
    ap = argparse.ArgumentParser(description="Force-align known transcript text to the audio with the WhisperX aligner.")
    ap.add_argument("--audio", required=True, help="audio or video file to align against")
    ap.add_argument("--raw", required=True, help="tl_words_raw.json, supplies the segment TEXT")
    ap.add_argument("--out", required=True, help="tl_words.json to write")
    ap.add_argument("--language", default=get("transcription.language", "en"))
    a = ap.parse_args()

    raw = json.load(open(a.raw))
    segs = [{"start": float(s["start"]), "end": float(s["end"]), "text": str(s["text"]).strip()}
            for s in raw["segments"] if str(s.get("text", "")).strip()]
    if not segs:
        sys.exit("no segments with text in the raw transcript")

    code = f'''
import json, whisperx
audio = whisperx.load_audio({str(a.audio)!r})
segs = {segs!r}
m, meta = whisperx.load_align_model(language_code={a.language!r}, device="cpu")
out = whisperx.align(segs, m, meta, audio, "cpu", return_char_alignments=False)
words = []
for si, seg in enumerate(out["segments"]):
    for w in seg.get("words", []):
        if w.get("start") is None:
            continue
        words.append({{"w": w["word"].strip(), "t": round(float(w["start"]), 3),
                       "end": round(float(w["end"]), 3), "seg": si,
                       "score": round(float(w.get("score", 0)), 3)}})
json.dump(words, open({str(a.out)!r}, "w"), indent=1)
print(f"aligned {{len(words)}} words")
'''
    r = subprocess.run([str(VENV), "-c", code])
    if r.returncode != 0:
        sys.exit("forced alignment failed, see the error above")


if __name__ == "__main__":
    main()
