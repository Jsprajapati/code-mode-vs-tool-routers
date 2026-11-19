# Department collision evaluation

400 runs. Tokens are chars/4 estimates; router_llm includes its own LLM call.

## haiku: overall by strategy and catalog size

| strategy | 15 tools: correct | 50 tools: correct | 150 tools: correct | avg input tokens (all sizes) | avg turns | wrong-department calls | tool errors |
|---|---|---|---|---|---|---|---|
| All tools | 12/12 | 14/14 | 14/14 | 20,858 | 2.7 | 0 | 6 |
| Router (BM25) | 8/12 | 10/14 | 10/14 | 3,064 | 3.4 | 3 | 6 |
| Router (BM25 + dept + LLM) | 12/12 | 14/14 | 14/14 | 3,609 | 2.7 | 0 | 6 |
| Tool search | 12/12 | 13/14 | 12/14 | 4,411 | 3.8 | 0 | 6 |
| Code Mode (stubs) | 10/12 | 13/14 | 12/14 | 8,516 | 3.2 | 0 | 13 |
| Code Mode (search+exec) | 10/12 | 12/14 | 11/14 | 5,495 | 5.1 | 12 | 18 |
| Code Mode (stubs) + return types | 11/12 | 12/14 | 12/14 | 6,170 | 2.5 | 0 | 12 |
| Code Mode (search+exec) + return types | 10/12 | 12/14 | 12/14 | 3,172 | 4.0 | 6 | 10 |
| Code Mode (stubs) + return types + param docs | 12/12 | 13/14 | 12/14 | 7,933 | 2.4 | 0 | 15 |
| Code Mode (search+exec) + return types + param docs | 12/12 | 13/14 | 13/14 | 3,092 | 3.9 | 0 | 9 |

### haiku, 15 tools: correct per scenario (all repeats)

| strategy | D1 | D2 | D3 | D4 | D5 | D6 |
|---|---|---|---|---|---|---|
| All tools | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 |
| Router (BM25) | 2/2 | 2/2 | 2/2 | 0/2 | 0/2 | 2/2 |
| Router (BM25 + dept + LLM) | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 |
| Tool search | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 |
| Code Mode (stubs) | 2/2 | 2/2 | 0/2 | 2/2 | 2/2 | 2/2 |
| Code Mode (search+exec) | 2/2 | 2/2 | 0/2 | 2/2 | 2/2 | 2/2 |
| Code Mode (stubs) + return types | 2/2 | 2/2 | 1/2 | 2/2 | 2/2 | 2/2 |
| Code Mode (search+exec) + return types | 2/2 | 2/2 | 0/2 | 2/2 | 2/2 | 2/2 |
| Code Mode (stubs) + return types + param docs | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 |
| Code Mode (search+exec) + return types + param docs | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 |

### haiku, 50 tools: correct per scenario (all repeats)

| strategy | D1 | D2 | D3 | D4 | D5 | D6 | D7 |
|---|---|---|---|---|---|---|---|
| All tools | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 |
| Router (BM25) | 2/2 | 2/2 | 2/2 | 0/2 | 0/2 | 2/2 | 2/2 |
| Router (BM25 + dept + LLM) | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 |
| Tool search | 2/2 | 2/2 | 2/2 | 1/2 | 2/2 | 2/2 | 2/2 |
| Code Mode (stubs) | 2/2 | 2/2 | 1/2 | 2/2 | 2/2 | 2/2 | 2/2 |
| Code Mode (search+exec) | 2/2 | 2/2 | 0/2 | 2/2 | 2/2 | 2/2 | 2/2 |
| Code Mode (stubs) + return types | 2/2 | 2/2 | 0/2 | 2/2 | 2/2 | 2/2 | 2/2 |
| Code Mode (search+exec) + return types | 2/2 | 2/2 | 0/2 | 2/2 | 2/2 | 2/2 | 2/2 |
| Code Mode (stubs) + return types + param docs | 2/2 | 2/2 | 1/2 | 2/2 | 2/2 | 2/2 | 2/2 |
| Code Mode (search+exec) + return types + param docs | 2/2 | 2/2 | 1/2 | 2/2 | 2/2 | 2/2 | 2/2 |

### haiku, 150 tools: correct per scenario (all repeats)

| strategy | D1 | D2 | D3 | D4 | D5 | D6 | D7 |
|---|---|---|---|---|---|---|---|
| All tools | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 |
| Router (BM25) | 2/2 | 2/2 | 2/2 | 0/2 | 0/2 | 2/2 | 2/2 |
| Router (BM25 + dept + LLM) | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 |
| Tool search | 2/2 | 2/2 | 2/2 | 1/2 | 1/2 | 2/2 | 2/2 |
| Code Mode (stubs) | 2/2 | 2/2 | 0/2 | 2/2 | 2/2 | 2/2 | 2/2 |
| Code Mode (search+exec) | 2/2 | 2/2 | 0/2 | 2/2 | 1/2 | 2/2 | 2/2 |
| Code Mode (stubs) + return types | 2/2 | 2/2 | 0/2 | 2/2 | 2/2 | 2/2 | 2/2 |
| Code Mode (search+exec) + return types | 2/2 | 2/2 | 0/2 | 2/2 | 2/2 | 2/2 | 2/2 |
| Code Mode (stubs) + return types + param docs | 2/2 | 2/2 | 0/2 | 2/2 | 2/2 | 2/2 | 2/2 |
| Code Mode (search+exec) + return types + param docs | 2/2 | 2/2 | 1/2 | 2/2 | 2/2 | 2/2 | 2/2 |

### haiku: average total input tokens per run, by size

| strategy | 15 tools | 50 tools | 150 tools |
|---|---|---|---|
| All tools | 6,182 | 12,224 | 42,072 |
| Router (BM25) | 3,109 | 2,853 | 3,236 |
| Router (BM25 + dept + LLM) | 3,857 | 3,470 | 3,535 |
| Tool search | 4,681 | 4,469 | 4,121 |
| Code Mode (stubs) | 3,866 | 6,221 | 14,797 |
| Code Mode (search+exec) | 6,751 | 5,037 | 4,878 |
| Code Mode (stubs) + return types | 2,668 | 4,896 | 10,447 |
| Code Mode (search+exec) + return types | 2,380 | 3,057 | 3,966 |
| Code Mode (stubs) + return types + param docs | 2,702 | 5,722 | 14,627 |
| Code Mode (search+exec) + return types + param docs | 2,900 | 3,178 | 3,172 |

### haiku: failures

- 15 tools D3/code_mode rep0: wrong answer: model said '{"approved": ["IT-010", "IT-022", "IT-030", "IT-032"], "hr_pending": 2'; last tool output '{"approved": ["IT-010", "IT-022", "IT-030", "IT-032"], "hr_pending": 25}\n'
- 15 tools D4/router rep0: wrong answer: model said 'Unable to determine. I retrieved all 56 pending finance requests acros'; last tool output '{"requests":[{"id":"FIN-137","requester":"Lena Fischer","status":"pending","kind":"
- 15 tools D3/code_mode_search rep0: wrong answer: model said '{"approved": ["IT-010", "IT-022", "IT-030", "IT-032"], "hr_pending": 2'; last tool output '{"it_status": {"IT-010": {"status": "pending", "system": "CRM"}, "IT-022": {"status
- 15 tools D3/code_mode rep1: wrong answer: model said '{"approved": ["IT-010", "IT-022", "IT-030", "IT-032"], "hr_pending": 2'; last tool output '{"approved": ["IT-010", "IT-022", "IT-030", "IT-032"], "hr_pending": 25}\n'
- 15 tools D3/code_mode_search rep1: wrong answer: model said '{"approved": ["IT-010", "IT-022", "IT-030", "IT-032"], "hr_pending": 2'; last tool output '{"approved": ["IT-010", "IT-022", "IT-030", "IT-032"], "hr_pending": 25}\n'
- 15 tools D4/router rep1: wrong answer: model said '{"names": [], "error": "Cannot determine. The finance list tool return'; last tool output '{"requests":[{"id":"FIN-137","requester":"Lena Fischer","status":"pending","kind":"
- 50 tools D4/router rep0: wrong answer: model said "I can't determine this. The finance list tool returns pending requests"; last tool output '{"requests":[{"id":"FIN-002","requester":"Marcus Lee","status":"pending","kind":"pu
- 50 tools D3/code_mode rep0: wrong answer: model said '{"approved": ["IT-010", "IT-022", "IT-030", "IT-032"], "hr_pending": 2'; last tool output '[{"id": "IT-010", "type": "access", "system": "CRM", "status": "pending"}, {"id": "
- 50 tools D3/code_mode_search rep0: wrong answer: model said '{"approved": ["IT-010", "IT-022", "IT-030", "IT-032"], "hr_pending": 2'; last tool output '{"approved": ["IT-010", "IT-022", "IT-030", "IT-032"], "errors": [], "it_crm_seen":
- 50 tools D3/code_mode_search rep1: wrong answer: model said '{"approved": ["IT-010", "IT-022", "IT-030", "IT-032"], "hr_pending": 2'; last tool output '{"approved": ["IT-010", "IT-022", "IT-030", "IT-032"], "hr_pending": 25, "errors": 
- 50 tools D4/router rep1: wrong answer: model said '{"names": null, "error": "No tool for finance requests is available in'; last tool output '[{"id":"LEG-002","requester":"Nora Quinn","counterparty":"Zenith Corp","status":"pe
- 50 tools D4/tool_search rep1: wrong answer: model said '{"names": [], "error": "Cannot determine. finance_list_requests return'; last tool output '{"requests":[{"id":"FIN-002","requester":"Marcus Lee","status":"pending","kind":"pu
- 150 tools D3/code_mode rep0: wrong answer: model said '{"approved": ["IT-010", "IT-022", "IT-030", "IT-032"], "hr_pending": 2'; last tool output '{"it_pending_total": 12, "crm_candidates": ["IT-010", "IT-022", "IT-030", "IT-032"]
- 150 tools D3/code_mode_search rep0: wrong answer: model said '{"approved": ["IT-010", "IT-022", "IT-030", "IT-032"], "hr_pending": 2'; last tool output '{"approved": ["IT-010", "IT-022", "IT-030", "IT-032"], "errors": [], "hr_pending": 
- 150 tools D4/router rep0: wrong answer: model said '{"names": null, "error": "Cannot determine which requesters exceed $6,'; last tool output '{"requests":[{"id":"FIN-137","requester":"Lena Fischer","status":"pending","kind":"
- 150 tools D4/tool_search rep0: wrong answer: model said 'Unable to determine. The pending finance list returns requests without'; last tool output '{"requests":[{"id":"FIN-002","requester":"Marcus Lee","status":"pending","kind":"pu
- 150 tools D3/code_mode rep1: wrong answer: model said '{"approved": ["IT-010", "IT-022", "IT-030", "IT-032"], "hr_pending": 2'; last tool output '{"it_pending_crm_found": 4, "approved": ["IT-010", "IT-022", "IT-030", "IT-032"], "
- 150 tools D3/code_mode_search rep1: wrong answer: model said '{"approved": ["IT-010", "IT-022", "IT-030", "IT-032"], "hr_pending": 2'; last tool output '{"approved": ["IT-010", "IT-022", "IT-030", "IT-032"], "hr_pending": 25, "errors": 
- 150 tools D4/router rep1: wrong answer: model said "I can't answer this from the available tools. The finance list returns"; last tool output '{"requests":[{"id":"FIN-137","requester":"Lena Fischer","status":"pending","kind":"
- 15 tools D5/router rep0: wrong answer: model said "I can't calculate this. The approved hardware requests list returns 16"; last tool output '{"requests":[{"id":"FIN-013","requester":"Nora Quinn","status":"approved","kind":"p
- 15 tools D5/router rep1: wrong answer: model said 'Unable to compute. The list shows 16 approved hardware requests (FIN-0'; last tool output '{"requests":[{"id":"FIN-013","requester":"Nora Quinn","status":"approved","kind":"p
- 50 tools D5/router rep0: wrong answer: model said "I can't compute this average. The finance_list_requests tool returns o"; last tool output '{"requests":[{"id":"FIN-013","requester":"Nora Quinn","status":"approved","kind":"p
- 50 tools D5/router rep1: wrong answer: model said "I can't compute this average. The list shows 16 approved Finance hardw"; last tool output '{"requests":[{"id":"FIN-013","requester":"Nora Quinn","status":"approved","kind":"p
- 150 tools D5/router rep0: wrong answer: model said "I can't calculate this average. The list endpoint returned 16 approved"; last tool output '{"requests":[{"id":"FIN-013","requester":"Nora Quinn","status":"approved","kind":"p
- 150 tools D5/router rep1: wrong answer: model said "I can't compute this. The list shows 16 approved hardware requests (FI"; last tool output '{"requests":[{"id":"FIN-013","requester":"Nora Quinn","status":"approved","kind":"p
- 150 tools D5/tool_search rep1: wrong answer: model said "I couldn't compute this. The list shows 16 approved hardware requests "; last tool output '{"requests":[{"id":"FIN-013","requester":"Nora Quinn","status":"approved","kind":"p
- 150 tools D5/code_mode_search rep1: wrong answer: model said 'No qualifying requests were found, so there is no average to round. I '; last tool output '{"pages_meta": [{"page": 2, "total_pages": 2}], "total_fetched": 150, "keys": ["cat
- 15 tools D3/code_mode_search_typed rep0: wrong answer: model said '{"approved": ["IT-010", "IT-022", "IT-030", "IT-032"], "hr_pending": 2'; last tool output '{"approved": ["IT-010", "IT-022", "IT-030", "IT-032"], "hr_pending": 25, "failed": 
- 15 tools D3/code_mode_typed rep1: wrong answer: model said '{"approved": ["IT-010", "IT-022", "IT-030", "IT-032"], "hr_pending": 2'; last tool output '{"approved": ["IT-010", "IT-022", "IT-030", "IT-032"], "hr_pending": 25}\n'
- 15 tools D3/code_mode_search_typed rep1: wrong answer: model said '{"approved": ["IT-010", "IT-022", "IT-030", "IT-032"], "hr_pending": 2'; last tool output '{"approved": ["IT-010", "IT-022", "IT-030", "IT-032"], "failed": [], "hr_pending": 
- 50 tools D3/code_mode_typed rep0: wrong answer: model said '{"approved": ["IT-010", "IT-022", "IT-030", "IT-032"], "hr_pending": 2'; last tool output '{"approved": ["IT-010", "IT-022", "IT-030", "IT-032"], "failed": [], "hr_pending": 
- 50 tools D3/code_mode_search_typed rep0: wrong answer: model said '{"approved": ["IT-010", "IT-022", "IT-030", "IT-032"], "hr_pending": 2'; last tool output '{"approved": ["IT-010", "IT-022", "IT-030", "IT-032"], "failed": [], "crm_pending_s
- 50 tools D3/code_mode_typed rep1: wrong answer: model said '{"approved": ["IT-010", "IT-022", "IT-030", "IT-032"], "hr_pending": 2'; last tool output '{"approved": ["IT-010", "IT-022", "IT-030", "IT-032"], "hr_pending": 25}\n'
- 50 tools D3/code_mode_search_typed rep1: wrong answer: model said '{"approved": ["IT-010", "IT-022", "IT-030", "IT-032"], "hr_pending": 2'; last tool output '{"approved": ["IT-010", "IT-022", "IT-030", "IT-032"], "hr_pending": 25, "failed": 
- 150 tools D3/code_mode_typed rep0: wrong answer: model said '{"approved": ["IT-010", "IT-022", "IT-030", "IT-032"], "hr_pending": 2'; last tool output '{"approved": ["IT-010", "IT-022", "IT-030", "IT-032"], "failed": [], "hr_pending": 
- 150 tools D3/code_mode_search_typed rep0: wrong answer: model said '{"approved": ["IT-010", "IT-022", "IT-030", "IT-032"], "hr_pending": 2'; last tool output '{"hr_pending": 25, "raw_count": 25}\n'
- 150 tools D3/code_mode_typed rep1: wrong answer: model said '{"approved": ["IT-010", "IT-022", "IT-030", "IT-032"], "hr_pending": 2'; last tool output '{"approved": ["IT-010", "IT-022", "IT-030", "IT-032"], "failed": [], "crm_candidate
- 150 tools D3/code_mode_search_typed rep1: wrong answer: model said '{"approved": ["IT-010", "IT-022", "IT-030", "IT-032"], "hr_pending": 2'; last tool output '{"approved": ["IT-010", "IT-022", "IT-030", "IT-032"], "hr_pending": 25}\n'
- 50 tools D3/code_mode_full rep0: wrong answer: model said '{"approved": ["IT-010", "IT-022", "IT-030", "IT-032"], "hr_pending": 2'; last tool output '{"approved": ["IT-010", "IT-022", "IT-030", "IT-032"], "hr_pending": 25}\n'
- 50 tools D3/code_mode_search_full rep0: wrong answer: model said '{"approved": ["IT-010", "IT-022", "IT-030", "IT-032"], "hr_pending": 2'; last tool output '{"approvals": [{"ok": true, "id": "IT-010", "status": "approved"}, {"ok": true, "id
- 150 tools D3/code_mode_full rep0: wrong answer: model said '{"approved": ["IT-010", "IT-022", "IT-030", "IT-032"], "hr_pending": 2'; last tool output '{"approved": ["IT-010", "IT-022", "IT-030", "IT-032"], "hr_pending": 25, "failed": 
- 150 tools D3/code_mode_search_full rep0: wrong answer: model said '{"approved": ["IT-010", "IT-022", "IT-030", "IT-032"], "hr_pending": 2'; last tool output '{"approved": ["IT-010", "IT-022", "IT-030", "IT-032"], "hr_pending": 25, "failed": 
- 150 tools D3/code_mode_full rep1: wrong answer: model said '{"approved": ["IT-010", "IT-022", "IT-030", "IT-032"], "hr_pending": 2'; last tool output '{"approved": ["IT-010", "IT-022", "IT-030", "IT-032"], "hr_pending": 25}\n'

