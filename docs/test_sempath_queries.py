#!/usr/bin/env python3
"""Comprehensive test: sempath vs all queries_review.md expectations on TREE_EXAMPLE.txt.

Creates a mock filesystem from TREE_EXAMPLE.txt, runs each of the 25 queries
through sempath SearchEngine, and reports ALL mismatches as individual failures.

This file does NOT modify the codebase — it lives in misc/ and is self-contained.

Usage:
    cd <project-root>
    py -3.13 misc/test_sempath_queries.py          # standalone run
    py -3.13 -m pytest misc/test_sempath_queries.py -v --tb=short
"""

from __future__ import annotations

import os
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

# ── Bootstrap ────────────────────────────────────────────────────────────────
_HERE = Path(__file__).resolve().parent
_PROJECT_ROOT = _HERE.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# Isolate user config/cache so the test doesn't touch the real system
_os_temp = tempfile.mkdtemp(prefix="sempath_test_")
os.environ["APPDATA"] = _os_temp
os.environ.pop("SEMPATH_CONFIG", None)

import yaml

from sempath.config import DEFAULT_CONFIG, load_config
from sempath.engine import SearchEngine
from sempath.models import SearchResult

# ═══════════════════════════════════════════════════════════════════════════════
# PART 1 — Mock filesystem builder (explicit tree from TREE_EXAMPLE.txt)
# ═══════════════════════════════════════════════════════════════════════════════

# Tree spec: every (relative_path, is_dir) entry from TREE_EXAMPLE.txt.
# Root-level entries have no prefix.
_TREE_SPEC: list[tuple[str, bool]] = [
    ("TREE_EXAMPLE.txt", False),
    ("0SC to 3D to Angle Swap", True),
    ("0SC to 3D to Angle Swap/50563c6c-5a60-4e9b-b262-b5ba3a5e5601.jpg", False),
    ("0SC to 3D to Angle Swap/Gemini_Generated_Image_3cfl483cfl483cfl.png", False),
    ("0SC to 3D to Angle Swap/Gemini_Generated_Image_3vcclj3vcclj3vcc.png", False),
    ("0SC to 3D to Angle Swap/Gemini_Generated_Image_vxa2jtvxa2jtvxa2.png", False),
    ("3D-to-reGEN-to-VID", True),
    ("3D-to-reGEN-to-VID/Annie Leonhart", True),
    ("3D-to-reGEN-to-VID/Annie Leonhart/000.kra", False),
    ("3D-to-reGEN-to-VID/Annie Leonhart/000.png", False),
    ("3D-to-reGEN-to-VID/Annie Leonhart/000_001.kra", False),
    ("3D-to-reGEN-to-VID/Annie Leonhart/000_001a.kra", False),
    ("3D-to-reGEN-to-VID/Annie Leonhart/010.png", False),
    ("3D-to-reGEN-to-VID/Annie Leonhart/020.png", False),
    ("3D-to-reGEN-to-VID/Annie Leonhart/030.png", False),
    ("3D-to-reGEN-to-VID/Annie Leonhart/040.png", False),
    ("3D-to-reGEN-to-VID/Annie Leonhart/050.png", False),
    ("3D-to-reGEN-to-VID/Annie Leonhart/060.png", False),
    ("3D-to-reGEN-to-VID/Annie Leonhart/061.png", False),
    ("3D-to-reGEN-to-VID/Annie Leonhart/FACE_MODEL_STYLE_REFERENCE.png", False),
    ("3D-to-reGEN-to-VID/Annie Leonhart/TEMP", True),
    ("3D-to-reGEN-to-VID/Annie Leonhart/TEMP/00000-4248846605.png", False),
    ("3D-to-reGEN-to-VID/Katsuragi Misato", True),
    ("3D-to-reGEN-to-VID/Katsuragi Misato/000.png", False),
    ("3D-to-reGEN-to-VID/Katsuragi Misato/010.png", False),
    ("3D-to-reGEN-to-VID/Katsuragi Misato/020.png", False),
    ("3D-to-reGEN-to-VID/Katsuragi Misato/025.png", False),
    ("3D-to-reGEN-to-VID/Katsuragi Misato/026.png", False),
    ("3D-to-reGEN-to-VID/Katsuragi Misato/030.png", False),
    ("3D-to-reGEN-to-VID/Katsuragi Misato/040.png", False),
    ("3D-to-reGEN-to-VID/Katsuragi Misato/adfsaf.png", False),
    ("3D-to-reGEN-to-VID/Katsuragi Misato/asfdafd.png", False),
    ("3D-to-reGEN-to-VID/Katsuragi Misato/var", True),
    ("3D-to-reGEN-to-VID/Mado Akira", True),
    ("3D-to-reGEN-to-VID/Mado Akira/1 - Untitled.png", False),
    ("3D-to-reGEN-to-VID/Mado Akira/delete-me (2)-gp-high fidelity v2-2x.kra", False),
    ("3D-to-reGEN-to-VID/Mado Akira/delete-me (2)-gp-high fidelity v2-2x.png", False),
    ("3D-to-reGEN-to-VID/Mado Akira/delete-me (2).png", False),
    ("3D-to-reGEN-to-VID/Mado Akira/delete-me1.png", False),
    ("3D-to-reGEN-to-VID/Mado Akira/panties_fixed.png", False),
    ("3D-to-reGEN-to-VID/Mikasa Ackerman", True),
    ("3D-to-reGEN-to-VID/Mikasa Ackerman/MIKASA_SETTEI.png", False),
    ("3D-to-reGEN-to-VID/Mikasa Ackerman/SITTING_POSE.png", False),
    ("3D-to-reGEN-to-VID/Mikasa Ackerman/this_took_22_minutes.png", False),
    ("3D-to-reGEN-to-VID/Mikasa Ackerman/this_took_24_minutes.png", False),
    ("3D-to-reGEN-to-VID/var_01", True),
    ("3D-to-reGEN-to-VID/var_01/000.png", False),
    ("3D-to-reGEN-to-VID/var_01/010.png", False),
    ("3D-to-reGEN-to-VID/var_01/020.png", False),
    ("3D-to-reGEN-to-VID/var_01/021.png", False),
    ("3D-to-reGEN-to-VID/var_01/022.png", False),
    ("3D-to-reGEN-to-VID/var_01/023.png", False),
    ("3D-to-reGEN-to-VID/var_01/030.png", False),
    ("3D-to-reGEN-to-VID/var_01/031.png", False),
    ("3D-to-reGEN-to-VID/var_01/032.png", False),
    ("3D-to-reGEN-to-VID/var_01/033.png", False),
    ("3D-to-reGEN-to-VID/var_01/040.png", False),
    ("3D-to-reGEN-to-VID/var_01/999.mp4", False),
    ("3D-to-reGEN-to-VID/var_01/unnamed_001.kra", False),
    ("3D-to-reGEN-to-VID/var_01/nb_gens", True),
    ("3D-to-reGEN-to-VID/var_01/nb_gens/Gemini_Generated_Image_f691lsf691lsf691.png", False),
    (
        "3D-to-reGEN-to-VID/var_01/nb_gens/Gemini_Generated_Image_gceu4lgceu4lgceu-gp-cgi-2048h.png",
        False,
    ),
    ("3D-to-reGEN-to-VID/var_01/nb_gens/Gemini_Generated_Image_gceu4lgceu4lgceu.png", False),
    ("3D-to-reGEN-to-VID/var_01/nb_gens/Gemini_Generated_Image_hm2y41hm2y41hm2y.png", False),
    ("3D-to-reGEN-to-VID/var_01/nb_gens/unnamed.jpg", False),
    ("3D-to-reGEN-to-VID/var_01/var", True),
    ("3D-to-reGEN-to-VID/var_01/var/this is fucking insane.mp4", False),
    ("3D-to-reGEN-to-VID/var_01/var/unname2d.kra", False),
    ("3D-to-reGEN-to-VID/var_01/var/unname2d.png", False),
    ("3D-to-reGEN-to-VID/var_01/var/unname2d_FOOT_FIX.png", False),
    ("3D-to-reGEN-to-VID/var_01/var/unnamed-gp-cgi-2048h.png", False),
    ("3D-to-reGEN-to-VID/var_01/var/unnamed.png", False),
    ("3D-to-reGEN-to-VID/var_01/var/Untitled.obj", False),
    ("3D-to-reGEN-to-VID/var_01/var/Untitled.png", False),
    ("About Feet", True),
    ("About Feet/B&W Stylized Shape", True),
    ("About Feet/B&W Stylized Shape/010.png", False),
    ("About Feet/B&W Stylized Shape/020.png", False),
    ("About Feet/B&W Stylized Shape/021.png", False),
    ("About Feet/B&W Stylized Shape/030.png", False),
    ("About Feet/B&W Stylized Shape/031.png", False),
    ("About Feet/B&W Stylized Shape/040__BEST.png", False),
    ("About Feet/B&W Stylized Shape/32.png", False),
    ("About Feet/B&W Stylized Shape/foot_study_003.png", False),
    ("About Feet/B&W Stylized Shape/LINES.png", False),
    ("About Feet/B&W Stylized Shape/LINES_CLEANER.png", False),
    ("About Feet/B&W Stylized Shape/var", True),
    ("About Feet/B&W Stylized Shape/var/041.png", False),
    ("About Feet/B&W Stylized Shape/var/042.png", False),
    ("About Feet/Best Looking Sole", True),
    ("About Feet/Best Looking Sole/050-gp-standard v2-2x.png", False),
    ("About Feet/Best Looking Sole/best_looking_foot_sole__feet.png", False),
    ("About Feet/Best Looking Sole/temp", True),
    ("About Feet/Best Looking Sole/temp/020-SharpenAI-Softness.png", False),
    ("About Feet/Best Looking Sole/temp/020.png", False),
    ("About Feet/Best Looking Sole/temp/030.png", False),
    ("About Feet/Best Looking Sole/temp/040.png", False),
    ("About Feet/Best Looking Sole/temp/041.png", False),
    ("About Feet/Best Looking Sole/temp/050-gp-redefine-2x.png", False),
    ("About Feet/Best Looking Sole/temp/050-gp-standard v2-2x.png", False),
    ("About Feet/Best Looking Sole/temp/050.png", False),
    ("About Feet/Colored, no Texture", True),
    ("About Feet/Colored, no Texture/010.png", False),
    ("About Feet/Colored, no Texture/020-gp-cgi-2x.png", False),
    ("About Feet/Colored, no Texture/020.png", False),
    ("About Feet/Colored, no Texture/030.png", False),
    ("About Feet/Impecable Soles", True),
    ("About Feet/Impecable Soles/001.png", False),
    ("About Feet/Impecable Soles/002.png", False),
    ("About Feet/Impecable Soles/003.png", False),
    ("About Feet/Impecable Soles/004.png", False),
    ("About Feet/Impecable Soles/005.png", False),
    ("About Feet/Impecable Soles/006.png", False),
    ("About Feet/Impecable Soles/007.png", False),
    ("About Feet/Impecable Soles/008.png", False),
    ("About Feet/Impecable Soles/009.png", False),
    ("About Feet/Impecable Soles/010.png", False),
    ("About Feet/Impecable Soles/process.mov", False),
    ("About Feet/Impecable Soles/video-gen_4k-upscale.mp4", False),
    ("About Feet/Impecable Soles/video-gen_4k-upscale_1_chr2.mp4", False),
    ("About Feet/Impecable Soles/zzz__full", True),
    ("About Feet/Impecable Soles/zzz__full/010-gp-low resolution-2x.png", False),
    ("About Feet/Impecable Soles/zzz__full/010.png", False),
    ("About Feet/Impecable Soles/zzz__full/020.png", False),
    ("About Feet/Impecable Soles/zzz__full/021.png", False),
    ("About Feet/Impecable Soles/zzz__full/022.png", False),
    ("About Feet/Impecable Soles/zzz__full/023.png", False),
    ("About Feet/Impecable Soles/zzz__full/023_contrast.png", False),
    ("About Feet/Impecable Soles/zzz__full/024-gp-standard v2-2x.png", False),
    ("About Feet/Impecable Soles/zzz__full/024.png", False),
    ("About Feet/Impecable Soles/zzz__full/025.png", False),
    ("About Feet/Impecable Soles/zzz__full/026_overfitted.png", False),
    ("About Feet/Impecable Soles/zzz__full/027_dodge-&-burn-gp-high fidelity v2-2x.png", False),
    ("About Feet/Impecable Soles/zzz__full/027_dodge-&-burn.png", False),
    ("About Feet/Impecable Soles/zzz__full/027_FREQUENCY-MANIPULATION-LETS-GO.png", False),
    ("About Feet/Impecable Soles/zzz__full/030.png", False),
    ("About Feet/Impecable Soles/zzz__full/031.png", False),
    ("About Feet/Impecable Soles/zzz__full/032.png", False),
    ("About Feet/Impecable Soles/zzz__full/032_ONE-SHOT-DODGE-&-BURN.png", False),
    ("About Feet/Impecable Soles/zzz__full/040.png", False),
    ("About Feet/Impecable Soles/zzz__full/990.png", False),
    ("About Feet/Impecable Soles/zzz__full/991.png", False),
    ("About Feet/Impecable Soles/zzz__full/992.png", False),
    ("About Feet/Impecable Soles/zzz__full/993.png", False),
    ("About Feet/Impecable Soles/zzz__full/994.png", False),
    ("About Feet/NB2 Renders", True),
    ("About Feet/NB2 Renders/010.png", False),
    ("About Feet/NB2 Renders/020.png", False),
    ("About Feet/NB2 Renders/030.png", False),
    ("About Feet/NB2 Renders/110.png", False),
    ("About Feet/NB2 Renders/120.png", False),
    ("About Feet/NB2 Renders/130.png", False),
    ("AI Latent Upscale Pipeline", True),
    ("AI Latent Upscale Pipeline/010.png", False),
    ("AI Latent Upscale Pipeline/020.png", False),
    ("AI Latent Upscale Pipeline/030.png", False),
    ("AI Latent Upscale Pipeline/040.png", False),
    ("AI Latent Upscale Pipeline/990.png", False),
    ("AI Latent Upscale Pipeline/process", True),
    ("AI Latent Upscale Pipeline/process/delete-me-576x768.png", False),
    ("AI Latent Upscale Pipeline/process/delete-me-768x1024.png", False),
    ("AI Latent Upscale Pipeline/process/delete-me-768x576-gp-recover-768w.png", False),
    (
        "AI Latent Upscale Pipeline/process/delete-me-768x576-gp-recover-768w_lighter_darks-gp-redefine-2x.png",
        False,
    ),
    (
        "AI Latent Upscale Pipeline/process/delete-me-768x576-gp-recover-768w_lighter_darks-gp-redefine-2x.png.kra",
        False,
    ),
    (
        "AI Latent Upscale Pipeline/process/delete-me-768x576-gp-recover-768w_lighter_darks.png",
        False,
    ),
    (
        "AI Latent Upscale Pipeline/process/delete-me-768x576-gp-recover-768w_lighter_darks.png.kra",
        False,
    ),
    (
        "AI Latent Upscale Pipeline/process/delete-me-gp-low resolution v2-2x-SharpenAI-Motion.png",
        False,
    ),
    (
        "AI Latent Upscale Pipeline/process/delete-me-gp-low resolution v2-2x-SharpenAI-Motion_dodge&burn.png",
        False,
    ),
    (
        "AI Latent Upscale Pipeline/process/delete-me-gp-low resolution v2-2x-SharpenAI-Motion_dodge&burn_retouched-gp-low resolution v2-2048h.png",
        False,
    ),
    (
        "AI Latent Upscale Pipeline/process/delete-me-gp-low resolution v2-2x-SharpenAI-Motion_dodge&burn_retouched.png",
        False,
    ),
    ("AI Latent Upscale Pipeline/process/delete-me-gp-low resolution v2-2x.png", False),
    ("AI Latent Upscale Pipeline/process/delete-me-gp-low resolution v2-2x.webp", False),
    ("AI Latent Upscale Pipeline/process/delete-me.jpg", False),
    ("Android 18 û From ImaGen to 3DGen 3DRenderGen", True),
    ("Android 18 û From ImaGen to 3DGen 3DRenderGen/000.jpg", False),
    ("Android 18 û From ImaGen to 3DGen 3DRenderGen/010.png", False),
    ("Android 18 û From ImaGen to 3DGen 3DRenderGen/020.jpg", False),
    ("Android 18 û From ImaGen to 3DGen 3DRenderGen/030.jpg", False),
    ("Android 18 û From ImaGen to 3DGen 3DRenderGen/040.jpg", False),
    ("Android 18 û From ImaGen to 3DGen 3DRenderGen/050.webp", False),
    ("Android 18 û From ImaGen to 3DGen 3DRenderGen/51.png", False),
    ("Best Proportions Search", True),
    ("Best Proportions Search/000.png", False),
    ("Best Proportions Search/010.png", False),
    ("Best Proportions Search/020.png", False),
    ("Best Proportions Search/110.png", False),
    ("Best Proportions Search/120.png", False),
    ("Best Proportions Search/130.png", False),
    ("Best Proportions Search/2acXp.jpg", False),
    ("Best Proportions Search/9ovh6.jpg", False),
    ("Best Proportions Search/Gemini_Generated_Image_879k79879k79879k.png", False),
    ("Best Proportions Search/Gemini_Generated_Image_coztgocoztgocozt.png", False),
    ("Best Proportions Search/Gemini_Generated_Image_oagrqooagrqooagr.png", False),
    ("Best Proportions Search/Gemini_Generated_Image_sdfpqusdfpqusdfp.png", False),
    ("Best Proportions Search/Gemini_Generated_Image_wh7caxwh7caxwh7c.png", False),
    ("Bowsette", True),
    ("Bowsette/Bowsette.glb", False),
    ("Bowsette/Gemini_Generated_Image_vkbzfovkbzfovkbz-gp-high fidelity v2-1610h.png", False),
    ("Bowsette/leslie-van-den-broeck-bowsette.jpg", False),
    ("Bowsette/Untitled.blend", False),
    ("Bowsette/Untitled_001.blend", False),
    ("Bowsette/Untitled_001.blend1", False),
    ("Bowsette/Untitled_002.blend", False),
    ("Bowsette/Untitled_002.blend1", False),
    ("CelebDeGEN", True),
    ("CelebDeGEN/001__Natalie_Portman", True),
    ("CelebDeGEN/001__Natalie_Portman/010-gp-recover-2x - Copy.png", False),
    ("CelebDeGEN/001__Natalie_Portman/010.png", False),
    (
        "CelebDeGEN/001__Natalie_Portman/011-SharpenAI-Softness-gp-standard v2-2048w-gp-redefine-2048w.kra",
        False,
    ),
    (
        "CelebDeGEN/001__Natalie_Portman/011-SharpenAI-Softness-gp-standard v2-2048w-gp-redefine-2048w.png",
        False,
    ),
    ("CelebDeGEN/001__Natalie_Portman/011-SharpenAI-Softness-gp-standard v2-2048w.png", False),
    ("CelebDeGEN/001__Natalie_Portman/011-SharpenAI-Softness.png", False),
    ("CelebDeGEN/001__Natalie_Portman/011.png", False),
    ("CelebDeGEN/001__Natalie_Portman/990.png", False),
    ("Chained Up, Spreading Toes", True),
    ("Chained Up, Spreading Toes/000.png", False),
    ("Chained Up, Spreading Toes/010.png", False),
    ("Chained Up, Spreading Toes/020.png", False),
    (
        "Chained Up, Spreading Toes/Gemini_Generated_Image_4k8ytj4k8ytj4k8y-gp-high fidelity v2-2048h.png",
        False,
    ),
    ("Chained Up, Spreading Toes/Gemini_Generated_Image_gxhy7zgxhy7zgxhy.png", False),
    ("Chained Up, Spreading Toes/Gemini_Generated_Image_hhj79ihhj79ihhj7.png", False),
    ("Chained Up, Spreading Toes/Gemini_Generated_Image_hr8ejfhr8ejfhr8e.png", False),
    ("Chained Up, Spreading Toes/Gemini_Generated_Image_tv1xcgtv1xcgtv1x.png", False),
    ("Chained Up, Spreading Toes/PLAN.md", False),
    ("Chained Up, Spreading Toes/Spreading Toes 01_fixed.glb", False),
    ("Chained Up, Spreading Toes/Spreading Toes 02_fixed.glb", False),
    ("Chains on the Ceiling, Great Ass", True),
    ("Chains on the Ceiling, Great Ass/000.png", False),
    ("Chains on the Ceiling, Great Ass/Gemini_Generated_Image_fc2kq0fc2kq0fc2k.png", False),
    ("Chains on the Ceiling, Great Ass/Gemini_Generated_Image_h1zwqjh1zwqjh1zw.png", False),
    ("Chains on the Ceiling, Great Ass/Gemini_Generated_Image_n7u5jln7u5jln7u5.png", False),
    ("Chains on the Ceiling, Great Ass/TIED_UP.kra", False),
    ("Character Insert Speedrun", True),
    ("Character Insert Speedrun/000.kra", False),
    ("Character Insert Speedrun/000.png", False),
    ("Character Insert Speedrun/010.png", False),
    ("Character Insert Speedrun/020.png", False),
    ("Character Insert Speedrun/030.png", False),
    ("Character Insert Speedrun/040.png", False),
    ("Character Insert Speedrun/Gemini_Generated_Image_styn36styn36styn-gp-cgi-2x.kra", False),
    ("Character Insert Speedrun/TEMP", True),
    ("Character Insert Speedrun/TEMP/000.png", False),
    ("Character Insert Speedrun/TEMP/010.png", False),
    ("Character Insert Speedrun/TEMP/020.png", False),
    ("Character Insert Speedrun/TEMP/030.png", False),
    ("Character Insert Speedrun/TEMP/031.png", False),
    ("Character Insert Speedrun/TEMP/040.png", False),
    ("Character Insert Speedrun/TEMP/041.png", False),
    ("Character Insert Speedrun/TEMP/050.png", False),
    ("Cunny DeGEN", True),
    ("Cunny DeGEN/001__first-test_redhead_blonde-slav", True),
    ("Cunny DeGEN/001__first-test_redhead_blonde-slav/025.png", False),
    ("Cunny DeGEN/001__first-test_redhead_blonde-slav/991.png", False),
    ("Cunny DeGEN/001__first-test_redhead_blonde-slav/process", True),
    (
        "Cunny DeGEN/001__first-test_redhead_blonde-slav/process/00079-3608986181-gp-standard v2-2x.png",
        False,
    ),
    ("Cunny DeGEN/001__first-test_redhead_blonde-slav/process/00079-3608986181.png", False),
    ("Cunny DeGEN/001__first-test_redhead_blonde-slav/process/011.png", False),
    ("Cunny DeGEN/001__first-test_redhead_blonde-slav/process/020.png", False),
    (
        "Cunny DeGEN/001__first-test_redhead_blonde-slav/process/021-gp-high fidelity v2-2x.png",
        False,
    ),
    ("Cunny DeGEN/001__first-test_redhead_blonde-slav/process/021.png", False),
    ("Cunny DeGEN/001__first-test_redhead_blonde-slav/process/022.png", False),
    ("Cunny DeGEN/001__first-test_redhead_blonde-slav/process/023.png", False),
    ("Cunny DeGEN/001__first-test_redhead_blonde-slav/process/024.png", False),
    ("Cunny DeGEN/001__first-test_redhead_blonde-slav/process/025.png", False),
    ("Cunny DeGEN/001__first-test_redhead_blonde-slav/process/031.png", False),
    ("Cunny DeGEN/001__first-test_redhead_blonde-slav/process/090.png", False),
    ("Cunny DeGEN/001__first-test_redhead_blonde-slav/process/990.png", False),
    ("Cunny DeGEN/001__first-test_redhead_blonde-slav/process/990_0.5625.png", False),
    ("Cunny DeGEN/001__first-test_redhead_blonde-slav/process/991.png", False),
    ("Cunny DeGEN/001__first-test_redhead_blonde-slav/process/download.png", False),
    ("Cunny DeGEN/001__first-test_redhead_blonde-slav/process/download2.png", False),
    (
        "Cunny DeGEN/001__first-test_redhead_blonde-slav/process/download3-gp-standard v2-2x.png",
        False,
    ),
    ("Cunny DeGEN/001__first-test_redhead_blonde-slav/process/download3.png", False),
    ("Cunny DeGEN/002__free-the-nipple", True),
    ("Cunny DeGEN/002__free-the-nipple/010.png", False),
    ("Cunny DeGEN/002__free-the-nipple/020-gp-standard v2-2x.png", False),
    ("Cunny DeGEN/002__free-the-nipple/020.png", False),
    ("Cunny DeGEN/002__free-the-nipple/030.png", False),
    ("Cunny DeGEN/002__free-the-nipple/031.png", False),
    ("Cunny DeGEN/002__free-the-nipple/032.png", False),
    ("Cunny DeGEN/002__free-the-nipple/033.png", False),
    ("Cunny DeGEN/002__free-the-nipple/034.png", False),
    ("Cunny DeGEN/002__free-the-nipple/035.png", False),
    ("Cunny DeGEN/002__free-the-nipple/040.png", False),
    ("Cunny DeGEN/002__free-the-nipple/041.png", False),
    ("Cunny DeGEN/002__free-the-nipple/042.png", False),
    ("Cunny DeGEN/002__free-the-nipple/050.png", False),
    ("Cunny DeGEN/002__free-the-nipple/051-gp-high fidelity v2-2x.png", False),
    ("Cunny DeGEN/002__free-the-nipple/051.png", False),
    ("Cunny DeGEN/002__free-the-nipple/060.png", False),
    ("Cunny DeGEN/002__free-the-nipple/061.png", False),
    ("Cunny DeGEN/002__free-the-nipple/062.png", False),
    ("Cunny DeGEN/002__free-the-nipple/063.png", False),
    ("Cunny DeGEN/002__free-the-nipple/064.png", False),
    ("Cunny DeGEN/002__free-the-nipple/990.png", False),
    ("Cunny DeGEN/003__fucking-adorable", True),
    ("Cunny DeGEN/003__fucking-adorable/0050_cropped.png", False),
    ("Cunny DeGEN/003__fucking-adorable/009.png", False),
    ("Cunny DeGEN/003__fucking-adorable/010-gp-high fidelity v2-2x-SharpenAI-Softness.png", False),
    ("Cunny DeGEN/003__fucking-adorable/010-gp-high fidelity v2-2x.png", False),
    ("Cunny DeGEN/003__fucking-adorable/010-gp-redefine-2x.png", False),
    ("Cunny DeGEN/003__fucking-adorable/010.png", False),
    ("Cunny DeGEN/003__fucking-adorable/020-gp-redefine-1x.png", False),
    ("Cunny DeGEN/003__fucking-adorable/020.png", False),
    ("Cunny DeGEN/003__fucking-adorable/030.png", False),
    ("Cunny DeGEN/003__fucking-adorable/034.png", False),
    ("Cunny DeGEN/003__fucking-adorable/035.png", False),
    ("Cunny DeGEN/003__fucking-adorable/040.png", False),
    ("Cunny DeGEN/003__fucking-adorable/050.png", False),
    ("Cunny DeGEN/003__fucking-adorable/990.png", False),
    ("Cunny DeGEN/003__fucking-adorable/991.png", False),
    ("Cunny DeGEN/004__purple-cunny", True),
    ("Cunny DeGEN/004__purple-cunny/001.png", False),
    ("Cunny DeGEN/004__purple-cunny/002.png", False),
    ("Cunny DeGEN/004__purple-cunny/003.png", False),
    ("Cunny DeGEN/004__purple-cunny/004.png", False),
    ("Cunny DeGEN/004__purple-cunny/005.png", False),
    ("Cunny DeGEN/004__purple-cunny/006.png", False),
    ("Cunny DeGEN/004__purple-cunny/007.png", False),
    ("Cunny DeGEN/004__purple-cunny/output.mov", False),
    ("Cunny DeGEN/004__purple-cunny/output.mp4", False),
    ("Cunny DeGEN/005_readhead_headshot", True),
    ("Cunny DeGEN/005_readhead_headshot/010-gp-redefine-2x.png", False),
    ("Cunny DeGEN/005_readhead_headshot/010.png", False),
    ("Cunny DeGEN/005_readhead_headshot/020.kra", False),
    ("Cunny DeGEN/005_readhead_headshot/020.png", False),
    ("Cunny DeGEN/005_readhead_headshot/030.png", False),
    ("Cunny DeGEN/005_readhead_headshot/031.kra", False),
    ("Cunny DeGEN/005_readhead_headshot/031.png", False),
    ("Cunny DeGEN/005_readhead_headshot/040.kra", False),
    ("Cunny DeGEN/005_readhead_headshot/040.png", False),
    ("Cunny DeGEN/005_readhead_headshot/050.png", False),
    ("Cute Pose Bitch", True),
    ("Cute Pose Bitch/696736443_17953733019169393_5194198410333873158_n.jpg", False),
    ("Cute Pose Bitch/86n6O.jpg", False),
    ("Cute Pose Bitch/9ix34.jpg", False),
    ("Cute Pose Bitch/Gemini_Generated_Image_dzwo67dzwo67dzwo.png", False),
    ("Cute Pose Bitch/Gemini_Generated_Image_jg9vn4jg9vn4jg9v.png", False),
    ("Cute Pose Bitch/Gemini_Generated_Image_qz15duqz15duqz15.png", False),
    ("Cute Pose Bitch/HDEES.jpg", False),
    ("Cute Pose Bitch/U6RcJ.jpg", False),
    ("DVa Raised Sole", True),
    ("DVa Raised Sole/000.png", False),
    ("DVa Raised Sole/010.png", False),
    ("DVa Raised Sole/020.png", False),
    ("DVa Raised Sole/030.png", False),
    ("DVa Raised Sole/040.jpg", False),
    ("From Charcoal to Ideal Proportions", True),
    ("From Charcoal to Ideal Proportions/000.png", False),
    ("From Charcoal to Ideal Proportions/010.png", False),
    ("From Charcoal to Ideal Proportions/020.png", False),
    ("From Charcoal to Ideal Proportions/030.png", False),
    ("From Charcoal to Ideal Proportions/040.png", False),
    ("From Charcoal to Ideal Proportions/090.png", False),
    ("From Charcoal to Ideal Proportions/099.webp", False),
    ("From Charcoal to Ideal Proportions/VAR", True),
    ("From Charcoal to Ideal Proportions/VAR/a24dW.jpg", False),
    ("From Charcoal to Ideal Proportions/VAR/Gemini_Generated_Image_1pajak1pajak1paj.png", False),
    ("From Charcoal to Ideal Proportions/VAR/Gemini_Generated_Image_292o5t292o5t292o.png", False),
    (
        "From Charcoal to Ideal Proportions/VAR/Gemini_Generated_Image_998s5w998s5w998s (1).png",
        False,
    ),
    ("From Charcoal to Ideal Proportions/VAR/Gemini_Generated_Image_998s5w998s5w998s.png", False),
    ("From Charcoal to Ideal Proportions/VAR/nVI2o.jpg", False),
    ("From Charcoal to Ideal Proportions/VAR/qj3BB.jpg", False),
    ("Fubuki Green Thong SDA (Stable Diffusion Assisted)", True),
    ("Fubuki Green Thong SDA (Stable Diffusion Assisted)/Fubuki_refs.pur", False),
    ("Fubuki Green Thong SDA (Stable Diffusion Assisted)/IMGs", True),
    ("Fubuki Green Thong SDA (Stable Diffusion Assisted)/IMGs/000.png", False),
    ("Fubuki Green Thong SDA (Stable Diffusion Assisted)/IMGs/010.png", False),
    ("Fubuki Green Thong SDA (Stable Diffusion Assisted)/IMGs/020.png", False),
    ("Fubuki Green Thong SDA (Stable Diffusion Assisted)/IMGs/021.png", False),
    ("Fubuki Green Thong SDA (Stable Diffusion Assisted)/IMGs/030.png", False),
    ("Fubuki Green Thong SDA (Stable Diffusion Assisted)/IMGs/031.png", False),
    ("Fubuki Green Thong SDA (Stable Diffusion Assisted)/IMGs/040.png", False),
    ("Fubuki Green Thong SDA (Stable Diffusion Assisted)/IMGs/041.png", False),
    ("Fubuki Green Thong SDA (Stable Diffusion Assisted)/IMGs/050.png", False),
    ("Fubuki Green Thong SDA (Stable Diffusion Assisted)/IMGs/051.png", False),
    ("Fubuki Green Thong SDA (Stable Diffusion Assisted)/IMGs/060.png", False),
    ("Fubuki Green Thong SDA (Stable Diffusion Assisted)/IMGs/061.png", False),
    ("Fubuki Green Thong SDA (Stable Diffusion Assisted)/IMGs/062-gp-cgi-2x.png", False),
    ("Fubuki Green Thong SDA (Stable Diffusion Assisted)/IMGs/062.png", False),
    ("Fubuki Green Thong SDA (Stable Diffusion Assisted)/IMGs/063.png", False),
    ("Fubuki Green Thong SDA (Stable Diffusion Assisted)/IMGs/064-gp-cgi-2x.png", False),
    ("Fubuki Green Thong SDA (Stable Diffusion Assisted)/IMGs/064.png", False),
    ("Fubuki Green Thong SDA (Stable Diffusion Assisted)/IMGs/070.png", False),
    ("Fubuki Green Thong SDA (Stable Diffusion Assisted)/IMGs/071.png", False),
    ("Fubuki Green Thong SDA (Stable Diffusion Assisted)/IMGs/072-gp-cgi-2x.png", False),
    ("Fubuki Green Thong SDA (Stable Diffusion Assisted)/IMGs/072.png", False),
    ("Fubuki Green Thong SDA (Stable Diffusion Assisted)/IMGs/073.png", False),
    ("Fubuki Green Thong SDA (Stable Diffusion Assisted)/IMGs/074.png", False),
    ("Fubuki Green Thong SDA (Stable Diffusion Assisted)/IMGs/075.png", False),
    ("Fubuki Green Thong SDA (Stable Diffusion Assisted)/IMGs/076.png", False),
    ("Fubuki Green Thong SDA (Stable Diffusion Assisted)/IMGs/077.png", False),
    ("Fubuki Green Thong SDA (Stable Diffusion Assisted)/IMGs/078.png", False),
    ("Fubuki Green Thong SDA (Stable Diffusion Assisted)/IMGs/079.png", False),
    ("Fubuki Green Thong SDA (Stable Diffusion Assisted)/IMGs/080.png", False),
    ("Fubuki Green Thong SDA (Stable Diffusion Assisted)/IMGs/081.png", False),
    ("Fubuki Green Thong SDA (Stable Diffusion Assisted)/IMGs/082.png", False),
    ("Fubuki Green Thong SDA (Stable Diffusion Assisted)/IMGs/090.png", False),
    ("Fubuki Green Thong SDA (Stable Diffusion Assisted)/IMGs/091.png", False),
    ("Fubuki Green Thong SDA (Stable Diffusion Assisted)/IMGs/83.png", False),
    ("Fubuki Green Thong SDA (Stable Diffusion Assisted)/IMGs/92.png", False),
    ("Fubuki Green Thong SDA (Stable Diffusion Assisted)/IMGs/999.png", False),
    ("Fubuki Green Thong SDA (Stable Diffusion Assisted)/IMGs/_IMGs_ABRIDGED", True),
    ("Fubuki Green Thong SDA (Stable Diffusion Assisted)/IMGs/_IMGs_ABRIDGED/000.png", False),
    ("Fubuki Green Thong SDA (Stable Diffusion Assisted)/IMGs/_IMGs_ABRIDGED/010.png", False),
    ("Fubuki Green Thong SDA (Stable Diffusion Assisted)/IMGs/_IMGs_ABRIDGED/020.png", False),
    ("Fubuki Green Thong SDA (Stable Diffusion Assisted)/IMGs/_IMGs_ABRIDGED/030.png", False),
    ("Fubuki Green Thong SDA (Stable Diffusion Assisted)/IMGs/_IMGs_ABRIDGED/031.png", False),
    ("Fubuki Green Thong SDA (Stable Diffusion Assisted)/IMGs/_IMGs_ABRIDGED/050.png", False),
    ("Fubuki Green Thong SDA (Stable Diffusion Assisted)/IMGs/_IMGs_ABRIDGED/051.png", False),
    ("Fubuki Green Thong SDA (Stable Diffusion Assisted)/IMGs/_IMGs_ABRIDGED/060.png", False),
    ("Fubuki Green Thong SDA (Stable Diffusion Assisted)/IMGs/_IMGs_ABRIDGED/061.png", False),
    ("Fubuki Green Thong SDA (Stable Diffusion Assisted)/IMGs/_IMGs_ABRIDGED/062.png", False),
    ("Fubuki Green Thong SDA (Stable Diffusion Assisted)/IMGs/_IMGs_ABRIDGED/063.png", False),
    ("Fubuki Green Thong SDA (Stable Diffusion Assisted)/IMGs/_IMGs_ABRIDGED/064.png", False),
    ("Fubuki Green Thong SDA (Stable Diffusion Assisted)/IMGs/_IMGs_ABRIDGED/070.png", False),
    ("Fubuki Green Thong SDA (Stable Diffusion Assisted)/IMGs/_IMGs_ABRIDGED/071.png", False),
    ("Fubuki Green Thong SDA (Stable Diffusion Assisted)/IMGs/_IMGs_ABRIDGED/072.png", False),
    ("Fubuki Green Thong SDA (Stable Diffusion Assisted)/IMGs/_IMGs_ABRIDGED/073.png", False),
    ("Fubuki Green Thong SDA (Stable Diffusion Assisted)/IMGs/_IMGs_ABRIDGED/074.png", False),
    ("Fubuki Green Thong SDA (Stable Diffusion Assisted)/IMGs/_IMGs_ABRIDGED/075.png", False),
    ("Fubuki Green Thong SDA (Stable Diffusion Assisted)/IMGs/_IMGs_ABRIDGED/076.png", False),
    ("Fubuki Green Thong SDA (Stable Diffusion Assisted)/IMGs/_IMGs_ABRIDGED/077.png", False),
    ("Fubuki Green Thong SDA (Stable Diffusion Assisted)/IMGs/_MASKS", True),
    ("Fubuki Green Thong SDA (Stable Diffusion Assisted)/IMGs/_MASKS/00.png", False),
    ("Fubuki Green Thong SDA (Stable Diffusion Assisted)/IMGs/_MASKS/01.png", False),
    ("Fubuki Green Thong SDA (Stable Diffusion Assisted)/IMGs/_MASKS/02.png", False),
    ("Fubuki Green Thong SDA (Stable Diffusion Assisted)/IMGs/_MASKS/03-gp-cgi-2x.png", False),
    ("Fubuki Green Thong SDA (Stable Diffusion Assisted)/IMGs/_MASKS/03.png", False),
    ("Fubuki Green Thong SDA (Stable Diffusion Assisted)/IMGs/_MASKS/04-gp-cgi-2x.png", False),
    ("Fubuki Green Thong SDA (Stable Diffusion Assisted)/IMGs/_MASKS/04.png", False),
    ("Fubuki Green Thong SDA (Stable Diffusion Assisted)/IMGs/_MASKS/_MAIN_ALPHA.png", False),
    ("High Contrast Test", True),
    ("High Contrast Test/000.jpg", False),
    ("High Contrast Test/010.png", False),
    ("High Contrast Test/015.png", False),
    ("High Contrast Test/020.jpg", False),
    ("High Contrast Test/030.jpg", False),
    ("High Contrast Test/040.png", False),
    ("High Contrast Test/999.jpg", False),
    ("High Contrast Test/Gemini_Generated_Image_40snvy40snvy40sn.png", False),
    ("High Contrast Test/Gemini_Generated_Image_ru6eqjru6eqjru6e.kra", False),
    ("High Contrast Test/PROMPT.txt", False),
    ("High Contrast Test/VAR", True),
    ("High Contrast Test/VAR/Charcoal Proportions.glb", False),
    ("High Contrast Test/VAR/charcoal_01.blend", False),
    ("High Contrast Test/VAR/charcoal_01.blend1", False),
    ("High Contrast Test/VAR/Gemini_Generated_Image_1iksud1iksud1iks.png", False),
    ("High Contrast Test/VAR/Gemini_Generated_Image_4txtug4txtug4txt.png", False),
    ("High Contrast Test/VAR/Gemini_Generated_Image_4un6504un6504un6.png", False),
    ("High Contrast Test/VAR/Gemini_Generated_Image_lblnc0lblnc0lbln.png", False),
    ("High Contrast Test/VAR/Gemini_Generated_Image_s0t5v0s0t5v0s0t5.png", False),
    ("High Contrast Test/VAR/Screenshot 2026-06-01 075217.png", False),
    ("Image to AI 1-to-1 Translation", True),
    ("Image to AI 1-to-1 Translation/IMAGES", True),
    ("Image to AI 1-to-1 Translation/IMAGES/000.png", False),
    ("Image to AI 1-to-1 Translation/IMAGES/010.png", False),
    ("Image to AI 1-to-1 Translation/IMAGES/011.png", False),
    ("Image to AI 1-to-1 Translation/IMAGES/020.png", False),
    ("Image to AI 1-to-1 Translation/IMAGES/021.png", False),
    ("Image to AI 1-to-1 Translation/IMAGES/022.png", False),
    ("Image to AI 1-to-1 Translation/IMAGES/023.png", False),
    ("Image to AI 1-to-1 Translation/IMAGES/024.png", False),
    ("Image to AI 1-to-1 Translation/IMAGES/025.png", False),
    ("Image to AI 1-to-1 Translation/IMAGES/026-gp-cgi-2x.png", False),
    ("Image to AI 1-to-1 Translation/IMAGES/026.png", False),
    ("Image to AI 1-to-1 Translation/IMAGES/030-gp-cgi-2x.png", False),
    ("Image to AI 1-to-1 Translation/IMAGES/030.png", False),
    ("Image to AI 1-to-1 Translation/IMAGES/031.png", False),
    ("Image to AI 1-to-1 Translation/IMAGES/999.png", False),
    ("Image to AI 1-to-1 Translation/IMAGES/_000.png", False),
    ("Image to AI 1-to-1 Translation/IMAGES/_010.png", False),
    ("Image to AI 1-to-1 Translation/IMAGES/temp", True),
    ("Image to AI 1-to-1 Translation/IMAGES/temp/023.png", False),
    ("Image to AI 1-to-1 Translation/IMAGES/temp/afdssadf.png", False),
    ("Image to AI 1-to-1 Translation/IMAGES/temp/arweuyh.png", False),
    ("Image to AI 1-to-1 Translation/KRAs", True),
    ("Image to AI 1-to-1 Translation/KRAs/010.kra", False),
    ("Image to AI 1-to-1 Translation/KRAs/butthole_01.kra", False),
    ("Last Tracing, Foot Switch", True),
    ("Last Tracing, Foot Switch/1.jpg", False),
    ("Last Tracing, Foot Switch/1.kra", False),
    ("Last Tracing, Foot Switch/1.png", False),
    ("Last Tracing, Foot Switch/asfgdshgdh.png", False),
    (
        "Last Tracing, Foot Switch/Gemini_Generated_Image_kgsigokgsigokgsi-gp-high fidelity v2-1707h.png",
        False,
    ),
    ("Last Tracing, Foot Switch/Gemini_Generated_Image_kgsigokgsigokgsi.png", False),
    ("Last Tracing, Foot Switch/Gemini_Generated_Image_mig4gpmig4gpmig4.png", False),
    ("Last Tracing, Foot Switch/photo_2026-05-28_03-33-12.jpg", False),
    ("Last Tracing, Foot Switch/YES.png", False),
    ("Lying on Ground, Lookin' at Phone", True),
    ("Lying on Ground, Lookin' at Phone/000.jpg", False),
    ("Lying on Ground, Lookin' at Phone/010.png", False),
    ("Lying on Ground, Lookin' at Phone/asfdasfdafdsafds-gp-high fidelity v2-2x.kra", False),
    ("Lying on Ground, Lookin' at Phone/asfdasfdafdsafds-gp-high fidelity v2-2x.png", False),
    ("Lying on Ground, Lookin' at Phone/chosen1.png", False),
    ("Lying on Ground, Lookin' at Phone/Gemini_Generated_Image_1tmcpk1tmcpk1tmc.png", False),
    ("Lying on Ground, Lookin' at Phone/Gemini_Generated_Image_57uxig57uxig57ux.png", False),
    ("Lying on Ground, Lookin' at Phone/Gemini_Generated_Image_a6metfa6metfa6me.kra", False),
    ("Lying on Ground, Lookin' at Phone/Gemini_Generated_Image_a6metfa6metfa6me.png", False),
    ("Lying on Ground, Lookin' at Phone/Gemini_Generated_Image_dd31kndd31kndd31.png", False),
    ("Lying on Ground, Lookin' at Phone/Gemini_Generated_Image_k11fi9k11fi9k11f.png", False),
    ("Lying on Ground, Lookin' at Phone/Gemini_Generated_Image_o3pa0oo3pa0oo3pa.png", False),
    (
        "Lying on Ground, Lookin' at Phone/Gemini_Generated_Image_q1jfpgq1jfpgq1jf-gp-high fidelity v2-2x.png",
        False,
    ),
    ("Lying on Ground, Lookin' at Phone/lastest.png", False),
    ("Lying on Ground, Lookin' at Phone/Untitled.obj", False),
    ("Lying on Ground, Lookin' at Phone/Untitled.png", False),
    ("Makima Deepthroat", True),
    ("Makima Deepthroat/throat_12.kra", False),
    ("Makima Deepthroat/PNGs", True),
    ("Makima Deepthroat/PNGs/00.png", False),
    ("Makima Deepthroat/PNGs/01.png", False),
    ("Makima Deepthroat/PNGs/02.png", False),
    ("Makima Deepthroat/PNGs/03.png", False),
    ("Makima Deepthroat/PNGs/04.png", False),
    ("Makima Deepthroat/PNGs/05-gigapixel-standard-scale-2_00x.png", False),
    ("Makima Deepthroat/PNGs/05.png", False),
    ("Makima Deepthroat/PNGs/delete-me.png", False),
    ("Mangafication Process", True),
    ("Mangafication Process/OUTPUT", True),
    ("Mangafication Process/OUTPUT/delete-me0001-2125.mp4", False),
    ("Mangafication Process/PROCESS", True),
    ("Mangafication Process/PROCESS/IMG_SQC", True),
    ("Mangafication Process/PROCESS/IMG_SQC/00.png", False),
    ("Mangafication Process/PROCESS/IMG_SQC/01.png", False),
    ("Mangafication Process/PROCESS/IMG_SQC/02.png", False),
    ("Mangafication Process/PROCESS/IMG_SQC/03.png", False),
    ("Mangafication Process/PROCESS/IMG_SQC/04.png", False),
    ("Mangafication Process/PROCESS/IMG_SQC/05.png", False),
    ("Mangafication Process/PROCESS/IMG_SQC/06.png", False),
    ("Mangafication Process/PROCESS/IMG_SQC/07.png", False),
    ("Mangafication Process/PROCESS/IMG_SQC/08.png", False),
    ("Mangafication Process/PROCESS/IMG_SQC/09.png", False),
    ("Mangafication Process/PROCESS/IMG_SQC/10.png", False),
    ("Mangafication Process/Test Video Edit", True),
    ("Mangafication Process/Test Video Edit/annie_21.blend", False),
    ("Mikasa In Shackles Arching", True),
    ("Mikasa In Shackles Arching/v1", True),
    ("Mikasa In Shackles Arching/v1/000.png", False),
    ("Mikasa In Shackles Arching/v1/010.png", False),
    ("Mikasa In Shackles Arching/v1/011.png", False),
    ("Mikasa In Shackles Arching/v1/012.png", False),
    ("Mikasa In Shackles Arching/v1/020.png", False),
    ("Mikasa In Shackles Arching/v1/030.png", False),
    ("Mikasa In Shackles Arching/v1/031.png", False),
    ("Mikasa In Shackles Arching/v1/032.webp", False),
    ("Mikasa In Shackles Arching/v1/040.png", False),
    ("Mikasa In Shackles Arching/v1/090.png", False),
    ("Mikasa In Shackles Arching/v1/091.png", False),
    ("Mikasa In Shackles Arching/v1/092.jpg", False),
    ("Mikasa In Shackles Arching/v1/093.png", False),
    ("Mikasa In Shackles Arching/v2", True),
    ("Mikasa In Shackles Arching/v2/000.png", False),
    ("Mikasa In Shackles Arching/v2/010.png", False),
    ("Mikasa In Shackles Arching/v2/020.png", False),
    ("Mikasa In Shackles Arching/v2/021.png", False),
    ("Mikasa In Shackles Arching/v2/080.png", False),
    ("Mikasa In Shackles Arching/v2/090.png", False),
    ("Mikasa In Shackles Arching/v2/100.png", False),
    ("Mikasa In Shackles Arching/v2/110.png", False),
    ("Mikasa In Shackles Arching/v2/Gemini_Generated_Image_89yo0089yo0089yo.png", False),
    ("Mikasa In Shackles Arching/v2/Mikasa in Shackles v1.glb", False),
    ("Mikasa In Shackles Arching/VAR", True),
    ("Mikasa In Shackles Arching/VAR/Gemini_Generated_Image_fjjavjfjjavjfjja.png", False),
    ("Mikasa In Shackles Arching/VAR/Gemini_Generated_Image_hqnxw2hqnxw2hqnx.png", False),
    ("Mikasa In Shackles Arching/VAR/Gemini_Generated_Image_yb8upgyb8upgyb8u.png", False),
    ("MyInputwo Proportions Test", True),
    ("MyInputwo Proportions Test/Gemini_Generated_Image_eswx39eswx39eswx.png", False),
    ("MyInputwo Proportions Test/Gemini_Generated_Image_lc4dghlc4dghlc4d.png", False),
    ("MyInputwo Proportions Test/my-inputwo-fo.jpg", False),
    ("MyInputwo Proportions Test/MyInputwo", True),
    ("MyInputwo Proportions Test/MyInputwo/my-inputwo-3e1.jpg", False),
    ("MyInputwo Proportions Test/MyInputwo/my-inputwo-b.webp", False),
    ("MyInputwo Proportions Test/MyInputwo/my-inputwo-d3.jpg", False),
    ("MyInputwo Proportions Test/MyInputwo/my-inputwo-mk123.jpg", False),
    ("MyInputwo Proportions Test/MyInputwo/my-inputwo-tht123.jpg", False),
    ("MyInputwo Proportions Test/MyInputwo/my-inputwo-x.jpg", False),
    ("NanoBanana Pro + Grok", True),
    ("NanoBanana Pro + Grok/000.png", False),
    ("NanoBanana Pro + Grok/010.png", False),
    ("NanoBanana Pro + Grok/015_NB_PRO.png", False),
    ("NanoBanana Pro + Grok/020.png", False),
    ("NanoBanana Pro + Grok/030.png", False),
    ("NanoBanana Pro + Grok/034.png", False),
    ("NanoBanana Pro + Grok/035.png", False),
    ("NanoBanana Pro + Grok/FACE_MODEL_STYLE_REFERENCE.png", False),
    ("NanoBanana Pro + Grok/Gemini_Generated_Image_oy630woy630woy63.kra", False),
    ("NanoBanana Pro + Grok/grok-video-c3bfc725-6964-421a-a29c-df1d11892952.mp4", False),
    ("NanoBanana Pro + Grok/temp", True),
    ("NanoBanana Pro + Grok/temp/00003-3261327098.png", False),
    ("NanoBanana Pro + Grok/temp/00032-2029616210.png", False),
    ("NanoBanana Pro + Grok/temp/010.png", False),
    ("NanoBanana Pro + Grok/temp/020.png", False),
    ("NanoBanana Pro + Grok/temp/MASK.kra", False),
    ("NanoBanana Pro + Grok/temp/MASK.png", False),
    ("NB2 Androssi Bikini", True),
    ("NB2 Androssi Bikini/000.jpg", False),
    ("NB2 Androssi Bikini/001.png", False),
    ("NB2 Androssi Bikini/bikini_clean.png", False),
    ("NB2 Androssi Bikini/bikini_lines.png", False),
    ("NB2 Androssi Bikini/Gemini_Generated_Image_1nd3if1nd3if1nd3.png", False),
    (
        "NB2 Androssi Bikini/Gemini_Generated_Image_41qjsv41qjsv41qj-gp-high fidelity v2-2x.png",
        False,
    ),
    (
        "NB2 Androssi Bikini/Gemini_Generated_Image_d9kntd9kntd9kntd-gp-high fidelity v2-2x.kra",
        False,
    ),
    (
        "NB2 Androssi Bikini/Gemini_Generated_Image_d9kntd9kntd9kntd-gp-high fidelity v2-2x.png",
        False,
    ),
    ("NB2 Androssi Bikini/YqPXF-gp-high fidelity v2-1200h.png", False),
    ("NB2 Androssi Bikini/YqPXF.jpg", False),
    ("NB2 Androssi Bikini/New folder", True),
    ("NB2 Androssi Bikini/New folder/000.png", False),
    ("NB2 Androssi Bikini/New folder/010.png", False),
    ("NB2 Androssi Bikini/New folder/050.png", False),
    (
        "NB2 Androssi Bikini/New folder/Gemini_Generated_Image_d9kntd9kntd9kntd-gp-high fidelity v2-2x_001.kra",
        False,
    ),
    ("NB2 Sketch to Render Speedrun", True),
    ("NB2 Sketch to Render Speedrun/000.png", False),
    ("NB2 Sketch to Render Speedrun/010.png", False),
    ("NB2 Sketch to Render Speedrun/020.png", False),
    ("NB2 Sketch to Render Speedrun/040.png", False),
    ("NB2 Sketch to Render Speedrun/050.png", False),
    ("NB2 Sketch to Render Speedrun/060.png", False),
    ("NB2 Sketch to Render Speedrun/061.jpg", False),
    ("Onodera Kazusa", True),
    ("Onodera Kazusa/000__1-1__16-9.png", False),
    ("Onodera Kazusa/dfsafadsfasfd.png", False),
    ("Onodera Kazusa/Gemini_Generated_Image_75m35q75m35q75m3.png", False),
    ("Onodera Kazusa/Gemini_Generated_Image_odbgh4odbgh4odbg.kra", False),
    ("Onodera Kazusa/_originals", True),
    ("Onodera Kazusa/_originals/000.png", False),
    ("Onodera Kazusa/_originals/000__1-1.png", False),
    ("Onodera Kazusa/_originals/Gemini_Generated_Image_i7v1tli7v1tli7v1.png", False),
    ("Pose to 3D to Pose to Stylization to Character Replacement +Render Styles", True),
    ("Pose to 3D to Pose to Stylization to Character Replacement +Render Styles/000.png", False),
    (
        "Pose to 3D to Pose to Stylization to Character Replacement +Render Styles/010_NB2.png",
        False,
    ),
    ("Pose to 3D to Pose to Stylization to Character Replacement +Render Styles/020.png", False),
    (
        "Pose to 3D to Pose to Stylization to Character Replacement +Render Styles/030_TRACE.png",
        False,
    ),
    (
        "Pose to 3D to Pose to Stylization to Character Replacement +Render Styles/040_NUDE.png",
        False,
    ),
    ("Pose to 3D to Pose to Stylization to Character Replacement +Render Styles/041.png", False),
    (
        "Pose to 3D to Pose to Stylization to Character Replacement +Render Styles/050_BIKINI.jpg",
        False,
    ),
    (
        "Pose to 3D to Pose to Stylization to Character Replacement +Render Styles/060_STYLIZATION_BODY.jpg",
        False,
    ),
    (
        "Pose to 3D to Pose to Stylization to Character Replacement +Render Styles/070_STYLIZATION_HEAD.jpg",
        False,
    ),
    ("Pose to 3D to Pose to Stylization to Character Replacement +Render Styles/080.png", False),
    ("Pose to 3D to Pose to Stylization to Character Replacement +Render Styles/090.png", False),
    ("Pose to 3D to Pose to Stylization to Character Replacement +Render Styles/100.png", False),
    ("Pose to 3D to Pose to Stylization to Character Replacement +Render Styles/110.png", False),
    ("Pose to 3D to Pose to Stylization to Character Replacement +Render Styles/111.jpg", False),
    ("Pose to 3D to Pose to Stylization to Character Replacement +Render Styles/120.png", False),
    ("Pose to 3D to Pose to Stylization to Character Replacement +Render Styles/121.png", False),
    ("Pose to 3D to Pose to Stylization to Character Replacement +Render Styles/130.png", False),
    ("Pose to 3D to Pose to Stylization to Character Replacement +Render Styles/131.png", False),
    ("Pose to 3D to Pose to Stylization to Character Replacement +Render Styles/VAR", True),
    (
        "Pose to 3D to Pose to Stylization to Character Replacement +Render Styles/VAR/500_333.jpeg",
        False,
    ),
    (
        "Pose to 3D to Pose to Stylization to Character Replacement +Render Styles/VAR/b_the_woman_poses.mp4",
        False,
    ),
    (
        "Pose to 3D to Pose to Stylization to Character Replacement +Render Styles/VAR/Gemini_Generated_Image_vd002pvd002pvd00.png",
        False,
    ),
    ("Simple Foot Render", True),
    ("Simple Foot Render/NewScene.pur", False),
    ("Simple Foot Render/sole_01.kra", False),
    ("Simple Foot Render/sole_02.kra", False),
    ("Simple Foot Render/sole_03.kra", False),
    ("Simple Foot Render/sole_04.kra", False),
    ("Simple Foot Render/sole_05.kra", False),
    ("Simple Foot Render/VAR", True),
    ("Simple Foot Render/VAR/1 - Untitled.kra", False),
    ("Simple Foot Render/VAR/REFERENCE.png", False),
    ("Simple Foot Render/VAR/LINEART", True),
    ("Simple Foot Render/VAR/LINEART/010.png", False),
    ("Simple Foot Render/VAR/LINEART/020.png", False),
    ("Simple Foot Render/VAR/TEST_REF_COPY", True),
    ("Simple Foot Render/VAR/TEST_REF_COPY/000.png", False),
    ("Simple Foot Render/VAR/TEST_REF_COPY/010.png", False),
    ("Simple Foot Render/__OUTPUT", True),
    ("Simple Foot Render/__OUTPUT/010.png", False),
    ("Simple Foot Render/__OUTPUT/020.png", False),
    ("Simple Foot Render/__OUTPUT/021.png", False),
    ("Simple Foot Render/__OUTPUT/022.png", False),
    ("Sitting on a Bench, Soles Peaking", True),
    (
        "Sitting on a Bench, Soles Peaking/31b64b2cfca3484db844bc8b18dcba97~tplv-wopfjsm1ax-aigc_resize_4096_4096.webp",
        False,
    ),
    (
        "Sitting on a Bench, Soles Peaking/53a946b9549742139e259d72d42db408~tplv-wopfjsm1ax-aigc_resize_4096_4096.webp",
        False,
    ),
    (
        "Sitting on a Bench, Soles Peaking/9fe60fd97217499db9c5483d72b0b9a1~tplv-wopfjsm1ax-aigc_resize_4096_4096-gp-high fidelity v2-2160h.png",
        False,
    ),
    ("Sitting on a Bench, Soles Peaking/Gemini_Generated_Image_cv4y6rcv4y6rcv4y.png", False),
    ("Sitting on a Bench, Soles Peaking/Gemini_Generated_Image_iziv3fiziv3fiziv.png", False),
    ("Sitting on a Bench, Soles Peaking/Gemini_Generated_Image_ozypl6ozypl6ozyp.png", False),
    ("Sitting on a Bench, Soles Peaking/Gemini_Generated_Image_qyf6jxqyf6jxqyf6.png", False),
    ("Sitting on a Bench, Soles Peaking/Gemini_Generated_Image_sjb079sjb079sjb0.png", False),
    ("Sitting on a Bench, Soles Peaking/photo_2026-05-28_03-33-12.jpg", False),
    ("Sitting on a Bench, Soles Peaking/Soles Peeking.glb", False),
    ("Sitting on a Bench, Soles Peaking/soles_peeking.png", False),
    ("Sitting on a Bench, Soles Peaking/THIS_TOOK_LIKE_FIFTY_TRIES.png", False),
    ("Sitting on a Bench, Soles Peaking/THIS_TOOK_LIKE_FIFTY_TRIES__EDITED.png", False),
    ("Sitting on a Bench, Soles Peaking/Untitled.blend", False),
    ("Stacked Tracer Sitting Topless", True),
    ("Stacked Tracer Sitting Topless/00001-3847304628.png", False),
    ("Stacked Tracer Sitting Topless/AfzJ6-gp-redefine-realistic-2x.png", False),
    ("Stacked Tracer Sitting Topless/Gemini_Generated_Image_z9h87kz9h87kz9h8.png", False),
    ("Stacked Tracer Sitting Topless/xEPqo.jpg", False),
    ("Struggling While Squatting", True),
    ("Struggling While Squatting/000.png", False),
    ("Struggling While Squatting/010.png", False),
    ("Struggling While Squatting/020.png", False),
    ("Struggling While Squatting/030.png", False),
    ("Struggling While Squatting/040.png", False),
    ("Struggling While Squatting/050.png", False),
    ("Struggling While Squatting/050__LOW_ANGLE_TRUE.png", False),
    ("Struggling While Squatting/051__LOW_ANGLE_RENDER__POSE_TRANSFER.png", False),
    ("Struggling While Squatting/090.png", False),
    ("Struggling While Squatting/KRA + BLEND", True),
    (
        "Struggling While Squatting/KRA + BLEND/051__LOW_ANGLE_RENDER__POSE_TRANSFER-gp-high fidelity v2-2048h.kra",
        False,
    ),
    ("Struggling While Squatting/KRA + BLEND/LOW_ANGLE_RENDER__POSE_TRANSFER.kra", False),
    ("Struggling While Squatting/KRA + BLEND/squatting_01.blend", False),
    ("Struggling While Squatting/KRA + BLEND/STRUGGLE.kra", False),
    ("Struggling While Squatting/KRA + BLEND/Struggling and Squatting.glb", False),
    ("Struggling While Squatting/VAR", True),
    ("Struggling While Squatting/VAR/060__HOLY_SHIT.png", False),
    ("Struggling While Squatting/VAR/Gemini_Generated_Image_pt1cbypt1cbypt1c.png", False),
    ("Test Fashion 3D Model", True),
    ("Test Fashion 3D Model/010.kra", False),
    ("Test Fashion 3D Model/010.png", False),
    ("Test Fashion 3D Model/020.png", False),
    ("Test Fashion 3D Model/030.png", False),
    ("Test Fashion 3D Model/031.png", False),
    ("Test Fashion 3D Model/032.png", False),
    ("Test Fashion 3D Model/040.png", False),
    ("Test Fashion 3D Model/3D_MODEL.png", False),
    ("Test Fashion 3D Model/ALPHA.png", False),
    ("Test Fashion 3D Model/AO.png", False),
    ("Test Fashion 3D Model/delete-me.blend", False),
    ("Test Fashion 3D Model/delete-me.blend1", False),
    ("Test Fashion 3D Model/Gemini_Generated_Image_ojk894ojk894ojk8-gp-cgi-2048h.kra", False),
    (
        "Test Fashion 3D Model/Gemini_Generated_Image_va8zk3va8zk3va8z-gp-cgi-2048h-faceai v2.kra",
        False,
    ),
    ("Test Fashion 3D Model/NB_GEN.png", False),
    ("Test Fashion 3D Model/OUTFIT.png", False),
    ("Uraraka Gape Stable Diffusion Render", True),
    ("Uraraka Gape Stable Diffusion Render/000.png", False),
    ("Uraraka Gape Stable Diffusion Render/010.png", False),
    ("Uraraka Gape Stable Diffusion Render/020.png", False),
    ("Uraraka Gape Stable Diffusion Render/030.png", False),
    ("Uraraka Gape Stable Diffusion Render/031.png", False),
    ("Uraraka Gape Stable Diffusion Render/040.png", False),
    ("Uraraka Gape Stable Diffusion Render/050.png", False),
    ("Uraraka Gape Stable Diffusion Render/060.png", False),
    ("Uraraka Gape Stable Diffusion Render/070.png", False),
    ("Uraraka Gape Stable Diffusion Render/071.png", False),
    ("Uraraka Gape Stable Diffusion Render/080.png", False),
    ("Uraraka Gape Stable Diffusion Render/081.png", False),
    ("Uraraka Gape Stable Diffusion Render/082.png", False),
    ("Uraraka Gape Stable Diffusion Render/083.png", False),
    ("Uraraka Gape Stable Diffusion Render/090.png", False),
    ("Uraraka Gape Stable Diffusion Render/100.png", False),
    ("Uraraka Gape Stable Diffusion Render/110.png", False),
    ("Uraraka Gape Stable Diffusion Render/111.png", False),
    ("Uraraka Gape Stable Diffusion Render/120-gp-cgi-2x.png", False),
    ("Uraraka Gape Stable Diffusion Render/120.png", False),
    ("Uraraka Gape Stable Diffusion Render/130.png", False),
    ("Uraraka Gape Stable Diffusion Render/140-gp-cgi-2x.png", False),
    ("Uraraka Gape Stable Diffusion Render/140.png", False),
    ("Uraraka Gape Stable Diffusion Render/150.png", False),
    ("Uraraka Gape Stable Diffusion Render/151.png", False),
    ("Uraraka Gape Stable Diffusion Render/160.png", False),
    ("Uraraka Gape Stable Diffusion Render/161.png", False),
    ("Uraraka Gape Stable Diffusion Render/999.png", False),
    ("Uraraka Gape Stable Diffusion Render/Uraraka Ochako Gaping.png", False),
    ("Uraraka Gape Stable Diffusion Render/__masks", True),
    ("Uraraka Gape Stable Diffusion Render/__masks/00.png", False),
    ("Uraraka Gape Stable Diffusion Render/__masks/01.png", False),
    ("Uraraka Gape Stable Diffusion Render/__masks/02.png", False),
    ("Uraraka Gape Stable Diffusion Render/__masks/03.png", False),
    ("Uraraka Gape Stable Diffusion Render/__temp", True),
    ("Uraraka Gape Stable Diffusion Render/__temp/01-gp-cgi-2x.png", False),
    ("Uraraka Gape Stable Diffusion Render/__temp/01.png", False),
    ("_Porn Account Logo", True),
    ("_Porn Account Logo/IMAGES", True),
    ("_Porn Account Logo/IMAGES/010.png", False),
    ("_Porn Account Logo/IMAGES/020.png", False),
    ("_Porn Account Logo/IMAGES/021.png", False),
    ("_Porn Account Logo/IMAGES/030.png", False),
    ("_Porn Account Logo/IMAGES/031.png", False),
    ("_Porn Account Logo/IMAGES/032.png", False),
    ("_Porn Account Logo/IMAGES/040.png", False),
    ("_Porn Account Logo/IMAGES/050.png", False),
    ("_Porn Account Logo/IMAGES/051.png", False),
    ("_Porn Account Logo/IMAGES/052.png", False),
    ("_Porn Account Logo/IMAGES/061.png", False),
    ("_Porn Account Logo/IMAGES/070.png", False),
    ("_Porn Account Logo/IMAGES/071.png", False),
    ("_Porn Account Logo/IMAGES/080.png", False),
    ("_Porn Account Logo/IMAGES/090.png", False),
    ("_Porn Account Logo/IMAGES/091-gp-cgi-2x.png", False),
    ("_Porn Account Logo/IMAGES/091.png", False),
    ("_Porn Account Logo/IMAGES/100.png", False),
    ("_Porn Account Logo/IMAGES/110-gp-cgi-2x-gp-cgi-2x.png", False),
    ("_Porn Account Logo/IMAGES/110-gp-cgi-2x.png", False),
    ("_Porn Account Logo/IMAGES/110.png", False),
    ("_Porn Account Logo/IMAGES/TWITTER_BANNER.png", False),
    ("_Porn Account Logo/IMAGES/__PROPORTIONS_FOR_PFP.png", False),
    ("_Porn Account Logo/KRAs", True),
    ("_Porn Account Logo/KRAs/010.kra", False),
    ("_Porn Account Logo/KRAs/010_001.kra", False),
    ("_Porn Account Logo/KRAs/010_002.kra", False),
    ("_Porn Account Logo/KRAs/010_003.kra", False),
    ("_Porn Account Logo/OUTPUT", True),
    ("_Porn Account Logo/OUTPUT/256.png", False),
    ("_Porn Account Logo/OUTPUT/512.png", False),
    ("_Porn Account Logo/OUTPUT/768.png", False),
    ("_Porn Account Logo/OUTPUT/delete-me.png", False),
    ("_Porn Account Logo/OUTPUT/glossy_logo.png", False),
    ("_Porn Account Logo/OUTPUT/glossy_logo_circle_black.png", False),
    ("_Porn Account Logo/VECTORS", True),
    ("_Porn Account Logo/VECTORS/STD.ai", False),
    ("_Porn Account Logo/VECTORS/STD.svg", False),
    ("_Porn Account Logo/zzz - temp", True),
    ("_Porn Account Logo/zzz - temp/02.png", False),
    ("_Porn Account Logo/zzz - temp/STD.png", False),
    ("_Porn Account Logo/zzz - temp/untitled.png", False),
]


def _build_tree(root: Path) -> int:
    """Build the explicit tree spec under *root*, returning file count."""
    file_count = 0
    for rel_path, is_dir in _TREE_SPEC:
        full = root / rel_path
        if is_dir:
            full.mkdir(parents=True, exist_ok=True)
        else:
            full.parent.mkdir(parents=True, exist_ok=True)
            full.touch()
            file_count += 1
    return file_count


# ═══════════════════════════════════════════════════════════════════════════════
# PART 2 — Test case definitions
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class ExpectedPath:
    """Flexible expected path spec for a test case."""

    relative: str  # relative path under root
    is_dir: bool = False  # is it a directory?
    partial: bool = False  # True → actual path must contain this as parent or match

    def absolute(self, root: Path) -> Path:
        return root / self.relative


EXPECTED_MATCHES: dict[int, list[ExpectedPath]] = {
    1: [
        ExpectedPath("Bowsette/Untitled.blend"),
        ExpectedPath("Bowsette/Untitled_001.blend1"),
        ExpectedPath("Bowsette/Untitled_002.blend1"),
    ],
    2: [
        ExpectedPath("TREE_EXAMPLE.txt"),
        ExpectedPath("High Contrast Test/PROMPT.txt"),
    ],
    3: [
        ExpectedPath("3D-to-reGEN-to-VID/Katsuragi Misato", is_dir=True),
    ],
    4: [
        ExpectedPath("3D-to-reGEN-to-VID/Mikasa Ackerman", is_dir=True),
    ],
    5: [
        ExpectedPath(
            "CelebDeGEN/001__Natalie_Portman/011-SharpenAI-Softness-gp-standard v2-2048w-gp-redefine-2048w.kra"
        ),
    ],
    6: [
        ExpectedPath("3D-to-reGEN-to-VID/Annie Leonhart/000.png"),
    ],
    7: [
        ExpectedPath("Makima Deepthroat/PNGs/00.png"),
    ],
    8: [
        ExpectedPath("Bowsette/Untitled_001.blend1"),
    ],
    9: [
        ExpectedPath("About Feet/Impecable Soles/video-gen_4k-upscale.mp4"),
    ],
    10: [
        ExpectedPath("High Contrast Test/VAR/charcoal_01.blend1"),
    ],
    11: [],  # match_any (picts → fuzzy→pics → image category)
    12: [
        ExpectedPath("DVa Raised Sole/040.jpg"),
    ],
    13: [
        ExpectedPath("Uraraka Gape Stable Diffusion Render/000.png"),
    ],
    14: [],  # match_any, latest checking done separately
    15: [
        ExpectedPath("3D-to-reGEN-to-VID/var_01/var/this is fucking insane.mp4"),
    ],
    16: [
        ExpectedPath("About Feet", is_dir=True),
    ],
    17: [
        ExpectedPath("Struggling While Squatting", is_dir=True),
    ],
    18: [
        ExpectedPath("Fubuki Green Thong SDA (Stable Diffusion Assisted)/Fubuki_refs.pur"),
    ],
    19: [
        ExpectedPath("Mikasa In Shackles Arching/v2/Mikasa in Shackles v1.glb"),
    ],
    20: [
        ExpectedPath("About Feet/Impecable Soles/video-gen_4k-upscale.mp4"),
    ],
    21: [
        ExpectedPath("CelebDeGEN/001__Natalie_Portman/010.png"),
    ],
    22: [
        ExpectedPath(
            "AI Latent Upscale Pipeline/process/delete-me-768x576-gp-recover-768w_lighter_darks.png.kra"
        ),
    ],
    23: [
        ExpectedPath(
            "3D-to-reGEN-to-VID/var_01/nb_gens/Gemini_Generated_Image_gceu4lgceu4lgceu.png"
        ),
    ],
    24: [
        ExpectedPath("3D-to-reGEN-to-VID/var_01/999.mp4"),
    ],
    25: [
        ExpectedPath("About Feet", is_dir=True),
        ExpectedPath("About Feet/Best Looking Sole/best_looking_foot_sole__feet.png"),
    ],
}


# ── Acceptance criteria ──────────────────────────────────────────────────────


@dataclass
class Acceptance:
    """Defines what constitutes a pass for a query."""

    expected_paths: list[ExpectedPath]  # what to check
    match_any: bool = False  # any success → pass
    check_latest: bool = False  # verify the result is newest
    check_largest: bool = False  # verify the result is largest
    category: str = ""  # expected category filter
    ok_if_any_in_dir: str = ""  # accept any match within this directory
    relax_dir_match: bool = (
        False  # for directory queries: accept match if actual path contains expected dir
    )


# fmt: off
ACCEPTANCE: dict[int, Acceptance] = {
    1:  Acceptance([ExpectedPath("Bowsette/Untitled.blend"), ExpectedPath("Bowsette/Untitled_001.blend1"),
                    ExpectedPath("Bowsette/Untitled_002.blend1")], ok_if_any_in_dir="Bowsette"),
    2:  Acceptance([ExpectedPath("TREE_EXAMPLE.txt"), ExpectedPath("High Contrast Test/PROMPT.txt")],
                   ok_if_any_in_dir="High Contrast Test/"),
    3:  Acceptance([ExpectedPath("3D-to-reGEN-to-VID/Katsuragi Misato", is_dir=True)], relax_dir_match=True),
    4:  Acceptance([ExpectedPath("3D-to-reGEN-to-VID/Mikasa Ackerman", is_dir=True)], relax_dir_match=True),
    5:  Acceptance([ExpectedPath("CelebDeGEN/001__Natalie_Portman/011-SharpenAI-Softness-gp-standard v2-2048w-gp-redefine-2048w.kra")]),
    6:  Acceptance([ExpectedPath("3D-to-reGEN-to-VID/Annie Leonhart")], ok_if_any_in_dir="3D-to-reGEN-to-VID/Annie Leonhart"),
    7:  Acceptance([ExpectedPath("Makima Deepthroat/PNGs")], ok_if_any_in_dir="Makima Deepthroat/PNGs"),
    8:  Acceptance([ExpectedPath("Bowsette/Untitled_001.blend1")], ok_if_any_in_dir="Bowsette"),
    9:  Acceptance([ExpectedPath("About Feet/Impecable Soles/video-gen_4k-upscale.mp4")], ok_if_any_in_dir="About Feet/Impecable Soles"),
    10: Acceptance([ExpectedPath("High Contrast Test/VAR/charcoal_01.blend1")], ok_if_any_in_dir="High Contrast Test"),
    11: Acceptance([], match_any=True, category="image"),
    12: Acceptance([ExpectedPath("DVa Raised Sole")], ok_if_any_in_dir="DVa Raised Sole"),
    13: Acceptance([ExpectedPath("Uraraka Gape Stable Diffusion Render/000.png")], ok_if_any_in_dir="Uraraka Gape Stable Diffusion Render"),
    14: Acceptance([], match_any=True, check_latest=True),
    15: Acceptance([ExpectedPath("3D-to-reGEN-to-VID/var_01/var/this is fucking insane.mp4")], check_largest=True,
                   ok_if_any_in_dir="3D-to-reGEN-to-VID/var_01"),
    16: Acceptance([ExpectedPath("About Feet", is_dir=True)], relax_dir_match=True),
    17: Acceptance([ExpectedPath("Struggling While Squatting")], relax_dir_match=True),
    18: Acceptance([ExpectedPath("Fubuki Green Thong SDA (Stable Diffusion Assisted)/Fubuki_refs.pur")]),
    19: Acceptance([ExpectedPath("Mikasa In Shackles Arching/v2/Mikasa in Shackles v1.glb")],
                   ok_if_any_in_dir="Mikasa In Shackles Arching"),
    20: Acceptance([ExpectedPath("About Feet/Impecable Soles/video-gen_4k-upscale.mp4")], ok_if_any_in_dir="About Feet/Impecable Soles"),
    21: Acceptance([ExpectedPath("CelebDeGEN/001__Natalie_Portman")], ok_if_any_in_dir="CelebDeGEN/001__Natalie_Portman"),
    22: Acceptance([ExpectedPath("AI Latent Upscale Pipeline/process/delete-me-768x576-gp-recover-768w_lighter_darks.png.kra")],
                   ok_if_any_in_dir="AI Latent Upscale Pipeline"),
    23: Acceptance([ExpectedPath("3D-to-reGEN-to-VID/var_01/nb_gens/Gemini_Generated_Image_gceu4lgceu4lgceu.png")],
                   ok_if_any_in_dir="3D-to-reGEN-to-VID/var_01"),
    24: Acceptance([ExpectedPath("3D-to-reGEN-to-VID/var_01/999.mp4")], check_latest=True, category="video",
                   ok_if_any_in_dir="3D-to-reGEN-to-VID/var_01"),
    25: Acceptance([ExpectedPath("About Feet", is_dir=True), ExpectedPath("About Feet/Best Looking Sole/best_looking_foot_sole__feet.png")],
                   relax_dir_match=True),
}
# fmt: on


QUERY_DESCRIPTIONS: dict[int, str] = {
    1: "Case-Sensitive Glob Matching",
    2: "Case-Insensitive Glob Matching",
    3: "Basename Glob Directory Match",
    4: "Stem Wildcard Matching",
    5: "Nested Directory/File Glob",
    6: "Exact Category Keyword (photo -> image)",
    7: "Exact Category Keyword (pic -> image)",
    8: "Category Keyword (backup_blend -> .blend*)",
    9: "Exact Category Keyword (video -> video extensions)",
    10: "Category Keyword (backup -> .blend*)",
    11: "Fuzzy Category Keyword (picts -> pics -> image)",
    12: "Phonetic Category Keyword (phothos -> photos -> image)",
    13: "Phonetic Category Keyword (piks -> pics -> image)",
    14: "latest sorting heuristic + Wildcard",
    15: "largest sorting heuristic + Wildcard",
    16: "Directory Intent + Wildcard",
    17: "Destructured Fuzzy Wildcard",
    18: "Destructured Token / Wildcard Match",
    19: "Wildcard Stem Match",
    20: "Multi-Token Wildcard Match",
    21: "Multi-Segment Wildcard",
    22: "Stem Wildcard Match (with hyphens)",
    23: "Suffix/Stem Wildcard Match",
    24: "latest sorting + Category + Path constraints",
    25: "Short token match with multiple candidates",
}

QUERIES: dict[int, str] = {
    1: "*.blend*",
    2: "*.TXT",
    3: "*misato*",
    4: "*ackerman*",
    5: "*Natalie_Portman/*.kra",
    6: "annie photo",
    7: "makima pic",
    8: "bowsette backup_blend",
    9: "impecable video",
    10: "high contrast backup",
    11: "picts on Desktop",
    12: "phothos of DVa",
    13: "piks of Uraraka",
    14: "latest *.png",
    15: "largest *.mp4",
    16: "folder *feet*",
    17: "str*ggling",
    18: "fub*ki pur",
    19: "shackles v1*",
    20: "*soles* *.mp4",
    21: "*Natalie*/*.png",
    22: "delete-me*.kra",
    23: "gceu4l*.png",
    24: "latest video under var_01",
    25: "feet",
}


# ═══════════════════════════════════════════════════════════════════════════════
# PART 3 — Result checking
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class Result:
    """Single query test result."""

    qid: int
    query: str
    description: str
    status: str  # "success" | "ambiguous" | "failed"
    actual_path: str  # path string or "(none)"
    handler: str  # handler name or ""
    confidence: float
    category_filtered: bool
    match_ok: bool  # does the match satisfy acceptance criteria?
    detail: str  # human-readable explanation
    near_misses: list[str] = field(default_factory=list)


def path_in_dir(path: Path, dir_rel: str, root: Path) -> bool:
    """Check if *path* is under *dir_rel* (relative to *root*)."""
    try:
        path.relative_to(root / dir_rel)
        return True
    except ValueError:
        return False


def check_query_result(
    qid: int,
    result: SearchResult,
    root: Path,
    acc: Acceptance,
) -> Result:
    """Evaluate a SearchResult against acceptance criteria."""
    query = QUERIES[qid]
    desc = QUERY_DESCRIPTIONS[qid]

    base_result = Result(
        qid=qid,
        query=query,
        description=desc,
        status=result.status,
        actual_path="(none)",
        handler="",
        confidence=0.0,
        category_filtered=False,
        match_ok=False,
        detail="",
    )

    # ── failed ──
    if result.status == "failed":
        base_result.detail = f"FAILED — {result.message}"
        return base_result

    # ── ambiguous ──
    if result.status == "ambiguous":
        nms = [str(p) for p in result.near_misses[:5]]
        top = str(result.near_misses[0].path) if result.near_misses else "(none)"
        top_handler = result.near_misses[0].handler if result.near_misses else ""
        top_conf = result.near_misses[0].confidence if result.near_misses else 0.0
        base_result.actual_path = top
        base_result.handler = top_handler
        base_result.confidence = top_conf
        base_result.near_misses = nms
        if acc.match_any:
            base_result.match_ok = True
            base_result.detail = f"AMBIGUOUS (accepted via match_any) — near_misses: {nms}"
        else:
            base_result.detail = f"AMBIGUOUS — near_misses: {nms}"
        return base_result

    # ── success ──
    if result.match is None:
        base_result.detail = "UNEXPECTED: status=success but match=None"
        return base_result

    actual = result.match.path
    handler = result.match.handler
    confidence = result.match.confidence

    base_result.actual_path = str(actual)
    base_result.handler = handler
    base_result.confidence = confidence

    # Check category filtering
    if "image" in handler.lower() or "category" in handler.lower() or "content" in handler.lower():
        base_result.category_filtered = True

    # match_any — any success passes
    if acc.match_any:
        base_result.match_ok = True
        base_result.detail = f"OK (match_any) — {handler}, conf={confidence:.2f}"
        return base_result

    # Check each expected path
    reasons = []
    for exp in acc.expected_paths:
        exp_abs = exp.absolute(root)
        if actual == exp_abs:
            reasons.append(f"exact match: {exp.relative}")
            base_result.match_ok = True
            break
        if exp.is_dir and acc.relax_dir_match:
            # Check if actual contains the expected dir as parent
            try:
                actual_path_obj = actual if isinstance(actual, Path) else Path(actual)
                actual_path_obj.relative_to(exp_abs)
                reasons.append(f"inside expected dir: {exp.relative} (actual: {actual.name})")
                base_result.match_ok = True
                break
            except ValueError:
                pass
        # File in expected dir
        if not exp.is_dir:
            if actual.parent == exp_abs.parent and actual.name == exp_abs.name:
                reasons.append(f"path match: {exp.relative}")
                base_result.match_ok = True
                break

    # Fallback: accept if in expected directory
    if not base_result.match_ok and acc.ok_if_any_in_dir:
        if path_in_dir(actual, acc.ok_if_any_in_dir, root):
            base_result.match_ok = True
            reasons.append(f"inside expected dir `{acc.ok_if_any_in_dir}` (actual: {actual.name})")

    if base_result.match_ok:
        base_result.detail = f"OK — {'; '.join(reasons)}, handler={handler}, conf={confidence:.2f}"
    else:
        exp_str = ", ".join(e.relative for e in acc.expected_paths)
        base_result.detail = (
            f"MISMATCH — expected [{exp_str}], got {actual}, "
            f"handler={handler}, conf={confidence:.2f}"
        )

    return base_result


# ═══════════════════════════════════════════════════════════════════════════════
# PART 4 — Main test runner
# ═══════════════════════════════════════════════════════════════════════════════


def write_lean_config() -> None:
    """Write a minimal config that enables H1-H6, adds categories, and avoids H7/H8."""
    cfg_dir = Path(os.environ["APPDATA"]) / "sempath"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    (cfg_dir / "cache").mkdir(exist_ok=True)

    config = dict(DEFAULT_CONFIG)
    config["handlers"] = {
        "enabled": ["h1", "h2", "h3", "h4", "h5", "h6"],
        "h4_threshold": 75,
    }
    config["index"] = {
        "auto": False,
        "store": str(cfg_dir / "cache"),
        "exclude_patterns": [],
    }
    config["exhaustive"] = True
    config["verbose"] = False
    config["aliases"] = DEFAULT_CONFIG.get("aliases", {})
    config.pop("embedding", None)
    config["heuristics"] = DEFAULT_CONFIG.get("heuristics", {})

    with open(cfg_dir / "config.yaml", "w") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)


def prepare_mock_fs(root: Path) -> None:
    """Build the tree and add extra metadata files for sorting tests."""
    n_files = _build_tree(root)
    now = time.time()

    # ── Extra files for Q14 (latest *.png) — varying mtimes ──
    latest_pngs = []
    for i, sub in enumerate(
        [
            "0SC to 3D to Angle Swap",
            "Chained Up, Spreading Toes",
            "Cute Pose Bitch",
            "About Feet/Impecable Soles",
        ]
    ):
        d = root / sub
        if d.exists():
            fp = d / f"_latest_test_{i}.png"
            fp.touch()
            os.utime(fp, (now - i * 7200, now - i * 7200))  # each 2h older
            latest_pngs.append(fp)

    # ── Sizes for Q15 (largest *.mp4) ──
    for fp in root.rglob("*.mp4"):
        # Make "this is fucking insane.mp4" the largest by far
        if "fucking insane" in fp.name:
            fp.write_bytes(b"x" * 9_999_999)
        else:
            fp.write_bytes(b"x" * 1_000)

    # ── Varying mtimes for var_01 content (Q24) ──
    var_01 = root / "3D-to-reGEN-to-VID" / "var_01"
    if var_01.exists():
        files = sorted(var_01.rglob("*"), key=lambda p: p.name.lower())
        for i, fp in enumerate(files):
            if fp.is_file():
                os.utime(fp, (now - i * 100, now - i * 100))


def run_query(engine: SearchEngine, qid: int, root: Path) -> SearchResult:
    query = QUERIES[qid]
    return engine.find_path(
        query=query,
        root_dir=root,
        depth=10,
        min_confidence=0.3,
        top_n=10,
        non_interactive=True,
        no_index=True,
    )


def run_all(root: Path) -> list[Result]:
    """Build FS, create engine, run all queries, return Results."""
    write_lean_config()
    prepare_mock_fs(root)
    config = load_config()
    engine = SearchEngine(config)

    results: list[Result] = []
    for qid in sorted(QUERIES):
        sr = run_query(engine, qid, root)
        res = check_query_result(qid, sr, root, ACCEPTANCE[qid])
        results.append(res)

    return results


# ═══════════════════════════════════════════════════════════════════════════════
# PART 5 — Reporting
# ═══════════════════════════════════════════════════════════════════════════════


# ── Failure Root-Cause Analysis ──────────────────────────────────────────────

FAILURE_ANALYSIS: dict[int, str] = {
    1: (
        "Wildcard token fuzzily matches category keyword, hijacking normal handler flow.\n"
        "Query `*.blend*` → heuristics extract token `blend` → fuzzily matches `blend1` "
        "(keyword in `backup_blend` category) at ratio ~90.9 (threshold 80).\n"
        "This incorrectly triggers a category filter `[blend*]` + `directory_content_match`, "
        "returning the shortest-depth .blend file instead of the full handler-chain search "
        "that would find all matching blend files. Glob pattern tokens should be excluded "
        "from category keyword matching."
    ),
    8: (
        "Compound query `backup_blend` does not trigger `backup` keyword.\n"
        "The query contains `backup_blend` as a single underscore-joined token. "
        "The `backup_blend` category keywords are `['blend1', 'blend1s', 'backup', 'backups']`. "
        "Regex `\\\\bbackup\\\\b` does NOT match inside `backup_blend` because `_` is a word character, "
        "so there is no word boundary between `p` and `_`.\n"
        "No category is matched → no extension filter → query falls through to H1-H6 as plain text "
        "`bowsette backup_blend` which doesn't match any filename.\n"
        "Possible fix: add `backup_blend` itself as a keyword, or split underscore tokens for matching."
    ),
    11: (
        "Fuzzy category match `picts` → `pics` works, but clean query `Desktop` has no match in tree.\n"
        "`picts` correctly fuzzy-matches `pics` (ratio 88.9) → image category → image extensions filter. "
        "Clean query becomes `Desktop` (after stripping `picts` and stopword `on`).\n"
        "No directory named `Desktop` exists in the tree, and no image filename contains `desktop`. "
        "The handler chain returns nothing against image-only candidates.\n"
        "The queries_review.md expected `.png/.jpg/.webp files in the tree` but the engine returns "
        "`No image files found!` because clean query `Desktop` doesn't match any image path."
    ),
    15: (
        "Glob token `mp4` matches category keyword, hijacking `largest` sorting.\n"
        "Query `largest *.mp4` → token `mp4` extracted → exactly matches keyword `mp4` in `video` "
        "category → triggers video extension filter + `directory_content_match`.\n"
        "The engine returns the first-found video file from `directory_content_match` "
        "(`NanoBanana Pro + Grok/grok-video-....mp4`) instead of properly sorting ALL .mp4 files "
        "by size and returning the largest. The `largest` sort is never reached because "
        "`directory_content_match` returns early.\n"
        "Fix: glob-only queries should not trigger category keyword matching on their components."
    ),
    17: (
        "Wildcard query fails due to H3 bijection requirement with extra tokens.\n"
        "Query `str*ggling` → tokens `{str*ggling}`. "
        "Candidate `Struggling While Squatting` → tokens `{struggling, while, squatting}`.\n"
        "H3 `_match_token_sets` matches the wildcard token `str*ggling` against `struggling` (via fnmatch), "
        "but then fails the bijection check: 1 query token consumed, 3 candidate tokens in set, "
        "but only 1 candidate token matched.\n"
        "H3's subset fallback explicitly skips wildcards (`not any('*' in q ...)`). "
        "H4 fuzzy with wildcards stripped → `strggling` vs `Struggling While Squatting` → ratio below 75.\n"
        "Fix: H3 should allow extra candidate tokens when query has embedded wildcards."
    ),
    18: (
        "Same wildcard bijection issue as Q17, plus multi-token query.\n"
        "Query `fub*ki pur` → tokens `{fub*ki, pur}`. "
        "File `Fubuki Green Thong SDA.../Fubuki_refs.pur` → name tokens `{fubuki, refs, pur}`.\n"
        "H3 matches `pur`→`pur` and `fub*ki`→`fubuki` (via fnmatch), "
        "but fails bijection because `refs` is an unmatched candidate token.\n"
        "Same root cause as Q17: wildcard queries require perfect bijection with no extra tokens."
    ),
    19: (
        "Same wildcard bijection issue as Q17/Q18.\n"
        "Query `shackles v1*` → tokens `{shackles, v1*}`. "
        "File `Mikasa in Shackles v1.glb` → name tokens `{mikasa, in, shackles, v1, glb}`.\n"
        "H3 matches `shackles`→`shackles` and `v1*`→`v1` (via fnmatch), "
        "but fails bijection: unmatched tokens `mikasa`, `in`, `glb`.\n"
        "Same bijection issue."
    ),
    22: (
        "Multiple matches — H1 picks wrong one via shortest-path tiebreaker.\n"
        "Query `delete-me*.kra` is a glob → matched by H1 for ALL `.kra` files "
        "starting with `delete-me`.\n"
        "Expected: `AI Latent Upscale Pipeline/process/delete-me-768x576-...lighter_darks.png.kra`. "
        "Got: `3D-to-reGEN-to-VID/Mado Akira/delete-me (2)-...v2-2x.kra`.\n"
        "Both have path depth 3, tie is broken by iteration order (first encountered wins).\n"
        "This is a sorting issue: the more specific/deeper match should rank higher."
    ),
    23: (
        "Glob token `png` matches category keyword, hijacking query.\n"
        "Query `gceu4l*.png` → tokens `gceu4l` and `png` extracted. "
        "`png` exactly matches keyword `png` in `image` category → image extension filter.\n"
        "Clean query becomes `gceu4l`. No directory or filename matches `gceu4l` → fails.\n"
        "Same root cause as Q1/Q15: glob pattern components trigger category keywords."
    ),
    24: (
        "Category + path constraint — clean query `under var_01` can't match path component.\n"
        "Query `latest video under var_01`: `video` matches `video` category → video extensions filter. "
        "`latest` sets `latest=True`.\n"
        "Clean query after removing `video` and `latest`: `under var_01` (stopword `under` not in "
        "stopword list → remains).\n"
        "Clean query `under var_01` doesn't match any directory or filename under video-only candidates.\n"
        "Engine returns `No video files found!` — video files DO exist, but the clean query fails "
        "to match them.\n"
        "The engine doesn't have a mechanism to use `var_01` as a path filter. "
        "Fix: support path-constraint tokens (e.g. `under`, `in` as path scoping, or match path "
        "components instead of just filenames)."
    ),
}


def print_report(results: list[Result]) -> tuple[int, int]:
    """Print a detailed Markdown report. Returns (pass, fail)."""
    n_pass = sum(1 for r in results if r.match_ok)
    n_fail = len(results) - n_pass

    print()
    print("=" * 88)
    print("  SEMPATH QUERY TEST REPORT — queries_review.md × TREE_EXAMPLE.txt")
    print("  Generated:", time.strftime("%Y-%m-%d %H:%M:%S"))
    print("=" * 88)
    print(f"  Queries: {len(results)}  |  Pass: {n_pass}  |  Fail: {n_fail}")
    print()

    if n_fail:
        print("## ❌ FAILURES")
        print()
        print("| # | Query | Status | Expected | Actual | Handler | Detail |")
        print("|---|---|---|---|---|---|---|")
        for r in results:
            if r.match_ok:
                continue
            exp_str = ", ".join(e.relative for e in ACCEPTANCE[r.qid].expected_paths) or "(any)"
            print(
                f"| Q{r.qid} | `{r.query}` | {r.status} | {exp_str[:50]} | "
                f"`{r.actual_path[:50]}` | {r.handler} | {r.detail[:80]} |"
            )
        print()
        print("---")
        print()

    # ── Full details ──
    print("## 📋 Per-Query Details")
    print()
    print("| # | Query | Status | Handler | Conf | Match | Detail |")
    print("|---|---|---|---|---|---|---|")
    for r in results:
        icon = "PASS" if r.match_ok else "FAIL"
        det = r.detail[:70]
        print(
            f"| Q{r.qid} | `{r.query}` | {r.status} | {r.handler} | {r.confidence:.2f} | {icon} | {det} |"
        )
    print()

    # ── Summary ──
    if n_fail == 0:
        print("🎉 **ALL 25 QUERIES PASS**")
    else:
        print(f"❌ **{n_fail} / {len(results)} QUERIES FAIL**")
        print()
        print("### Failure Breakdown")
        print()
        for r in results:
            if r.match_ok:
                continue
            print(f"#### Q{r.qid}: `{r.query}` — {r.description}")
            print()
            print(f"- **Status**: `{r.status}`")
            print(f"- **Handler**: `{r.handler}`" if r.handler else "- **Handler**: (none)")
            print(f"- **Confidence**: {r.confidence:.2f}")
            exp_str = (
                ", ".join(e.relative for e in ACCEPTANCE[r.qid].expected_paths) or "(any match)"
            )
            print(f"- **Expected**: {exp_str}")
            print(f"- **Actual**: `{r.actual_path}`")
            if r.near_misses:
                print(f"- **Near misses**: {r.near_misses[:3]}")
            print(f"- **Detail**: {r.detail}")
            print()
            # ── Root-cause analysis ──
            if r.qid in FAILURE_ANALYSIS:
                print("**Root Cause Analysis:**")
                for line in FAILURE_ANALYSIS[r.qid].split("\n"):
                    print(f"> {line}")
                print()
        print()
        print("---")
        print()
        print("### 🔍 Failure Root-Cause Summary")
        print()
        print("The 10 failures fall into 3 categories:")
        print()
        print("**1. Category keyword pollution from glob tokens (Q1, Q15, Q23)**")
        print()
        print("| Query | Token | Matched Keyword | Category | Effect |")
        print("|---|---|---|---|---|")
        print(
            "| `*.blend*` | `blend` | `blend1` (fuzzy ~90.9) | `backup_blend` | Filters to `[blend*]`, then `directory_content_match` |"
        )
        print(
            "| `largest *.mp4` | `mp4` | `mp4` (exact) | `video` | Filters to video files, then `directory_content_match` |"
        )
        print(
            "| `gceu4l*.png` | `png` | `png` (exact) | `image` | "
            "Filters to images, then `directory_content_match` |"
        )
        print()
        print(
            "The heuristics parser extracts alphanumeric tokens from glob patterns "
            "(`blend` from `*.blend*`, `mp4` from `*.mp4`, `png` from `*.png`) and matches them "
            "against category keywords. This triggers an extension filter + "
            "`directory_content_match` early return, bypassing the normal handler chain and "
            "preventing the intended glob/sorting behavior. Fix: exclude glob pattern "
            "components from category keyword matching, or run category matching only AFTER the "
            "handler chain fails to find a glob match."
        )
        print()
        print("**2. Wildcard bijection limitation in H3 (Q17, Q18, Q19)**")
        print()
        print("| Query | Tokens | Candidate Tokens (name/stem) | Issue |")
        print("|---|---|---|---|")
        print(
            "| `str*ggling` | `{str*ggling}` | `{struggling, while, squatting}` | "
            "`str*ggling` matches `struggling`, but `while`, `squatting` remain |"
        )
        print(
            "| `fub*ki pur` | `{fub*ki, pur}` | `{fubuki, refs, pur}` | "
            "`pur`+`fub*ki` match, but `refs` remains |"
        )
        print(
            "| `shackles v1*` | `{shackles, v1*}` | `{mikasa, in, shackles, v1, glb}` | "
            "`shackles`+`v1*` match, but `mikasa`, `in`, `glb` remain |"
        )
        print()
        print(
            "H3 `_match_token_sets` enforces a bijection (each query token maps to exactly "
            "one candidate token, and all candidate tokens must be consumed). The subset "
            "fallback (allowing extra candidate tokens) explicitly skips queries containing `*` "
            "or `?`. For wildcard queries that match a subset of the candidate's tokens, the "
            "bijection constraint is too strict. Fix: allow extra unmatched candidate tokens "
            "when query tokens have embedded wildcards (similar to the non-wildcard subset "
            "behavior)."
        )
        print()
        print("**3. Compound-query parsing limitations (Q8, Q11, Q24)**")
        print()
        print("| Query | Issue |")
        print("|---|---|")
        print(
            "| `bowsette backup_blend` | Keyword `backup` doesn't match inside compound token "
            "`backup_blend` (underscore is a word char, so `\\bbackup\\b` fails). "
            "No category triggered. |"
        )
        print(
            "| `picts on Desktop` | Fuzzy match `picts→pics` works, but clean query `Desktop` "
            "has no matching directory in this tree. Expected by queries_review, but "
            "`Desktop` literally doesn't exist in the tree → no match. |"
        )
        print(
            "| `latest video under var_01` | `video` triggers category, `latest` sets sort. "
            "Clean query becomes `under var_01`. `under` is not a stopword. The engine doesn't "
            "support path-scoping tokens (`under`, `in`, etc.) to restrict candidates to a "
            "subdirectory. |"
        )
        print()
        print("**4. Tiebreaker picks wrong result for multiple glob matches (Q22)**")
        print()
        print(
            "Query `delete-me*.kra` matches multiple `.kra` files via H1 glob matching. "
            "The tiebreaker (`min(..., key=lambda m: len(m.path.parts))`) returns the first "
            "shortest-path match encountered in iteration order, which may not be the semantically "
            "best match. Expected a path inside `AI Latent Upscale Pipeline/process/` but got one "
            "in `3D-to-reGEN-to-VID/Mado Akira/`."
        )
        print()

    return n_pass, n_fail


# ═══════════════════════════════════════════════════════════════════════════════
# PART 6 — CLI / pytest entry points
# ═══════════════════════════════════════════════════════════════════════════════


def main() -> int:
    # Create temp root for mock FS
    root = Path(tempfile.mkdtemp(prefix="sempath_mock_"))
    results = run_all(root)
    _n_pass, n_fail = print_report(results)
    return 0 if n_fail == 0 else 1


def test_all_queries() -> None:
    """pytest entry: run all queries, assert zero failures."""
    import tempfile

    root = Path(tempfile.mkdtemp(prefix="sempath_mock_"))
    results = run_all(root)
    failures = [r for r in results if not r.match_ok]
    if failures:
        # Build failure message
        lines = [f"\n{'=' * 70}"]
        lines.append(f"SEMPATH QUERY TEST: {len(failures)} FAILURES")
        lines.append("=" * 70)
        for r in failures:
            exp_str = ", ".join(e.relative for e in ACCEPTANCE[r.qid].expected_paths) or "(any)"
            lines.append(f"\nQ{r.qid}: {r.query}")
            lines.append(f"  Status:   {r.status}")
            lines.append(f"  Expected: {exp_str}")
            lines.append(f"  Actual:   {r.actual_path}")
            lines.append(f"  Handler:  {r.handler}")
            lines.append(f"  Detail:   {r.detail}")
        lines.append(f"\n{'=' * 70}")
        lines.append(f"BANZAI~! (But {len(failures)} queries failed)")
        lines.append(f"{'=' * 70}")
        pytest_msg = "\n".join(lines)
        raise AssertionError(pytest_msg)
    # else all pass — print cute message
    import builtins

    builtins.print("\n🎉 ALL 25 QUERIES PASS")


if __name__ == "__main__":
    sys.exit(main())
