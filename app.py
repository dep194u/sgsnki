import os, re, uuid, json, shutil, zipfile, subprocess
from pathlib import Path
from flask import Flask, render_template, request, jsonify, send_file, url_for
from werkzeug.utils import secure_filename

BASE = Path(__file__).resolve().parent
UPLOAD_DIR = BASE / "uploads"
OUTPUT_DIR = BASE / "outputs"
UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024 * 1024  # 2 GB
ALLOWED = {".mp4", ".mov", ".mkv", ".webm", ".m4v"}

def valid_youtube_url(url):
    return bool(re.match(r"^(https?://)?(www\.)?(youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)[A-Za-z0-9_-]{6,}", url.strip()))

def run(cmd):
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr[-1800:] or "Command failed")
    return result.stdout

def get_duration(path):
    out = run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
               "-of", "default=noprint_wrappers=1:nokey=1", str(path)])
    return float(out.strip())

def transcribe(path):
    # faster-whisper is optional at installation time but required for AI transcription.
    from faster_whisper import WhisperModel
    model_name = os.getenv("WHISPER_MODEL", "base")
    model = WhisperModel(model_name, device="cpu", compute_type="int8")
    segments, info = model.transcribe(str(path), vad_filter=True, word_timestamps=False)
    items = []
    for s in segments:
        text = (s.text or "").strip()
        if text:
            items.append({"start": float(s.start), "end": float(s.end), "text": text})
    return items

HOOK_WORDS = {
    "secret": 2.0, "mistake": 1.8, "never": 1.3, "best": 1.0, "why": 0.8,
    "how": 0.8, "important": 1.2, "amazing": 1.3, "actually": 0.8,
    "surprising": 1.5, "tip": 1.0, "truth": 1.2, "learn": 0.6,
    "remember": 0.8, "first": 0.4, "stop": 1.0, "secret": 1.5
}

def build_candidates(transcript, duration, min_len=15, max_len=60):
    # Candidate windows are built around speech, with a score for useful/high-energy phrasing.
    windows = []
    step = 5
    start = 0.0
    while start < duration:
        end = min(start + max_len, duration)
        if end - start < min_len:
            break
        parts = [s for s in transcript if s["end"] > start and s["start"] < end]
        text = " ".join(s["text"] for s in parts).strip()
        words = re.findall(r"\b[\w']+\b", text.lower())
        if len(words) >= 12:
            hook_score = sum(weight for w, weight in HOOK_WORDS.items() if w in words)
            question_score = 1.0 if "?" in text else 0.0
            density = min(len(words) / max((end-start), 1), 3.0)
            start_coverage = sum(1 for s in parts if s["start"] < start + 8)
            score = density * 3 + hook_score + question_score + min(start_coverage, 3) * .25
            windows.append({"start": start, "end": end, "text": text, "score": score})
        start += step
    # Greedy select highest scoring non-overlapping candidates.
    selected = []
    for item in sorted(windows, key=lambda x: x["score"], reverse=True):
        if all(item["end"] <= chosen["start"] or item["start"] >= chosen["end"] for chosen in selected):
            selected.append(item)
            if len(selected) == 5:
                break
    # If the video is short or windows overlap heavily, fill with remaining best windows.
    if len(selected) < 5:
        for item in sorted(windows, key=lambda x: x["score"], reverse=True):
            if item not in selected:
                selected.append(item)
                if len(selected) == 5:
                    break
    return sorted(selected, key=lambda x: x["start"])

def make_title(text, number):
    clean = re.sub(r"\s+", " ", text).strip()
    words = clean.split()
    title = " ".join(words[:9]).strip(".,!?;:")
    return (title[:70] or f"Highlight {number}") + ("…" if len(words) > 9 else "")

def render_clip(source, item, out_path):
    start, end = item["start"], item["end"]
    length = max(1, end - start)
    # Center crop to 9:16, scale to 1080x1920, preserve source audio.
    vf = "crop='ih*9/16:ih':(iw-ih*9/16)/2:0,scale=1080:1920:force_original_aspect_ratio=increase"
    run(["ffmpeg", "-y", "-ss", str(start), "-i", str(source), "-t", str(length),
         "-vf", vf, "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
         "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(out_path)])

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/process", methods=["POST"])
def process():
    url = request.form.get("youtube_url", "").strip()
    clip_mode = request.form.get("clip_mode", "both")
    if not valid_youtube_url(url):
        return jsonify(error="Please enter a valid YouTube video URL."), 400
    uploaded = request.files.get("video")
    if not uploaded or not uploaded.filename:
        return jsonify(error="Upload the original video file you own or have permission to edit. A YouTube URL alone cannot provide the video file."), 400
    ext = Path(secure_filename(uploaded.filename)).suffix.lower()
    if ext not in ALLOWED:
        return jsonify(error="Unsupported file type. Upload MP4, MOV, MKV or WebM."), 400

    job_id = uuid.uuid4().hex[:12]
    job_dir = OUTPUT_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    source = UPLOAD_DIR / f"{job_id}{ext}"
    uploaded.save(source)

    try:
        duration = get_duration(source)
        if duration < 15:
            raise ValueError("The video must be at least 15 seconds long.")
        transcript = transcribe(source)
        if not transcript:
            raise ValueError("No speech was detected. This first version selects clips using speech transcription.")
        if clip_mode == "short":
            min_len, max_len = 15, 30
        elif clip_mode == "long":
            min_len, max_len = 30, 60
        else:
            min_len, max_len = 15, 60
        candidates = build_candidates(transcript, duration, min_len, max_len)
        if not candidates:
            raise ValueError("Not enough spoken content to find five suitable clips.")
        clips = []
        for i, item in enumerate(candidates[:5], 1):
            filename = f"clip_{i}.mp4"
            render_clip(source, item, job_dir / filename)
            clips.append({
                "number": i, "filename": filename,
                "start": round(item["start"], 1), "end": round(item["end"], 1),
                "duration": round(item["end"] - item["start"], 1),
                "title": make_title(item["text"], i),
                "caption": item["text"][:260],
                "hashtags": "#shorts #reels #clips #ClipGenius"
            })
        (job_dir / "clips.json").write_text(json.dumps(clips, indent=2), encoding="utf-8")
        zip_path = OUTPUT_DIR / f"{job_id}_clips.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
            for c in clips:
                z.write(job_dir / c["filename"], c["filename"])
        return jsonify(job_id=job_id, clips=clips,
                       zip_url=url_for("download_zip", job_id=job_id))
    except Exception as e:
        shutil.rmtree(job_dir, ignore_errors=True)
        return jsonify(error=str(e)), 500
    finally:
        try: source.unlink(missing_ok=True)
        except Exception: pass

@app.route("/download/<job_id>/<filename>")
def download_clip(job_id, filename):
    if not re.fullmatch(r"[a-f0-9]{12}", job_id) or not re.fullmatch(r"clip_[1-5]\.mp4", filename):
        return "Invalid file", 400
    path = OUTPUT_DIR / job_id / filename
    if not path.exists(): return "File not found", 404
    return send_file(path, as_attachment=True, download_name=filename)

@app.route("/download-all/<job_id>")
def download_zip(job_id):
    if not re.fullmatch(r"[a-f0-9]{12}", job_id): return "Invalid job", 400
    path = OUTPUT_DIR / f"{job_id}_clips.zip"
    if not path.exists(): return "File not found", 404
    return send_file(path, as_attachment=True, download_name="ClipGenius_5_shorts.zip")

@app.route("/health")
def health():
    return jsonify(status="ok")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=False)
