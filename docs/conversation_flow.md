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
