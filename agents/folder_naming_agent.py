import os
from openai import OpenAI
from core.models import ClusteredFile
from core.utils import log_error

class FolderNamingAgent:
    def __init__(self, model="gpt-3.5-turbo", max_examples=3):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.model = model
        self.max_examples = max_examples

    def name_clusters(self, cluster_map: dict[int, list[ClusteredFile]]) -> dict[int, str]:
        labels = {}

        for cluster_id, files in cluster_map.items():
            if cluster_id == -1:
                labels[cluster_id] = "Noise"
                continue

            examples = [f.raw_text.strip().replace("\n", " ") for f in files[:self.max_examples]]
            prompt = self._build_prompt(examples)

            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.2,
                )
                label = response.choices[0].message.content.strip().strip('"')
                labels[cluster_id] = label
                print(f"Cluster {cluster_id}: {label}")
            except Exception as e:
                log_error(f"[FolderNamingAgent] Failed to name cluster {cluster_id}: {e}")
                labels[cluster_id] = f"cluster_{cluster_id}"

        return labels

    def _build_prompt(self, examples: list[str]) -> str:
        numbered = "\n".join(f"{i+1}. \"{text[:300]}\"" for i, text in enumerate(examples))
        return f"""You are a semantic classifier.

Given the following sample documents from a group, assign a short descriptive label (1–4 words) that summarizes the group topic.

Documents:
{numbered}

Label:"""