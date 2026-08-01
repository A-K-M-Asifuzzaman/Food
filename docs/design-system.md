# FoodGenome AI — Design System

**Theme:** Spider-Man: Brand New Day, read as a *comic print* language rather than a
character skin. No Spider-Man iconography, no costume imagery, no trademarked marks — the
theme lives in ink, dots, panels and kinetic motion. That keeps it legally clean for a
public portfolio piece and, more importantly, makes it look designed rather than
merchandised.

**Explicitly rejected** (user instruction, §2.1 of `prompt.md`): the common gradient-mesh
SaaS look. No purple-to-blue blurs, no glassmorphism, no floating rounded cards on a soft
gradient.

---

## 1. The organising idea

FoodGenome AI and a spider's web share one primitive: **the strand**. A DNA helix and a
web are the same shape family. That is the spine of the system.

| Concept | Strand expression |
|---|---|
| Nutrient profile | double helix — the "genome" of a dish |
| GraphRAG knowledge graph | a literal web of dish → ingredient → nutrient nodes |
| Navigation, transitions | web-lines that shoot, connect and snap |
| Loading / progress | a strand being spun |

Every 3D element in this project is justified by a real feature. Nothing is decorative
for its own sake — see §6.

---

## 2. Colour

Ink-on-newsprint, not glow-on-dark. The palette is small and high-contrast, the way
comic printing actually works.

| Token | Value | Role |
|---|---|---|
| `--ink` | `#0B0B0F` | near-black, primary text and panel borders |
| `--newsprint` | `#F4F1E8` | warm off-white page — never pure white |
| `--red` | `#E62429` | primary action, the classic comic red |
| `--red-deep` | `#A4161A` | pressed states, shadow side of red |
| `--blue` | `#1B4CE0` | secondary, links, the web-blue |
| `--blue-deep` | `#0A2A66` | depth, night panels |
| `--cyan` | `#22D3EE` | data highlight, chart accent |
| `--amber` | `#F5A524` | warnings, "check this" states |
| `--green` | `#16A34A` | confirmed, grounded, healthy |
| `--halftone` | `rgba(11,11,15,0.14)` | Ben-Day dot ink |

**Dark mode is a night-panel inversion**, not a grey wash: `--ink` becomes the page,
`--newsprint` becomes the text, red and cyan stay saturated. Both modes must be designed —
the viewer's theme toggle has to win in both directions.

**Semantic colour is reserved for meaning, never decoration.** Green means *grounded in a
source*. Amber means *low confidence or large conformal set*. Red means *rejected as
non-food or failed grounding*. If those colours appear anywhere they don't carry that
meaning, the signal is destroyed.

---

## 3. Type

| Role | Face | Notes |
|---|---|---|
| Display / SFX | a heavy condensed grotesk or comic-display face | tight tracking, uppercase, slight rotation on impact words |
| Body | a highly legible humanist sans | this is a *nutrition* app — numbers must be unambiguous |
| Data / mono | a tabular-figure mono | **tabular figures are mandatory** so digits align in nutrition tables |

Nutrition figures are the product. Legibility beats style wherever they meet: numbers get
the clean face, drama goes to headings and SFX.

---

## 4. Surface language

- **Panels, not cards.** Hard 2–3 px `--ink` borders, square or barely-rounded corners,
  offset hard shadows (no blur). Comic panels have weight and edge.
- **Ben-Day halftone** as texture on fills, sized 3–6 px, never over body text.
- **Action lines** for emphasis and motion direction, used sparingly.
- **Diagonal panel breaks** for section transitions — the classic comic page cut.
- **SFX typography** on real events only: `THWIP` on a successful web-connect,
  `KRAK` on an error. Tie sound-words to system state so they read as feedback, not noise.

---

## 5. Motion

Comic motion is **snappy and staged**, not smooth and floaty. Ease-out, short durations,
overshoot on entry.

| Token | Value |
|---|---|
| `--dur-instant` | 90 ms |
| `--dur-snap` | 180 ms |
| `--dur-panel` | 320 ms |
| `--ease-snap` | `cubic-bezier(0.2, 0.9, 0.1, 1)` |
| `--ease-overshoot` | `cubic-bezier(0.34, 1.56, 0.64, 1)` |

Signature transitions: panel-to-panel wipe on route change; web-shot reveal where a strand
fires out and the panel snaps in behind it; halftone dissolve on image load.

**`prefers-reduced-motion` is honoured everywhere.** Reduced mode keeps opacity fades and
drops all transform, parallax and 3D auto-motion. This is not optional politeness — motion
sensitivity is a real accessibility need and a reviewer will check it.

---

## 6. Where 3D earns its place

Every one of these is a real feature made visible. If a 3D element cannot be justified by
data it displays, it does not ship.

1. **Depth-map portion view.** Stage 6 estimates food volume from monocular depth.
   Rendering that depth map as a rotatable 3D surface *is* the feature. No competing food
   app shows this — it is the single strongest differentiator in the product.
2. **GraphRAG web.** The dish → ingredient → nutrient graph from stage 8, rendered as an
   interactive 3D web. Real data, on-theme, and it makes the RAG grounding visible.
3. **Nutrient helix.** The macro/micro profile as a double strand — the "genome" reading.
4. **Confidence field.** Conformal prediction sets shown as competing candidates with
   visual weight proportional to calibrated probability.

**Stack:** React Three Fiber + drei, GSAP for staged timelines, Lenis for scroll. WebGPU
where available with a WebGL fallback.

---

## 7. Performance discipline

This is what separates genuinely premium work from a flashy demo. A janky hero reads as
amateur no matter how good the shader is.

- 3D is **lazy-loaded** and never blocks the core upload → result path.
- The critical path — pick photo, get prediction, read nutrition — must work with **zero
  3D loaded**.
- Target 60 fps on a mid-range phone; degrade particle counts and shadow quality by device
  capability rather than shipping one heavy scene.
- Respect `prefers-reduced-motion` and `prefers-reduced-data`.
- Every image `max-width: 100%`; wide tables scroll inside their own container so the page
  body never scrolls horizontally.

---

## 8. Accessibility

- Contrast ≥ 4.5:1 for body text in **both** themes. The newsprint/ink pairing is chosen
  partly because it passes comfortably.
- Colour is never the sole carrier of meaning — confidence states pair colour with a label
  and an icon.
- Full keyboard navigation; visible focus rings styled as comic panel outlines rather than
  suppressed.
- 3D canvases are `aria-hidden` with an equivalent accessible data table beside them. A
  screen-reader user must be able to read the nutrition figures the helix encodes.
