from evals.fertility import measure, render, words


def test_words_keep_apostrophes_and_skip_punctuation():
    assert words("Le tz'i' kawar - pa le ja . 17") == ["Le", "tz'i'", "kawar", "pa", "le", "ja"]


def test_measure_with_a_fake_tokenizer():
    pairs = [{"quc": "k'ak' ja", "spa": "casa nueva", "source": "s"}]
    stats = measure(pairs, count=lambda text: len(text))  # one "token" per character
    assert stats["all"]["quc_fertility"] == len("k'ak' ja") / 2
    assert stats["all"]["token_ratio"] == len("k'ak' ja") / len("casa nueva")
    assert stats["s"]["pairs"] == 1
    assert "K'iche' tokens/word" in render(stats, "tok", "v1", None)
