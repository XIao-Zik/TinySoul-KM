# Knowledge Search

Use source + steps + page over km: documents. source must be a JSON object (never a string), e.g. {"kind": "query", "scope": "all", "query": "..."}. Query finds original-text matches (Chinese and English); scope "all" or one of "obsidian", "chat", "card", "workspace". A query must be a non-empty single line. Use directory to enumerate, refs for exact known km: refs or line fragments (km:...#L10-L20), backlinks for real incoming km_links edges of one anchor, and result to reuse a previous result.

Optional filter (where: source, tag, updated_on), select and rerank steps constrain or order candidates. Results include km: refs and real content previews with locations; continuation reads the remaining frozen members of the same snapshot. A scope_required failure calls for a narrower scope or filter and is not evidence of absence.
