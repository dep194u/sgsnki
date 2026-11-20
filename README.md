# ClipGenius AI

Responsive Flask web app for finding five speech-based highlights from a video file and exporting vertical MP4 clips.

## Important YouTube/copyright limitation
The YouTube URL is used as a reference only. The app does not download videos from YouTube. Upload the matching original video file that you own or have permission to edit. Editing or cropping content does not make it copyright-free. Check licenses, music, footage, and platform policies before posting.

## Requirements
- Python 3.10+
- FFmpeg and FFprobe installed and available on PATH
- 2 GB+ free disk space recommended
- Internet connection on first run so faster-whisper can download its speech model

## Install

### Windows
1. Install Python 3.10 or newer.
2. Install FFmpeg and add its `bin` folder to PATH.
3. Extract this ZIP.
4. Open Command Prompt in the `clipgenius_ai` folder.
5. Run:

```bash
py -m venv venv
venv\\Scripts\\activate
py -m pip install --upgrade pip
pip install -r requirements.txt
py app.py
```

Open http://127.0.0.1:5000

### macOS
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```
Install FFmpeg with your package manager first.

### Linux (Ubuntu/Debian)
```bash
sudo apt update
sudo apt install ffmpeg
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

## Android and PC
The UI is responsive. For private testing on the same Wi-Fi, run the server with `host="0.0.0.0"` (already configured) and open `http://YOUR_PC_LOCAL_IP:5000` on Android. Both devices must be on the same network. For access from anywhere, deploy to a server with HTTPS and sufficient CPU/RAM/storage. Installable PWA support is included; browser support and install prompts vary.

## Current AI behaviour
- Uses faster-whisper `base` model by default to transcribe speech.
- Scores transcript windows using speech density and simple hook-word/question heuristics.
- Selects up to five non-overlapping candidate windows.
- Uses FFmpeg to center-crop to 9:16 and export 1080x1920 MP4.

This is a functional first version, not a guarantee of viral performance. The scoring algorithm is a baseline and should be improved with visual scene detection, semantic models, face-aware reframing, word-level captions, and user review.

## Configuration
Set `WHISPER_MODEL=tiny`, `base`, `small`, or another supported faster-whisper model. `tiny` is faster on low-powered machines; `small` may improve transcription quality but needs more resources.


## One-click Windows launch (after extracting once)
Double-click `Start_ClipGenius.bat`. It creates the virtual environment, installs dependencies, opens the browser, and starts the server. Keep the command window open while using the app. You do not need to extract the ZIP again.

## Online hosting
The repository includes `Procfile` and `apt.txt` for platforms such as Render that support Python web services and apt packages. Push the project to GitHub, create a web service from the repository, and use the build command `pip install -r requirements.txt` and start command `gunicorn --workers 1 --threads 2 --timeout 900 app:app`. Confirm the host supports FFmpeg, long-running uploads, and sufficient RAM/disk. Free hosting may sleep or impose processing/storage limits; do not assume it can handle large video uploads.
