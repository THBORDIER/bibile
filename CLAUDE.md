# CLAUDE.md - Bibile Project Guide

## Project Overview

Bibile is a Flask web application that extracts shipment/pickup data ("enlevements") from Hillebrand PDF text and generates structured Excel files with quality control validation. The UI and codebase use **French** for variable names, labels, and documentation.

## Tech Stack

- **Backend**: Python 3.8+ / Flask 3.0+ / pandas 3.0+ / openpyxl 3.1.5+
- **Frontend**: Vanilla HTML5/CSS3/JavaScript (no frameworks, no build step)
- **Deployment**: Windows batch scripts or Linux systemd service
- **Port**: 5001

## Project Structure

```
bibile/
├── server.py                  # Flask app - all backend logic (routes, parsing, Excel generation)
├── requirements.txt           # Python dependencies (Flask, pandas, openpyxl)
├── launcher.pyw               # Windows launcher
├── templates/
│   ├── index.html             # Home page (text input)
│   ├── donnees.html           # Data visualization page
│   ├── historique.html        # History/archive page
│   └── aide.html              # Help page
├── static/
│   ├── css/style.css          # Single stylesheet (CSS variables, flexbox layout)
│   └── js/
│       ├── app.js             # Home page logic
│       ├── donnees.js         # Data visualization logic
│       └── historique.js      # History page logic
├── deployment/                # Linux systemd deployment files
├── logs/                      # Generated log files (gitignored)
└── historique/                # Generated Excel files (gitignored)
```

## Quick Start

```bash
pip install -r bibile/requirements.txt
python bibile/server.py
# Open http://localhost:5001
```

## Running Tests

```bash
python test_dynamic_mapping.py   # Validates delivery mapping extraction
python test_full_process.py      # End-to-end extraction and Excel generation
```

No test framework is configured — tests are standalone scripts using assertions.

## Key Architecture

### Data Flow

```
Pasted PDF text → POST /generer → parser_texte()
  → extraire_totaux_livraisons()        # Extract delivery totals for QC
  → extraire_info_enlevement() (loop)   # Extract each pickup's data
  → controler_totaux()                  # Quality control validation
  → generer_excel()                     # Write formatted .xlsx
  → log_to_file()                       # Write processing log
  → send_file()                         # Return Excel to browser
```

### API Routes

| Route | Method | Purpose |
|-------|--------|---------|
| `/` | GET | Home page |
| `/aide` | GET | Help page |
| `/historique` | GET | History page |
| `/donnees` | GET | Data visualization page |
| `/generer` | POST | Process text, return Excel |
| `/api/historique` | GET | List generated files (JSON) |
| `/api/donnees/<filename>` | GET | Excel data as JSON |
| `/telecharger/<filename>` | GET | Download Excel file |
| `/log/<filename>` | GET | View log file |

### Pallet Counting Rules

- PART PALLET = 0 palettes
- HALF PALLET = 1 palette
- EURO / VMF = specified quantity
- QC totals only validate EURO/VMF counts (HALF/PART excluded per source document convention)

## Coding Conventions

### Python (server.py)

- **French** variable and function names: `texte`, `lignes_tableau`, `enlevement`
- Snake_case for functions: `extraire_info_enlevement()`, `controler_totaux()`
- Function prefixes: `extraire_*` (extract), `controler_*` (check), `parser_*` (parse), `generer_*` (generate)
- Section comments with `===` delimiters
- Paths via `pathlib.Path`
- UTF-8 encoding explicitly specified
- Regex with detailed inline comments

### JavaScript

- Vanilla JS, no frameworks or libraries
- camelCase naming
- Async/await for API calls
- localStorage for draft auto-saving
- One JS file per page

### CSS

- CSS custom properties for design tokens (colors, shadows)
- BEM-inspired class naming (`btn-primary`, `status-message`)
- Responsive flexbox layouts

### File Naming

- Logs: `logs/log_YYYYMMDD_HHMMSS.md`
- Excel: `historique/Enlevements_YYYYMMDD_HHMMSS.xlsx`

## Important Notes

- All backend logic lives in a single `server.py` — there are no separate modules
- No authentication or access control is implemented
- No linting/formatting tools are configured (no eslint, prettier, black, etc.)
- No CI/CD pipeline — deployment is manual
- The `MAX_CONTENT_LENGTH` is 16 MB
- Generated files (logs/, historique/) are gitignored
