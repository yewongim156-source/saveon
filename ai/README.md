# Save:On AI server

FastAPI server for URL and uploaded-video analysis.

## YouTube URL pipeline

`POST /analyze` now accepts a public YouTube watch, Shorts, or `youtu.be`
URL. The server:

1. validates the host and rejects playlists/live streams;
2. reads metadata before download and checks the duration limit;
3. downloads temporary video and audio streams with `yt-dlp`;
4. runs Whisper, EasyOCR, and CLIP through `video_pipeline.py`;
5. returns title, summary, categories, keywords, and entities;
6. deletes the temporary media when the request finishes.

When YouTube does not expose a combined media file, video and audio are kept
separate during analysis. OpenCV reads the video while Whisper reads the audio,
so an external ffmpeg merge step is not required.

Private, login-required, age-restricted, region-restricted, and unavailable
videos are not supported. The MVP runs synchronously, so the Spring request
waits until analysis finishes.

## Configuration

| Environment variable | Default | Purpose |
| --- | ---: | --- |
| `YOUTUBE_MAX_DURATION_SECONDS` | `600` | Reject longer videos before download |
| `YOUTUBE_MAX_FILE_SIZE_MB` | `150` | Maximum downloaded media size |
| `WHISPER_MODEL` | `base` | faster-whisper model name |
| `CLIP_MODEL` | `openai/clip-vit-base-patch32` | Transformers CLIP model |

## Run

```bash
python -m venv .venv
python -m pip install -r requirements.txt
python -m uvicorn main:app --reload --port 8000
```

Run these commands from the `ai` directory. The first analysis downloads the
configured Whisper, OCR, and CLIP model files.

## Test

```bash
python -m unittest discover -s tests -v
```
