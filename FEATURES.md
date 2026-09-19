# Jalebi — What's Built and What Isn't

**For:** anyone deciding what to fund or build next. No technical knowledge needed.
**Date:** 19 September 2026

Everything below was checked against the actual code, not from memory.

---

## The short version

**Jalebi works today, for TIES, on one machine.** A writer can open a Google Doc, get
a score with specific feedback, see whether it meets the SOP, and move it through
assignment → review → sign-off.

**Three things stop it being finished:** it has never been deployed anywhere real, only
TIES can use it, and no working editor has confirmed the scores match their judgement.

---

## Part 1 — Built and working

| Feature | What it does |
|---|---|
| **Scoring** | Reads a draft and scores it out of 100 across seven areas — accuracy, insight, narrative, depth, sourcing, writing, headline |
| **Explains the score** | Every criticism quotes the actual sentence and says what to do about it |
| **Works without AI** | About 72% of the score comes from fixed rules. No API key, no cost, and the same text always scores the same |
| **Hard limits** | A fabricated quotation caps the score at 0 no matter how good the rest is. Six such rules |
| **SOP compliance** | Checks the header block, the 300–350 word window, subheadings, and the references section |
| **Fact-check worklist** | Lists every claim needing checking, hardest first, with the nearest citation attached |
| **Production loop** | Assignment → drafting → review → revision → sign-off, with the SOP's own deadline windows |
| **Overdue tracking** | Shows which articles are past their window, in red |
| **Editor sign-off** | Approving a piece that fails its checks requires a written reason, which is recorded |
| **Reassign / scrap** | The editor's veto, with a mandatory reason |
| **Integrity recording** | Stores the AI% and plagiarism% the editor obtained, and applies the 20%/15% caps |
| **Inline grammar** | Underlines mistakes as you type, on any website. Never reads passwords or card details |
| **Google Docs integration** | Reads the document, can highlight problems and leave comments in it |
| **Accounts and roles** | Writer / editor / admin, with Google sign-in |
| **Admin dashboard** | Article tracker, writer performance, scoring weights, audit log |
| **Tunable weights** | An admin can change how much each area counts, and it takes effect immediately |

---

## Part 2 — Not built

Split by why it matters, not by difficulty.

### Blocking a real launch

| Missing | What it means in practice | Effort |
|---|---|---|
| **Never deployed** | It has only ever run on one laptop. Nobody has installed it on a server, and no real user has touched it | 1–2 days |
| **No editor has checked the scores** | I tested it with seven articles I wrote myself. A working editor has not confirmed the scores match their judgement — which is the whole point of the product | A few hours of an editor's time |
| **Never called a real AI provider** | The AI half has never been switched on. The rules half works; the connection to Claude or GPT is untested | Half a day + an API key |

### Blocking anyone outside TIES

| Missing | What it means in practice | Effort |
|---|---|---|
| **Only knows TIES' standards** | A perfectly good American article loses 27 points for spelling "normalized" instead of "normalised". Everything is hardcoded to TIES: house style, word limits, deadlines, approved news sources | 2–3 weeks |
| **One organisation only** | There is no concept of separate companies. Two newsrooms cannot use the same installation without seeing each other's work | 2 weeks |
| **No setup wizard** | A new team would have to hand-write their editorial standards into a config file. Almost nobody will | 2 weeks |
| **Chrome Web Store rejection risk** | The grammar checker reads text fields on every website. Google is likely to refuse to list it as-is | 1 week |

### Would make it better

| Missing | What it means in practice | Effort |
|---|---|---|
| **Nobody chases deadlines** | Overdue articles are shown in red, but nothing emails or messages anyone about them | 2–3 days |
| **No email** | Notifications go to Slack or Teams only | 2 days |
| **No assignment briefs** | An editor can assign an article and set a word count, but the topic, angle and reference links from the SOP have nowhere to live | 3–4 days |
| **No reports** | You cannot export the tracker or writer statistics to a spreadsheet or PDF | 2–3 days |
| **Can't check formatting** | The SOP requires Times New Roman, 12pt, 1.5 spacing. Jalebi reads the text only, so it cannot see any of that | 1 week |
| **Can't verify facts** | It finds claims needing checking; it cannot confirm whether a source supports one. **This is deliberate** — a tool that appeared to fact-check would be believed, and it would be wrong | Not recommended |
| **No AI-writing detection** | **Deliberately not built.** Published research found these tools wrongly accuse non-native English writers 61% of the time. Jalebi records the editor's own checker results instead | Not recommended |

---

## Part 3 — What I'd do next

| Order | What | Why | Cost |
|---|---|---|---|
| **1** | Have an editor score five real articles by hand, then compare | Cheapest, and it either validates the whole premise or reveals it needs work. Everything else is wasted if the scores don't match editorial judgement | Hours |
| **2** | Deploy it somewhere real and run the TIES pilot | It cannot be trusted until it has run outside a laptop | 1–2 days |
| **3** | Turn on a real AI provider and check it holds up | The remaining 28% of the score has never run | Half a day |
| **4** | Make the standards configurable | The single change that turns this from a TIES tool into a product | 2–3 weeks |

Steps 1–3 together are under a week and would tell you whether step 4 is worth funding.

---

## One thing worth understanding

Two features are **deliberately absent**, not unfinished:

**It will not verify facts.** It finds every claim that needs checking and ranks them, but never says "this is true". A tool that appeared to fact-check would be trusted to, and would eventually be confidently wrong about something that mattered.

**It will not detect AI writing.** A Stanford study found commercial AI detectors falsely flagged **61% of essays by non-native English writers**. Several universities have switched them off. Jalebi records the numbers your editor obtains from their own tools instead — which is both more honest and more accurate.

Both decisions could be reversed. I'd argue against it.
