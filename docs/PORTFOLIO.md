# Portfolio and resume

Use the wording below after installing this release, reproducing the checks, and pushing the repository. Describe this as a personal project, not a contribution to MedQuAD. A public source repository does not itself establish an upstream open-source contribution.

**HealthQuery — Medical Information Retrieval | Python, scikit-learn, FastAPI, Docker**

- Built an English medical-information retrieval application over 16,377 archived QA records from 5,476 source URLs, with a FastAPI service, browser UI, and source-linked results.
- Compared three TF-IDF retrieval designs; increased Hit@3 from 0.5833 to 0.6250 and MRR@3 from 0.4444 to 0.4792 on a frozen 24-query development set with partial relevance judgments.
- Implemented 54 automated tests, reproducible data/model pipelines, Docker packaging, and a GitHub Actions test-and-build workflow.

Use two or three bullets according to space. Do not describe the development results as medical accuracy or an independently validated benchmark. The 0.0417 Hit@3 change is about 4.2 percentage points, representing one additional query in this small set.

If you want a latency bullet, run the benchmark on your own machine and use its actual p95, sample count, and local sequential-request scope. Do not copy the reference Linux latency as a measurement of your Mac or a cloud service.

After the public Space runs and you verify it, you may add: "Deployed a containerized research demo on Hugging Face Spaces." Add that claim only after the deployment succeeds. Use the actual Space URL rather than a guessed address.

## A 60-second project explanation

“I built HealthQuery to explore medical-information retrieval with transparent sources. I prepared a pinned MedQuAD dataset, exposed lexical retrieval and an experimental classifier through an API and browser interface, and added reproducible tests and evaluation. A key finding was that perfect template-heavy validation did not transfer to paraphrases. I kept classification separate from ranking and compared three retrieval designs. The selected design found one additional labeled relevant result among 24 development queries, at a memory and latency cost. I documented those limits and packaged the system for repeatable deployment.”

## Demo outline

1. Open the app, enter `What causes asthma?`, and point to archived excerpts and their source links.
2. Show the experimental label and explain why it does not filter search results.
3. Show the three-method result table and explain Hit@3 with 14/24 versus 15/24.
4. Show a known failure case and the classifier paraphrase gap.
5. Show the tests, local latency report, Docker configuration, and actual CI run if it has completed.

A short screen recording and a reproducible repository are useful even without a hosted app. Record public example questions only. Explain code and decisions in your own words and credit MedQuAD as the dataset source.
