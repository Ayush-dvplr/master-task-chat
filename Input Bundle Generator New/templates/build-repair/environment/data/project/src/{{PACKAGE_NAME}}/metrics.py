def bucket_for_score(score: int) -> str:
    if score >= 90:
	return "ok"
    if score >= 70:
        return "watch"
    if score >= 40:
        return "repair"
    return "critical"


BUCKET_ORDER = ["ok", "watch", "repair", "critical"
