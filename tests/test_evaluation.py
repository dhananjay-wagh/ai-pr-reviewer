from evaluation.dataset import cases
from evaluation.run import aggregate, score_case
from app.reviews import validate_locations


def test_dataset_is_unique_and_ground_truth_locations_exist():
    dataset = list(cases())
    assert len(dataset) == 30
    assert len({case["id"] for case in dataset}) == 30
    for case in dataset:
        for expected in case["expected"]:
            for line in expected["lines"]:
                validate_locations([{"file": expected["file"], "line": line}], case["diff"])


def test_scoring_penalizes_duplicates_and_wrong_categories():
    expected = [{"file":"a.py", "lines":[2], "category":"bug"}]
    correct = {"file":"a.py", "line":2, "category":"bug"}
    wrong = {**correct, "category":"security"}
    assert score_case(expected, [correct, correct, wrong]) == {"tp":1, "fp":2, "fn":0}
    assert score_case(expected, []) == {"tp":0, "fp":0, "fn":1}
    assert score_case([], [correct])["fp"] == 1


def test_empty_report_does_not_claim_perfect_precision():
    assert aggregate([], "dry-run")["location_category_precision"] is None
