import pytest

from changgeun.nlp.command_registry import direct_candidates
from changgeun.parser.contracts import ParseError
from changgeun.parser.jev import _stage1_selected


def answer(choice, probabilities, confidence):
    return {"type": "choice", "choice": choice,
            "probabilities": probabilities, "confidence": confidence}


def test_one_retrieved_command_with_strong_distribution_can_recover_feedback():
    options = {"C01": "목록 보기", "__NONE__": "없음"}
    assert set(direct_candidates("목록 보여줘", allow_admin=False)) == {"C01"}
    assert _stage1_selected(
        answer("C01", {"C01": .86, "__NONE__": .14}, .73), options,
        expected="C01", text="목록 보여줘",
    ) == "C01"
    kinds = {key: key for key in ("single", "multiple", "not_request", "unclear")}
    assert _stage1_selected(
        answer("single", {"single": .81, "multiple": .05,
                          "not_request": .10, "unclear": .04}, .75), kinds,
        expected="single", text="입장해줘",
    ) == "single"
    assert set(direct_candidates("여기 들어와", allow_admin=False)) == {"C21"}
    assert set(direct_candidates("입장해줘", allow_admin=False)) == {"C21"}
    assert set(direct_candidates("들어와줘", allow_admin=False)) == {"C21"}
    assert set(direct_candidates("들어와봐", allow_admin=False)) == {"C21"}
    assert set(direct_candidates("퇴장해", allow_admin=False)) == {"C22"}
    assert set(direct_candidates("나가", allow_admin=False)) == {"C22"}


@pytest.mark.parametrize("expected,text,choice,confidence,probabilities", [
    ("C01", "목록 보여줘라고 했어", "C01", .73, {"C01": .86, "__NONE__": .14}),
    ("C01", "목록 보여줘", "__NONE__", .6, {"C01": .2, "__NONE__": .8}),
    ("C01", "목록 보여줘", "C01", .49, {"C01": .86, "__NONE__": .14}),
    ("C01", "목록 보여줘", "C01", .73, {"C01": .70, "__NONE__": .30}),
])
def test_calibration_does_not_override_negative_or_weak_jev(
    expected, text, choice, confidence, probabilities,
):
    with pytest.raises(ParseError):
        _stage1_selected(answer(choice, probabilities, confidence),
                         {"C01": "목록 보기", "__NONE__": "없음"},
                         expected=expected, text=text)
