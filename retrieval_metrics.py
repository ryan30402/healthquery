from statistics import mean


def score_ranking(retrieved_ids, relevant_ids):
    relevant = set(relevant_ids)
    if not relevant:
        raise ValueError("Each query needs at least one known relevant record.")
    first_rank = None
    for rank, record_id in enumerate(retrieved_ids[:3], start=1):
        if record_id in relevant:
            first_rank = rank
            break
    return {
        "hit_at_1": int(first_rank == 1),
        "hit_at_3": int(first_rank is not None),
        "rr_at_3": 0.0 if first_rank is None else 1.0 / first_rank,
    }


def summarize(scores):
    if not scores:
        raise ValueError("Cannot summarize an empty evaluation.")
    return {
        "hit_at_1": mean(row["hit_at_1"] for row in scores),
        "hit_at_3": mean(row["hit_at_3"] for row in scores),
        "mrr_at_3": mean(row["rr_at_3"] for row in scores),
    }
