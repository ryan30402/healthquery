from sklearn.metrics.pairwise import linear_kernel


def search(index, question, top_k=3):
    if top_k < 1:
        raise ValueError("top_k must be at least 1.")
    query_vector = index["vectorizer"].transform([question.strip()])
    # Stored and query TF-IDF vectors have L2 norm, so dot product equals cosine.
    scores = linear_kernel(query_vector, index["matrix"]).ravel()
    if "answer_vectorizer" in index:
        answer_query = index["answer_vectorizer"].transform([question.strip()])
        answer_scores = linear_kernel(answer_query, index["answer_matrix"]).ravel()
        scores = 0.5 * scores + 0.5 * answer_scores
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
