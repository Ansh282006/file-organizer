# File Organizer

A local web app that sorts a messy folder into clean subfolders — with a full preview, one-click undo, and editable rules. Runs entirely on your machine. Nothing is uploaded anywhere.

![status](https://img.shields.io/badge/tests-36%20passing-brightgreen)
![license](https://img.shields.io/badge/license-MIT-blue)

---

## What it does

Point it at a folder. It scans the files, shows you exactly where each one would go, and waits. Nothing moves until you click **Organize**. If you change your mind, click **Undo** — every file goes back where it came from.

- **Preview before moving** — dry-run is the default
- **Undo any run** — logged to JSON, reversed in one click
- **Editable rules** — add categories and extensions from the UI
- **Collision-safe** — `photo.jpg` becomes `photo_1.jpg` instead of overwriting
- **Skips hidden files** — `.DS_Store`, dotfiles, `Thumbs.db`
- **No build step** — pure Python + vanilla HTML/CSS/JS

---

## Quick start

### 1. Clone

```bash
git clone https://github.com/Ansh282006/file-organizer.git
cd file-organizer