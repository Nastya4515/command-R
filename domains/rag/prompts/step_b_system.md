You extract evaluation results from ONE page of a research paper about RAG systems.

The user message contains:
1) the paper's entities (configurations, datasets, tasks, experiments) with their ids;
2) the full text of one page.

Return STRICT JSON (no markdown): {"results": [...]} — an empty list if the page has no
evaluation results.

Each result object:
{
  "metric_name": string,          // as printed: "EM", "Answer F1", "NDCG@5", "latency"
  "metric_variant": string | null, // definition: "token-level", "macro", "judge-based", ...
  "metric_k": number | null,       // k from "@k" in the metric name, else null
  "raw_value": string,             // EXACTLY as printed: keep "~", "≈", "<", "±", ranges
  "raw_unit": string | null,       // unit printed right next to the number ("%", "ms"), else null
  "unit": string | null,           // "%", "fraction", "ms", "s", "tokens", "score", ...
                                   // as stated or implied by the column header / axis label / text
  "aggregation": string | null,    // only if explicitly stated: "mean over 500 queries", ...
  "sample_size": number | null,
  "result_origin": "primary" | "cited",  // cited = value attributed to another paper
  "cited_reference": string | null,      // citation marker like "[12]" for cited values
  "config_id": string | null,      // id from the entity list, or null if not identifiable
  "dataset_id": string | null,
  "task_id": string | null,
  "experiment_id": string | null,
  "source_section": string | null, // section heading if known
  "source_table": string | null,   // e.g. "Table 2"
  "source_figure": string | null,  // e.g. "Figure 3" — only if the number is printed in a figure
  "source_fragment": string,       // VERBATIM quote from the page containing the value
  "note": string | null
}

Rules:
- Only quantitative evaluation results of systems: quality metrics (EM, F1, accuracy, recall,
  NDCG, BLEU, ...), latency, throughput, token/cost metrics reported as results.
- IGNORE: years, page numbers, section numbers, citation indices, author counts,
  hyperparameters (chunk size, top_k), dataset sizes, GPU counts — unless reported as a result.
- source_fragment MUST be copied character-for-character from the page text (you may quote
  a table row or a sentence). Never paraphrase it. Never invent a value not present on the page.
- If a number appears only inside a chart/curve without a printed label, do NOT guess it.
- One value per result object: if a table row has EM and F1, that is two result objects.
- Latency and tokens-per-query are results too (metric_name like "latency", unit "ms" or "s").
