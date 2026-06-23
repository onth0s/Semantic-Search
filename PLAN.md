# Wildcard Query Matching and Configurable Category Parsing

Implement category keyword parsing in the Heuristic Parser layer (`src/heuristics.py`) with exact, fuzzy, and phonetic tag matching, support wildcard patterns in candidate extension filters, and implement glob/wildcard query matching across the H1-H6 handlers, with semantic translation for H7/H8.

## User Review Required
> [!NOTE]
> - Query strings containing `*` or `?` (e.g. `"*.blend*"`) will be evaluated as glob patterns directly in H1 and H2 handlers using Python's `fnmatch`.
> - If a wildcard query falls back to semantic embedding (H7) or LLM rewrite (H8), we will translate it into a descriptive query phrase (e.g. `"*.blend*"` -> `"a file whose name ends with .blend followed by any characters"`).
> - Category keyword matching will analyze query tokens and match them against configured tag keywords using exact, fuzzy, and phonetic matching.
> - Candidate extension filtering will support glob-style wildcards using `fnmatch`.

## Proposed Changes

### Handlers Layer (Wildcard Query Support)

#### [MODIFY] [h1_exact.py](file:///c:/Users/Leonardo/001/00__DEV/Semantic%20Search/src/handlers/h1_exact.py)
- If the query contains `*` or `?`, perform case-sensitive glob matching using `fnmatch.fnmatchcase` against candidate names, stems, and path suffixes.

#### [MODIFY] [h2_case_insensitive.py](file:///c:/Users/Leonardo/001/00__DEV/Semantic%20Search/src/handlers/h2_case_insensitive.py)
- If the query contains `*` or `?`, perform case-insensitive glob matching using `fnmatch.fnmatch` against candidate names, stems, and path suffixes.

#### [MODIFY] [h7_embedding.py](file:///c:/Users/Leonardo/001/00__DEV/Semantic%20Search/src/handlers/h7_embedding.py)
- Translate queries containing wildcards before encoding them. E.g. replace `*.ext*` with `"a file whose name ends with .ext and any suffix"`.

#### [MODIFY] [h8_llm.py](file:///c:/Users/Leonardo/001/00__DEV/Semantic%20Search/src/handlers/h8_llm.py)
- Translate wildcard expressions in the system prompt or query pre-processing before invoking the chat model.

### Heuristic Parser Layer

#### [MODIFY] [heuristics.py](file:///c:/Users/Leonardo/001/00__DEV/Semantic%20Search/src/heuristics.py)
- Support parsing and stripping fuzzy/phonetic/exact category keyword matches.
- Add a helper `translate_wildcards(query: str) -> str` that expands glob queries into descriptions for semantic matching:
  - E.g., replacing `*.blend*` with `"a file ending in .blend and any suffix"`.

### Core Search Engine & Filtering

#### [MODIFY] [engine.py](file:///c:/Users/Leonardo/001/00__DEV/Semantic%20Search/src/engine.py)
- Filter candidate lists based on directory/file intent and wildcard category extensions using `fnmatch`.

### Configuration Updates

#### [MODIFY] [config.yaml](file:///c:/Users/Leonardo/001/00__DEV/Semantic%20Search/config.yaml)
Add the default categories configuration section:
```yaml
heuristics:
  categories:
    image:
      keywords: [pic, pics, picture, pictures, photo, photos, image, images, img, imgs, png, pngs, jpg, jpgs, jpeg, jpegs, webp, gif, gifs, bmp, bmps]
      extensions: [png, jpg, jpeg, gif, bmp, webp, tiff, ico, svg]
    document:
      keywords: [doc, docs, document, documents, pdf, pdfs, text, txt, txts, csv, csvs, md, markdown, markdowns]
      extensions: [pdf, docx, doc, txt, rtf, odt, xls, xlsx, ppt, pptx, csv, md, markdown]
    code:
      keywords: [code, script, scripts, source, py, python, js, javascript, ts, typescript, html, css, json, yaml, yml, toml]
      extensions: [py, js, ts, html, css, json, yaml, yml, toml, sh, bat, ps1, rs, go, cpp, c, h]
    audio:
      keywords: [audio, audios, sound, sounds, music, mp3, mp3s, wav, wavs, flac, flacs]
      extensions: [mp3, wav, flac, m4a, ogg, aac]
    video:
      keywords: [video, videos, vid, vids, movie, movies, film, films, mp4, mp4s, mkv, mkvs, avi, avis, mov, movs]
      extensions: [mp4, mkv, avi, mov, wmv, flv, webm]
    archive:
      keywords: [archive, archives, compressed, compression, zip, zips, rar, rars, 7z, 7zs, tar, tars]
      extensions: [zip, rar, tar, gz, 7z, tgz]
    backup_blend:
      keywords: [blend1 files, backup blends]
      extensions: [blend*]
```

### Tests

#### [MODIFY] [test_handlers.py](file:///c:/Users/Leonardo/001/00__DEV/Semantic%20Search/tests/test_handlers.py)
- Add tests verifying H1 and H2 direct wildcard/glob query matching.
- Add tests verifying the wildcard translation logic.

## Verification Plan

### Automated Tests
- Run `.venv\Scripts\python.exe -m pytest` to check all tests pass.
