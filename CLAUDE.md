# Big Tech News — Curation Instructions

> This taxonomy reflects one person's interests. If you've forked this
> repo, edit the **Filter taxonomy** section to match yours — that's
> the whole point of having it in a file Claude reads.

This repo captures Techmeme story items into a local sqlite archive (`archive.db`)
and lets you generate HTML digests on demand. **Your job, when asked for a digest,
is curation only — never summarization.** The output must contain verbatim Techmeme
headlines and verified Techmeme cluster permalinks. No AI-written prose.

## How to generate a digest

When the user asks for "this week's digest", "the last week", "catch me up
since X", or similar, follow this **stable, incremental** flow. Re-running
over an overlapping window reuses prior judgments from the `curation` table
instead of re-deciding — that's the whole point of option 2.

1. **Compute the window** (see "Week semantics" below). Call it `START..END`.

2. **List items that have no prior verdict** in the window. These are the
   only items you need to think about this run:
   ```bash
   .venv/bin/python curate.py list-unjudged --start START --end END > /tmp/unjudged.json
   ```
   Items already judged in a prior run are NOT in this list. Do not re-judge
   them — their verdicts stand.

3. **Apply the filter taxonomy** (below) to the unjudged items. For each,
   decide `include` (with a section name) or `skip`. Build a verdicts JSON:
   ```json
   {
     "260411p5":  {"verdict": "include", "section": "AI model & product releases"},
     "260411p7":  {"verdict": "skip"},
     "260410p42": {"verdict": "include", "section": "Platform & policy"}
   }
   ```
   Use section names from the canonical list in the taxonomy — the renderer
   orders sections by that list.

4. **Write the verdicts:**
   ```bash
   .venv/bin/python curate.py write --verdicts /tmp/verdicts.json
   ```

5. **Render** from the window. The renderer reads `curation` and assembles
   sections from every `include` verdict in range. You never pass headlines
   or permalinks — those load verbatim from the DB.
   ```bash
   .venv/bin/python render.py \
     --window START..END \
     --title "Week of Apr 5 \u2013 Apr 11, 2026" \
     --subtitle "Sun 2026-04-05 \u2192 Sat 2026-04-11" \
     [--partial] \
     --out digests/2026-04-05_week.html
   ```

6. **Tell the user the path** so they can open it in their browser.

### Stability rules

- **Never re-judge an item with a prior verdict.** Prior decisions are
  authoritative. If the user wants to re-curate, they'll say so — run
  `curate.py clear --start START --end END` first, then start from step 2.
- **Sections are mutable only for new items.** An item filed in "Platform
  & policy" last run stays there, even if you'd re-bucket it now.

### Day filter in the rendered HTML

Each rendered digest has one button per day in the window across the top.
Clicking toggles that day off/on. All days start active. Days with zero
items are shown but disabled. State resets each time the page reloads —
intentionally simple. Do not add any persistence or extra controls to the
template without the user asking.

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

Use these as section names. Skip any section with zero items. Aim for a
reasonably even spread — if one section balloons past ~10 items while others
sit at 1\u20132, you're probably miscategorizing. See **Balance discipline** below.

- **AI model & product releases** \u2014 Major model launches (GPT-N, Claude N,
  Gemini N, Llama N, Mistral, DeepSeek, Qwen, Z.ai, etc.), proprietary or open
  source. New product *categories* from major labs (Operator-style agents,
  Sora-style video, agent harnesses, etc.). Also paid tier launches and
  pricing shifts from major labs when they reframe access (e.g., a new
  ChatGPT Pro tier with materially different limits).
- **Capability thresholds** \u2014 First time a model/system crosses a meaningful
  threshold (passes a major exam, wins a competition, ships a real-world
  autonomous service in a new city, first autonomous intelligence report
  from a government agency, etc.).
- **Revenue & scale milestones** \u2014 ARR, run-rate, revenue, or valuation
  milestones for category leaders; unit economics disclosures; capex/opex
  signals; mega-deals where the dollar figure itself *is* the story (e.g.,
  Anthropic's $30B run rate, AWS hitting $15B AI ARR, a $350B tender).
  This is the bucket for financial-scale signals; keep it separate from
  behavioral/usage signals below.
- **User behavior & adoption** \u2014 How people are actually using (or not
  using) these products: usage milestones by headcount (X hits N00M WAU),
  survey data on attitudes and habits, behavior shifts at scale, accuracy
  analyses that imply real-world impact, new distribution surfaces (native
  apps inside chatbots, etc.). Not financial milestones \u2014 those go above.
- **Platform & policy** \u2014 Platform rule changes, app store actions, and
  company policy proposals that move developer or user behavior (Apple
  opens/closes iOS doors, Anthropic bans wrappers, OpenAI policy proposals
  for a post-superintelligence world, EU AI Act enforcement, app store
  takedowns at state request). Mixes company policy and government policy
  when the effect is platform-level.
- **Infrastructure & compute** \u2014 Shifts symptomatic of demand or scarcity
  (data center buildouts/delays, compute deals, power constraints, custom
  silicon, Nvidia generations, new chip entrants, advanced packaging,
  lab-designed accelerators). Anthropic/Meta/OpenAI compute deals land here,
  not under Deals & funding.
- **Deals & funding** \u2014 Acquisitions, strategic partnerships, and funding
  rounds, consolidated into one bucket. Include only when the deal itself
  is the story: category-reshaping M&A, valuation-tier shifts for category
  leaders, mega-rounds that imply scale, strategic investor signals. Skip
  ordinary Series A/B/C. When an "infra deal" (e.g., Meta \u2192 CoreWeave) is
  really about compute capacity, route it to Infrastructure & compute
  instead.
- **Regulation & legal** \u2014 Significant developments even if unresolved
  (major lawsuits filed/settled, court rulings, antitrust action, new laws
  taking effect, state AG probes, first convictions under new laws). Skip
  incremental motions in long-running cases.
- **Geopolitics & trade** \u2014 Export controls, sanctions, chip wars, sovereign
  AI moves, cross-border chip smuggling cases. Skip generic diplomatic
  friction.
- **Hardware & devices** \u2014 Generational jumps, new entrants, devices that
  define or redefine a category, AR/VR/smartglasses partnerships, foldables
  and new form factors. Skip spec bumps.
- **Research & ideas** \u2014 Technical papers and durable essays with
  downstream implications (notable Anthropic/OpenAI/DeepMind papers,
  influential Karpathy/Sutton/etc. essays, urgent technical calls like
  post-quantum crypto rollouts). Skip blog posts that are just
  announcements. *This bucket is for written artifacts with durable claims,
  not interviews.*
- **Voices & interviews** \u2014 Q&As, profiles, podcasts, and public letters
  from people who matter (CEO Q&As, researcher interviews, notable profiles).
  Use when the interview itself is the surface for a newsworthy idea or
  candid statement. Sibling to Research & ideas: one is durable text, the
  other is spoken/conversational.
- **Industry narratives** \u2014 Beefs, exec departures, org restructures,
  leaked memos, and stories that *reshape how the industry is talked
  about*. Musk-vs-Altman level, or "Meta pulls top engineers into a new
  Applied AI division" level. Use sparingly; if a story is really a deal
  or a policy change, put it there.
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

### Calibration notes (lessons from past curation)

The user has overridden past exclusions enough times to establish these
inclusion bars. When in doubt, lean toward including items that match
these patterns:

- **Accuracy/reliability analyses at scale** are structural. "Gemini
  Overviews 90% accurate across 5T+ searches/year" = tens of millions of
  errors per hour, which is a behavioral signal, not a UX story.
- **Generational attitude surveys toward AI** are structural. Shifts in
  how under-30s feel about AI tools (hopefulness, daily use rates, trust)
  are paradigm signals worth including.
- **New distribution surfaces** are structural. First-of-kind native apps
  inside chatbots (Tubi in ChatGPT), AI features landing in system-level
  surfaces (Google News showing Polymarket), and platform integrations
  that imply a new pattern all count.
- **App store removals at government request** are structural, especially
  cross-border (CAC, EU, India). The act itself reshapes developer calculus.
- **State AG probes of frontier labs** count. A Florida AG probe of OpenAI
  is not routine political noise \u2014 probes of named frontier labs are
  structural because they signal where state enforcement is aiming.
- **Federal-vs-state AI policy friction** counts. When the White House
  pushes back on state AI bills (or vice versa), that's a live policy
  front, not day-to-day political noise.
- **Lawsuit amendments with novel relief asks** count. "Musk amends suit
  to ask Altman be removed from the nonprofit board" is not a procedural
  motion \u2014 the *ask itself* is the story. Same for first-of-kind
  injunctions, novel damages theories, or novel remedies.
- **Appeals court rulings on named frontier labs** count. A DC Circuit
  ruling on Anthropic's DOD designation is not a procedural motion. Any
  appellate ruling that names a frontier lab or big-tech defendant
  usually clears the bar.
- **First convictions under new laws** are capability thresholds for the
  legal system. Include them \u2014 they establish how a new statute actually
  gets enforced.
- **Gurman-on-Apple rumors** clear the rumor bar. Mark Gurman's Apple
  sourcing has a long enough track record that his Bloomberg reports on
  Apple product timing count as includable even when labeled "Sources:".
  Similar bar for Kuo-on-Apple-supply-chain.
- **AR/smartglasses infrastructure deals** count. Snap\u2013Qualcomm,
  Meta\u2013EssilorLuxottica, Apple\u2013Sony-optics, etc. The category is
  nascent enough that chip and optics partnerships are category-defining,
  not portfolio noise.
- **Frontier lab acquisitions of non-AI startups** count. When OpenAI,
  Anthropic, Google DeepMind, or Meta acquire a startup outside their
  core domain (e.g., OpenAI buying a personal finance app), the
  expansion intent is the story regardless of deal size. Include in
  Deals & funding.
- **Novel compute paradigms** count even at stealth/seed stage. Living
  neurons for AI chips, photonic computing, thermodynamic computing,
  etc. \u2014 if the approach is genuinely new (not just another chip
  startup), it clears the bar for Research & ideas. The paradigm is the
  story, not the funding stage.

### Balance discipline

Aim for roughly even volume across included sections. A digest where one
section holds 10+ items while four others hold 1 is usually a sign that the
fat bucket is absorbing items that belong elsewhere. Before finalizing:

- If **Infrastructure & compute** is crowded and **Deals & funding** is
  empty, you probably routed compute-capacity deals correctly \u2014 leave it.
- If **User behavior & adoption** is crowded, check whether some items are
  really **Revenue & scale milestones** (financial) and reroute.
- If **Industry narratives** is crowded, check whether some items are really
  **Deals & funding** (talent-for-hire, org buys) or **Platform & policy**
  (exec making a policy statement) and reroute.
- If a section has a single item, consider whether it's really significant
  enough to stand alone or should be dropped.
- Single-item sections are acceptable when the item is genuinely important
  and doesn't fit any other bucket (e.g., one crucial research paper). Don't
  force-merge unrelated items to avoid singletons.

### Edge-case rules

- **Deals & funding vs Infrastructure:** Compute-capacity deals (GW of TPU,
  multi-GW CoreWeave commits, fab partnerships) belong in Infrastructure &
  compute, even when the dollar figure is huge. Deals & funding is for
  deals where the *transaction* is the story, not the capacity.
- **Revenue vs Behavior:** "$30B ARR" is **Revenue & scale milestones**.
  "500M weekly users" is **User behavior & adoption**. If a headline has
  both, pick whichever the lead emphasizes.
- **Voices & interviews vs Research & ideas:** Karpathy tweet-essay = ideas.
  Brockman Q&A = voices. Written artifact with durable claims \u2192 ideas;
  spoken/conversational/profile \u2192 voices.
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
- **Day counts reflect Techmeme's own volume, not a curation quota.**
  Saturdays and Sundays run roughly a third to half of weekday volume
  (Sat ~10 leads/day, Sun ~13, weekdays ~23\u201337 based on local archive).
  Do not try to flatten the day filter by including weaker weekend items
  or dropping strong weekday ones. A quiet Sunday is just a quiet Sunday.
  Also: if the current day shows zero items, the 06:00 fetch may not
  have run yet — check before concluding anything about curation.

## Manual capture

If a digest is requested for a window not yet covered by the archive, run:
```bash
.venv/bin/python fetch.py --days N
```
where N covers the gap. Then proceed with curation.
