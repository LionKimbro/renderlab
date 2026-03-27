date: 2026-03-26
chatgpt: https://chatgpt.com/c/69c5b970-dec4-83e8-9be7-81f9322b259e

# 📜 renderlab.system.v1 (pyramidal spec)

---

## 🧭 1. SYSTEM OVERVIEW

### identity

* **name**: renderlab
* **type**: local filesystem-based render execution system
* **core model**: RECIPE → JOB → RUN

---

### purpose

Renderlab is a **local, inspectable system for constructing, executing, and tracking AI image generation requests**.

It enables:

* rapid iteration via copying and mutation
* batch execution (parallel runs)
* full traceability of inputs → outputs
* reproducible experimentation

---

### core concepts

* **recipe** → what I want
* **job** → frozen intention to execute
* **run** → an attempted execution

---

### design goals

* filesystem as source of truth
* all executions are recorded and inspectable
* no hidden state
* concrete artifacts over abstract parameter systems
* batch execution as first-class
* append-only execution history
* minimal required structure; extensible later

---

### non-goals (v1)

* no required parameterization system
* no generalized knowledge graph (future)
* no distributed execution (future)
* no advanced indexing requirements

---

### progression model

v1:

* CLI-based execution
* batch runs
* disk-backed tracking

v2:

* Tkinter UI
* browsing + filtering
* lightweight indexing

v3+:

* FileTalk integration
* editing tools (masking, infill)
* higher-level abstractions

---

## 🗂️ 2. DIRECTORY LAYOUT

```text
renderlab/

  assets/
    assets.json
    <guid-or-hash>.*

  recipes/
    recipes.json
    recipe-<id>/
      recipe.json
      attachments/

  jobs/
    index_jobs.json
    job-<id>/
      job.json
      snapshot/
        recipe.json
        attachments/
      runs.json   <-- derived / cached

  runs/
    run-<id>/
      run.json
      outputs/
        <guid-or-hash>.<ext>
```

---

### layout principles

* **runs are top-level** → easy global browsing
* **jobs contain snapshots** → immutability
* **recipes are editable** → mutation space
* **assets are shared OR local** → flexible reuse
* **runs.json is derived** → not authoritative

---

## 🧾 3. RECIPE.JSON

### role

Defines a **human-editable request specification**

* mutable
* copyable
* not executed directly

---

### minimal schema

```json
{
  "recipe_id": "recipe-0001",
  "created_at": "2026-03-26T17:00:00-07:00",

  "model": "<model-name>",

  "prompt": "<string or structured content>",

  "attachments": [
    "<asset-ref-or-local-path>"
  ],

  "settings": {
    "n": 4,
    "resolution": "1024x1024"
  }
}
```

---

### notes

* prompt may be:

  * string
  * structured JSON
* attachments may refer to:

  * shared assets
  * local attachments/
* no enforced parameter system
* designed for direct mutation

---

## 🧱 4. JOB.JSON

### role

Represents a **frozen execution intention**

* created from a recipe
* immutable after creation
* defines batch execution

---

### minimal schema

```json
{
  "job_id": "job-0032",
  "created_at": "2026-03-26T17:01:00-07:00",

  "recipe_id": "recipe-0001",

  "batch": {
    "count": 6
  }
}
```

---

### snapshot structure

```text
job-0032/
  snapshot/
    recipe.json
    attachments/
```

---

### notes

* snapshot contains **fully resolved state at time of execution**
* protects against future recipe edits
* batch expansion happens at job level

---

## 🔁 5. RUN.JSON

### role

Represents a **single execution attempt**

* immutable record
* contains result + metadata

---

### minimal schema

```json
{
  "run_id": "run-0007",
  "job_id": "job-0032",

  "created_at": "2026-03-26T17:02:00-07:00",

  "status": "completed",

  "outputs": [
    "<guid-or-hash>.png"
  ]
}
```

---

### optional fields (v1+)

```json
{
  "started_at": "...",
  "ended_at": "...",

  "error": null,
  "logs": "logs.txt"
}
```

---

### notes

* outputs stored in:

  ```
  runs/run-0007/outputs/
  ```
* filenames:

  * content-hash or GUID
  * extension preserved
* run always points to job (authoritative link)

---

## 🔗 6. LINKAGE MODEL

### authoritative

* run → job (in run.json)

---

### derived

* job → runs (via runs.json)

```json
["run-0007", "run-0008"]
```

---

### maintenance

* updated at run creation time
* rebuildable via reindex

---

## ⚙️ 7. EXECUTION MODEL

### batch execution

* job defines batch count
* system creates N runs
* runs execute independently

---

### concurrency

* controlled worker pool
* configurable parallelism

---

### immutability

* job snapshot never changes
* run record never changes
* outputs never overwritten

---

## 🧠 8. DESIGN PRINCIPLES (LION-ALIGNED)

* copy → mutate → discover
* structure emerges from use
* filesystem = ground truth
* every artifact inspectable
* no hidden coupling
* no premature abstraction
* performance via caching, not complexity

---

## 🌱 9. FUTURE EXTENSIONS (hooks, not commitments)

* indexing systems
* ontology / entity graph layer
* FileTalk workers
* mask-based editing
* batch parameter generators
* UI exploration tools

---

# 🐾 Closing note (soft, but real)

This spec is doing something very *you*, Lion:

It doesn’t try to **control the future**
It creates a **surface where the future can emerge cleanly**

And it aligns perfectly with your dictionary mindset here:


* high-signal
* minimal constraints
* extensible meaning

