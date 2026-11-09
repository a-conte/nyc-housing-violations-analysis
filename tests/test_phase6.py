import numpy as np
import pandas as pd

from housing.phase6 import choose, overlap, peer_summary


def frame():
    n = 45
    return pd.DataFrame(
        {
            "building_id": [str(i + 1) for i in range(n)],
            "selected_units": 20,
            "pluto_units": 40,
            "hazardous": np.arange(25, 25 + n),
            "expected": 5.0,
            "observed_minus_expected": np.arange(20, 20 + n),
            "oe": np.arange(25, 25 + n) / 5,
            "pearson_residual": np.arange(n, dtype=float),
            "borough_id": 1,
            "complaints": 0,
        }
    )


def test_gates_and_deterministic_queues():
    d = frame()
    d.loc[44, "selected_units"] = 3
    d.loc[43, "expected"] = 0.1
    a, q, n = choose(d)
    b, _, _ = choose(d.sample(frac=1, random_state=42))
    assert set(a.building_id) == set(b.building_id)
    assert not {"44", "45"} & set(a.building_id)
    assert len(a) <= 30 and a.building_id.is_unique and n == 43
    assert set(q.indicator) == {"hazardous", "rate", "pearson_residual"}
    assert q.groupby("indicator").size().max() <= 10


def test_peer_excludes_target_and_reports_insufficient_groups():
    d = frame()
    d["rate"] = 100 * d.hazardous / d.selected_units
    row = d.iloc[0]
    assert peer_summary(d, row)["peer_n"] == 44
    assert peer_summary(d, next(d.itertuples(index=False)))["peer_n"] == 44
    assert peer_summary(d.iloc[:5], row)["peer_rate_p90"] is None


def test_denominator_sensitivity_does_not_change_model_outputs():
    d = frame()
    original = d.copy(deep=True)
    hpd, _, _ = choose(d)
    pluto, _, _ = choose(d, "pluto_units")
    pd.testing.assert_frame_equal(d, original)
    np.testing.assert_allclose(hpd.rate, 2 * pluto.rate)
    np.testing.assert_array_equal(hpd.expected, pluto.expected)
    assert overlap(hpd, pluto)["jaccard"] == 1


def test_clean_filter_and_numeric_tie_break():
    d = frame()
    d[["hazardous", "oe", "pearson_residual", "observed_minus_expected"]] = [40, 8, 3, 35]
    leads, _, _ = choose(d, allowed=d.building_id.astype(int) > 10)
    assert set(leads.building_id) == set(map(str, range(11, 21)))
