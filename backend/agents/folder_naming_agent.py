import os
import re
import json
import math
import hashlib
import sys
from collections import Counter, defaultdict
from typing import Dict, List, Tuple

from openai import OpenAI
from ..core.models import ClusteredFile
from ..core.utils import log_error

CACHE_PATH = "folder_name_cache.json"

# --- Tiny stopword list (tune for your corpus) ---
STOPWORDS = {
    "the","a","an","and","or","but","for","nor","on","in","to","of","at","by","from",
    "with","as","is","are","was","were","be","been","being","that","this","these","those",
    "it","its","if","then","else","when","while","do","does","did","done","not","no",
    "into","about","over","under","between","per","via","vs","vs.","&"
}

# Words that should not appear in labels
PROFANITY = {"fuck","shit","bitch","asshole","dick","bastard", "queef", "cunt", "dick", "faggot", }  # extend as needed

# Filesystem-unsafe characters (we’ll strip/replace)
UNSAFE_FS_CHARS = r'[:<>"/\\|?*\n\r\t]'

TOKEN_RE = re.compile(r"[A-Za-z0-9]+(?:['’][A-Za-z0-9]+)?")  # keeps contractions like client's
NUM_RE = re.compile(r"^\d+$")


def _safe_title_case(words: List[str]) -> str:
    def cap(w: str) -> str:
        return w.upper() if w.isupper() and len(w) <= 4 else w.capitalize()
    return " ".join(cap(w) for w in words)


def _sanitize_label(label: str, max_words: int = 4, max_len: int = 60) -> str:
    # remove profanity and unsafe chars; collapse whitespace
    label = re.sub(UNSAFE_FS_CHARS, " ", label)
    label = re.sub(r"\s+", " ", label).strip()

    # split, filter profanity, limit words, title-case
    words = [w for w in label.split() if w.lower() not in PROFANITY]
    words = words[:max_words]
    label = _safe_title_case(words)

    # final length guard
    if len(label) > max_len:
        label = label[:max_len].rstrip()

    # fallback if empty
    return label or "Cluster"


def _extract_text_fields(f: ClusteredFile) -> Tuple[str, str]:
    """Return (short_metadata_line, long_body) for weighting."""
    # Try to grab a filename stem and any known title field if present
    name = getattr(f, "filename", "") or getattr(f, "path", "") or ""
    name = os.path.splitext(os.path.basename(name))[0]
    title = getattr(f, "title", "") or ""
    meta = " ".join([name, title]).strip()

    body = (getattr(f, "raw_text", "") or "").strip()
    return meta, body


def _tokens(text: str) -> List[str]:
    toks = []
    for m in TOKEN_RE.finditer(text.lower()):
        w = m.group(0)
        if w in STOPWORDS: 
            continue
        if NUM_RE.match(w):  # filter pure numbers
            continue
        if len(w) <= 2:  # filter tiny tokens (tune if needed)
            continue
        toks.append(w)
    return toks


def _ngrams(tokens: List[str], n: int) -> List[Tuple[str, ...]]:
    return [tuple(tokens[i:i+n]) for i in range(len(tokens)-n+1)]


def _score_candidates(examples: List[ClusteredFile]) -> List[Tuple[Tuple[str, ...], float]]:
    """
    Build a tiny TF-IDF-ish score over bigrams/trigrams across the selected example files.
    We overweight metadata tokens (filename/title) by 2x since they’re highly indicative.
    """
    docs_unigram = []
    docs_bigram = []
    docs_trigram = []

    for f in examples:
        meta, body = _extract_text_fields(f)

        meta_toks = _tokens(meta)
        body_toks = _tokens(body)

        # Overweight meta by simple duplication
        tokens = meta_toks + meta_toks + body_toks

        docs_unigram.append(Counter(tokens))
        docs_bigram.append(Counter(_ngrams(tokens, 2)))
        docs_trigram.append(Counter(_ngrams(tokens, 3)))

    def tf_idf(doc_list: List[Counter]) -> Dict[Tuple[str, ...], float]:
        N = len(doc_list)
        df = defaultdict(int)
        for c in doc_list:
            for k in c:
                df[k] += 1
        scores = {}
        for c in doc_list:
            for k, tf in c.items():
                idf = math.log((N + 1) / (df[k] + 0.5)) + 1.0  # smoothed IDF
                scores[k] = scores.get(k, 0.0) + tf * idf
        return scores

    uni_scores = tf_idf(docs_unigram)  # not used directly for labels, but for boosting
    bi_scores = tf_idf(docs_bigram)
    tri_scores = tf_idf(docs_trigram)

    # Merge, with a preference: trigrams > bigrams; also lightly boost n-grams that contain high-scoring unigrams
    def boost_from_unigrams(ng: Tuple[str, ...]) -> float:
        return sum(uni_scores.get((w,), 0.0) if isinstance(next(iter(uni_scores), None), tuple) else uni_scores.get(w, 0.0) for w in ng)

    combined: Dict[Tuple[str, ...], float] = {}
    for ng, s in bi_scores.items():
        combined[ng] = combined.get(ng, 0.0) + s + 0.15 * boost_from_unigrams(ng)
    for ng, s in tri_scores.items():
        combined[ng] = combined.get(ng, 0.0) + 1.35 * s + 0.20 * boost_from_unigrams(ng)

    # Filter junky candidates
    def ok(ng: Tuple[str, ...]) -> bool:
        # Drop n-grams that start or end with stopwords (shouldn't happen post-filter, but extra guard)
        if not ng: 
            return False
        if any(w in PROFANITY for w in ng):
            return False
        # avoid pure numbers or IDs
        if all(NUM_RE.match(w) for w in ng):
            return False
        # avoid overly generic terms
        too_generic = {"document","notes","file","draft","final","copy","new","updated","version"}
        if any(w in too_generic for w in ng):
            return False
        return True

    ranked = [(ng, sc) for ng, sc in combined.items() if ok(ng)]
    ranked.sort(key=lambda x: x[1], reverse=True)
    return ranked


def _choose_label_from_ranked(ranked: List[Tuple[Tuple[str, ...], float]]) -> str:
    # Prefer trigrams/bigrams; convert to words; light post-filters
    for ng, _ in ranked[:50]:
        words = list(ng)
        # compact duplicates like "policy policy"
        dedup = []
        for w in words:
            if not dedup or dedup[-1] != w:
                dedup.append(w)
        candidate = _sanitize_label(" ".join(dedup))
        # target 2–4 words; allow 1 if it's strong
        wc = len(candidate.split())
        if 1 <= wc <= 4 and candidate.lower() not in {"cluster","noise"}:
            return candidate
    return ""


class FolderNamingAgent:
    """
    Heuristics-first folder naming with LLM fallback + caching.
    """
    def __init__(self, model="gpt-4o-mini", max_examples=5, use_llm_fallback=True):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY")) if use_llm_fallback else None
        self.model = model
        self.max_examples = max_examples
        self.use_llm_fallback = use_llm_fallback

        try:
            with open(CACHE_PATH, "r") as f:
                self.prompt_cache = json.load(f)
        except FileNotFoundError:
            self.prompt_cache = {}

    def name_clusters(self, cluster_map: Dict[int, List[ClusteredFile]]) -> Dict[int, str]:
        labels: Dict[int, str] = {}
        for cluster_id, files in cluster_map.items():
            if cluster_id == -1:
                labels[cluster_id] = "Noise"
                continue

            examples = files[: self.max_examples]
            cache_key = self._cache_key_examples(examples)

            try:
                if cache_key in self.prompt_cache:
                    label = self.prompt_cache[cache_key]
                else:
                    # --- Heuristic pass ---
                    ranked = _score_candidates(examples)
                    label = _choose_label_from_ranked(ranked)

                    # --- Fallback to LLM if needed ---
                    if not label and self.use_llm_fallback and self.client:
                        prompt = self._build_prompt_for_llm(examples)
                        resp = self.client.chat.completions.create(
                            model=self.model,
                            messages=[{"role": "user", "content": prompt}],
                            temperature=0.2,
                        )
                        llm_label = (resp.choices[0].message.content or "").strip().strip('"')
                        label = _sanitize_label(llm_label) or f"Cluster_{cluster_id}"

                    # Final guardrails
                    label = _sanitize_label(label)
                    self.prompt_cache[cache_key] = label
                    with open(CACHE_PATH, "w") as f:
                        json.dump(self.prompt_cache, f, indent=2)

                labels[cluster_id] = label
                print(f"Cluster {cluster_id}: {label}", file=sys.stderr)

            except Exception as e:
                log_error(f"[FolderNamingAgent] Failed to name cluster {cluster_id}: {e}")
                labels[cluster_id] = f"Cluster_{cluster_id}"

        return labels

    # ---------- Internals ----------
    def _cache_key_examples(self, examples: List[ClusteredFile]) -> str:
        # Stable key from top examples' salient text
        blobs = []
        for f in examples:
            meta, body = _extract_text_fields(f)
            # pull ~300 chars from body to keep key bounded
            blobs.append((meta[:120], body[:300]))
        key = json.dumps(blobs, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(key.encode("utf-8")).hexdigest()

    def _build_prompt_for_llm(self, examples: List[ClusteredFile]) -> str:
        def short(s: str, n: int) -> str:
            return re.sub(r"\s+", " ", s)[:n].strip()
        numbered = []
        for i, f in enumerate(examples, 1):
            meta, body = _extract_text_fields(f)
            snippet = (meta + " — " + body) if meta else body
            numbered.append(f'{i}. "{short(snippet, 300)}"')
        numbered = "\n".join(numbered)
        return (
            "You are a semantic clustering assistant.\n\n"
            f"Below are {len(examples)} example files from the same group. "
            "Assign a short, descriptive folder name (1–4 words) that represents the shared topic across them all.\n\n"
            "Examples:\n"
            f"{numbered}\n\n"
            "Respond with only the folder name, no punctuation or quotes, do not end with the word folder."
        )