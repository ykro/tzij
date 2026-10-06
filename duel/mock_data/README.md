# Mock data (MOCK_AI=1, tests)

A handful of real, licensed pairs so the tests run without Ollama, a GPU or the full dataset, and
without showing any invented K'iche'.

- `index_pairs.jsonl`: 26 pairs from the train split (UD K'iche'-IU, CC BY-SA 4.0 with ALMG
  permission; COERLL course, CC BY 4.0; GATITOS, CC BY 4.0; PanLex, CC0), indexed at startup with
  hashing embeddings.

Each record keeps its `source_name`, `url` and `license`. Regenerate from the current dataset if
the pipeline changes; never write K'iche' by hand here.
