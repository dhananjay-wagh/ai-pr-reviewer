import json

import pytest

from app.reviews import parse_findings, validate_locations

DIFF = "diff --git a/a.py b/a.py\n--- a/a.py\n+++ b/a.py\n@@ -4,2 +4,2 @@\n-old\n+new\n context\n"


@pytest.mark.parametrize("line", [0, -1, True, "4"])
def test_invalid_lines_fail_closed(line):
    with pytest.raises(ValueError):
        parse_findings(json.dumps([dict(file="a.py", line=line, comment="Bug")]))


def test_locations_support_deletions_and_reject_hallucinations():
    validate_locations([dict(file="a.py", line=4, side="LEFT")], DIFF)
    validate_locations([dict(file="a.py", line=4, side="RIGHT")], DIFF)
    with pytest.raises(ValueError):
        validate_locations([dict(file="a.py", line=100)], DIFF)
    with pytest.raises(ValueError):
        validate_locations([dict(file="other.py", line=4)], DIFF)


def test_empty_output_is_distinct_from_invalid_output():
    assert parse_findings("[]") == []
    with pytest.raises(ValueError):
        parse_findings('[{"file":"a.py","line":0,"comment":"bug"}]')
