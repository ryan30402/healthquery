# Retrieval development benchmark v1

`retrieval_dev_v1.jsonl` contains 24 English queries: six topics with four intents
per topic (information, symptoms, causes, and treatment). The topics are
hypothyroidism, gallstones, insomnia, pneumonia, iron-deficiency anemia, and
bronchitis. These were chosen because the local index contains archived answers
covering all four intents. They are not a random or representative sample of
medical information needs.

## How the queries and judgments were created

An assistant read the indexed questions, focus fields, and full archived answers
for the selected topics. It then wrote natural-language queries and selected
known relevant record IDs based on answer content. This is a corpus-informed,
assistant-authored development set, not independent patient questions, expert
medical judgments, a clinical validation, or a final test set.

The author did not call the retrieval search function or inspect rankings for
these queries while constructing the file. The queries, target IDs, and notes
were frozen before their first retrieval evaluation. Their wording avoids the
three established diabetes/asthma demo questions and does not copy any normalized
question in the processed MedQuAD corpus. Here, normalization means lowercase
text with whitespace collapsed; zero exact overlap does not prove semantic
independence or absence of paraphrase similarity.

The source is the local MedQuAD-derived index built from upstream revision
`577bd37b96c02d1833b2c9eed2de9f96964e96cb`. Source attribution and data-use notes
remain in `DATA_SOURCES.md`. The judgments describe correspondence to archived
text; they do not verify that the medical content is current or correct.

## Row fields

| Field | Meaning |
| --- | --- |
| `id` | Stable identifier for this development query. |
| `question` | English query to send to the retrieval function. |
| `topic` | Topic used to summarize this deliberately small sample. |
| `intent` | Author-assigned information need, not a model prediction. |
| `relevant_record_ids` | Nonempty list of distinct, known relevant indexed record IDs. |
| `relevance_note` | Short justification based on the archived answer content. |

## Evaluation unit and incomplete judgments

The evaluation unit is an indexed question-answer **record**, identified by `id`.
A matching URL alone is not a hit: multiple records can share one source page
while containing different answer sections. A page that discusses treatment
does not make every record from that page a treatment answer. The current search
function still returns at most one record per exact URL; evaluate its actual
returned records without replacing them with a more relevant section.

Relevance is based on the **full archived answer** attached to that record.
The browser displays a shortened preview, so a target-record hit does not prove
that the visible preview includes the relevant passage. Preview completeness,
live destination content, and source-link availability require separate checks.

The relevant-record lists are **partial**, not exhaustive. The author inspected
a bounded set of records for the selected topics, not every possible supporting
answer in the 16,377-record index. Multiple IDs are included when the inspected
answers clearly support the same query, even if their source question types
differ. A record omitted from the list is unjudged for scoring purposes, not
clinically wrong or proven irrelevant.

Report the fraction of queries with a known-relevant hit in the first k results
and the reciprocal rank of the first such hit. Label these as measurements
against **known relevant records**. A query with no marked hit may still retrieve
an unjudged relevant record. Do not present these scores as complete retrieval
precision or recall, classifier accuracy, medical accuracy, or population-level
performance. Twenty-four hand-authored examples do not support those claims.

## Versioning and use

Keep v1 frozen after scoring. Log its SHA-256 with the index hash and results.
Use its errors to guide development and document any tuning that uses them.
If a judgment needs correction or coverage expansion, create a new version with
the reason recorded; do not retroactively relabel v1 to improve reported scores.
Any model or retriever selected using these examples needs separate, untouched
evaluation data before making claims about generalization.
