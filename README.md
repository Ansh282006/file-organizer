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