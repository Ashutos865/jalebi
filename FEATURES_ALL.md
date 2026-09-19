# Jalebi — Every Feature, Explained

**For:** anyone who wants to know what this thing actually does. No technical
knowledge assumed.
**Date:** 19 September 2026

Every row was checked against the working code. Where something is built but
unproven, the table says so rather than implying it is finished.

**Status key:** ✅ Built and tested · ⚠️ Built, never used in the real world ·
🔧 Needs setup first · ❌ Not built

---

## 1. Writing help, while you type

Works on any website — Gmail, LinkedIn, X, Notion, WordPress, your CMS.

| Feature | What you see | Status |
|---|---|---|
| Mistakes underlined in place | A coloured line under the exact word, like Grammarly | ✅ |
| Colour tells you the type | Red = spelling or grammar · Blue = punctuation · Purple = style | ✅ |
| Hover to see the problem | A small card explains what is wrong in plain words | ✅ |
| One-click fixes | Up to four suggested corrections as buttons — click to apply | ✅ |
| Rewrite the whole sentence | "Rewrite with AI" offers 2–3 better versions of the sentence | 🔧 needs an AI key |
| Dismiss a suggestion | Hide one you disagree with, for this session | ✅ |
| Personal dictionary | Add a word so it stops being flagged, permanently | ✅ |
| Turn it off | A single switch in Settings | ✅ |
| Never reads private fields | Passwords, card numbers and one-time codes are skipped | ✅ |

**What it catches:** typos, repeated words, "a" vs "an", missing or extra spaces,
capital letters, passive voice, wordy phrases, redundant phrases, filler.

**Optional upgrade:** connect a LanguageTool server and you get thousands of
professional grammar rules instead of the built-in set. 🔧

---

## 2. Editorial scoring — the main event

This is what makes Jalebi different from a grammar checker. It judges whether a
piece is **good enough to publish**.

| Feature | What you see | Status |
|---|---|---|
| A score out of 100 | One number, with the verdict: Ready to Publish, Needs Minor Revision, Needs Major Revision, or Not Ready | ✅ |
| Seven areas scored separately | Accuracy · Insight · Narrative · Depth · Sourcing · Writing · Headline | ✅ |
| Every criticism quotes your text | It shows the actual sentence it means, never vague advice | ✅ |
| Says what to do about it | Problem, why it matters, and the specific fix | ✅ |
| Lists what is good | Strengths, so feedback is not purely negative | ✅ |
| Numbered next steps | What to fix first | ✅ |
| Works with no AI at all | About 72% of the score is fixed rules — no key, no cost, same answer every time | ✅ |
| Hard limits that cannot be argued with | A made-up quotation caps the score at 0 regardless of everything else. Six such rules | ✅ |
| Different standards per article type | Breaking news is judged on accuracy; opinion on insight | ✅ |
| Detects the article type for you | Suggests whether it is news, analysis, opinion, etc. | ✅ |
| Change the weightings | An admin can decide how much each area counts, and it applies immediately | ✅ |

---

## 3. Fact-checking support

Jalebi **finds what needs checking**. It never claims something is true.

| Feature | What you see | Status |
|---|---|---|
| Fact-check worklist | Every claim needing verification, hardest first, with its nearest source link | ✅ |
| Risk ranking | An unsourced quotation or statistic ranks above an attributed one | ✅ |
| Unsourced statistics flagged | A number with no source is called out and caps the score | ✅ |
| Source quality rating | Six tiers, from government data down to social media | ✅ |
| Citation gaps | Claims sitting too far from any source | ✅ |
| Loaded language | Bias phrases, absolutes ("always", "never"), hedging | ✅ |
| Editorial red lines | Unsourced attacks on institutions raised for the editor to judge — **never an automatic penalty** | ✅ |
| Actually verifying a fact | **Deliberately not built** — see the note at the end | ❌ |

---

## 4. Following your editorial standards (the SOP)

| Feature | What you see | Status |
|---|---|---|
| Header block check | Confirms all nine required fields are filled in | ✅ |
| Word count check | Flags anything outside the 300–350 window, and says how much to cut or add | ✅ |
| Structure check | Warns if there are no subheadings, or no bullet points or key takeaways | ✅ |
| References check | Confirms a references section exists and contains real links | ✅ |
| Header does not skew the score | The metadata block is excluded from the article being judged | ✅ |
| Compliance panel | A simple pass/fail list in the sidebar | ✅ |
| Only appears when relevant | Ordinary drafts are not covered in red failures | ✅ |

---

## 5. The production loop

| Feature | What you see | Status |
|---|---|---|
| Assign an article | Set the writer, the editor and the word count | ✅ |
| Stage tracking | Assigned → Drafting → Submitted → Under review → Revising → Approved → Published | ✅ |
| Cannot skip stages | An article cannot jump from assigned to approved | ✅ |
| Deadline clocks | Uses your SOP's own windows: 12–18h drafting, 10–12h editing | ✅ |
| Overdue shown in red | With hours remaining, or hours overdue | ✅ |
| Amber warning | When a piece is past target but inside the limit | ✅ |
| Submit from the sidebar | The writer hands off without leaving the document | ✅ |
| Editor sign-off ("GTG") | Records who approved and when | ✅ |
| Override with a reason | Approving despite failing checks requires a written explanation, which is recorded | ✅ |
| Reassign or scrap | The editor's veto, with a mandatory reason | ✅ |
| Only editors can approve | Enforced by the server, not just hidden in the UI | ✅ |
| Slack / Teams alerts | On submission, approval, reassignment and scrapping | 🔧 needs a webhook |
| **Someone chasing overdue work** | Overdue is shown but nobody is told | ❌ |
| **Email notifications** | Slack and Teams only | ❌ |
| **Assignment briefs** | Topic, angle and reference links have nowhere to live | ❌ |

---

## 6. Google Docs

| Feature | What you see | Status |
|---|---|---|
| Reads your document | Detects a Google Doc and pulls the text in | ⚠️ untested with multiple Google accounts |
| Side panel | Everything appears beside the document, not over it | ✅ |
| Highlight problems in the doc | Marks the flagged passages in the document itself | 🔧 needs Google sign-in |
| Leave comments in the doc | Adds a comment with the fix on each flagged passage | 🔧 needs Google sign-in |
| Clear the marks | Removes everything Jalebi added | ✅ |
| Review workspace | A copy of your text where you can apply fixes and copy the result back | ✅ |
| Apply all fixes at once | One button | ✅ |
| **Checking font and spacing** | Times New Roman, 12pt, 1.5 spacing cannot be seen — Jalebi reads text only | ❌ |

---

## 7. Research integrity

| Feature | What you see | Status |
|---|---|---|
| Record AI and plagiarism percentages | The editor enters the figures from their own checker | ✅ |
| Applies your limits | 20% AI, 15% plagiarism | ✅ |
| Blocks clean sign-off | Approving with a breach requires a recorded reason | ✅ |
| Shows who checked and when | On the tracker | ✅ |
| Writers cannot certify themselves | Editor-only | ✅ |
| **Detecting AI writing itself** | **Deliberately not built** — see the note at the end | ❌ |

---

## 8. Accounts

| Feature | What you see | Status |
|---|---|---|
| Sign in with Google | Standard Google login | 🔧 needs Google setup |
| Email sign-in | Simple email + shared secret | ✅ |
| Three roles | Writer, Editor, Admin | ✅ |
| Demotion takes effect instantly | Removing someone's access is immediate | ✅ |
| Restrict who can join | By email address or company domain | ✅ |
| Refuses unsafe setup | Will not start with insecure settings on a live server | ✅ |

---

## 9. Dashboard (editors and admins)

Nine tabs, in the browser, no installation.

| Tab | What it shows | Status |
|---|---|---|
| Overview | Total articles, average score, pass rate, trend | ✅ |
| Documents | Every tracked article: stage, deadline, score trend, integrity results | ✅ |
| Writers | Per-writer averages and pass rates | ✅ |
| Issues | The most common problems across all articles | ✅ |
| AI Usage | Which model was used, how often | ✅ |
| Knowledge | Your editorial standards, searchable | ✅ |
| Rubrics | Change how much each scoring area counts | ✅ |
| Users | Manage roles and departments | ✅ |
| Logs | Audit trail of every significant action | ✅ |
| **Export to Excel or PDF** | Not available | ❌ |

---

## 10. AI providers

Jalebi works with none of these. Connecting one adds judgement on top of the rules.

| Feature | Detail | Status |
|---|---|---|
| Choose your provider | 11 supported: Claude, GPT, Gemini, Grok, OpenRouter, Groq, Together, DeepSeek, Mistral, Ollama, or none | ✅ |
| Run it entirely offline | Ollama runs a model on your own machine — nothing leaves it | 🔧 |
| Restrict which are allowed | Admin sets the permitted list | ✅ |
| Keys never reach the browser | They stay on your server | ✅ |
| Survives a slow provider | Times out and falls back to rules-only rather than hanging | ✅ |
| **Has ever been used for real** | No live call has ever been made | ⚠️ |

---

## 11. Knowledge base

| Feature | What you see | Status |
|---|---|---|
| Store your editorial standards | Handbook, approved articles, founder notes | ✅ |
| Used when scoring | Relevant passages are consulted automatically | ✅ |
| Searchable | From the dashboard | ✅ |
| Editors can add to it | Without touching code | ✅ |

---

## What is missing, in one place

| Missing | Effort |
|---|---|
| Never deployed anywhere real | 1–2 days |
| No editor has confirmed the scores are right | Hours of an editor's time |
| Never called a real AI provider | Half a day + a key |
| Only works for TIES' standards | 2–3 weeks |
| One organisation at a time | 2 weeks |
| Nobody chases overdue articles | 2–3 days |
| No email | 2 days |
| No assignment briefs | 3–4 days |
| No Excel or PDF export | 2–3 days |
| Cannot check font or spacing | 1 week |

---

## Two things left out on purpose

These look like gaps. They are decisions.

**Jalebi will not tell you a fact is true.** It finds every claim worth checking and
ranks them, but never verifies one. A tool that appeared to fact-check would be
believed — and would eventually be confidently wrong about something that mattered.
The editor checks; Jalebi makes sure nothing is missed.

**Jalebi will not detect AI writing.** A Stanford study found commercial AI detectors
falsely accused **61% of essays written by non-native English speakers**. Several
universities have switched them off for that reason. Jalebi records the numbers your
editor gets from their own tools instead — more honest, and more accurate.

Both could be added. I would argue against both.
