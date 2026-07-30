# Sempath Queries for Review

The following table presents 24 exhaustive test queries designed against the directory tree layout in [TREE_EXAMPLE.txt](file:///c:/Users/Leonardo/001/00__DEV/Semantic%20Search/misc/TREE_EXAMPLE.txt). 

These queries cover wildcard/glob syntax, category keyword extraction (exact, fuzzy, phonetic), temporal/size sorting heuristics, directory/file intent constraints, and combinations thereof.

| ID | Query String | Targeted Features / Heuristics | Expected Match (Relative to root) | Resolution Mechanism & Handler Details |
|---|---|---|---|---|
| **1** | `*.blend*` | Case-Sensitive Glob Matching | `Bowsette/Untitled.blend`<br>`Bowsette/Untitled.blend1`<br>`Bowsette/Untitled.blend2` | Evaluates as a wildcard/glob pattern using `fnmatchcase` in **H1** (Exact). Matches files of any suffix starting with `.blend`. |
| **2** | `*.TXT` | Case-Insensitive Glob Matching | `TREE_EXAMPLE.txt`<br>`High Contrast Test/PROMPT.txt` | Matches filenames ending with case-insensitive `.txt` under **H2** (Case-Insensitive Glob). |
| **3** | `*misato*` | Basename Glob Directory Match | `3D-to-reGEN-to-VID/Katsuragi Misato/` | Evaluates wildcard match on the directory name itself in **H2**. |
| **4** | `*ackerman*` | Stem Wildcard Matching | `3D-to-reGEN-to-VID/Mikasa Ackerman/` | Matches directory stem case-insensitively using glob syntax under **H2**. |
| **5** | `*Natalie_Portman/*.kra` | Nested Directory/File Glob | `CelebDeGEN/001__Natalie_Portman/011-SharpenAI-Softness-gp-standard v2-2048w-gp-redefine-2048w.kra` | Resolves multi-segment wildcard query by comparing candidate path suffixes against pattern using `fnmatch`. |
| **6** | `annie photo` | Exact Category Keyword (`photo` -> image) | `3D-to-reGEN-to-VID/Annie Leonhart/000.png` | `extract_heuristics` parses category keyword `photo`, stripping it and setting the target extensions list to images (`.png`, `.jpg`, etc.). Query `annie` matches under **H1** / **H2**. |
| **7** | `makima pic` | Exact Category Keyword (`pic` -> image) | `Makima Deepthroat/PNGs/00.png` | `extract_heuristics` parses `pic` to restrict search to image extensions. Search engine filters candidate list, matching `makima` on the directory path. |
| **8** | `bowsette backup_blend` | Category Keyword (`backup_blend` -> `.blend*`) | `Bowsette/Untitled.blend1` | Custom category `backup_blend` (keyword `backup`) filters candidate extensions to `.blend*` wildcards. Matches Krita/Blender backups. |
| **9** | `impecable video` | Exact Category Keyword (`video` -> video extensions) | `About Feet/Impecable Soles/video-gen_4k-upscale.mp4` | Extracts `video` -> filters by `.mp4`, `.mov`, `.avi`, etc. Clean query `impecable` matches the parent directory stem. |
| **10** | `high contrast backup` | Category Keyword (`backup` -> `.blend*`) | `High Contrast Test/VAR/charcoal_01.blend1` | Extracts custom category `backup` -> extension `.blend*`. Clean query `high contrast` matches the directory name. |
| **11** | `picts on Desktop` | Fuzzy Category Keyword (`picts` -> `pics` -> image) | `.png` / `.jpg` / `.webp` files in the tree | `picts` matches category keyword `pics` (ratio: 88.9) fuzzy-matching on category tags. Filters candidates to images and cleans query to `on Desktop`. |
| **12** | `phothos of DVa` | Phonetic Category Keyword (`phothos` -> `photos` -> image) | `DVa Raised Sole/040.jpg` | `phothos` phonetically matches `photos` (Metaphone: `FTS`). Filters candidates to image extensions. Clean query `of DVa` matches stem. |
| **13** | `piks of Uraraka` | Phonetic Category Keyword (`piks` -> `pics` -> image) | `Uraraka Gape Stable Diffusion Render/000.png` | `piks` phonetically matches `pics` (Metaphone: `PKS`). Filters candidates to image extensions. Clean query `of Uraraka` matches directory. |
| **14** | `latest *.png` | `latest` sorting heuristic + Wildcard | Newest `.png` file in the tree (e.g., in `0SC to 3D to Angle Swap`) | Heuristics parser sets `latest=True`. Search filters candidates using `*.png` glob and sorts by file modification time descending. |
| **15** | `largest *.mp4` | `largest` sorting heuristic + Wildcard | `3D-to-reGEN-to-VID/var_01/var/this is fucking insane.mp4` | Heuristics parser sets `largest=True`. Search filters candidates using `*.mp4` glob and sorts by file size descending. |
| **16** | `folder *feet*` | Directory Intent + Wildcard | `About Feet/` | Heuristic sets `directory_only=True`. Search restricts to directory paths and filters by `*feet*` wildcard pattern. |
| **17** | `str*ggling` | Destructured Fuzzy Wildcard | `Struggling While Squatting/` | Wildcard is stripped (`strggling`) and fuzzy-matched against candidate stems under **H4** (Fuzzy Match). |
| **18** | `fub*ki pur` | Destructured Token / Wildcard Match | `Fubuki Green Thong SDA (Stable Diffusion Assisted)/Fubuki_refs.pur` | Wildcard is stripped and token-normalized under **H3** / **H4**. Matches Krita/PureRef file. |
| **19** | `shackles v1*` | Wildcard Stem Match | `Mikasa In Shackles Arching/v2/Mikasa in Shackles v1.glb` | Wildcard stem matching case-insensitively matches the `.glb` file under **H2**. |
| **20** | `*soles* *.mp4` | Multi-Token Wildcard Match | `About Feet/Impecable Soles/video-gen_4k-upscale.mp4` | Evaluates multi-token wildcards against candidate paths to find paths matching both components. |
| **21** | `*Natalie*/*.png` | Multi-Segment Wildcard | `CelebDeGEN/001__Natalie_Portman/010.png` | Glob matches path components, requiring directory part to contain `Natalie` and file to end in `.png`. |
| **22** | `delete-me*.kra` | Stem Wildcard Match (with hyphens) | `AI Latent Upscale Pipeline/process/delete-me-768x576-gp-recover-768w_lighter_darks.png.kra` | Stem match with hyphenated wildcard prefix and `.kra` extension. |
| **23** | `gceu4l*.png` | Suffix/Stem Wildcard Match | `3D-to-reGEN-to-VID/var_01/nb_gens/Gemini_Generated_Image_gceu4lgceu4lgceu.png` | Matches the complex randomly generated filenames containing `gceu4l` and ending in `.png`. |
| **24** | `latest video under var_01` | `latest` sorting + Category + Path constraints | `3D-to-reGEN-to-VID/var_01/999.mp4` (or other new video under `var_01`) | Extracts `latest=True` and filters by `video` extensions (e.g. `.mp4`, `.mov`). Matches files containing path token `var_01` and returns the newest one. |
| **25** | `feet` | Short token match with multiple candidates | `About Feet/` (directory)<br>`About Feet/Best Looking Sole/best_looking_foot_sole__feet.png` (file) | Tests ranking, confidence scoring, and grouping when a query matches multiple directories and files containing `feet` or `foot`. |

***

### Notes for Review
- **Exact & Fuzzy Category keyword matching**: Custom keyword mappings (like `backup` -> `backup_blend` category) and misspelled categories (like `picts`, `phothos`, `piks`) will be stripped out and converted to extension filters.
- **Semantic Translations**: For handlers **H7** (Embedding) and **H8** (LLM), queries like `*.blend*` will be programmatically translated to `"a file whose name ends with .blend followed by any characters"` to enable high-quality semantic similarity checks.
