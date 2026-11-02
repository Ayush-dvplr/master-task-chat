# Contrast across 90 (scripts/contrast.py output)

| feature | HardExpert (n=14) median | Medium (n=25) median | Easy (n=51) median |
|---|---|---|---|
| final | 23.5 | 45.6 | 63.6 |
| tests | 7.49 | 23.9 | 55.2 |
| rubric | 33.2 | 65 | 76.9 |
| loss_tests | 46.2 | 38.1 | 22.4 |
| loss_judge | 33.4 | 17.5 | 11.5 |
| n_tests | 30 | 27 | 27 |
| h_hidden_wshare | 0.677 | 0.155 | 0.179 |
| h_hidden_mean_w | 4.97 | 4.29 | 4.43 |
| h_shipped_mean_w | 2.68 | 3.38 | 3.2 |
| h_hidden_pass | 0.013 | 0.038 | 0.333 |
| h_shipped_pass | 0.198 | 0.25 | 0.649 |
| top1 | 0.052 | 0.062 | 0.06 |
| distinct_w | 3 | 3 | 3 |
| n_rub | 19.5 | 27 | 19 |
| n_rub_neg | 3.5 | 7 | 4 |
| rub_P | 42 | 60 | 53 |
| rub_fig_share | 0.151 | 0 | 0 |
| rub_trajprobe_share | 0.326 | 0.316 | 0.818 |
| rub_neg_applied_w | 0 | 0 | 0 |
| instr_words | 652 | 691 | 652 |
| n_data_files | 41.5 | 48 | 54 |
| data_kb | 753 | 1.28e+03 | 973 |
| agent_min | 30.2 | 24 | 17.7 |
| steps | 73 | 63 | 52 |
| first_write_min | 9.45 | 5.9 | 6.8 |
| selftests | 6 | 5 | 6 |
| used_time_share | 0.23 | 0.13 | 0.14 |
| truth_bytes | 2.43e+04 | 1.97e+04 | 1.98e+04 |

- tp_subprocess: HardExpert 13/14; Medium 24/25; Easy 49/51
- tp_seeded: HardExpert 11/14; Medium 23/25; Easy 46/51
- h_induction_instr: HardExpert 5/14; Medium 13/25; Easy 27/51
- h_induction_truth: HardExpert 8/14; Medium 12/25; Easy 11/51

## Which side loses the points (count of tasks where judge loss > tests loss)
- HardExpert: judge-dominant 4/14; tests<85 13; rubric<85 14; final<40 14
- Medium: judge-dominant 5/25; tests<85 25; rubric<85 20; final<40 4
- Easy: judge-dominant 21/51; tests<85 42; rubric<85 36; final<40 0

## Our gate (tests<85 AND rubric<85 AND final<40) across 90
- pass: 17 -> ['18b5d99f', '3f39299a', '42e79476', '4a5f9738', '59417607', '5b2b0901', '6d12f970', '7c2e77a1', '80202e15', '8defd7be', '9f5486ac', 'aa314fee', 'b51a883e', 'b5c7b14c', 'd22ff871', 'd49e259f', 'df8f123b']

## Confound: contributor (toml author) -> bands
- Abdus Samad Ali: n=5 HardExpert=2 Medium=0 Easy=3 median_final=61.4
- Harshank Kanungo: n=15 HardExpert=2 Medium=8 Easy=5 median_final=47.4
- Aditya Jain: n=5 HardExpert=2 Medium=3 Easy=0 median_final=39.7
- Anjali Kumari: n=7 HardExpert=2 Medium=4 Easy=1 median_final=39.0
- Ayush Sah: n=4 HardExpert=2 Medium=1 Easy=1 median_final=37.5
- Bhavik Jain: n=3 HardExpert=2 Medium=0 Easy=1 median_final=34.5
- Sanvi Gupta: n=5 HardExpert=1 Medium=0 Easy=4 median_final=63.6
- Aditya Patel: n=8 HardExpert=1 Medium=1 Easy=6 median_final=56.4
- Aryan Mehta: n=8 HardExpert=0 Medium=3 Easy=5 median_final=51.4
- Kunwar Singh: n=5 HardExpert=0 Medium=2 Easy=3 median_final=52.5
- Nikhil Bansal: n=11 HardExpert=0 Medium=1 Easy=10 median_final=64.4
- Shubhi Goyal: n=4 HardExpert=0 Medium=0 Easy=4 median_final=70.6
- Harsh Gupta: n=4 HardExpert=0 Medium=0 Easy=4 median_final=60.3
- Aniket Datta: n=4 HardExpert=0 Medium=0 Easy=4 median_final=62.8
- Aditya Joshi: n=2 HardExpert=0 Medium=2 Easy=0 median_final=42.4

## Confound: category -> bands
- Data Processing: n=25 HardExpert=5 Medium=4 Easy=16
- Software Engineering: n=12 HardExpert=1 Medium=5 Easy=6
- Debugging: n=9 HardExpert=1 Medium=1 Easy=7
- Optimization: n=6 HardExpert=3 Medium=1 Easy=2
- Scientific Computing: n=5 HardExpert=0 Medium=1 Easy=4
- Machine Learning: n=4 HardExpert=1 Medium=0 Easy=3
- Security: n=3 HardExpert=0 Medium=1 Easy=2
- Personal Assistant: n=3 HardExpert=2 Medium=0 Easy=1
- Data Science: n=3 HardExpert=0 Medium=2 Easy=1
- Video Processing: n=3 HardExpert=0 Medium=1 Easy=2
- System Administration: n=3 HardExpert=0 Medium=2 Easy=1
- Data Reconciliation: n=2 HardExpert=0 Medium=0 Easy=2
- File Operations: n=2 HardExpert=0 Medium=1 Easy=1
- Model Training: n=2 HardExpert=0 Medium=1 Easy=1
- Reverse Engineering: n=2 HardExpert=1 Medium=1 Easy=0
- Mathematics: n=1 HardExpert=0 Medium=1 Easy=0
- Data Querying: n=1 HardExpert=0 Medium=1 Easy=0
- Game Replay Reverse Engineering: n=1 HardExpert=0 Medium=1 Easy=0
- CLI Repair and Configuration Generation: n=1 HardExpert=0 Medium=0 Easy=1
- Games: n=1 HardExpert=0 Medium=1 Easy=0
- Binary Format Implementation: n=1 HardExpert=0 Medium=0 Easy=1

## Within-contributor contrast (authors with both HardExpert and Easy tasks)
- Abdus Samad Ali HardExpert: 5b2b0901 f21.77 t36.56 hidW0.43 hidPass0.0 shpPass0.642 induce1 figs0.814; 6d12f970 f33.9 t3.09 hidW0.825 hidPass0.013 shpPass0.118 induce1 figs0.0
- Abdus Samad Ali Easy: 0b27b9dc f61.39 t96.47 hidW0.0 hidPassNone shpPass0.965 induce0 figs0.035; 11564348 f68.55 t91.35 hidW0.49 hidPass0.824 shpPass1.0 induce0 figs0.0; f357cd96 f64.77 t70.71 hidW0.596 hidPass0.661 shpPass0.775 induce1 figs0.0
- Harshank Kanungo HardExpert: d22ff871 f32.36 t25.93 hidW0.198 hidPass0.188 shpPass0.277 induce0 figs0.0; d49e259f f20.28 t6.38 hidW0.936 hidPass0.0 shpPass1.0 induce1 figs0.241
- Harshank Kanungo Easy: 9bbcb50f f67.69 t58.46 hidW0.277 hidPass0.444 shpPass0.638 induce0 figs0.0; a5b17048 f67.41 t42.5 hidW0.188 hidPass0.333 shpPass0.446 induce0 figs0.077; ae640566 f59.59 t34.97 hidW0.252 hidPass0.306 shpPass0.364 induce0 figs0.0; be15694a f67.15 t45.0 hidW0.475 hidPass0.0 shpPass0.857 induce0 figs0.0; c55a1967 f65.06 t70.13 hidW0.0 hidPassNone shpPass0.701 induce0 figs0.0
- Anjali Kumari HardExpert: aa314fee f17.64 t3.03 hidW0.227 hidPass0.0 shpPass0.039 induce1 figs0.645; df8f123b f25.3 t11.84 hidW0.0 hidPassNone shpPass0.118 induce1 figs0.062
- Anjali Kumari Easy: 92dd0b24 f70.34 t84.72 hidW0.0 hidPassNone shpPass0.847 induce1 figs0.476
- Ayush Sah HardExpert: 42e79476 f14.7 t35.64 hidW0.99 hidPass0.36 shpPass0.0 induce0 figs0.5; b5c7b14c f31.61 t54.64 hidW0.464 hidPass0.278 shpPass0.779 induce0 figs0.0
- Ayush Sah Easy: b47fd5f7 f59.91 t94.83 hidW0.103 hidPass1.0 shpPass0.942 induce0 figs0.0
- Sanvi Gupta HardExpert: 8defd7be f9.06 t2.41 hidW0.663 hidPass0.0 shpPass0.071 induce1 figs0.586
- Sanvi Gupta Easy: 4da82574 f64.6 t32.43 hidW0.27 hidPass0.0 shpPass0.444 induce0 figs0.0; 7e0d8feb f63.56 t94.12 hidW0.235 hidPass1.0 shpPass0.923 induce0 figs0.049; 82423338 f63.11 t85.19 hidW0.012 hidPass1.0 shpPass0.85 induce0 figs0.0; b5ab455b f64.02 t89.25 hidW0.0 hidPassNone shpPass0.892 induce0 figs0.0
- Aditya Patel HardExpert: 725e575c f35.77 t96.55 hidW0.207 hidPass1.0 shpPass0.957 induce0 figs0.0
- Aditya Patel Easy: 56fe3bdd f61.62 t64.9 hidW0.265 hidPass0.625 shpPass0.658 induce0 figs0.0; 8764bfdd f67.39 t51.46 hidW0.388 hidPass0.812 shpPass0.325 induce0 figs0.0; b6237098 f51.14 t25.0 hidW0.0 hidPassNone shpPass0.25 induce1 figs0.0; cf9b2067 f65.59 t84.52 hidW0.179 hidPass1.0 shpPass0.812 induce0 figs0.0; daaca581 f50.23 t17.12 hidW0.068 hidPass0.0 shpPass0.184 induce0 figs0.0; dad47963 f65.56 t78.49 hidW0.301 hidPass0.286 shpPass1.0 induce1 figs0.0
- Bhavik Jain HardExpert: 80202e15 f34.52 t2.38 hidW0.8 hidPass0.018 shpPass0.048 induce0 figs0.0; 9f5486ac f19.76 t2.68 hidW0.691 hidPass0.029 shpPass0.022 induce0 figs0.0
- Bhavik Jain Easy: 9125255a f57.48 t32.61 hidW0.174 hidPass0.188 shpPass0.355 induce0 figs0.0

## 13 models + judge sensitivity (final points per 1 judge weight = 50/P)
- 8defd7be f9.06 tests2.41 rub15.71 lossT48.8 lossJ42.1 P70.0 pts/w 0.71 negApplied0 hidW0.663 hidMeanW5.0 shpMeanW1.0 shpPass0.071 induce1 used0.63
- 42e79476 f14.7 tests35.64 rub-6.25 lossT32.2 lossJ53.1 P16.0 pts/w 3.12 negApplied5.0 hidW0.99 hidMeanW3.57 shpMeanW1.0 shpPass0.0 induce0 used0.18
- 59417607 f15.68 tests7.22 rub24.14 lossT46.4 lossJ37.9 P58.0 pts/w 0.86 negApplied0 hidW0.928 hidMeanW5.0 shpMeanW1.0 shpPass1.0 induce1 used0.2
- aa314fee f17.64 tests3.03 rub32.26 lossT48.5 lossJ33.9 P62.0 pts/w 0.81 negApplied0 hidW0.227 hidMeanW5.0 shpMeanW3.4 shpPass0.039 induce1 used0.16
- 9f5486ac f19.76 tests2.68 rub36.84 lossT48.7 lossJ31.6 P19.0 pts/w 2.63 negApplied3.0 hidW0.691 hidMeanW4.9 shpMeanW4.6 shpPass0.022 induce0 used0.33
- d49e259f f20.28 tests6.38 rub34.18 lossT46.8 lossJ32.9 P79.0 pts/w 0.63 negApplied0 hidW0.936 hidMeanW3.14 shpMeanW1.5 shpPass1.0 induce1 used0.72
- 5b2b0901 f21.77 tests36.56 rub6.98 lossT31.7 lossJ46.5 P43.0 pts/w 1.16 negApplied0 hidW0.43 hidMeanW5.0 shpMeanW2.3 shpPass0.642 induce1 used0.56
- df8f123b f25.3 tests11.84 rub38.75 lossT44.1 lossJ30.6 P80.0 pts/w 0.62 negApplied3.0 hidW0.0 hidMeanW0 shpMeanW3.45 shpPass0.118 induce1 used0.2
- b5c7b14c f31.61 tests54.64 rub8.57 lossT22.7 lossJ45.7 P35.0 pts/w 1.43 negApplied0 hidW0.464 hidMeanW5.0 shpMeanW3.06 shpPass0.779 induce0 used0.04
- d22ff871 f32.36 tests25.93 rub38.78 lossT37.0 lossJ30.6 P49.0 pts/w 1.02 negApplied0 hidW0.198 hidMeanW4.0 shpMeanW3.1 shpPass0.277 induce0 used0.06
- 6d12f970 f33.9 tests3.09 rub64.71 lossT48.5 lossJ17.6 P34.0 pts/w 1.47 negApplied0 hidW0.825 hidMeanW4.44 shpMeanW1.89 shpPass0.118 induce1 usedNone
- 80202e15 f34.52 tests2.38 rub66.67 lossT48.8 lossJ16.7 P18.0 pts/w 2.78 negApplied3.0 hidW0.8 hidMeanW4.94 shpMeanW4.2 shpPass0.048 induce0 used0.26
- 725e575c f35.77 tests96.55 rub-25.0 lossT1.7 lossJ62.5 P12.0 pts/w 4.17 negApplied3.0 hidW0.207 hidMeanW5.0 shpMeanW4.6 shpPass0.957 induce0 usedNone
- 18b5d99f f36.81 tests7.77 rub65.85 lossT46.1 lossJ17.1 P41.0 pts/w 1.22 negApplied14.0 hidW0.922 hidMeanW5.0 shpMeanW1.0 shpPass1.0 induce1 used0.27

## Split tests (final medians, across 90)
- induction in TRUTH (withheld/undocumented): yes n=31 median_final=48.4 HE=8 | no n=59 median_final=59.9 HE=6
- hidden weight share >=0.5: yes n=14 median_final=35.7 HE=8 | no n=76 median_final=56.5 HE=6
- hidden mean weight exceeds shipped by >=1.5: yes n=33 median_final=48.3 HE=9 | no n=57 median_final=57.5 HE=5
- judge exact-figure share >=0.25: yes n=18 median_final=40.4 HE=6 | no n=72 median_final=57.1 HE=8
- judge P<=20: yes n=16 median_final=53.9 HE=4 | no n=74 median_final=52.7 HE=10
- induction AND hidden share>=0.5: yes n=9 median_final=36.8 HE=5 | no n=81 median_final=54.0 HE=9