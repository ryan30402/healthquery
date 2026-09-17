from sklearn.metrics.pairwise import cosine_similarity


def search(index, question, top_k=3):
    if top_k < 1:
        raise ValueError("top_k must be at least 1.")
    query_vector = index["vectorizer"].transform([question.strip()])
    if query_vector.nnz == 0:
        return []
    scores = cosine_similarity(query_vector, index["matrix"]).ravel()
    order = (-scores).argsort(kind="stable")
    results = []
    seen_urls = set()

    for position in order:
        score = float(scores[position])
        if score <= 0:
            break
        record = index["records"][position]
        url = record["source_url"]
        if url in seen_urls:
            continue
        seen_urls.add(url)
        results.append({**record, "lexical_similarity": score})
        if len(results) == top_k:
            break
    return results
