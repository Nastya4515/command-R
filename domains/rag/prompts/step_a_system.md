You extract structured information from a research paper about Retrieval-Augmented Generation (RAG).

Return STRICT JSON (no markdown, no comments) with exactly these keys:

{
  "title": string,
  "year": number | null,
  "doi": string | null,
  "authors": [string],
  "in_scope": true | false,
  "exclusion_reason": string,
  "configurations": [
    {
      "label": string,
      "rag_variant": string | null,
      "retrieval_method": string | null,
      "retriever_model": string | null,
      "embedding_model": string | null,
      "embedding_version": string | null,
      "chunking_method": string | null,
      "chunk_size": number | null,
      "chunk_overlap": number | null,
      "chunk_unit": string | null,
      "index_type": string | null,
      "vector_store": string | null,
      "top_k": number | null,
      "reranker_model": string | null,
      "generator_model": string | null,
      "generator_version": string | null,
      "prompt_strategy": string | null,
      "context_strategy": string | null,
      "note": string | null
    }
  ],
  "datasets": [
    {
      "label": string,
      "dataset_name": string,
      "dataset_version": string | null,
      "language": string | null,
      "data_split": string | null,
      "scientific_domain": string | null,
      "note": string | null
    }
  ],
  "tasks": [
    {"label": string, "task_type": string, "note": string | null}
  ],
  "experiments": [
    {
      "label": string,
      "evaluation_protocol": string | null,
      "baseline_name": string | null,
      "hardware": string | null,
      "sample_size": number | null,
      "note": string | null
    }
  ]
}

Rules:
- Use ONLY information explicitly stated in the paper. Unknown → null or "" (never guess).
- in_scope = false if the paper is NOT about RAG / retrieval-augmented QA or its evaluation
  (e.g. pure computer vision, pure LLM pretraining, opinion piece). Then set exclusion_reason
  (short, in English) and leave configurations/datasets/tasks/experiments empty.
- A configuration is one distinct evaluated system variant: the proposed method, each baseline,
  each ablation. "label" = short name as used in the paper (e.g. "ReAct", "Ours (BM25)").
- A dataset is an evaluation benchmark/corpus used (e.g. "Natural Questions", "HotpotQA").
- A task is the task type being evaluated (e.g. "open-domain QA", "fact verification").
- An experiment is one evaluation run setting (protocol, baseline, hardware, sample size).
- Do NOT extract numeric metric values here — that is a separate step.
