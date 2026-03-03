#!/usr/bin/env python3
"""
AP Chemistry FRQ Image Analyzer

Analyzes PNG images of AP Chemistry FRQ pages using Gemini via Vertex AI,
categorizing each question by unit and subtopic.

uv run python analyze_frq.py /path/to/input/folder

"""

import argparse
import asyncio
import logging
import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types

# Load .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Configuration (same env vars as quantum-tutor-lit)
USE_VERTEX_AI = os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "true").lower() == "true"
GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID", "third-flare-455923-k2")
VERTEX_AI_LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "global")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
DEFAULT_MODEL = os.getenv("GEMINI_DEFAULT_MODEL", "gemini-2.5-flash-lite")

# Initialize Gemini client
client: genai.Client | None = None

def init_client():
    global client
    if client is None:
        if USE_VERTEX_AI:
            client = genai.Client(
                vertexai=True,
                project=GCP_PROJECT_ID,
                location=VERTEX_AI_LOCATION
            )
            logger.info(f"Vertex AI client initialized (project={GCP_PROJECT_ID}, location={VERTEX_AI_LOCATION})")
        else:
            client = genai.Client(api_key=GEMINI_API_KEY)
            logger.info("Gemini Developer API client initialized")

# AP Chemistry Units Reference
AP_CHEM_UNITS = """
AP Chemistry Units:
- Unit 1: Atomic Structure and Properties
- Unit 2: Molecular and Ionic Compound Structure and Properties
- Unit 3: Intermolecular Forces and Properties
- Unit 4: Chemical Reactions
- Unit 5: Kinetics
- Unit 6: Thermodynamics
- Unit 7: Equilibrium
- Unit 8: Acids and Bases
- Unit 9: Applications of Thermodynamics
"""

ANALYSIS_PROMPT = f"""Analyze this AP Chemistry FRQ page image.

{AP_CHEM_UNITS}

Respond with one of these formats:

If NO question on page (cover page, instructions, blank):
NO_QUESTION

If question(s) found, one line per question part (e.g. 1a, 1b, 2a, etc):
QUESTION: <number/letter> | UNIT: <unit name> | SUBTOPIC: <subtopic>

TIE-BREAKER RULE: If multiple units apply to a question part, use the 'highest unit number required' rule and don't reconsider. One pass only.

Example output:
QUESTION: 1a | UNIT: Unit 6: Integration and Accumulation of Change | SUBTOPIC: Average value of a function
QUESTION: 1b | UNIT: Unit 5: Analytical Applications of Differentiation | SUBTOPIC: Mean Value Theorem"""

YEAR_EXTRACT_PROMPT = """Look at this AP Chemistry exam cover page image.

Extract the year and whether it's Form B.

YEAR: <year>
FORM_B: <yes or no>

Example:
YEAR: 2025
FORM_B: no"""


def get_png_files(folder: Path) -> list[Path]:
    """Returns sorted list of PNG files in a folder."""
    png_files = list(folder.glob("*.png")) + list(folder.glob("*.PNG"))
    return sorted(png_files, key=lambda p: p.name.lower())


async def analyze_image(
    image_path: Path,
    model: str,
    prompt: str = ANALYSIS_PROMPT,
    max_retries: int = 3
) -> str | None:
    """Call Gemini to analyze one image. Returns raw response text or None on failure."""
    try:
        image_data = image_path.read_bytes()
    except Exception as e:
        logger.error(f"Failed to load image {image_path}: {e}")
        return None

    # Build contents with image and prompt
    contents = [
        types.Part.from_bytes(data=image_data, mime_type="image/png"),
        prompt
    ]

    # Configure generation with thinking for accuracy
    # Gemini 3 uses thinking_level, Gemini 2.5 uses thinking_budget
    is_gemini_3 = "gemini-3" in model.lower()

    if is_gemini_3:
        thinking_config = types.ThinkingConfig(
            thinking_level="high",
            include_thoughts=False
        )
    else:
        thinking_config = types.ThinkingConfig(
            thinking_budget=8000
        )

    gen_config = types.GenerateContentConfig(
        max_output_tokens=2048,
        temperature=0.1,
        thinking_config=thinking_config
    )

    for attempt in range(max_retries):
        try:
            response = await client.aio.models.generate_content(
                model=model,
                contents=contents,
                config=gen_config,
            )
            content = response.text or ""
            logger.debug(f"Raw response for {image_path.name}: {content}")
            return content
        except Exception as e:
            logger.warning(f"Error analyzing {image_path.name} (attempt {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(0.5 * (attempt + 1))
            else:
                return None

    return None


def parse_response(response: str) -> list[str]:
    """
    Extract question info from AI response.
    Returns list of formatted question lines, or empty list if no question.
    """
    if not response:
        return []

    response = response.strip()

    # Check for no question
    if "NO_QUESTION" in response.upper():
        return []

    results = []
    seen = set()  # Track seen question numbers to avoid duplicates
    lines = response.split("\n")

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Skip template/placeholder lines
        if "<number" in line.lower() or "<unit" in line.lower() or "<subtopic" in line.lower():
            continue

        # Look for the structured format
        match = re.search(
            r"QUESTION:\s*([^|]+)\s*\|\s*UNIT:\s*([^|]+)\s*\|\s*SUBTOPIC:\s*(.+)",
            line,
            re.IGNORECASE
        )
        if match:
            question_num = match.group(1).strip()
            unit = match.group(2).strip()
            subtopic = match.group(3).strip()

            # Skip if we've already seen this question number
            if question_num.lower() in seen:
                continue
            seen.add(question_num.lower())

            # Format: <question_number_or_letter>, Unit <N>: <Unit Name>, <Subtopic>
            results.append(f"{question_num}, {unit}, {subtopic}")

    return results


def parse_year_response(response: str) -> str:
    """
    Extract year and form info from AI response.
    Returns a string like "2025" or "2019B" (for Form B).
    Returns "Unknown" if parsing fails.
    """
    if not response:
        return "Unknown"

    year = None
    is_form_b = False

    for line in response.split("\n"):
        line = line.strip()

        # Look for year
        year_match = re.search(r"YEAR:\s*(\d{4})", line, re.IGNORECASE)
        if year_match:
            year = year_match.group(1)

        # Look for form B
        form_match = re.search(r"FORM_B:\s*(yes|no)", line, re.IGNORECASE)
        if form_match:
            is_form_b = form_match.group(1).lower() == "yes"

    if year:
        return f"{year}B" if is_form_b else year
    return "Unknown"


async def process_directory(dir_path: Path, model: str) -> list[str]:
    """Process all images in one directory, return list of result lines."""
    png_files = get_png_files(dir_path)

    if not png_files:
        logger.warning(f"No PNG files found in {dir_path}")
        return []

    logger.info(f"Processing {len(png_files)} images in {dir_path.name}")

    # First, extract year/form from the first image
    logger.info(f"  Extracting year/form from {png_files[0].name}...")
    year_response = await analyze_image(png_files[0], model, prompt=YEAR_EXTRACT_PROMPT)
    year_info = parse_year_response(year_response) if year_response else "Unknown"
    logger.info(f"  Detected: {year_info}")

    all_results = []
    seen_questions = set()  # Track seen question numbers across all images

    for i, png_file in enumerate(png_files, 1):
        logger.info(f"  [{i}/{len(png_files)}] Analyzing {png_file.name}...")

        response = await analyze_image(png_file, model)

        if response is None:
            logger.warning(f"  Skipping {png_file.name} (failed to analyze)")
            continue

        questions = parse_response(response)

        if not questions:
            # Log truncated response to help debug parsing issues
            preview = response[:200].replace('\n', ' ') if response else "(empty)"
            logger.info(f"  No question found in {png_file.name}")
            logger.debug(f"  Response preview: {preview}")
        else:
            for q in questions:
                # Extract question number (first part before comma)
                q_num = q.split(",")[0].strip().lower()
                if q_num in seen_questions:
                    logger.debug(f"  Skipping duplicate: {q}")
                    continue
                seen_questions.add(q_num)
                # Prepend year info to each result
                result = f"{year_info}, {q}"
                logger.info(f"  Found: {result}")
                all_results.append(result)

    return all_results


def write_results(dir_path: Path, results: list[str]) -> Path:
    """Write results to a text file in the directory."""
    output_file = dir_path / f"{dir_path.name}.txt"
    with open(output_file, "w") as f:
        for line in results:
            f.write(line + "\n")
    return output_file


async def main_async():
    parser = argparse.ArgumentParser(
        description="Analyze AP Chemistry FRQ images and categorize by unit/subtopic"
    )
    parser.add_argument(
        "input_folder",
        type=Path,
        help="Root folder containing subdirectories with PNG images"
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Gemini model name (default: {DEFAULT_MODEL})"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Initialize Gemini client
    init_client()

    input_folder = args.input_folder.resolve()

    if not input_folder.exists():
        logger.error(f"Input folder does not exist: {input_folder}")
        sys.exit(1)

    if not input_folder.is_dir():
        logger.error(f"Input path is not a directory: {input_folder}")
        sys.exit(1)

    # Find all subdirectories
    subdirs = [d for d in input_folder.iterdir() if d.is_dir()]

    if not subdirs:
        # Maybe the input folder itself contains images
        logger.info("No subdirectories found, checking input folder for images...")
        subdirs = [input_folder]

    logger.info(f"Found {len(subdirs)} directories to process")

    for subdir in sorted(subdirs):
        logger.info(f"\nProcessing directory: {subdir.name}")
        results = await process_directory(subdir, args.model)

        if results:
            output_file = write_results(subdir, results)
            logger.info(f"Wrote {len(results)} questions to {output_file}")
        else:
            logger.warning(f"No questions found in {subdir.name}")

    logger.info("\nDone!")


def main():
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
