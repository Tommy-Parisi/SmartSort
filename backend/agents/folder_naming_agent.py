import os
import re
import json
import math
import hashlib
from collections import Counter, defaultdict
from typing import Dict, List, Tuple

from ..core.models import ClusteredFile
from ..core.utils import log_error
from .identity_utils import clean_filename

CACHE_PATH = "folder_name_cache.json"

STOPWORDS = {
    "the","a","an","and","or","but","for","nor","on","in","to","of","at","by","from",
    "with","as","is","are","was","were","be","been","being","that","this","these","those",
    "it","its","if","then","else","when","while","do","does","did","done","not","no",
    "into","about","over","under","between","per","via","vs","vs.","&"
}

PROFANITY = {"fuck","shit","bitch","asshole","dick","bastard","queef","cunt","faggot"}

UNSAFE_FS_CHARS = r'[:<>"/\\|?*\n\r\t]'

# Words that add noise to folder labels
_TOO_GENERIC = {
    "document","notes","file","draft","final","copy","new","updated","version",
    "untitled","unnamed","sample","test","temp","tmp","data","backup","old",
}

ALWAYS_STRIP = {
    "google", "docs", "sheets", "slides", "microsoft", "word", "excel",
    "pdf", "docx", "file", "document", "documents", "new", "copy", "final",
    "draft", "version", "untitled", "readme", "index", "main",
    "page", "pages", "http", "https", "www", "com", "org", "edu",
    "img", "image", "images", "photo", "scanned", "scan", "screenshot",
    "jpeg", "jpg", "png", "heic", "gif", "svg", "webp",
    "series",
    # Camera-roll and device prefixes — never meaningful folder-name words
    "dsc", "dscn", "dcim", "pic", "pxl", "cam", "mvimg", "pano",
    "vlcsnap", "burst", "live", "vid", "clip", "received", "capture",
    "snapshot", "signal",
}


EXTENSION_LABELS = {
    "pdf": "documents",
    "doc": "documents",
    "docx": "documents",
    "txt": "documents",
    "md": "documents",
    "markdown": "documents",
    "rst": "documents",
    "ppt": "slides",
    "pptx": "slides",
    "csv": "sheets",
    "xls": "sheets",
    "xlsx": "sheets",
    "jpg": "images",
    "jpeg": "images",
    "png": "images",
    "heic": "images",
    "heif": "images",
}

TOKEN_RE = re.compile(r"[A-Za-z0-9]+(?:[''][A-Za-z0-9]+)?")
NUM_RE = re.compile(r"^\d+$")
# Structural tokens followed by a number (page3, side1, slide2, fig4, ch3, sec2, vol1, step5)
# — these describe position in a series, not content, and make terrible folder names.
_STRUCTURAL_NUM_RE = re.compile(
    r'^(page|pg|side|part|sheet|slide|fig|figure|ch|chapter|sec|section|vol|step)\d+$',
    re.IGNORECASE,
)


# ── Text helpers ──────────────────────────────────────────────────────────────

def _safe_title_case(words: List[str]) -> str:
    def cap(w: str) -> str:
        return w.upper() if w.isupper() and len(w) <= 4 else w.capitalize()
    return " ".join(cap(w) for w in words)


def _sanitize_label(label: str, max_words: int = 4, max_len: int = 60) -> str:
    label = re.sub(UNSAFE_FS_CHARS, " ", label)
    label = re.sub(r"\s+", " ", label).strip()
    words = [w for w in label.split() if w.lower() not in PROFANITY]
    words = words[:max_words]
    label = _safe_title_case(words)
    if len(label) > max_len:
        label = label[:max_len].rstrip()
    return label or "Cluster"


def _extract_text_fields(f: ClusteredFile) -> Tuple[str, str]:
    """Return (filename_stem, extracted_body) for TF-IDF scoring."""
    stem = clean_filename(os.path.splitext(f.file_meta.file_name)[0])
    # Normalise separators so "canvas_calendar_doc" → individual tokens
    stem = re.sub(r"[_\-.]", " ", stem)
    body = (f.raw_text or "").strip()
    return stem, body


def _clean_filename_stem(file_name: str) -> str:
    stem = clean_filename(os.path.splitext(file_name)[0])
    return re.sub(r"[_\-.]", " ", stem)


def _tokens(text: str) -> List[str]:
    toks = []
    for m in TOKEN_RE.finditer(text.lower()):
        w = m.group(0)
        if w in STOPWORDS:
            continue
        if NUM_RE.match(w):
            continue
        if len(w) <= 2:
            continue
        if _STRUCTURAL_NUM_RE.match(w):
            continue
        toks.append(w)
    return toks


def _ngrams(tokens: List[str], n: int) -> List[Tuple[str, ...]]:
    return [tuple(tokens[i:i+n]) for i in range(len(tokens) - n + 1)]


def is_filename_proper_noun(token: str, filenames: List[str]) -> bool:
    """True if the token appears in only one filename, is capitalised there, and is long enough
    to be a document title word rather than a shared subject keyword."""
    if len(token) <= 3:
        return False
    appearances = 0
    capitalized_match = False
    token_lower = token.lower()
    for filename in filenames:
        parts = re.findall(r"[A-Za-z0-9]+", filename)
        if any(part.lower() == token_lower for part in parts):
            appearances += 1
            if any(part.lower() == token_lower and part[:1].isupper() for part in parts):
                capitalized_match = True
    return appearances <= 1 and capitalized_match


def _strip_label_noise(words: List[str], filenames: List[str]) -> List[str]:
    cleaned: List[str] = []
    for word in words:
        if word.lower() in ALWAYS_STRIP:
            continue
        if is_filename_proper_noun(word, filenames):
            continue
        cleaned.append(word)
    return cleaned


def _image_filename_has_useful_tokens(file_name: str) -> bool:
    """True if the filename would contribute at least one useful token to the naming pipeline."""
    stem = clean_filename(os.path.splitext(file_name)[0])
    stem_normalized = re.sub(r"[_\-.]", " ", stem)
    return any(w not in ALWAYS_STRIP for w in _tokens(stem_normalized))


def _is_all_images_no_semantic_names(files: List[ClusteredFile]) -> bool:
    """True when every file is an image whose filename contributes no useful naming tokens.
    Uses the same token filter as the naming pipeline so the two are guaranteed consistent."""
    if not files:
        return False
    return all(
        f.file_meta.detected_type == "image"
        and not _image_filename_has_useful_tokens(f.file_meta.file_name)
        for f in files
    )


def _dominant_extension(files: List[ClusteredFile]) -> str:
    extensions = [
        os.path.splitext(f.file_meta.file_name)[1].lstrip(".").lower()
        for f in files
        if os.path.splitext(f.file_meta.file_name)[1]
    ]
    if not extensions:
        return "files"
    dominant = Counter(extensions).most_common(1)[0][0]
    return EXTENSION_LABELS.get(dominant, dominant)


def _score_candidates(examples: List[ClusteredFile]) -> List[Tuple[Tuple[str, ...], float]]:
    """TF-IDF over unigrams/bigrams/trigrams; filename tokens weighted 2x."""
    docs_uni, docs_bi, docs_tri = [], [], []

    for f in examples:
        meta, body = _extract_text_fields(f)
        meta_toks = _tokens(meta)
        body_toks = _tokens(body)
        tokens = meta_toks * 2 + body_toks   # filename upweighted

        docs_uni.append(Counter(tokens))
        docs_bi.append(Counter(_ngrams(tokens, 2)))
        docs_tri.append(Counter(_ngrams(tokens, 3)))

    def tf_idf(doc_list: List[Counter]) -> Dict:
        N = len(doc_list)
        df: Dict = defaultdict(int)
        for c in doc_list:
            for k in c:
                df[k] += 1
        scores: Dict = {}
        for c in doc_list:
            for k, tf in c.items():
                idf = math.log((N + 1) / (df[k] + 0.5)) + 1.0
                scores[k] = scores.get(k, 0.0) + tf * idf
        return scores

    uni_scores = tf_idf(docs_uni)
    bi_scores = tf_idf(docs_bi)
    tri_scores = tf_idf(docs_tri)

    def uni_boost(ng: Tuple[str, ...]) -> float:
        return sum(uni_scores.get(w, 0.0) for w in ng)

    combined: Dict = {}
    for ng, s in bi_scores.items():
        combined[ng] = combined.get(ng, 0.0) + s + 0.15 * uni_boost(ng)
    for ng, s in tri_scores.items():
        combined[ng] = combined.get(ng, 0.0) + 1.35 * s + 0.20 * uni_boost(ng)

    def ok(ng: Tuple[str, ...]) -> bool:
        if not ng:
            return False
        if any(w in PROFANITY for w in ng):
            return False
        if all(NUM_RE.match(w) for w in ng):
            return False
        if any(w in _TOO_GENERIC for w in ng):
            return False
        return True

    ranked = [(ng, sc) for ng, sc in combined.items() if ok(ng)]
    ranked.sort(key=lambda x: x[1], reverse=True)
    return ranked


def _choose_label_from_ranked(ranked: List[Tuple[Tuple[str, ...], float]], files: List[ClusteredFile]) -> str:
    filenames = [_clean_filename_stem(f.file_meta.file_name) for f in files]
    for ng, _ in ranked[:50]:
        words = list(ng)
        # Remove non-adjacent duplicates ("Lecture Fall Lecture" → "Lecture Fall")
        seen: List[str] = []
        for w in words:
            if w not in seen:
                seen.append(w)
        candidate_words = _strip_label_noise(seen, filenames)
        if not candidate_words:
            continue
        if len(candidate_words) < 2:
            fallback = _sanitize_label(f"{candidate_words[0]} {_dominant_extension(files)}")
            if fallback.lower() not in {"cluster", "noise"}:
                return fallback
            continue
        candidate = _sanitize_label(" ".join(candidate_words))
        wc = len(candidate.split())
        if 1 <= wc <= 4 and candidate.lower() not in {"cluster", "noise"}:
            return candidate
    return ""


def _common_prefix_label(files: List[ClusteredFile]) -> str:
    """For numeric series (PS1/PS2/PS3, HW1/HW2) use the shared filename prefix."""
    stems = [clean_filename(os.path.splitext(f.file_meta.file_name)[0]) for f in files]
    prefix = os.path.commonprefix(stems).strip()
    prefix = re.sub(r"[\s_\-]+$", "", prefix)   # strip trailing separators
    if len(prefix) >= 2:
        return _sanitize_label(prefix)
    return ""


def _filename_fallback(files: List[ClusteredFile]) -> str:
    """Last-resort: most distinctive token(s) across all filenames in the cluster.

    Prefers tokens that appear in ≥2 filenames (shared signal) over unique tokens.
    When only one shared token survives, appends the dominant file-type label so the
    folder name stays descriptive ("Egypt Images" vs a bare "Egypt").
    """
    all_tokens: List[str] = []
    filenames = [_clean_filename_stem(f.file_meta.file_name) for f in files]
    token_file_count: Dict[str, int] = defaultdict(int)
    for f in files:
        stem = _clean_filename_stem(f.file_meta.file_name)
        seen_in_file: set = set()
        for tok in _tokens(stem):
            all_tokens.append(tok)
            if tok not in seen_in_file:
                token_file_count[tok] += 1
                seen_in_file.add(tok)
    if not all_tokens:
        return ""

    def _candidate_words(min_files: int) -> List[str]:
        return [
            w for w, _ in Counter(all_tokens).most_common(5)
            if token_file_count[w] >= min_files
            and w not in _TOO_GENERIC and w not in ALWAYS_STRIP and len(w) > 2
        ]

    # Try tokens shared across ≥2 files first; fall back to unique tokens
    top = _candidate_words(2) or _candidate_words(1)
    filtered = _strip_label_noise(top[:2], filenames)
    if len(filtered) >= 2:
        return _sanitize_label(" ".join(filtered[:2]))
    if filtered:
        return _sanitize_label(f"{filtered[0]} {_dominant_extension(files)}")
    return _sanitize_label(f"{_dominant_extension(files)} files")


# ── Agent ─────────────────────────────────────────────────────────────────────

class FolderNamingAgent:
    """TF-IDF folder naming with filename-token fallback. Fully local, no external calls."""

    def __init__(self, max_examples: int = 5):
        self.max_examples = max_examples
        try:
            with open(CACHE_PATH) as f:
                self.prompt_cache = json.load(f)
        except FileNotFoundError:
            self.prompt_cache = {}

    def name_clusters(self, cluster_map: Dict[int, List[ClusteredFile]]) -> Dict[int, str]:
        labels: Dict[int, str] = {}
        for cluster_id, files in cluster_map.items():
            if cluster_id == -1:
                labels[cluster_id] = "Unsorted"
                continue

            examples = files[: self.max_examples]

            try:
                # Guard must run before cache: a stale cache entry for the same OCR
                # text would otherwise bypass this check and serve a garbage name.
                if _is_all_images_no_semantic_names(files):
                    labels[cluster_id] = "Images"
                    continue

                cache_key = self._cache_key(examples)

                if cache_key in self.prompt_cache:
                    label = self.prompt_cache[cache_key]
                else:
                    avg_tokens = sum(
                        len((f.raw_text or "").split()) for f in files
                    ) / max(len(files), 1)

                    # 1. Short numeric-series clusters: common filename prefix wins
                    if avg_tokens < 10:
                        label = _common_prefix_label(files)
                    else:
                        label = ""

                    # 2. TF-IDF over extracted text + filenames
                    if not label:
                        ranked = _score_candidates(examples)
                        label = _choose_label_from_ranked(ranked, files)

                    # 3. Filename-token fallback (no text needed)
                    if not label:
                        sample_names = [f.file_meta.file_name for f in files[:3]]
                        print(
                            f"[FolderNamingAgent] cluster {cluster_id}: TF-IDF produced no label "
                            f"(avg_tokens={avg_tokens:.1f}, ranked={len(ranked)}), "
                            f"falling back to filename tokens. Sample files: {sample_names}",
                            file=sys.stderr,
                        )
                        label = _filename_fallback(files)

                    label = _sanitize_label(label) or f"Cluster {cluster_id}"
                    self.prompt_cache[cache_key] = label
                    try:
                        with open(CACHE_PATH, "w") as f:
                            json.dump(self.prompt_cache, f, indent=2)
                    except Exception:
                        pass

                labels[cluster_id] = label

            except Exception as e:
                log_error(f"[FolderNamingAgent] Failed to name cluster {cluster_id}: {e}")
                labels[cluster_id] = f"Cluster {cluster_id}"

        return labels

    def _cache_key(self, examples: List[ClusteredFile]) -> str:
        blobs = []
        for f in examples:
            meta, body = _extract_text_fields(f)
            blobs.append((meta[:120], body[:300]))
        key = json.dumps(blobs, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(key.encode()).hexdigest()

