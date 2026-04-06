#!/usr/bin/env bash
# build_arxiv_zip.sh — Compile EL-DRUIN paper and package for arXiv upload.
#
# Usage (from any directory):
#   bash paper/latex/build_arxiv_zip.sh
#
# What it does:
#   1. Cleans LaTeX auxiliary files from a previous run.
#   2. Runs pdflatex twice (+ bibtex if a .bib file exists) to resolve
#      cross-references and produce a clean main.pdf.
#   3. Packages main.tex, figures/ (if present), and *.bib/*.bbl (if present)
#      into eldruin_arxiv.zip ready for arXiv upload.
#   4. Prints a summary of the zip contents.
#
# Requirements: pdflatex (MacTeX / TeX Live), zip, unzip (all standard on macOS).

set -euo pipefail

# Resolve the directory containing this script so it works regardless of $CWD.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

ZIP_NAME="eldruin_arxiv.zip"
TEX_MAIN="main.tex"

# Print a helpful hint if pdflatex (or any step) fails.
_on_error() {
    echo ""
    echo "ERROR: build failed. Check the LaTeX log for details:"
    echo "  less ${SCRIPT_DIR}/${TEX_MAIN%.tex}.log"
    echo "Common causes: missing package, undefined reference, missing figure file."
}
trap '_on_error' ERR

# ---------------------------------------------------------------------------
# 1. Clean auxiliary files from previous runs
# ---------------------------------------------------------------------------
echo "==> Cleaning auxiliary files..."
rm -f ./*.aux ./*.log ./*.out ./*.toc ./*.lof ./*.lot ./*.bbl ./*.blg \
      ./*.fls ./*.fdb_latexmk ./*.synctex.gz

# ---------------------------------------------------------------------------
# 2. Compile: pdflatex → bibtex (if .bib exists) → pdflatex × 2
# ---------------------------------------------------------------------------
echo "==> Running pdflatex (pass 1)..."
pdflatex -interaction=nonstopmode "$TEX_MAIN"

if ls ./*.bib 1>/dev/null 2>&1; then
    echo "==> Running bibtex..."
    bibtex "${TEX_MAIN%.tex}"
    echo "==> Running pdflatex (pass 2 — after bibtex)..."
    pdflatex -interaction=nonstopmode "$TEX_MAIN"
fi

echo "==> Running pdflatex (final pass)..."
pdflatex -interaction=nonstopmode "$TEX_MAIN"

echo "==> main.pdf built successfully."

# ---------------------------------------------------------------------------
# 3. Package for arXiv
# ---------------------------------------------------------------------------
echo "==> Creating ${ZIP_NAME}..."
rm -f "$ZIP_NAME"

# Always include the main source file.
zip "$ZIP_NAME" "$TEX_MAIN"

# Include figures/ if the directory exists and contains at least one file.
if [ -d "figures" ] && [ -n "$(ls -A figures 2>/dev/null)" ]; then
    echo "    Including figures/ directory..."
    zip -r "$ZIP_NAME" figures/
fi

# Include .bib files if present.
for bib_file in ./*.bib; do
    [ -f "$bib_file" ] || continue
    echo "    Including ${bib_file}..."
    zip "$ZIP_NAME" "$bib_file"
done

# Include the compiled .bbl file if present (needed when arXiv cannot run bibtex).
for bbl_file in ./*.bbl; do
    [ -f "$bbl_file" ] || continue
    echo "    Including ${bbl_file}..."
    zip "$ZIP_NAME" "$bbl_file"
done

# ---------------------------------------------------------------------------
# 4. Summary
# ---------------------------------------------------------------------------
echo ""
echo "==> ${ZIP_NAME} contents:"
unzip -l "$ZIP_NAME"
echo ""
echo "Done. Upload ${SCRIPT_DIR}/${ZIP_NAME} to arXiv."
