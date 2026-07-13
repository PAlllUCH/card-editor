# Card Editor — Agent Guide

## Project Purpose

Tkinter desktop GUI for Arkham Horror LCG fans who print proxy cards. The app scrapes card image data from GitHub TTS/Tabletop Simulator repositories, processes images through an OpenCV pipeline, generates print-ready PDF layouts, adds bleed margins, and upscales via cloud API or local GPU.

---

## Quick Start

```bash
pip install -r requirements.txt   # requests, pillow, opencv-python, numpy
python main.py                     # launch GUI
```

No tests, linters, formatters, or CI configured. No `pyproject.toml` — bare Python.

---

## Architecture Overview

```
main.py                     ← entry: Tk root → MainAppWindow
├── core/                   ← backend logic (no GUI deps)
│   ├── scraper.py          ← GitHub API → downloads card images + CSV tracker
│   ├── image_editor.py     ← OpenCV 8-step image processing pipeline
│   ├── layout_generator.py ← CSV → print-ready PDF grid layout + individual PDFs
│   ├── pdf_editor.py       ← PyMuPDF + OpenCV — add bleed to existing PDFs
│   └── upscaler.py         ← cloud (KIE.ai) + local (Upscayl CLI) upscaling
├── gui/
│   ├── app_window.py       ← MainAppWindow: notebook (5 tabs), theme menu
│   ├── theme_manager.py    ← dark/light theme manager (observer pattern), 70+ color keys
│   ├── components/
│   │   └── image_preview.py ← Canvas-based zoom/pan image viewer
│   └── tabs/
│       ├── tab_scraper.py
│       ├── tab_editor.py
│       ├── tab_layout.py
│       ├── tab_pdf_editor.py
│       └── tab_upscaling.py
├── config.json             ← persisted state (API key in plaintext!)
├── pull_cards.py           ← standalone script: query ArkhamDB API for Dunwich cycle
└── mirror_bleed.bat        ← legacy ImageMagick mirror-bleed script
```

### Critical: The `__old/` directory is dead code and must be ignored. Never read, modify, or reference it.

---

## Tab Workflow (top-to-bottom)

The notebook tabs are ordered 1–5 and must be used sequentially in most cases:

1. **Scraper** — Input a GitHub folder URL → downloads card JSON/image files → generates `cards_data.csv`
2. **Image Editor** — Load CSV → process images through OpenCV pipeline (bg removal, corner fill, color grading, bleed, blending)
3. **Print Layout** — Read CSV → generate grid-layout PDF for duplex printing, or individual card PDFs
4. **PDF Editor** — Add bleed margins to an existing PDF
5. **Upscaling** — Upscale images via KIE.ai cloud API or local Upscayl CLI

---

## CSV Schema & Column Gotcha

The `cards_data.csv` has 9 columns:

```
ArkhamDB, card_name, ID, front name, back name, count, front_downloaded, back_downloaded, count_registered
```

**Critical gotcha:** The `card_name` column was inserted *after* initial development, shifting indices by 1. Never hardcode column indices — always use header name lookups (e.g., `headers.index('front name')`). Multiple places do this dynamically, and the pattern must be followed in any CSV-reading code.

The `update_csv_quantities()` function in `scraper.py` also handles schema migration: if `card_name` or `count_registered` headers are missing, it inserts them automatically.

---

## Threading & UI Communication Pattern

All long-running operations use `threading.Thread(target=..., daemon=True)`.

### Pause/Resume (Scraper)
Uses `threading.Event` (`pause_event`). The worker calls `pause_event.wait()` at checkpoints. UI buttons clear/set the event.

### Callbacks Dictionary (Scraper)
The `run_scraping_task()` function communicates with the UI through a `callbacks` dict with keys: `log`, `finish`, `trigger_pause`, `init_file_list`, `update_file_status`. All callbacks should dispatch UI updates via `app.root.after(0, callback, arg)` for thread safety.

### Stop/Cancel (Upscaler)
The upscaler pipeline uses a `stop_check_fn` callable (a lambda wrapping a `tk.BooleanVar` check) that is polled during API polling and local process execution. When True, raises `InterruptedError`. The local Upscayl path actually calls `process.terminate()` on the subprocess.

---

## Image Processing Pipeline (8 Steps)

`process_image_advanced()` in `core/image_editor.py` executes these steps sequentially:

| Step | Name | Details |
|------|------|---------|
| 0 | Background Removal | Contour Isolation or GrabCut Auto |
| 1 | Base Sizing | mm→px resize at specified DPI |
| 2 | Corner Fill | 7 modes: Telea Inpaint, Navier-Stokes, Pixel Stretch, Smooth Pixel Stretch, Edge Mirror, Dual-Axis Mirror, Gradient Edge Blend |
| 3 | Blend (Before Color) | Conditional — only if `blend_stage == 'Before Color'` |
| 4 | Color Grading | Saturation, Contrast, Brightness, Sepia + presets |
| 5 | Blend (Before Bleed) | Conditional — only if `blend_stage == 'Before Bleed'` |
| 6 | Directional Bleed (Spad) | `cv2.copyMakeBorder` with `BORDER_REFLECT_101` |
| 7 | Blend (After Bleed) | Conditional — only if `blend_stage == 'After Bleed'` |
| 8 | Legacy Scaling | Optional upscale factor resize |

**Non-obvious:** The function converts images with alpha channels to BGR (losing transparency). All corner sizes and fade amounts are *percentage-based* (relative to the smaller image dimension), not pixel values. The function always returns a PIL `Image` (RGB) via `cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)`.

---

## Theme System (Observer Pattern)

`ThemeManager` in `gui/theme_manager.py`:

- Widgets register via `theme_manager.register(callable_or_widget)`
- On theme change, all registered callables are invoked with `(theme_manager,)`
- If a callable has a `configure` method (tk widget), it's called directly
- Two palettes: `LIGHT_COLORS` and `DARK_COLORS`, each with 70+ color keys
- Preferred color access: `theme_manager.c("key_name")`
- Theme preference persisted to `config.json`
- Every tab registers itself via `self.app.theme_manager.register(self._apply_theme)` — the convention is `def _apply_theme(self, tm):`

---

## Config Persistence

`config.json` is read/written by `tab_upscaling.py` on every relevant change (model selection, folder change, etc.). It stores API key, last paths, model selection, upscaling parameters, and theme preference. **The KIE API key is stored in plaintext.**

---

## Non-Obvious Patterns & Gotchas

1. **ArkhamDB ID Formatting**: `format_arkhamdb_id()` pads numeric IDs to 5 digits while preserving alphanumeric suffixes (e.g., `3279a` → `03279a`). This is used in both scraped data and API lookups.

2. **PDF Generation (Duplex Logic)**: `layout_generator.py` positions back-face cards mirrored based on duplex mode:
   - *Long Edge (Horizontal)*: flips columns (`cols - 1 - c`), right margin start
   - *Short Edge (Vertical)*: flips rows (`rows_per_page - 1 - r`), bottom margin start + left margin

3. **Individual PDF Naming**: Cards are named `{card_id}_{copy_number}.pdf`. Copy numbers are cumulative across duplicate CSV rows using an `id_counters` dict — so a card appearing in 2 rows with count=2 each will produce `_1` through `_4`.

4. **PyMuPDF Import**: Imported as `fitz` (the module name), wrapped in a try/except with a helpful error message. Optional dependency.

5. **Image Preview Component**: Extends `tk.Canvas` (not `tk.Label` despite its usage pattern). Supports mouse-wheel zoom (factor 0.1–20x), click-drag pan, double-click to reset. It wraps a PIL Image and renders via `ImageTk.PhotoImage`.

6. **Keyboard Navigation**: The Editor and Upscaling tabs bind `<Up>`/`<Down>` at the root window level for navigating the file queue. Entries/Comboboxes are excluded via `isinstance` check.

7. **Scraper Auto-Pause**: On download error, the scraper auto-pauses and logs `--- AUTO-PAUSED DUE TO ERROR ---`. The user must manually resume.

8. **Config Overwrites**: Upscaling tab `save_config()` is wired to every `<<ComboboxSelected>>`, folder browse, and the notebook tab switch event. It rewrites the entire `config.json` on each call.

9. **`pull_cards.py`** is a standalone script (not part of the GUI) that hardcodes the Dunwich cycle filter (`cycle_code == '2'`). It's not imported by any other module.

10. **`mirror_bleed.bat`** requires ImageMagick's `magick` command. Uses viewport distortion with `-virtual-pixel Mirror` and adds 24px padding on each side.

11. **Default window geometry**: 1150x850.

12. **Empty `__init__.py` files**: All packages (`core/`, `gui/`, `gui/tabs/`, `gui/components/`) have empty `__init__.py` files — they exist only for package recognition.
