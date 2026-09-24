## Standalone executable

Build a single-file binary that runs without Python installed.

### Build (once)

```bash
python -m pip install pyinstaller
```

**Windows:**
```powershell
.\build.ps1
```

**macOS / Linux:**
```bash
./build.sh
```

### Run

**Windows:** double-click `dist\FileOrganizer.exe`

**macOS / Linux:**
```bash
./dist/FileOrganizer
```

The app starts, opens `http://127.0.0.1:8000` in your browser, and stays running until you close the console window.

### Where config lives

A `data/` folder is created next to the executable on first run. It holds:

```
FileOrganizer.exe
data/
├── rules.yaml
├── settings.yaml
├── schedules.yaml
├── folder_rules.yaml
└── logs/
```

Move the whole folder (exe + data/) to back up or relocate.

### Build size

~50–80 MB depending on platform. Most of it is the Python runtime and
bundled dependencies (Pillow, watchdog, uvicorn).

## Video thumbnails (optional)

Video files show a real thumbnail in the preview table when **ffmpeg** is installed.

Install once:

- **Windows:** `winget install --id Gyan.FFmpeg -e`
- **macOS:** `brew install ffmpeg`
- **Linux:** `sudo apt install ffmpeg`

If ffmpeg isn't on PATH, video files show a plain `MP4` / `MOV` / `MKV` badge
instead. The app works fine either way — nothing breaks.

The frame is extracted at ~2 seconds in (skipping fade-ins), resized to 96×96,
and cached in memory. Extracted frames are cached keyed by `(path, mtime)`, so
a file's thumbnail regenerates automatically after it changes.