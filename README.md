# AP Test Parser

A pipeline for parsing AP exam Free Response Question (FRQ) PDFs and categorizing each question by unit and subtopic using Gemini AI.

## Pipeline

Run these steps in order:

### 1. Clean up scoring files
```bash
uv run delete_scoring_files.py <folder>
```
Removes scoring guide PDFs (files containing "sg" or "scoring" in the name).

### 2. Convert PDFs to images
```bash
uv run pdf_to_images.py <folder>
```
Converts each PDF in the folder to a set of PNG images, one per page. Each PDF gets its own subfolder named after the PDF stem.

Requires [poppler](https://poppler.freedesktop.org/):
```bash
brew install poppler
```

### 3. Analyze FRQ images
```bash
uv run python analyze_frq.py <folder>
```
Sends each PNG to Gemini via Vertex AI, which identifies the question number, AP unit, and subtopic. Results are written to a `.txt` file in each subfolder.

Options:
- `--model <name>` — Gemini model to use (default: `gemini-2.5-flash-lite`)
- `--verbose` / `-v` — Enable debug logging

### 4. Aggregate results into Excel
```bash
uv run concat_txt.py <folder>
```
Collects all `.txt` result files and writes them into a single `unit-topics.xlsx` spreadsheet. Prompts for an output path (defaults to `./unit-topics.xlsx`).

### 5. Sort the spreadsheet
```bash
uv run sort_frq_files.py
```
Sorts all `.xlsx` files found in subdirectories of the project root by:
1. Unit number (ascending)
2. Year (descending)
3. Question number (ascending)

Form B exams (e.g. `2006B`) are sorted after the standard exam for the same year.

## Output Format

Each `.txt` result file contains one line per question part:
```
2008B, 1a, Unit 9: Inference for Quantitative Data: Slopes, Slope of regression line
2025, 2b, Unit 6: Inference for Categorical Data: Proportions, Two-sample z-test
```

The Excel file has columns: **Year**, **Question**, **Unit Topic**, **Source** (hyperlinked to the source PDF).

## Configuration

`analyze_frq.py` reads from a `.env` file or environment variables:

| Variable | Default | Description |
|---|---|---|
| `GOOGLE_GENAI_USE_VERTEXAI` | `true` | Use Vertex AI (vs. Gemini Developer API) |
| `GCP_PROJECT_ID` | `third-flare-455923-k2` | GCP project for Vertex AI |
| `GOOGLE_CLOUD_LOCATION` | `global` | Vertex AI location |
| `GEMINI_DEFAULT_MODEL` | `gemini-2.5-flash-lite` | Gemini model name |
| `GEMINI_API_KEY` | — | API key (only needed if not using Vertex AI) |

## Setup

```bash
# Install dependencies
uv sync

# Authenticate with GCP (for Vertex AI)
gcloud auth application-default login
```
