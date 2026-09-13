import pandas as pd

from filters import filter_for_child_age, minimum_age_months


def test_minimum_age_months_parses_explicit_ages() -> None:
    assert minimum_age_months("対象年齢：6ヶ月以上　予約不要") == 6
    assert minimum_age_months("対象年齢：満2歳以上") == 24
    assert minimum_age_months("対象年齢：小学生以上") == 72


def test_minimum_age_months_is_conservative_without_label() -> None:
    assert minimum_age_months("小児科です。6ヶ月以上を受付") is None


def test_filter_for_child_age_keeps_only_eligible_explicit_notes() -> None:
    facilities = pd.DataFrame(
        {
            "医療機関通信欄": ["対象年齢：6ヶ月以上", "対象年齢：中学生以上", "記載なし"],
            "医療機関名称": ["A", "B", "C"],
        }
    )
    result = filter_for_child_age(facilities, 72)
    assert result["医療機関名称"].tolist() == ["A"]
