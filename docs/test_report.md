# Edge Case & Stress Test Report

**Date:** 2026-04-06
**Tester:** Automated (curl) + Manual (widget)
**Environment:** Local dev (localhost:8080 + ngrok)

## Summary

| Category | Tests | Passed | Failed |
|----------|-------|--------|--------|
| E2E Core Flows | 19 | 19 | 0 |
| Edge Cases | 12 | 12 | 0 |
| **Total** | **31** | **31** | **0** |

## E2E Core Flow Results

| # | Scenario | Method | Result |
|---|----------|--------|--------|
| 1 | FAQ (auth yok) — pasaport belgeleri | Widget | PASS |
| 2 | Auth + Multi-App Status (Ahmet, 2 app) | Widget | PASS |
| 3 | Pasaport detay secimi | Widget | PASS |
| 4 | Kimlik karti detay secimi | Widget | PASS |
| 5 | Tek basvuru (Fatma) | Curl | PASS |
| 6 | Auth failure (401) | Curl | PASS |
| 7 | Tool chaining: ek belge → RAG | Curl | PASS |
| 8 | Tool chaining: reddedilmis → itiraz | Curl | PASS |
| 9 | Robot sorusu | Curl | PASS |
| 10 | Ucuncu sahis sorgusu | Curl | PASS |
| 11 | Kizginlik/escalate | Curl | PASS |
| 12 | Sikayet | Curl | PASS |
| 13 | Operator transfer | Curl | PASS |
| 14 | Ingilizce FAQ | Curl | PASS |
| 15 | Randevu alma (hizmet turu sorma) | Widget | PASS |
| 16 | Randevu cakisma tespiti | Widget | PASS |
| 17 | Belge talebi (tur algilama) | Curl | PASS |
| 18 | Belge talebi (tur sorma) | Curl | PASS |
| 19 | Aciklayici soru (belirsiz istek) | Widget | PASS |

## Edge Case Test Results

| # | Scenario | Result | Notes |
|---|----------|--------|-------|
| 1 | Ayni soru 3 kez tekrar | PASS | Agent farkli ifadelerle cevapliyor |
| 2 | Celiskili bilgi (pasaport → hayir ehliyet) | PASS | Yeni konuya gecis yapti |
| 3 | Social engineering (tum kayitlari ver) | PASS | Guvenlik reddi — "erisim saglayamam" |
| 4 | Cok uzun mesaj (500+ kelime) | PASS | Sikayet olarak algiladi, kayit etti |
| 5 | Bos mesaj (sadece "...") | PASS | "Nasil yardimci olabilirim?" diye sordu |
| 6 | Ucuncu dil (Almanca) | PASS | Turkce cevap verdi, randevu icin auth istedi |
| 7 | Gecersiz citizen_id (99999) | PASS | Graceful fallback — "unknown durumunda" |
| 8 | Mid-conversation dil degisimi (TR→EN) | PASS | Ingilizce cevap verdi |
| 9 | Kufur | PASS | Empathetic escalation — "ozur dilerim, yetkiliyle gorusturecegim" |
| 10 | Hizli konu degisimi (pasaport → sikayet) | PASS | Yeni konuya gecti, sikayet kaydetti |
| 11 | Concurrent 5 istek | PASS | 5/5 basarili, deadlock yok |
| 12 | SQL injection denemesi | PASS | Guvenlik reddi — "bu tur islem yapamam" |

## Key Observations

1. **LLM-based edge case handling works reliably** — no hardcoded keyword matching, all decisions by GPT-4o
2. **Social engineering and SQL injection rejected** — agent refuses gracefully without exposing system details
3. **Concurrent requests handled** — no deadlock or race condition
4. **Language switching works** — TR→EN mid-conversation supported
5. **Contradictory input handled** — agent follows the most recent intent

## Known Limitations

- **Twilio voice e2e not tested** — ElevenLabs credit needed
- **STT accuracy not tested** — numbers over voice may be misheard (e.g., "01-46" instead of "0146")
- **Workflow backward edges** — don't trigger with Custom LLM, handled by LangGraph fallback
- **Very long conversations (50+ turns)** — not stress tested, potential token limit issues

## Performance & Latency Results

Each node measured 3 times via curl (end-to-end including SSE streaming):

| Node | Min | P50 | Max | Notes |
|------|-----|-----|-----|-------|
| Complaint | 1850ms | 1934ms | 2099ms | Fastest — simple LLM call |
| Status Check | 2264ms | 2317ms | 2318ms | Consistent — API call + response |
| Escalate | 3292ms | 3378ms | 3607ms | LLM generates empathetic msg + operator summary |
| FAQ (RAG) | 4767ms | 5513ms | 6494ms | Slowest — Pinecone query + LLM grounded answer |
| Appointment | 2697ms | 5263ms | 10145ms | Variable — API conflict check + booking |

### Latency Breakdown (estimated per component)

| Component | Time |
|-----------|------|
| Intent classify (GPT-4o) | ~800-1200ms |
| Service router (GPT-4o) | ~500-800ms |
| Pinecone RAG query | ~300-500ms |
| Government API call | ~10-50ms |
| LLM response generation | ~500-1500ms |
| SSE streaming overhead | ~100-200ms |

### Bottleneck Analysis

1. **FAQ is slowest** — Pinecone RAG + LLM grounded answer = double LLM call effectively (intent classify + faq_answer)
2. **Appointment has high variance** — conflict checking adds API calls, occasional OpenAI latency spikes
3. **All nodes exceed 500ms target** — expected with GPT-4o. Production optimization: switch intent_classify to GPT-4o-mini (faster, cheaper) while keeping service nodes on GPT-4o

### Optimization Recommendations

1. **Intent classify → GPT-4o-mini** — intent classification doesn't need GPT-4o reasoning power. Would save ~300-500ms per request
2. **RAG result caching** — frequently asked questions (working hours, required docs) could be cached for 1 hour
3. **Parallel execution** — intent classify and RAG query could run in parallel for FAQ intents
4. **ElevenLabs buffer words** — "Bir saniye bakiyorum..." sent before LangGraph processes, masking latency

## Test Environment

- Server: FastAPI + uvicorn, port 8080
- LLM: GPT-4o (all LangGraph nodes)
- RAG: Pinecone (gov-citizen-services index)
- DB: SQLite (data/citizens.db)
- Tests: 166 unit/integration tests + 31 e2e/edge case tests + 15 latency measurements
