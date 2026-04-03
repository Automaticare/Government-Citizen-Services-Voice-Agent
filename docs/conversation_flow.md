# Conversation Flow Design

## State Diagram

```
                         ┌─────────────┐
                         │   GREETING   │
                         │  Karşılama   │
                         └──────┬──────┘
                                │
                                ▼
                     ┌──────────────────┐
                     │ LANGUAGE DETECT   │
                     │ Dil Algılama      │
                     └────────┬─────────┘
                              │
                              ▼
                   ┌─────────────────────┐
                   │  INTENT DETECTION    │◄──────────────────┐
                   │  İhtiyaç Belirleme   │                   │
                   └────┬────┬────┬──┬──┬─┬──┬───┘           │
                        │    │    │  │  │ │  │                │
          ┌─────────────┘    │    │  │  │ │  └──────────┐    │
          │         ┌────────┘    │  │  │ └─────┐       │    │
          │         │       ┌─────┘  │  │       │       │    │
          ▼         ▼       ▼        │  ▼       ▼       ▼    │
     ┌────────┐┌────────┐┌───────┐   │┌──────┐┌──────┐┌────┐│
     │ STATUS ││APPOINT-││DOCU-  │   ││ FEE  ││COMP- ││OUT ││
     │ CHECK  ││ MENT   ││MENT   │   ││QUERY ││LAINT ││OF  ││
     │        ││BOOKING ││REQUEST│   ││      ││      ││SCOP││
     └───┬────┘└───┬────┘└──┬────┘   │└──┬───┘└──┬───┘└─┬──┘│
         │         │        │        │   │       │      │   │
         │         │        │        │   │       │      │   │
         ▼         ▼        ▼        │   ▼       ▼      │   │
    ┌─────────────────────────┐      │ ┌─────────────┐  │   │
    │    AUTH REQUIRED?       │      │ │ NO AUTH     │  │   │
    │  Kimlik doğrulama       │      │ │ NEEDED      │  │   │
    │  gerekli mi?            │      │ └──────┬──────┘  │   │
    └─────┬──────┬────────────┘      │        │         │   │
       YES│     NO│                  │        │         │   │
          ▼      │                   │        │         │   │
    ┌───────────┐│                   │        │         │   │
    │   AUTH    ││                   │        │         │   │
    │  FLOW    ││                   │        │         │   │
    └──┬────┬──┘│                   │        │         │   │
   OK  │  FAIL│  │                   │        │         │   │
       │     ▼  │                   │        │         │   │
       │┌──────┐│                   │        │         │   │
       ││HUMAN ││                   ▼        │         │   │
       ││TRANS-││            ┌───────────┐   │         │   │
       ││FER   ││            │  HUMAN    │   │         │   │
       │└──────┘│            │  TRANSFER │◄──┼─────────┘   │
       │        │            └───────────┘   │             │
       ▼        ▼                            ▼             │
    ┌──────────────────────────────────────────┐           │
    │           SERVICE DELIVERY               │           │
    │         Hizmet Sunumu                    │           │
    └─────────────────┬────────────────────────┘           │
                      │                                    │
                      ▼                                    │
               ┌──────────────┐                            │
               │   CLOSING     │                           │
               │   Kapanış     │                           │
               └──┬────────┬──┘                            │
                  │        │                               │
          "Hayır" │        │ "Evet, başka bir şey var"     │
                  ▼        └───────────────────────────────┘
           ┌───────────┐
           │    END     │
           │  Görüşme   │
           │   Sonu     │
           └───────────┘
```

## Intent Routing Rules

| Intent | Auth Required | Tool Call | Fallback |
|--------|:---:|---|---|
| Başvuru durumu sorgulama | Yes | `check_application_status` | Operatöre bağla |
| Randevu alma | Yes | `book_appointment` | Operatöre bağla |
| Belge talebi | Yes | `request_document` | Operatöre bağla |
| Genel soru | No | RAG retrieval | "Bilgi bulunamadı" + operatöre yönlendir |
| Ücret/harç bilgisi | No | RAG retrieval | "Bilgi bulunamadı" + operatöre yönlendir |
| Şikayet/geri bildirim | No | `file_complaint` | Operatöre bağla |
| Operatöre bağla | No | `transfer_to_human` | — |

## Authentication Flow

```
┌──────────────────────────────────────────────┐
│              AUTH FLOW                        │
│                                              │
│  1. KVKK consent notice                     │
│     "Bu görüşme kaydedilmektedir..."        │
│                                              │
│  2. Ask preferred method:                    │
│     A) TC Kimlik + Doğum Tarihi             │
│     B) Başvuru No + Soyad                   │
│                                              │
│  3. Collect fields ONE BY ONE               │
│     - Validate format in real-time           │
│     - TC Kimlik: 11 digits + checksum       │
│     - DOB: valid date                        │
│                                              │
│  4. Verify against database                  │
│     ├─ SUCCESS → return citizen profile     │
│     └─ FAILURE → retry (max 3)              │
│         └─ 3 failures → human transfer      │
│                                              │
│  Security:                                   │
│  - Never read back full TC Kimlik           │
│  - Mask all PII in logs                      │
│  - Session auth expires after call ends      │
└──────────────────────────────────────────────┘
```

## Out-of-Scope Handling

### Strategy: 3-Step Graceful Decline

**Step 1 — Acknowledge and clarify:**
> "Anlıyorum, [konu] hakkında bilgi almak istiyorsunuz."

**Step 2 — Explain limitation and redirect:**
> "Bu konu ne yazık ki benim hizmet alanımın dışında. [Konu] için [doğru birim/kanal] ile iletişime geçmenizi öneririm."

**Step 3 — Offer escalation (if citizen insists):**
> "Dilerseniz sizi bir müsait operatöre bağlayabilirim, size daha detaylı yardımcı olabilirler."

### Common Out-of-Scope Categories

| Category | Example | Response |
|----------|---------|----------|
| Legal advice | "Davamı kazanır mıyım?" | Avukata yönlendir |
| Medical | "Hangi hastaneye gitmeliyim?" | ALO 182 veya 112'ye yönlendir |
| Political | "X partisi hakkında ne düşünüyorsun?" | Kibarca reddet, hizmetlere yönlendir |
| Other agencies | "Vergi borcumu öğrenebilir miyim?" | İlgili kuruma yönlendir (GİB) |
| Personal opinion | "En iyi okul hangisi?" | Görüş bildirmediğini belirt |

## Language Management

### Architecture: Single Agent, Multiple Languages

```
┌─────────────────────────────────────────────────┐
│          Agent: Umut (Multilingual)              │
│                                                  │
│  Primary Language: Turkish (TR)                  │
│  TTS Model: eleven_flash_v2_5 (multilingual)    │
│                                                  │
│  Language Presets:                                │
│  ┌─────────────────────────────────────────┐    │
│  │ EN: English                              │    │
│  │   - first_message: "Hello, welcome..."   │    │
│  │   - TTS: auto (flash v2 for EN)         │    │
│  └─────────────────────────────────────────┘    │
│                                                  │
│  System Tool: language_detection                 │
│  Triggers on:                                    │
│    1. User speaks different language than current │
│    2. User explicitly asks to switch language    │
└─────────────────────────────────────────────────┘
```

### Language Detection Flow

1. **Greeting** — Agent greets in primary language (Turkish)
2. **First user utterance** — Language detection tool analyzes audio
3. **Switch decision:**
   - User speaks Turkish → continue in Turkish
   - User speaks English → tool triggers, agent switches to English
   - User explicitly asks ("Can you speak English?") → tool triggers switch
4. **Ongoing** — Agent continues in detected language for rest of call

### Why Single Agent (Not Per-Language Agents)

| Approach | Pros | Cons |
|----------|------|------|
| **Single agent + presets** (chosen) | One endpoint, unified analytics, easy to add languages | First message always in primary language |
| **Separate agents per language** | Full control per language | Multiple endpoints, split analytics, double maintenance |

For a government service: one phone number, one agent, it just works. Adding Arabic later = one preset addition, not a new agent deployment.

### Known Behavior: Widget vs Production Language Switching

| Environment | STT Language Selection | Mid-Call Switch |
|-------------|----------------------|-----------------|
| **Widget / Test UI** | User selects language from dropdown before call starts. STT is locked to that language for the duration. Switching requires selecting a different language and starting a new call. | Not supported — widget limitation |
| **Telephony (Twilio/SIP)** | STT auto-detects language from audio. `language_detection` system tool triggers switch when user speaks a different language. | Supported — platform-native |

**Impact on testing:** When testing via dashboard widget, select the correct language before starting the call. The `language_detection` system tool and our Custom LLM's language heuristics work correctly — but the widget's STT transcribes in the pre-selected language, so spoken English gets transcribed as Turkish if "Turkish" is selected.

**Impact on production:** No impact. Telephony calls use audio-based language detection. The single-agent + language-presets architecture works as designed.

## Multi-Intent Handling

Citizens may have multiple needs in one call. Strategy:

1. **Detect first intent** — handle it completely
2. **At closing, ask** — "Başka yardımcı olabileceğim bir konu var mı?"
3. **If new intent** — loop back to intent detection (see diagram)
4. **Track completed intents** — don't re-ask for auth if already verified in this session

Example:
```
Citizen: "Başvurumun durumunu öğrenmek istiyorum, bir de randevu almam lazım."
Agent:   (detects 2 intents, handles status check first)
         "Önce başvuru durumunuza bakalım... [completes status check]
          Şimdi randevu almak istediğinizi söylemiştiniz, hangi hizmet için?"
```
