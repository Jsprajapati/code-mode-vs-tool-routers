# Department collision evaluation

147 runs. Tokens are chars/4 estimates; router_llm includes its own LLM call.

## haiku: overall by strategy and catalog size

| strategy | 500 tools: correct | avg input tokens (all sizes) | avg turns | wrong-department calls | tool errors |
|---|---|---|---|---|---|
| All tools | 3/3 | 119,027 | 2.3 | 0 | 0 |
| Router (BM25) | 29/36 | 19,247 | 4.0 | 0 | 2 |
| Router (BM25 + dept + LLM) | 34/36 | 8,302 | 3.1 | 0 | 2 |
| Tool search | 33/36 | 9,145 | 4.1 | 0 | 2 |
| Code Mode (search+exec) | 36/36 | 2,365 | 3.4 | 0 | 5 |

### haiku, 500 tools: correct per scenario (all repeats)

| strategy | C1 | C2_100 | C2_20 | C2_200 | C2_5 | C2_50 | C3 | C4 | C5 | D1 | D2 | D3 | D4 | D5 | D6 | D7 | R1 | R3 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| All tools | - | - | 1/1 | - | - | - | - | - | - | - | 1/1 | - | - | - | - | - | - | 1/1 |
| Router (BM25) | 1/2 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 0/2 | 0/2 | 2/2 | 2/2 | 0/2 | 2/2 |
| Router (BM25 + dept + LLM) | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 0/2 | 2/2 |
| Tool search | 1/2 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 1/2 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 1/2 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 |
| Code Mode (search+exec) | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 |

### haiku: average total input tokens per run, by size

| strategy | 500 tools |
|---|---|
| All tools | 119,027 |
| Router (BM25) | 19,247 |
| Router (BM25 + dept + LLM) | 8,302 |
| Tool search | 9,145 |
| Code Mode (stubs) | - |
| Code Mode (search+exec) | 2,365 |
| Code Mode (stubs) + return types | - |
| Code Mode (search+exec) + return types | - |
| Code Mode (stubs) + return types + param docs | - |
| Code Mode (search+exec) + return types + param docs | - |

### haiku: failures

- 500 tools D4/router rep0: wrong answer: model said "I can't determine this yet. The finance list tool returns request IDs,"; last tool output '{"requests":[{"id":"FIN-002","requester":"Marcus Lee","status":"pending","kind":"pu
- 500 tools D5/router rep0: wrong answer: model said "I can't compute this average. The approved hardware requests (16 total"; last tool output '{"period":"2026-10","rows":[{"id":"L-0001","vendor":"Acme Holdings","category":"tra
- 500 tools R1/router_llm rep0: wrong answer: model said '["FAC-015","IT-020","LEG-025","LEG-028"]'; last tool output '[{"id":"FAC-015","requester":"Ivan Petrov","building":"Lab","type":"desk","status":"pendin'
- 500 tools R1/router rep0: wrong answer: model said '["FAC-015","LEG-025","LEG-028"]'; last tool output '[{"id":"FAC-015","requester":"Ivan Petrov","building":"Lab","type":"desk","status":"pendin'
- 500 tools D4/router rep1: wrong answer: model said "I can't determine which requesters exceed $6,000. The finance list too"; last tool output '{"requests":[{"id":"FIN-002","requester":"Marcus Lee","status":"pending","kind":"pu
- 500 tools D4/tool_search rep1: wrong answer: model said 'Unable to determine. The finance list tool does not return amounts, an'; last tool output '{"requests":[{"id":"FIN-002","requester":"Marcus Lee","status":"pending","kind":"pu
- 500 tools D5/router rep1: wrong answer: model said '0'; last tool output '{"period":"2026-11","rows":[{"id":"L-0001","vendor":"Acme Holdings","category":"travel","a'
- 500 tools R1/router_llm rep1: wrong answer: model said '["FAC-015","IT-020","LEG-025","LEG-028"]'; last tool output '[{"id":"FAC-015","requester":"Ivan Petrov","building":"Lab","type":"desk","status":"pendin'
- 500 tools R1/router rep1: wrong answer: model said '["FAC-015","LEG-025","LEG-028"]'; last tool output '[{"id":"FAC-015","requester":"Ivan Petrov","building":"Lab","type":"desk","status":"pendin'
- 500 tools C1/router rep1: wrong answer: model said '{"count": 86, "total": 37729}'; last tool output '{"period":"2026-09","rows":[{"id":"L-0001","vendor":"Acme Holdings","category":"travel","a'
- 500 tools C1/tool_search rep1: wrong answer: model said '{"count": 86, "total": 37963}'; last tool output '{"period":"2026-09","rows":[{"id":"L-0001","vendor":"Acme Holdings","category":"travel","a'
- 500 tools C3/tool_search rep1: wrong answer: model said "I couldn't copy DOC-17 into a note on LEG-007. I can retrieve document"; last tool output '{"id":"DOC-17","title":"Master services agreement draft v3","text":"data confidenti

