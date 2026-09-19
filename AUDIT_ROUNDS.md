# Later audit rounds

The original [AUDIT.md](AUDIT.md) covered the code as imported. This file records the
rounds that came after it, once the obvious faults were gone and the remaining ones had
to be hunted for.

Every fix below was **reproduced by running code before being changed**, and ships with
a test confirmed to fail against the pre-fix version. Where a fix turned out to deliver
less than it first appeared to, that is written down rather than smoothed over.

Suite: **548 backend + 95 extension tests**, from 349 + 60 at the end of the first pass.

---

## The two recurring bug classes

Two mistakes kept reappearing in unrelated files, which is worth stating plainly because
it predicts where the next one will be.

**Substring matching where whole words were meant** — eight instances. `"war" in text`
matched *warehouse* and capped innocent business copy at 45. `"pti"` matched inside
*corruption*, *adoption* and *consumption*, so a document with no sources reported a 36%
citation density. `"caution"` matched inside *precaution*, scoring a counter-argument
that was not there. Term lists now go through one boundary-matching helper.

**Confusing the subject of a claim with a source for it** — three instances. "The
Government is corrupt" counted as *citing* the government, because "government" is a
tier-1 source keyword. Naming who you are writing about is not evidence.

A third pattern emerged in these later rounds: **a feature reporting success while doing
nothing.** RAG served knowledge-free judgments while reporting `knowledge_used: 2`; an
admin's rubric change applied to one worker in four; reindexing blanked the knowledge
base while claiming to rebuild it. These are the most dangerous kind, because nothing
looks wrong from the outside.

---

## Round 2 — cache, ownership, citations, hearsay

**RAG was silently inert.** The AI cache key covered the text, model and content type,
but not the retrieved passages. A knowledge-free evaluation poisoned the cache, and
every later evaluation of that text reused the knowledge-free judgment while the
response reported `knowledge_used: 2`.

**Anyone could rename a tracked article.** The tracker took `owner` and `title` from the
latest evaluation, and `/api/evaluate` is unauthenticated by default. One anonymous
re-run blanked the writer's credit; anyone who knew a Google Doc id could repoint the
link. Both now come from the permission-checked `Document` row.

**The opinion-as-fact cap depended on paragraph order.** It used `low.find()`, checking
only the first occurrence of each marker, so if that one was attributed the marker
counted as clean — and swapping two paragraphs changed the score.

**Anonymous hearsay counted as sourcing.** "Critics say" needed to register as
attribution, but adding `say` also admitted "many people are saying" — precisely the
phrasing these rules exist to catch. `"sources said"` had the same flaw from the start.
Vague attribution is now stripped before the attribution list is applied. Whose sources
they are is the distinction that matters, so "Ministry sources said" still attributes
while a bare "sources said" does not.

## Round 3 — hearsay laundering, fact-check ranking

**Adding a fake attribution made a flag disappear.** Nation-First treated any attribution
word as evidence, so "sources say the Government is completely corrupt" escaped review
while the identical sentence without the prefix was flagged. The inverse of the module's
purpose.

**The fact-check worklist ignored source quality.** `source_tier` was recorded and then
never consulted for any claim without a figure, so a claim resting on a tweet ranked
`low` — the same as one resting on a Supreme Court judgment. The equivalent rule already
existed for statistics and had simply never been generalised.

## Round 4 — counting, figures, blending

**One concession earned double credit.** Reasoning signals were counted with
`sum(haystack.count(n) for n in needles)`, letting overlapping terms claim the same
span: "although" counted twice, as *although* and *though*.

**Statistics were extracted mangled.** The pattern matched the tail of a decimal rather
than the number: "5.5%" yielded "5%", "$1.5 million" matched twice as "$1" and
"5 million". Detection happened to survive it, so no call site misbehaved — but any
caller reading the matched text would have quoted the writer a figure they never wrote.

**The no-API-key path drifted.** When the model said nothing about a dimension, the
blend fell back to the rules score — after quantising it to the nearest 5 and blending
it with itself. Every dimension moved by up to a point. With no API key that is the
whole score.

---

## Round 5 — concurrency and infrastructure

**An editor's decision could vanish.** Two editors acting on one submitted article — one
approving, one scrapping — each validated against the status they had read, each wrote,
and *each received 200 OK*. The scrap disappeared and the article went on to publication
carrying a sign-off. `submitted → scrapped` and `submitted → approved` are both
individually valid; nothing checked the row still held the status it had validated
against. Fixed with optimistic locking; the loser now gets a 409.

**A new writer's first login could 500.** User provisioning was check-then-insert against
a unique email column. Four simultaneous first logins: two succeeded, two crashed.

**Reindexing blanked the knowledge base.** `reindex_all` cleared the store and then
rebuilt it, and an admin can trigger it against a live service. Every evaluation
arriving during the rebuild scored without the handbook.

> Proving this needed care. A watcher thread sampling `store.count()` **passes against
> the buggy code** — the rebuild is sub-millisecond and the sampler never lands in the
> empty window. Reading at a fixed point inside the rebuild shows it exactly: pre-fix a
> reader observes `[0, 4, 8, 12, 16]`, post-fix `[20, 20, 20, 20, 20]`.

**An admin's rubric change reached one worker in four.** The override cache is a
per-process dict loaded at startup, and the deployment guide runs four workers. The same
article scored accuracy at 0.50 or 0.25 depending on which worker answered, indefinitely.
Workers now re-read the overrides table when their cache is over 30 seconds old.

**Webhooks delayed the user's response.** Failures were already swallowed, so "the
evaluation path never depends on them" held for correctness — but not for latency. Each
webhook was posted in turn, inside the request, with an 8-second timeout: two hung
webhooks added sixteen seconds to a response for a message the user never sees. Now
concurrent and scheduled in the background. Two handoffs, `PUBLISHED` and `REVISING`,
were never announced at all.

**Eight identical model calls for one document.** Concurrent evaluations of the same
article all missed the cache and all called the model — eight times the cost and the
rate-limit consumption for one answer. This is the ordinary case, not a rare one. A
single-flight map now collapses them to one call.

**RAG retrieval stalled the event loop.** Embedding and searching is synchronous CPU work
scaling with the corpus: 13 ms at 551 chunks, 38 ms at 1671. Every other in-flight
request waited that long, however unrelated.

> This fix delivers less than it looks like. Moving the work to a thread cuts the stall
> from ~25 ms to ~14 ms median, but the cosine loop is pure Python and holds the GIL, so
> **four concurrent retrievals still cost about four times one.** One of the new tests
> originally asserted that they overlap. They do not, and that assertion was claiming a
> benefit the change does not provide, so it was replaced with one that records the
> serialisation and will fail if retrieval ever does become parallel. Real concurrency
> needs a vectorised search or Qdrant.

**Every timestamp meant one of two things.** A single response carried both
`2026-09-19T21:47:13` (read back from SQLite, which stores no offset) and
`2026-09-20T15:47:13+00:00` (computed in Python). A browser reads the first as *local*
time, so for a reader in IST an evaluation timestamp moved five and a half hours and
could appear to be in the future. The SLA arithmetic was already safe — it had a private
helper doing exactly this conversion, which is what made it obvious the API serialisers
had never been given the same treatment.

**One phrase, three penalties.** "Needless to say" is in `BIAS_PHRASES`, `AI_CLICHES` and
reasoning's `FILLER`, and was charged by each, so the penalty depended on how many lists
happened to contain a phrase rather than on how bad it was. Writing now charges once;
accuracy keeps its own charge, because asserting certainty without evidence is a
different fault. Three distinct reasoning findings also shared the title "Reasoning gap",
so a report showed one heading three times and read as a single complaint repeated.

---

## What is not fixed

**Retrieval is not parallel.** See the note above. It is off the event loop, which is
what unblocks unrelated requests, but concurrent retrievals still serialise on the GIL.
The fix is Qdrant or a vectorised search, both already recommended in
[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for multi-worker deployments.

**Rubric changes take up to 30 seconds to propagate** across workers, rather than being
instant. The database is the source of truth and the window is bounded, but a worker can
briefly score on weights an admin has just changed.

**No provider has been called for real.** Everything on the AI path is exercised against
recorded and stand-in clients. The first live call against OpenRouter or Anthropic will
be the first real test of the prompt, the repair loop and the timeout ceiling.
