"""Offline tests for TEMPO error-envelope detection (canned payloads, no network)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from insseption.upstream import is_error_envelope, looks_like_unknown_envelope  # noqa: E402

# Verbatim TEMPO responses (HTTP 200) from the 2026-10-24 data outage.
RO_ERROR = [[
    "Rezultatul solicitat nu poate fi returnat. <br />Va rugam sa revizuiti criteriile de cautare<br />"
    "Daca problema persista va rugam sa ne contactati la webmaster@insse.ro specificand matricea "
    "pentru care ati primit acest mesaj"
]]
EN_ERROR = [[
    "The results to your query could not be returned.<br />Please try again and if the problem persists "
    "please contact us at webmaster@insse.ro, specifiying the matrix code for which you got this message.<br />"
    "Thank you!"
]]
DATA = [
    ["Varste si grupe de varsta", "Sexe", "Anul 1995"],
    ["Varste si grupe de varsta", "Sexe", "UM: Numar persoane"],
    ["Varste si grupe de varsta", "Sexe", "Numar persoane"],
    ["Total", "Total ", "23062448"],
]
HEADERS_ONLY = DATA[:3]
REWORDED = [["Serviciul este momentan indisponibil. Va rugam reveniti mai tarziu sau contactati webmaster@insse.ro"]]


@pytest.mark.parametrize("raw", [RO_ERROR, EN_ERROR])
def test_known_error_envelopes_are_detected(raw):
    assert is_error_envelope(raw)
    assert not looks_like_unknown_envelope(raw)


@pytest.mark.parametrize("raw", [DATA, HEADERS_ONLY, [], None, [["Total", "23062448"]]])
def test_real_and_empty_results_are_not_errors(raw):
    assert not is_error_envelope(raw)
    assert not looks_like_unknown_envelope(raw)


def test_reworded_error_is_flagged_as_unknown():
    assert not is_error_envelope(REWORDED)
    assert looks_like_unknown_envelope(REWORDED)
