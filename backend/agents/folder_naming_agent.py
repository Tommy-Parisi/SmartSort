import os
import re
import json
import math
import hashlib
import sys
from collections import Counter, defaultdict
from typing import Dict, List, Tuple

from ..core.models import ClusteredFile
from ..core.utils import log_error

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

TOKEN_RE = re.compile(r"[A-Za-z0-9]+(?:[''][A-Za-z0-9]+)?")
NUM_RE = re.compile(r"^\d+$")


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
    stem = os.path.splitext(f.file_meta.file_name)[0]
    # Normalise separators so "canvas_calendar_doc" → individual tokens
    stem = re.sub(r"[_\-.]", " ", stem)
    body = (f.raw_text or "").strip()
    return stem, body


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
        toks.append(w)
    return toks


def _ngrams(tokens: List[str], n: int) -> List[Tuple[str, ...]]:
    return [tuple(tokens[i:i+n]) for i in range(len(tokens) - n + 1)]


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


def _choose_label_from_ranked(ranked: List[Tuple[Tuple[str, ...], float]]) -> str:
    for ng, _ in ranked[:50]:
        words = list(ng)
        # Remove non-adjacent duplicates ("Lecture Fall Lecture" → "Lecture Fall")
        seen: List[str] = []
        for w in words:
            if w not in seen:
                seen.append(w)
        candidate = _sanitize_label(" ".join(seen))
        wc = len(candidate.split())
        if 1 <= wc <= 4 and candidate.lower() not in {"cluster", "noise"}:
            return candidate
    return ""


def _common_prefix_label(files: List[ClusteredFile]) -> str:
    """For numeric series (PS1/PS2/PS3, HW1/HW2) use the shared filename prefix."""
    stems = [os.path.splitext(f.file_meta.file_name)[0] for f in files]
    prefix = os.path.commonprefix(stems).strip()
    prefix = re.sub(r"[\s_\-]+$", "", prefix)   # strip trailing separators
    if len(prefix) >= 2:
        return _sanitize_label(prefix + " Series")
    return ""


def _filename_fallback(files: List[ClusteredFile]) -> str:
    """Last-resort: most distinctive token(s) across all filenames in the cluster."""
    all_tokens: List[str] = []
    for f in files:
        stem = re.sub(r"[_\-.]", " ", os.path.splitext(f.file_meta.file_name)[0])
        all_tokens.extend(_tokens(stem))
    if not all_tokens:
        return ""
    top = [w for w, _ in Counter(all_tokens).most_common(5)
           if w not in _TOO_GENERIC and len(w) > 2][:2]
    return _sanitize_label(" ".join(top)) if top else ""


# ── Agent ─────────────────────────────────────────────────────────────────────

class FolderNamingAgent:
    """
    TF-IDF-first folder naming, filename-token fallback, optional LLM last resort.

    By default runs entirely offline (use_llm_fallback=False).
    Pass use_llm_fallback=True and set OPENAI_API_KEY to enable LLM top-up.
    """

    def __init__(self, model: str = "gpt-4o-mini", max_examples: int = 5,
                 use_llm_fallback: bool = False):
        self.model = model
        self.max_examples = max_examples
        self.use_llm_fallback = use_llm_fallback
        self.client = None

        if use_llm_fallback:
            api_key = os.getenv("OPENAI_API_KEY")
            if api_key:
                from openai import OpenAI
                self.client = OpenAI(api_key=api_key)
            else:
                print("[FolderNamingAgent] OPENAI_API_KEY not set — LLM fallback disabled.",
                      file=sys.stderr)
                self.use_llm_fallback = False

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
            cache_key = self._cache_key(examples)

            try:
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
                        label = _choose_label_from_ranked(ranked)

                    # 3. Filename-token fallback (no text needed)
                    if not label:
                        label = _filename_fallback(files)

                    # 3. LLM last resort (optional, requires API key)
                    if not label and self.use_llm_fallback and self.client:
                        prompt = self._build_llm_prompt(examples)
                        resp = self.client.chat.completions.create(
                            model=self.model,
                            messages=[{"role": "user", "content": prompt}],
                            temperature=0.2,
                        )
                        llm_label = (resp.choices[0].message.content or "").strip().strip('"')
                        label = _sanitize_label(llm_label)

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

    def _build_llm_prompt(self, examples: List[ClusteredFile]) -> str:
        def short(s: str, n: int) -> str:
            return re.sub(r"\s+", " ", s)[:n].strip()
        numbered = []
        for i, f in enumerate(examples, 1):
            meta, body = _extract_text_fields(f)
            snippet = (meta + " — " + body) if meta else body
            numbered.append(f'{i}. "{short(snippet, 300)}"')
        return (
            "You are a semantic clustering assistant.\n\n"
            f"Below are {len(examples)} example files from the same group. "
            "Assign a short, descriptive folder name (1–4 words) that represents "
            "the shared topic across them all.\n\n"
            "Examples:\n"
            + "\n".join(numbered)
            + "\n\nRespond with only the folder name, no punctuation or quotes, "
            "do not end with the word folder."
        )
