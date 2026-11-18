#!/usr/bin/env python3
"""Build the OpenMontage AI drama video prompt library.

Pipeline: load sources -> license allowlist gate -> normalize to schema ->
explicit / IP / promo-word filters -> dedupe -> write data/*.json + ATTRIBUTION.md.

Inputs (all under prompts/library/ in this repository):
  originals/*.txt            OpenMontage original prompts (CC BY 4.0)
  curation/translations_*.txt Chinese translations written by OpenMontage for imported prompts
  sources/                   third-party files fetched at pinned revisions (see SOURCES);
                             not committed, fetch with scripts/fetch_prompt_sources.sh

Outputs:
  studio/config/prompt_library/  prompts.json, by-category/, categories.json, stats.json, schema.json,
                                 plus copies of ATTRIBUTION.md and LICENSES/ (shipped with the studio image)
  prompts/library/ATTRIBUTION.md

Run:  scripts/fetch_prompt_sources.sh && python3 scripts/import_prompts.py [--out DIR]
"""
from __future__ import annotations

import argparse
import csv
import difflib
import hashlib
import json
import re
import sys
from collections import Counter, OrderedDict
from pathlib import Path

csv.field_size_limit(sys.maxsize)

REPO = Path(__file__).resolve().parent.parent
ROOT = REPO / "prompts" / "library"
DATA_OUT = REPO / "studio" / "config" / "prompt_library"
SRC = ROOT / "sources"
CUR = ROOT / "curation"
ORIG = ROOT / "originals"

# ---------------------------------------------------------------- licenses
LICENSE_ALLOWLIST = {"CC0-1.0", "CC-BY-4.0", "MIT", "Apache-2.0"}
LICENSE_DENY_PATTERNS = [r"\bNC\b", r"NonCommercial", r"^unknown$", r"^none$", r"NOASSERTION"]
LICENSE_URLS = {
    "CC0-1.0": "https://creativecommons.org/publicdomain/zero/1.0/",
    "CC-BY-4.0": "https://creativecommons.org/licenses/by/4.0/",
    "MIT": "https://opensource.org/licenses/MIT",
    "Apache-2.0": "https://www.apache.org/licenses/LICENSE-2.0",
}

SOURCES = OrderedDict({
    "openmontage": {
        "name": "OpenMontage",
        "url": "https://github.com/charliewwdev/OpenMontage",
        "license": "CC-BY-4.0",
        "license_evidence": "Original content written for this library; released under CC BY 4.0.",
        "revision": None,
        "author": "OpenMontage",
    },
    "vbench": {
        "name": "Vchitect/VBench prompt suite",
        "url": "https://github.com/Vchitect/VBench/tree/master/prompts",
        "license": "Apache-2.0",
        "license_evidence": "GitHub API license=Apache-2.0; LICENSE file at pinned commit.",
        "revision": "fd18b3d055cb0fc6f066ca90fe2c3c8cbb698490",
        "author": "VBench authors (Vchitect)",
    },
    "lichamnesia": {
        "name": "LichAmnesia/awesome-ad-video-prompts",
        "url": "https://github.com/LichAmnesia/awesome-ad-video-prompts",
        "license": "CC-BY-4.0",
        "license_evidence": "LICENSE file: CC BY 4.0, 'All prompts in this repository are original works'.",
        "revision": "ac5b61177a81343e958f63212c4df7f25dc4c265",
        "author": "awesome-ad-video-prompts contributors",
    },
    "rapidata": {
        "name": "Rapidata/text-2-video-human-preferences-veo3",
        "url": "https://huggingface.co/datasets/Rapidata/text-2-video-human-preferences-veo3",
        "license": "Apache-2.0",
        "license_evidence": "Hugging Face dataset card: license: apache-2.0 (prompt text only; videos not used).",
        "revision": "51fd4dfc8b7ca886328dfb0f95497bd8ec5a19e2",
        "author": "Rapidata",
    },
    "promptschat": {
        "name": "fka/prompts.chat",
        "url": "https://huggingface.co/datasets/fka/prompts.chat",
        "license": "CC0-1.0",
        "license_evidence": "Hugging Face dataset card: license: cc0-1.0.",
        "revision": "be0e61647a60dac415f7639453f351ce1b4ed585",
        "author": "prompts.chat contributors",
    },
})

# Sources we looked at and deliberately excluded (documented in ATTRIBUTION.md).
EXCLUDED_SOURCES = [
    ("songguoxs/awesome-video-prompts", "no license"),
    ("WenhaoWang/VidProM", "CC BY-NC 4.0 (non-commercial)"),
    ("facebookresearch/MovieGenBench", "CC BY-NC 4.0 (non-commercial)"),
    ("Gustavosta/Stable-Diffusion-Prompts", "license unknown"),
    ("YouMind-OpenLab/awesome-seedance-2-prompts, ZeroLu/awesome-seedance", "repo license does not clearly cover third-party creators' prompts"),
    ("ai-boost/awesome-image-video-prompts", "GPL-3.0; kept out to keep the dataset under permissive terms"),
]

# ---------------------------------------------------------------- taxonomy
CATEGORIES = OrderedDict([
    ("actions",    {"zh": "动作写法", "en": "How to write actions", "emoji": "🏃"}),
    ("genres",     {"zh": "短剧题材", "en": "Short-drama genres", "emoji": "🎬"}),
    ("hooks",      {"zh": "钩子与节拍", "en": "Hooks & beats", "emoji": "🪝"}),
    ("camera",     {"zh": "镜头与运镜", "en": "Camera & movement", "emoji": "🎥"}),
    ("lighting",   {"zh": "光影与调色", "en": "Lighting & color", "emoji": "💡"}),
    ("character",  {"zh": "角色三视图与设定", "en": "Character turnarounds & design", "emoji": "👤"}),
    ("storyboard", {"zh": "分镜时序", "en": "Storyboard timing", "emoji": "🗂️"}),
    ("ecommerce",  {"zh": "电商广告", "en": "E-commerce ads", "emoji": "🛍️"}),
    ("platform",   {"zh": "平台爆款结构", "en": "Platform structures", "emoji": "📱"}),
    ("sound",      {"zh": "声音与配音", "en": "Sound & voice", "emoji": "🔊"}),
    ("negative",   {"zh": "约束词", "en": "Constraint words", "emoji": "🚫"}),
])
SUBCATEGORY_LABELS = {
    "actions": {"formula": ("动作公式与原则", "Formulas & principles"), "fighting": ("打斗与武术", "Fighting & martial arts"),
                "chase": ("追逐", "Chases"), "dance": ("舞蹈", "Dance"), "sports": ("运动", "Sports"),
                "everyday": ("日常动作", "Everyday actions"), "emotion": ("情绪表演与微表情", "Emotional acting & micro-expressions"),
                "interaction": ("多人互动", "Multi-person interaction"), "hands-props": ("手部与道具", "Hands & props"),
                "romance": ("浪漫（牵手/拥抱/吻）", "Romance (hands, hugs, kisses)")},
}
MODELS = {"Seedance", "Veo", "Sora", "Kling", "Hailuo", "generic"}
STAGES = {"script", "character", "scene", "prop", "storyboard", "voice", "edit"}

# ---------------------------------------------------------------- filters
EXPLICIT_PATTERNS = [
    r"\bsex", r"\bnud(e|ity)", r"\bnaked", r"\berotic", r"\bporn", r"\blingerie", r"\bseduct", r"\bsensual",
    r"\bsexy\b", r"\bbikini", r"\bbreast", r"\bcleavage", r"\bbuttock", r"\bstrip(per|tease)", r"\bnsfw", r"\bfetish",
    r"\bundress", r"\btopless", r"\bin bed together\b", r"\bmake out\b", r"\bmaking out\b", r"\bshower\b",
    r"性感", r"裸", r"(?<!角)色情", r"(?<![表神])情色", r"床戏", r"擦边", r"内衣", r"比基尼", r"诱惑", r"露骨的", r"挑逗", r"胸部", r"臀", r"脱衣", r"洗澡", r"淋浴",
]
# Allowed phrases that contain a pattern above but are explicitly safe (our own safety guidance).
EXPLICIT_ALLOW = [r"no nudity", r"无暴露", r"非露骨", r"not explicit"]
IP_BRAND_PATTERNS = [
    r"storm ?trooper", r"gwen stacy", r"marvel", r"disney", r"pixar", r"\bhbo\b", r"netflix", r"pok[eé]mon", r"lego",
    r"chucky", r"jpmorgan", r"star wars", r"spider-?man", r"batman", r"harry potter", r"漫威", r"迪士尼", r"冲锋队",
]
OTHER_EXCLUDE = [r"\bsmoking\b", r"\bcigarette", r"\bbeer\b", r"抽烟", r"啤酒", r"\bgore\b(?! *[,.]? *no)", r"\bblood(?!line)"]
# Promo-word lint (project rule): never describe anything with these words.
BANNED_PROMO = [r"免费", r"从零", r"零成本", r"\bfree\b", r"from scratch", r"no subscription", r"calesthio"]


def _hits(patterns, text):
    return [p for p in patterns if re.search(p, text, flags=re.I)]


def check_explicit(text):
    t = text
    for a in EXPLICIT_ALLOW:
        t = re.sub(a, " ", t, flags=re.I)
    return _hits(EXPLICIT_PATTERNS, t)


def norm(s: str) -> str:
    s = s.lower()
    s = re.sub(r"[\s\W_]+", "", s, flags=re.U)
    return s


# ---------------------------------------------------------------- parsers
HEADER_RE = re.compile(r"^##\s+(.*)$")


def parse_blocks(path: Path):
    """Parse '## a | b | ...' header + 'ZH:'/'EN:' lines."""
    blocks, cur = [], None
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.rstrip()
        if line.startswith("# ") or not line.strip():
            continue
        m = HEADER_RE.match(line)
        if m:
            cur = {"fields": [f.strip() for f in m.group(1).split("|")], "zh": "", "en": ""}
            blocks.append(cur)
        elif line.startswith("ZH:") and cur is not None:
            cur["zh"] = line[3:].strip()
        elif line.startswith("EN:") and cur is not None:
            cur["en"] = line[3:].strip()
        else:
            raise ValueError(f"{path.name}: unexpected line: {line[:80]}")
    return blocks


def split_cat(s):
    cat, _, sub = s.partition("/")
    return cat.strip(), sub.strip() or None


def tags_of(s):
    return [t.strip() for t in re.split(r"[,，]", s) if t.strip()]


def make_entry(*, id, title_zh, title_en, prompt_zh, prompt_en, model, category, subcategory, stage, tags,
               source_key, original_ref=None, modified=False, translated="none", lang_origin="zh"):
    src = SOURCES[source_key]
    lic = src["license"]
    if source_key == "openmontage":
        attribution = f"© OpenMontage, {lic.replace('-', ' ')}"
    else:
        attribution = f"Prompt from {src['name']} by {src['author']}, licensed {lic}"
        if translated != "none":
            attribution += "; Chinese translation by OpenMontage (AI-assisted)"
        if modified:
            attribution += "; modified"
    return OrderedDict(
        id=id,
        title={"zh": title_zh, "en": title_en},
        prompt_zh=prompt_zh,
        prompt_en=prompt_en,
        model=model,
        category=category,
        subcategory=subcategory,
        stage=stage,
        tags=tags,
        preview=None,
        source=OrderedDict(name=src["name"], url=src["url"], revision=src["revision"], ref=original_ref),
        license=lic,
        license_url=LICENSE_URLS[lic],
        attribution=attribution,
        lang_origin=lang_origin,
        translated=translated,
        modified=modified,
    )


def load_originals():
    out = []
    for f in sorted(ORIG.glob("*.txt")):
        for b in parse_blocks(f):
            fid, tzh, ten, model, catsub, stage, tags = b["fields"]
            cat, sub = split_cat(catsub)
            out.append(make_entry(id=fid, title_zh=tzh, title_en=ten, prompt_zh=b["zh"], prompt_en=b["en"], model=model,
                                  category=cat, subcategory=sub, stage=stage, tags=tags_of(tags) + ["原创"],
                                  source_key="openmontage", lang_origin="zh"))
    return out


def load_translations(name):
    res = {}
    for b in parse_blocks(CUR / name):
        f = b["fields"]
        if len(f) == 5:
            key, tzh, catsub, stage, tags = f
            ten = None
        else:
            key, tzh, ten, catsub, stage, tags = f
        res[key] = dict(title_zh=tzh, title_en=ten, catsub=catsub, stage=stage, tags=tags_of(tags), zh=b["zh"])
    return res


def load_lichamnesia():
    data = json.loads((SRC / "lich_prompts.json").read_text())
    by_slug = {p["slug"]: (s, p) for s in data["sections"] for p in s["prompts"]}
    tr = load_translations("translations_lich.txt")
    out = []
    for i, (slug, t) in enumerate(tr.items(), 1):
        s, p = by_slug[slug]
        cat, sub = split_cat(t["catsub"])
        out.append(make_entry(id=f"lich-{slug}", title_zh=t["title_zh"], title_en=p["title"], prompt_zh=t["zh"],
                              prompt_en=p["prompt"], model="generic", category=cat, subcategory=sub, stage=t["stage"],
                              tags=t["tags"] + [p.get("aspect", ""), p.get("duration", "")], source_key="lichamnesia",
                              original_ref=f"prompts.json › {s['key']} › {slug}", translated="machine", lang_origin="en"))
    return out


def load_rapidata():
    import pandas as pd  # requires pyarrow
    prompts = pd.read_parquet(SRC / "rapidata.parquet")["prompt"].drop_duplicates().tolist()
    tr = load_translations("translations_rapidata.txt")
    out = []
    for i, (key, t) in enumerate(tr.items(), 1):
        match = [p for p in prompts if p.startswith(key)]
        if len(match) != 1:
            raise ValueError(f"rapidata key not unique: {key}")
        cat, sub = split_cat(t["catsub"])
        out.append(make_entry(id=f"rapidata-{i:03d}", title_zh=t["title_zh"], title_en=t["title_en"], prompt_zh=t["zh"],
                              prompt_en=match[0], model="generic", category=cat, subcategory=sub, stage=t["stage"],
                              tags=t["tags"], source_key="rapidata", original_ref="data/train-00000-of-00001.parquet › prompt",
                              translated="machine", lang_origin="en"))
    return out


def load_promptschat():
    rows = {r["act"]: r for r in csv.DictReader((SRC / "promptschat.csv").open(encoding="utf-8"))}
    tr = load_translations("translations_promptschat.txt")
    out = []
    for i, (key, t) in enumerate(tr.items(), 1):
        r = rows[key]
        cat, sub = split_cat(t["catsub"])
        e = make_entry(id=f"promptschat-{i:03d}", title_zh=t["title_zh"], title_en=t["title_en"], prompt_zh=t["zh"],
                       prompt_en=r["prompt"].strip(), model="generic", category=cat, subcategory=sub, stage=t["stage"],
                       tags=t["tags"], source_key="promptschat", original_ref=f"prompts.csv › act='{key}'",
                       translated="machine", lang_origin="en")
        if r.get("contributor"):
            e["attribution"] += f" (contributor: {r['contributor']})"
        out.append(e)
    return out


VBENCH_ACTION_SUB = {
    "sports": ["riding a bike", "roller skating", "skateboarding", "dunking basketball", "skydiving", "shooting goal",
               "canoeing", "shooting basketball", "push up", "frisbee", "squat", "rock climbing", "hula hooping",
               "bungee jumping", "jogging", "motorcycling", "doing aerobics", "archery", "baseball", "ice skating",
               "climbing a rope", "running on treadmill", "sailing", "horse", "stretching leg", "bending back",
               "throwing axe", "riding scooter", "flying kite"],
    "fighting": ["wrestling", "sword fighting", "tai chi"],
    "dance": ["robot dancing", "dancing ballet", "cheerleading", "marching", "air drumming"],
    "emotion": ["laughing", "crying", "shaking head", "clapping", "finger snapping"],
    "interaction": ["shaking hands", "giving or receiving award", "rock scissors paper", "playing chess",
                    "getting a haircut", "massaging legs"],
    "romance": ["hugging", "kissing"],
    "hands-props": ["drawing", "playing harp", "playing flute", "playing piano", "playing trumpet", "playing controller",
                    "strumming guitar", "clay pottery", "shuffling cards", "sharpening knives", "writing", "knitting",
                    "arranging flowers", "bending metal", "counting money", "peeling apples", "cutting watermelon",
                    "bandaging", "filling eyebrows", "tying tie"],
}
VBENCH_ACTION_SKIP = ["smoking", "taking a shower", "tasting beer", "petting animal", "sticking tongue out"]
CAMERA_OPS = OrderedDict([
    ("zoom in", ("推镜头", "Zoom in", "push")), ("zoom out", ("拉镜头", "Zoom out", "pull")),
    ("pan left", ("向左摇/移", "Pan left", "pan")), ("pan right", ("向右摇/移", "Pan right", "pan")),
    ("tilt up", ("上摇", "Tilt up", "tilt")), ("tilt down", ("下摇", "Tilt down", "tilt")),
    ("intense shaking", ("剧烈抖动", "Intense shake", "handheld")), ("steady and smooth", ("稳定平滑", "Steady and smooth", "stabilized")),
    ("racking focus", ("移焦", "Rack focus", "rack-focus")), ("super slow motion", ("超级慢动作", "Super slow motion", "slow-motion")),
])
CAMERA_SCENES = [("A couple in formal evening wear", "雨夜情侣", "Couple in the rain"),
                 ("A beautiful coastal beach", "春日海滩", "Spring beach"),
                 ("The bund Shanghai", "上海外滩", "The Bund, Shanghai")]
STYLE_SCENE = ("A couple in formal evening wear", "雨夜情侣", "Couple in the rain")


def load_vbench():
    en = (SRC / "vbench_all_dimension.txt").read_text(encoding="utf-8").splitlines()
    zh = (SRC / "vbench_all_dimension_cn.txt").read_text(encoding="utf-8").splitlines()
    assert len(en) == len(zh), "VBench en/zh files not aligned"
    pairs = list(zip(en, zh))
    actions = set((SRC / "vb_en_human_action.txt").read_text().splitlines())
    temporal = set((SRC / "vb_en_temporal_style.txt").read_text().splitlines())
    styles = set((SRC / "vb_en_appearance_style.txt").read_text().splitlines())
    out, seen = [], set()
    n_act = n_cam = n_sty = 0
    for idx, (e, z) in enumerate(pairs, 1):
        if e in seen:
            continue
        ref = f"prompts/all_dimension.txt line {idx} (+ all_dimension_cn.txt)"
        if e in actions:
            verb = e.replace("A person is ", "")
            if any(s in verb for s in VBENCH_ACTION_SKIP):
                continue
            sub = next((k for k, v in VBENCH_ACTION_SUB.items() if any(x in verb for x in v)), "everyday")
            n_act += 1
            seen.add(e)
            zverb = z.replace("一个人在", "")
            out.append(make_entry(id=f"vbench-act-{n_act:03d}", title_zh=f"基础动作·{zverb}", title_en=f"Basic action: {verb}",
                                  prompt_zh=z, prompt_en=e, model="generic", category="actions", subcategory=sub,
                                  stage="storyboard", tags=["基础例句", "VBench", "单人动作"], source_key="vbench",
                                  original_ref=ref, lang_origin="en"))
        elif e in temporal:
            scene = next((s for s in CAMERA_SCENES if e.startswith(s[0])), None)
            op = next((v for k, v in CAMERA_OPS.items() if k in e), None)
            if not scene or not op:
                continue
            n_cam += 1
            seen.add(e)
            out.append(make_entry(id=f"vbench-cam-{n_cam:03d}", title_zh=f"基础运镜·{op[0]}（{scene[1]}）",
                                  title_en=f"Basic camera move: {op[1]} ({scene[2]})", prompt_zh=z, prompt_en=e,
                                  model="generic", category="camera", subcategory=op[2], stage="storyboard",
                                  tags=["基础例句", "VBench", op[0]], source_key="vbench", original_ref=ref, lang_origin="en"))
        elif e in styles and e.startswith(STYLE_SCENE[0]):
            n_sty += 1
            seen.add(e)
            style_zh = z.split("，")[-1]
            style_en = e.split(", ")[-1] if ", " in e else e
            out.append(make_entry(id=f"vbench-style-{n_sty:03d}", title_zh=f"风格对照·{style_zh}（{STYLE_SCENE[1]}）",
                                  title_en=f"Style comparison: {style_en} ({STYLE_SCENE[2]})", prompt_zh=z, prompt_en=e,
                                  model="generic", category="lighting", subcategory="style", stage="storyboard",
                                  tags=["基础例句", "VBench", "风格"], source_key="vbench", original_ref=ref, lang_origin="en"))
    return out


# ---------------------------------------------------------------- build
def validate(e):
    errs = []
    for k in ("id", "prompt_zh", "prompt_en", "model", "category", "stage", "license", "attribution"):
        if not e.get(k):
            errs.append(f"missing {k}")
    if not e["title"]["zh"] or not e["title"]["en"]:
        errs.append("missing title")
    if e["model"] not in MODELS:
        errs.append(f"bad model {e['model']}")
    if e["category"] not in CATEGORIES:
        errs.append(f"bad category {e['category']}")
    if e["stage"] not in STAGES:
        errs.append(f"bad stage {e['stage']}")
    if e["license"] not in LICENSE_ALLOWLIST:
        errs.append(f"license not allowed {e['license']}")
    if e["preview"] is not None and not str(e["preview"]).startswith("http"):
        errs.append("preview must be a URL or null")
    return errs


def license_gate():
    for k, s in SOURCES.items():
        lic = s["license"]
        if lic not in LICENSE_ALLOWLIST or any(re.search(p, lic, re.I) for p in LICENSE_DENY_PATTERNS):
            raise SystemExit(f"Source {k} has non-allowlisted license {lic}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(DATA_OUT))
    ap.add_argument("--attribution", default=str(ROOT / "ATTRIBUTION.md"))
    args = ap.parse_args()
    out_dir = Path(args.out)
    license_gate()

    loaders = [("openmontage", load_originals), ("lichamnesia", load_lichamnesia), ("rapidata", load_rapidata),
               ("promptschat", load_promptschat), ("vbench", load_vbench)]
    candidates = []
    for key, fn in loaders:
        items = fn()
        print(f"loaded {len(items):4d} from {key}")
        candidates.extend(items)

    kept, rejected = [], []
    seen_hash, seen_ids = {}, set()
    for e in candidates:
        is_orig = e["source"]["name"] == "OpenMontage"
        text = " ".join([e["title"]["zh"], e["title"]["en"], e["prompt_zh"], e["prompt_en"]])
        reasons = []
        errs = validate(e)
        if errs:
            reasons += errs
        if e["id"] in seen_ids:
            reasons.append("duplicate id")
        hx = check_explicit(text)
        if hx:
            reasons.append(f"explicit filter: {hx}")
        hi = _hits(IP_BRAND_PATTERNS, text)
        if hi:
            reasons.append(f"IP/brand filter: {hi}")
        ho = _hits(OTHER_EXCLUDE, text) if not is_orig else []
        if ho:
            reasons.append(f"content filter: {ho}")
        hp = _hits(BANNED_PROMO, text)
        if hp:
            reasons.append(f"banned promo word: {hp}")
        h = hashlib.sha1((norm(e["prompt_en"]) + "|" + norm(e["prompt_zh"])).encode()).hexdigest()
        if h in seen_hash:
            reasons.append(f"exact duplicate of {seen_hash[h]}")
        if not reasons:
            # near-duplicate check within category (English text)
            ne = norm(e["prompt_en"])
            for k in kept:
                if k["category"] == e["category"] and difflib.SequenceMatcher(None, ne, norm(k["prompt_en"])).quick_ratio() > 0.97:
                    if difflib.SequenceMatcher(None, ne, norm(k["prompt_en"])).ratio() > 0.95:
                        reasons.append(f"near duplicate of {k['id']}")
                        break
        if reasons:
            if is_orig and not any(r.startswith("near duplicate") for r in reasons):
                raise SystemExit(f"Original entry {e['id']} failed checks: {reasons}")
            rejected.append({"id": e["id"], "reasons": reasons, "prompt_en": e["prompt_en"][:160]})
            continue
        seen_hash[h] = e["id"]
        seen_ids.add(e["id"])
        kept.append(e)

    # order: category order, then originals first
    order = {c: i for i, c in enumerate(CATEGORIES)}
    kept.sort(key=lambda e: (order[e["category"]], e["subcategory"] or "", e["source"]["name"] != "OpenMontage", e["id"]))

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "by-category").mkdir(exist_ok=True)
    (out_dir / "prompts.json").write_text(json.dumps(kept, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    cat_counts = Counter(e["category"] for e in kept)
    sub_counts = Counter((e["category"], e["subcategory"]) for e in kept)
    for c in CATEGORIES:
        items = [e for e in kept if e["category"] == c]
        (out_dir / "by-category" / f"{c}.json").write_text(json.dumps(items, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    cats = []
    for c, lab in CATEGORIES.items():
        subs = sorted({e["subcategory"] for e in kept if e["category"] == c and e["subcategory"]})
        cats.append(OrderedDict(key=c, emoji=lab["emoji"], zh=lab["zh"], en=lab["en"], count=cat_counts[c],
                                subcategories=[OrderedDict(key=s, count=sub_counts[(c, s)],
                                                           zh=SUBCATEGORY_LABELS.get(c, {}).get(s, (None, None))[0],
                                                           en=SUBCATEGORY_LABELS.get(c, {}).get(s, (None, None))[1]) for s in subs]))
    (out_dir / "categories.json").write_text(json.dumps(cats, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    stats = OrderedDict(total=len(kept), rejected=len(rejected),
                        by_category=OrderedDict((c, cat_counts[c]) for c in CATEGORIES),
                        by_source=OrderedDict(Counter(e["source"]["name"] for e in kept).most_common()),
                        by_license=OrderedDict(Counter(e["license"] for e in kept).most_common()),
                        by_model=OrderedDict(Counter(e["model"] for e in kept).most_common()))
    (out_dir / "stats.json").write_text(json.dumps(stats, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out_dir / "schema.json").write_text(json.dumps(SCHEMA, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (ROOT / "curation" / "rejected.json").write_text(json.dumps(rejected, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    attribution = build_attribution(kept)
    Path(args.attribution).write_text(attribution, encoding="utf-8")
    # Ship the attribution and license texts next to the data the studio serves.
    (out_dir / "ATTRIBUTION.md").write_text(attribution, encoding="utf-8")
    lic_out = out_dir / "LICENSES"
    lic_out.mkdir(exist_ok=True)
    for lic in sorted((ROOT / "LICENSES").glob("*.txt")):
        (lic_out / lic.name).write_bytes(lic.read_bytes())
    print(json.dumps(stats, ensure_ascii=False, indent=2))


def build_attribution(kept):
    L = ["# ATTRIBUTION / 署名与许可", "",
         "提示词库中的原创条目（`source.name` 为 `OpenMontage`）以 **CC BY 4.0** 发布；OpenMontage 代码本身仍按仓库根目录的 AGPL-3.0 `LICENSE` 授权。",
         "第三方提示词保留其原始许可，下表逐条列出来源、许可与改动说明。中文翻译由 OpenMontage 完成，标注为 `translated: machine`（AI 辅助翻译）。",
         "", "Original prompt entries (source `OpenMontage`) are released under **CC BY 4.0**; the OpenMontage code itself stays under the AGPL-3.0 `LICENSE` at the repository root.",
         "Third-party prompts keep their original licenses. Every imported entry is listed below with its source, license and changes.",
         "Chinese translations of English-only prompts were written by OpenMontage (`translated: machine`, AI-assisted). No third-party media is rehosted.", "",
         "## Sources / 来源", "", "| Source | License | Revision | Entries | License evidence |", "|---|---|---|---|---|"]
    cnt = Counter(e["source"]["name"] for e in kept)
    for k, s in SOURCES.items():
        rev = s["revision"][:12] if s["revision"] else "—"
        L.append(f"| [{s['name']}]({s['url']}) | [{s['license']}]({LICENSE_URLS[s['license']]}) | `{rev}` | {cnt.get(s['name'], 0)} | {s['license_evidence']} |")
    L += ["", "Apache-2.0 sources (VBench, Rapidata): a copy of the Apache License 2.0 is in `LICENSES/Apache-2.0.txt`. "
          "VBench prompts are used verbatim (English and the official Chinese version). Rapidata prompts are used verbatim with an added Chinese translation; "
          "the Rapidata videos are not included.", "",
          "License texts / 许可全文: `LICENSES/Apache-2.0.txt` (Apache License 2.0, identical to the VBench `LICENSE` at the pinned commit), "
          "`LICENSES/CC-BY-4.0.txt` (CC BY 4.0 legal code), `LICENSES/awesome-ad-video-prompts-LICENSE.txt` (the LichAmnesia/awesome-ad-video-prompts "
          "`LICENSE` file, kept verbatim), `LICENSES/CC0-1.0.txt` (CC0 1.0).", "",
          "## Not imported / 未收录的来源", ""]
    for n, why in EXCLUDED_SOURCES:
        L.append(f"- {n}: {why}")
    L += ["", "## Per-entry list / 逐条清单", "", "| id | Source | Original reference | License | Changes |", "|---|---|---|---|---|"]
    for e in kept:
        if e["source"]["name"] == "OpenMontage":
            continue
        ch = []
        if e["translated"] != "none":
            ch.append("Chinese translation added")
        if e["modified"]:
            ch.append("modified")
        L.append(f"| `{e['id']}` | {e['source']['name']} | {e['source']['ref'] or ''} | {e['license']} | {', '.join(ch) or 'verbatim'} |")
    L.append("")
    return "\n".join(L)


SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "AI drama video prompt",
    "type": "object",
    "required": ["id", "title", "prompt_zh", "prompt_en", "model", "category", "stage", "tags", "source", "license", "attribution"],
    "properties": {
        "id": {"type": "string"},
        "title": {"type": "object", "required": ["zh", "en"], "properties": {"zh": {"type": "string"}, "en": {"type": "string"}}},
        "prompt_zh": {"type": "string"},
        "prompt_en": {"type": "string"},
        "model": {"enum": sorted(MODELS)},
        "category": {"enum": list(CATEGORIES)},
        "subcategory": {"type": ["string", "null"]},
        "stage": {"enum": sorted(STAGES)},
        "tags": {"type": "array", "items": {"type": "string"}},
        "preview": {"type": ["string", "null"], "description": "Optional URL to a preview hosted by the rights holder or generated by OpenMontage. Never rehost third-party media."},
        "source": {"type": "object", "properties": {"name": {"type": "string"}, "url": {"type": "string"}, "revision": {"type": ["string", "null"]}, "ref": {"type": ["string", "null"]}}},
        "license": {"enum": sorted(LICENSE_ALLOWLIST)},
        "license_url": {"type": "string"},
        "attribution": {"type": "string"},
        "lang_origin": {"enum": ["zh", "en"]},
        "translated": {"enum": ["none", "human", "machine"]},
        "modified": {"type": "boolean"},
    },
}

if __name__ == "__main__":
    main()
