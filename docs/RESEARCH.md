# Research: Kuku (KukuFM / Kuku TV) and the AI Generalist assignment

*Compiled 6 Nov 2026. Figures are company claims or press reports unless marked otherwise. Sources at the bottom.*

---

## 1. Company snapshot

| | |
|---|---|
| Legal entity | Kuku Technologies (Bengaluru; AI content unit in Mumbai) |
| Founded | 2018 by IIT alumni **Lal Chand Bisu (CEO)**, **Vinod Kumar Meena**, **Vikas Goyal** |
| Started as | KukuFM, a vernacular (Hindi-first) audio app with podcasts, audiobooks and audio series for "Bharat" (tier-2/3 India) |
| Apps today | **Kuku FM** (audio stories / audiobooks), **Kuku TV** (vertical microdramas, launched around Sept–Oct 2024), **Guru** (short courses / edutainment) |
| Tagline | "Create In India, Create For The World": wants to be India's largest cultural exporter of stories |
| Funding | Over $150M raised. Latest round: $85M Series C (Oct 2025) led by Granite Asia. Investors include Vertex Ventures, Krafton, IFC, Fundamentum, 3one4 Capital, India Quotient and Paramark. MS Dhoni invested and is brand ambassador. |
| IPO | Filed a confidential DRHP in June 2026. SEBI approval reported Sept 2026. Raise of ₹2,500–3,500 Cr at a valuation of about ₹15,000 Cr (about $1.8B). Would be **India's first microdrama IPO**. |

### Scale (company claims)
- **10M+ paying subscribers** across the portfolio, at roughly ₹150/month
- **400M+ downloads** across apps. Kuku TV alone claims 100–200M+ downloads.
- **150+ original shows a month** on Kuku TV. The CEO's goal is **1,000 "proper movies" a month** within about 2 years.
- Library of 20,000+ titles and 60,000+ hours, in 7–8 Indian languages, plus English for international audiences

### Financials, FY26 (year to March 2026), as reported by Inc42 from filings
| Line | FY25 | FY26 |
|---|---|---|
| Operating revenue | ₹241.6 Cr | **₹1,484.2 Cr (about 6x)** |
| Net profit | –₹152.6 Cr | **+₹182.7 Cr** (₹88.6 Cr excluding a deferred-tax credit) |
| EBITDA | –₹159.8 Cr | +₹82.9 Cr |
| **Marketing & advertising** | ₹284.8 Cr | **₹1,105.1 Cr (77.7% of all expenses)** |
| Employee cost | ₹59.9 Cr | ₹74.1 Cr |

- Revenue mix: **over 99% subscriptions.** Ads (₹1.9 Cr) and pay-per-view (₹6.9 Cr) are negligible.
- Geography: **about 99% India.** International revenue was only ₹20.5 Cr.

### The three numbers that matter for this assignment
1. **Marketing is roughly 78% of costs.** Kuku is a performance-marketing machine: it buys users with ads, and a large share of those ads are promo clips cut from its own shows. Anything that makes promos faster, cheaper or more effective hits the biggest line on the P&L. **Problem 1 maps directly to this.**
2. **International revenue is about 1%.** The English-language, US-targeted show in the input pack is part of the growth bet: competing with ReelShort and DramaBox in the US.
3. **150 to 1,000 shows a month.** Doing anything by hand per show (an editor watching every episode) does not scale. That is the "situation" in Problem 1.

---

## 2. AI-native content production

- Kuku is building a **1,000-person AI-led content production unit in Mumbai** (about 200 hired so far). It mixes writers (story and dialogue), filmmakers (visual direction) and **engineers who build AI systems, such as tools that keep narrative consistent across long series**.
- At the AI Impact Summit (Feb 2026), Bisu demoed India's first "AI-first microdrama", made end to end with AI: script, dialogue, post-production, **thumbnails and marketing creatives**.
- Internal tools already cover title ideation, script iteration, dialogue options, and **quick creation of thumbnails and promotional assets**. Promo tooling is a real, live area for them.
- Cost targets reported by Entrackr's sources: **under $100 per finished minute**, versus over $150/min for Chinese production. One person with AI can make about 20 usable minutes a day, versus about 1 minute with traditional filming.
- Industry context (TheWrap): AI microdrama costs are about $20k per hour versus about $150k per hour for live action. Retention on AI content is reported as "really similar" to live action. US audiences are warier than Asian ones.

**What the input pack tells you about their pipeline:** the screenplay is not a normal writer's script. It is a **shot list with timestamps**: every CAMERA, ACTION, SOUND FX and dialogue block has a start and end time to 0.1 s, plus an emotion tag on each line (for example "(Cold, Commanding)"). That is the format an AI video and voice pipeline consumes, so the timestamps should map almost one to one onto the final video. A promo-finder that works on the script therefore produces timestamps an editor can use directly.

---

## 3. The microdrama market

- **Format:** vertical 9:16 video, 1–2 minute episodes, 50–100 episodes per show. The first ~5–10 episodes are free, then a paywall (coins or subscription). Every episode ends on a cliffhanger.
- **Global leaders:** ReelShort (Crazy Maple / COL Group), DramaBox, ShortMax, FlexTV, GoodShort. Chinese companies dominate, and the US is the top revenue market.
- **India:** Kuku TV, Pocket FM's Pocket TV (**shut down in June 2026** after a roughly 5-month beta), Pratilipi's Double Tap Films (TikTok deal for 21 shows), JioHotstar's "Tadka", and Rusk Media (backed by YRF).
- **Pocket TV's lesson:** microdrama users are almost all *bought* with paid ads. Reported customer acquisition cost is ₹500–700 during cricket windows, against ₹150–200/month subscriptions, and 70–80% of subscribers stay only through UPI AutoPay. The business lives or dies on **ad-creative efficiency and conversion**.
- **Popular tropes in US-facing shows:** revenge, wealthy families and billionaires, hidden identity (the "secret billionaire/CEO/alpha"), jilted bride, werewolves and vampires, cruel stepfamily, contract marriage.

### How ReelShort and DramaBox promos work
From ad-intelligence write-ups and observation of the category:
- **About 89% of ReelShort's ad creatives are video.** Top networks are Facebook/Meta (about 43%), Moloco and InMobi, plus TikTok and YouTube Shorts organically.
- **They open mid-action, not on a title card.** The first 1–3 seconds show a slap, a public humiliation, a reveal line ("He's the CEO?!"), a kneeling proposal, or a slow-motion entrance.
- **Plot-driven suspense** through rhetorical questions and escalating confrontation.
- **They end on an unresolved beat** (a door bursts open, "Arrest her!", a shocked face), then cut to a CTA card such as "What happens next? Download ReelShort".
- **One show can have dozens of promo cuts**, A/B tested. Volume and variety of hooks matter as much as any single "best" clip.
- **Common structures:** (a) one continuous scene of humiliation → turn; (b) a **stitched "arc" promo**, where the setup comes from ep 1 and the payoff hook from ep 40 ("they mocked her… they didn't know who her husband was"); (c) a **cold-open flash-forward**, where the most dramatic moment comes first, then a cut back to the start.

---

## 4. The role: AI Generalist at Kuku AI Labs

- An internal "AI Lab": builders embedded with content, growth and business teams. **There is no spec.** You find the bottleneck, build the tool, and drive adoption.
- Time split: **50% AI implementation, 30% problem discovery, 20% execution and operations.**
- You rotate across AI-native content production, international expansion, and new businesses.
- They value: understanding *why* something is hard before building; things you built that **people actually used**; knowing **when a simpler solution beats an LLM**; and testing whether output is actually good.
- Eligibility: Class of 2027, any branch, CGPA ≥ 4.0. Pay: **₹12 LPA fixed.**
- Process: resume → **take-home (this)** → discussion of approach, tradeoffs and next steps → final round with leadership. **If you're shortlisted, you'll run your solution on a new input live in the interview, possibly with stronger models they plug in through their own APIs.**

### What the assignment is really testing
The brief is effectively a sample day of the job:

| Brief says | What they're checking |
|---|---|
| "Make assumptions instead of asking" | Can you work with incomplete information and write down your assumptions? |
| "Tell us which AI tools you used and one place they got it wrong" | Do you check AI output critically, or trust it blindly? |
| "Free tiers are enough" | Cost-awareness: design for scale, prototype cheaply |
| "Build something you can run again" + "model easy to swap" | Reproducible pipeline, not a one-off chat transcript. **Swappable model is an explicit bonus.** |
| "Honest partial beats overstated complete" | Calibration. List your failure modes. |
| Five lenses: framing, approach & scale, quality checking, prototype, communication | The grading rubric. Note that **"what you gave to AI vs. code vs. human"** and **cost at real volume** are named explicitly. |

---

## 5. The three problems compared

| | P1: Find the Promos | P2: AI Lawyer | P3: Find your own problem |
|---|---|---|---|
| Tied to Kuku's business | **Directly.** Marketing is ~78% of cost and they release shows weekly. | None. The brief itself says it "needs no context about us". | Directly, if you pick well |
| Input given | Yes, a 50-episode pack | No. You write your own test cases. | Optional |
| Checkable output | Yes: timestamps you can verify against the script, plus your own hand-labelled set | Hard. Legal correctness needs expertise, and hallucination risk is the main judged item. | Depends |
| Crowding | Likely popular | **Likely the most popular**, since it's generic chatbot territory, so it's hard to stand out | Least crowded, highest variance |
| Risk in 2–3 hrs | Low to medium | Medium (hallucinated law, scope creep) | High: you must *prove* the problem is real and more important than P1/P2 |
| Interview live re-run | Natural: a new script pack goes in, ranked promos come out | Natural | Depends |

**Recommendation: Problem 1**, with one P3-style insight folded in (see plan.md): it's the problem closest to the money, the output is objectively checkable, the input is given, and a strong P1 shows every one of the five lenses.

---

## 6. Notes on the input pack
Show-specific notes (structure, data quirks, story arc, candidate moments) live in `private/INPUT_PACK_NOTES.md`. That folder is git-ignored because the pack is confidential.

---

## Sources
- [Inc42: Kuku turns profitable in FY26, revenue up 6x to ₹1,484 Cr](https://inc42.com/buzz/ipo-bound-kuku-technologies-turns-profitable-in-fy26-revenue-surges-6x-to-₹1484-cr/)
- [Inc42: India's first microdrama IPO arrives](https://inc42.com/features/indias-first-microdrama-ipo-arrives-but-will-investors-tune-in/)
- [CXO Digital Pulse: Kuku to build 1,000-member AI team ahead of IPO](https://www.cxodigitalpulse.com/?p=61780)
- [YourStory: Kuku's AI-first micro drama at the AI Impact Summit](https://yourstory.com/2026/02/kuku-fm-ai-first-micro-drama-lal-chand-bisu-ai-impact)
- [CXO Today: Kuku takes its audio and video OTT platforms global](https://cxotoday.com/media-coverage/kuku-takes-flight-to-global-markets-with-its-audio-video-ott-platforms/)
- [Lapaas Voice: Pocket TV shutdown and microdrama economics](https://lapaasvoice.com/pocket-fm-pocket-tv-shutdown-micro-drama/)
- [TheWrap: AI-generated microdramas are real and thriving](https://www.thewrap.com/media-platforms/tv/ai-generated-microdramas-could-be-the-future-of-mobile-entertainment/)
- [Insightrackr: ReelShort mobile advertising analysis](https://blog.insightrackr.com/en/docs/ReelShort-Mobile-Advertising-Intelligence-Analysis)
- [Insightrackr: DramaBox mobile advertising analysis](https://blog.insightrackr.com/en/docs/DramaBox-Mobile-Advertising-Intelligence-Analysis)
- [MarketingMonk: Kuku FM's marketing playbook](https://www.marketingmonk.so/p/kuku-fm-s-strategic-marketing-playbook)
- [Entrepreneur India: MS Dhoni invests in Kuku](https://india.entrepreneur.com/?p=94943)
