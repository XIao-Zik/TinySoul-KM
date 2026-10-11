# Knowledge

The knowledge store (km) holds externally imported personal knowledge: Obsidian/Markdown notes under km: refs, chat session exports, and generated knowledge cards. Use km.search to discover evidence with query/backlinks/directory/refs combined with filter/select/rerank; results carry km: refs, real content previews, and real backlink edges from km_links. Use memory.search for facts the Agent itself has committed to Memory — external notes live in km, Agent-owned memory lives in memory.

A backlinks query on km.search returns only documents whose km_links actually resolve to the anchor. Source attributes (source: obsidian/chat/card, tag, updated_on) support filter steps. Card documents are derived daily digests; when a card and its source note disagree, prefer the source note. km documents are read-only through actions: import and card generation happen through km-ingest and the daily reflection, not through Turn actions.
