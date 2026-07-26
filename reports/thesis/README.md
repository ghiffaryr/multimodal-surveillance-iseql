# Thesis Template

This repository is a cleaned LaTeX thesis template based on `MastersDoctoralThesis.cls`. The project keeps the original folder layout and replaces the previous thesis-specific content with reusable placeholders.

## Start Here

1. Update the metadata in `Pages/preamble.tex`.
2. Adjust the title page and optional front matter in `main.tex`.
3. Replace the placeholder text in `Chapters/*.tex`.
4. Add your sources to `references.bib`.
5. Put your figures in `Figures/`.

## Build

With `latexmk`:

```bash
latexmk -pdf -interaction=nonstopmode main.tex
```

Manual build:

```bash
pdflatex main.tex
bibtex main
pdflatex main.tex
pdflatex main.tex
```

If the template does not contain any citations yet, you can skip the `bibtex main` step until you start citing entries from `references.bib`.

## Optional Sections

- The title page uses `\titlepagelogo` together with the programme partner logos configured in `Pages/preamble.tex`.
- The programme-specific `edisspage` block in `main.tex` reuses the same logo assets and is commented out by default.
- Appendices are present but commented out by default.
- Update or remove the abbreviations page in `Pages/abbreviations.tex` if you do not need it.

## Repository Cleanup

Generated LaTeX build artifacts and `main.pdf` are ignored by `.gitignore`.
