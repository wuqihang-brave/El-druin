# arXiv Submission Guide — EL-DRUIN Paper

This directory contains the LaTeX source for the EL-DRUIN paper.

## Files

| File | Purpose |
|---|---|
| `main.tex` | Full paper source |
| `figures/` | Figure images referenced by `main.tex` |
| `*.bib` / `main.bbl` | Bibliography (BibTeX source or pre-compiled) |
| `build_arxiv_zip.sh` | Helper script: compile PDF + create submission zip |

> **Do not commit** `main.pdf` or `eldruin_arxiv.zip` — these are build artifacts and are listed in `.gitignore`.

---

## Step 1 — Build `main.pdf` locally

Requirements: a working TeX distribution (e.g. [MacTeX](https://www.tug.org/mactex/) on macOS or [TeX Live](https://tug.org/texlive/) on Linux).

```bash
cd paper/latex
pdflatex main.tex
bibtex main        # only if you have a .bib file
pdflatex main.tex
pdflatex main.tex
```

Or use the helper script (recommended — it does all of this automatically):

```bash
bash paper/latex/build_arxiv_zip.sh
```

---

## Step 2 — Create `eldruin_arxiv.zip`

The helper script builds the zip automatically. To build manually:

```bash
cd paper/latex
zip eldruin_arxiv.zip main.tex
# Add figures if the figures/ directory exists and is non-empty:
[ -d figures ] && zip -r eldruin_arxiv.zip figures/
# Add bibliography files if present:
for f in *.bib *.bbl; do [ -f "$f" ] && zip eldruin_arxiv.zip "$f"; done
```

arXiv requires the zip to include **all source files** needed to compile the paper:
- `main.tex` (required)
- `figures/` directory with all referenced images (if any)
- `*.bbl` **or** `*.bib` — include the `.bbl` file if you ran BibTeX; otherwise include the `.bib` source

---

## Step 3 — Upload to arXiv

1. Log in to [arxiv.org](https://arxiv.org) and start a new submission.
2. Choose **Upload a File** and select `eldruin_arxiv.zip`.
3. arXiv will auto-detect the LaTeX source and compile it server-side. If compilation fails, check the arXiv log and fix any missing packages or files.
4. Verify the generated PDF on the arXiv preview page before submitting.

### Recommended subject classification

- **Primary:** `cs.AI`
- **Cross-list (optional):** `cs.LO` (logic in CS — appropriate for the semigroup / ontology formalism)

---

## Notes

- arXiv compiles with `pdflatex` by default. If you use `xelatex` or `lualatex`, add a `00README.XXX` file specifying the engine (see [arXiv TeX help](https://info.arxiv.org/help/submit_tex.html)).
- Figures must be in a format supported by `pdflatex`: **PDF**, **PNG**, or **JPEG**. Do not use EPS without conversion.
- If you have a `.bib` file, you can include it instead of (or alongside) the compiled `.bbl`; arXiv runs BibTeX automatically.
- The paper title, abstract, and metadata entered on arXiv must match the content of `main.tex` exactly.
