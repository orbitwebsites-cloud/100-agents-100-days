"""Shared text helpers: word counts, sentence splits and syllables that agents' readability numbers rest on."""

import pytest

from hundred.lib import text


def test_written_words_count_like_word_and_docs():
    s = "Café owners in the U.S. raised $6.5M (a 4.5% fast-paced jump) at https://acme.io/x, don't they? 250,000 users."
    assert text.words(s) == ["Café", "owners", "in", "the", "U.S.", "raised", "$6.5M", "a", "4.5%", "fast-paced", "jump",
                             "at", "https://acme.io/x", "don't", "they", "250,000", "users"]
    assert text.words("A 30-60-90 plan, and/or 24/7 support from 2026-10-05; see acme.io/raise.") == [
        "A", "30-60-90", "plan", "and/or", "24/7", "support", "from", "2026-10-05", "see", "acme.io/raise"]


def test_spoken_words_split_what_a_listener_hears():
    assert text.words("A fast-paced café, José.", spoken=True) == ["A", "fast", "paced", "café", "José"]


def test_sentences_handle_headings_tables_salutations_and_wrapping():
    doc = ("# Heading\nFirst line here. Second one\nwraps onto a new line!\n\nHi Sam,\n\nThanks for the call. "
           "We will ship it.\n\nBest,\n— Dana\n\n| a | b |\n|---|---|\n| 1 | 2 |")
    assert text.sentences(doc) == ["# Heading", "First line here.", "Second one wraps onto a new line!",
                                   "Thanks for the call.", "We will ship it.", "| a | b |", "| 1 | 2 |"]
    assert text.sentences("Mr. Smith met Dr. Jones at 5 p.m. today. It went well.")[-1] == "It went well."


# Syllable counts checked against the CMU Pronouncing Dictionary (and letter-by-letter for acronyms).
@pytest.mark.parametrize("word,n", [
    ("created", 3), ("needed", 2), ("stated", 2), ("named", 1), ("jumped", 1), ("frameworks", 2), ("rules", 1),
    ("changes", 2), ("pages", 2), ("fixes", 2), ("tables", 2), ("table", 2), ("style", 1), ("make", 1),
    ("idea", 3), ("ratio", 3), ("period", 3), ("median", 3), ("criteria", 4), ("situation", 4), ("any", 2),
    ("business", 2), ("schedule", 2), ("requirements", 3), ("baseline", 2), ("pipeline", 2), ("safety", 2),
    ("statement", 2), ("moment", 2), ("payment", 2), ("unique", 2), ("buyer", 2), ("you", 1), ("read", 1),
    ("could", 1), ("count", 1), ("readability", 5), ("doesn't", 2), ("don't", 1), ("HTML", 4), ("SEO", 3),
    ("API", 3), ("PDF", 3), ("company's", 3),
])
def test_syllables_match_dictionary(word, n):
    assert text.syllables(word) == n


def test_readability_uses_the_standard_formulas():
    r = text.readability("Invoices appear here after your first payment. Download them as PDF for your records.")
    # 14 words, 2 sentences, 23 syllables (CMU): FRE = 206.835 - 1.015*7 - 84.6*23/14; FK = 0.39*7 + 11.8*23/14 - 15.59
    assert (r["words"], r["sentences"]) == (14, 2)
    assert r["fk_grade"] == round(0.39 * 7 + 11.8 * 23 / 14 - 15.59, 1) == 6.5
    assert r["flesch_reading_ease"] == round(206.835 - 1.015 * 7 - 84.6 * 23 / 14, 1)
