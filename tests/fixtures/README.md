# Test fixtures (test-only)

These files are **hand-written for the tests** and are not licensed web data:

- `retrieval_train.jsonl` and the pairs in `duel/tests/conftest.py`: `origin=human`, `license=test-only`.
- `raw/`: a few lines in each source's file format, to test the parsers.

They exist only to exercise code paths (parsing, normalization, splits, retrieval, the duel). They
are never indexed for the stage, never trained on and never shown in the app. The K'iche' in them
is not a reference translation. Mock mode (`MOCK_AI=1`) uses `duel/mock_data/` instead, which
contains only real, licensed pairs.
