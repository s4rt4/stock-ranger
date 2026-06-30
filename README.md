# Stock Ranger

Desktop app Linux untuk contributor microstock. Mengubah file SVG dari Inkscape
menjadi paket **siap upload**: EPS 10 + JPG preview, lengkap dengan metadata
XMP/IPTC ter-embed — mengisi gap tooling vektor→microstock di Linux.

![Stock Ranger UI](poc/ui_final.png)

## Fitur

- **Konversi SVG → EPS 10** dengan dua mode warna: **RGB** (default microstock)
  atau **CMYK** (cetak), dipilih per batch.
- **Resolusi terjaga** — output dipastikan memenuhi syarat minimum megapixel
  microstock, dihitung dari bounding box artwork.
- **JPG preview** ter-rasterize dengan aturan ukuran/kualitas yang dapat diatur.
- **Metadata XMP/IPTC** (judul, deskripsi, keyword) di-embed ke EPS *dan* JPG.
- **Multi-target preset** — satu batch sekaligus di-export ke beberapa microstock
  dengan paket berbeda (ZIP berpasangan / file lepas / EPS-only) per target.
- **Batch & UI** — folder tree, grid thumbnail, inspector metadata, drag & drop,
  template metadata (save/load), import JPG manual, log panel.

## Pipeline

```
SVG (Inkscape)
  → validasi
  → EPS 10 (RGB atau CMYK)   (Inkscape → PDF → Ghostscript)
  → JPG preview              (Inkscape rasterize + Pillow)
  → embed metadata XMP/IPTC  (ExifTool, ke EPS & JPG)
  → ZIP / file lepas siap upload
```

Konversi warna vektor ke CMYK dilakukan **Ghostscript** di level device; konversi
raster pakai **LittleCMS** (`PIL.ImageCms`).

## Dependencies

**Eksternal** (CLI):

```bash
# Fedora
sudo dnf install inkscape ghostscript perl-Image-ExifTool
# Debian/Ubuntu
sudo apt install inkscape ghostscript libimage-exiftool-perl
```

**Python:**

```bash
pip install -r requirements.txt
```

## Menjalankan

```bash
python3 main.py                                   # GUI

# atau via CLI:
python3 -m stock_ranger.core.pipeline input.svg -o ./out \
    --title "Judul" --desc "Deskripsi" --keywords "a,b,c"
```

## ICC Profile (mode CMYK)

Untuk mode CMYK, Stock Ranger memakai profil ICC CMYK standar industri yang
**diunduh saat runtime** ke `~/.local/share/stock-ranger/profiles/`. Jika
dilewati, app memakai `default_cmyk.icc` bawaan Ghostscript yang setara dan boleh
didistribusi. Mode RGB tidak memerlukan profil ICC.

## Arsitektur

```
stock_ranger/
├── core/      # pipeline headless (testable, tanpa Qt)
│   ├── pipeline.py        svg_parser.py      eps_generator.py
│   ├── jpg_generator.py   metadata_writer.py zip_builder.py
│   ├── file_pairer.py     profile_manager.py preview.py
│   ├── templates.py       deps.py            models.py  util.py
└── ui/        # PyQt6 — dark theme, folder tree | grid | inspector
    ├── main_window.py  sidebar.py  panels.py  inspector.py
    ├── worker.py  preview_worker.py  theme.py  icons.py
    ├── flowlayout.py   imageconv.py
```

## Status

- **Fase 1 (MVP)** — pipeline inti + UI ✅ selesai & teruji end-to-end.
- **Fase 2 (Batch & Metadata UX)** — ✅ selesai: drag & drop, live preview
  RGB/CMYK (soft-proof LittleCMS) + gamut warning, template metadata, manual JPG
  import + pairing, multi-target preset, log panel.
- **Fase 3 (Polish & Packaging)** — settings persistence, packaging
  (.deb / RPM / Windows) — menyusul.

## Lisensi

Kode: MIT.
</content>
</invoke>
