from __future__ import annotations

import numpy as np
import pytest

from backend.app.config import CONSTANTS, SET_THRESHOLD
from backend.app.inference import conformal_set

N = 101


def probabilities(**assigned: float) -> np.ndarray:
    probs = np.zeros(N)
    for index, value in assigned.items():
        probs[int(index[1:])] = value
    probs[0] += 1.0 - probs.sum()
    return probs


def test_the_threshold_follows_the_calibrated_qhat():
    assert SET_THRESHOLD == pytest.approx(1.0 - CONSTANTS["conformal_qhat"])
    assert 0.0 < SET_THRESHOLD < 1.0


def test_a_confident_prediction_gives_a_singleton():
    probs = np.full(N, 1e-6)
    probs[7] = 1.0 - 1e-6 * (N - 1)
    assert conformal_set(probs) == [7]


def test_candidates_come_back_in_descending_probability():
    probs = np.full(N, 1e-6)
    probs[3], probs[9], probs[50] = 0.2, 0.5, 0.3
    assert conformal_set(probs) == [9, 50, 3]


def test_everything_above_the_threshold_is_included():
    probs = np.full(N, 1e-6)
    above = SET_THRESHOLD * 2
    probs[1] = probs[2] = probs[3] = above
    probs[4] = SET_THRESHOLD / 2
    probs[0] = 1.0 - probs.sum()
    assert set(conformal_set(probs)) >= {1, 2, 3}
    assert 4 not in conformal_set(probs)


def test_the_set_is_never_empty_even_when_nothing_clears_the_threshold():
    probs = np.full(N, SET_THRESHOLD / 10)
    probs[42] = SET_THRESHOLD / 2
    result = conformal_set(probs)
    assert result[0] == 42
    assert len(result) >= 1


def test_the_top_class_is_always_first_when_it_is_below_the_threshold():
    probs = np.full(N, 0.0)
    probs[11] = SET_THRESHOLD / 3
    assert conformal_set(probs)[0] == 11


def test_a_uniform_distribution_clears_nothing_and_still_names_one_class():
    probs = np.full(N, 1.0 / N)
    assert 1.0 / N < SET_THRESHOLD
    assert conformal_set(probs) == [0]


def test_a_broad_distribution_is_capped_rather_than_returning_everything():
    probs = np.full(N, 1e-6)
    probs[:20] = 0.05
    assert 0.05 > SET_THRESHOLD
    assert len(conformal_set(probs)) == 8
    assert len(conformal_set(probs, k_max=3)) == 3


def test_indices_are_plain_python_ints_so_they_serialise():
    probs = np.full(N, 1e-6)
    probs[5] = 0.9
    assert all(isinstance(i, int) for i in conformal_set(probs))
