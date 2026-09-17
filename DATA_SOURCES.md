# Data sources

HealthQuery uses [MedQuAD](https://github.com/abachaa/MedQuAD), created by Asma Ben Abacha and Dina Demner-Fushman.

Reference: Asma Ben Abacha and Dina Demner-Fushman, "A Question-Entailment Approach to Question Answering," BMC Bioinformatics 20, 511 (2019). https://doi.org/10.1186/s12859-019-3119-4

The dataset repository identifies its license as [Creative Commons Attribution 4.0 International](https://creativecommons.org/licenses/by/4.0/). Retain the upstream license and attribution when using the dataset. The selected source commit is recorded in `data/medquad_revision.txt`.

The repository omits answers from some subsets. Retrieval uses only locally supplied, nonempty answers with HTTP(S) source URLs; it does not scrape missing answers. Its answer coverage is narrower than the classifier's 39 labels; available types are recorded in `reports/retrieval_index.json`. Equivalent question/answer/URL records are deduplicated, while different answers to the same question are preserved. The selected dual-field retrieval index represents question/focus text and answer text in separate TF-IDF spaces, then averages their cosine similarities with fixed equal weights. The original question/focus baseline and a concatenated-text candidate remain reproducible through the index builder.

CLI previews collapse whitespace and truncate answer text for display. Full retained answer text and original source URLs remain in the local retrieval artifact. Excerpts are archived dataset material; links and clinical currency have not been verified by HealthQuery. A matching source candidate is not a verified answer to the user's question.

The classifier and retriever are separate baselines. Retrieval searches all eligible source records and does not filter by the predicted question type. Its scores are lexical similarities, not probabilities of relevance or correctness. A query with no indexed terms or no positive similarity returns no candidates; this is not a general out-of-domain detector.

Building a searchable corpus may use the full source collection. It does not retrain the classifier or establish retrieval quality. Retrieval evaluation requires separately authored queries and relevance judgments; searching for a question already in the index is only a functional check.
