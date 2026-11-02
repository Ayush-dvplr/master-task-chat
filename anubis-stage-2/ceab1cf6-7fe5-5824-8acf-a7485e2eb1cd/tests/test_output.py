"""Deterministic checks for the budget-envelope allocation ledger repair.

Two kinds of evidence are graded. The artifacts under /app/out are compared with
values worked out independently from the shipped corpus. The repaired tool that
the agent packs into /app/out/tool.zip is also run, unprivileged, against three
held-back corpora that share the shipped file layout but carry their own
base_config and list their decoy rows ahead of the canonical ones, so only a tool
that genuinely derives from the corpus it reads can match them.

Every check returns a bool and never raises: missing or malformed agent output
makes the check return False.
"""

from __future__ import annotations

import ast
import base64
import configparser
import csv
import hashlib
import io
import json
import lzma
import os
import pwd
import re
import shutil
import signal
import subprocess
import sys
import tarfile
import tempfile
import tomllib
import xml.etree.ElementTree as ET
import zipfile
import zlib
from pathlib import Path

import yaml
from rewardkit import criteria, criterion

ARTIFACTS = ['config.json',
 'report.json',
 'tool.zip',
 'profile_dev.json',
 'profile_prod.json',
 'validation_report.json',
 'summary.json',
 'ladder_solution.yaml',
 'bitrate_ladder.csv',
 'gop_plan.ini',
 'vbv_plan.properties',
 'qp_curve.psv',
 'color_config.env',
 'framerate_plan.kv',
 'tiling_plan.toml',
 'selection_trace.kv',
 'rounding_audit.yaml',
 'profile_delta_report.json',
 'convergence_report.txt',
 'reproducibility_manifest.json',
 'derivation_provenance.xml',
 'input_manifest.ndjson',
 'ladder_ordering.tsv']
SPINE_KEYS = sorted(['avg_bitrate_kbps',
 'bframes',
 'checksum',
 'codec',
 'color_matrix',
 'color_primaries',
 'color_transfer',
 'container',
 'film_grain',
 'fps_den',
 'fps_num',
 'gop_size_frames',
 'height',
 'lookahead_frames',
 'luma_pixels',
 'max_bitrate_kbps',
 'min_keyint_frames',
 'mode',
 'pass_count',
 'pixel_format',
 'profile',
 'qp',
 'temporal_layers',
 'threads',
 'tile_columns',
 'tile_rows',
 'tiles',
 'trailer',
 'vbv_buffer_kbits',
 'vmaf_target',
 'width'])
BASE = {"max_records": 460, "retry_limit": 6, "timeout_ms": 3284}
TRAILER = "harbor:cli-config:TASK:00000000013500bb"
TARGET_TIER = 0
FORBIDDEN_KEYS = ("timestamp", "generated_at", "uuid", "random_seed", "ladder")
MAX_ARTIFACT_BYTES = 1048576
RUN_TIMEOUT_SEC = 60

# Independently derived answers for the shipped corpus.
EXPECTED_MAIN = {'avg_bitrate_kbps': 2350,
 'bframes': 2,
 'checksum': 'blake2-32',
 'codec': 'ledger-core',
 'color_matrix': 'fifo',
 'color_primaries': 'cash',
 'color_transfer': 'weekly',
 'container': 'envelope-pack',
 'film_grain': 6,
 'fps_den': 1001,
 'fps_num': 7000,
 'gop_size_frames': 42,
 'height': 360,
 'lookahead_frames': 14,
 'luma_pixels': 230400,
 'max_bitrate_kbps': 3231,
 'min_keyint_frames': 35,
 'mode': 'strict-envelope',
 'pass_count': 2,
 'pixel_format': 'cents-int64',
 'profile': 'TASK',
 'qp': 56,
 'temporal_layers': 2,
 'threads': 4,
 'tile_columns': 2,
 'tile_rows': 1,
 'tiles': 2,
 'trailer': 'harbor:cli-config:TASK:00000000013500bb',
 'vbv_buffer_kbits': 13842,
 'vmaf_target': 90,
 'width': 640}
EXPECTED_PROFILES = {'dev': {'profile': 'TASK-dev',
         'avg_bitrate_kbps': 1425,
         'max_bitrate_kbps': 1959,
         'vbv_buffer_kbits': 8392,
         'gop_size_frames': 49,
         'qp': 58,
         'trailer': 'harbor:cli-config:TASK:00000000013500bb:dev'},
 'prod': {'profile': 'TASK-prod',
          'avg_bitrate_kbps': 2725,
          'max_bitrate_kbps': 3747,
          'vbv_buffer_kbits': 19799,
          'gop_size_frames': 42,
          'qp': 55,
          'trailer': 'harbor:cli-config:TASK:00000000013500bb:prod'}}
EXPECTED_AUDIT = {'granularity_kbps': 25,
 'maxrate_ratio_permille': 1375,
 'eff_permille': 6000,
 'band_offset': 7,
 'keyint_seconds': 6,
 'min_keyint_seconds': 5,
 'vbv_seconds_milli': 4284,
 'staircase': [[0, 0],
               [600, 4],
               [1400, 7],
               [3000, 11],
               [6500, 15],
               [13000, 19],
               [26000, 23],
               [52000, 27]]}

# Held-back corpora: shipped layout, own base_config, decoy rows listed first.
HELD = {'c1': {'base': {'max_records': 299,
                 'retry_limit': 35,
                 'timeout_ms': 1250,
                 'trailer': 'harbor:cli-config:TASK:000000000a1c2e07'},
        'config': {'avg_bitrate_kbps': 12150,
                   'bframes': 4,
                   'checksum': 'blake2-32',
                   'codec': 'ledger-core',
                   'color_matrix': 'lifo',
                   'color_primaries': 'escrow',
                   'color_transfer': 'monthly',
                   'container': 'envelope-pack',
                   'film_grain': 10,
                   'fps_den': 1001,
                   'fps_num': 14000,
                   'gop_size_frames': 490,
                   'height': 720,
                   'lookahead_frames': 28,
                   'luma_pixels': 921600,
                   'max_bitrate_kbps': 16706,
                   'min_keyint_frames': 476,
                   'mode': 'strict-envelope',
                   'pass_count': 2,
                   'pixel_format': 'cents-int64',
                   'profile': 'TASK',
                   'qp': 48,
                   'temporal_layers': 3,
                   'threads': 8,
                   'tile_columns': 3,
                   'tile_rows': 2,
                   'tiles': 6,
                   'trailer': 'harbor:cli-config:TASK:000000000a1c2e07',
                   'vbv_buffer_kbits': 37588,
                   'vmaf_target': 93,
                   'width': 1280},
        'profiles': {'dev': {'profile': 'TASK-dev',
                             'avg_bitrate_kbps': 7275,
                             'max_bitrate_kbps': 10003,
                             'vbv_buffer_kbits': 22507,
                             'gop_size_frames': 503,
                             'qp': 50,
                             'trailer': 'harbor:cli-config:TASK:000000000a1c2e07:dev'},
                     'prod': {'profile': 'TASK-prod',
                              'avg_bitrate_kbps': 13975,
                              'max_bitrate_kbps': 19216,
                              'vbv_buffer_kbits': 62452,
                              'gop_size_frames': 490,
                              'qp': 43,
                              'trailer': 'harbor:cli-config:TASK:000000000a1c2e07:prod'}}},
 'c2': {'base': {'max_records': 234,
                 'retry_limit': 2,
                 'timeout_ms': 1000,
                 'trailer': 'harbor:cli-config:TASK:00000000005d3b91'},
        'config': {'avg_bitrate_kbps': 32500,
                   'bframes': 4,
                   'checksum': 'blake2-32',
                   'codec': 'ledger-core',
                   'color_matrix': 'avco',
                   'color_primaries': 'hybrid',
                   'color_transfer': 'weekly',
                   'container': 'envelope-pack',
                   'film_grain': 18,
                   'fps_den': 1001,
                   'fps_num': 5000,
                   'gop_size_frames': 10,
                   'height': 900,
                   'lookahead_frames': 10,
                   'luma_pixels': 1571400,
                   'max_bitrate_kbps': 44688,
                   'min_keyint_frames': 5,
                   'mode': 'strict-envelope',
                   'pass_count': 2,
                   'pixel_format': 'cents-int64',
                   'profile': 'TASK',
                   'qp': 40,
                   'temporal_layers': 3,
                   'threads': 8,
                   'tile_columns': 4,
                   'tile_rows': 2,
                   'tiles': 8,
                   'trailer': 'harbor:cli-config:TASK:00000000005d3b91',
                   'vbv_buffer_kbits': 89376,
                   'vmaf_target': 95,
                   'width': 1746},
        'profiles': {'dev': {'profile': 'TASK-dev',
                             'avg_bitrate_kbps': 19500,
                             'max_bitrate_kbps': 26812,
                             'vbv_buffer_kbits': 53624,
                             'gop_size_frames': 15,
                             'qp': 46,
                             'trailer': 'harbor:cli-config:TASK:00000000005d3b91:dev'},
                     'prod': {'profile': 'TASK-prod',
                              'avg_bitrate_kbps': 37375,
                              'max_bitrate_kbps': 51391,
                              'vbv_buffer_kbits': 154173,
                              'gop_size_frames': 10,
                              'qp': 39,
                               'trailer': 'harbor:cli-config:TASK:00000000005d3b91:prod'}}},
 'c3': {'base': {'max_records': 45,
                 'retry_limit': 37,
                 'timeout_ms': 1500,
                 'trailer': 'harbor:cli-config:TASK:00000000000c3b03'},
        'config': {'avg_bitrate_kbps': 19100,
                   'bframes': 6,
                   'checksum': 'blake2-32',
                   'codec': 'ledger-core',
                   'color_matrix': 'fifo',
                   'color_primaries': 'cash',
                   'color_transfer': 'quarterly',
                   'container': 'envelope-pack',
                   'film_grain': 14,
                   'fps_den': 1001,
                   'fps_num': 14000,
                   'gop_size_frames': 517,
                   'height': 900,
                   'lookahead_frames': 28,
                   'luma_pixels': 1440000,
                   'max_bitrate_kbps': 26262,
                   'min_keyint_frames': 503,
                   'mode': 'strict-envelope',
                   'pass_count': 2,
                   'pixel_format': 'cents-int64',
                   'profile': 'TASK',
                   'qp': 44,
                   'temporal_layers': 3,
                   'threads': 8,
                   'tile_columns': 4,
                   'tile_rows': 2,
                   'tiles': 8,
                   'trailer': 'harbor:cli-config:TASK:00000000000c3b03',
                   'vbv_buffer_kbits': 65655,
                   'vmaf_target': 95,
                   'width': 1600},
        'profiles': {'dev': {'profile': 'TASK-dev',
                             'avg_bitrate_kbps': 11450,
                             'max_bitrate_kbps': 15744,
                             'vbv_buffer_kbits': 39360,
                             'gop_size_frames': 531,
                             'qp': 50,
                             'trailer': 'harbor:cli-config:TASK:00000000000c3b03:dev'},
                     'prod': {'profile': 'TASK-prod',
                              'avg_bitrate_kbps': 21950,
                              'max_bitrate_kbps': 30181,
                              'vbv_buffer_kbits': 105634,
                              'gop_size_frames': 517,
                              'qp': 43,
                              'trailer': 'harbor:cli-config:TASK:00000000000c3b03:prod'}}}}

# Every file shipped in /app/data with its size in bytes.
INVENTORY = {'aspect_table.csv': 5840,
 'avg_formula.edn2': 9007,
 'batch_frames.scsv': 5342,
 'bpp.env': 4291,
 'clamp_rule.xml2': 13865,
 'color_matrix.html': 11181,
 'color_primaries.rst': 6952,
 'color_transfer.sexp': 11424,
 'config_schema.json': 780,
 'container.pipe': 8894,
 'crosscheck_ledger.tsv4': 4827,
 'defaults.json': 301,
 'dev_avg_scale.properties2': 10983,
 'dev_gop_delta.tilde2': 8894,
 'dev_qp_delta.kv2': 8765,
 'dev_vbv_delta.hex2': 9320,
 'dither_scale.caret': 5351,
 'eff_permille.conf': 12305,
 'env_overrides.json': 310,
 'fidelity_target.tilde': 5359,
 'field_registry.ndjson3': 14330,
 'fps_den.jsonl': 10888,
 'fps_num.ndjson': 11500,
 'gop_formula.scsv2': 7245,
 'gop_keyint_map.jsonl2': 10594,
 'granularity.kv': 9633,
 'kernel_selector.xml': 14499,
 'lookahead_seconds.conf2': 5987,
 'luma_formula.rst2': 8086,
 'max_formula.pipe2': 6823,
 'max_kbps.properties': 5280,
 'maxrate_ratio.toml': 3094,
 'min_kbps.ini': 6043,
 'mode.hex': 9520,
 'output_contract.md': 7440,
 'pass_count.env2': 4936,
 'pixel_format.b64': 8597,
 'precision_ladder.tsv': 8895,
 'prod_avg_scale.ini2': 10941,
 'prod_gop_delta.fixed2': 7974,
 'prod_qp_delta.caret2': 7312,
 'prod_vbv_delta.sexp2': 9520,
 'profile_id_map.kv3': 6179,
 'qp_base.txt': 6169,
 'qp_floor_ceil.edn': 10095,
 'qp_from_avg.b64_2': 9453,
 'qp_stair.psv': 3375,
 'rounding_policy.rst3': 8842,
 'sample_config_dev.json': 70,
 'sample_config_prod.json': 71,
 'selection_rule.txt2': 12181,
 'shard_cols.tsv2': 3409,
 'shard_rows.csv2': 3406,
 'temporal_layers.tsv3': 3170,
 'threads.fixed': 4908,
 'tier_codename.csv3': 5629,
 'tool.zip': 7876,
 'trailer_suffix.txt3': 7227,
 'validation_rules.json': 792,
 'vbv_formula.psv2': 5370,
 'vbv_window_map.ndjson2': 13212,
 'width_even.html2': 10537}

# The shipped text corpus (every /app/data file except tool.zip) as an
# xz-compressed tar, base85 encoded. It is only ever unpacked into a scratch
# directory and read as data; nothing in it is executed.
CORPUS_B85 = (
    "{Wp48S^xk9=GL@E0stWa8~^|S5YJf5=coT<dR+i8oXSLaHGvoVRz3yDd40(8|8VCIGTG=hGxKCEISlrq31F$=&Sx_%+Tuaw6y0"
    "WBO6r~OmMqR$WFRZQ)!p{?FBLb;>n$bmr8Fnm@COhv3hB9B12gr@TIQmR#>^alkXhJbXo3{vPwd)CMV4#x@k<B;wAHU){VDau;"
    "@4dKiW0_&pYMWhEtgyH8$BIqaQO~EFfUnz26LogsyVzMz%o6+f}{W9An{IWsJsNBDPpEex_$bn`weu}@fLk_gMsT|QkeL2>N*~"
    "mb+U?z)i2myU_T-3x5_(TvBs-diI0Mrpt~leyvT!TIW_J3d1I~0O>=Cvznl1tHRvX;ckNrh`moHx{78J#h)?3HM}@3D*QNz---"
    "ci2kE!Ce43bI`s+3=0_ciI_Jl-W4p_4W>Xt3_knUe3^r$_LVi@XJaQy8F%V7oO4S#J4sBV#H5%~)O<U?ecFdV4yRVQr|E4!~H2"
    "Ct{H;wd_o-?CKP-JNr`2?)M`Uy<?>D%MmCc{{=IOFDppBIhIT<y=gJ;(|xTU9;-X8@LNk8x4~{`JvwT)b)Z-fE$J4hXqRi_4bS"
    "AM;%nx(R;eKQ(Fj!H36Oqt-D+t7&DJ|zsfvex<_%HL(;j^Ep5~U}=ctsp|E`5KDek8h?ru_6Ilo*AT1@%FyPVXd{C5PDtIgFVv"
    "ksSU1&PrcjxDtnfN70ZklobKf|<Bg(s^9z%>q~NiyHid(iIG}2xWkf!pL0*0h#WEj+HNaRY^ALFch?!QobP5NKnt8^S71{<z_!"
    "xrn&@B^C9Hv&#m!09)y90b}6o{G#yMpBkJ1~=*%8=$4y|25}re|-qV=H%*|N_X0ij}vEYsoo5TnwfwZF3%{=miPh_N$hdgFZ?B"
    "tBre<(jcGG5iWy+do1cYo>)8nc4rFjzI2p_@QxV7KTmP4AgwBPd_0$D3nvLv{38j{Q+~@pDrjvr=o|<2P$q<3`n;dlQKBD<>_%"
    "@-fu8)5->C;ZZ~@A~V0cMcacC;V<}a5Zr<#sp2Z+&QO2PN?G>e(GdL<97G0{MZjed>R^l(nyGR^W0)zG?|=`_m?mpFAljdTZng"
    "R5W1eMdkanGpW5YGVpv)Bii?6H(1*JZWeTXe?Z3K9~{|Mg{zGH)?ZSTa=$JnL@o>wIUWP@ikd|jz3vU4;yLn$2vut+<T_4(Xty"
    "<((T?`WqjD~JL5a>$#NTJG*sc2Lz_wqQ6_b{-sykcUWPJ>pwIhy~vTUo_ci%6zCk%kJpB=Z*V1^yKp%zDlue!P<A^MOq>Efnse"
    "nF~rDEv+lxSK<MLH{;3!8Uq$nanPaN5RST4uz8OWY?nf*>xTjc+RN?0mEmf)7wf$RpmP2!49c?DTGrH1n*$J+M%yM8-wqbr^f9"
    "BEx5@&~RBzmR&r4t>)hD$ImfQ*R~4rq^$kti_{xs=B8xF?K%CTVM5p@8&v9&V6{48cVHjYMG!#q&PKX`$#*#hm{sI|pK>z0D?Q"
    "nCaz}n7Kl-2+vZDNheQ8l>YUahC^!81)8=U5ho5W40@Ss>{DU|Y>J%$KC}Wked<vaG?~}k8j87>pQa1;z_pcZ<JX6Fd0<HcG+V"
    "@1d4RJ>=8zpr=~+yiZ(+#>)p5fwE_zTHXOeqf3W=LOboNbhb;tC#*tE9HDc!nXby%f9db~`)BR;V0N|bRcCrfL77q5`Z;yf?*H"
    "rRSzLmhEY-03H0L%uWt(YQ>@&62RE5m{l`IQ7H46DPpNAv^_m?=Jk--l`so58l9(Pzd&b>tY@VNEZ`Dtx4z#gQcItjt4GO-1Dd"
    "aX&}+b&+Sf#-m@hW!8#l^E`Wzz9;uM~L>cylf?0v)?I$JtIUm~6{`A`A+cy1D;vJs`yA`r%R7gYyBDB0U{kU_u_5x+%;1&drk@"
    "@@;GGC9>GP&>|kde6FV7{v&fCX5U(_&9<ZI>hI`8Mdjq&Au%2fPoAb4_dD#_x-+C&oB$TlH9M*}~2inI@?Y+9)vIbZj3taP|L$"
    "#6j6Uc7a5iA>WKguP@95uU^fkMc6Xd>+j5A%6j}&5TN+!jeyjL?jJ`c#{XwOTs~y7wOqLZ?{JI*)tadUU`AbSUJ}MY%%_l;!s?"
    "g-2JPHAs?&aGVaG=~MgckDq;1VJB;W)%H86A)m6uMUG~><TI4t1_mRAtAV9Ws<b=YSU`hn~5?}0@65Y8&p7Z%%Rh53n;7gTyU9"
    "Eu_(z~3DT@XTwlTVQp^RGh>P8aGAmVwuOJU2~kOTq9?-s|jsTIX*Kw+7WIBSBqGdXDW<O`-3>SeTZR62H?|wlI9=WTrsfEZtd-"
    ")Fdt86VONH@kyBCd34AMJU05&1F0sP>7sF#S#GBn1+Qv>JA97n-E3A+|+I<lIw?3gEr`vCXyDqnfIqV!*182fXSY9;&kh|dnvm"
    "E?Us<LRPOOSnm7nnLg@`NH^q5i&NwM|=Q61a8|IKh}GF4g0!LSdA_<7mm(Umxd_sVDCDXgpT+0V_~a9;82B?lPxK#e-H*f+d`o"
    "jqm<(;I+S?R#Mv3u3_)V8*d_)c?QFn7=9+AQ?jZPr!=Su3Q-5?)3cWE-q9M@vy;lemztqHD8LI@0gW+S3blyeI||v{6VY8m>-4"
    "JLiq5(Vm#+M*0S4B-lTEF!)<!=d+WSt8hY%tW+!NvlI%{9b<#%4#_+c_aVRaY;K6132Ka*J^|A!!j-Ep*OX+xnFIi44(2&;8<D"
    "{|j%_GyXjzVnEIp>c6DPTkvmW1;D4*BEa7IkTlLp1E)|XP1#q+AH$HxKn8>@VS9j?ud3Etj8XOUupWVRMoBmcv1l~44%mToQXm"
    "ySb&9NUjqztzTS7Wa)P?Bc?)W`5);VT6{fYivBi_tA7S;h)~+{Nr?(nbPbKYL_TM*BJ+ug97q1UBCAugte}bnS8ou*bRQIiMj7"
    "LsErs+uDU&x#L#19YbG2()L*b^#DuR4i5Pi?G_VhwIM6>wg`ZhG@%yOC9>Ow{{NlmbDVe0jC78}JT#e!O;BqVGoS!j6y@MtozY"
    ")pCPli_*uG|BYat9Y{QbIZg-hriy@uzn^05?QOpCgSforrY$+6(?g#v+gO@Lu9LRppe;iGBXFrZ!E1?G#HMk!J_V4lN0#FY-K8"
    "q3Oc&1=-%n(0Y`UC?uK6)0k?bE961tFv+8TaPtRiA{lK-2&TXN<FyIJ`;pX**84Xx~S`RL*H=jHT+&M7qZn82Tzbr0(Wb$8u)O"
    "~wZ=7a~IF40rU_hWp0bf`k59QZ;&<S&aO%QQe(2S0<j&JmH8-#$!o6khPaK`m#6*L$3rVwx>O9Lpmz2Dx=k>n7@bQrrGCT!rL-"
    "LzG~|63Q@%WMtQsRvI9EyB)_@j$C0+B>LdtwHX&u&G=s)@Z1mSm<QaGOPf%wJ1eZbiY{{dnVkx*qsljoooS?vx%CbmVp@cqw4m"
    "@p05bG5q_Pi*dv$8ecAN-1Q-^%RSr~m2Q&cJ#N-`0n@W+Ye4*mA49lqW3YS}jBjjoi(!Hx1vjU*NgUX0n!lpaxs@zn`SCZxY@b"
    "XfuFDsWFl)5cmLbyhUGNlA|Q{(}qsdZ+^l5k&C1}Ggz0wfnFeS<*t;xXSb3f%*Q_ulqSDFEgL>1^xFzR<;hMG#mJ51sN%>xQz+"
    "kzt<3zx;%oY!iQjl)yrpE2&dbFOw@&33BGJ4I+%2sw2Bf(s@uDgPB6h#|M<oV;8b%+>pla32zp0~PDJw-W>o0{(ns=wZD4BhCs"
    "E<AG?fz!E{`d4rv}(b1y<*%ic+={MxHJdga$UCfZnMw$n5Li103ifi$}enz2K|-h!o1FStXdlihWht+Dmc5S7*o2t0L_*U7<+T"
    "e#jBX=x4lit*a&AB;blUERbIGaumP-6QTFfb@MKCWbX!?w{`Oo|mm6<;NQS9!*%Eh+Vl^v=OC@X-j5fuW&%H>Lyyy}zf(u9i)P"
    "4e^^_Bs8d6*}HpL7{r$@nUjdx-@F24+P#z>2C;c-kz)RaccOIA~{_%f8Jb61K;;AfWB{areFKdc@;swl_@hnMXjWsP^&~r}@|J"
    "Z%K?4QvVvBOa?AyA`eT6yyZ=!-C6%aWC3O@X><Kq(AjPZ0B%_G>FoC6N)PAAnupPM2~Yd&@V<=G`7YFJc$q<Kl$)yicaKPQmxJ"
    "}NyHi<EXrY7Ybvf6)><SMykaA{A)1gh+>LV(`?J3%r;v8EB`(1H9^c>yh6wMbM`?efW!|*iflqrDIk)0K?i_ABBM#NHCyr_2XQ"
    "?MkX59Aad`h$lJywq=9h9G)at0i;;B%B!Ry4PNAxwUrxT=GmhgU%^A53vQ=w2W7MXPE<|A7W!n{ig>Hsw+H;sGV<(Z;CyINOjV"
    "p+m0vP;vf}C_!aV7PqHiVig=7eWO<sgb>{B)B$nrO(jKAc{!iXndSO`4dkLzH`d=-FN&6P*!OlKYZ(tG3Q@j;q|9K2BV<i^VJG"
    "Ok%U5pb@axdpBzhmEK;qa!pL0uLVe~URO@pv4wY-cmvihZ=C3OKz$%)huiWMNO0rD-*Q(dZW7Z^QwO3(})w!Z(|BkH_XZI;p*Q"
    "TQgV->BpDit`uWdE0tuZzbUIZ_}$N{*K^nDOhqk;!cOsv?0$9LK21IFU-s+;|02yzdwSZ+CS_TKT9Uns|DLZ_|L`C!G&14;V$1"
    "a_slI2x_u#7<n%@Jh&k``y;!1t#`4##tfdu=lHW5!fHePb9MHmGQQ|M4hJch1*>#{=2jqPw(kMgY}x<Def#~qvh1ZG<n@gKZd-"
    "KF>u$WTWL!YQiuoV|Nzn_+A^&{ek|bfOB79>8a3h)61_AeD(RiGLV@K+<KFosIR0(qRwD!I4Z6oa0afzeiSQXFEoZ4Z!zMn;c="
    ";cNjmBHn=(aIzhQLpUUFutoUCKIG>5Xq!FKH{b(0#v1rp`!R>P#nkBH%s`X`oi$F2Ge*Y-5gDV}j4{*)!2hhI1f!~`uh94v<I9"
    "OqBEKpO2)ZKOoZGuvzeO>5AS514f*pZ_BIWYDc?@$24eB%*sT&-@E)>|a_ikmh0de`;<K#V@8;NfR0)_H;2{Aar_YYMtFq}Cp@"
    "?ag+Qyr%T?46<{Rce%w93+6BiP@~1;*^F~Pne({L-*NBU#DwCaDy7)=ull_{L>P{|l*wy3IOMJPfeS?$+7W7Gv$87@&$!ABsJ?"
    "{+PiXpQY)P{qm=gg!yb=!4;{`#c&_XH~hEenn9aUxwi=5XRHBsU~Pf`{Y)EfZ#TJGwubCc!#*+G+k95e@XeY6l~SH^4Q@us=KJ"
    "Cjv^$qvLnYT9I_8Iz-W*qB~lJjpPQFh+K>H%i7U7mUE%uD^oQe?>fm#3@9Lz=2+bgW>miQbGqp|J+$=Ts!EA=GDr`u=|2D&mmB"
    "JHG4`S3MAgUT$z@=S}u)PyWe}@pSk|mY;^4`x-$@@&atcPMWd)PW<=*8^uf*>vgarr;wds7OX1AWAx@vKc@dE!OnLXDAO@1P^<"
    "J+Dm*9730Qfn-c~I1pu;g!+mSFwQJEIefoTI3X9VIwxR55cp-_;h_u48Wby$EJ*4mO|2nA)=1crR@$+0o7-O9H_;FD6U~xe4$I"
    "p=EY$rM@zi9hm-PU1OIpD|ifvrxIl)csJ{VUhs7^i|vH-Y#7E`?d=4NU&77+)ygfCguM`>_~VCZ^Dw~I_<)*Z*kV-LU&h@M-Ew"
    "Jydz8fC9kw%Feou4zjYwYhz)$9KDv~{cAoLFjDRAm_7})RDv-GHU$uC&=8`-`#B@F&?pTJB^tZ+ZCrX6z!(dm4IUa|`Go!L#L9"
    "o)iPX@j_UmEkbal%Bsl&FMG&9Q<!wwD}{Foeo-0s<5WbWiU6<Q(fVK38d+h_R-0A(I~t5L7gv80yRj`bH#-Cw&et^m0%3%71H&"
    "*CCX00$Y|MNTq(DKcIyQ>W<Qs`?(d+4#QgQzK&}+nLS^_XjwFu}Pv?PIzl&_}#)&#?cfXl~#l0&Gl5pL6^Zs~m^nxR+at%EsLl"
    "OtBQ9#Ko9xi=tRPf4eFK2)Tc-#ui-Es!hOmZOt&_D?@(Q$92bv>IJAM1RN$G^CRi3nwy39CcmGNB8y@cpehUt(0x!1S$ii7}Yo"
    "#$eO-hr-dGTQeEzj=~-#Wa!34GauUn1XU?;vO1cOsW`7Ie*((Wy52p@*k3f5WmBmwZpT%g2?Zuh>V_xtO??TpA}UkTL=Qi`yWZ"
    "0PFE@=ipGl_?td1+qVT9$2({D1WVnGI3;||JZaAhK6Xxay)c!Z4;jn>0un!Jt{k$XNWf_zM6<I_NX>=koK&Z6DRrh2Cl2+>}%H"
    "NJcRlHps9hFS*F()D27*%mL8!9x4?Vg&@3Dpfu~%^%+qY#2onax23&mDCQmVw9?b9iVP;5(>5xUPjBAr@eVEH|g5)eP2|&8V^n"
    "Ah;pO8E!SUN2{1)$l=)<@zKNhK8v4=xw?cUl?Iga^!b@Dv?CR82;V;aRtri!I{9(3{XN39~Q*^&pzLxT@ZLOzL7f9TaLBGyu8z"
    "HYox8rYw(G>cu&DO;l#=m$Ieif{8=k2`T1glMo#XGf@vd!<eu<HMH^2F=S4q70WZSnGiGF1=<S({gdUwNtud*iQ(eVLE6-fhis"
    "STjXJiR~&RI0?4rx~^09FXN;psH<mmQoa>`%acs+D=jSWzu<g+SaxGPh_q=nLEZW}RSTWR80>Zx#)YsmOR_J33J08|%tn9OHE#"
    "UZ?4NXthink6ryx_%gET1(op2@ANB!MvlE^_UJL1AUVJ~}GTTthmi!P%#M^*5rdiuS5REqtf>H~C9qlzY1yhQ0P6l;@LCyUX$;"
    "u}trUYIx;O~SOjdt620wNNLxHOdEHO)HtA3Wsx9zqP#5UzWI-wLe998tcRxg0q$eK;@$mlmwCK!2|QSbv{wWzb^CLbUTHW=dMR"
    "F2*c07V9rFja_X;~iSFNnPG%L{c9a{K`*<x!RUBCVN~sl4Hw++a4S@J7UmSoPg&)(KOAj?*%G1OhD9n7gKF)$_w}&J|mcBw@+1"
    "-Dy#tOgPtbTOHS5xa-c{)^T^9FX|7pR6ahA*rEk9G1cUX?21v}79Qy9CFgQt3Eu&yp{H3v|=ZQvC6X<S|vO=_D^qV#B}sN+NTm"
    "cZm?_UXYqU=&9MZYvpa>lmbp3SoKAlWI@#3#7HN9tjRFp(n@;vWHU@4h1LXvFe@2*b)h_+FC8X@G=+}t7o(hh5Z|^K6K;CRK-`"
    "A){4R6Ze}TeYa-bPFGB4u>0|5*EP?NH=_?Z5bIr{HFNfBlcrH5-~(APOls$`CD9BpQ7D?T5>uM+@UPl@+NGK}dV$IZ3z8vI(7Q"
    "FFhZA<OxBpdJ<JDZs}SJUdz(*|zzajBEnnZ^nU7586MxM97|AI;oijHp1o9XKF07E{5!uDt~`?&B&CZibtNRlEQcZeJ0G6R#-<"
    "-%3C51fc6e8=#nQ2<M7qjdYwkb98wujm#dWEFFV0P(glP2_ybi6Ju9CsY(9Z+NWL%490MV3SLwHf?~-Y&snDoz@)k;R1ROE!2p"
    "9?a`Kg1T{2HzFG<O|6|2{)<mOOUwlPqWjoosdnhkbhDn_^ZzXQ7jaL><OWH(c232>oN-XGgtQsBP}Bjaf4<<Da+-?E{j2d3X48"
    "?6VN@U)cDK8ANWnDq1RnkWht7(Yy8l>nj^e1B718`myi%DTBNVCqHdO(|SK-E6N0YJuRhji*xHIGbx;I3df88{LP;pbA^mdc^G"
    "i^mE<>h=``m*U&-*D{l$kqR$9Uc_W)=0u7}Xk)J5Nzt?1YW;iN~5Fp~?|<Ny&%F8yPZF>xo|Z*Vz)D|`Iw9K+T%#3O099DIn<3"
    "6_I*kHEQe=w~%szNm(i;Nv{@=YCYv)!ao)v_`9pEfxL-4i4lr!2b_~V^V2pV0y(3xy-w-?AsjHx;E7Ov%l<&Us^KUuE_vDGGv4"
    "BlEn1n|GOQN<a1ly%!V3#A@u->33t7dgSK=dyY6oXAF&OuCp|FbJdupL9Q;w<T^x|qsL1BOLZY-N#%I{=7NI}zn9C29Jy&QvFV"
    "d6xzEAiOUO{LMjIiJM)6vtdn@F%G7O@}UZm8%&_osvY`NQp_7^0o*w6>}tr|3T*;N<5ezL3K-eaf>`hpt0yb463;nH3I?V1!KM"
    "C9l|3{oF(klu)q$VFT@Ti&X)a9%^nso$)!^N6Sg?9BI8w4EsEF3_5xp>YNNIL$M^lhY0^s^1yklu_y5OlE<M$Y5MA^s9Y2E!x_"
    "XXRvhlD+6ICNNMm&C9H%aYm=nRptIQ|#;|x5FvnZE}g|txfb!L$q>k_ZWk&@x_3=bd`c=jwD_P`1x1Ib4c+l3+tE@!=OV1OiU;"
    "|~DkXY2Y3gzI)xh;HQ6bx~GkxuxX=lQ>W1L$F?EV<5_H+|q&kYz~M{amkQy9JxTKRYLCFW&XHln;^x(uU|J<p#>dPmIm4Wqp#-"
    "WAd=KD^eM&bcmNz2VfmpPtW~P#xC<oD<|;m#)68|B4?-oH4bW!7W*bLHMd+mR*JSD`QV*5eR10)}nYYqEsuYr5UaUbLzW=aLC|"
    "vH1Bivjn;A32;;Ggbg1IRP{+*d|4h<y#2hul+ExP58@2<k&~uny%Sr4L5M5HW+-O=F$*n=waod1S@3zEEpfuD~s^5>vi<>ES4o"
    "j|I1`TTo2RfLt-YcLs6akBK480m;Zu<V*)m<+cOw#4D*yrI+(8Xb`oo&7p(ZqN1nl;-@JX%Bw%o<_Df~aL<Gy#BsY8wFo(8@8B"
    "Hxd56j<D3tg8^3~lc3EI6(r7I4oCtXhoL{=Iiaw0B&P&hjwsfJ`1**~Ehj&V2M!{Isls5%>k`+ihHsau8A=27E17ZC>A#vT(pL"
    "$%EXa$b>L$41YpmtiY(Qv5s_!#wMUA7^A>CqA<gv$NalHc65Dc0lPYvwE0n%)fwiE24<vYpeX->bb2l6jZJaWQlyUt7R)fr~!{"
    "i<i85{^c<0yC2EHhC2Fj2*)boZf;es%I`ze%-kp3N(h_4j5+XUsCyq|;b2}zyGhWsn!a#S@6~Dt<@Cw$j`=!-j2pf&&klHP!oA"
    "XlRLWwTO-vJ_)s+ls<l~^tzP4wJ*WTx}7-N|Np)zg87+_j`xL1?2T=c%l;@?ogH)h=5uU(D21szgKN6F3Rg#qu21rezgyRVc>Z"
    "`lKfalWLm3d9W%JYepnZuixH!013iq$hTDMBj%6k&n=}ITrVq8PlJXz4%kI`Nef&ZHGj^ogdJz<f$;yqW3?mlb-1x$?|fbPJEL"
    "KuI@4=tZ^PXHkC-GI=Ou|6%H|PACmDe->S5Jz7#|iTt}jgtdN4TFbj1548i;zyjmxKhb`ZsPL6W?-%h{UNU6Z{GC0A^^ONS1Bg"
    "Z#~YL`wS?S=s!(-%m(o*1)z(q<4c~KLO`umTBovyGhAO86Cux@`gT;*(M98x-Q%KOppre!p?!v5q@<sGSa!S4fpEjxSn2xI|R_"
    "<qtR-n0iDg@qb0j;xR;H!@j`mq4Q6XGP#u=qwLEgvh$n$RX;NF%cG>p@wvOcu*)Ei9dRNFbBm%AQn&$v(O$+o;Ki+w!dGHtb-n"
    "tv?L%{e*IusP{PUQd|fbA~O)L}vP{=-%^z1CuMkI*PwDW&DTkX0!@OYG0G$*{>=91V;IjT`)Fk>k)FlRB0T`Thl6YbpLQV;F1o"
    "zU;z$WhT4<qa?AByA(B@N-nViTych<6In+&H#WyAF*6-y`wp#t(^aH}VvZPnu1UzWBp8BN_&P#6I*g1RC;cj8uv)4YD~hgqV_#"
    "3|)%3>C1Zab`SdZi9mk3NR^7$(-2eKymFMkN8-oCa`Dt*rT>aspDeoD*JYQ%9ny`(%Ze42Xp;cS!aO+xJfhO1H^#QEFUx41Kg+"
    "uN1^U<gU~XrgT`(P*9w+2x30GH4r^wQMkNM;MuK0~*6|7=h~Mrl+SH7@=HC({QmGcdFD<jLtUr&AWV;us5%dqGA!id0^+cN0_d"
    "yftpnR3$S$|Sn8!4_ueEIBq7kUx$X`Tpx6cNoa1<!YtCjLYq6N$>Po$qi(J!5`S%CQcr%~QtS^XTgv5VU$0X5?JtiR5b}zeRPL"
    "|%P(O+K6?)Y+ox{L6YetbfckmeLeZ1Y|nS1P;OeOUK;wY~@VEOOJ!Zr|F$YgC;uajryFX>hi$EmD0(UOpV|P0@}hO~{!$P36FJ"
    "p(WxUmmH4b6imtm*_TC@Vk*KkHBiw!<b4UEJgAVQ!5;Z*8`xXWz>mNxS~O0y7_qqrIFSu}#L_ODW|{s<P^c2sIbdD7zYpNMJQp"
    "{6PzdGh_YT2O#)klTj?fmi=n~Wa1zDQ$!mJ?E{S`EfV=ceK^U63R2-R_PhVz$w1n6oci4N~ni25!QQR(~<UUze13UL#~5J4~6z"
    ";OAdEeL$dz7#O}r(Xb4euxPyzmfjLndZNz?rB+EKvs3Ik8K2&dgt3MtNp<cY;?so<9{{?vEvRd3qux>p<1Y7C)jgcusS}WM|Zm"
    "FRiQ<f#>xf3&D0!m@6zU`x%WU|R~sq5<wP}Ie0ydlv8&#(1I#Df0m+W7S+%kD2<fAa2=1hZ<Gt2D1vr_TBb9KSw*U_%J$lvv7&"
    "5?v@d$Ddxi||nx#P=EaAvhMA5qIoPIgWF!$n;AGVas`VU|w!t+l+$cdM%JDDCw>bJ&s=+_0*U^^r#7P1wp)WH=Ct`3p|VP{R&4"
    "@jaH{vI&UOR`@J^Rwqc82FfgEmL!_JR9bo~6QOjpo0ESX6$qKv`K+mPUQkfB)G^^R{7Kp3vqtAC`*m;nIEh)4>at%j&flFBh)8"
    "i!7=#TLeHY;Op=nfK=6^O}cmF6&XVYbajfw>NsVbcLRIK`y_g~8S0$BAIG6$e^A9{d7449Y~R9h_mw@MC&$PCfAdru2a$4voce"
    "p?0xeSHJbG%=;FaJCh;7fJJE2|Iz2p!7vP_v4l^y|Bye7N52~PxP5lMiUcD0lGr3E~dOmQo5^rrsdsVQ`bkQ%gn3yj$*|r*JZW"
    "KD^3ZCjS3h+i}x<Yr5XCr)tro;k9Fmv(VII_)#Il0<AFN2`@*sA99@LpY<+%k5Woo!nPVw@4_=yUw3c<NN7Q4y;}7gc_7yUXl!"
    "Mdpxf|}7*D^Re+);X+L`BV?GWgcLj5@>RzI5F)7xUJ8A(Kj)XyH%RLQ;z$k%@c&<_4fNRxVl{H(dE*Y74#%{wr_Z?-Cc9Jyslr"
    "a6!FyS9Y|4>yE|#@XaomMqrPeK2MLtLZVzi`bxX>qRfNp45F5mRP{!QFzW}(hfs~#i-Na5cRhtQ{z5&#aO0TUy{4)~;Ufi4ANM"
    "&nBMIFI_{w6nwU_2j(zAYr$g*w-<R?wXkC8^39OP(pVcKrf%`-2o9S{8!6NAC!h~TlB)3`BRJ`p;=yK2GkC7ny>&l{CRmS)(J^"
    "XA{mh_oDd{aVz<k1P9%L@G)7_~;_^j!;bP31)RK<Uf`-t<XF9Y?f#Dfz>P5QA)pe6l3Q9QpqQVUB~4q{)rNRK2t6j0QMWe8WMz"
    "QfU?32hP~+#!!g&fG(Uz0K43M43O^U#c@2m5%_occ_%T0>(WE<x$sfi?`RLmm@ca!px6*sBAU={&=$IOtb%K}T_Wllkw{h_e>r"
    "U*1ip`zZp???GfJBY^@+FjBe0T;e{DP2GTBY8k^)nT`63+Fc#P+ZQqsOW#2Uqyf+66M7&zaye^G37Ff!`pSc1k0ZO4IISaB(DA"
    "?KlYv@6l|!4o10u^LIeX*)h#0A)o{|RU?LY{|qh8Tkiu-2~<(Z)@D$PHLd}=EpqgF`;W~-Dn`8RzaFW#T-be3YpjnZ#ZwAG?sO"
    "X;w>Q+nB|~?kf@NkJ_0XO}kLw2FZfe8IG8kL-IqdGxG~@N6P+9J$Q!!%Kxc4Wv#^F!20c|quh{*O6BjTXa3Zgdri>v3b^H8#V7"
    "ae-5D|2oQIQ8Cuo@|{dFFjIHcH01HKBKrlE3bBQg39=~?w=-75pRs%rep97I-Y~vQ(Gc)@qMIUp%LnNzj}8qn%jK)axp4NMJo#"
    "6T+Aq=OfwgI2xBMX?FYFcQl+YUW#p*BZ3XcmM9wM?h}&VwTR>w#UI-q1{!sm}J*P=M`2V&!YJvSeyzyAqPI`LtpL`puMCbV9IV"
    ";;U{qNu<eVv-V*I~#f+T|V^GpFT0MOs=+HaOoF<tKq3u)ngVW`>zs`E?JNxjX0hNjw7JWE@EI8}t~p{?&P}T|wd*VUC4Yi6|Md"
    "&iRDFoj)2`qvFrY-6MU3%hkdC{+QAv6pg8CSTFp`49tb#tpk4*9{}Y)+FS;*JIxY#f-#D5Q9c{dQyo3T7vF7w6FSOzm#7~CH8E"
    "W|yXVk^K|kFrESf@QFBCp0M6H-Z-Y?&A_>(0LX```icB!4m14o<aGvu9%Pr?&g|5MTE<`m*^`!e@WV3cJqLq@cRO+W<ZDTkan#"
    "K5=hNUMUeTJ{aJKu6%m{t|sf{etpTul_?8fjIH-?KD2vg0z<wrr7^r^@>WYhq0jGo~$P@qBiLp!gqY6pL@J;$Il8e%;>%WZW)+"
    "<^fMn=P8?<>7AOg5JAtW=W!E54eZ)_Y!@Doixh(t?eYuoALgX8ttLJDMHaP>FcUx80`llgho{rw+Xj>qIv=^KK_`kw;a~R?%A*"
    "=|JojA95q*2?7^Ph`K<VNIf`0BWfpAfa<lHX<-pR+b%E}fT}*&*Rw<JvKr7D*X!hs!IHUZJ<>{F=HxN|{Y325-qvEs&}``|#^c"
    "Kf1VLwwfDt60Uj<(bL#}9@?SewWRk9IT5iu;(DCzu>56EOnH0^r!ZwR&&lU+2TvUA{g3xJOHyiCp{nz>z|jIbpF<0sos$64EP&"
    "VMv4LSL5RLj&<jYOze`95azir;9=Yx7$)C~*_m(jrMv38~=o2MVXE`JqkobCfVjjA8;=X>U2?Tn+~{FT?Ud}}n{6J>@X)b>Vrb"
    "mHCl{Tou3Qr8hZ31|d8cg1AG)`c;i25+261I?{K$FWd={u!pCPg=Oz>A1x8>9AJJ(IS56nHxR#*UO`(((i%>h%1S|kwjcu4nkP"
    "NbPTQOwch_BJ3(^3ip0zeTe`nusF(oznRg_uSu)MgOOoI7GR`{OR!D|{dzJ224hLO?RiZe5%Gl+2i!BVvAFe3zI$iBi1-pa!Ng"
    "dR?{aBZ{J;374Tk~b(k2uB5v~+J3^l(ol9dJs?>w$FB867Jxfd%AyJwzgMIysv53E%|j@3GlnEx>lHSf+9EoZma`BlnZOQ16yV"
    "c9aZqLE_of7XFemp4NI|hFI<Z*K*|aDDL)(?pPE|G7^>B%X^A8n}BxZY<Z*x0_4SDE>MRl`mYIwMNL^gyJyRH`<0&P86)h~e!N"
    "c06xLBsgv!&1q87v1IjgH=1J2Cazu=_1QTtCXt0cowfMmZ*JeqFN7*zzV3|dv)P;`1{!AkQs_K$^(xjZrL=~^mDWmb_3okn2Vc"
    "wO;eutCN19WDU`H{6Q2j$D5D48lR=aGyExJ+tKX<5)J}B_;G$wm6E4&54rW{bR-U^(TKn*Nj(j?y<;jAZXpzp-3$|qqGP(rr=>"
    "$QZr7cMKNu5uVD-`c~x2UujsHmCZdE~bNNV&8hFhCy`EOUn&SsJ$8aph-e;;M#<x>5K7AcRm4x?tAI@v@lfWn1B}`fQUH!H1wZ"
    "y*O-n7&e@2Pjx$j6{fdYjn@SC4gPal0N&RBnfdXe7axPNR-fh~<=g*dCiK`Q~oLzriL-F-r{ze?~I(kR}oLb^^y(l}Xl%-k!|h"
    "H&V>s3;5#>E7DF_VSPzJ++n=DVo+7fh+b-c(XAq%=b)a|a~4*`BRvT_*%Yr?<)wh5HTieC0K~912aRLn1<2SqNZ8}ZuS|x#j>h"
    "&$5ryc>k<m%-dWGQkFD9VAt2VV9e$fq%3SQPEFn9q#33su5z6x=+VIf%D1;IoqT57to=%OqGlqZ|<x2-o}_9OicEexoO-ak-Lb"
    "*V-x3}~Xn6*PO3Wb!LgkqmdloC4ZI;zFH&c)3S88wv~_iBu#NAc5QfU@PyH-FK4XR}Rqhs0pa>VBc@xwR93cbc5o>w|$&S&C}m"
    "5FY2dulhBTxR%y9oieRsCo5$<XH{A+1-bK>vHU6FTg06ACIf)<6_D0)*53l1qUJI|{GtFilEwlH(I=6|VjWuuS1{t~-njO>9I)"
    "q~9ix9xD0PyaupD_2b9GV4s4wHzMpSp^iv_OWNk{1{D<ovt?9xru=tJqpQ9YjhwtSikyU{@{4Yw!vj1u8%*0|YB=x`w%HI8KMT"
    "QnTe|NDeo_&NUI~I*;*CUpKSB;gN$Lc(`@pWrFa(>!`*}Z~ka-gqFnE3_(kG1fSe6gpAA=1?h0SP~!{^((^W&df6O2%;Il(Cz_"
    "5et!o=iEmvEKI1Ini{tQDdh>d8`+g{2bt-fn8iF>Sm?75a;0qkU#7@o`-O+u6+?oJd?EzGic3;Vs~U)$h79S$;{!hF~@sR}ngm"
    "05hTt(U<#GKf6%7tI|9Li4NW97`RE32pf2#2Ba4pr8J-Gf%3ey#NTouYY2`0yb?)R7ZpO(&=*J2`B3^pTv#)tr-$GF{@MzM)st"
    "QC<DqbB8MB9Z8#X74VIR>rBS4`^s0vhOUkvuwZwyxae6)!?NzRJk#H@o!1m1iqjpNIHkTV`!E~GgVtWbbcL^>ZMDf30V;V05_7"
    "EjfY~J3f$v&P`3PBHWXF-MHegvH5qlWPRK8D9mZf<jeRZV=51I2(|fHF3?exG$7-C4{9{%CNi{tInDC*g#|yUDr=39s5A1iR+L"
    "mdYwOEjxE-h!)Yke$hccRA%{_((lwz&r>dDi5P8bi`}+=vZZTE5W*IF`RM+Mc<1VIstRbZASxbjQBP%fF!h8`3YYk&5NdVBch<"
    "2-{;;&dX@a?VOzd74H<pe1D)-hO2-0RgX>Vg~5kh#!&z7I0!jft=P*NZL7|zcMSo7j`0WW6q%{C#MVn5vXvyUwE8cN{{{?8Yni"
    "%gzOU1MmV)_KqxS`CqW<_k`f`y1>K$sdHlD;SAvS(cjTJa!RflL=-2M}Kj4hqc}Q&shS`8J}C1uxW+X1Z`yKZBb}pL9zg3BCu!"
    "T)|;Z_Gi~GG6nXq_m(|_!M`4(nJ0SlpK67v@ZP!?-ui?vgjNGq&Bjrqsx>eX$$Szxi?&b1KHuw9NGJ?M>wiu4D?PQ=)@xPyhlz"
    ")Ena<GDLfjvy{$GcYy|9ySz5Hd2zUT5}ql)>|_SsJ{JhW+2=lJVVz(WYxt*nkQ2idihhQbZ`7;&~hGUCyuQvZahhgO90#zWUD_"
    "uxB)q9|MHk4YsTW1;)k}UL|)enhLYRIPEIiNz^gr9s7q+oq7SXI76vR(KK0rITbP^UEymiWu3SXe}twv7|ux1SY)u8W{Hm#ore"
    "7&a)HWBal#O7i^Jx$0~cllOb^rwi{<>SETuwvK1vQYj?dQ)eTc2wkgqrfcmwLh-fFW6nR1!M<#=kR_-AN$RL%5t0|kr)!)6^AC"
    "IgWXOiX{P%;XKQv8tz{`9jq@hsZ=7S<8;5s?YU+ZhUsdhj_$q+7fqm6OH;8=S;be$!DkY6o{|bEY7Z~g>&^rr9Ql9i}M<V!3g*"
    "iej*K_slI@&(0xqtoVZ5`D6J5V2c|Wzw>1AGEfc?YNzHqplsbl{x1P)?Ygk9_2j&0_mg^p%&d}#~-3trY)J%!^??3QsvL<XzU{"
    "|ty&!l3v-3y>^DWHSbh}fs$qkVoHWs=c<`n?f>nRsJJWthb@?mVY`+^UBwj*0zT6Eo1IQf2%voL6>qF@8JybgzxSa$iIYlv83#"
    "+OYD^rjC^U%kbndS2cKgplq72WW%+KvglN!%AEbruM)@481Id+IPlvZ5f;S(8wD1OdjlJ*Qs$h<=Y+tW%M?oBf0|ra;ME9jGZG"
    "TpFl9Zp#A0`T{P;+6>rqJCT1Fmi*M9sBYi*}Y7CXv1wj6TuS98?;y$5lJX=oU>BNh=VPzl-xN%5fze+-9BW75!Dhl#b?*3_p+Y"
    "{;(v&Ms*uC5jR^Jl^yYHdV?qTT+WUo^+3&tk(ifga7F(dWfzWU>F!+U(8@Y`1Ox@R0xO-(<orAb=~(Boo;JzH3$Mgrc#E}0xW;"
    "PGd8pB+auT>J!V_DE{{;WH?Xz3u~GW?Pc_}dmQbMTTxqQUH+0&3ff$qjd}ot+IXeIF@nzyk>p;JJW>hwSToo(4y=W+cn))zEIt"
    "nbf;nv<nUy+`TY%C?(me?NeiF&JKn0w)r=;#;%$^9kCw~8#_YfO;Xx@J>W($|Of%r)(_#ql7VjJfcnhT#dp=f>F>1@VuT<yW%q"
    "K|m~9p{xhuTw`leJ$Ey#qD%icoyfWFI@5Jgu2q5T^3;vitW*f_nD}ur2AC7j|5KqH(vj{ut!us(pqTrNa^0oUNg^LUJx`e13uY"
    "f=K^K%Yvbq{JD2tFa3JRc-L*)?iA2p-uw9XTblC0S386;$@a9k&St;)p62xKx6;r>|fO<2Wip@>K*jc7^R0XN>_*_kl_>8dUjg"
    "6IHcE}ij^78%}3_ZZj%*BpRT>%F;C=(RPhG$`-R8#oGUemeN1EEwYw5ON=r`ii7f`cdyMr6lHL&5YMy4@nXK)jqBXV5paJkr0E"
    "TO*7s7((I?i%Bi^?8%eZfWLJtyt;;)iQ=P4y#CgDQ=t>Xr0$?_Sw%mw32lNm7Z@%MhqeZ<`_u|&Nwq%7e*0ZcS#PlMgYMRf(!5"
    "bXP15CwLWrs?cv(;F!K-gh;z)-nkSUuz7Gc;QA0MfG6HjyJuQ<iIvS)RSgMkb>JT(NF|;GFVX$W+o0Qi8g635_$Tm<-x}qipiJ"
    "S5=09eXb8SdSl0L>Va!@&pI#_p#nvBE=@6j@0R?y;nb`rwf%!N-IGf_+oVA4Y!Qr2O3PP_Yh+g5zGX&cFLB~E4P3D)WmF(K_$n"
    "MOP43Dv{S9Em&?^6jv!};3+dZ(urya)12-SUpS|3Rk3(I5JhoWo>!{*{3h(Gp4hoo~~Pizl&*NJ}(R2MYYe;-6X+hd^~Ozhw1e"
    "I$%?coQ_P4ry168#-ROr}=v+D$(uXwfQ@*4h1{ea*aW2>ovE^aq)c1Y@#w=wQ42iT$tyGq1mm!sbH_~!1^Q~;Mj(79KFfxQ#ih"
    "Q_>ebO@PNdermnvPl8(-6^`rXdEpCPM*zM=HyqD+HOMy^TUWddWMZ2jyQ}OsM+8V}NEPF9v*_<C;dA=04R%EBx%9@Y49^PuPAJ"
    "3SH{28D6kyXX(j>0&7g>pwwNeScr{WL^OiT9BG9gyCK3LrS#;Q(Mz7IrRR05Vv*pG9>oDo=K_U&506`Butzm#t?u@Q>nQK&YHf"
    "(r85m4p{2zf1o2RSjOrQ!0XldxPF2mL?1e>V(@vjy)O42TBhnK@uecZ%yl6w0etQjZ$gtyvHdX0BzqBmq;4yud!2q~Wf_XlikI"
    "WnELQC=lwdRbuLFSK`<X>e`y>C>R{|p<?4Y?s?!qWXgr|{$`;ac}4aAV6^FD`c75v!J(zM4I29S=-(4-ONjvfjJI_r1mrSIQ0d"
    "UmP9!DLf}FMQ0DG~XxHY_uI7v|n2Orh17%u{d+HUu)u6I0Tf>pd5%U=P&t!Gs%cw@R(R5Z-jF0cWAQMZ=w2D&xC}D`J8(5L-<z"
    "HRZL|a36kIL?{2RK*94Vdtsrejdrn@iSmuPl<0=?)Tur`&rk&?choMR3T+M@EO~8a=&&0X<(GdoKRP7QU!bk0*lI?<%hdS9Quk"
    "}K}zUst(ByK&XXH}?s3tn`NyBaUP>CWiBqvGp)7atQMUu&8ZzULG9y_903>XHlx-wvQ{bJ;Oke$Nrjr&1!q%R#x|K<Cgo;L!*o"
    "MyGOHrW-U~S|yHrzbavY_lzIqwaU)xQw}yK=Q}NDUK%AY_5wn9v}?~DMy<0sTA%c@H2&B)0DKWhWsoc?38_YwkM6iecPjJsb`R"
    "E_Sp6*5o<#2Uu8xS{zx$Do`J{5)b)H~pdZYVN2*V;sx^Sv9wF)b+RLc!zksEe|@Rhw~=z%$zWfIl#k@`@uRQG09s~dj{fDBG-t"
    "{S-E7!5cxkOSdR6!C5{6kZ=eWFKOktY|pN|7=TSsQFG)Z=yG-{tzSIps|yBSf<z`gceV&g5o)#Ll*Md70_VXmA=C?q>54(wpr<"
    "GAEpL_&2Qyy3Bgihe|0K_3MUF-mE_5tYR*#d)CLiVKxmk#^SurHjNmRIcM7)@9Wt!Ks1l1EK0_)x+&exFC2_tve$!lt1ugwaf{"
    "v-#I>FjDq@tW7UwM|&5$j|kz6X2qFriYI+&X4vVBh3X5kIqb>s35mmIOv^U&rKr7Eduk90niNXbu3c%fgCaaAS;AXN}FN>i>wH"
    "u)5O~7J=D9z|9-Yd@y#?yjdGJa|M!UYp}>ezQO=Y;m?J-s_R`Hn$|+tt@6xkP2)U08JGPnTnSHhmv`hR#S5U+eN|{TX_8q#!2Y"
    "0&4{7~;=oNPi^&(bEwfzp6MjJr-9pU@sD-)t&^I%EpA6rRyXrqOMPyJ-&j|*p!D_{Z>MAF$>1#izMU-J!iBs8s_+=2iP0`cT-+"
    "yBtGa!-*=Luy1AC?e08ne_41@q_NV3X{jY`ZAo8mogmsT9Re)lJa?IDDjdxs5kLDiH@wjcA%Q~@E~MYC<}K83(-mAwW#9@*0}p"
    "h$8_(D1pI@mavAA0Wg5PQ9XX=q^M5x0coO$EWRJ`>4F)=Jbx8@&{8n$5FfsMGaxks;L;mJV_|z}nad6nRtm`8AjrMp9kJBupE|"
    "4&o93ru_+73?F0HuV19Tny`c{Qh{FV-U=nd!q@w=M_}L8l-!l;e@O{BVe{bNyXnZS|-~srP_7^eHaq4_W%-e-H+>nYKB;l5x$="
    "f&iB(8Yq7Lak~qkHp%1RdrN3CX!9d_Fce_M^OzHVJI#!&2y1Pt{m0zpuos@)9T@gmTj9cwjO+I9M=5E;yR<=Y2V(_vrK^aa3bD"
    "r74f@tc_C(jsO)oJ~+2HbN-kG9`t{p<jvHaZ0kFS>U&$Qi7Ze~<6VPi{V-MIyn&!6-0)lN^oHBr*0;q~0P$G@+%-CAmb4jvnqw"
    "lvBjbR0FdF+0cia}B9!H5Pj6z_?>2OVg!Y>`d9v=t(M$rJQo(-Ix^|ATF11*iAvgGz)#9>_tz_hDP66aAD3eCLiC%o0(02q!k$"
    "&+*DOF(w7AtB_#%1NC-FlhR<=VQqzn)vJ<{n*N2_AVLzTE+kUScF)x}cvNNWDKK~Q{)qW}!Me?YwsiSq?L3JKEKMvCeHJr%5F1"
    "Cov9`)OP9K)+B#Au1XD>?jT$xnD;HXDXJxWVaQoyR*Dm`4+|9V*TsfPV*LjQ!v~fcK1<$z<q12Iu#lmU;@K0q*j59WN(>@N$Qc"
    "BQ>u5y9|c!J8S(ps}~$XBuSyJ{Ge-Ff;hN@%SRy#A*S&Rmpd^H*;(p=!M9G30z#32j}{oI%UrlglsHktAUM!^WxR}E*8i~9C$~"
    "~dan0L(y{Qoj5yZ{%m0HlkpJ=7)yT5i_I(~cJcGY}_cZt@(@M1}$V3!fv+=8yemr_Aoh%cD}Gb-9z>-VAT+%jWz?LWencTsu0N"
    "tOcPyYuhSoVVYX*b<U&XrKztblb1^ULjH=BVy~OgI6X-AP<-x72lZ%;oF0XwJycB+gnogyde9d{!%qaXyd;>u^ud7u*a|D^Vc4"
    "EwjDl@ZVQHrs;r9PC4jlUAOm7k+?33ZEjN>3@YH@V8mp@YTwvd0L!jrF%!}VbFRKXl?!{DQSd2Qg0xx@!gpzpwiRLTCZEH-)IN"
    ")shcCQpPP}>N9=}NkE@qE<%13VZpYstHsudDSQM|fx#Qc2L!HTIT6x^1|32?z&c3!k84DpPo2wj0KTZk=mY#+Og;e7(5*QE}kR"
    "U%S>5gBQe|z|2bEH}a5yC`+3geTsDoW8CqK0_^e-EekrhdzX1=rhHp59m&uc9`g#6=LC9(o6De5h<sQTWr6hAo_!QZpPVp-04x"
    "-WjFKbFP)pcm^;i~FwgN}MfWA&47w^jDvBHR5@Y74mQ@X)%j+k>3Q?(qbQ>ER$4DD?RrL*{M2KV;+X9mCO2e9BBO*i{<)kDR>u"
    "uQA)y%%w>>Wj`tXt8J6bNL&kP&}a;E3eCHYXgbEzPCcF1Z-?t-%v4q&AD6z5spPmg3%2?TA^EaIsSk0vBm%NRjEagkHCUt8~t|"
    "f?^UQcXDf`lQ~oRnke3I_-7vvVj*Nb9!BzlATICh`W)(HN>-b_8jK4Yiy8Zp{ubNx<DBB|5<Q+Gqt*98KRQ@DFb(0P}UdRLVN^"
    "$D%JG3*u$pAo~Yz}_mZ*SVny1xU{uxWA&w2i-X6BfXV#sJ=CTUzC>-*^v3EbfUOl?5tsjl>O!<{Dj2br8<`?y;f3z6_`dhX#f8"
    "2#K8RP^$GiFt)#X=5DtJD_UJWzZkx1b>?m{_;d^KM)y}{c>|oE2IVao2ET}DB&x4o-b&!nMkBGYQ4PBdOEV7VWbJD@lxxXiuFo"
    "v#`5kW+Jg+rR`;HVzs(4tEj81lpqmNI#upbxL^&rPVfVH(8fEYnV@3}DlREh;0*LZ0b!M7%8wO-yu`foYRT8-5<#I7>v#J}a(^"
    "T!?He*}+`F~iAL*+D%nK2e%z8UrHmA{6M~Pn{<4P>g;+mIPKDu&8HqjOOfg%y{tt{eFk)R<q*2x?TLSb8JUu4u0<hbLPAK<Ngs"
    "M9ou5jk^HH>eH@!FrCd+db}|M0>-f4o;Y`Cry9n3F2t_+jHp!k@T)zKn#(a+bggN?(5%j5}RUfpcns1feJf_sveo$zL)LGB<T}"
    "<YD*zRRzBk6;dqt@rv1!rl-nPZV*XDo;O3rdt@qiN4e`P_~r7Q};2XJub?3pjCzntYZ%MM($G9W^Y*S4y#7wOqvNiNnh#CuC`!"
    "6=8vr@0DY|>0)WZ?6pbG`J=RW!?`b#b?JU^Lr;f|S|CI{qqGw?x54firJbIt^;67<0OG7(30l|QSt7k1=(Gt$T6qPAJ#zV{O}_"
    "9sXP_B0O`|*od8%S+PnsZA%`6xLkgDD7u)3!jQ=)8krQYMoF1$p3%BfV&{D?aNesD%ONfQYXes>5EE`9i<;>GMT0;AoH>$r-*E"
    "&gasYsHHv{hhMi*~c+{o!`Y?ZD=z%wQ=9@J|;AEIQeS%%bG~{gH^ptPCS<72BUhv>YZ*3JH46;B(BdU4VA-U^WqW3No?1O7_<("
    "xBwbg%`!rWSDIAc;r9g>~x^Tn5oRDe1^Wv}`la#xCZu5nZpI0D1X!M;Vo57Kfy_-dziAxS<H02KUb7702%HecTXFjrZD#(?!fD"
    "Tp^c6!G*#L49-;ft>|3X0I|=Z;e3u9xrQPKn&)>!C9$BS-qeZ_ZT-c#nhgL*PL8tjj)raX($K8b!6zKG-t9&$}PVOGX$LJl)*L"
    "&Iyi%?yu)-?$N0Q%a)5wcw9EBg_w@fBf1$N%&^g%o}<2XInrw{xzxRvSY*x0|E2@jDS&V9yr-!OG`(~Wn9h%zP0?qxA>0o4J*b"
    "2G2Q5C>1QdZm`+vqS=)cT%r~&ih$N_q0B~-hRg|9Zj4>6s}Njt4U4Kic7DRyMcXd7$Zc3`^88t$=mn5Mh?tU?g}Q(p5Wfo-(dy"
    "gS&@-*5ossyvSyC6U{gI>-3I*(%m$e)!po%(g0Ex^>>O&YP#MBR4H|2QrZ|Iy9)l-uT#!&ywQh%;~74`~8`_ie;EbH~NN~(jRP"
    "m1Zk8Aj{-bQ0<Axb%k`%Tn1?8xtA4Z7kah~2{hq~)9vgHnxRv6tyL<_~Z~velH&Bn`*@)TXE_8b42#oBlEhk_WQ>i44PN0V=uq"
    "Q@so*d0aNB#q}u}~kh2d$C?&|8dUpiBWA5bVBNsu0jId;;5&Il&lDZFmW9`4IP!G6Zhx3PjiAVF)@4=%UYlzQHV1zN4n!_qemK"
    "NWUYYG5N=yF6+dv7W#b7;O1+@gq7Few~N3cUr{VBjAx&*5;ANEzr0UmB(-24Cv5NR$yXE%<-}<ysa{u@6Rs6<zp5$@qf!(znl|"
    "Q)wqs{!mYY(dKl6_Wm-k8a*5Ns(Nvm)Q8^#yB*T$D#<^L$a>*w~4x;@}2&G&j17;;|Nx)Ne(U<%Jxe15;81}KcDHal6;!6<AG("
    "a~2*FSxm1O2BAydlpV&En508je{)_D#36$VZl6XQQ#T}10%O9G!Qsqc2WIiVWDa(e*<Q2PDX(Ihh|$nc0v?fyFHcK<6=?}SL;-"
    "{%&}nPXwcfTjz%?nW0`U-g$FokG)Hql8_l2$*C;eU8tsvXhQXYA8;}7(es~<;96dOMCUi-h{iKqt%IUHQW=|HGK<u3D`<WTnE7"
    "uhj@xDr|Zn>912ZI$r;*)G!A54MdFH4q-ZpVoWhKvrOUR`V+1ZNgo&<Ai5{R!7`AbWQu15M-<f($0#10-&4hA2c_sq1rpoDSd8"
    "&(Mw4C)-6>99-%754Hn?tEx&y*4=1m9r#ym#V9pEF_FZGs+J+#7;#wLP#89`q+2j3NdpOGVHt06wyXez5z5ghBjIdVm<0@<((W"
    "z11MX~`Mm_9oM!4st++uCZ5M|yuNd_eS2XIlLF2Cq4+Y5r!k9Y<YWy8i1t~06YK_hBl*Q2NIlSw@JH7YX~wEaeWM35}50#zB|A"
    "9FWD&Vj5{gI0BzEMa}toITSUB}!KNYSL{cVlwcoST!Qw_W32!tl3Od^%}AD`F}FD?kKp*u*XtSWOHWQP_cJTQk*$H|Aj^JpcYE"
    "PE0)10x{<p=Rna}T{Wy+~RiWq981{Qsp@0#LPqo5;u_+Nr^DwCvF?NFaSEGNBnvrkA+u5HgIrF~X2qeE>?4IhPdQ1sTf|+Emd#"
    "_Z2{1cLyC$1BT#@aAMrlQPl{!|t4HWNp&(e5Rg%X{km+yA7HAw~)&;bwBn3x7%g`8cCpsp{IeQyebrJkA?3G^G^2q9mx`NV`4I"
    "$}JdLu`_m}g4MBlOBEMME=%<@4=Q0p`m?g78jeABtyEE>|9c9P97R+PuL74a{y~ZHFVO3xtz<eS>x@P&FuSePX;`~+BsMlpycj"
    "o~{ldd*no@GN6CgG=WQgNc97D2GvSdY%e#b$a&2|Z{TFV!lP%wqacf+5CS4~)Yv(-#~V^?cuG*->f07S#l8Jj#g>5L5O;~I}jB"
    "q5(AbwMMhx&EBg*LAuo1P$W`SoG)#<+~XgV^{AN-v?u~(tW9KDzP#w?qvf-Fx)VQYe}b%`>V_Ng=xR+f^)dBr$*4~YlpSDy2Wg"
    "Ra@SvDF#Lx=;K<+yGo0v)Es6FmPk6i~P4Sv#<<ZkdMy6|@phw^Y%390@NxHvsz<%T3+G;V>#p`J(lviH-w^$b&UGbMf5T2*x<n"
    "eWG0QFEk4s$1SWKMsT@|jdw(K}XM_|+&j5Up?6?Q<U+3F+Z)-1X*Tqf<C3lhXEec;Za^zDMd~=B{z<|Is9JTKeX)XfA*4=x`%d"
    "f^6JQ+7bdiGWO?$kc|jM*BlUez;Da$$bg6ma`X=wQ$yhoV+oZBwg`tomrMO##)8p{p5Fwnp2p>Y9qt4GK%|7gnbV8PjeHSo!Ru"
    "!=iS&b8qHo=0bH2Sj57zrl-l$xaQh@RumA-HTY6vHwDuU?*hfO*SV%vLErC@kr`*2PadsyS-bM_G^`P(HJr9sr5NXWX$v+yq{V"
    "Ym~FRs&1u{DBD}Zbwz!k|RMK0__4t9f5U^@yqyVx5oOHKT%<}56Yj8g;Jm$Fe^^(aYutXos?D}*662OOds<B3~Q|FexxxBGlP*"
    "9U;Tw}$GBxv1Wzp!Tf;c37PY!2En&W&t`!S3%sWXyc#97vLx<LfrYA}kInjL5AkV<>|CY^s>&HI#B4Qnf1(FE0OJ<a>GQ%?XSF"
    "U=A;u05R@|wESR*)%@AcEkx{Oo4G0Mk~y#B~K++l+7(Lyivh26aH{{-{WKR6t}~<ZybBj73r=@NLC&Q5h3NiJt1fo^DMEeqs;Q"
    "D*!#H?R|l;DP#%ULdhnTLge>Aq02eP?$+}2FF=&4izaf4Mo{K0H-8N80$H5xrpH^Tn%Zl@_xMa7b94UMpQR3=A#0&Z2n`3X0wR"
    "jYAiN0LeJz$do<AQQW5*f`H{>y~y1iZNiMj|x5}AH*rp#i*dcwpyYE@=awIOM9<unN8HXoDcf5RS#Wg36br`L%uW+3IyyRrjLO"
    "oZM|*fZ0<WJ6CJ5(eYIf<W{a-ZdMu*>l&Bb>#QjvAqvR`ewql7{h;IEVT;?ZL{a)q2ftQ>MYHoyRJhLL&3gS-9I-g>7Ak!NdCf"
    "oL@sH&Rt{v8yC%Aos#B+K#w{0E9$W&XY~@im?Sa2RXSDHhs#^A|jOP1@dK~~b3E4>`b?xd%k&u&wTf;N^7IFnsnf2m&bQ_?rT9"
    "^uS<YWO;y7p?|#<|9HF;`5$;p!mW)^N1?dXYS)-PI7T3*mKr8=reEuJ_#B!Rss<iTtmmlebRL$C$@`7HpM}+b#3$L`No9kEu~?"
    "in~8~DG?uyu*(rpmP9e%tkTEV&U|U&V--7NoPg0HqVj->-##Hz&an@sJOG3BkKHkURah!!agn>P=+d8d5&@pmx<V2VD7rp#Ney"
    "FZU?f@QC5|hkV`Y2;HIrFkXaO$mA}bO9o2s7Gx^R{&2DR|?Z2(mna2KWa+o_7g{EHSIJ^~DkBr6J~FVpYBw6B}}&c`ZR?X0aRZ"
    "mko8C9*Ga9-~7!fGBosvH5J%5yjbbN3`}pW(#~hX1#t)++23s;@3ByR=%$FbpKJLEc1~J5d8l9n+CpD*kTXm*n2}rWk;Js2Kw>"
    "0WeV1Q(Dw?9%qa~e|Ee=;;%x=u-c<g#Ec5{)w}lu*IwtNVmTe!(plknjp*X8Y0e-=@<abbv{3PU0N*UsoBv!&60u!|65t|ScE1"
    "Q8oqp(SYk`y8IR;KA0`16w*23$hS5<LAUZy9`DbOdmDp<XW>q7H)U0&@pmknED<>h$EdCU6k2$z}$~IIn}Ygzud(U*q&}ItG{s"
    "Rb4VjaWU|wGGoqK=%|yMFne1Bd4O}-^ptt#9S)*%G?QHLPGx?)0xwkZC764MyCzdS;L=BcU|yKu((2ex9XUi<3iF=&VUl@O^|2"
    "(5_0N8UD|GM&`e<>&7{AeDOo)pkrKhvYj(Aej{`QIP0ik4(=jYQL;4|B(+*?l#Dj@4(MHxf>x?~f%7LQHK1e^}?E0HcDsPIqAV"
    "_xt{n6r|1cZG+r46%VK!=+cjb$Vcv@DDPBc6p+RmEW$83=^KRkT@hrSBx3OaM88Gf<+N~w~WS3SKfMbBAPSFN=e<bGZyagA$CV"
    "vBv?JTFqg0W`YOKv1L5S*3@93}FjwAk{}w>=B0|ZBu*fKz!)4Zkx=FnV^!pX3xCN@*s}&5B5o5s94Dv&g(muZ-|1bbY9lFb`ji"
    "@u}H<r6?8M{cXiW@S@s<e2ChlbC1^t7uuw#t)27!ebsN9PDX;p`7IRX@k9iE76JmJCohBxYF}<m<sxXUP1m$s6$#(%D_#c~3DP"
    "j;$mj9cC!5(jJMi4y_%l=Xi>h=(hl@O=H1F`N<!>=vzP882km%yY)HJ-!}*g`Sp)#R&>-CdcHz8k6&fjqCB-ABMlRCPJC?%XlA"
    "iyKQ1djGzH>*_dlIiP@lTl3*_?qB@RE-Mj`=3KMFkH*Tb0qY8ywTQXiPaqZR6((i!7?sXVPUckRX#t0%6S`^et!?@{eVB2`0P!"
    "<U;d!dO$SA@lA%bk0$$JC5L$b3Jgsn9(Iv$<pmvVUFP=Zt;*L<XiIuqDqVvHi5f>Nc)%xVqcX3S>v8;C)=u5b(05^)N&6milux"
    "9zvQ?{bOhfJ|5X2%nWj7|{kVTTjeW_XB71fX1c4K}+PFv1Gd(D%tuinjb#0mt3uo+#LRjK_SVgx@r5=q>*VmMZXFQQJS^<Jbud"
    "ON<YcDVz$mviPA&@y7J4)d35S`W{QFllSg9+JT20VR#0HXkv%JxfE73>AtOP2q9!XRnj1G?gOFEn?Ew6P!!@09X=F)lVMB!)j+"
    "NZl|(SegobUiFdQUuea>!f65skt#?phXbr|4NKWs?e)1oCbmvf{NtfgqR$@gm)qBRf{!LzVad)&)5BdwY-k9iXc5m2ViRS@N%M"
    "lbATg63YCjypOV;Qs<X<BJI1$N-=Zm^H_AF-B1IHZL(vKWD1_vvrD!RX?+dBMKb@LQLjE;7g#(XDezZm_ByyXRv2i5^Cv{4ydn"
    "yKSVLBaxN@Pn4nP@=?vOqx+_%5JRmpUh&txjr~JVYu&V|8PVwhK8ZpfIXT=<Qg@Q^*8SsFkmN%-z*`Ke}ZS$&AZuyJ*WC5aH5I"
    "$Ahy;nZS8Vxd{i>sFmg40;wfKVm$Pa8Yfulx7^BX=98t|AL0^p(c#(G`u)xkf6p44)Ue&QD9Vc#osft#vaB0_96mO+;`pt9~Mr"
    ";Bc!j4-~5TP0!g`Q{;)o6)e+d?8Nitg_;2V8@Ni7<YH?+%K!z+BLfoK9FXN^_=<y$693*SDpf-||~onhF+PFy{lD_{n2{5^$Dn"
    ";kUn}CJqZwVh(QI3}Z343m>dZt>K+;CeZ*<0HFZ4>`jBWSDtizByyC3Yw#4xQ2yXv#J{h9Rr289M#zFo<tX?4s44ZB=4dMiE}x"
    "zxY*oZq_UTl4Mi)NP18$e)U|Vm#pv)BknXk;WB^-eU_n4o^msdQ;HBESg>4YRPAz3gyvuWWvV*&Rs2^^PIB#S0b`HXXw)P0>ck"
    "8d8d0FuQtKoISlh)QwBc7;-g$1t6J$!rlP_WZzkHvP;RBG$Uu0%HnN5cuZ}By8q=#)sm2b@S?^8Xp5T>hOnzefMOo%rk|#ZyKT"
    "@t*ES&HKn?F!==-n^;|DjrGs5Sn?p{e;P=$$wbaw1K|JV=A4;0~-UdXjjE$prH^-ryK(yj>?FWe;zE#t+b$G9NcWZEbn!S~m{5"
    "0a$c1u)bx=UNMwv{3uJ-q3KGGlDyO-tqCfX>b&Y3w?ko-)*DNdCUTWNd8mYqt%L)5hvvjt`SmYd0RTK<{;=<A%^FM$fg8ZUaMN"
    "uLxolYn=fnp!-qG7K}^W+Mif==Gzk7p!r_!y^BR!f9O0YQ34Xc+|QefVDk&^=|9UnZs@NlOc@h)DTfvlk}C6tGVzpJuUpB1Yg8"
    "uH0SXR7q|5oUet9*wM-PxdD-k1i*?R$!^ss+f9UHD@kNfOYgm)pH0itOo?l=lJrw#XXszD(!Ci?(68XvLrF_EfURNVHaqp4QET"
    "KJ8IiH9@T3Jvie=Ha;f7#w}898{eqYAJF!E*>P>k5|}o@pR(HL+r*^eeBe=<NL+{akwI`ZV&gEuX<B2lQ)vi*7^{b@OTAliM`a"
    "VAL>COl|!V#x|gZYlTUC`LJcWnOPf*kTvFfkd??DOo*MWMiJ1OKOO|7>M)HdJa4U-!eNZrY2eGO)A`qK<As|uLZF*xVy;=>#0z"
    "x(qZ^Od5FU5jbz)UMo`QTbE*c$^{;xY<SZJX)z>|P%>&<0x>3TK}&GWG>#B$o^DJ#7G$K23WK@)O^V4dOCi_6Zt=BRGIPi8jO5"
    "si}g8bF_M`sa&;@Xn`D%52j!7)5jy=xD0|cNRX6cy;uc9uyG7_A1<H@bOxjN&jPsj!$n{di7%-0VbYyE__4EQG}+pdXYIm*F~p"
    "EXL>Hmnq%~adeS2^<Q&|whO!ZrZ=TE(w00T5>7o}ynL0hSsY&O|=x-L)?DB)9{5kkMhkq1y#x(;a=rrT3FL%!BUJ=$TiY4c>N6"
    "r!@WotDqN1+#i{A>@75j1;4AsztQ5OO$}@ueR1phG6XZldh`uv}tJe;Ui}n?IrpptE~NH?wo(Sy@;JZC}DU@VVKl(UKc!z#pI@"
    "jcuw>uCuy=4l7$EfbtJ35$}qEJX#s_l!zNlpxyjJEX3LIsm&*6{H0<eF;dDfWeeIn#eVHt*3dDUVP^rJA|Gu_?KfTzy;nI~{3m"
    ">^?jCrAdL+^<mvELRv^iNI20Gi6fvN3cJfXuch7SGzwxp4i$1X_KNoRS1yrgX^(hEF%Ed%m+sdsS15-&>-t{7AaIwO-8m#XfG8"
    "A4%%{oPG>AJ)yYQQQq&7vEOnuies#Tbjx+cG;xLqQq~7zOS?p;gG-f{*n750`{sSwTZ;?t%OlTX?b1i^UqFwk3({as<=}5W-+k"
    "cmtV>%(q(7)=zUG5jI6q5>qT5SlMI~U)wGEQ;ZW82W<m)ZaAW?Tg!ts6WxxpCMgfL^2;O!R}%rz9J!)1MoMrx7A4(P*dwR-xf^"
    "$UCPfVEuPcOy;aeaXPgq%#STMEPm02jRW~^5ZW<8Tp>^e>2oL`PJ@3Osr4es<^y7)}+F>y=&aCVd1$u@uOB}+MI)mhs5i0tur_"
    "!Z)1z2tT#2al!p<o-~s-GlD=+qscSNM-{L`?v^XImUV@afJWx1Qq)b>qtEgYs6)?t#7)~esBTt~AxP7sMwp7UVgcMD+E1A&n(<"
    "+-{dGm96VVorpobE;z?{0nRE5Z~Tj&A>;k{*TG;`5y(OzB?*ouhSwjmMV2&wh7NoY+adr{GJn5AE-L+?bV}r6Q?qwy!giDj=m5"
    "g)L<38U(FRtRo}ZnU|D!Z|$|3fQf*onSWd<_KV9(Z-n^HkEz>`2G~fwS5x7&4M{VdjU#Cl%*n^fMK0eYo|yqB+-%p+@tA;c2bY"
    "g?meCG?Am+<p8JTnWUhCE9)3t`5310d9zZm_ozsqb<*o%Gb+K-aW?h@F7S+DIsHaDoMNdYMIj!7^R_~&SDnPbFXaRAHHMjg1MP"
    "{y(H8xIUzF3acfRui439Oup=Nx*@J+fuM_Jj|>s54cLlrf!5d7ASOwKFE-pv6dFEe$%1+SR-UYvi`|J3u*gw$v1u2@GvfO9WRA"
    "vh6X?YR{OrYUh0b|#e~p^ybfD2VI${kbVrTrB@?Vh<OA+Mj;>SkGAYJ&7_(*6Xb#<pESBFNvCXT6d1;)y*?~OyjTybJ>;wF>Ye"
    "d|NS}D6p=X)l*P;m<O@Rp&oeQeV!Yt6=O%|ea`F&Z8+O*m$&)aYC1I9#QV`|<7!Nc--Ga(XHU<c-GlkKyMOw*^*i8;W0=yjx$a"
    "6}=D6yQDSTL;dV_CZvIin?+|GJtZ7wYykr`&(?Pd?k=n1zO2qr@46fgsqH0LnHD?K*Nuh2m4!2hIUZD~mZZNqUTH>zVmrFELrg"
    "gwUCagXr%@yb&$`8rKXF+@Zr??yNK8?3q9jgx9zHqEL$ql#GeIokF<>=xh=Vt6>R6+0p9BU5c&rP?h}oRmfECMUX~^24p91~r1"
    "yo+H=4-LCmf@A=)Lks9Z$iG{bduAjslM`(MIxFM-L4-JawM@dqUGQjTspL7mu2HpT%ly>^QEtKL#=JU(hb`vh%Kw{+BaY3=b!Z"
    "wq@EFWpZJjg72f9Z;{+DPOJfNF1^+IdN`YjbA;d;Y3y3Ah21=n09&|(5=4c|oGOZ7AQ<$f%f>^xSb|B%$5`RY0;!lzJHFyWvxo"
    "}SVdnNTy-wZ=hpukBCmJJrLHkJrCR!V5Z$mrZrudp%`#OvRRo;rD3Ncu)*<?j4XWFbu_0=p?0n{>2HCRD&_Z=Gr}uB`M?&fic*"
    "+vEP~-k6~U)ZBAO<r%lMuc8xlf2*aUOP%}>M;BV<oDggpXVnLWm0q_LF?I^Zh?&&r4mXbq3e?ys#E;<CoO{=@b2Jr)JR!&mo)s"
    "?9W)-6<a%k-W;K5o(_QLi>gNPoX1>`7vlszA+%6YRtS#%Z1Q$u2qt0+{;{|^Jz=EDRjSRn`QBVcs97Y4<cJfnRY2tuL=@B_BuT"
    "%drs!r0T=C^6-i6Bi;IJiSANnPo0UwaDENXcl)#@(j;by~zb)m7BW>(Pr8IaBPcf?X@`bj~<%X0~@x@(*R?J8Vo0&E7co#TOoo"
    "l9|3#1w}K|`gLEmK#}$29olD7p#22cW*pQgKf3?9TwYpK6!0_5Dd2{M3-&!j4M620OhHCePN>0Rlz`<v09;ElZN~GJ1<IHKLQs"
    "qb?p7NPF!3#qN9E1u{By-~LUQLFG{=X$bdefvqisJ;)+);%?`^ze9AHl!AJ+8VsoVAc&dQj*mcZvyL1`yjk#);Fa_(>`>YW@ok"
    "3<`GL`3qHT24l?8S3(04Z4qgiR6bTj!-$}Yo$8pGB<qPh42rD`sFh6-11Ic&Mhh1(s#%%OXt1~U`$sna_MugpY@52nx~360+eo"
    "|grK=Crcc~GQ1C**w9wfI=2l4Xb<j2R2zKMl@bs2Js=jgRROZaH)h~p8Kw6)x~-~QSuh3;!pxOhKjwe@3?J1CX#DHC2ms%~^Lg"
    "A1jMZfrFbl-2l{8?!ie1wlud%^c8qZ_E=fV|W@Su2lF9t-@)0)us~!xYOin)8ppu7L405LxtRudeb$@vA{=v@QA~Xf#hvQ7$Zz"
    "8_BnV6lyD3s7^w(uHFlv5p$MlWp{mIk7wH;*z+oW+3;Ief)(*Q{wlqyqMYrMVj71HhgZHVPAC*Mh+You=!hPIcu3}|`9KG(_?R"
    "Sgqx8(K~u)Gn*#g0CifJ^}L|LC|b8ngo)BB)U<r0&cX=kL`&m1|!LqzFS7`()y?kLwZTM{jCM=Jt3~nWik)&6y||*>t3ZcP^hM"
    "@tys_+lU25@AYyLg{1MP$Q0vMdWe(J8bts|2)Ym{HpNaY8#U8D>VI<+L^mCHmn(y5xI7hUSnwr-zxC;OZXO94;oq0NvgD~B!)z"
    "+in#0HBb&qORjtGOr(RzoAl?<a-$gyTiv7<b{0SINTDKK=Qiv2?5d-HMUZc34wrPfTQPV!mBJtB@?m3Ff{Lz+*Dqp?E-NGU5o1"
    "!Wyuuee6gEW+>Zaza%h_*8!I4&o@jbi6|mis4;zNGNMi`ZT*{&|wix!JebQ@w*O@JH7q2ju%1%1}Bfw_<`kAa5aD{a1BbXsZ4v"
    "m9&L3c4Q<vH?3<zwVF4a5?(*ByC3raxwb<}47$eq9{5Z7dI14Spc27o9ZridWjkjy((znj882nSip55GY2T9>fz4OFqR9L$l!p"
    "Ijt#^QFQ9iw;s*GT&*Jy%o72O$EOkdmY*TKMLHKQws8__(#gK{?sw>?}&;bG0APhUYko4OKp{6E>nx>Gjy@<-PDd3BR6>F#H*;"
    "IHbgp_+UT=1LVI_hd5$^;;#Z|8VFP-qFu$x?I0{7`b(n;I$?ysJ8RSb1wQb=52IZ59g61e|K$2ziaeC#-@5gjB|h@227sd1$TR"
    "tWCB!&8-Hv5t{ZS#bNFCdLPwhSmTpO9Ra;bQ@{-=H$y{}u{K_jFU$<{lONMXFIdjFt20J<nV*owjfhsP`psJ?&Ws8>Vi3(v+LE"
    "HCt*5GGs#hq<Br=i0Ls$^Bwfw!$c3Oht0Et=R*)LWE86r#i|O<=)NIzRf|SOCiCGU!sPFE8C0>%q2%+WTEiS3H-hWCtct((6#&"
    "6_-T5Gi|Yu`A48ZGQE(O7pnZ2jEiMHo0$?UD^gP)#y1_Zdh|53|90}k23&TNmRfLQ}tyXl!q;aWzdn<^ibXwEjnmu_0Da%P<!Q"
    "&g(g7R?do|3i-fYXGNuavi%GBI&(KUg#MJOu864Llwm+;E`H9;Ne<=+SFgp>5^zFrE_j=~vCz912Mjpj%2x$zX}}isri9to>NF"
    "EHP|ST(b?zDU7gU{KU_!DkmaIv#CuVh!T=2O)5<tbmgRd4-ox{VZ1B^X+fKMyIx9^diUHj+#pL<rZjpy&cBBHM*4l~UZbY9MSL"
    "}c&Oqf+(?sCbLDV~PGH)Ok;yY|rb<YhwLWw8Zb$6jnFe^GVtikYN3OhVKH`}y`{R5m5m<#)1iAh5IFZ}c;5~MGE68xmB`u>rM$"
    "sTRE>La`;lrW8S9hFGgPL+D{6W{_DE82o2j3fI$0Y4W+@DD7&B0Wf_(78BHdtT1wI0j8TS}(sn?tdCij^~Eple4qj>(Xec=!a#"
    "82ZaXAtA|pwCAM0(_~mqe&l+*ylMVj7kGyqsXBIYiuDgn|kbLgoWj(!FH*B#=Uf68wX2Y+Lznco)Ac9d@Jp|YQuBSt_6Xou%0K"
    "mdN1;+<cGk~!!7EOxY^ujY{m=1?jsv~;m5!<>oi0q+*x^KWHdL-;y)Y1^`%1c(@mT@16M8TH9VE`=a$e=U)1iaF;J^8<E7%D1$"
    "wgWLr0Ag>8o5Nt;j+zJx_-7r3a!)siiTu#X)TPB|_hJxeU&2XWGPSN%W@2fslg(04`3fRpWCRpIaq(p&;^Jd?Q@w61co2Uh`mx"
    "KD>H{;In=jF7q27Cv`s)sbLGrm!eV=cc{0?ap%Jl!w(=lf=^O`Y}NbPWcEuzMHo+M*vQw{7%Pt0tnTmn^DlVX8k@)1`njO1_E)"
    "zYR`kT6zcb!!lCbLCH-v#vc^dX;^*c=pI!q%G={s&6&16vJ#fvipmYV6y&K+$>lRd9Og70^d8??j{^aE2AkW-#lX<KWZ{It?V5"
    "0-GP|_<rC&eK3G9_OwHWWkDf9AFL5N<`vL@-)_v<aZLyM~u^}+zd;iT_LSooIkFsWmNj)o<7gzshSUF;Vjo6951SYopsdeoq^5"
    "@w}Xy-bzNWzhMZ_oh;hF^?2V&Wk?Y^NsAb_g}Ud?i?FTZ(Av#MBgd+|26W;H95=bCBG6F4K^HkOpBRs8`zI54FpLS(Q*ca^Py~"
    "?;DH)oYH<Xa5*fnd28fSK9Z5qDRl#h5_Rwl{m`5R$m#zW6TmYoP58*7oYnn{_Hk?sB-cD|>kr&Sr2*mK6|vm8+|<r1)iw|*>{W"
    "P^d7W36bh~!+IsQD$*TXv7nc^euzHu%*$X463uzP%80s{UfN_hK&1PdMUKK=xI{bHjPZf9caj!VUbllN8YA;}PBa+N}rD&mkR>"
    "UPOxBD$PzrXoG(Kk}1X8w2&cDrb~nS>Sf-znb+P`%nXp^mI+wdZ-Xc)R^11YPfM$?f{fMD)n<LJNPN|DxI@SO0fTn`9bJ)peP_"
    "OX?L)z$IiYP$*H4)4Bmz%@rcg7J60bKA5~7e@A4aB1}9|Obh%rh%ygg}VQIUAj+yV|p{Qnpm{_jMFK+gpF<2}~)BN)XkzUJ&OH"
    "Pd3>UR7A56)MQa_1UnSe<5Ksl<_h(dSQ4)3PG0Fx&lauDQZ*o2bv0>+VwA@iq<}FNUrc8R-Yh)5cNLQ_vFY(-Jqx1qk@*RU_>U"
    "nYDWkS$3eFh2@yw!GbWinoZDE*XGNyo~@b<Gdc^Pempbof$k{%QtF=ggjj8WM70G+4OUjyk9xboY@r#70HtvBpxLpuO~K7-)-;"
    "g7G2}w>CfR!E<+cyqhBD*_=>nf|naZYbkS=8U5>_<Kg#3yHbW9AH4GlZ%!;y*rn)D)1={lZ?IG(xMYuV>Q*zk%DVuS#`QGsYGo"
    "^?+lG{q-iMcG4_I6hymI2?AtvGKRP|5E)^mfxr2j>#(gj-yZu1#A=fr6hYPHk4PEP~Z{l`{PaB&Z|MR-22U-_~j%%jd&^O;)X9"
    "ExUO5sp(>%5CHgI4s;J8s`<8w(H8P(f{b>LsmAG&(l*Bb(kN^MxYQjb1c0PIe00EZC0f5jRurJZhvBYQl0ssI200dcD"
)

_STATUS = re.compile(r"\b(CANONICAL|DEPRECATED|PHANTOM|ARCHIVED|ARCHIVE|INACTIVE)\b")
_KEEP_ORDER = {
    "min_kbps.ini", "maxrate_ratio.toml", "max_kbps.properties", "bpp.env", "defaults.json",
    "env_overrides.json", "config_schema.json", "validation_rules.json",
    "sample_config_dev.json", "sample_config_prod.json", "output_contract.md",
}
_NETWORK_MODULES = {"socket", "urllib", "http", "requests", "ftplib", "smtplib", "telnetlib", "ssl"}


# --- reading agent output safely ---------------------------------------------
def _out(workspace: Path, name: str) -> Path:
    return Path(workspace) / "out" / name


def _json(workspace: Path, name: str):
    try:
        return json.loads(_out(workspace, name).read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeDecodeError, RecursionError):
        return None


def _text(workspace: Path, name: str) -> str | None:
    try:
        return _out(workspace, name).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def _kv(workspace: Path, name: str) -> dict:
    text = _text(workspace, name)
    pairs: dict = {}
    for line in (text or "").splitlines():
        line = line.strip()
        if not line or line.startswith(("#", ";", "!", "[")):
            continue
        key, sep, value = line.partition("=")
        if sep:
            pairs[key.strip()] = value.strip()
    return pairs


def _int(value) -> int | None:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _same(got, want) -> bool:
    """Equal values of the same type, so 1.0 or True never stands in for 1."""
    if type(got) is not type(want):
        return False
    if isinstance(want, dict):
        return set(got) == set(want) and all(_same(got[k], want[k]) for k in want)
    return got == want


def _sha256(workspace: Path, name: str) -> str | None:
    try:
        return hashlib.sha256(_out(workspace, name).read_bytes()).hexdigest()
    except OSError:
        return None


def _yaml(workspace: Path, name: str):
    text = _text(workspace, name)
    if text is None:
        return None
    try:
        return yaml.safe_load(text)
    except Exception:
        return None


# --- running the packaged tool, unprivileged -----------------------------------
def _nobody() -> tuple[int, int]:
    entry = pwd.getpwnam("nobody")
    return entry.pw_uid, entry.pw_gid


def _extract_tool(workspace: Path, dest: Path) -> Path | None:
    """Unpack the delivered tool.zip; None when it is missing, unsafe or lacks cli.py."""
    try:
        with zipfile.ZipFile(_out(workspace, "tool.zip")) as archive:
            for info in archive.infolist():
                rel = Path(info.filename)
                if rel.is_absolute() or ".." in rel.parts or "\\" in info.filename:
                    return None
                if ((info.external_attr >> 16) & 0o170000) == 0o120000:
                    return None
                target = dest / rel
                if info.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.read(info))
                target.chmod(0o644)
    except (OSError, zipfile.BadZipFile, RuntimeError, ValueError, zlib.error):
        return None
    for path in [dest, *dest.rglob("*")]:
        if path.is_dir():
            path.chmod(0o755)
    cli = dest / "cli.py"
    return cli if cli.is_file() else None


def _kill_group(pid: int) -> None:
    try:
        os.killpg(pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError, OSError):
        pass


def _grant_read(argument: str) -> None:
    """Make an agent-written path readable before the uid drop.

    Agent editors write through a temp file in the same directory and rename it,
    so a program the agent wrote can land at mode 0600 (owner-only). The checks
    run that program as an unprivileged user, which then cannot open it, and a
    correct submission would score zero for a reason that has nothing to do with
    the task. The verifier runs as root, so widening the mode is always allowed
    here and it changes no graded content.
    """
    if not argument.startswith("/app"):
        return
    path = Path(argument)
    if not path.exists():
        return
    try:
        path.chmod(path.stat().st_mode | (0o555 if path.is_dir() else 0o444))
        for parent in path.parents:
            parent.chmod(parent.stat().st_mode | 0o555)
            if str(parent) == "/app":
                break
    except OSError:
        pass


def _run(cli: Path, args: list[str], cwd: Path, data_dir: Path | None = None):
    """Run the agent's cli.py as nobody; returns (returncode, stdout, stderr) or None."""
    env = {"PATH": "/usr/local/bin:/usr/bin:/bin", "PYTHONHASHSEED": "0", "LANG": "C.UTF-8",
           "LC_ALL": "C.UTF-8", "HOME": str(cwd)}
    if data_dir is not None:
        env["TASK_CTL_DATA"] = str(data_dir)
    command = [sys.executable, "-I", str(cli), *args]
    try:
        if os.geteuid() == 0:
            for argument in command:
                _grant_read(argument)
            command = ["setpriv", "--reuid=nobody", "--regid=nogroup", "--clear-groups", *command]
        proc = subprocess.Popen(command, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                start_new_session=True)
    except (OSError, ValueError):
        return None
    try:
        stdout, stderr = proc.communicate(timeout=RUN_TIMEOUT_SEC)
    except subprocess.TimeoutExpired:
        _kill_group(proc.pid)
        proc.communicate()
        return None
    finally:
        _kill_group(proc.pid)
    return (proc.returncode, stdout.decode("utf-8", "replace"), stderr.decode("utf-8", "replace"))


def _reorder(text: str) -> str:
    lines = text.split("\n")
    slots = [i for i, line in enumerate(lines)
             if _STATUS.search(line) and not line.lstrip().startswith(("#", ";", "<!--", "~ "))]
    rows = [lines[i] for i in slots]
    canonical = [row for row in rows if "CANONICAL" in row]
    decoys = [row for row in rows if "CANONICAL" not in row]
    for i, row in zip(slots, decoys + canonical):
        lines[i] = row
    return "\n".join(lines)


def _write_corpus(dest: Path, base: dict, reorder: bool = True) -> None:
    raw = lzma.decompress(base64.b85decode("".join(CORPUS_B85)))
    with tarfile.open(fileobj=io.BytesIO(raw)) as tar:
        for member in tar.getmembers():
            name = Path(member.name).name
            handle = tar.extractfile(member)
            if handle is None:
                continue
            text = handle.read().decode("utf-8")
            if reorder and name not in _KEEP_ORDER:
                text = _reorder(text)
            if name == "defaults.json":
                document = json.loads(text)
                document["base_config"].update(base)
                text = json.dumps(document, indent=2) + "\n"
            (dest / name).write_text(text, encoding="utf-8")
            (dest / name).chmod(0o644)
    dest.chmod(0o755)


def _held_run(workspace: Path, corpus: str, args_for) -> dict | None:
    """Run one subcommand of the delivered tool against a held-back corpus."""
    work = Path(tempfile.mkdtemp(prefix="task-ctl-held-"))
    try:
        work.chmod(0o755)
        tool_dir = work / "tool"
        tool_dir.mkdir()
        data_dir = work / "data"
        data_dir.mkdir()
        out_dir = work / "out"
        out_dir.mkdir()
        cli = _extract_tool(workspace, tool_dir)
        if cli is None:
            return None
        _write_corpus(data_dir, HELD[corpus]["base"])
        if os.geteuid() == 0:
            os.chown(out_dir, *_nobody())
        result_path = out_dir / "result.json"
        result = _run(cli, args_for(tool_dir / "schema.json", result_path), out_dir, data_dir)
        if result is None or result[0] != 0:
            return None
        return json.loads(result_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, KeyError, lzma.LZMAError, tarfile.TarError, UnicodeDecodeError,
            RecursionError):
        return None
    finally:
        shutil.rmtree(work, ignore_errors=True)


def _held_config_ok(workspace: Path, corpus: str) -> bool:
    produced = _held_run(workspace, corpus,
                         lambda schema, out: ["derive", "--schema", str(schema), "--out", str(out)])
    return isinstance(produced, dict) and _same(produced.get("config"), HELD[corpus]["config"])


def _held_profiles_ok(workspace: Path, corpus: str) -> bool:
    for name in ("dev", "prod"):
        produced = _held_run(
            workspace, corpus,
            lambda schema, out, name=name: ["profile", "--schema", str(schema), "--name", name,
                                            "--out", str(out)])
        if not _same(produced, HELD[corpus]["profiles"][name]):
            return False
    return True


def _tool_source(workspace: Path) -> str | None:
    try:
        with zipfile.ZipFile(_out(workspace, "tool.zip")) as archive:
            return archive.read("cli.py").decode("utf-8", "replace")
    except (OSError, KeyError, zipfile.BadZipFile, RuntimeError, ValueError, zlib.error):
        return None


# --- positive checks ---------------------------------------------------------
@criterion(description="every one of the 23 declared artifacts exists under /app/out and is non-empty")
def artifacts_exist(workspace: Path) -> bool:
    try:
        return all(_out(workspace, n).is_file() and _out(workspace, n).stat().st_size > 0
                   for n in ARTIFACTS)
    except OSError:
        return False


@criterion(description="every artifact is a regular non-empty file no larger than max_artifact_bytes and not a symlink")
def artifacts_within_size_limit(workspace: Path) -> bool:
    try:
        return all(_out(workspace, n).is_file() and not _out(workspace, n).is_symlink()
                   and 0 < _out(workspace, n).stat().st_size <= MAX_ARTIFACT_BYTES for n in ARTIFACTS)
    except OSError:
        return False


@criterion(description="config.json is one JSON object whose lowercase key set is exactly the 31-key spine")
def config_key_set_matches_spine(workspace: Path) -> bool:
    data = _json(workspace, "config.json")
    return isinstance(data, dict) and sorted(data) == SPINE_KEYS


@criterion(description="config.json equals the independently derived ladder, value and type, for the shipped corpus")
def config_matches_derived_ladder(workspace: Path) -> bool:
    return _same(_json(workspace, "config.json"), EXPECTED_MAIN)


@criterion(description="config.json max and reserve allocations follow from its own average allocation")
def allocation_chain_is_consistent(workspace: Path) -> bool:
    cfg = _json(workspace, "config.json")
    if not isinstance(cfg, dict):
        return False
    avg, mx, vbv = cfg.get("avg_bitrate_kbps"), cfg.get("max_bitrate_kbps"), cfg.get("vbv_buffer_kbits")
    if not all(type(v) is int for v in (avg, mx, vbv)):
        return False

    def rhe(num: int, den: int) -> int:
        q, r = divmod(num, den)
        return q + (1 if 2 * r > den or (2 * r == den and q % 2) else 0)

    window = 1000 + BASE["timeout_ms"] % 4000
    return (avg % EXPECTED_AUDIT["granularity_kbps"] == 0
            and mx == rhe(avg * EXPECTED_AUDIT["maxrate_ratio_permille"], 1000)
            and vbv == rhe(mx * window, 1000))


@criterion(description="config.json qp equals the integer staircase priority for its own average allocation")
def qp_follows_integer_staircase(workspace: Path) -> bool:
    cfg = _json(workspace, "config.json")
    if not isinstance(cfg, dict) or type(cfg.get("avg_bitrate_kbps")) is not int:
        return False
    offset = 0
    for threshold, delta in EXPECTED_AUDIT["staircase"]:
        if cfg["avg_bitrate_kbps"] >= threshold:
            offset = delta
    return cfg.get("qp") == max(10, min(63, 63 - offset))


_SUBCOMMANDS = ("derive", "profile", "init", "set", "validate", "export-report")
_REPLAYED = ("init", "set", "validate")


def _subcommand(argv: list) -> int | None:
    """Index of the first argv token that names a task-ctl subcommand."""
    for i, token in enumerate(argv):
        if token in _SUBCOMMANDS:
            return i
    return None


def _replay_transcript(workspace: Path, commands: list, config_path: str) -> bool:
    """Re-run the recorded init/set/validate steps with the delivered tool.

    Each step must give the recorded return code and stdout, and the config the
    replay builds must be byte for byte the delivered config.json. Paths naming
    the config or the schema are redirected into a scratch directory, so nothing
    under /app/out is touched.
    """
    work = Path(tempfile.mkdtemp(prefix="task-ctl-replay-"))
    try:
        work.chmod(0o755)
        tool_dir = work / "tool"
        tool_dir.mkdir()
        run_dir = work / "run"
        run_dir.mkdir()
        cli = _extract_tool(workspace, tool_dir)
        if cli is None:
            return False
        if os.geteuid() == 0:
            os.chown(run_dir, *_nobody())
        scratch_config = run_dir / "config.json"
        for item in commands:
            argv = item["argv"]
            at = _subcommand(argv)
            if at is None or argv[at] not in _REPLAYED:
                continue
            args = []
            for token in argv[at:]:
                if token == config_path or Path(token).name == "config.json":
                    token = str(scratch_config)
                elif Path(token).name == "schema.json":
                    token = str(tool_dir / "schema.json")
                args.append(token)
            result = _run(cli, args, run_dir)
            if result is None or result[0] != item["returncode"]:
                return False
            if result[1].strip() != item["stdout"].strip():
                return False
        return scratch_config.is_file() and \
            scratch_config.read_bytes() == _out(workspace, "config.json").read_bytes()
    except (OSError, ValueError):
        return False
    finally:
        shutil.rmtree(work, ignore_errors=True)


@criterion(description="report.json has the contract fields and the config digest, and its init/set/validate transcript replays with the delivered tool to the delivered config.json")
def report_matches_contract(workspace: Path) -> bool:
    report = _json(workspace, "report.json")
    if not isinstance(report, dict) or report.get("ok") is not True or report.get("tool") != "task-ctl":
        return False
    if report.get("config_sha256") != _sha256(workspace, "config.json") or report.get("trailer") != TRAILER:
        return False
    config_path = report.get("config_path")
    commands = report.get("commands")
    if not isinstance(config_path, str) or not isinstance(commands, list) or len(commands) < 6:
        return False
    order = []
    for item in commands:
        if not isinstance(item, dict) or not isinstance(item.get("argv"), list):
            return False
        if type(item.get("returncode")) is not int or item["returncode"] != 0:
            return False
        if not isinstance(item.get("stdout"), str) or not all(isinstance(a, str) for a in item["argv"]):
            return False
        at = _subcommand(item["argv"])
        order.append(item["argv"][at] if at is not None else None)
    if not {"init", "set", "validate", "export-report"} <= set(order) or order[-1] != "export-report":
        return False
    first_init = order.index("init")
    last_set = len(order) - 1 - order[::-1].index("set")
    if first_init > order.index("set"):
        return False
    if not any(order[i] == "validate" and commands[i]["stdout"].strip() == "ok"
               for i in range(last_set + 1, len(order))):
        return False
    return _replay_transcript(workspace, commands, config_path)


@criterion(description="the delivered tool run with no subcommand exits non-zero with a usage error, not a traceback")
def tool_requires_a_subcommand(workspace: Path) -> bool:
    work = Path(tempfile.mkdtemp(prefix="task-ctl-bare-"))
    try:
        work.chmod(0o755)
        cli = _extract_tool(workspace, work / "tool")
        if cli is None:
            return False
        result = _run(cli, [], work)
        return result is not None and result[0] != 0 and "Traceback" not in result[2]
    except OSError:
        return False
    finally:
        shutil.rmtree(work, ignore_errors=True)


@criterion(description="the delivered tool's validator accepts the delivered config.json and prints ok")
def config_passes_the_tool_validator(workspace: Path) -> bool:
    work = Path(tempfile.mkdtemp(prefix="task-ctl-validate-"))
    try:
        work.chmod(0o755)
        cli = _extract_tool(workspace, work / "tool")
        if cli is None:
            return False
        config = work / "config.json"
        config.write_bytes(_out(workspace, "config.json").read_bytes())
        config.chmod(0o644)
        result = _run(cli, ["validate", "--schema", str(work / "tool" / "schema.json"),
                            "--config", str(config)], work)
        return result is not None and result[0] == 0 and result[1].strip() == "ok"
    except OSError:
        return False
    finally:
        shutil.rmtree(work, ignore_errors=True)


@criterion(description="profile_dev.json equals the independently derived dev profile, value and type")
def profile_dev_matches_derived(workspace: Path) -> bool:
    return _same(_json(workspace, "profile_dev.json"), EXPECTED_PROFILES["dev"])


@criterion(description="profile_prod.json equals the independently derived prod profile, value and type")
def profile_prod_matches_derived(workspace: Path) -> bool:
    return _same(_json(workspace, "profile_prod.json"), EXPECTED_PROFILES["prod"])


@criterion(description="profile_delta_report.json gives all five signed profile-minus-main deltas for dev and prod")
def profile_delta_report_is_correct(workspace: Path) -> bool:
    report = _json(workspace, "profile_delta_report.json")
    if not isinstance(report, dict):
        return False
    for name in ("dev", "prod"):
        want = {k: EXPECTED_PROFILES[name][k] - EXPECTED_MAIN[k]
                for k in ("avg_bitrate_kbps", "max_bitrate_kbps", "vbv_buffer_kbits", "gop_size_frames", "qp")}
        if not _same(report.get(name), want):
            return False
    return True


@criterion(description="gop_plan.ini and vbv_plan.properties carry the derived cycle-span and reserve values")
def gop_and_vbv_plans_are_correct(workspace: Path) -> bool:
    parser = configparser.ConfigParser()
    try:
        parser.read_string(_text(workspace, "gop_plan.ini") or "")
        gop = parser["gop"]
        gop_ok = all(_int(gop.get(k)) == v for k, v in (
            ("gop_size_frames", EXPECTED_MAIN["gop_size_frames"]),
            ("min_keyint_frames", EXPECTED_MAIN["min_keyint_frames"]),
            ("keyint_seconds", EXPECTED_AUDIT["keyint_seconds"]),
            ("min_keyint_seconds", EXPECTED_AUDIT["min_keyint_seconds"])))
    except (configparser.Error, KeyError):
        return False
    vbv = _kv(workspace, "vbv_plan.properties")
    return gop_ok and all(_int(vbv.get(k)) == v for k, v in (
        ("vbv_buffer_kbits", EXPECTED_MAIN["vbv_buffer_kbits"]),
        ("max_bitrate_kbps", EXPECTED_MAIN["max_bitrate_kbps"]),
        ("vbv_seconds_milli", EXPECTED_AUDIT["vbv_seconds_milli"])))


@criterion(description="color_config.env and framerate_plan.kv carry the active band's ledger classes and cadence")
def color_and_framerate_plans_are_correct(workspace: Path) -> bool:
    color = _kv(workspace, "color_config.env")
    rate = _kv(workspace, "framerate_plan.kv")
    return (all(color.get(k) == EXPECTED_MAIN[k] for k in ("color_primaries", "color_transfer", "color_matrix"))
            and all(_int(rate.get(k)) == EXPECTED_MAIN[k] for k in ("fps_num", "fps_den", "lookahead_frames")))


@criterion(description="tiling_plan.toml parses and carries the derived columns, rows, tiles and helpers")
def tiling_plan_is_correct(workspace: Path) -> bool:
    try:
        plan = tomllib.loads(_text(workspace, "tiling_plan.toml") or "")
    except (tomllib.TOMLDecodeError, RecursionError):
        return False
    return all(_same(plan.get(k), EXPECTED_MAIN[k]) for k in ("tile_columns", "tile_rows", "tiles", "threads"))


@criterion(description="qp_curve.psv has the contract header and one row of the derived qp, band offset and average")
def qp_curve_is_correct(workspace: Path) -> bool:
    rows = [ln for ln in (_text(workspace, "qp_curve.psv") or "").splitlines() if ln.strip()]
    if len(rows) != 2 or rows[0].strip() != "qp|band_offset|avg_bitrate_kbps":
        return False
    cells = [_int(c) for c in rows[1].split("|")]
    return cells == [EXPECTED_MAIN["qp"], EXPECTED_AUDIT["band_offset"], EXPECTED_MAIN["avg_bitrate_kbps"]]


@criterion(description="bitrate_ladder.csv has one row each for main, dev and prod with the derived allocations")
def bitrate_ladder_is_correct(workspace: Path) -> bool:
    try:
        rows = list(csv.DictReader(io.StringIO(_text(workspace, "bitrate_ladder.csv") or "")))
    except csv.Error:
        return False
    ladder = {"main": EXPECTED_MAIN, **EXPECTED_PROFILES}
    labels = [r.get("profile") for r in rows]
    if any(not isinstance(p, str) for p in labels) or sorted(labels) != ["dev", "main", "prod"]:
        return False
    return all(_int(r.get(k)) == ladder[r["profile"]][k] for r in rows
               for k in ("avg_bitrate_kbps", "max_bitrate_kbps", "vbv_buffer_kbits"))


@criterion(description="ladder_solution.yaml holds the tier, the flat config and both profiles")
def ladder_solution_is_correct(workspace: Path) -> bool:
    doc = _yaml(workspace, "ladder_solution.yaml")
    if not isinstance(doc, dict) or not _same(doc.get("tier"), TARGET_TIER):
        return False
    profiles = doc.get("profiles")
    return (_same(doc.get("config"), EXPECTED_MAIN) and isinstance(profiles, dict)
            and _same(profiles.get("dev"), EXPECTED_PROFILES["dev"])
            and _same(profiles.get("prod"), EXPECTED_PROFILES["prod"]))


@criterion(description="rounding_audit.yaml records the half-even policy and the canonical granularity, ratio and efficiency")
def rounding_audit_is_correct(workspace: Path) -> bool:
    doc = _yaml(workspace, "rounding_audit.yaml")
    return isinstance(doc, dict) and doc.get("policy") == "round_half_even" and all(
        _same(doc.get(k), EXPECTED_AUDIT[k]) for k in ("granularity_kbps", "maxrate_ratio_permille", "eff_permille"))


@criterion(description="ladder_ordering.tsv lists main, dev and prod with their derived allocations in ascending order")
def ladder_ordering_is_correct(workspace: Path) -> bool:
    rows = [ln.split("\t") for ln in (_text(workspace, "ladder_ordering.tsv") or "").splitlines() if ln.strip()]
    if not rows or [c.strip() for c in rows[0]] != ["profile", "avg_bitrate_kbps", "max_bitrate_kbps", "rank"]:
        return False
    body = rows[1:]
    if len(body) != 3 or any(len(r) != 4 for r in body):
        return False
    ladder = {"main": EXPECTED_MAIN, **EXPECTED_PROFILES}
    if sorted(r[0].strip() for r in body) != ["dev", "main", "prod"]:
        return False
    avgs = [_int(r[1]) for r in body]
    return (all(_int(r[1]) == ladder[r[0].strip()]["avg_bitrate_kbps"]
                and _int(r[2]) == ladder[r[0].strip()]["max_bitrate_kbps"] for r in body)
            and avgs == sorted(avgs))


@criterion(description="selection_trace.kv records the base numbers, the active band, its height and the selection rule")
def selection_trace_is_correct(workspace: Path) -> bool:
    trace = _kv(workspace, "selection_trace.kv")
    return (all(_int(trace.get(k)) == v for k, v in BASE.items())
            and _int(trace.get("target_tier")) == TARGET_TIER
            and _int(trace.get("height")) == EXPECTED_MAIN["height"]
            and trace.get("rule", "").replace(" ", "") == "active_band=(max_records//13)%7")


@criterion(description="validation_report.json passes every check, lists the required artifacts and both profile trailers")
def validation_report_is_correct(workspace: Path) -> bool:
    report = _json(workspace, "validation_report.json")
    if not isinstance(report, dict) or report.get("ok") is not True:
        return False
    checks = report.get("checks")
    if not isinstance(checks, dict):
        return False
    profiles = checks.get("profiles")
    return (all(checks.get(k) is True for k in ("all_artifacts_present", "config_matches_policy", "config_scalar_flat"))
            and checks.get("command_failures") == [] and checks.get("required_artifacts") == ARTIFACTS
            and isinstance(profiles, dict) and set(profiles) == {"dev", "prod"}
            and all(isinstance(profiles[n], dict) and profiles[n].get("scalar_flat") is True
                    and profiles[n].get("trailer") == f"{TRAILER}:{n}" for n in ("dev", "prod")))


@criterion(description="summary.json lists the artifacts in order, both profiles and the whole input inventory")
def summary_is_correct(workspace: Path) -> bool:
    summary = _json(workspace, "summary.json")
    return (isinstance(summary, dict) and _same(summary.get("artifact_count"), len(ARTIFACTS))
            and summary.get("artifacts") == ARTIFACTS and summary.get("profiles") == ["dev", "prod"]
            and summary.get("format_tag") == "TASK" and summary.get("trailer") == TRAILER
            and _same(summary.get("target_tier"), TARGET_TIER) and summary.get("tool") == "task-ctl"
            and _same(summary.get("input_count"), len(INVENTORY)) and summary.get("inputs") == sorted(INVENTORY))


@criterion(description="reproducibility_manifest.json pins the base numbers, the config digest and the sorted spine keys")
def reproducibility_manifest_is_correct(workspace: Path) -> bool:
    manifest = _json(workspace, "reproducibility_manifest.json")
    return (isinstance(manifest, dict) and _same(manifest.get("base"), BASE)
            and manifest.get("config_sha256") == _sha256(workspace, "config.json")
            and manifest.get("spine_keys") == SPINE_KEYS)


@criterion(description="convergence_report.txt claims a reproduced run, and two fresh derive runs of the delivered tool agree byte for byte and carry the delivered config.json")
def convergence_report_is_correct(workspace: Path) -> bool:
    fields = {}
    for line in (_text(workspace, "convergence_report.txt") or "").splitlines():
        key, sep, value = line.partition(":")
        if sep:
            fields[key.strip()] = value.strip()
    runs = _int(fields.get("iterations"))
    if not (fields.get("config_sha256") == _sha256(workspace, "config.json")
            and fields.get("reproduced") == "true" and runs is not None and runs >= 2):
        return False
    # The claim is only paid when it is true: two fresh derive runs of the
    # delivered tool on the shipped corpus must agree byte for byte and carry
    # exactly the delivered config.json.
    delivered = _json(workspace, "config.json")
    work = Path(tempfile.mkdtemp(prefix="task-ctl-repeat-"))
    try:
        work.chmod(0o755)
        tool_dir = work / "tool"
        tool_dir.mkdir()
        data_dir = work / "data"
        data_dir.mkdir()
        out_dir = work / "out"
        out_dir.mkdir()
        cli = _extract_tool(workspace, tool_dir)
        if cli is None or not isinstance(delivered, dict):
            return False
        _write_corpus(data_dir, {}, reorder=False)
        if os.geteuid() == 0:
            os.chown(out_dir, *_nobody())
        outputs = []
        for n in (1, 2):
            path = out_dir / f"derive_{n}.json"
            result = _run(cli, ["derive", "--schema", str(tool_dir / "schema.json"),
                                "--out", str(path)], out_dir, data_dir)
            if result is None or result[0] != 0 or not path.is_file():
                return False
            outputs.append(path.read_bytes())
        if outputs[0] != outputs[1]:
            return False
        produced = json.loads(outputs[0].decode("utf-8"))
        return isinstance(produced, dict) and _same(produced.get("config"), delivered)
    except (OSError, ValueError, KeyError, lzma.LZMAError, tarfile.TarError, UnicodeDecodeError,
            RecursionError):
        return False
    finally:
        shutil.rmtree(work, ignore_errors=True)


@criterion(description="derivation_provenance.xml names shipped data files as field sources and lists the canonical config keys")
def derivation_provenance_is_correct(workspace: Path) -> bool:
    try:
        root = ET.fromstring(_text(workspace, "derivation_provenance.xml") or "")
    except ET.ParseError:
        return False
    sources = root.find("field_sources")
    keys = root.find("registry_keys")
    if root.tag != "derivation_provenance" or sources is None or keys is None:
        return False
    named = [(child.text or "").strip() for child in sources.findall("source")]
    listed = sorted((child.text or "").strip() for child in keys)
    return bool(named) and all(n in INVENTORY for n in named) and listed == SPINE_KEYS


@criterion(description="input_manifest.ndjson has one entry per inventory file with its exact size")
def input_manifest_is_correct(workspace: Path) -> bool:
    entries = {}
    for line in (_text(workspace, "input_manifest.ndjson") or "").splitlines():
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except (ValueError, RecursionError):
            return False
        if not isinstance(entry, dict) or not {"name", "format", "bytes", "rows"} <= set(entry):
            return False
        if not isinstance(entry["name"], str):
            return False
        entries[entry["name"]] = entry["bytes"]
    return _same(entries, INVENTORY)


@criterion(description="tool.zip holds cli.py and schema.json at its root, members sorted, every timestamp 1980-01-01 00:00:00")
def tool_archive_is_deterministic(workspace: Path) -> bool:
    try:
        with zipfile.ZipFile(_out(workspace, "tool.zip")) as archive:
            infos = archive.infolist()
    except (OSError, zipfile.BadZipFile, RuntimeError, ValueError):
        return False
    names = [i.filename for i in infos]
    return ({"cli.py", "schema.json"} <= set(names) and names == sorted(names)
            and all(i.date_time == (1980, 1, 1, 0, 0, 0) for i in infos))


@criterion(description="the delivered tool derives the exact flat config for held-back corpus c1")
def tool_derives_held_corpus_c1(workspace: Path) -> bool:
    return _held_config_ok(workspace, "c1")


@criterion(description="the delivered tool derives the exact flat config for held-back corpus c2")
def tool_derives_held_corpus_c2(workspace: Path) -> bool:
    return _held_config_ok(workspace, "c2")


@criterion(description="the delivered tool derives the exact dev and prod profiles for held-back corpus c1")
def tool_profiles_held_corpus_c1(workspace: Path) -> bool:
    return _held_profiles_ok(workspace, "c1")


@criterion(description="the delivered tool derives the exact dev and prod profiles for held-back corpus c2")
def tool_profiles_held_corpus_c2(workspace: Path) -> bool:
    return _held_profiles_ok(workspace, "c2")


@criterion(description="the delivered tool derives the exact flat config for held-back corpus c3 (exercises rounded minimum interval)")
def tool_derives_held_corpus_c3(workspace: Path) -> bool:
    return _held_config_ok(workspace, "c3")


@criterion(description="the delivered tool derives the exact dev and prod profiles for held-back corpus c3")
def tool_profiles_held_corpus_c3(workspace: Path) -> bool:
    return _held_profiles_ok(workspace, "c3")


@criterion(description="the delivered tool's validator rejects a nested configuration with a non-zero exit and no traceback")
def validator_rejects_nested_config(workspace: Path) -> bool:
    work = Path(tempfile.mkdtemp(prefix="task-ctl-nested-"))
    try:
        work.chmod(0o755)
        cli = _extract_tool(workspace, work / "tool")
        if cli is None:
            return False
        config = work / "nested.json"
        config.write_text(
            json.dumps({"profile": "TASK", "ladder": {"avg_bitrate_kbps": 2350}}),
            encoding="utf-8")
        config.chmod(0o644)
        result = _run(cli, ["validate", "--schema", str(work / "tool" / "schema.json"),
                            "--config", str(config)], work)
        return result is not None and result[0] != 0 and "Traceback" not in result[2]
    except OSError:
        return False
    finally:
        shutil.rmtree(work, ignore_errors=True)


@criterion(description="the delivered tool clamps the average allocation to the band ceiling before quantising")
def tool_clamps_average_to_band_ceiling(workspace: Path) -> bool:
    # Ceiling tightened below the pre-clamp average: a clamp-honouring tool emits exactly it.
    work = Path(tempfile.mkdtemp(prefix="task-ctl-clamp-"))
    try:
        work.chmod(0o755)
        tool_dir = work / "tool"
        tool_dir.mkdir()
        data_dir = work / "data"
        data_dir.mkdir()
        out_dir = work / "out"
        out_dir.mkdir()
        cli = _extract_tool(workspace, tool_dir)
        if cli is None:
            return False
        _write_corpus(data_dir, {"max_records": 460, "retry_limit": 6, "timeout_ms": 3284,
                                 "trailer": "harbor:cli-config:TASK:00000000013500bb"})
        ceiling = 1000
        maxp = data_dir / "max_kbps.properties"
        text = maxp.read_text(encoding="utf-8")
        if "tier.0.max_kbps=5200" not in text:
            return False
        maxp.write_text(text.replace("tier.0.max_kbps=5200", f"tier.0.max_kbps={ceiling}"),
                        encoding="utf-8")
        maxp.chmod(0o644)
        if os.geteuid() == 0:
            os.chown(out_dir, *_nobody())
        result_path = out_dir / "result.json"
        result = _run(cli, ["derive", "--schema", str(tool_dir / "schema.json"),
                            "--out", str(result_path)], out_dir, data_dir)
        if result is None or result[0] != 0:
            return False
        produced = json.loads(result_path.read_text(encoding="utf-8"))
        config = produced.get("config") if isinstance(produced, dict) else None
        return isinstance(config, dict) and _same(config.get("avg_bitrate_kbps"), ceiling)
    except (OSError, ValueError, KeyError, lzma.LZMAError, tarfile.TarError, UnicodeDecodeError,
            RecursionError):
        return False
    finally:
        shutil.rmtree(work, ignore_errors=True)


# --- negative checks (True when the cheat is present) -------------------------
@criterion(description="the delivered cli.py embeds the shipped corpus's derived answers")
def negative_hardcoded_answers(workspace: Path) -> bool:
    # Fires when answer numbers that only a derivation produces appear in the source.
    source = _tool_source(workspace)
    if source is None:
        return False
    markers = [str(EXPECTED_MAIN[k]) for k in ("max_bitrate_kbps", "vbv_buffer_kbits")]
    markers += [str(EXPECTED_PROFILES[n]["vbv_buffer_kbits"]) for n in ("dev", "prod")]
    return any(re.search(rf"(?<!\d){m}(?!\d)", source) for m in markers)


@criterion(description="config.json carries a nested value or a forbidden dynamic key")
def negative_nested_or_dynamic_config(workspace: Path) -> bool:
    # Fires only when the config parses and shows the cheat; a missing file is graded elsewhere.
    data = _json(workspace, "config.json")
    if not isinstance(data, dict):
        return False
    return any(isinstance(v, (dict, list)) for v in data.values()) or any(k in data for k in FORBIDDEN_KEYS)


@criterion(description="the delivered cli.py imports a network module or embeds a URL")
def negative_network_access_in_tool(workspace: Path) -> bool:
    # Fires on an actual import of a network module or a URL literal, not on prose.
    source = _tool_source(workspace)
    if source is None:
        return False
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError, RecursionError, MemoryError):
        return False
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if any(a.name.split(".")[0] in _NETWORK_MODULES for a in node.names):
                return True
        elif isinstance(node, ast.ImportFrom):
            if (node.module or "").split(".")[0] in _NETWORK_MODULES:
                return True
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            if re.search(r"\b[a-z][a-z0-9+.-]*://", node.value):
                return True
    return False


criteria.artifacts_exist(weight=1)
criteria.artifacts_within_size_limit(weight=1)
criteria.config_key_set_matches_spine(weight=3)
criteria.config_matches_derived_ladder(weight=5)
criteria.allocation_chain_is_consistent(weight=1)
criteria.qp_follows_integer_staircase(weight=1)
criteria.report_matches_contract(weight=1)
criteria.tool_requires_a_subcommand(weight=1)
criteria.config_passes_the_tool_validator(weight=1)
criteria.profile_dev_matches_derived(weight=5)
criteria.profile_prod_matches_derived(weight=5)
criteria.profile_delta_report_is_correct(weight=3)
criteria.gop_and_vbv_plans_are_correct(weight=1)
criteria.color_and_framerate_plans_are_correct(weight=1)
criteria.tiling_plan_is_correct(weight=1)
criteria.qp_curve_is_correct(weight=1)
criteria.bitrate_ladder_is_correct(weight=1)
criteria.ladder_solution_is_correct(weight=1)
criteria.rounding_audit_is_correct(weight=1)
criteria.ladder_ordering_is_correct(weight=1)
criteria.selection_trace_is_correct(weight=1)
criteria.validation_report_is_correct(weight=1)
criteria.summary_is_correct(weight=1)
criteria.reproducibility_manifest_is_correct(weight=1)
criteria.convergence_report_is_correct(weight=1)
criteria.derivation_provenance_is_correct(weight=1)
criteria.input_manifest_is_correct(weight=1)
criteria.tool_archive_is_deterministic(weight=1)
criteria.tool_derives_held_corpus_c1(weight=5)
criteria.tool_derives_held_corpus_c2(weight=5)
criteria.tool_derives_held_corpus_c3(weight=5)
criteria.tool_profiles_held_corpus_c1(weight=5)
criteria.tool_profiles_held_corpus_c2(weight=5)
criteria.tool_profiles_held_corpus_c3(weight=5)
criteria.validator_rejects_nested_config(weight=1)
criteria.tool_clamps_average_to_band_ceiling(weight=1)
criteria.negative_hardcoded_answers(weight=-5)
criteria.negative_nested_or_dynamic_config(weight=-3)
criteria.negative_network_access_in_tool(weight=-3)
