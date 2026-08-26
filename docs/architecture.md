# FoodGenome AI — Architecture

Every diagram below reflects what is actually built or specified, with measured numbers
where measurements exist. Nothing here is aspirational unless marked *planned*.

---

## 1. System overview

The whole product in one view: a photograph enters on the left, a grounded nutritional
answer leaves on the right, and every gate in between exists because a wrong answer in a
nutrition app is worse than no answer.

**Legend** — 🔵 client (Vercel) · 🔴 backend (HF Spaces) · 🟢 knowledge (local, zero cost) ·
🟠 external services

```mermaid
%%{init: {'theme':'base','themeVariables':{'fontFamily':'ui-sans-serif, system-ui, -apple-system, sans-serif','primaryColor':'#F4F1E8','primaryTextColor':'#0B0B0F','primaryBorderColor':'#0B0B0F','lineColor':'#0B0B0F','clusterBkg':'#ECE7D9','clusterBorder':'#0B0B0F','edgeLabelBackground':'#F4F1E8'},'flowchart':{'padding':16,'nodeSpacing':45,'rankSpacing':55,'curve':'basis','htmlLabels':true},'themeCSS':'.nodeLabel{padding:2px 6px}'}}%%
flowchart LR
    UP["Photo upload<br/><small>Next.js · Vercel</small>"]
    MW["Middleware<br/><small>trace ID · latency · cost</small>"]
    VIS["Vision service<br/><small>ONNX ensemble</small>"]
    REL["Reliability gate<br/><small>calibrate → conformal → OOD</small>"]
    RAG["RAG service<br/><small>FastAPI · HF Spaces</small>"]
    UI["Result panels<br/><small>3D depth · helix · web</small>"]
    ADM["Admin console<br/><small>RBAC gated</small>"]

    KB[("Nutrition KB<br/><small>101 classes · 32 nutrients</small>")]
    COR[("Corpus<br/><small>577 documents</small>")]
    GR[("Graph<br/><small>dish → ingredient → nutrient</small>")]

    PROM["Prometheus<br/><small>→ Grafana Cloud</small>"]
    FB[("Firestore<br/><small>predictions · cost · feedback</small>")]
    OAI["OpenAI<br/><small>last resort only</small>"]

    UP --> MW --> VIS --> REL
    REL -->|"accepted"| RAG
    REL -->|"rejected"| UI
    RAG --> KB
    RAG --> COR
    RAG --> GR
    RAG -.->|"~15%"| OAI
    RAG --> UI
    MW --> PROM
    MW --> FB
    ADM --> FB

    classDef c fill:#1B4CE0,stroke:#0B0B0F,stroke-width:2px,color:#fff
    classDef a fill:#E62429,stroke:#0B0B0F,stroke-width:2px,color:#fff
    classDef k fill:#16A34A,stroke:#0B0B0F,stroke-width:2px,color:#fff
    classDef e fill:#F5A524,stroke:#0B0B0F,stroke-width:2px,color:#0B0B0F
    class UP,UI,ADM c
    class MW,VIS,REL,RAG a
    class KB,COR,GR k
    class FB,OAI,PROM e
```

---

## 2. Training pipeline — the frozen feature bank

The central engineering decision. Running each backbone over the corpus **once** and
caching pooled embeddings converts every downstream experiment from hours into seconds,
which is what makes rigorous ablation affordable on a laptop.

```mermaid
%%{init: {'theme':'base','themeVariables':{'fontFamily':'ui-sans-serif, system-ui, -apple-system, sans-serif','primaryColor':'#F4F1E8','primaryTextColor':'#0B0B0F','primaryBorderColor':'#0B0B0F','lineColor':'#0B0B0F','clusterBkg':'#ECE7D9','clusterBorder':'#0B0B0F','edgeLabelBackground':'#F4F1E8','pie1':'#16A34A','pie2':'#E62429','pie3':'#1B4CE0','pie4':'#F5A524'},'flowchart':{'padding':16,'nodeSpacing':45,'rankSpacing':55,'curve':'basis','htmlLabels':true}}}%%
flowchart LR
    F101[("Food-101<br/><small>101,000 images<br/>75,750 train · 25,250 test</small>")]

    B1["SigLIP-SO400M<br/><small>384px · 428M · 5.16 img/s</small>"]
    B2["EVA-02-L<br/><small>448px · 304M · 4.04 img/s</small>"]
    B3["DINOv2-L<br/><small>518px · 304M · 3.6 img/s</small>"]

    C1[("siglip cache<br/><small>101k × 1152</small>")]
    C2[("eva02 cache<br/><small>101k × 1024</small>")]
    C3[("dinov2 cache<br/><small>101k × 1024</small>")]

    H1["probe<br/><small>96.83%</small>"]
    H2["probe<br/><small>95.53%</small>"]
    H3["probe<br/><small>pending</small>"]
    HF["gated fusion<br/><small>96.97%</small>"]

    AVG["probability average<br/><small>0 params · 97.16%</small>"]
    FT["EVA-02-L 448 fine-tune<br/><small>layer decay · mixup · EMA</small>"]
    ENS["final ensemble + TTA"]

    F101 --> B1 --> C1 --> H1 --> AVG
    F101 --> B2 --> C2 --> H2 --> AVG
    F101 --> B3 --> C3 --> H3
    C1 --> HF
    C2 --> HF
    C3 --> HF
    F101 --> FT
    AVG --> ENS
    HF --> ENS
    FT --> ENS

    classDef d fill:#0B0B0F,stroke:#0B0B0F,stroke-width:2px,color:#F4F1E8
    classDef x fill:#1B4CE0,stroke:#0B0B0F,stroke-width:2px,color:#fff
    classDef s fill:#22D3EE,stroke:#0B0B0F,stroke-width:2px,color:#0B0B0F
    classDef w fill:#16A34A,stroke:#0B0B0F,stroke-width:2px,color:#fff
    classDef p fill:#F4F1E8,stroke:#0B0B0F,stroke-width:2px,color:#0B0B0F
    class F101 d
    class B1,B2,B3 x
    class C1,C2,C3 s
    class AVG,ENS w
    class H1,H2,H3,HF,FT p
```

### Measured results

```mermaid
%%{init: {'theme':'base','themeVariables':{'fontFamily':'ui-sans-serif, system-ui, -apple-system, sans-serif','primaryColor':'#F4F1E8','primaryTextColor':'#0B0B0F','primaryBorderColor':'#0B0B0F','lineColor':'#0B0B0F','clusterBkg':'#ECE7D9','clusterBorder':'#0B0B0F','edgeLabelBackground':'#F4F1E8','pie1':'#16A34A','pie2':'#E62429','pie3':'#1B4CE0','pie4':'#F5A524'},'flowchart':{'padding':16,'nodeSpacing':45,'rankSpacing':55,'curve':'basis','htmlLabels':true}}}%%
xychart-beta
    title "Food-101 test top-1 accuracy (%)"
    x-axis ["EVA-02 probe", "SigLIP probe", "Gated fusion", "Prob average"]
    y-axis "top-1 %" 95 --> 98
    bar [95.53, 96.83, 96.97, 97.16]
```

**The learned fusion head lost to a parameter-free average.** McNemar exact test on paired
test predictions (n = 25,250): prob-average vs gated-fusion **p = 0.0050 (significant)**,
while gated-fusion vs SigLIP alone was **p = 0.071 (not significant)** — the 3.97M-parameter
head failed to beat its own best input.

---

## 3. Why the ensemble gains are small

```mermaid
%%{init: {'theme':'base','themeVariables':{'fontFamily':'ui-sans-serif, system-ui, -apple-system, sans-serif','primaryColor':'#F4F1E8','primaryTextColor':'#0B0B0F','primaryBorderColor':'#0B0B0F','lineColor':'#0B0B0F','clusterBkg':'#ECE7D9','clusterBorder':'#0B0B0F','edgeLabelBackground':'#F4F1E8','pie1':'#16A34A','pie2':'#E62429','pie3':'#1B4CE0','pie4':'#F5A524'},'flowchart':{'padding':16,'nodeSpacing':45,'rankSpacing':55,'curve':'basis','htmlLabels':true}}}%%
pie showData
    title "SigLIP vs EVA-02 agreement on 25,250 test images"
    "Both correct" : 23842
    "Only SigLIP correct" : 607
    "Only EVA-02 correct" : 279
    "Both wrong" : 522
```

65.2% of SigLIP's errors are *also* EVA-02's errors. The oracle ceiling — either model
correct — is **97.93%**, so roughly 0.8 points of headroom remain unexploited. This is why
DINOv2 matters disproportionately: as the only self-supervised member it should be the
least correlated with the other two.

---

## 4. Knowledge base construction

Naive text matching against USDA fails **confidently**, which is the dangerous failure
mode: beef carpaccio → "Soup, stock, beef" at 13 kcal, chicken wings → "Soup, stock,
chicken" at 36 kcal.

```mermaid
%%{init: {'theme':'base','themeVariables':{'fontFamily':'ui-sans-serif, system-ui, -apple-system, sans-serif','primaryColor':'#F4F1E8','primaryTextColor':'#0B0B0F','primaryBorderColor':'#0B0B0F','lineColor':'#0B0B0F','clusterBkg':'#ECE7D9','clusterBorder':'#0B0B0F','edgeLabelBackground':'#F4F1E8','pie1':'#16A34A','pie2':'#E62429','pie3':'#1B4CE0','pie4':'#F5A524'},'flowchart':{'padding':16,'nodeSpacing':45,'rankSpacing':55,'curve':'basis','htmlLabels':true}}}%%
flowchart TD
    CLS["101 Food-101 class names"]
    USDA[("USDA SR Legacy<br/>generic unbranded foods")]

    CLS --> DEC{"Does SR Legacy<br/>contain this dish?"}
    DEC -->|"yes · 41 classes"| DIR["Direct match<br/>tuned query + require/avoid"]
    DEC -->|"no · 60 classes"| COMP["Composite recipe<br/>weighted ingredient list"]

    DIR --> RES["Resolver<br/>penalises baby food,<br/>dry mixes, brands"]
    COMP --> RES
    USDA --> RES
    RES --> ENTRY["KB entry<br/>32 nutrients<br/>per 100 g + per serving"]

    ENTRY --> V{"Validation"}
    V --> V1["Coverage 101/101"]
    V --> V2["Energy 20–600 kcal/100 g"]
    V --> V3["Atwater 4/4/9 consistency"]
    V --> V4["Composite mass ≈ 100 g"]
    V --> V5["Token-level provenance"]

    V1 & V2 & V3 & V4 & V5 --> OUT[("kb.json + audit.md<br/>0 flags")]
    COMP -.->|"dish → ingredient edges"| GRAPH[("Knowledge graph<br/>for GraphRAG")]

    classDef ok fill:#16A34A,stroke:#0f6b32,color:#fff
    classDef warn fill:#F5A524,stroke:#b37a18,color:#0B0B0F
    classDef data fill:#0B0B0F,stroke:#0B0B0F,color:#F4F1E8
    class V1,V2,V3,V4,V5,OUT ok
    class DEC,V warn
    class USDA,GRAPH data
```

> **A validator that shares the failure mode of the thing it validates is worse than no
> validator.** The ingredient query `"water"` substring-matched **"Watermelon, raw"**,
> putting watermelon into miso soup, churros and takoyaki. No numeric check caught it —
> watermelon is low-calorie enough to stay in band — and the *first* provenance check
> written to catch it had the same substring flaw and passed it too. Provenance now compares
> whole tokens.

---

## 5. Advanced RAG — the LLM is the last resort

Cost and correctness point the same way: a deterministic KB lookup is *more* accurate than
an LLM for numeric facts, because a model reading "310 kcal" from context can transcribe it
wrong and a lookup cannot.

```mermaid
%%{init: {'theme':'base','themeVariables':{'fontFamily':'ui-sans-serif, system-ui, -apple-system, sans-serif','primaryColor':'#F4F1E8','primaryTextColor':'#0B0B0F','primaryBorderColor':'#0B0B0F','lineColor':'#0B0B0F','clusterBkg':'#ECE7D9','clusterBorder':'#0B0B0F','edgeLabelBackground':'#F4F1E8','pie1':'#16A34A','pie2':'#E62429','pie3':'#1B4CE0','pie4':'#F5A524'},'flowchart':{'padding':16,'nodeSpacing':45,'rankSpacing':55,'curve':'basis','htmlLabels':true}}}%%
flowchart TD
    Q["User question"] --> RT{"Intent router<br/>local embeddings + rules<br/>no API call"}

    RT -->|"structured lookup"| T1["KB read → template"]
    RT -->|"comparison"| T2["KB compare → template"]
    RT -->|"superlative"| T3["Precomputed ranking docs"]
    RT -->|"portion maths"| T4["Arithmetic on KB"]
    RT -->|"open-ended"| CACHE{"Semantic cache hit?<br/>FAISS cosine"}

    CACHE -->|"hit"| ANS
    CACHE -->|"miss"| HYB

    subgraph retrieval["HYBRID RETRIEVAL  "]
        direction TB
        HYB["Query"] --> BM["BM25 sparse"]
        HYB --> DEN["Dense bi-encoder"]
        BM --> RRF["Reciprocal Rank Fusion"]
        DEN --> RRF
        RRF --> RR["Rerank · cross-encoder or Cohere<br/>top-k only → caps prompt size"]
    end

    RR --> CRAG{"CRAG<br/>retrieval quality?"}
    CRAG -->|"poor"| REW["Rewrite query · re-retrieve"] --> HYB
    CRAG -->|"ambiguous"| GRAPH["GraphRAG traversal<br/>dish → ingredient → nutrient"]
    CRAG -->|"good"| GEN
    GRAPH --> GEN

    GEN{"Budget remaining?"}
    GEN -->|"yes"| LLM["OpenAI generation<br/>capped context"]
    GEN -->|"no · degrade"| T1

    LLM --> GRD{"Grounding check<br/>claim supported by context?"}
    GRD -->|"supported"| ANS["Answer + citations"]
    GRD -->|"unsupported"| LOG["Log grounding failure<br/>→ admin console"] --> T1

    T1 & T2 & T3 & T4 --> ANS

    classDef free fill:#16A34A,stroke:#0f6b32,color:#fff
    classDef paid fill:#E62429,stroke:#A4161A,color:#fff
    classDef gate fill:#F5A524,stroke:#b37a18,color:#0B0B0F
    class T1,T2,T3,T4 free
    class LLM paid
    class RT,CRAG,GEN,GRD,CACHE gate
```

**~85% of traffic never reaches OpenAI.** Controls on the remainder: semantic answer cache,
hard daily budget that degrades to templates rather than erroring, context capped to
reranked top-k, prompt-prefix caching, and the Batch API for offline evaluation.

The shipped subset of this design lives in `src/nutrivision/rag/`: the retrieval stages are
LangChain retrievers and a document compressor, and the control flow — CRAG gate, relaxed
retry, budget gate, grounding check, template fallback — is a compiled LangGraph in
`pipeline.py`. `python -m nutrivision.rag.pipeline --graph` prints what is actually wired.

---

## 6. Reliability gate

Accuracy alone is an insufficient goal. This is the decision flow between a raw prediction
and anything shown to a user.

```mermaid
%%{init: {'theme':'base','themeVariables':{'fontFamily':'ui-sans-serif, system-ui, -apple-system, sans-serif','primaryColor':'#F4F1E8','primaryTextColor':'#0B0B0F','primaryBorderColor':'#0B0B0F','lineColor':'#0B0B0F','clusterBkg':'#ECE7D9','clusterBorder':'#0B0B0F','edgeLabelBackground':'#F4F1E8','pie1':'#16A34A','pie2':'#E62429','pie3':'#1B4CE0','pie4':'#F5A524'},'flowchart':{'padding':16,'nodeSpacing':45,'rankSpacing':55,'curve':'basis','htmlLabels':true}}}%%
stateDiagram-v2
    [*] --> Logits
    Logits --> Calibrated : temperature scaling<br/>T = 0.834

    Calibrated --> OODCheck
    state OODCheck <<choice>>
    OODCheck --> Rejected : energy + Mahalanobis<br/>below threshold
    OODCheck --> Conformal : passes

    Rejected --> LogReject : "not food"<br/>reviewable in admin
    LogReject --> [*]

    Conformal --> SetSize
    state SetSize <<choice>>
    SetSize --> Confident : set size = 1
    SetSize --> Ambiguous : set size > 1

    Confident --> Explain
    Ambiguous --> Explain : "one of these N dishes"
    Explain --> GradCAM : Grad-CAM + attention rollout
    GradCAM --> Portion : depth → volume → mass
    Portion --> [*]
```

Calibration measured on the SigLIP head: **ECE 0.03250 → 0.00425** (7.6× better), accuracy
byte-identical at 96.828 — temperature scaling cannot move the arg-max, which is the
correctness check. The fitted **T = 0.834 is below 1**, meaning the model was *under*-confident,
the opposite of the textbook result, traced to stacking label smoothing with mixup.

---

## 7. Request lifecycle

```mermaid
%%{init: {'theme':'base','themeVariables':{'fontFamily':'ui-sans-serif, system-ui, -apple-system, sans-serif','primaryColor':'#F4F1E8','primaryTextColor':'#0B0B0F','primaryBorderColor':'#0B0B0F','lineColor':'#0B0B0F','clusterBkg':'#ECE7D9','clusterBorder':'#0B0B0F','edgeLabelBackground':'#F4F1E8','pie1':'#16A34A','pie2':'#E62429','pie3':'#1B4CE0','pie4':'#F5A524'},'flowchart':{'padding':16,'nodeSpacing':45,'rankSpacing':55,'curve':'basis','htmlLabels':true}}}%%
sequenceDiagram
    autonumber
    participant U as User
    participant W as Next.js
    participant A as FastAPI
    participant M as Model
    participant K as KB / RAG
    participant O as OpenAI
    participant F as Firebase

    U->>W: upload photo
    W->>A: POST /predict
    activate A
    A->>A: assign trace ID · start timer
    A->>M: ensemble inference
    M-->>A: calibrated logits
    A->>A: conformal set · OOD score
    alt not food
        A-->>W: rejected + reason
    else accepted
        A->>K: nutrition for class
        K-->>A: per-100g + per-serving
        A-->>W: prediction + confidence + nutrition
    end
    A->>F: rollup increment (1 write, 0 reads)
    deactivate A

    U->>W: asks a follow-up question
    W->>A: POST /ask
    activate A
    A->>K: intent route
    alt structured · ~85%
        K-->>A: templated answer (zero cost)
    else open-ended
        A->>K: hybrid retrieve → RRF → rerank
        A->>O: generate with capped context
        O-->>A: answer + token usage
        A->>A: grounding verification
        A->>F: log cost + any grounding failure
    end
    A-->>W: grounded answer + citations
    deactivate A
```

---

## 8. Firestore schema

Firestore bills **per document read**, and the free tier allows ~50k reads/day. An admin
dashboard reading raw rows would exhaust that in minutes, so metrics are written as
pre-aggregated rollups updated with atomic increments.

```mermaid
%%{init: {'theme':'base','themeVariables':{'fontFamily':'ui-sans-serif, system-ui, -apple-system, sans-serif','primaryColor':'#F4F1E8','primaryTextColor':'#0B0B0F','primaryBorderColor':'#0B0B0F','lineColor':'#0B0B0F','clusterBkg':'#ECE7D9','clusterBorder':'#0B0B0F','edgeLabelBackground':'#F4F1E8','pie1':'#16A34A','pie2':'#E62429','pie3':'#1B4CE0','pie4':'#F5A524'},'flowchart':{'padding':16,'nodeSpacing':45,'rankSpacing':55,'curve':'basis','htmlLabels':true}}}%%
erDiagram
    USERS ||--o{ MEALS : logs
    MEALS ||--|| PREDICTIONS : from
    PREDICTIONS ||--o{ FEEDBACK : receives
    METRICS_HOURLY }o--|| MODELS : attributed_to

    USERS {
        string uid PK
        string email
        timestamp created_at
        bool is_admin
    }
    PREDICTIONS {
        string id PK
        string food_class
        float confidence
        int conformal_set_size
        bool ood_rejected
        string model_version
        string trace_id
        int latency_ms
        timestamp created_at
    }
    METRICS_HOURLY {
        string bucket PK "YYYY-MM-DD-HH"
        int requests
        int errors
        float p50_ms
        float p95_ms
        int openai_tokens
        float cost_usd
    }
    GROUNDING_FAILURES {
        string id PK
        string question
        string unsupported_claim
        string trace_id
        timestamp created_at
    }
    FEEDBACK {
        string id PK
        string prediction_id FK
        bool correct
        string corrected_class
    }
    MODELS {
        string version PK
        float test_top1
        float ece
        timestamp deployed_at
    }
```

**One write per request, zero reads.** A full day of dashboard data is 24 documents rather
than tens of thousands.

---

## 9. Deployment topology

```mermaid
%%{init: {'theme':'base','themeVariables':{'fontFamily':'ui-sans-serif, system-ui, -apple-system, sans-serif','primaryColor':'#F4F1E8','primaryTextColor':'#0B0B0F','primaryBorderColor':'#0B0B0F','lineColor':'#0B0B0F','clusterBkg':'#ECE7D9','clusterBorder':'#0B0B0F','edgeLabelBackground':'#F4F1E8','pie1':'#16A34A','pie2':'#E62429','pie3':'#1B4CE0','pie4':'#F5A524'},'flowchart':{'padding':16,'nodeSpacing':45,'rankSpacing':55,'curve':'basis','htmlLabels':true}}}%%
flowchart TB
    subgraph vercel["VERCEL  "]
        APP["User app<br/>anonymous-first"]
        ADMIN["Admin console<br/>RBAC gated"]
    end

    subgraph hf["HUGGING FACE  "]
        SPACE["Space · Docker<br/>FastAPI + ONNX Runtime"]
        HUB[("Model Hub<br/>ONNX artifacts")]
    end

    subgraph gcp["FIREBASE  "]
        AUTH["Auth"]
        FS[("Firestore")]
        ST[("Storage")]
        AC["App Check"]
    end

    OAI["OpenAI API"]

    APP --> SPACE
    ADMIN --> SPACE
    APP --> AUTH
    ADMIN --> AUTH
    SPACE --> HUB
    SPACE --> FS
    SPACE --> ST
    SPACE -.->|"budget-capped"| OAI
    AC -.->|"attests"| APP
    ADMIN --> FS

    classDef v fill:#0B0B0F,stroke:#0B0B0F,color:#F4F1E8
    classDef h fill:#F5A524,stroke:#b37a18,color:#0B0B0F
    classDef g fill:#1B4CE0,stroke:#0A2A66,color:#fff
    class APP,ADMIN v
    class SPACE,HUB h
    class AUTH,FS,ST,AC g
```

---

## 10. Delivery plan

```mermaid
%%{init: {'theme':'base','themeVariables':{'fontFamily':'ui-sans-serif, system-ui, -apple-system, sans-serif','primaryColor':'#F4F1E8','primaryTextColor':'#0B0B0F','primaryBorderColor':'#0B0B0F','lineColor':'#0B0B0F','clusterBkg':'#ECE7D9','clusterBorder':'#0B0B0F','edgeLabelBackground':'#F4F1E8','pie1':'#16A34A','pie2':'#E62429','pie3':'#1B4CE0','pie4':'#F5A524'},'flowchart':{'padding':16,'nodeSpacing':45,'rankSpacing':55,'curve':'basis','htmlLabels':true}}}%%
gantt
    title FoodGenome AI — stage plan
    dateFormat YYYY-MM-DD
    axisFormat %b %d

    section Perception
    Frozen feature bank        :done,    s1, 2026-07-31, 2d
    Probe heads + ensemble     :active,  s2, 2026-08-01, 2d
    EVA-02-L 448 fine-tune     :         s3, after s2, 3d
    Ensemble + TTA + final eval:         s4, after s3, 1d

    section Reliability
    Calibration                :done,    s5a, 2026-08-01, 1d
    Conformal + OOD            :         s5b, after s4, 2d
    Grad-CAM + portion         :         s6, after s5b, 2d

    section Knowledge
    Nutrition KB               :done,    s7, 2026-08-01, 1d
    Advanced RAG               :active,  s8, 2026-08-01, 3d
    RAG evaluation             :         s9, after s8, 2d

    section Delivery
    ONNX export + Hub          :         s10, after s4, 1d
    FastAPI + Firebase         :         s11, after s10, 3d
    User app                   :         s12, after s11, 4d
    Admin console              :         s13, after s12, 3d
    Docs, paper, slides        :         s14, after s13, 3d
    Deploy                     :         s15, after s14, 1d
```
