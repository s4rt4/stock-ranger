# PoC Results — SVG → EPS 10 CMYK Pipeline

**Status: PROVEN ✓** (2026-06-24)

De-risked the #1 project risk: generating CMYK EPS from SVG vectors without
writing a custom PostScript generator.

## Validated Pipeline

```bash
# Step 1: SVG -> PDF (Inkscape), text converted to outlines
inkscape --export-type=pdf --export-text-to-path \
         --export-filename=work.pdf input.svg

# Step 2: PDF -> CMYK EPS (Ghostscript does the RGB->CMYK vector conversion)
gs -dNOPAUSE -dBATCH -dSAFER \
   -sDEVICE=eps2write \
   -dColorConversionStrategy=/CMYK \
   -dProcessColorModel=/DeviceCMYK \
   -sOutputFile=output.eps work.pdf

# Step 3: Validate (renders cleanly = valid PostScript)
gs -dNOPAUSE -dBATCH -dSAFER -sDEVICE=nullpage output.eps
```

## Key Findings

- **Color conversion is correct.** #ff0000 → `0 0.996 1 0 k`, etc. Body is 100%
  CMYK operators (`k`/`K`); only leftover `rg` strings are unused prolog proc
  definitions.
- **Visual integrity preserved** — rendered output matches source SVG.
- **Text MUST use `--export-text-to-path`** — otherwise EPS carries live font
  refs (Shutterstock rejects live fonts; also caused gs font-substitution warnings).
- **Original plan approach NOT needed:** no manual PostScript body generation, no
  `colour-science`, no hand-injected `%%Creator: Adobe Illustrator` DSC header.
  Ghostscript does the heavy lifting cleanly via `eps2write`.

## SWOP v2 Injection — PROVEN ✓ (follow-up #1 done)

Real "U.S. Web Coated (SWOP) v2" profile injection works:

```bash
gs --permit-file-read="$SWOP" \           # REQUIRED: gs 10.x -dSAFER blocks
   -dNOPAUSE -dBATCH -dSAFER \            # profile load otherwise (silent fallback!)
   -sDEVICE=eps2write -dColorConversionStrategy=/CMYK -dProcessColorModel=/DeviceCMYK \
   -sOutputICCProfile="$SWOP" -sOutputFile=out.eps work.pdf
```

- **GOTCHA:** without `--permit-file-read`, gs 10.x `-dSAFER` blocks the profile
  ("Permission denied") and silently falls back to default. MUST permit the path.
- Proven by profile-swap test (same SVG, 3 profiles → 3 distinct CMYK results):
  red #ff0000 = `0 0.996 1 0` (SWOP) vs `0 1 1 0` (Newspaper).
- Ghostscript's bundled `default_cmyk.icc` ≈ real SWOP v2 (both SWOP-family,
  near-identical output) — viable license-clean default.

## ⚠️ LICENSING CONSTRAINT (changes the plan)

Adobe Color Profile EULA forbids bundling `USWebCoatedSWOP.icc` *inside the app*:
> distribute only (a) embedded within digital image files, (b) standalone.
> NOT when "incorporated into or bundled with any application software."

- ❌ Cannot ship `profiles/USWebCoatedSWOP.icc` in the app (plan's original design).
- ✅ CAN embed the profile into OUTPUT files (EPS/JPG) — exactly our use case (a).
- ✅ Ghostscript `default_cmyk.icc` is redistributable (AGPL) and SWOP-equivalent.
- Decision pending: default to gs profile, let user supply own Adobe SWOP optionally.
2. **Output LanguageLevel is 2.** Plan wanted PS Level 3. Level 2 EPS is
   universally accepted; likely a non-issue, but note it.
3. **DSC header says "GPL Ghostscript", not Illustrator.** Unproven assumption
   in original plan that Shutterstock sniffs the Creator header. Can rewrite via
   ExifTool/string-replace if a real submission proves it necessary. Cannot fully
   verify acceptance without an actual Shutterstock submission.

## Environment (verified available)

Python 3.14.5 · Inkscape 1.4.4 · Ghostscript 10.05.1 · Pillow 11.3.0 (ImageCms) ·
lxml 6.1.1 · PyQt6 6.11.0 · **ExifTool: MISSING** (needed for metadata step only).
