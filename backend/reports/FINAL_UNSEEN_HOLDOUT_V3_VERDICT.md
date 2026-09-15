# Final Unseen Holdout v3 — verdict

**Outcome:** VALID
**Created:** 2026-09-13T17:49:54.363486+00:00

The system was warm, the pack was locked, and the run completed. Whatever
is below is the v3 result — including clips lost to Whisper variance.

## Hard gates

| Gate | Measured | Threshold | Result |
|---|---|---|---|
| Overall intent | 0.8083 | >= 0.92 | FAIL |
| HC wrong | 0 | = 0 | PASS |
| Meaning lost | 0.0 | <= 0.01 | PASS |
| Compound gold-part | 0.5556 | >= 0.9 | FAIL |
| Simple median post | 2634.0 ms | <= 1500.0 ms | FAIL |
| Compound median post | 4091.0 ms | <= 2000.0 ms | FAIL |
| Warm-valid run | True | must be True | PASS |

## Targets (not gates)

| Target | Measured | Target | Met |
|---|---|---|---|
| Simple p95 | 6516.6 ms | <= 2000.0 ms | no |
| Compound p95 | 6935.7 ms | <= 3000.0 ms | no |

## Observations

- Whisper pass counts: {'1': 107, '2': 13, '3': 0}
- Clips whose transcript needed a term repair: 0/120
- Whisper is not deterministic across runs on this machine. That variance is
  part of the system under test; clips lost to it count against v3 and are
  not re-run.

## Per-clip

| clip | type | cond | passes | intent | HC | meaning lost | post ms | raw -> repaired |
|---|---|---|---|---|---|---|---|---|
| fuh3_001 | ultra_short | clean | 1 | Y | N | N | 1290.2 | Chunk Overlap |
| fuh3_002 | ultra_short | office | 1 | N | N | N | 2535.0 | Rer. Rer. Win? |
| fuh3_003 | ultra_short | poor | 1 | Y | N | N | 1257.8 | Drift meaning. Drift meaning? |
| fuh3_004 | ultra_short | far | 1 | Y | N | N | 1536.1 | P95 is fine. |
| fuh3_005 | ultra_short | fast | 1 | Y | N | N | 2106.3 | Item potency? |
| fuh3_006 | ultra_short | clean | 1 | Y | N | N | 1266.5 | LoRA, briefly. |
| fuh3_007 | ultra_short | office | 1 | Y | N | N | 2704.8 | or Gap sight? |
| fuh3_008 | ultra_short | poor | 1 | Y | N | N | 2270.7 | Your notice, period? |
| fuh3_009 | ultra_short | far | 1 | Y | N | N | 2207.8 | Redis, wonderful! |
| fuh3_010 | ultra_short | fast | 2 | Y | N | N | 2929.3 | Hybrid search. |
| fuh3_011 | ultra_short | clean | 1 | Y | N | N | 1214.1 | Golden Dataset |
| fuh3_012 | ultra_short | office | 1 | Y | N | N | 2632.8 | Canary roll out? Canary roll out? |
| fuh3_013 | ultra_short | poor | 1 | Y | N | N | 2394.8 | Temperature. Temperature, effect? |
| fuh3_014 | ultra_short | far | 1 | Y | N | N | 2179.7 | MCD quickly. |
| fuh3_015 | ultra_short | fast | 1 | Y | N | N | 1594.8 | Circuit breaker? |
| fuh3_016 | short | clean | 1 | Y | N | N | 1378.4 | How do you pick a chunk size? |
| fuh3_017 | short | office | 1 | Y | N | N | 1395.5 | What happens when to retrieved policies disagree |
| fuh3_018 | short | poor | 1 | Y | N | N | 1455.5 | Why not simply fine-tune on everything? |
| fuh3_019 | short | far | 1 | Y | N | N | 3180.5 | Who carries the brain when the agent is wrong? W |
| fuh3_020 | short | fast | 1 | Y | N | N | 1438.2 | How many GPU would we actually need? |
| fuh3_021 | short | clean | 1 | N | N | N | 2747.7 | Can it cope with scan documents? Can it cope wit |
| fuh3_022 | short | office | 1 | Y | N | N | 1766.9 | Do you stream tokens straight to the user? |
| fuh3_023 | short | poor | 1 | Y | N | N | 1369.6 | Is Kubernetes something you have run? |
| fuh3_024 | short | far | 1 | N | N | N | 2581.3 | How are we bathing away? |
| fuh3_025 | short | fast | 2 | Y | N | N | 3464.4 | What pushed you out of project management? |
| fuh3_026 | short | clean | 1 | N | N | N | 2860.4 | Which metric mattered for the dropout model? |
| fuh3_027 | short | office | 1 | Y | N | N | 2745.5 | Did any student record reach the model? Did any  |
| fuh3_028 | short | poor | 1 | N | N | N | 2846.5 | What stops the bill from exploding? What stops t |
| fuh3_029 | short | far | 1 | Y | N | N | 2750.7 | How do you go in approves in production? |
| fuh3_030 | short | fast | 1 | Y | N | N | 1552.4 | What would you build in your first three months? |
| fuh3_031 | medium | clean | 1 | Y | N | N | 2249.0 | If retrieval comes back empty, what should the u |
| fuh3_032 | medium | office | 1 | Y | N | N | 1480.3 | How would you stop one school from reading anoth |
| fuh3_033 | medium | poor | 2 | Y | N | N | 3366.7 | What tells you the embedding model is the weak l |
| fuh3_034 | medium | far | 2 | Y | N | N | 3416.4 | Supposed we swap the embedding model X-4. What h |
| fuh3_035 | medium | fast | 1 | Y | N | N | 1443.2 | How would you check that an answer is really sup |
| fuh3_036 | medium | clean | 2 | Y | N | N | 3132.9 | What would make you reach for a knowledge graph  |
| fuh3_037 | medium | office | 1 | Y | N | N | 2223.1 | Talk me through sizing hardware for an on-premis |
| fuh3_038 | medium | poor | 2 | Y | N | N | 3719.7 | How do you keep an agent from running the same a |
| fuh3_039 | medium | far | 1 | N | N | N | 2426.5 | When you watch on the dashboard, once this is li |
| fuh3_040 | medium | fast | 2 | Y | N | N | 3513.6 | How did you keep future information out of the e |
| fuh3_041 | medium | clean | 1 | Y | N | N | 1879.0 | Which libraries do you actually reach for day to |
| fuh3_042 | medium | office | 1 | Y | N | N | 2816.0 | How would you explain a retrieval failure to a h |
| fuh3_043 | medium | poor | 2 | Y | N | N | 3001.0 | What changes in your design if the users speak G |
| fuh3_044 | medium | far | 1 | Y | N | N | 1590.4 | When is a simple router enough, instead of super |
| fuh3_045 | medium | fast | 1 | Y | N | N | 3442.2 | How do you decide a system is ready to go live? |
| fuh3_046 | long | clean | 1 | Y | N | N | 2831.6 | We have 12 years of circulars in PDF, some scann |
| fuh3_047 | long | office | 1 | Y | N | N | 4020.1 | If a retrieved file contains a line telling the  |
| fuh3_048 | long | poor | 1 | Y | N | N | 2313.7 | Our regulations are rewritten every academic yea |
| fuh3_049 | long | far | 1 | Y | N | N | 3249.5 | Imagine the answer posts a paragraph that does n |
| fuh3_050 | long | fast | 1 | Y | N | N | 1391.7 | Describe how you would roll a new retriever into |
| fuh3_051 | long | clean | 1 | Y | N | N | 2772.1 | Explain what you would put in front of the model |
| fuh3_052 | long | office | 1 | N | N | N | 3006.7 | If the language model provider goes offline in t |
| fuh3_053 | long | poor | 1 | Y | N | N | 2667.5 | Tell me how you would raise a single slow reques |
| fuh3_054 | long | far | 1 | Y | N | N | 2169.7 | You inherited a system that answered confidently |
| fuh3_055 | long | fast | 1 | Y | N | N | 2520.8 | Walk me through the decision between calling a h |
| fuh3_056 | long | clean | 2 | Y | N | N | 5783.0 | Talk me through the voice kiosk you built and wh |
| fuh3_057 | long | office | 1 | Y | N | N | 1767.5 | How would you convince a finance director that t |
| fuh3_058 | long | poor | 1 | Y | N | N | 2206.1 | Describe how you would evaluate whether the retr |
| fuh3_059 | long | far | 1 | Y | N | N | 1726.8 | Suppose the teacher refuses the generated exam q |
| fuh3_060 | long | fast | 1 | Y | N | N | 1724.0 | Explain what a checkpoint gives you in a graph-b |
| fuh3_061 | very_long | clean | 1 | Y | N | N | 2716.0 | We are a ministry with confidential files per de |
| fuh3_062 | very_long | office | 1 | N | N | N | 7765.1 | Assume the pilot goes well, and suddenly 3,000 s |
| fuh3_063 | very_long | poor | 1 | Y | N | N | 4893.5 | I want to understand your judgment rather than y |
| fuh3_064 | very_long | far | 1 | Y | N | N | 2893.7 | A supplier upload a proposal that quietly contai |
| fuh3_065 | very_long | fast | 1 | Y | N | N | 2149.2 | A documents are half Arabic and half English, us |
| fuh3_066 | very_long | clean | 1 | N | N | N | 6516.6 | say we give the assistant the ability to open ti |
| fuh3_067 | very_long | office | 1 | Y | N | N | 2533.7 | Describe the full life cycle of one exam questio |
| fuh3_068 | very_long | poor | 1 | N | N | N | 6552.2 | If I asked you to cut the answer time in half wi |
| fuh3_069 | very_long | far | 1 | Y | N | N | 7087.1 | Tell me about the production incidents you perso |
| fuh3_070 | very_long | fast | 1 | Y | N | N | 7173.2 | We have a small team and no machine learning eng |
| fuh3_071 | very_long | clean | 1 | Y | N | N | 7173.7 | Imagine two specialized assistants reach opposit |
| fuh3_072 | very_long | office | 1 | Y | N | N | 3557.2 | Take me through how you would prove to an audito |
| fuh3_073 | very_long | poor | 1 | Y | N | N | 6160.7 | Explain the difference between a plane automatio |
| fuh3_074 | very_long | far | 1 | Y | N | N | 3373.3 | Suppose the model answers correct me 95% of time |
| fuh3_075 | very_long | fast | 1 | Y | N | N | 5246.3 | Describe how you would set up evaluation for thi |
| fuh3_076 | compound | clean | 1 | Y | N | N | 5124.0 | What is re-ranking, and when would you bother ad |
| fuh3_077 | compound | office | 1 | Y | N | N | 2917.7 | Explain hallucination and then tell me how you h |
| fuh3_078 | compound | poor | 1 | Y | N | N | 5065.8 | Tell me what a context window is, and say what y |
| fuh3_079 | compound | far | 1 | Y | N | N | 3899.8 | Describe the similarity checker, name the techno |
| fuh3_080 | compound | fast | 1 | Y | N | N | 2918.2 | What is overfitting? How do you spot it? And wha |
| fuh3_081 | compound | clean | 2 | Y | N | N | 6935.7 | Point me to your vector database experience, the |
| fuh3_082 | compound | office | 2 | Y | N | N | 5423.7 | Explain what an orchestrator does and when a sin |
| fuh3_083 | compound | poor | 1 | Y | N | N | 4234.3 | Give me your education background, your certific |
| fuh3_084 | compound | far | 1 | Y | N | N | 2216.3 | What is prompt injection? Where does it come fro |
| fuh3_085 | compound | fast | 1 | Y | N | N | 2248.3 | Tell me what Docker solves, how a container diff |
| fuh3_086 | compound | clean | 1 | Y | N | N | 4040.5 | Describe the early warning work, the metric you  |
| fuh3_087 | compound | office | 2 | Y | N | N | 4091.0 | Explain tool calling, say why the arguments need |
| fuh3_088 | compound | poor | 1 | Y | N | N | 3610.9 | What speech to text doing under the hood? Why di |
| fuh3_089 | compound | far | 1 | Y | N | N | 7197.5 | Give me the difference between the two draft lib |
| fuh3_090 | compound | fast | 2 | Y | N | N | 4444.3 | Cover four things for me, what embeddings are ho |
| fuh3_091 | indirect_paraphrase | clean | 1 | N | N | N | 2706.8 | Our head of department keeps saying the assistan |
| fuh3_092 | indirect_paraphrase | office | 1 | N | N | N | 2780.4 | Staff complained the answers changed after we sw |
| fuh3_093 | indirect_paraphrase | poor | 1 | N | N | N | 2813.3 | Finance notice the invoice tripled between Tuesd |
| fuh3_094 | indirect_paraphrase | far | 1 | N | N | N | 2457.8 | We keep in the right document, but the wrong par |
| fuh3_095 | indirect_paraphrase | fast | 1 | Y | N | N | 3188.4 | A colleague insists we should train the model on |
| fuh3_096 | indirect_paraphrase | clean | 1 | N | N | N | 2647.6 | The assistant answers beautifully, but nobody ca |
| fuh3_097 | indirect_paraphrase | office | 1 | N | N | N | 2634.0 | It keeps saying it cannot help, and the staff ha |
| fuh3_098 | indirect_paraphrase | poor | 1 | N | N | N | 3281.4 | Somebody from procurement was able to read a fil |
| fuh3_099 | indirect_paraphrase | far | 1 | N | N | N | 2930.3 | The assistant went round in circles for four min |
| fuh3_100 | indirect_paraphrase | fast | 1 | N | N | N | 2598.5 | We were in a pilot, and everyone liked it, but I |
| fuh3_101 | indirect_paraphrase | clean | 1 | N | N | N | 2718.4 | Do people ask the same thing and get to differen |
| fuh3_102 | indirect_paraphrase | office | 1 | N | N | N | 2426.2 | Our lawyers are nervous about anything leaving t |
| fuh3_103 | indirect_paraphrase | poor | 1 | Y | N | N | 2940.6 | You have been at the ministry three years. What  |
| fuh3_104 | indirect_paraphrase | far | 1 | N | N | N | 6220.9 | If we hired you, then you stop giving you intere |
| fuh3_105 | indirect_paraphrase | fast | 1 | Y | N | N | 1961.4 | I want to know what you are not good at, and I w |
| fuh3_106 | follow_up_contextual | clean | 1 | Y | N | N | 2047.5 | And what exactly was your part in it? |
| fuh3_107 | follow_up_contextual | office | 1 | Y | N | N | 2818.6 | All right, so how would you actually put one tog |
| fuh3_108 | follow_up_contextual | poor | 1 | Y | N | N | 2920.6 | And how does the search itself work on top of th |
| fuh3_109 | follow_up_contextual | far | 1 | Y | N | N | 3237.7 | So where does that differ from its ordinary work |
| fuh3_110 | follow_up_contextual | fast | 1 | Y | N | N | 1643.3 | How do you actually build those? |
| fuh3_111 | follow_up_contextual | clean | 1 | N | N | N | 6074.0 | And what do you do to keep it down? And what do  |
| fuh3_112 | follow_up_contextual | office | 1 | Y | N | N | 2363.0 | Which technologies sat behind that one? |
| fuh3_113 | follow_up_contextual | poor | 1 | Y | N | N | 2249.8 | So how do you keep it out of a model? |
| fuh3_114 | follow_up_contextual | far | 1 | Y | N | N | 2615.4 | In your usual way of preventing it, |
| fuh3_115 | follow_up_contextual | fast | 1 | Y | N | N | 2440.7 | Have you shipped anything with it yourself? Have |
| fuh3_116 | follow_up_contextual | clean | 1 | Y | N | N | 2563.7 | Would you still choose it for us? |
| fuh3_117 | follow_up_contextual | office | 1 | Y | N | N | 3925.7 | And where would you draw the line against retrie |
| fuh3_118 | follow_up_contextual | poor | 1 | Y | N | N | 2019.3 | What stops in your own design? |
| fuh3_119 | follow_up_contextual | far | 1 | Y | N | N | 1756.7 | What was the hard part there? |
| fuh3_120 | follow_up_contextual | fast | 1 | Y | N | N | 2073.8 | Why run that locally rather than a cloud service |

## Next

- A gate failed. If you fix a real bug after seeing this, v3 is VOID and a new unseen v4 pack is required.
