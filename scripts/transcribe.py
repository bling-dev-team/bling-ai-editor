#!/usr/bin/env python3
"""Word-level transcription. **Groq by default**, WhisperX only on request.

Why Groq is the default: measured over the same edited voiceover, WhisperX's forced-alignment onsets run a
median **+65 ms LATE** (p75 +113, p95 +213) with no drift, a constant bias, because alignment marks
where the phoneme model is confident, which sits inside the word. Groq returned 470 words in 2.0 s;
WhisperX had not finished the same file after an hour on CPU. So Groq is both faster AND better
placed, and it is the default for cuts, captions and any timing work.

Both backends write the SAME schema, so `tighten.py` / `clamp_pads.py` / `plan_cuts.py` are unchanged:
    {media, model, device, language, elapsed_sec, segments, words:[{word,start,end,score}]}

Cached forever: once per video, never twice.

The Groq free tier caps whisper audio per rolling hour: the retry honours the
"try again in Nm Ns" hint in the error, up to 40 tries, so a long master walks through as the window rolls.

The backend default comes from config.yaml transcription.engine; the key comes from GROQ_API_KEY in .env.

Device policy (from the build brief):
  Apple Silicon / no GPU -> CPU + int8. torch's GPU path is still unreliable for
  some ops on Macs; CPU is slower but never silently wrong.
  NVIDIA -> cuda + float16, falling back to CPU int8 on any CUDA error.
"""
import argparse, json, math, os, platform, subprocess, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import FFMPEG, FFPROBE, get, path as cfg_path  # noqa: E402

# whisperx runs in this Python unless config transcription.whisperx_python names another one.
VENV = cfg_path("transcription.whisperx_python") or Path(sys.executable)

def pick_device():
    if platform.system() == "Darwin":
        return "cpu", "int8"            # Apple Silicon: never CUDA, never MPS
    try:
        subprocess.run(["nvidia-smi"], capture_output=True, check=True)
        return "cuda", "float16"
    except Exception:
        return "cpu", "int8"

GROQ_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
GROQ_MAX_BYTES = 20 * 1024 * 1024      # Groq caps uploads; stay well under it
CHUNK_SECONDS = 600                    # 10 min at 96 kbps mp3 is ~7 MB


def _groq_key():
    key = os.environ.get("GROQ_API_KEY", "").strip()
    if not key:
        sys.exit("no GROQ_API_KEY. Put it in the .env file at the repo root.")
    return key


def _to_mp3(media, dst, start=None, dur=None):
    cmd = [FFMPEG, "-v", "error", "-y"]
    if start is not None:
        cmd += ["-ss", f"{start:.3f}"]
    cmd += ["-i", str(media)]
    if dur is not None:
        cmd += ["-t", f"{dur:.3f}"]
    cmd += ["-vn", "-ac", "1", "-c:a", "libmp3lame", "-b:a", "96k", str(dst)]
    subprocess.run(cmd, check=True)
    return dst


def _duration(media):
    out = subprocess.run([FFPROBE, "-v", "error", "-show_entries",
                          "format=duration", "-of", "default=nw=1:nk=1", str(media)],
                         capture_output=True, text=True).stdout.strip()
    return float(out)


def _groq_call(mp3, model, language, key):
    """One request. Returns verbose_json. Retries transient failures rather than dying."""
    import time as _t
    # The free tier caps audio seconds per hour, and the error names the wait
    # ("try again in 2m20.5s"). Honour that wait and keep going.
    import re as _re
    for attempt in range(40):
        r = subprocess.run(["curl", "-sS", GROQ_URL,
                            "-H", f"Authorization: Bearer {key}",
                            "-F", f"file=@{mp3}", "-F", f"model={model}",
                            "-F", "response_format=verbose_json",
                            "-F", "timestamp_granularities[]=word",
                            "-F", "timestamp_granularities[]=segment",
                            "-F", f"language={language}"],
                           capture_output=True, text=True)
        try:
            j = json.loads(r.stdout)
        except Exception:
            j = {"error": {"message": (r.stdout or r.stderr)[:200]}}
        if "words" in j or "text" in j:
            return j
        msg = j.get("error", {}).get("message", "unknown")
        if attempt == 39:
            sys.exit(f"groq failed after 40 tries: {msg}")
        m = _re.search(r"try again in (?:(\d+)m)?([\d.]+)s", msg)
        wait = (int(m.group(1) or 0) * 60 + float(m.group(2)) + 2) if m else 3 * (attempt + 1)
        print(f"  groq retry {attempt+1} in {wait:.0f}s: {msg[:120]}", flush=True)
        _t.sleep(wait)


def _resequence_from_segments(words, segments):
    """Take word ORDER and punctuation from the segments; take TIMING from the words.

    Groq's word list is authoritative for *when* but not for *what order*. It can swap two
    adjacent word timings ("about | compared | this" where the speech is "about | this | compared"),
    float a word into the previous phrase, and return one fewer word than its own text contains.
    Rendered as captions that is visible nonsense.

    A sequence-alignment fix does not work, a swap looks like insert+delete to difflib and it
    duplicates tokens. So work per segment: the segment text gives the correct token sequence and
    the punctuation, and the segment's word timings, SORTED, give the onsets. Pair them in order.
    When the counts disagree, resample the onsets linearly across the segment so every token still
    gets a monotonic time.
    """
    out = []
    for i, sg in enumerate(segments):
        toks = str(sg.get("text", "")).split()
        ws = sorted([w for w in words if w.get("seg") == i], key=lambda w: w["start"])
        if not toks:
            out.extend(ws); continue
        starts = [w["start"] for w in ws]
        ends = [w["end"] for w in ws]
        if len(starts) != len(toks):
            lo = float(sg.get("start", starts[0] if starts else 0.0))
            hi = float(sg.get("end", ends[-1] if ends else lo + 0.5))
            n = len(toks)
            starts = [round(lo + (hi - lo) * k / n, 3) for k in range(n)]
            ends = [round(lo + (hi - lo) * (k + 1) / n, 3) for k in range(n)]
        for k, t in enumerate(toks):
            out.append({"word": t, "start": starts[k], "end": ends[k], "score": 1.0, "seg": i})
    out.sort(key=lambda w: w["start"])
    changed = sum(1 for x, y in zip(words, out) if x.get("word") != y.get("word"))
    words[:] = out
    print(f"  re-sequenced from segment text: {len(out)} tokens, {changed} differed from Groq's order")
    return words


def _tag_segments(words, segments):
    """Tag every word with the index of the Groq segment it belongs to.

    Groq returns almost no punctuation (measured: 1 of 64 words, and its segment text is bare too),
    so `captions.py` cannot break cards on `.`/`?` the way it could with WhisperX. Its SEGMENTS are
    sentence-sized units though, so the segment index is the replacement break signal, and it is
    more robust than a timestamp near a boundary. Groq can place a speaker's leading "and"
    a few ms BEFORE a clip cut, which glues it onto the previous card; the segment id puts it
    where it belongs.
    """
    for w in words:
        mid = (w["start"] + w["end"]) / 2
        w["seg"] = next((i for i, sg in enumerate(segments)
                         if sg["start"] - 0.05 <= mid <= sg["end"] + 0.05), -1)
    # words that fell in no segment inherit the previous one
    last = 0
    for w in words:
        if w["seg"] == -1:
            w["seg"] = last
        last = w["seg"]
    return words


def transcribe_groq(media, out, a):
    """Groq whisper-large-v3 with word timestamps, chunked so long files fit the upload cap."""
    import tempfile, time as _t
    key = _groq_key()
    total = _duration(media)
    t0 = _t.time()
    tmp = Path(tempfile.mkdtemp(prefix="groq-tx-"))
    n_chunks = max(1, math.ceil(total / CHUNK_SECONDS))
    print(f"groq {a.model} on {total:.1f}s of audio in {n_chunks} chunk(s) -> {out}", flush=True)

    words, segments = [], []
    for i in range(n_chunks):
        start = i * CHUNK_SECONDS
        dur = min(CHUNK_SECONDS, total - start)
        mp3 = _to_mp3(media, tmp / f"c{i}.mp3", start if n_chunks > 1 else None,
                      dur if n_chunks > 1 else None)
        size = mp3.stat().st_size
        if size > GROQ_MAX_BYTES:
            sys.exit(f"chunk {i} is {size/1e6:.1f} MB, over the cap, lower CHUNK_SECONDS")
        j = _groq_call(mp3, a.model, a.language, key)
        for w in (j.get("words") or []):
            words.append({"word": str(w.get("word", "")).strip(),
                          "start": round(float(w["start"]) + start, 3),
                          "end": round(float(w.get("end", w["start"])) + start, 3),
                          "score": 1.0})       # Groq gives no per-word confidence
        for sg in (j.get("segments") or []):
            segments.append({**sg,
                             "start": round(float(sg["start"]) + start, 3),
                             "end": round(float(sg["end"]) + start, 3)})
        print(f"  chunk {i+1}/{n_chunks}: {len(j.get('words') or [])} words", flush=True)

    words.sort(key=lambda w: w["start"])
    _tag_segments(words, segments)
    _resequence_from_segments(words, segments)
    payload = {"media": str(media), "model": a.model, "device": "groq-api",
               "language": a.language, "elapsed_sec": round(_t.time() - t0, 1),
               "segments": segments, "words": words}
    json.dump(payload, open(out, "w"), indent=1)
    print(f"{len(words)} words, {len(segments)} segments, {_t.time()-t0:.1f}s")
    print(f"wrote {out}")


def main():
    ap = argparse.ArgumentParser(description="Word-level transcription (Groq or WhisperX) to words.json.")
    ap.add_argument("media", help="video or audio file")
    ap.add_argument("-o", "--out", help="default: <job>/transcript/words.json")
    ap.add_argument("--model", default=None,
                    help="default: whisper-large-v3 (groq) or large-v3 (whisperx)")
    ap.add_argument("--backend", choices=("groq", "whisperx"),
                    default=get("transcription.engine", "groq"))
    ap.add_argument("--whisperx", action="store_true", help="shorthand for --backend whisperx")
    ap.add_argument("--language", default=get("transcription.language", "en"))
    ap.add_argument("--force", action="store_true", help="re-transcribe even if cached")
    a = ap.parse_args()

    media = Path(a.media).expanduser().resolve()
    if not media.is_file():
        sys.exit(f"no such file: {media}")

    out = Path(a.out) if a.out else media.parent.parent / "transcript" / "words.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists() and not a.force:
        print(f"cached, not re-transcribing: {out}   (--force to override)")
        return

    if a.whisperx:
        a.backend = "whisperx"
    if a.backend == "groq":
        a.model = a.model or "whisper-large-v3"
        return transcribe_groq(media, out, a)
    a.model = a.model or "large-v3"
    device, compute = pick_device()
    print(f"whisperx {a.model} on {device}/{compute} -> {out}", flush=True)
    print("first run downloads the model (~3-5 GB) and takes several minutes", flush=True)

    code = f'''
import json, sys, time
import whisperx
t0 = time.time()
audio = whisperx.load_audio({str(media)!r})
model = whisperx.load_model({a.model!r}, {device!r}, compute_type={compute!r}, language={a.language!r})
result = model.transcribe(audio, batch_size=8)
align_model, meta = whisperx.load_align_model(language_code=result["language"], device={device!r})
aligned = whisperx.align(result["segments"], align_model, meta, audio, {device!r},
                         return_char_alignments=False)
words = []
for seg in aligned["segments"]:
    for w in seg.get("words", []):
        if w.get("start") is None:
            continue
        words.append({{"word": w["word"].strip(), "start": round(float(w["start"]), 3),
                       "end": round(float(w["end"]), 3), "score": round(float(w.get("score", 0)), 3)}})
payload = {{"media": {str(media)!r}, "model": {a.model!r}, "device": {device!r},
            "language": result["language"], "elapsed_sec": round(time.time() - t0, 1),
            "segments": aligned["segments"], "words": words}}
json.dump(payload, open({str(out)!r}, "w"), indent=1)
print(f"{{len(words)}} words, {{len(aligned['segments'])}} segments, {{time.time()-t0:.0f}}s")
'''
    # HF's Xet transfer backend can stall mid-download. Force the plain-HTTP path.
    env = {**os.environ, "HF_HUB_DISABLE_XET": "1"}
    r = subprocess.run([str(VENV), "-c", code], env=env)
    if r.returncode != 0:
        sys.exit("whisperx failed, see the error above. Do not retry the same way twice.")
    print(f"wrote {out}")

if __name__ == "__main__":
    main()
