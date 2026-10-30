# Part 9 spec: knowledge base (search for agents)

Goal: agents can look up accurate facts about products and policies.

Done when: a set of test questions returns the right products and policy passages, measured,
not eyeballed. `app/search_evals.py` holds 18 product questions and 20 knowledge questions,
each with its right answers, and scores hit@1, hit@5 and MRR.
`python -m app.cli search-evals` prints the scores and every miss. CI runs it with the built-in
stand-in embedder and fails if the scores drop below a floor (`tests/test_search.py`).

| Embedder | Products hit@5 | Products MRR | Knowledge hit@5 | Knowledge MRR |
| --- | --- | --- | --- | --- |
| Hashing stand-in (no account) | 83% | 0.75 | 90% | 0.72 |
| Voyage `voyage-3.5-lite` | to measure once a key is set | | | |

## How search works

- **Embeddings.** `app/embeddings.py` turns text into 1024-number vectors, using Voyage AI when `VOYAGE_API_KEY` is set. Otherwise it uses a hashing stand-in that matches words and spellings, not meaning, for development and tests.
- **Storage.** pgvector in the existing Postgres, with HNSW indexes for cosine distance.
  - `product_vectors`: one row per product, holding the text it's found by (name, description, occasions, recipients) and its vector.
  - `knowledge_documents` and `knowledge_chunks`: one row per passage, with a vector and a full-text index.
- **Hybrid ranking.** Each search ranks by vector similarity and by Postgres full-text search (any of the words, English stemming), then merges the two lists with reciprocal rank fusion. Keyword search on products runs on the products themselves, so a new product is found by name before it's indexed.
- **Filters.** Applied before ranking, so they always hold: active only, in stock (`on_hand - reserved > 0`, on by default), min and max price, occasion and recipient tags (by name or slug).

## Knowledge

Markdown files in `backend/knowledge/`:

| Folder | What |
| --- | --- |
| `policies/` | Delivery, returns, privacy and terms: the storefront's policy pages as text |
| `faq/` | Orders and payment, gifts |
| `guides/` | Birthday gifts; gifts for Sri Lankan occasions |
| `suppliers/` | Supplier documents, to be added when there are some |

Each `## Heading` is a passage, and long sections are split at paragraphs. Each passage is
embedded with its document title and heading, so it makes sense on its own. Prices and the
stock hold time are written as `{placeholders}`, filled in from the API's settings. A test checks
that the policy files have the same headings as the storefront pages, and that the numbers on
the storefront (`frontend/src/lib/shop.ts`) match the settings and the files.

## Tools

| Tool | Who | Input | Returns |
| --- | --- | --- | --- |
| `search_products` | anyone | query, min and max price, occasion, recipient, in stock only (default yes) | Up to 5 products: id, name, link, price, in stock, description, occasions, recipients |
| `search_knowledge` | anyone | question, optional kind (policies, faq, guides, suppliers) | Up to 4 passages: document, section, text, storefront link |

Both are `auto` tools. `search_products` replaces Part 8's simpler version, and the test
agent gains `search_knowledge`.

## Re-indexing

The worker updates the index every minute. A product or passage is embedded again only when its
text, or the embedding model, changes, which a hash of the two detects. That covers console
edits, imports, tag changes and deploys that change the knowledge files. A file that's removed
is dropped from the index. A problem with the embeddings service is logged and doesn't stop
the worker's order jobs. `python -m app.cli index-search` runs the same update by hand.

## Left for later

- Supplier documents, once there are some.
- Editing FAQs and guides in the console rather than in files.
