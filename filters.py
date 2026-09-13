import re
import unicodedata

import pandas as pd

CHILD_AGE_OPTIONS: dict[str, int | None] = {
    "指定しない": None,
    "0歳（生後6か月）": 6,
    "1歳": 12,
    "2歳": 24,
    "3歳": 36,
    "6歳（小学生）": 72,
    "12歳（中学生）": 144,
    "15歳（高校生）": 180,
}

SCHOOL_AGE_MONTHS = {
    "小学生": 72,
    "中学生": 144,
    "高校生": 180,
    "成人": 216,
}


def minimum_age_months(notes: object) -> int | None:
    """Extract a conservative lower age bound from an explicit 対象年齢 note."""
    if pd.isna(notes):
        return None

    normalized = unicodedata.normalize("NFKC", str(notes))
    match = re.search(r"対象年齢\s*[:：]?\s*([^。\n]+)", normalized)
    if not match:
        return None
    age_text = match.group(1)

    months = re.search(r"(?:生後\s*)?(\d+)\s*(?:か月|ヶ月|ケ月|箇月)\s*以上", age_text)
    if months:
        return int(months.group(1))

    years = re.search(r"満?\s*(\d+)\s*歳以上", age_text)
    if years:
        return int(years.group(1)) * 12

    for school, age_months in SCHOOL_AGE_MONTHS.items():
        if f"{school}以上" in age_text:
            return age_months
    return None


def filter_for_child_age(facilities: pd.DataFrame, age_months: int | None) -> pd.DataFrame:
    if age_months is None:
        return facilities
    minimum_ages = facilities["医療機関通信欄"].map(minimum_age_months)
    return facilities[minimum_ages.notna() & (minimum_ages <= age_months)].copy()
