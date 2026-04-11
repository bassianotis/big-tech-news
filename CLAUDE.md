# Big Tech News — Curation Instructions

> This taxonomy reflects one person's interests. If you've forked this
> repo, edit the **Filter taxonomy** section to match yours — that's
> the whole point of having it in a file Claude reads.

This repo captures Techmeme story items into a local sqlite archive (`archive.db`)
and lets you generate HTML digests on demand. **Your job, when asked for a digest,
is curation only — never summarization.** The output must contain verbatim Techmeme
headlines and verified Techmeme cluster permalinks. No AI-written prose.

## How to generate a digest

When the user asks for "this week's digest", "the last week", "catch me up since X",
or similar:

1. **Compute the window** (see "Week semantics" below).
2. **Query `archive.db`** for items in the window. Default to lead items only:
   ```sql
   SELECT id, item_date, headline, source
     FROM items
    WHERE is_lead = 1
      AND item_date BETWEEN ? AND ?
    ORDER BY item_date, id;
   ```
3. **Apply the filter taxonomy** (below) to choose which items to include and
   bucket each into a section.
4. **Build a JSON spec** in this exact shape:
   ```json
   {
     "title": "Week of Apr 5 \u2013 Apr 11, 2026",
     "subtitle": "Sun 2026-04-05 \u2192 Sat 2026-04-11",
     "partial": false,
     "sections": [
       {"name": "AI model & product releases", "item_ids": ["260408p42", "260409p3"]},
       {"name": "Platform & policy", "item_ids": ["260404p2"]}
     ]
   }
   ```
5. **Render** by piping the spec to `render.py`:
   ```bash
   .venv/bin/python render.py --out digests/2026-04-05_week.html < /tmp/spec.json
   ```
   (Or use `--spec /tmp/spec.json`.) The renderer looks every id up in the DB
   and emits the verbatim headline + verified permalink. Never put headlines or
   permalinks in the spec yourself.
6. **Tell the user the path** so they can open it in their browser.

## Week semantics

- A **week** is **Sunday \u2192 Saturday**, inclusive on both ends.
- **"This week"** = the most recent Sunday (inclusive) through today (inclusive).
  If today is Wed 2026-04-08, "this week" = Sun 2026-04-05 \u2192 Wed 2026-04-08
  (4 days) and the digest is **partial** (`"partial": true`, filename suffix
  `_partial`).
- **"Last week"** = the previous fully-completed Sun \u2192 Sat block.
- **"Last N weeks"** = N completed weeks before this week. By default skip the
  current partial week unless the user says otherwise.
- **Filename convention:** `digests/YYYY-MM-DD_week.html` where `YYYY-MM-DD` is
  the **Sunday** anchoring the week. Partial current weeks get
  `digests/YYYY-MM-DD_week_partial.html`. Multi-week digests:
  `digests/YYYY-MM-DD_to_YYYY-MM-DD.html`.
- **Title format:** `Week of Mon DD \u2013 Mon DD, YYYY` (e.g. `Week of Apr 5 \u2013 Apr 11, 2026`).
- Always present a single window per digest unless the user explicitly asks
  for stacked windows.

## Filter taxonomy

The goal is to surface **structurally significant** stories the user would
regret missing — paradigm shifts, threshold-crossings, infrastructure shifts,
new behaviors at scale — and skip routine churn. The user is not interested in
"what happened today", but "what shifted that I should know about".

When in doubt: **err toward inclusion for structural items, exclusion for
churn.** A digest of ~10\u201325 items per week is typical. If you find yourself
with >35 items in a week, you're probably being too generous; tighten.

### INCLUDE

Use these as section names. Skip any section with zero items.

- **AI model & product releases** \u2014 Major model launches (GPT-N, Claude N,
  Gemini N, Llama N, Mistral, DeepSeek, Qwen, etc.), proprietary or open
  source. New product *categories* from major labs (Operator-style agents,
  Sora-style video, Vision Pro, etc.).
- **Capability thresholds** \u2014 First time a model/system crosses a meaningful
  threshold (passes a major exam, wins a competition, ships a real-world
  autonomous service in a new city, etc.).
- **Adoption & usage shifts** \u2014 Usage milestones with structural meaning
  (X hits N00M weekly users, ARR milestones for category leaders, traffic
  collapses for incumbents, behavior change at scale).
- **Platform & policy** \u2014 Platform rule changes that move developer or user
  behavior (Apple opens iOS to alternative stores, Anthropic bans wrappers,
  EU AI Act enforcement, app store policy shifts).
- **Infrastructure & compute** \u2014 Shifts symptomatic of demand or scarcity
  (data center buildouts/delays, compute deals, power constraints, custom
  silicon, Nvidia generations, new chip entrants).
- **M&A and strategic deals** \u2014 Acquisitions or partnerships that reshape a
  category, not just expand a portfolio. Big-number deals where the *strategic
  signal* matters.
- **Funding** \u2014 Only when paradigm-signaling: new valuation tier for a
  category leader, mega-rounds that imply scale, strategic investor signals.
  Skip ordinary Series A/B/C.
- **Regulation & legal** \u2014 Significant developments even if unresolved
  (major lawsuits filed/settled, court rulings, antitrust action, new laws
  taking effect). Skip incremental motions in long-running cases.
- **Geopolitics & trade** \u2014 Export controls, sanctions, chip wars, sovereign
  AI moves. Skip generic diplomatic friction.
- **Hardware & devices** \u2014 Generational jumps, new entrants, devices that
  define or redefine a category. Skip spec bumps.
- **Research & ideas** \u2014 Papers, essays, or talks with downstream
  implications (notable Anthropic/OpenAI/DeepMind papers, influential
  Karpathy/Sutton/etc. essays). Skip blog posts that are just announcements.
- **Drama & narratives** \u2014 Beefs, public letters, exec departures, leaks
  that *reshape an industry narrative*. Musk-vs-Altman level, not random
  sniping. Use sparingly.
- **Beyond AI** \u2014 Catch-all for structurally significant non-AI tech
  (crypto/stablecoin milestones, biotech, space, EVs, social, search). Use
  this section if there are 1\u20133 items that don't fit elsewhere; otherwise
  promote them into their own section.

### SKIP

- Routine quarterly earnings beats/misses (unless the result is itself a
  paradigm signal, e.g. "AI capex now exceeds X% of total tech capex").
- Stock price movements / market cap milestones with no story behind them.
- Ordinary funding rounds (Series A/B/C of non-defining startups).
- Ordinary exec changes (VP shuffles, departures without strategic context).
- Incremental product updates (new emoji picker, settings redesign, minor
  feature flips).
- Conference announcements without substance ("X to keynote at Y").
- Day-to-day political noise that doesn't translate into industry change.
- Procedural court motions in long-running cases.
- Single-source rumor or speculation without corroboration.

### Edge-case rules

- **Funding/M&A:** Include only if the headline itself implies a strategic or
  market shift (valuation tier, category-defining acquisition). When unsure,
  exclude.
- **Earnings:** Include only when the *content* of the earnings release is the
  story (e.g., a major capex commitment, a guidance reset that reframes the
  category), not the beat/miss itself.
- **Rumors:** Include "Sources:" / "Report:" stories from credible outlets
  (Bloomberg, FT, Reuters, The Information, NYT) when the substance would
  matter even if loosely confirmed. Skip blog rumors.
- **Open source vs proprietary:** Same bar for both. A Llama or DeepSeek
  release is as important as a GPT release.
- **Non-AI:** Welcome whenever structurally significant. Don't force AI
  framing.

## Working notes

- The DB has both `is_lead = 1` and `is_lead = 0` items. **Default to leads.**
  Non-leads are usually secondary coverage of the same cluster and would
  produce duplicates.
- Items can carry into adjacent days because Techmeme's daily page includes
  recent items. The `item_date` column reflects the canonical date encoded in
  the Techmeme item id.
- Re-running `fetch.py` is always safe (idempotent upsert).
- Re-curating an old digest is fine: regenerate the spec, render to a new
  filename, the old file stays.
- If you need raw item context, query the DB directly with sqlite3. Don't
  fetch Techmeme yourself during curation; the archive is the source of truth.
- The `source` column on items can help you spot reputable outlets when
  judging borderline rumor stories.

## Manual capture

If a digest is requested for a window not yet covered by the archive, run:
```bash
.venv/bin/python fetch.py --days N
```
where N covers the gap. Then proceed with curation.
