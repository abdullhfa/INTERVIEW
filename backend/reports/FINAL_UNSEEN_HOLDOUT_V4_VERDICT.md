# Final Unseen Holdout v4 — verdict

**Outcome:** VALID
**Created:** 2026-09-13T23:09:59.898373+00:00

The system was warm, the pack was locked, and the run completed. Whatever
is below is the v4 result — including clips lost to Whisper variance.

## Hard gates

| Gate | Measured | Threshold | Result |
|---|---|---|---|
| Overall intent | 0.825 | >= 0.92 | FAIL |
| HC wrong | 0 | = 0 | PASS |
| Meaning lost | 0.0 | <= 0.01 | PASS |
| Compound gold-part | 0.3944 | >= 0.9 | FAIL |
| Simple median post | 977.2 ms | <= 1500.0 ms | PASS |
| Compound median post | 1019.3 ms | <= 2000.0 ms | PASS |
| Warm-valid run | True | must be True | PASS |

## Targets (not gates)

| Target | Measured | Target | Met |
|---|---|---|---|
| Simple p95 | 1517.8 ms | <= 2000.0 ms | yes |
| Compound p95 | 1597.7 ms | <= 3000.0 ms | yes |

## Observations

- Whisper pass counts: {'1': 111, '2': 9, '3': 0}
- Clips whose transcript needed a term repair: 0/120
- Whisper is not deterministic across runs on this machine. That variance is
  part of the system under test; clips lost to it count against v4 and are
  not re-run.

## Per-clip

| clip | type | cond | passes | intent | HC | meaning lost | post ms | raw -> repaired |
|---|---|---|---|---|---|---|---|---|
| fuh4_001 | ultra_short | clean | 1 | Y | N | N | 846.5 |  |
| fuh4_002 | ultra_short | office | 1 | Y | N | N | 956.5 |  |
| fuh4_003 | ultra_short | poor | 1 | Y | N | N | 950.1 |  |
| fuh4_004 | ultra_short | far | 1 | N | N | N | 958.2 |  |
| fuh4_005 | ultra_short | fast | 1 | Y | N | N | 965.8 |  |
| fuh4_006 | ultra_short | clean | 1 | Y | N | N | 913.7 |  |
| fuh4_007 | ultra_short | office | 1 | Y | N | N | 1013.6 |  |
| fuh4_008 | ultra_short | poor | 1 | Y | N | N | 984.9 |  |
| fuh4_009 | ultra_short | far | 1 | Y | N | N | 898.6 |  |
| fuh4_010 | ultra_short | fast | 1 | N | N | N | 944.0 |  |
| fuh4_011 | ultra_short | clean | 1 | Y | N | N | 951.8 |  |
| fuh4_012 | ultra_short | office | 1 | Y | N | N | 936.7 |  |
| fuh4_013 | ultra_short | poor | 1 | Y | N | N | 905.5 |  |
| fuh4_014 | ultra_short | far | 1 | Y | N | N | 1044.8 |  |
| fuh4_015 | ultra_short | fast | 1 | Y | N | N | 973.0 |  |
| fuh4_016 | short | clean | 1 | Y | N | N | 970.7 |  |
| fuh4_017 | short | office | 1 | N | N | N | 1151.1 |  |
| fuh4_018 | short | poor | 1 | Y | N | N | 935.8 |  |
| fuh4_019 | short | far | 1 | Y | N | N | 1064.7 |  |
| fuh4_020 | short | fast | 1 | Y | N | N | 943.7 |  |
| fuh4_021 | short | clean | 1 | Y | N | N | 1063.9 |  |
| fuh4_022 | short | office | 1 | Y | N | N | 1054.3 |  |
| fuh4_023 | short | poor | 2 | Y | N | N | 1575.1 |  |
| fuh4_024 | short | far | 1 | Y | N | N | 948.3 |  |
| fuh4_025 | short | fast | 2 | Y | N | N | 1701.9 |  |
| fuh4_026 | short | clean | 1 | Y | N | N | 904.5 |  |
| fuh4_027 | short | office | 1 | Y | N | N | 1002.9 |  |
| fuh4_028 | short | poor | 1 | N | N | N | 1056.5 |  |
| fuh4_029 | short | far | 1 | N | N | N | 977.2 |  |
| fuh4_030 | short | fast | 1 | Y | N | N | 1037.8 |  |
| fuh4_031 | medium | clean | 1 | Y | N | N | 995.8 |  |
| fuh4_032 | medium | office | 1 | Y | N | N | 1018.8 |  |
| fuh4_033 | medium | poor | 1 | Y | N | N | 941.7 |  |
| fuh4_034 | medium | far | 1 | Y | N | N | 971.4 |  |
| fuh4_035 | medium | fast | 1 | Y | N | N | 853.0 |  |
| fuh4_036 | medium | clean | 2 | Y | N | N | 1589.4 |  |
| fuh4_037 | medium | office | 1 | Y | N | N | 1071.9 |  |
| fuh4_038 | medium | poor | 1 | Y | N | N | 957.2 |  |
| fuh4_039 | medium | far | 1 | Y | N | N | 953.9 |  |
| fuh4_040 | medium | fast | 1 | Y | N | N | 983.7 |  |
| fuh4_041 | medium | clean | 1 | Y | N | N | 841.4 |  |
| fuh4_042 | medium | office | 1 | Y | N | N | 974.7 |  |
| fuh4_043 | medium | poor | 1 | Y | N | N | 993.5 |  |
| fuh4_044 | medium | far | 1 | Y | N | N | 999.6 |  |
| fuh4_045 | medium | fast | 1 | Y | N | N | 906.7 |  |
| fuh4_046 | long | clean | 1 | Y | N | N | 945.3 |  |
| fuh4_047 | long | office | 1 | Y | N | N | 913.3 |  |
| fuh4_048 | long | poor | 1 | Y | N | N | 1058.0 |  |
| fuh4_049 | long | far | 1 | Y | N | N | 1028.2 |  |
| fuh4_050 | long | fast | 1 | Y | N | N | 843.6 |  |
| fuh4_051 | long | clean | 1 | Y | N | N | 1036.4 |  |
| fuh4_052 | long | office | 1 | Y | N | N | 1090.1 |  |
| fuh4_053 | long | poor | 1 | Y | N | N | 1026.3 |  |
| fuh4_054 | long | far | 1 | Y | N | N | 940.2 |  |
| fuh4_055 | long | fast | 1 | Y | N | N | 1117.3 |  |
| fuh4_056 | long | clean | 2 | Y | N | N | 1836.8 |  |
| fuh4_057 | long | office | 1 | Y | N | N | 1072.5 |  |
| fuh4_058 | long | poor | 1 | Y | N | N | 930.2 |  |
| fuh4_059 | long | far | 1 | Y | N | N | 1049.5 |  |
| fuh4_060 | long | fast | 1 | Y | N | N | 1041.3 |  |
| fuh4_061 | very_long | clean | 1 | Y | N | N | 1162.4 |  |
| fuh4_062 | very_long | office | 1 | N | N | N | 1105.0 |  |
| fuh4_063 | very_long | poor | 1 | Y | N | N | 1034.9 |  |
| fuh4_064 | very_long | far | 1 | Y | N | N | 948.3 |  |
| fuh4_065 | very_long | fast | 1 | Y | N | N | 1045.5 |  |
| fuh4_066 | very_long | clean | 1 | Y | N | N | 1207.0 |  |
| fuh4_067 | very_long | office | 1 | Y | N | N | 1007.9 |  |
| fuh4_068 | very_long | poor | 1 | Y | N | N | 1054.3 |  |
| fuh4_069 | very_long | far | 1 | N | N | N | 1095.6 |  |
| fuh4_070 | very_long | fast | 1 | Y | N | N | 926.0 |  |
| fuh4_071 | very_long | clean | 1 | Y | N | N | 1058.2 |  |
| fuh4_072 | very_long | office | 1 | Y | N | N | 963.0 |  |
| fuh4_073 | very_long | poor | 1 | Y | N | N | 1203.8 |  |
| fuh4_074 | very_long | far | 1 | N | N | N | 987.9 |  |
| fuh4_075 | very_long | fast | 1 | Y | N | N | 1012.4 |  |
| fuh4_076 | compound | clean | 2 | Y | N | N | 1597.7 |  |
| fuh4_077 | compound | office | 1 | Y | N | N | 978.2 |  |
| fuh4_078 | compound | poor | 2 | Y | N | N | 1526.3 |  |
| fuh4_079 | compound | far | 1 | Y | N | N | 1013.9 |  |
| fuh4_080 | compound | fast | 1 | Y | N | N | 1012.3 |  |
| fuh4_081 | compound | clean | 1 | Y | N | N | 989.9 |  |
| fuh4_082 | compound | office | 1 | Y | N | N | 1019.3 |  |
| fuh4_083 | compound | poor | 1 | Y | N | N | 1122.5 |  |
| fuh4_084 | compound | far | 1 | Y | N | N | 888.6 |  |
| fuh4_085 | compound | fast | 1 | Y | N | N | 932.6 |  |
| fuh4_086 | compound | clean | 1 | Y | N | N | 1061.4 |  |
| fuh4_087 | compound | office | 2 | Y | N | N | 1659.0 |  |
| fuh4_088 | compound | poor | 1 | Y | N | N | 1105.3 |  |
| fuh4_089 | compound | far | 1 | Y | N | N | 1217.3 |  |
| fuh4_090 | compound | fast | 1 | Y | N | N | 1012.3 |  |
| fuh4_091 | indirect_paraphrase | clean | 1 | N | N | N | 905.9 |  |
| fuh4_092 | indirect_paraphrase | office | 1 | N | N | N | 1061.1 |  |
| fuh4_093 | indirect_paraphrase | poor | 1 | N | N | N | 995.4 |  |
| fuh4_094 | indirect_paraphrase | far | 1 | N | N | N | 912.7 |  |
| fuh4_095 | indirect_paraphrase | fast | 1 | Y | N | N | 1005.8 |  |
| fuh4_096 | indirect_paraphrase | clean | 1 | N | N | N | 920.2 |  |
| fuh4_097 | indirect_paraphrase | office | 1 | N | N | N | 992.2 |  |
| fuh4_098 | indirect_paraphrase | poor | 1 | N | N | N | 998.0 |  |
| fuh4_099 | indirect_paraphrase | far | 2 | Y | N | N | 1589.8 |  |
| fuh4_100 | indirect_paraphrase | fast | 1 | Y | N | N | 975.7 |  |
| fuh4_101 | indirect_paraphrase | clean | 1 | N | N | N | 922.0 |  |
| fuh4_102 | indirect_paraphrase | office | 1 | Y | N | N | 881.0 |  |
| fuh4_103 | indirect_paraphrase | poor | 1 | N | N | N | 950.3 |  |
| fuh4_104 | indirect_paraphrase | far | 1 | N | N | N | 1112.9 |  |
| fuh4_105 | indirect_paraphrase | fast | 1 | Y | N | N | 923.2 |  |
| fuh4_106 | follow_up_contextual | clean | 1 | N | N | N | 984.8 |  |
| fuh4_107 | follow_up_contextual | office | 1 | Y | N | N | 976.7 |  |
| fuh4_108 | follow_up_contextual | poor | 1 | Y | N | N | 860.1 |  |
| fuh4_109 | follow_up_contextual | far | 1 | Y | N | N | 970.2 |  |
| fuh4_110 | follow_up_contextual | fast | 1 | Y | N | N | 1000.5 |  |
| fuh4_111 | follow_up_contextual | clean | 1 | N | N | N | 911.3 |  |
| fuh4_112 | follow_up_contextual | office | 1 | Y | N | N | 850.2 |  |
| fuh4_113 | follow_up_contextual | poor | 1 | Y | N | N | 983.1 |  |
| fuh4_114 | follow_up_contextual | far | 1 | Y | N | N | 884.9 |  |
| fuh4_115 | follow_up_contextual | fast | 1 | Y | N | N | 906.2 |  |
| fuh4_116 | follow_up_contextual | clean | 2 | Y | N | N | 1517.8 |  |
| fuh4_117 | follow_up_contextual | office | 1 | Y | N | N | 947.7 |  |
| fuh4_118 | follow_up_contextual | poor | 1 | N | N | N | 935.8 |  |
| fuh4_119 | follow_up_contextual | far | 1 | Y | N | N | 873.3 |  |
| fuh4_120 | follow_up_contextual | fast | 1 | Y | N | N | 969.0 |  |

## Next

- A gate failed. If you fix a real bug after seeing this, v4 is VOID and a new unseen v5 pack is required.
