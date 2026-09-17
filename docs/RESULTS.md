# Evaluation and model notes

## Data and provenance

Pinned MedQuAD commit: `577bd37b96c02d1833b2c9eed2de9f96964e96cb`.

The ingest pipeline parses 11,274 XML files into 47,441 question records, including 16,407 nonempty answers. It retains questions without answers for classification. Normalized question deduplication leaves 43,449 unique questions across 39 classes. The processed file SHA-256 is `5e14b1be4193741f8f8bff71c40f4872cb28f6e9b604d2cb7e7dc73b2e585c87`.

Retrieval removes records without question/answer text, malformed HTTP(S) URLs, and duplicate question/answer/URL triples. It retains 16,377 records, 16 question types, and 5,476 distinct original URLs. URL syntax validation is not a live link check. The index uses the searchable corpus, including material outside classifier training; retrieval is evaluated separately from classification.

## Classifier

TF-IDF unigrams/bigrams feed class-balanced logistic regression. Records sharing a file, normalized focus, or exact source URL are connected into groups. Grouped stratified splits use seed 42: training 34,758; validation 4,347; reserved test 4,344. The TF-IDF classifier vocabulary is fitted on training data only. The reserved classifier test set has not been evaluated or used to select the retrieval design.

| Development evaluation | Accuracy | Macro-F1 |
|---|---:|---:|
| Majority classifier, validation | 0.1714 | 0.0075 |
| TF-IDF/logistic regression, validation | 1.0000 | 1.0000 |
| TF-IDF/logistic regression, 32 paraphrases | 0.3438 | 0.3010 |

The paraphrase score averages F1 across its eight covered labels, not all 39 supported labels. These assistant-authored challenge questions have zero exact normalized overlap with MedQuAD but are not an independently sampled user test. Group separation does not eliminate shared wording templates. The gap supports keeping classifier labels experimental, and retrieval never gates on those labels.

## Retrieval experiment

Before this comparison, three candidate definitions were fixed: question/focus only; concatenated question/focus/answer; independent question/focus and answer vectorizers averaged 50/50. All use English stop-word removal, unigrams/bigrams, L2 normalization, stable descending ranking, and one result per exact source URL. No weight sweep or extra candidates were added after inspecting scores.

Both fields are lexical TF-IDF representations; this is not a dense embedding model or BM25. Because vectors have L2 norm, the dot product computes cosine similarity without repeatedly normalizing the whole stored matrix. Verification found the same top-three rankings as cosine_similarity for all 24 queries and all three candidates; numerical differences were roundoff only.

| Candidate | Hit@1 | Hit@3 | MRR@3 |
|---|---:|---:|---:|
| Question/focus | 8/24 (0.3333) | 14/24 (0.5833) | 0.4444 |
| Concatenated | 9/24 (0.3750) | 13/24 (0.5417) | 0.4583 |
| Equal-field blend | 8/24 (0.3333) | 15/24 (0.6250) | 0.4792 |

The blend's additional top-three hit is `retrieval-dev-015`, about pneumonia causes. It loses no baseline top-three hits, but moves four previous rank-one hits to rank two while four other queries improve to rank one. It still misses labeled records for 9/24 queries. Concatenation improves Hit@1 while worsening Hit@3, illustrating that metrics reflect different retrieval preferences.

The selected blend trades increased storage and latency for one additional development hit and better MRR. The uncompressed artifacts in the initial experiment were approximately 28.7 MB for question/focus versus 76.8 MB for the blend; the release saves compressed artifacts, so on-disk release sizes differ. Compression reduces file size, not the loaded vocabulary/matrix requirements.

The 24 queries were written with corpus knowledge and partial relevance judgments before first baseline scoring. They cover six topics and four information needs. The frozen file SHA-256 is `054da423dfe7d57deaec493aaf9429f0c7dd0ff2cb1f90f081cf1133aa59d0ff`. They were used to select this release: all comparison scores are development scores. Unjudged results may be relevant; no statistical significance, clinical validity, or generalization claim is made. Judgments refer to full records, not only the displayed 360-character previews.

## Software and performance

The reference release passed 54 tests in a clean Python 3.12 virtual environment. Tests cover input validation, artifact loading, source deduplication, answer-only retrieval, score equivalence, evaluation arithmetic, XML preparation failures, and deployment file selection.

`python -m scripts.benchmark` starts its own Uvicorn server on loopback and issues 120 measured requests (24 queries repeated five times) after five warmups. Reference p50: 28.65 ms; p95: 62.06 ms; mean: 33.69 ms. This met the chosen local interactive target of p95 below 100 ms in that run; the finalizer records measurements but does not enforce that threshold.

The timer includes client JSON handling, loopback HTTP, request validation, classification, retrieval, and response serialization. It excludes startup/model loading, the warmups, browser rendering, a remote network, and concurrent load. The report records all observations, environment versions, logical CPU count, and artifact/source hashes. These are machine-specific measurements, not throughput or availability claims.

The numerical stack now pins NumPy 2.3.5 and SciPy 1.17.0. The observed NumPy 2.5/joblib deprecation warnings are avoided in the validated environment; one Starlette/AnyIO deprecation warning remains. No warnings are suppressed by the project.

## Evidence boundaries

The source package supplies the measured reference reports under `reports/reference_v1/`. Running the finalizer produces fresh reports in `reports/`. Source and artifact hashes make changes traceable; they do not certify content quality.

The user verified an earlier local Docker version before this release. The final release was verified locally through its Python pipeline and real HTTP requests; this authoring environment has no Docker Engine. Final Docker builds, GitHub Actions, and a public Space must therefore be checked using the supplied instructions. No successful cloud deployment is claimed here.
