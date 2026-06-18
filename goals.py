from normalize import normalize


def match_goals(ocr_text: str, goals: list[dict]) -> list[int]:
    matched = []

    for goal in goals:
        keywords_hit = any(
            normalize(kw) in ocr_text
            for kw in goal["keywords"]
        )
        if keywords_hit:
            matched.append(goal["id"])

    return matched