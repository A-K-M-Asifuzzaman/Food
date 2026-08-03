# FoodGenome AI

**Food-101 classification with calibrated confidence, a conformal guarantee, and nutrition traced to the USDA record it came from.**

Photograph a dish and the system returns the category, a confidence figure that means what it says, the full set of candidates it cannot rule out, where it looked, and a nutrition profile you can follow back to source. It also refuses to answer questions outside what it knows, which turned out to be harder to build than answering them.

**Live:** [food-red-omega.vercel.app](https://food-red-omega.vercel.app)

| | |
|---|---|
| **97.16%** | Food-101 test top-1, on a split untouched until final evaluation |
| **99.56%** | measured conformal coverage, averaging 1.54 candidates |
| **97.94%** | accuracy on accepted images, after abstaining on 2.28% |
| **98.6%** | RAG answers correct on a 76-case gold set, 100% grounded |
| **101** | dish categories, each with a 32-nutrient USDA profile |
| **$0.024** | cost of a full RAG evaluation run, with a daily budget gate |

---

## The interface

### Landing

![Landing page](docs/images/home.png)

Comic-print design language: plate misregistration on display type, graded Ben-Day dots, hard-bordered panels with unblurred offset shadows. Deliberately not the gradient-mesh SaaS look.

### Analyse a photo

![Analysis result](docs/images/analyze-result.png)

One upload returns everything at once — the prediction with its calibrated confidence, the conformal candidate set with its guarantee stated in plain language, macro and micronutrient tables, and the provenance of every figure. Composite dishes list the USDA records they were built from, each linking to FoodData Central.

### Where the model looked

![Grad-CAM attribution](docs/images/explain-panel.png)

Grad-CAM over the final transformer block, back through the pooling head to the patch grid. The panel reports how *concentrated* the attribution is and changes what it claims accordingly — a map covering much of the frame is labelled diffuse, with the architectural reason. Showing a heatmap without that context invites a reader to see precision the method does not have.

### Grounded question answering

![Grounded answer with citations](docs/images/ask-panel.png)

Ask in natural language. The question is rewritten to name the dish the vision model already identified, so "how much sodium is in this" can resolve against 101 near-identical sodium documents. Every quantity in the answer is verified against the retrieved sources before it is shown, and the badge states how the answer was produced.

### The knowledge web

![3D GraphRAG explorer](docs/images/explore.png)

The dish → ingredient graph rendered as an actual web: 181 nodes and 323 weighted edges, all derived from real USDA composite recipes. Search by name, click to pin a node, read its neighbours with their gram weights. This answers questions no single document contains — *which dishes contain walnuts* is an inversion of sixty separate ingredient lists.

### Search anything

![Command palette](docs/images/command-palette.png)

`⌘K` from any page. Matching is subsequence-based, so `chkn` finds Chicken Curry — a substring search would not, and a fuzzy-search library would be a dependency for thirty lines of scoring.

### Browse all 101 dishes

![Dish browser](docs/images/dishes.png)

Searchable and filterable by cuisine, sortable by calories or protein. Each card states whether its figures were measured directly by USDA or composed from ingredients.

### A single dish

![Dish detail page](docs/images/dish-detail.png)

Full nutrient profile on both bases, energy split by macronutrient, the USDA records behind the numbers, and where the dish ranks against the other hundred.

### Benchmarks

![Benchmarks page](docs/images/benchmarks.png)

Every measured result, including the experiments that failed. Nothing here is typed in by hand — the page renders the JSON the evaluation scripts wrote.

### Method

![Method page](docs/images/methods.png)

Seven stages with a measurement behind each, followed by a section on what the system *cannot* do.

---

### Signing in

![Sign in](docs/images/login.png)

Predictions are filed against an account. A browser-generated id would have been
less friction, and it was the first implementation — but it is lost the moment
somebody clears site data or opens the page on their phone, and anyone reading
the network tab can forge one. Neither makes a history worth showing.

Google or email, whichever is quicker. The ID token is verified server-side
against Google's public keys, so the uid comes from the signature rather than
from the request; `/history` can only ever return the caller's own rows, and
there is no value a client can send to read somebody else's.

![Sign-in gate](docs/images/analyze-gate.png)

The gate on the analyser explains what an account buys before asking for one,
and returns you to the page you wanted rather than the home page. That is the
difference between a gate and an obstacle.

### Your own record

Every dish you have analysed, every question you asked about one, and every
correction you sent back — with a delete button that actually deletes. A record
you cannot remove is not a record you agreed to keep, and "contact us to delete
your data" is not a delete button.

---

## The admin console

### Overview

![Admin overview](docs/images/admin-overview.png)

Model, reliability, retrieval and knowledge-base health, each tile linking to its evidence, above live operational counters: request and error rates, p50/p95/p99 latency per endpoint, a rolling prediction feed that doubles as the low-confidence review queue, OpenAI spend, resident memory and uptime.

Those counters are in-process, so they cover the container currently running and reset when it restarts — which the panel says outright, because a dashboard implying a history the service does not keep is worse than one admitting its window.

### People

Every signed-in account and what it has been analysing: volume, mean confidence, how often the model declined, and the dishes each person photographs most. Rows are per account rather than per request on purpose — thirty predictions from one person is a different fact from thirty people trying it once, and a request count cannot tell them apart.

Two lists on that page carry signal no labelled split can produce: what the model declined as too uncertain, and what a person marked wrong. A thumbs-down on a confident prediction is the single most valuable row in the console.

### Model registry

![Model registry](docs/images/admin-models.png)

Every head trained, the full ablation, and exact McNemar tests on the differences between them.

### Reliability

![Calibration and conformal](docs/images/admin-reliability.png)

A reliability diagram plotting raw against calibrated confidence, with the diagonal a perfect model sits on. Below it, conformal coverage and set size for four methods at three targets.

### Retrieval operations

![Retrieval quality](docs/images/admin-rag.png)

Retrieval and answer quality by question category, plus cost control.

---

## Three results that ran against expectation

**A parameter-free average beat a trained fusion head.** A 3.97M-parameter gated fusion model, trained for 21.9 minutes, lost to a probability average computed in milliseconds — and by exact McNemar test it did not significantly outperform its own best single input.

**A third backbone earned no place.** DINOv2-L was expected to decorrelate from the others, being the only self-supervised member. It is the *most* correlated: 66.3% of SigLIP's errors are shared with it. Adding it made the ensemble marginally worse.

**Attention is not saliency.** Reading the pooling head's own attention weights should be the most faithful account of where a model looked. Measured against a border-mass baseline it is *worse than chance* at finding the food — reproducing the documented artefact where transformers park high attention on empty background patches.

---

## How it works

```mermaid
%%{init: {'theme':'base','themeVariables':{
  'fontFamily':'ui-sans-serif, system-ui, sans-serif','fontSize':'14px',
  'primaryColor':'#ffffff','primaryTextColor':'#0b0b0f','primaryBorderColor':'#0b0b0f',
  'lineColor':'#4b4b55'},
  'flowchart':{'curve':'basis','padding':22,'nodeSpacing':34,'rankSpacing':60}}}%%
flowchart LR
    IMG(["photograph"])
    S["SigLIP-SO400M · 96.83%"]
    E["EVA-02-L · 95.53%"]
    AVG{{"probability average · 97.16%"}}
    CAL["temperature T = 0.7621"]
    CONF["conformal set · 99.56% coverage"]
    AB{"model confident?"}
    NUT["USDA nutrition · 101 classes"]
    OUT(["dish · confidence · candidates"])
    LOST(["declines — the model is lost"])

    AUTH["Firebase ID token · verified server-side"]
    HIST[("Firestore · your history")]

    IMG --> AUTH --> S & E
    S & E --> AVG --> CAL --> CONF --> AB
    AB -- "yes" --> NUT --> OUT
    AB -- "no" --> LOST
    OUT -.-> HIST
    LOST -.-> HIST

    classDef vision fill:#e62429,stroke:#0b0b0f,stroke-width:2px,color:#ffffff
    classDef rel fill:#1b4ce0,stroke:#0b0b0f,stroke-width:2px,color:#ffffff
    classDef know fill:#0e8fa3,stroke:#0b0b0f,stroke-width:2px,color:#ffffff
    classDef gate fill:#f5a524,stroke:#0b0b0f,stroke-width:2px,color:#0b0b0f
    classDef term fill:#ffffff,stroke:#0b0b0f,stroke-width:3px,color:#0b0b0f
    classDef refuse fill:#0b0b0f,stroke:#0b0b0f,stroke-width:2px,color:#f4f1e8

    class S,E,AVG vision
    class CAL,CONF rel
    class AUTH gate
    class HIST know
    class NUT know
    class AB gate
    class IMG,OUT term
    class LOST refuse
```

<sub>**red** vision · **blue** reliability · **teal** knowledge · **amber** a decision that can refuse</sub>

Ask a question about the identified dish and a second pipeline runs, which can refuse in two more places:

```mermaid
%%{init: {'theme':'base','themeVariables':{
  'fontFamily':'ui-sans-serif, system-ui, sans-serif','fontSize':'14px',
  'primaryColor':'#ffffff','primaryTextColor':'#0b0b0f','primaryBorderColor':'#0b0b0f',
  'lineColor':'#4b4b55'},
  'flowchart':{'curve':'basis','padding':22,'nodeSpacing':34,'rankSpacing':58}}}%%
flowchart LR
    Q(["how much sodium is in this?"])
    RW["rewrite to name the dish"]
    HYB["BM25 + bi-encoder"]
    RRF["reciprocal rank fusion"]
    RR["cross-encoder rerank"]
    CRAG{"evidence relevant?"}
    GEN["generate from sources only"]
    GATE{"every number in a source?"}
    ANS(["answer with citations"])
    TPL(["the record itself, verbatim"])
    NONE(["outside the knowledge base"])

    Q --> RW --> HYB --> RRF --> RR --> CRAG
    CRAG -- "yes" --> GEN --> GATE
    CRAG -- "no" --> NONE
    GATE -- "yes" --> ANS
    GATE -- "no" --> TPL

    classDef prep fill:#0e8fa3,stroke:#0b0b0f,stroke-width:2px,color:#ffffff
    classDef gate fill:#f5a524,stroke:#0b0b0f,stroke-width:2px,color:#0b0b0f
    classDef term fill:#ffffff,stroke:#0b0b0f,stroke-width:3px,color:#0b0b0f
    classDef refuse fill:#0b0b0f,stroke:#0b0b0f,stroke-width:2px,color:#f4f1e8

    class RW,HYB,RRF,RR,GEN prep
    class CRAG,GATE gate
    class Q,ANS,TPL term
    class NONE refuse
```

A failed grounding check does not refuse — it serves the retrieved record verbatim, which is correct by construction and needs no verification.


Two paths lead to a refusal, and that is deliberate. The abstention gate declines when the model is lost on the image; the CRAG gate declines when the knowledge base holds nothing relevant. A failed grounding check does not refuse — it falls back to the deterministic record, which is correct by construction.

### Where the accuracy actually comes from

```mermaid
%%{init: {'theme':'base','themeVariables':{
  'fontFamily':'ui-sans-serif, system-ui, sans-serif','fontSize':'13px',
  'primaryColor':'#ffffff','primaryTextColor':'#0b0b0f','primaryBorderColor':'#0b0b0f',
  'lineColor':'#4b4b55'},'flowchart':{'padding':12,'nodeSpacing':30}}}%%
flowchart TD
    A["DINOv2-L alone<br/><b>94.87%</b>"]
    B["EVA-02-L alone<br/><b>95.53%</b>"]
    C["SigLIP-SO400M alone<br/><b>96.83%</b>"]
    D["gated fusion head<br/>3.97M params · 21.9 min<br/><b>96.97%</b>"]
    F["SigLIP + EVA-02 averaged<br/>0 params · 0 seconds<br/><b>97.16%</b>"]
    G["all three averaged<br/><b>97.09%</b>"]
    H["oracle ceiling<br/><b>98.30%</b>"]

    C --> D
    B --> D
    C --> F
    B --> F
    F --> G
    A --> G
    F -.->|"0.77 unexploited"| H

    classDef solo fill:#ffffff,stroke:#4b4b55,stroke-width:1.5px
    classDef lost fill:#f4f1e8,stroke:#4b4b55,stroke-width:1.5px,stroke-dasharray:4 3
    classDef win fill:#16a34a,stroke:#0b0b0f,stroke-width:3px,color:#fff
    classDef ceil fill:#f5a524,stroke:#0b0b0f,stroke-width:2px

    class A,B,C solo
    class D,G lost
    class F win
    class H ceil
```

The winner has no parameters. The trained fusion head and the three-way average both lost to it, and neither loss is explained by noise — the pairing beats its best single input at p = 0.000003.


**Vision.** Three backbones were run once over all 101,000 images and their embeddings cached — about twenty hours, after which every downstream experiment finished in seconds. Lightweight MLP probes train on the cache; the shipped classifier averages two of them.

**Reliability.** Temperature fitted on held-out data cut expected calibration error eightfold. Split-conformal prediction gives a coverage guarantee that holds without assuming anything about the model. Abstention combines calibrated confidence with conformal set size, because neither is sufficient alone.

**Retrieval.** 693 documents — 577 written from the knowledge base plus 116 graph facts — indexed for both lexical and semantic search, fused by Reciprocal Rank Fusion, reranked by a cross-encoder, and conditioned on the dish the vision model identified.

**Grounding.** Every quantity in a generated answer must appear in the retrieved context, matched per unit so milligrams can never be supported by the same digits in grams. An answer that fails is withheld, not annotated.

---

## Repository

```
src/nutrivision/
  data/         Food-101 download and the fixed validation split
  models/       backbone feature extraction, probe heads
  training/     probe training, ensembling, fine-tuning
  reliability/  temperature scaling, split-conformal prediction
  explain/      Grad-CAM and attribution comparison
  nutrition/    USDA resolution and the 101-class knowledge base
  rag/          corpus, index, retrieval, graph, generation, grounding, evaluation
backend/app/
  main.py       the API surface
  inference.py  ensemble, calibration, conformal sets
  auth.py       Firebase ID token verification and the admin list
  store.py      durable storage — Firestore or MongoDB, both optional
  metrics.py    in-process counters and the rolling prediction feed
web/            Next.js frontend
firestore.rules deny-all: no browser talks to the database
notebooks/      Kaggle fine-tuning notebook
docs/           architecture, design system, proposal
```

### Running it

```bash
# Python environment
python -m venv .venv && .venv/bin/pip install -e .

# Build the knowledge base, corpus and retrieval index
.venv/bin/python -m nutrivision.nutrition.build_kb
.venv/bin/python -m nutrivision.rag.corpus
.venv/bin/python -m nutrivision.rag.index

# Serve the model
.venv/bin/python -m uvicorn backend.app.main:app --port 8000

# Frontend
cd web && npm install && FOODGENOME_API=http://127.0.0.1:8000 npm run dev
```

Copy `.env.example` to `.env` for the OpenAI key. Without it the RAG pipeline serves deterministic template answers assembled from the same records — correct by construction, and free.

#### Optional services

Both degrade rather than fail, so a fresh clone serves predictions with neither configured.

| Variable | On | Effect when unset |
|---|---|---|
| `OPENAI_API_KEY` | model service | answers come from deterministic templates over the same records |
| `FIREBASE_CREDENTIALS` | model service | predictions are answered but not kept; history and analytics report themselves off |
| `MONGODB_URI` | model service | the alternative store, used only if no Firebase credential is present |
| `REQUIRE_AUTH` | model service | unset, the service serves unauthenticated callers; set to `1` in deployment |
| `ADMIN_EMAILS` | model service | comma-separated; the only accounts `/analytics` and `/stats` will answer |
| `FOODGENOME_API` | frontend | the frontend serves clearly-labelled demo responses instead of predictions |

`firestore.rules` denies every client read and write. No browser in this system
talks to Firestore — the web app uses Firebase only to sign a user in, and all
reads go through the API where they can be scoped to the caller.

#### API

| Route | Auth | What it does |
|---|---|---|
| `POST /predict` | user | classification, conformal set, abstention, nutrition |
| `POST /explain` | user | Grad-CAM overlay, composited server-side |
| `POST /ask` | user | grounded answer with citations, or a refusal |
| `POST /feedback` | user | thumbs up or down on a prediction |
| `GET /history` | user | the caller's own rows |
| `DELETE /history` | user | erases them |
| `GET /stats` | admin | in-process counters for the current container |
| `GET /analytics` | admin | per-day, per-dish and per-account rollups |
| `GET /me` | open | who the presented token belongs to, if anyone |
| `GET /health` `POST /warm` | open | readiness, and starting the model load early |

### Evaluation

```bash
.venv/bin/python -m nutrivision.training.ensemble          # ablation + McNemar
.venv/bin/python -m nutrivision.reliability.calibration \
    --name ensemble --members siglip_so400m eva02_large
.venv/bin/python -m nutrivision.reliability.conformal      # coverage vs set size
.venv/bin/python -m nutrivision.rag.evaluate               # retrieval + answers
```

---

## Methodology

Food-101 ships only train and test splits. A fixed 4% class-stratified validation slice is carved out of **train** (seed 1337) and shared by every pipeline; the 25,250-image test split stays untouched until final evaluation. Reporting model-selection numbers on test is the most common way projects like this overstate themselves.

Nutrition figures are USDA reference values for a typical serving. Real portions vary, and this is not dietary advice.

**Data:** [Food-101](https://data.vision.ee.ethz.ch/cvl/datasets_extra/food-101/) · [USDA FoodData Central, SR Legacy](https://fdc.nal.usda.gov/)
