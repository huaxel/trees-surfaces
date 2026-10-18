# Equal-length canopy check

Nonoverlapping full windows from each source endpoint separately; exclude incomplete remainders. Reverse-anchor results overlap forward-anchor results and are sensitivity checks, not extra observations.

10 windows per anchoring scheme; 1000 m of 1295.5 m analysed per scheme.

Ranges below span windows and both endpoint choices. They are not confidence intervals.

| gid | Windows per anchor | Direct overlap range (%) | Within 5 m range (%) |
|---|---:|---:|---:|
| 266 | 5 | 0.0–60.8 | 68.2–100.0 |
| 5630 | 1 | 0.0–0.0 | 8.4–20.6 |
| 5634 | 1 | 0.0–0.0 | 0.0–3.0 |
| 5642 | 2 | 0.0–4.2 | 23.9–34.5 |
| 5643 | 1 | 0.0–0.0 | 0.0–0.0 |

## Limits

- Local frame, five road segments, no independent sampling or inferential tests
- Remainders excluded; endpoint sensitivity does not test every possible window placement
- 2021 vegetation with current geometry, including one recorded 2022 start
- Mapped canopy/proximity, not shade or exposure; classification omissions remain unvalidated

Source: VUB / Gallez et al. (2024), https://zenodo.org/records/13869065, CC BY 4.0; Brussels Mobility cycling-street geometry. Reuses the verified local extraction footprint. Temporary reproduction script: `.cache/vub-canopy-2021/equal_windows.py`.
