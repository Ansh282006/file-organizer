## Docker (no Python setup)

Runs in a container. One command, no dependency install, no venv.

### 1. Build

```bash
docker compose build
```

### 2. Choose a folder to organize

Set `ORGANIZE_DIR` to the folder on your machine you want the app to see:

**Windows (PowerShell):**
```powershell
$env:ORGANIZE_DIR = "C:\Users\anshb\Downloads"
docker compose up
```

**macOS / Linux:**
```bash
ORGANIZE_DIR=/Users/anshb/Downloads docker compose up
```

### 3. Open

```
http://127.0.0.1:8000
```

**Inside the container, your folder appears as `/data`.** Paste `/data` in the folder input.

### What persists

| Item | Location | Survives container removal? |
|---|---|---|
| `rules.yaml`, `settings.yaml`, `schedules.yaml` | Docker volume `file-organizer-data` | ✅ Yes |
| Undo history (`logs/*.json`) | Docker volume `file-organizer-data` | ✅ Yes |
| Files in `ORGANIZE_DIR` | Your host folder (bind mount) | ✅ Yes |

Reset all config:
```bash
docker compose down -v
docker compose up
```

### Limitations

- **OS trash is disabled inside Docker.** Files can't be sent to your host's Recycle Bin / Trash from a container — use **Quarantine duplicates** instead.
- **File watching** (the "Watch folder" panel) works on Linux hosts. On macOS and Windows it depends on Docker Desktop's file-sharing implementation; if files aren't detected automatically, use **Schedules** or click **Scan** manually.