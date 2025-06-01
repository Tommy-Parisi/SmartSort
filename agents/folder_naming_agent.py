import os
import json
import hashlib
from openai import OpenAI
from core.models import ClusteredFile
from core.utils import log_error

CACHE_PATH = "folder_name_cache.json"

class FolderNamingAgent:
    def __init__(self, model="gpt-3.5-turbo", max_examples=3):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.model = model
        self.max_examples = max_examples

        # Load prompt cache
        try:
            with open(CACHE_PATH, "r") as f:
                self.prompt_cache = json.load(f)
        except FileNotFoundError:
            self.prompt_cache = {}

    def name_clusters(self, cluster_map: dict[int, list[ClusteredFile]]) -> dict[int, str]:
        labels = {}

        for cluster_id, files in cluster_map.items():
            if cluster_id == -1:
                labels[cluster_id] = "Noise"
                continue

            examples = [f.raw_text.strip().replace("\n", " ") for f in files[:self.max_examples]]
            prompt = self._build_prompt(examples)
            prompt_hash = self._hash_prompt(examples)

            try:
                if prompt_hash in self.prompt_cache:
                    label = self.prompt_cache[prompt_hash]
                else:
                    response = self.client.chat.completions.create(
                        model=self.model,
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.2,
                    )
                    label = response.choices[0].message.content.strip().strip('"')
                    self.prompt_cache[prompt_hash] = label
                    with open(CACHE_PATH, "w") as f:
                        json.dump(self.prompt_cache, f, indent=2)

                labels[cluster_id] = label
                print(f"Cluster {cluster_id}: {label}")
            except Exception as e:
                log_error(f"[FolderNamingAgent] Failed to name cluster {cluster_id}: {e}")
                labels[cluster_id] = f"cluster_{cluster_id}"

        return labels

    def _build_prompt(self, examples: list[str]) -> str:
        numbered = "\n".join(f"{i+1}. \"{text[:300]}\"" for i, text in enumerate(examples))
        return f"""You are a semantic clustering assistant.

Below are {len(examples)} example files from the same group. Your task is to analyze them *collectively* and assign a short, descriptive folder name (1–4 words) that represents the shared topic or purpose of the group.

Ignore the order of examples. Focus on the common semantic themes across them all. Avoid names that only apply to the first file.

Examples:
{numbered}

Respond with only the folder name, no punctuation or quotes."""

    def _hash_prompt(self, examples: list[str]) -> str:
        key = json.dumps(sorted(examples), separators=(',', ':'))
        return hashlib.sha256(key.encode('utf-8')).hexdigest()
