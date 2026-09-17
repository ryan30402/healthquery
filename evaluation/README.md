# HealthQuery development challenge set

`challenge_v1.jsonl` contains 32 assistant-authored English medical-information requests, with four examples for each of eight raw MedQuAD question-type labels: `information`, `symptoms`, `causes`, `treatment`, `prevention`, `exams and tests`, `outlook`, and `inheritance`.

Authored on 2026-09-17 for development diagnostics, motivated by the baseline's already-known paraphrase failure. All questions and intended labels were fixed before the first prediction run on this set; no candidate was selected or revised in response to its own model prediction. The three existing demonstration questions are excluded; in particular, the already-known diabetes-treatment example remains a separate regression check.

This small, balanced, development-only set covers 8 of the project's 39 raw labels. It is not a held-out final test, is not representative of real patient questions or their distribution, and has not received clinical validation or independent human annotation. It contains information-seeking questions only, with no medical answers or advice. A score on it does not establish clinical usefulness, safety, or generalization to all 39 labels.

Freeze this file before the first prediction run. Use it to inspect paraphrase sensitivity and guide development; do not add its examples to training data. Once developers inspect its results, it remains development material. Record later revisions under a new version rather than silently editing v1, and obtain independently authored, separately held-out evaluation data for final claims.

Each JSONL row has three fields: `id` (stable example identifier), `question` (classifier input), and `question_type` (intended raw label). Labels were chosen for one intended intent per request. A broad request for a condition overview is labeled `information`; requests about progression or recovery are labeled `outlook`; explicit family transmission is labeled `inheritance`.
