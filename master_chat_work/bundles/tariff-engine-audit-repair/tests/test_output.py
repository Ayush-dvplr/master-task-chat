"""Checks for the repaired tariff package delivered under /app/out."""

from __future__ import annotations

import ast
import base64
import csv
import io
import json
import os
import random
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import tomllib
import zipfile
import zlib
from datetime import date, timedelta
from fractions import Fraction
from bisect import bisect_right
from math import gcd
from pathlib import Path
from typing import Any

from rewardkit import criteria, criterion

H1_SEED = int("740213")
H3_SEED = int("518806")
H5_SEED = int("962457")
H7_SEED = int("307541")
APP_ROOT = Path(os.environ.get("APP_ROOT", "/app"))
OUT_DIR = APP_ROOT / "out"
ARTIFACTS = [
    "/app/out/patched-repo.zip",
    "/app/out/repair-report.json",
    "/app/out/module_core.json",
    "/app/out/module_parser.json",
    "/app/out/module_report.json",
    "/app/out/test_fixes.json",
    "/app/out/summary.json",
]
INPUT_FILES = ("meter_reads.jsonl", "accounts.csv", "billing_periods.csv", "rate_card.json")
CORRECTED = ["test_commitment_credit_base", "test_partial_period_standing_charge"]
CONTRACT_TEST_EDITS = (
    ('[("M1", "standing", 0, 14, "8.68")]', '[("M1", "standing", 0, 14, "9.30")]'),
    ('self.assertEqual(_money(invoice["credit"]), "0.99")', 'self.assertEqual(_money(invoice["credit"]), "0.00")'),
    ('self.assertEqual(_money(invoice["total"]), "47.75")', 'self.assertEqual(_money(invoice["total"]), "48.74")'),
)
REUSED_IDS = ("A0003", "A0010", "A0042")
_SETPRIV = ["setpriv", "--reuid=nobody", "--regid=nogroup", "--clear-groups"]

_SHIPPED_DATA: dict[str, str] = {
    'ci/accounts.csv': (
        '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'
    ),
    'ci/api_contract.md': (
        'eNqtW21v40aS/s5f0XA+jI2jNZLtSTb27AC+ZBbI3mYTTHJ7CYJApMSWxTVFatmUPdpg/vvVU1X9QknO3S1ugc1YZHd1db0+'
        'Vd38zPxY9vVqZWz7ULfWLLt26MvlkGU/rmtnVnVjDf07rOMr0634dzHwzMJsy+Vj+UDjWlO8Lrfb173ddkVuntf1cm36crAu'
        '29jB9qa3ZeVo3NDRf566emndxPzX2ra6QGVzUw/OVN3SDX3dPjj5/eH9/dffvjddj1/ZU+3qBfFFdDG2duVDb615roc10VGu'
        '8/gnvWndJMs++8x8L6xm2aX5kVYMnG+2XU+0Shd3teq7TbKf165fFqZsK7NzVgTy/X5Yd21mjBvoedlXpqkXfdnvTdc2+1vT'
        'dqa1w3PXP5plU9t2yPGo37VDvbFm07WPdr8tB5LRuuse8ZJoEdd9dbkt+2FvKru1bWXb5X5CDCtnk7+9//DDN9/9tYBeSiNy'
        'MvYfu7IxJNfiyfau7lp6DdZkA8v6tW51vinbekWCm/zd0aAJi4H2V9a9rUyx3W/77u92OUyGbtMUZln2fa3bdeXGgqJfIKfV'
        'i54WpqnucsvCKCIjmOIXe+XiyLmOzCFM0Au7xEJ/NL/8WqS7Xezqppp7azmvyqGcV3V/UagxYZm63e4GVrXzxklDaBddv+cV'
        'dJLor7fDrm/9TKYLg9ttSEOwgJImkwASHnrw15/7Qbx2pJHO/fMP3/2V7PKjTJedmsuNEULmrefkHW2fDEFs9tDIOnEHMUqy'
        '0WGd0y6e+5oMHnJkZl6Sy4VssiTTe27g0aSKYJ/dboCkRPD2I1xrqg5YtokYYVqb2jlYVj34pduOjJOeHFNM+APnvG4RCIDs'
        'rXnLhFsyonfFiITte3LsFf0fc1d17wYi52cLOyKRrqedE2HEkjmrn624IWEW5XLZkWe5ydI9FeCnWNQNMfIw39q+7ip9QfKj'
        'eDQnu67EA9gMVRZXp7V2eUm8DhY6dscq9K5hnst9nkhB4oJMizZC5pmY47mjuPVDIH4RTOhQhWmQiUr0KmQzIhnNpsZZCtOV'
        'u/OjhnU5UGDdEE9NiRAsUiJ6JRSqwybm3ozUFaxgTcs0FBloNDR0JJxC4upXXftEO6Cw4BBb31OM2LMfmKey2QUFpo5KxIkv'
        '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'
    ),
    'ci/billing_periods.csv': (
        'eNqVvUuuJUuOHdqvUdwBnDywP43NTEiA1JDUkCaQKFVDQH0enkrQ9GVcNHfjvsedjOhEBbJ4PWzbl1xcXPz7P/7jv/2ff/33'
        'r//973/////965/+9X9+/X///Pd//frHf/uXf/lf//4v/7T+P3//53/+t//793/9x3/6h7+mlPJXSWX8JZW/mL+W+fU/asv9'
        'q4zx3cdX'
        'XX9WmJdtU495/UvNX//pv/2X//iXv34t85a/0ndKsK7bpB3r9peavv7zf/0Pf8lfuefvWb9m/i4d5s37+N++Wv2e'
        '46t9J4J1f/n4Hkor31TPUIYzlPKVG3/z+ufH92wwp5eh/I/SxjJP7bvwV6XvpCOf/tdpjaWdsbD78dm+KX2V+T2yWOd0fzCX'
        '+6/rX9+/s/bvRuuf+G4Yec4vQ/nvy3rNObe1lF/83Qqsiz+JfX5T/8pzrSrMq79b2hr6Wf7cvI//DdOX5eNjwLwHy8/ru+sH'
        'fBdsxTxexnLWv7SvPL4Z2yW/rmjOLcne4jXRa3J0Fqf38b99jfld+Svnb54w55dfqvPCdf3EtWnWxGAaS3LPRVlDn/QlpwOL'
        'VIIlrel7tC/6LpjG8nZExXrtLpJjsX4oYVpK9Sed6rfMXPvO+nGzpMNuxutc0Pfar2kdDlj3t+0C67qNdbeUt/XUSWm5fPd+'
        'rN+WU0/cXPfQWvy1H4eaT3/GOdnLorA7burftCx4LZJY1/S+s9afa2fVsQ5cwVrW1/s253WL5Crjrm3fK9Ws5VmofK08Fzn6'
        '16hrff/02uFl3RNJRq0rWZu7TXIqa+rW//5dsGVr983bkK+3vOe7ns1h7q9y3ytrMEV27vfUr5Oz9msOaK1jlb3Iav52OnVa'
        'RpFHaOR9UVT277h1ga6P533zt+T+0IFXRW4u/M6W/Stu3Z/lXIitBO/h+myTVa3YWK26556yPFnr4u/YWc0czW6nXD/OLN++'
        'R9LdB6vgUsbhx2Zp5vWk8+2xdy2xLP79bXJXZz1v6+/5O+mXzVKW+6/rytFNO9azXM6X2X1+ZP76+qVrPTF/PT1uQtpLufYg'
        'dzlrhDu8m6U8t0W+Pl6XeT5XRC/u/dPkyTzT3b2VXKdnHYQ12HlZvx3NPRJ5AtdOTPuS6OZoznNJXBdnXr9wXdvrkWA1N/fs'
        'mc+1lvs4iK/CX+uywPp08t+Hmb7X43f/zum/yb3IyG9r9udwPYNjftW6zUfyh7JeY3kpeTmsMM/u18s6OPOMZRR3a9XlRyxX'
        'dd0pHS/bMHctPZivs9nPZhnNHUqe9VtdEHWyR3dfwtKbvVSG/27mNYv57MThv5s8xcXOfXxnbJYxg4+nj0k0C3rOxz7563fK'
        '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'
    ),
    'ci/build_config.json': (
        'eNplj80KwyAQhO95CvGc5q9pKX2VEIrVBT0YF90U2pB3ryYRCj05O98yOy4FY1x4qc0L+J0tcYwGCtJx4rVArN1MdTSkBnXy'
        'gK76GOTlviidRQ8hGDel/UDOg8qQjIVAwmJEw2Yx1jXtpTz0LYuuz6r5F9s7HpHWqVSTN9drn88E5wnUw4J9gg+Rkp8hojVx'
        '7ucp9fj525v03vZctV0OUYAwKZikgRQxjCmgWIsvUGdHgw=='
    ),
    'ci/failing_tests.log': (
        'eNrsvV+PJtlx3nnPT9FrLEzJEHMzTvwXoAsBK8MGjJVB8GZhGAI97N0deMjhzgwF69s7s+rNfJtgn9A8QJ9yAdG6eslSJasr'
        'KvJEnF888fzvH7753YcfPv7x+w//9t9++M//92/+wz/+X//573/zH/7uxx+++fDHf/np//v+D/zhV7//8Kc/fPvTTx9//OnD'
        '77798Zvv//njDx9+9eOH87/48cOv/vjhl+enf/p32x//5ZcffvXPv3j5T8f/4x//9NPHf9r3nT781ct/9cPH//eHjz/++O33'
        'f/hx+z9fv/zrj3/87rf/8uP2F9/y1x+2bfvw7//+P/6nv3jcwB83Xh/3/X//i4cx/jAufjbBHyfF4xR/nBaPM/xxNv3NOf4w'
        'L362wB8XxeMSf1zOH0c7/DjaZ785wvOBinwgPB9oFI/DM4J4+k/F84Fk+jA8G6jIBsKzgR7Z8A+//vU//vovnocnBBUJQXhC'
        'UJEQhCcE5SwSA0+HMU2HgafDoOnD8GQYRTIMPBlGcTwMPB1GcTwMPCFGkRADT4hhxePwfBhFPgw8H0aRDwPPhzHNB8bzgff5'
        'z8Z4RnBxQDCeEzyKFx3jScHTE4LxlOAiJRhPCS5SgvGU4CIlGE8JLlKC8ZTgIiUYTwkuaibBk0KKpBA8KaRICsGTQoqDQvCc'
        'kGlOCJ4TUuSE4DkhRU4InhNS5ITgOSFevJ0ETwopkkLwpJAsfjzFs0KnpZPiOaFFTiieE1rkhOI5oUXxpHhWaJEVimeFFlmh'
        'eFbotLdWPCe0OCcUTwktUkLxlNDinDA8I6w4JwzPCZu2E4ZnhBUZYXhGWJERhmeEFRlheEZYkRGGZ4QV54ThOWFFThieE1bk'
        'hOE5YUVOOJ4TXuSE4znhxTnheFZ41VA4nhZepIXjaeHTSyfHk8J1+jA8JbxICcdTwn36s+EJ4UVCOJ4QXiRE4AkRRUIEnhBR'
        'JETgCRHFMRF4PsS0mQg8G6I4JALPh5jmQ+D5ENOiKfBsiOKACDwfosiHwPMhinxIPB+yyIfE8yGnRVPi2ZBFNiSeDTnNhsSz'
        'IYtsSDwbcpoNiWdDTrMh8WzI6dmQeC5kkQuJ50LO7l5phzPh+Jbpz0Y4rKadpj/bwB9WFEqE02oqaDXhtJoKWk04raaCVhNO'
        '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'
        '0wPH06OQUg8cUI9CSj1wRD28GGQaOKMePs0InFAPr84IHFGPmTv18RU8Hwoh9cAR9fBpwYQD6lEA6oED6lEA6oED6hGFNGjg'
        'jHoEV8/DcyIKEoFj6lFg6oFj6lFg6oFj6lFIqQcOqkcBqgcOqkcU5wSOqkeBqgeOqkchpx44rB4zi+rjK3hSFKh64Kh6FGLq'
        'gcPqMRVTD5xUj4JUD5xUjywyAmfVo5BTD5xWj4JWM06ruaDVjNNqLraAM86reSqpZpxW85RWM06ruaDVjNNqLmg147SaC1rN'
        'OK3mglYzTqt5ZlV9fCXxhxX5gLNqLkTVjNNqLmg147SaC1rNOK3mglYzTqt5SqsZp9Vc0GrGaTUXtJpxWs1TVTXjrJorVs04'
        'q+Ypq2acVXMhq2acVnOxAZxxXs0Fr2acV3PBqxnn1Tzl1Yzzai54NeO8mgtezTiv5oJXM86rueDVjPNqvnj1ZzMMB9ZcAGvG'
        'gTUXa8AZR9ZcIGvGkTVPkTXjyJoLfTXj0JoLaM04tOYCWjMOrbmA1oxDay7WgDOOrZmnxwQOrbmA1oxDaxaa/mx4Pkhx38Q4'
        's+aCWTPOrLlQWDNOrbmg1oxTay6oNePUmgtqzTi15oJaM06teUqtGafWXOirGefWrNOUwKk167Sxxpk1F8yacWbNxQpwxqk1'
        'F9Jqxrk1FxvAGcfWXIirGafWPBVXM86suWDWjDNrLpg148yaC2bNOLPmglkzzqx5yqwZZ9ZcKKsZp9ZcKKsZ59ZccGvGuTXb'
        'tLXGoTUXumrGsTXb9HzAoTUXqmrGsTUX2JpxbM0FtmYcW3OBrRnH1uzTzhpn1jxl1owza3abPgzPhUJTzTiy5gJZM46seYqs'
        'GUfWHPv0YXguxLRWwnE1F1u/GafVXCiqGYfVPFVUM46quUDVjKNqjmku4KCap3pqxjE1x7ROwiE1F5CacUjNBaRmHFJzAakZ'
        'h9Q8hdSMQ2rOaZWEI2ouEDXjiJqzyAUcUnMBqRmH1FxAasYhNWeFIHBKzQWlFpxSyz47HARn1DJVVAtOqKVQVAvOqKVY+y04'
        'pZaCUgtOqWW69ltwRi0FoxacUUvBqAVn1FIoqgWn1FJQasEptRSUWnBKLQWlFpxSS0GpBafUUlBqwSm1FLu/BefUMrWqFpxS'
        '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'
        '2y/+7ov83y/Oh/3thz/7Xzr+h9AMO7/lr3/xqy/yf7/4zQ+//ebjf/vtN//9w1/9/vsff/rww8dvPv7hpw/f/Pa77z5899sf'
        'f/rrv/3Fhw///tvvPn74N+cP8eP/8Rc/6h//5d/8zYfvvv3Dxw8if/Ph2z8cjzh/6OPbPnz48eN3/8/22x9//PjDT//w///p'
        't9/91bd/+Ofvv/3m43/55U/f//Tb7375X//m+F/68fiP3/zpx5++//3HH/7pm+9+++3vf/lf//oXf//yXcf/wj/88MP3P/zt'
        'h1+KbkK//PC//d3Lx11/uTgsjIeFG4ZFacvxGhbmjZaHRfCwSMOwGG+sr2FR2cRXh0XxsGjHbIlt31/DMuT8uDgsjofFG4aF'
        '/Hh1+WtcyP0NAhN4YKJhYMbIjR7Hyxi+0fLAJB6Y7JgxvG92ZczxWXlxYAgvk6ljmWyxcTzK5H1jWx2WgYdldAyLbfaox4w2'
        'Wx4WvB6jjvVY7pvT3b1EfrmwvCDDv4yL4XGx9xkX+jQuv/n29x+//9NPj1/r63/54eP/+Objx999/N2Ho13/8OPiP3i80qWW'
        'la7k3RgS0earCyrCK13qWOmKb3qd236WVmvDMvBze7Q8t/dNHg37+XF1lTvwW8fR8tbRtyGP6y3bglaHBb91HB1vHWnIZvxI'
        'F91MVscFL3NHxzKX9tz2xzUK7b7l6v5j4HXusJYJ489ybND5eXFg8Dp59KyTeRuPeoyOgkyWv8rwOnlEy4zh81x5CUyOjXJx'
        'XGDR1vktHW/q93HS39eEOQLDqxOG8QthppZnv9+E3o6XGq2+42K8teTx9Y7rZ/zF410Id+xC9Og8Hj378XE5AmG8CeGOTQjv'
        '2/7oDcd+tu+Lw4K3INyxBRkum+QjLr5vvryiwlsQ7tiC+NjikS+am4/VYcEbEO7ZgORZRL02ILbF8uMFn0jhjhMpQtv+eI0d'
        'H2N1ugjeF8re8y123dS/zkAsDgveFUrHrjBso8dLLHjbV7/EBO8JZfSkwHnNB9P6UkzwjlJaci0+DvrrckvGOSu8ODB4Tykd'
        'e8qITR5xiaOnXP4aw3tK6dhTZm6aF248CgBffecoeE8p/vXO8Wf8xeNdobQUKgifs3SvJzfv543K6j95vC+U/Pon/6//ySve'
        'Qii11Ob4tsdVrI71klzFmwgdLVFsbkZXYHi9+lPxqUXtOLV4dhGPM+L4mLE6LHh3p9Lziiof1er5cfVEvOK9nXYfWkw5j5rF'
        'ccF7CPWmAyX73d3tW64eile8B9H42nWP5cc+3oFoRzJleWs/B63XkBhOpqwjmaKgja+heNtP2fTiwOD9i3XsX9LvuLzFLg7D'
        'uxfr2L28tJJ2rXygc5hrcWDw/sVa0qmjCKOrgeH1UgXDGxjTnqs4Lphrth5OGQ6nrCOcime2HGHJ1VWy4W2ldWwrVbZ4LBSS'
        '2HS1pNfwptKi56AQP7JFef0wveE9pWXTKVS/irH9CMzqfHG8q/SW84528pZrj4eu7ikdh5XeUgV3Hi9yTXAdzf6+ms873u37'
        'Vxncz/mTx/t179mv61Nw9RYY2PEGxFs2IHJumntt12X9ygfHK11vKexJuscmKHR9Z+h4revZc8iXHyVV+DZWXzsGXulGx0r3'
        'aAd3egquVmsVAq90g3oaMtiDnshY/xILvMyNlsqevNW8p8hndbseODuJlrNffKqsrtkvX54t+GVweM912bvd9iXrj3y8RI7o'
        'PvL9urpucWDwEjlaXgeTPK+Diddv3ky8SM6WQ0YeWzwyxsYpVlwcF7wcy9FzJi8e+XJ8XE4bEy/HUnr2lNe2iHPP4+pyLPFz'
        'P1ue+3a/xI6w6OKXGMF+nee3dMyWvF3LZP+iAonPIi3aBx6Xr0jr5/zBM/6L5ZZbme3pOnY0hjpWv4kED4w0Hdn2t5OeEO43'
        'Si39RknjmTAmp9nV4sAYHpiODJiPMuoRFx7bvjxfHA+LN5XOX8tQiXK5RptwI1jqaQSrtMltBJvLL7gIN4KllkawYzzV82/h'
        '0EuEN4fUsTk8PRji5sBfcvHm55tD3AmW6Gtz+HP+4PHmkFo2h2fjoW/YhBDeHFJLxi73RMrRs69eakq49zG19D4+W5AHAhmy'
        'jeXnNt6C9HTo/bMx1JfRx8WBwStdasnYze+BR/J921e3IAOvdMfec/N/3uaWm60+XwbhYaGeLFf4plPLoSHuaE1j9L6q97Fc'
        'oEi4ozW1dLQevsmF2GO52w/hzsnU0zlZ87kkauzLrcYJd06mls7JfOQL3btUY3X3gvsmU0vfZH6aYx2H/vJbetw1mXq6JpPc'
        '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'
        'dp9btvu73lpkSjnXwi4ODN7ut7RDPmKR477lt9XdC26HLD3tkI8WX+OZL8tHk3HnXWnpvGt0UzE7QrT82Mebyp7Ou5ybXCpx'
        'Xm+OKLj1rnBPsdjY4haLjbNmXhwYvK/klstg+SnfT1luwye4+660dN89p/kv7YtssbpOxt13paX7rue5NvH1lj9PXfLisOB1'
        'ck/vXb6dkkSXW4iL4FBMWhpY0UaPDb3KW6wetcQtkaWnJTLRNj5ZoLh8egy3RJaelsh8rud7sMr1zQtuiSwtLZFZzh2jr+yF'
        'Nl1ei+GtS09L5FeTt9fWxd/geMGZWEtLZHI/PUQfLq+6niEr3lNqx54yx73OmmP5IljB3Xelpftu8j0z7rleiIzbvIo2Xf5u'
        '/nZIDLd5lZ42r/tzb3Lm8qX8gru8SkuXV4/bjefcbL0aVOIer9LS45X53DjyeubL+rkxxWtkzZ7LR4SeVgmrw2L42JjtTVUv'
        'zwvL5WcL7ocsLf2QVe6G8niJfUnNyz/8+tf/+Ou/jAtOw+yd0jD6NC6/+fb3H7//00+PX+vrf/nh4//45uPH33383Qfd9g8/'
        'Lv6Dx1tCazn3dfTnci2n2l/2ha/+k8eR1nv1AH9nf/J4u93SxNv2jfP2XRmrb0EMb7etY7s9Yt8GX9s+4zyHFwcG77dbmquP'
        'Yfd6qXHuMlx9QYXbeEtLG++jWL1Gg8+wrH6R4Sbe0tLE+xxAvSCunstAFocFb+286wIQy2elu1wIjNt4S08b7xhPwzUbGy1/'
        'keG9YUsbb5M7YY6jxlZPo+Am3tLSxPvcZ/Do2DXWb8fFLbylpYW3PGdRJE8JyuKw4G2ld2wr4+nm6Xk2mIvDgjeVLZ3VXzSm'
        'jwnU4I1Wv8VwZ3Xp6az+icnqy2dffR8ceJkcXxHIz/mTx8vc4PY+3MuVVoGXuSE9XeuvsBwVbywPC17mhvYcXLjWqB5N4fps'
        'weuplq71HDc8OT7G6onrwIfiInrqrPii6+PEjovDgpOTyJ5y0VvzTl+0xv1sWBJvPnJvb1ybbxAYnJ0k9S6R1U5Tm8VhwVvC'
        'HC2R1glLXu+2Nl99tZV4P5nc1Idzt6fL8/rA4FfBaT0Hv64Vd8PXu9clXiNnxxr5nPV6HC7hy/U8usPF2PEtTe9fHmMstn66'
        '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'
        'W37cmthaWhPTyPuIobGfQ3qLA4M3MC29iVVOseprXylfdL748/OSuDmxvVdz4vc1L4nbC5v2lKD4c+ME7du+ugnBDYZNe5rh'
        'vRhJvF6l2HopneLFrjaVOuzXxCRtsdqV0wy/qrf96wnxr//BG95EGPWc3L62RFqcQ9yLw4K3EC0Ntc9G2+TZdC9n7LihtrU0'
        '1B5HwsS9m4DOG97FgcF7CGvqNHj13Pxlt0NPTm68Bfnqp/2z/uDxFqKln/Y5qThuVS4tPyBwjmEtOYbvmz9ObufNVp8Pjhe6'
        '3vK2XPOplj4+L+exjl/KesupEqXTLug1YXz9sifcUdtaOmoPltON7mEYuG+5evoa99S2lp7a514hsuel7vI1wrirtrV01Ra/'
        'e3b29TISxwtl71goi2374z0mup6S42bn1tLsnPV2QDs+Ll8ijJudW0uz86FPRj5OteLasOBm59bS7Px4c+33auctVyutcVdt'
        'i56udEcneQ3HHY0MLw8M3lW2dNUefDYs16jP8qYSd9W2lq7aQqfq/TUsuX5hBO6pbS09tfnpRnt83JdnC95QhvXsXC5hz9Fb'
        '8urOBbc6t5ZW50THq+u+gPHNVyutcbNza2l2fho234vVju5l+YsMtzu3lnbnLLch3bBtX32TjJudW0uz8yFx+9IM4RPDLA4M'
        '3r209NT+ZJjlaDCXaxRxT21r6an9ycjFUSYvbypxS21raaltfJfJRFsuDwvevbQ01B5+u2oevb4tP/TxC/6W7sBM9xwMj+W7'
        'un2HS+TjW1r2LrbF9Rbj9cuIfCc8MB2L5KOnvHbbH+f/6mVEjptpe0szbdnvpWpsyw99xz2bvaVnc+TGj0M/fNNYHRbDw9Kx'
        'FstPhl93OruYxXFxPC4dr5L9aCMf4MX35TWy407a3tJJ+3h1Bd/gJZaf+YmHpeVsEu/34mHKcS7tXhsY3EjbWxppC92n/tjP'
        'pUSLw8J4WDpeI4ts8uTHq9cQOW6j7S1ttCn9OcCf61dDOm6k7S2NtNk/2dv1BvmCNy8tjbSPdLlOF9rHNlb3+rgvsLf0BQ66'
        'qf7xcSymlI6bpHpLk9TgLR9Q//gYq4uxgZ/6oyk8vnCY6ubLswU/81ta19LO90jy+dmWBwa/Ghsdr8ZiPy9ebrOB1cUYbl7r'
        'Pc1rze4ZS/dT/LI4Lngx1tK71sf56rqmLfbVN2O4d6339K4l3/RxZZn7aZe6OC441W/pXfu2LhCOG6R6T4PU5zrK44W2ei2u'
        '4wap3tMg9TlhKbH+AgY3SPWWBqlD8t41NmScddniwOC9S0snzohbIBZj21dfweBOnN7SiZPG0+j5NHyU5YHBmxfOnuNJ476D'
        'We8s6LhDqrd0SLX9to8wPw0LFocFH7eQ0VOufxk9c26yunnB/VG9pT+qjW1ctui0vtUXvHmRluDFT9+bK1tiebbgVL+lPSpZ'
        'Pi0O6GVp8uLA4M1LS4PUk4LpoxpLXt/t4w6p3tIh9VPPqKQTJq+Ni+JFsra84j8VldfYGI9TlrQ4MPgdvza947/Qi75s7Fkc'
        'Frx7aWmPOvQTVLmvX2/huD2qt7RHpXPf2CNhZJyzfYvjgjcw2rKB4Vvqem4gWX1pibvWumrPyzHmeyXvar96xz1vvaXn7akG'
        't+fl2PJTH+8q1Zu6VrA82cty0YvibaW2hGLCT/hyql2XBwaHYi29iJ228dCGq2+6WhuOO+Z6S8fcc7rSniusV2+4MLx5sZYL'
        '3/cXrctDvPcGokrcMddbOubS/rI16dYjjcXOrI475vp7dcx9V86sjlveujVd286fGE6t7tdxw1xvaZgrcjt3Hx9ptXAFN8z1'
        'loa5uT9p4/FxNdVynGr53lsgIS9ObYvDgncfLW2M/2wXAi/fQe2OQy3vCLXObVSX63ecYonFYcGbj5YmxjHu3kP5XLW3OCz4'
        'me89RcR+67xON53VpqyOu396S/dPGnIj4HPGaPUlCm7/6S3tP8/ZL7q2g5/rw5YHBq/HomM9pvu9PeQ4YGL1bTDuy+pNfVn3'
        '26qFOL/o2vbP3zrixqz+Xo1Z39etI+7h6S09PIntvD15cNx949XFLu7i6S1dPE8nQrkC8xZ7JQMvdqNjsXu63z23GsRq8Txu'
        'FunZdmXONZBy9CPLLYpwu0hvaReZ8dy+vsuWq+e2Ey92s2Ox63bmyKtKW5ebeDpu4uktTTydblN129/geMGvhFuaeIo/Zadx'
        'Nu+Lw4K3Ly1NPCn53GTwuOF6AzkwbuPp2XT7uuz3jfBYLXNIHKFkR4Sise1xexGvvngM3C0yWrpFkse9tphiPwWoiwMz8MC0'
        'VJ360bFcu/KYl3eVsTMeGO7pHWVPU/UvKTr97EV97ILHRb5e1P+MP3jFf7E9K116+tVHbuGr30SGB6blRf2e2/54Fem+3CQ1'
        'cJPUaGmSSucygnttp5+q68WBCTwwLXsQusHW8XFf3oMkHpaWNqk0bt/Hc0h49QavIJhsHd/SU4GS+VSgrO5ACO/ZqWXPTnYP'
        'C2ms7wxxV+Fo6Sp81GDjkqDkcnP0wO1ro6V9rft98+ixca4OC95WtjSvJefncnvbN11dJRPevlDPfap6z9TTvt6HOwhvX6hj'
        '+xJ57+tmX651CNxWOFraCh+t5KXTZtv2xVK6GHjzMvaee9X4yhZartiKgTcvo+U6ouGn2+O9vmv11s4YePcyegLHzR+vsfPj'
        '6jIZd0ePlu7o5x7CS6kdutwoNXAf7mjpw30umbjmJvIk9YvDgjOx0XT663KAOgqAsfqKHzdHj5bm6KdeRe6hidVSr8DN0aOl'
        'ObrRlleNzFuu5i64N3qMpvaCepXI+1jPw3Bz9Ghpjj7E7lrsLfxrA7fhjpY23BKf+j0vbylxG+5oacN97rXNC+wPO+fyFwcG'
        'L8e6+j2L3juhc3WVjPs9R0+/53O6Ut9w0lLwS0uhnga28egqz0Utq0kl7isc0lVIzPf86/KuEvcVjpa+wiGn2ePrjWUu930M'
        '3Fc4pOti+0sZaXxOKC+OC35l2dJYeBCdSxAeV8njrAAWBwavklsaCw87gpFv2O7jzsIhPS2g/L5OpqM225dnDH5xKR0vLmM/'
        'L5FfT/59/agl7vgcLR2fj/fYNThmtNnqURjc7zla+j2fu/Ue2ZKbr54bw+2eo6Xds4/TG/VagzRWn/m42XP0NHs+3lx+QTG1'
        '9fIK3O05Wro9Z953/BFvcLjg80kt3Z59v7frmm/78mzBm/2Wbs/6JGL6oq5cHBa81e/p9nw6ostTsk+rr/hxt+fo6fZMLy4F'
        'b2YgFbitcPS0FZaXe5fHrSVvvjpjcGPhaGks/KoIv2y4fXm+4GVyT1thkufA+PFSWy7fw91vo6X77Wkc+YDI5+rQ1VfJuPtt'
        'tHS//fQqmU4MszYsuM1qtLRZHfxiVX8zseWzyY4f+849G0t+Okcu1yM5fg3jLbdcnBzsk/26vHrW0vFj363nVphrBFZlvawS'
        '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'
        'gyun+/7F9y+aLp8fkky8Fkv9OiT5M/7g8Woqmy5YtMuWcmy+uvdI/F4rO95rud/KxDNCi/eSDdyearS1p7qqXKJxLilbHJiB'
        'B6ZlPWV2T0mS6LltcXFgBA9MRwDMpPeKk3HuvlyeMYoHpuPtlsbp4XYNGK1/kdn/bO9sUmxZdizdf6N4zUooDDPJZCZrZC9z'
        'AjmD16iCgiI7j5x/ufZ2M48LJ6lYEAoCVvR253DvOXJ3aelnfXhYGOsxfRZZZIUleXJYJh6WST45qelHK4LT3ISS5tZXMT00'
        't96yw7LwsFDemtoIssW9VfzyjMgNDM5zE0qem8RN5Hbw1Rpjx+TA4PqlCSctdKf9wFKmh0XxsFAaq/T6ABV0FU0PDK5eGucC'
        '6/Xx8qcRYzM7MLh+aYPTuV/vuFyJP5sMIw3XL41yf1V70fMh+9o2zB8nW9JwCdP8d7L1/3/kcdKeUJL2ljx+NyMdGCo4aE8o'
        'QXvazuKDaizYJYcFL6iEsh08g66317eqZocFL6co+Yd9nLelX98zyw4LXk5x8g9fLs67HZzepcf5h0LJP5zteA/OWmb6Rwxv'
        'BwvrkVY/9MP00TwOpRRKKGXQR/wcm6787KK4clHKZrA8hyeePzzB6YfCST9sYUT/DkvLVy44/FCU8ma+tVjUfrw/snuOODxR'
        'KOGJS84Oq6107w/B2YlCyU68wtLO6xLqMjcsODlReiXdmVi7GvuG62zB2YlCyU4cVuRelOyW7lwoHS+Su1D6Fa+DgA3oQMve'
        'YO14g78r6yr++ZD1IukfMly/dMoW/yguZzTf0hM/rl/64MQUbFlp+f7egnNKpU9SA9adXr7hnginnAon5bTWs8gyrwogOy44'
        'slEokY2zH9v1sMrL3sTHgY1CCWz0dey9YziWXYrhwEahBDb2S9/vbYvxpdzZPy/jGV6L2S/2/VP/sng5Zb/Y9898SvCCyCgJ'
        'DhquHfdFT5xaJ4cF77JT4hZ7D9eOdxNkpfsFCw5blEGJfG96CNZttTKzC1Uc1iiUsEZZ4d5820QUz96ow2GNQglrjI7UOsOP'
        'bMiZ4JAzoYSc9VlknLDkH/PglDMZv1XuZx54vJwanPRqC4LvO2/Xll/n4uQloSQvXTVUlYNb9OzpxcTz9hRO7pLfK6TS85d8'
        'Jt73m5SzcZfDjwuA7Ff6/v45c+OgMvmpoLIf1vnDmVYyf3uqn/mY4J2/STkKbVL8/pj4TLfcFxx+JJTwoz7+MtzJXhjE4UdC'
        'CT8KLx/dLdkrMF/J2flzhnC8WHX5zRCf+ZfF682fSpb6WbnX8XLROyeEaOx1F8/XVziySziRXTUs2jYbyrObRDiySyiRXS1s'
        'J487+4pOXnJg8H61U9qCmYdueAdm9ECBJAcG13aUNLXwaLPj19bTAVHi+CDCFydP7UOGGdmJH8fcCSfmTovc/e7xDf3uhWvu'
        'Ram5r7iMfQs2VsQoOTC4MKTk3MXu0zE2XrXM9MDgwnJ1zr3B+mx2aLaCwTF5QonJe3sivsNyvTnZ1djC9csiPdLb5PRLyWj6'
        'RwxXL4tyJ138abWPF3IiOTC4emHFSu6J4Rzpx5OKYyWVEit5xULuJarZ0w3ftDY8LJS7bevAoFuVdPGiOFNSKZmSASq+X5cx'
        'vuF1MTwsjMOXwK7Ws/eQjZZSnCiplETJ1q9iTB6b157+GZt4YCanLfK2THBPX99SHF6olPDCAEneYVFLt0zQhtfIjXKr7mlY'
        '9hpHaclhwWtkSqJku4oxtWerLvsCRHGipFISJSO73I3kcb062UUyTpRUSqKkj2AV7kFldiNZcZ6kUvIkZz+Scs70O2fFaZJK'
        'SZNs1Q/RxWus1ecuFitOLdRfauFnnnjBy1ypnBw23fPf/EVJFbzMFUp7kmYxXnwf1LaePmpUnPKplJTPGC82fzZYJbvQxTmf'
        'Ssn5vLTgXvnu+RcSinM+VUib9MMP5zPb/kpxzqdycj6vr9iD/JL0sOAtekrO5xUW2civFd+z5LDg6oOS89m12K3Wr5/p9leK'
        'gz71p4I+f5YqxFGdyonqFImm1NtmyUtL9hRQxWWhNs78cNR6zV8QwgGqSglQvZLCRqrE4nZ2E0XxvS1l3NuS2s5CndSav7mF'
        'k22Vkmwbrsg7vbRp6Wwoxdm2qqSycNvv6kg/AlacbKtKurlV7ZheZgOHVXFZqM7pRbpXhJbGPDc3LDjZVinJtv6y690z3JWu'
        '1nGCqvZf263PPPD46IOSgPrRfNdDiSSHBZcfnVJ+jBhD7bC09LDg4oMSS3ulh21BZF56elhw6UGJpW1tFN+gTcnfg8e5tErJ'
        'pb3k+dRDdJTsPXicS6uUXNpLB55jnhUvTm5YDNceRrlO50XudQezYtlzE5x/qpT809bms7XVekxzkwOD18jGWCOPdgwiYj0o'
        'u+FoeI1slDWyHD8Vz7cfUhwXrMZYI4+Xi/we/9aaHRa8RDZKV9thoSNv89RRZrZ2waG4SgnFtX7GjNry3xcciquDFFgiehDS'
        'K3sqjyNxlRKJ+9HM/hsueHEkrlIicdcodR1JObNXJQauXEYnJYSOnfTjd/r7gmuXwahdlp+Lk6X5xh04QlopEdJjHZub6+fK'
        'bsAMvI88GPvItk5jLPgC2Up/4iXypNxhsWcRbxbJVi44fVrn71m25nvb4fxppeRPR1N/jt3g17iiSw4MPnmZrGfZz6HpTH9f'
        '8JblnJxzl7MEs750R/LPYcGrMUrE8vAwSd8tGMvW+jgwVl04w7I9B7vkF8k4bVadMbdcCUXbae/nhwVvwFBCUbtGM+zdgAmH'
        '7uSo4LMwSpBgWNvtBkz0KzW7MYajBJUSJdg9bHHepdhVlaWHBZf6lChBu9R9O3SBmr3Jh/PqlJJX19rLjuKmC7T8/v7Cs/5i'
        'zPrNpbSNfYjf6W8MPnihRAnKnMV2a2yuotmtMRwmqJQwwSXHsTB+juw7VZwmqOvXa/gzDzwuQShpgOtpOk4N/8HUsPQKd7eu'
        'P8IYlnlmWibpXpC9Kh4WpXQv0nPW3abHeCs5MB0PDKMEsXoWjFovrWaHZeBhoTwgvnKKbHzmVfO29Pdl4oGhPI+QcRJMaxae'
        'OcmBcTwwTtkSXuHxdQfmkiCeHZiFB4ayVz8/vDFdA0mTGxgcCtgpoYAtbu1393HmH0l0HAvYKbGAox1j3HEp/uwMg0MBOyUU'
        'MAaN5+7+yjbZ062OYwE7JRZwSKn3Cd7109M/Y7i0bJTTrT6e6VZr6UOUjoMBOyUYcMyYm2xzKpHssODSslHyUnqsFN/lWPrS'
        'd8dpjb055yVxv+1DuqXf3feGy8pGOX95OVKdE7zstwVHcHZKBOdVgG1Xl2+4u+84grNTIjhjL88OULCmvy24pKQEcF4fsWGH'
        'nG3ZnTEcv9kp8ZtuxdfZxW/pbwsuKKWzNyzjd/bSBU567JSkR/O4unsvXcx0MlHHSY+dkvToIxbxtvHhzFYuOPeuc3Lv5mlX'
        'Xj97eljwWoySezd6cTk6X9PDgtdiqpwlstx7ltf3LD8seC1GiSOM3CJP+yV7RonDCDsljLCFlf79urTVSs+eUeIwwk4JI/yr'
        'NVXX7LDgyoUSRhgz/TN0qTPdv7XjOMLOiSPssfjyvifq31Ak41MXZZy6zB6Llbth2bIbljglslNSImN7b1djM51A3HFIZO/C'
        'bUJtVjz7I4YjJjslYlLkZXZ4Gx/O/FVxHDLZKSGTH1YtZOTfiOGQyU4Jmbz+2kfstyoBOUoODK5eKHGGNk7L8vqZn/Zx7UKJ'
        'MwxA2877a+UvwXRcvHRO1zAt846LS/4qH86Z7JScSXnmlOLpXm7d8DmlNU629OxnfGzpbwteJFNSJpu187r0kZ9dcMxkp8RM'
        'jsccfFxiP1tT4pjJTomZFHscXNvyYtnbfDhoslOCJrv+5a4iW7wYLl6M1LV97e0kzTeEwXmGnZJnGM4J28I1jo/Tr1xxomGn'
        'JBpKGMHtZrJ7/qhy4F3+Qbk4tj5c69f86QvOmuycrEm3AzIOLZO+0oezJjsla1JUo7V/o4zrl+6O/dHEteO4yf5TcZM/ysS1'
        'D1yDjElu4upxipccFrxRPygb9R++RIH6MMv+EuEoz/5TUZ4/60uEwzg7JYxzXoXQ3uDqRbIvG3EUZ6dEcfrDGbLXfVByWHAN'
        'MTk1RCtzi7uh+asPE9cQ03736fP36XEYZ6eEcUo/lgai8e7khsXxesor6fvSP6zWpX/IcEpqp6SkTnt8jFb+0BCnpHZKSmrk'
        'lCmPp2T69oPjFZl38sRvlr+7jfNrOyW/1uTkfdN8AeN4R9cp+R6xLfR4sNb0uOANYWdsCIvXIvqN01zH9YtT7tRfgdHxwArS'
        'v2Q48blTEp+XP7dBK/+UDic+d0ri86VfTM+hds+ebC1cvyxKZ8l1wnLJypktK3Hec6fkPc9RvJ1Th1Wzx4047rmv38WHzzzw'
        'eJ1LiWtuaueIJLbj0tkcOK+5L+fU69oOv7Zmt1Fw2nOnpD038TDter8vsuKMNDUwVmH5cf0RUvnRTn+re3ZYFA8LZZ9eelnP'
        '/CQ/LobHxUj7jtuaoAWgo2UHZuCBGaTeBCbHm6D37LhMPC6cBpGxjHfXycGxTQ6L42GhbAfPefwhm9Qyst8XHCpslFDhS7RY'
        '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'
        'GU41XpRU425nEiyz9PT3BVeWlEzj4EvbWS6WbGGJM43XZAUd2G24s2b+fB6n5y5Keq6t44kQpyvZcn/isnKyTlD63GsTI3+C'
        'gkONFyXU2CzgOds3LL8Yw1UlJ9K41bI20rjWdODkcly+eCVtw2wI+Ot3duLH2bmLkp07aswZt9y37DoZJ+cuUnJuf27vv+M6'
        'EifnLkpyrmg/i6zSZlnpbwxeKlMiWvuINcndhxHNDgveTvbFmV+qHGE5susxHNC6KAGtq5322PVzZut9HM+6KPGsYbMj8ymT'
        '07PLwsvkRbmotPQAD+QSlulO4Tg5d1GSc7sUvfOLvG6+k8OCl8mU4NxW18n7sfqdPt7H0bmLEp3b4nJ1LypdL09LDwyuXyjh'
        'ubKszPqNp6sLb/WvyemuP/ep9xWW9AyDt/qXs9rs9qciS55ZXv8JVFrGH2FU/CPWLd5HLBpLsX/7qn+D//jHf/79FYfX3zD+'
        'Cv0qLVTHP//2Ctm//9vf/8f//sf/+b//df2d/7X1av/z7/8r/qf++a9z/cvf/h+pzYW6'
    ),
    'ci/lint_report.json': (
        'eNrtnUtv20YUhff5FYRWLRCk855hd0XRXbsJ4GZRFwZNjVICEimQVAojyH8vpUWzIVHKVTnnqNwYMClZH4b3nvuYq/HnN1m2'
        '6Ztmv/k+2xxf9lXdZ/qd2rw9X6+67hS74c5vw29Z9vnyc7h+aLanfTy/oy/aare7vPpyZ3j/+br8+0LZbC8v/FFI6b6+rouf'
        'Ylv1L+dbVb1rvt45xK4rPl7e88vw+VX9Mdud6rKvmjpr2uwQ+z+abbZtyq5vh5uby/u+vL0BoBbySsCfhz+WDYuX7ZsB8xsp'
        'zHdSiG/vmukn4YQaZ4pt27SjUA/1Nu6Gv7jNPg2fUzwPn3m3PFJqdy3Pr8X+FLOqy051d3ruyrY69jel+iCcmrCkP4u2PjvS'
        'GNf7eFmnsxPWxSFmu7Y5ZM2pj23Wlc1x5UvDpwCVgoMprVrg87yXXtgrn9lDXcfy/Gv7kj1u4r6Lj5us2J2N/HHTxv7U1o+b'
        'mxF+EEqq6z3xh/KMOJhWVmTHtulj2Q/rd4iH5wGz2Q1Xy30Vh+Sn3Bddd0NabN1Y+e6JTwNqsAbTvJXnWh60mKCpYsJKuyyt'
        'k6/Q44f61A141eHYtP0KswQMdNhc+Va+5fgMereUEjB14rsyvZYJOeVYaZelTZa0QMFYdAG2gMJiwSprAh6AvauVaqVahgqt'
        'r2WpgjU/LVA0X2FYYIDaBivfv+Nz6Ek1JWDqrH9lei1T2mrEQWaNjirL4adNFuwdXbBa+Yj53j09HYqqfnpCm3Bewf5LsOUE'
        '7koqRE9QCBnBNXhAwfZ/gZ3elzSq9MBN8d0pKoXvaBLfAY1DaNMv15Eu3Ge4Bg4qnBtO3zaQvk1Ehag4lkZxmEmh5MfyZEHU'
        'qAg6ZFl0yGH7jOMxRMeZXThI//GoVbfH9hfP4y9EqIEmBQrI5eEKdzs4EDkkAiNSF4QIjEmV0ygxMylF4npH2Ih+BUuFWEXT'
        'gEpBI0ujqDAZ2QgdykiKwC5RpeQxQQltgpLuQUMMRzFhQcYQBSt94PNkhHywVbNUNP6ieQKehg54bHQoskg61CZp5sck+OST'
        'RJuLKZs2zhpbxzHT2ciL5ZKjRBrCEmeipc4uRjHhhkFnUy4dC2eCwXtx4mN75kIBSrZDtUKPK4Oe4cEGRJeAhMpRXSDnWC3E'
        'RFTApXUgzd5xNkWRMYF03+ay4dc+GlX5qMgARBm8QTTObDmqSWkJ19ZxCDoJJnAtIiFTahk4fFsRdiyVQo2NSpE8deAWq9K0'
        'a5i6wlKGBAmtWlaOxOY83maNQAy/WjAsFKAnaOAmzcp2M7bkzgCbwmmFt1iaQjnwkg9N2LjQHtYzAuFq5hT9lRFMzLkSCTuy'
        'wUQGkxlAs8GmCEYhljxGMWQJRnOMprEM+hFuexkDLDoWmA12Us14SEHE2LQ6Fm0XW9Bzwyfg8NRvNiiS/E1AI8w9T6AlPYrw'
        'GqaEec0EZuJ/VTQfi8BDPK6HBGTdHpn6BBVuwO/p3iNpevWWcIcvT4ECi470jCouPUfkVoLEREeGtUClSEGXNwpRKJUi8RZN'
        'wmlYvNrSeLVlDEPK4QZ2FajYULtAgkOStCKRJA3cotI0cqkdYJqhoRsYRlE2dDX0mpIkbMZQPnvElrlxLBppAolx5pjtfUvT'
        'nbQGdAURo7SF3ru2gSSPtQHU5gLZ4wXwiBwQykmSvWkFujmN2Ih1mkTdnMWt0p1jWUTKAQkXKKlzDrn0NPtsXgIKqGdpc3qF'
        'K6CeZftqBBTVWWg2NHxOTJpegIIAnh8ETcUDTSMpaOCnC70TECg77MGCekzSxmEbLy/+59P8l/eNCTQ8gZkATd2onsCygOaG'
        'XTxPQPt7gU5ZOk9g5hyYaY/HvgoKcPEk4uIpTNVOflzyfC6Ah6hJPMCScDqIcmSKLsd0DSUYEwQF13WdAtWUy2uRXUkhFgeA'
        'p6pOkXoa0kDpPAHRPHNAqOTH6c7ngsx4xs5hhVg/yaIwWpI8aUuzog7UJh3HkzYCOfUylNWCIdHz0XM9EasaYynNIGekto7E'
        'KEDG+OfTgUbQ5HP8U9tfgsQQnaBZQFATJCKl7K85y+JKJL1/51kW1OPOrDiaEOkopxpGvhEAlCA5xA6hBw3lnqbD5Vl2yrzi'
        'CDWepJHkocsxT7m1E6Cbc4EyFw4kYzDBAMbHAL1RH5aWyuHn72++vPkLBeJWDg=='
    ),
    'ci/meter_reads.jsonl': (
        'eNqsvcuuZkmSnTfXUwRirCLs4hdzzfoBNOkXEBpkERDQoqBm90Ag9O7yXXUO0fGvL7GNkaxhVmbs+Ldvdzdbti7/7ee//PWf'
        '/tP/8X/+p5//24+f/xi2h8fP//XHz3/6j//x//63//Kvzz/9B1/rPP/s//rrv/71X55/8r9b1MjnH/2nf/p/n38QFusvln/x'
        '8fzD/+ff/um//Ov/+a/P/xMe/9//8t9+ecYpSxvyjFH78xkzXZ4x/mL74xk+hzzj5Mwpz/BVH8/wc/QZ8RfPj2fk+XyEz+/X'
        '8u8fYTY+H2FWBo+w8/kz/PMR68zhWx6R+fmmbNaA1Yj58Yiyoc+4ryD1TdnnM7wqYTVcfsb+fESV+V76UVl+LvjOQYtRH484'
        'JY/w46Xf7fz7m//3j1jH4FeEfzxiyHrnsTlLFmON+HxRboNeVMqLkgWf5X50wYd/bj/bUbDg9vmm3ORNzbkWrfeU9d6n89lG'
        'yA73XFX6M1wW3L4W7fO7XZ/frbypYXd/6wY/53P3ZR46RPxza7gs+Fr3jHN5RKSchfft0SM+z6kx9Si8P0IWw8rlV6y/n2af'
        'R+HnrxgD1sINjqkpZ4ibw1qk7IzUT+pklh7of/9P//2LGkk7I+L1Rd1H3O9WfsU+n4/wnPRFyRHyX/7tn//58yH7vpXjusNN'
        'Lg0btBry2Q45CkfME7IanrL7IpzuVzmn9F46FV/v4OOb0ldVi36FbHBZjPuH6WL43EMO26LLNT5PwrX0q90rdL3TXG6+SDql'
        'Ph8hN0bG0OP8x49/sLPqx+ebWqPoTclpO3XB7+FtejGd6XJOGT3DQo5beVd3MVyPwnnknNpB16t8U75li3uNSr01Qo7bCMMT'
        '/XM9tGSrPHPr/Xr2kdVYePdtKT3lerU9ZTHukg8tqPY89IzPHe66/2Jv26YX7DQpPRd9ulJQlXy7Z3sOWHGXguprT77dTB6y'
        'A+8GrD31GJFN7uNE5xm19GckVNC3LJKP6oTRoR6v58i5tecyuDek2smF98bngqc84lYJq3Qxcks7k7k6Fyxsv8oaGxoB2eK2'
        'zuhUOwMO9ZOldUJFynpjtSOl5zJd7xquO3xveUR6daqdOHpx1FkHvqkhjcCZkw7DzwZ2ay3y9AH6pvbSn2F4/X3+jKW95f2i'
        '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'
        'sL/2GL+TQ1cvsRjxLpTutfRayk5hqw6BWQEQqj5ruhoWnXUvvvM3xty6odED/dbnkDijYaYf19xbTfjHn8MP7fzufwIQpRrt'
        'jPJb/UFUn3dvuoIpVYjuZWS24lqUaX1imz66NhTLt9dswTj0Y9y6Ewhq91zScUKdDgf16AC3ClQQnyDV30060Rl1ByS2nHsO'
        'w9/QiT15NmBHs6Bjum+0Q2REKd6s5bxUglrYINqVqXs7UC+irzmYeWtRRoE+U+u0TnUdgkXkgdozlCifWLWp7VlNWX6/KVg7'
        'TD0PEWMhsnF1uafNAgZxKj6UZKUgc3KddM8H2TVhte+62reWzEI+x9fXvZ7G7VW+dBEkv7mPmJ017B9+Hz84ECFuyOZQIdKe'
        'LeUn8P/2JgK/TA3vb9dybujQsPD9sKF8z40BOioLO5t4j0k6JFXXWOsW1DCxetzusPub6nGZrZEhGeXO45RLmLaZTtta1dsf'
        '99uaep3/qVQYvWbWW9Aa0ApVQiEaqWRJDCjXEesAhfeAqmRsTXKfmI8su1Lw/D0MJYAAKprjFyL1bThpQBA6BZG8PxfZGATN'
        'znHgXFxHr1rWjfjriv/kA1LQElHPRDutPOx7M1BKJCwAMZNktx4qSPO4fSA5C12VmaPFB9CP4bczAI5ve16lJmv9pnZSclI7'
        '3kFhahNyMBxKBi10I8o78Eqdqa/H07ABan4Uaj5bvDZCzJ8BNH6Frrqfnm5E9U51z0Jyuxx1u+yW2wWkeo9Wj6KkNTKkrJXw'
        'AA/V2bT/25J8YhO9w5p8osvYp7UhrEXoQXU6xLY1lG3n4xi4Cyt1qbxbvIkMqKySyp4leACv2ZvmwqR1x4Hupk9SkDwdzbI6'
        'CXxoHbSG4eBNa3YVEcQnruWbisdVxYP9k7+2/bcl9zo/p3/o2johbyNgeKHRJE9IcmulBYFcawPUoq0+a1Wgt+WYEyj2StIe'
        '2YKz62ruPPlJlFShGlaknSnVCVYQaxLtbGodjYJibZj19nvyr+dPh/em8mt1UM1BwWKfZKjfRjD4g8tZCPy8MrJ6qn/xlren'
        'pUMa8DcWBRgPmRdbIYwl7D1e+FYiYD1CIxh6RN4dVPfZWbDeD6FBjIzV0tCpZCR8GkgBfz5W0B+8ztxqdbElmkkvPArl/VYC'
        'QT48cKigjybBImHL33dO908siNyr0rX16K0gdHJ4SzYciKlECIVn8lvo3brHrwCgb1XI1irkdB7aAGBiLAjC6EeP6kGohthd'
        'YEM5pdR0NkiOV2nbAzCBQ6odJD3eQcFr3lbYwRCrAaqzpSDQ1+LcBwX2pEuJjHtg8fzekd3SYhps9123+9jKNIIXVtYg1r9q'
        'x2221BzgHN4roDy3X+aa39vj6KRdKl9k/+lcBF23XhjpnaLTxqTkQIB3maI5aCACiwFavZsmUZpKfG3P03kxNuCiRk2opIaG'
        'YCCKeDT8z35vJFBjploekhML7O2Lsiflpn4OXJVPkcAJPhtMFabSOUfAbrzvyzJqQ/s9j3Lfc/8MkL+8aPGusjm3QGvIede+'
        'P4Iwh4WZoJwscYgns0iwn9gk91cpDTU4i+t9wHZWbRCMaMjNR3vxhnrRRum2RA76oJDC2emRamnffS8DBX8pFvrgslonCPpI'
        'RcaGEkQHIQOJkqORtjdrAAfC1HtyeA8wXhVn+cR9wsZEuZjGZJ/1iha5FXcAIMXkof1E3r5GHwJQeZIWM0yfKMzBg2wYHTzf'
        'tgsQvqow5AGevX+Kc98K2DQoJdg2rsNV1KbH+b25FzStU6u1idh3TcNWvcstXyD40FTFERy1d97NFE+fVLTNUGvnqo4WE7rW'
        'RxkEFgEsz7NlbtGDcAbArU054Ldc+aL7W/Y+C4b0c8LPofLbUTx59vchfaRR6Hafu6MUCEhQ9QWqcaV3DYYgaZ+hDdkeG44R'
        'dUxF9OxME7KAFpImUkkTszXA030Jio8yZJ5zzDslYUBo2W2L7OcAUX2iDgCbH587AJt10UcFOkzXND31HoQbskKmtPhjW6sH'
        '0DnFOZPqEBX4Wp3V2l4NLUTG3qBL1/TUD4L3DQEBO/CwDRL+Urju4AiM7x8DotfmcuCxH1mBR7CdouMcDZpUzFLeY0+oZSp6'
        'yPMRj35DvquxercqdEC1nZmUaaQ65UD+kTJE4bDdH+zC72WhVjvDozNOncBgmWVwL031ZNXuvH3qbXlSYOGbSlfHs7VojEqK'
        'qmc2Be3x0St8rg5VBOYINT7ojfeMm+xwK4u2PklanaG7q4Wvxnqdbe+c4FwzlTB69nIEVCX5zH9hQq+5h8PQeKIB6ABOuC8f'
        '1ehTa/TVqdhcV3C7kn6MpbERG1cy6jzRzjKJAW5byUSDCzblECu4ZC9KedZlhpGRkGwCAx4qqwFSUpm5+IweXndBczkgUqzf'
        'XDbSyas+cqVvSzjxAeVsZS6A5GgGeQlD33Dv5fkB0uehamldGMotIfcamPAgCG+VEYL/qJ2p90wpGiUqBq1M5A3/qInfsAkO'
        'i4BpwAXThEhf1Yq/OCppwhfjCfeSCxxjdGSEfoAn6SAhvQewWHQOXuCiKNSJ6oOXgEwjXeo6rkPh7ZY/cZuMhLR7hSmv1QqI'
        'hNCWfPBc0AOoUfi0Iqz+eIRQ+oMvmtvW1hLdW7ZtG9rN5DSQn7jSrY3TKRroWzcKKzgaXZzR+j1K0Q8PsxIscsIo9aoeB1Vb'
        'jT+1Ahs0TaGaphY0Aa7Xh5O4fi5h0yQ8/RPPVwWdZWryoUens0ywrs2dQLDYOkyInR1bmVGG3Ia56lTJ/qyWagqS0cyLRgk6'
        '16ndUsICvT4+G5JvsgrFiWzvlOgGW/D5EeX8/kxJoNGtTHZHHAJYsDNjgtpP1ia292zBPlT1cKtniCz7WH1+b/R3R4Gi++MV'
        'H2bnN+OoClDQmdPYvNq0gFwH/BOtOBJw2ebHSfnOWt2d5S6oHu6/bkHfp9mm99LIFlvJgLM6oCo8pcgS7l6lfNaL6UlSjP03'
        'gkfzrdrxuQ7sj9WSMw4wDVJfPsgNv/0xxEvV1v0xM6hE1KQk8/SEHK6tRCJ2VMtJqP3xY2WB2vboSbi85XYGqc59UACPv1SB'
        'YtWzKOrc9s8WHLQ6pnIgpKxqEr1OuG3Hho5MbaMZp0X519d7f+TH32YuqgZCo76qHtSrtn3DTNXUBXmslfmr46/yaaTMksJ2'
        '83K3XmM0vR6Zu54fsuvzxVmg76i8/UC+DsSVyf74YMqsGpd0nbFmUJSYLsGRsKob6gFwiUHJ5woxH/hyN3qMeLqYARIXLc5n'
        'i2RgsM34bNy+8WlS08pO66coCAk5AO0d6mgoO51aLQD5kDbBRV2qaBrWqdVi66Lvz1UDrMhKJ6r+U7lALARap276+M2QdqzA'
        'KHM/BVm11bPbm0yB+isXBHh88tp/ezV2K/hp6gwvn5oTrMc6tJ2Ih/L32fNt3AsC6n45BH4PbtwdErTSgszHL3fK73WtzFNv'
        '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'
    ),
    'ci/package_manifest.json': (
        'eNo1y7EKwjAUheG9T1EyS6DVSdDNwUVBwUUkpOmtXhqSeJMUivjuJg2O/3c4n6qumZNqlE9g25oFSTgMbJV5AvJoTeaWb3hT'
        'lOAdkcALN4dXWfe7NW/aMms52xiyelKFfOg1dsIaPScPFGFhFzuNSkiHSe9Jkt0Ol+vxfFp+KbuIuhdoJosK/F8JTA/EUjyq'
        'b/UDyig19A=='
    ),
    'ci/rate_card.json': (
        'eNqtlEtrg0AUhff+CnFth7lz59ldSwPtoi30sSoliJE0EEwwZlFC/ntHmphkcXUiLgTvOXjQzzN3F8Vxkm+rqijz3+Q2Tiaf'
        'b0naiOtlVm68svODHx9fnyc3d+3slU2dlbNFOZ/mP1k1L7wFlun0aOdVMVvU0yqrG4szLk7WalY00V8HwUsfANwm6YWAkBzm'
        '7/bRelFUl4/u2jtvb9fTeuVtwXl6rrdvIUBha+zT7hRNpYA1Jjil3C6XRIxGOMUcvzU6C/3Hft+NXQCTiuaOPdwlH4wZFIUZ'
        'QQQDUuTP4ijHwGys68H87ilDN2WUTNCQVSdkgdyclzv2CrjB2CXZS2d1MDAgDwkYKcbgroQN4C56uDvmaO66m7vUYjBlpGtp'
        'XDAeR+8QxFF2CPTtkKeXh75yK8GMuqrdV+O0dNtglFMunQkA0dM2DQyHtg0lqOGrlJN8tLLBfJCOkTjKoRZGUZij5tpHfyfD'
        'rlQ='
    ),
    'ci/regression_cases.jsonl': (
        'eNrMvUuPLMuRrTfXr7jgWDsQ5mb+0qxbEiANdDXQUBAaBEkBBPi4YrMlCI3+74rIijo8u2yZ53KPCuHOGifZ+8uKtPCHrWVm'
        '//6bv/z2z3/4zX/3n37z+z/+63/5t7//4V/2fZff/Lf/6Te//d3v/vpvf/n7+dF///nf/ssf/vbHv/7++E///pt//ftv//b6'
        'MO2p/Nj1h+zn/+IPf/n9r/9jKr/5j/P/70+//cv5n/+n//V/+R9//PP5v/vdX//85z/+/c9/+ACYbLW/oH/601//n9/+5Xev'
        'b7Rv++vf/PMf/v6Hv/3r8V/+93//+L/PD//z+Z32jy/69z/+33/4l//zb3/984XOP/b8Q/qvPvz7X8+PfvMf/8fxn/72h9/+'
        '/vrXzv/zX/74+1/+xh/xnw7Av//t//vTA7DzP/5f//bbv/z9j38/P8n78bcjSLoBySxEb0Cah5xP7gqR3x+P8++//dPrh8ub'
        'vf7R3/3bv/79r3/+w9/+5Xd/+u0f/3x9tOff/Md/8+8owtATSOMIS9eP81OEpR+p/RRh/9sRYMkHWL5CaS6+0ii+9uzi6/WR'
        'pDMSfo40/PA++f7ZvT4JHh36XfXdywke3fFyCvVyJt16mn94Onw5bfrlVPxyqgtpRSG9f305U0fvjeKXk4RI+QppAURvQCoL'
        'sXVI6l8gzYIVIMsVHT6KVTcJVwD05WwpjPXnMP6f//P/8EPACnAsAeKiWPbN8jCMLQjj44eQazWeCmPDYWzudzEYxl+X/5TR'
        'j284jElIchANILoO+Qi7nyE4wopumnGEZdusRhGWwZfLb08xCS2UldljUtnMbzJatyLDCMtBhH0eoGYjLOMIy+53yfDH/7qG'
        'iSX062ccYiylAkqwwLRwm0w22CcL+HZl/PMbWmDsDNWvP7+QR4y6NR3++CXeJeXHT+fbX44Yr2PP8dFzR4wKHl39jtPZuTaD'
        'N0dKP9/j6SNGjR9e+6H79JtT8ZtTXUxXH9PpWg1/WpsLenMqfnNIioij5ICi65S0AwoOManHNl9xkEmtgzBr4Pu17zoCoAW6'
        '5y3pfJi1MMzOs/78At1wmDX30zR4BPgaZqqGAqDhMCMpsjuKBhRdpyii4DBLqW8SHDRTqpuEYdbB9+tvV7OOVjPqpCkq16r/'
        '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'
        'YjuAujfGk8W80yG2Hgo9xixDjlL3xkTdkw0P5cDq3nAyzxiUt7UhvWpgdY+GVO+mwRC9AWksxDiIMLVPjS5XuQFxFoQRQOo+'
        'RAAkGnUTT398j7oJ7ur/KWd/fb3rv33lHIyj3tfv6td3il9S01Ulnt/Vr39iNiNkedju699Dd/VIv9WXP9/90zIFFrk3I99g'
        '/L6pa8DQfYY7r0UM4xjC/B0jYJR9hhPTI0a9wWgko+0ywLkmR0af024YGcgtVAAGXPSfOwbt85S/KHks9SNn5IvUOt0zZGYL'
        'kPUbXv6L/3YA/n1IS4xr7U3JNyiZ8ZO9KXqDojTFdikowD8MwZDxWiMSDRN9fxasZnSt86OFoHIYqqL9VblGiznPOsdyW17M'
        'GS/m7H4aHI3sgpoK+v3zf/H1/QwBEwUDiN6A+HpDFLTSjxq8oecUBr0O+OX0Wy9OcGilHAm8oMvRZLrEdGaDEGHOWCqzf2J9'
        'lSpepep+W9gV6L06cJUqXqUkxJ3STQOI7kO8FT2CGAehJkT06HKVfYiPtYog9QakspC2CwG1HdEw7byMq5kTPJ5+Pgs2D/Rz'
        'fk1DBFWX18kvg1aqs0tmtnXYVKUYy/e94fve3C9DDryFL1eG73sW0lmI7kOEhtgXL9es6/TPWRy+NMR1BrRjlCdNHZIMRXt+'
        'LDTMZ+oa8xAsMpn+nMryzVDwzVDcr1u4sXRwLyz4ZmAhro1FA4juQ5ycEkKMgwjzl1gEKfsQ11sUQuo+xJl1TOM5kTlIh+5x'
        'ssuAX64+eVOXiuZkl6v5LrynaywJbNTzX/8eviGr+10qFVGK6wAV35AspBImqjdE9yFuGYcQ24UUlIIUjkeyK0oSjEd6fxSs'
        'Y3QIbE9me9hANQCpcwn19aWmpta6vJAbXsjN/TJckDJeyA0vZBIi3EJueCGTEN8VH0FsF4LKWaHlpPejBqamn4+ChdzBt/sc'
        'O60oaqtSXoCh19i7tUPWxArQd9Zxx+u4ux+Gy4zOaDrSm5JvUFxhHmX0vym6T3Gv1znM6D8HAkWBbtdnwTIb4Pt9tAL8lHg3'
        '07bkKr2tLbMxcx4uj+8daeBlNtxPM6i0LYPb5cCrjIW442sNILoP8dWoCGK7EEXjeyP/bLPQO2X1LKzjdSxA/Jb0YGVWGxpu'
        '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'
        'enCj+/dRe/6yY326OI2yDKH8lxW5PAvWp1mKV0JDij6gVECJlvQvAz0OrShx9UYFemtNb0Zz5XK6G52CYEeZjt6aZk6KvKy3'
        'Vqy3VqdR1kTttqDcWrHcSkNc28YaQHQf4gZZWCJU4/Q3rWfb3mCIocd8K7V+T8U/5seznyIxP9Yjrdf5V5nte3S5PqhiqbU6'
        '7bAKdTMx0CJcsdRKQwoTJVGx1EpDQPJGYAbrV/IWmMN6HLxT0RPIb1Y6po5aV490Xf+FQ2xSTCvXc1oaYlgGrU7XqzjIO1Oe'
        'kYp1UJbir9jwLIaFUJpSf6XScYy4wVNFX+++oFbRNW2jcnf6VTn7Iya1TMtpq87qHKHa8HNzV2ONUv43S2NhnGKNsjotqSpV'
        '7NLRVVDFIiULcaWS3QKI7kOclhBCjIMIE98My5wq1ilZiG/qE0HqA0jxkI0brTzRXip60PfVyxn54bkcBrne3381xJQue1j4'
        'Wk9axReUSH73TmIRsTpVrNqD4tKKVUSaUrm1A8uINKXTFHtAySu9kGqY5H2e5iJbfEVv9H1b8Yq22pQtHl7P6rU5CodyiYey'
        'otqwv26mXruerWieerMuV0Y7uq/L/UpamD28OpsHKA22xnW5n/9C1o/SWOqpTrioZF0u1C0rlnpYSjZKt6xY6qEphaYYR6Ea'
        'G4SQ8gDiS4wDSN2HiLCQ9puPazLz9naMKJXzjLCOdN6KvmB7M86w1ENQg3KZBjrVNovl5I4Hk3Rq3SjMrbgwt7qqydoSk88H'
        'C5IqrsulIYVRXiouy2UhzpQeQmwXArqJCN654aJcRKEaLo+AUfcZ7odvAaPtMzLL6LsM8ItYDxsL9su4BbLAPqeccHJC366/'
        'WS5p+arr/NdhdheZWHs4O6WxYZWsWDmuTj6sXEUubhBWsXRMUxrVIKxi7ZilwDZkgRSa8zGiqqpeJ+cPIIXW+2jqDBZB4dQk'
        'HWgTfXvXPxbFpL+6Et4MOKxeVqf4VRy7nKnG4RWrlzRFASVoKaWHBk15z4+igdCArNjeLOPMSY+cl51CbRLurBtOlYZVxea0'
        'uMZWPqK1uWFZkaZwUfgN64o0pfE38pPu9NItNlc29KzlbpgBafErSprqSFiu9+Hf67txDb5wnE3FxfUo4IbFxeYkuSZUTj00'
        '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'
    ),
    'ci/vouchers.csv': (
        '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'
        'TJ9QmaZIctXlPHpGb+xYGKPchdvH/0bGxhQ='
    ),
    'repo/README.md': (
        'eNqFUj1PwzAQ3f0rTmJgaVMkNiSGDkiIoUXQhak2zrU+lPgi+xLov+fshsJGButkv7v3cbkCcYkOB2PsubCQnGAGCQg9CiZI'
        '6NoMfAAH79R1FI+QxggUhcGPWbhXEMWJyWNujAH9nt92j9vN83r3eJ+Th+EkgeMtLPuZDlaDk7ASXrVOnDE7ZSsVtJTQC6cT'
        'BO6U1lYN+6qh+cgcO7sA67znMUpufJ7swthZ137ARNyer8HFFmwxs/cutbXZNlCYPPd9eR2SmlBrEeHpdbsxLfuxxyjwSRK0'
        'H+yPLQsdZakjyzV+eRyEOM4P6vrB+fCTAihhIjxPxojpeFKY1qoPhPRwv9n6oMAyWMEmi1Yl4Qu84hYqlYsVRU21/fZm2boT'
        '9BwlNLCe84DPwBlN7VGsV4FjX4VemHSvlGoCJNWr5o00YV340Ll4nf+8Gq9zqPh70ZUXyBhJQH+QQqYp3f2374IvcN1s9lX8'
        'Ms/9y8l8A9974jo='
    ),
    'repo/pyproject.toml': (
        'eNotjLEOwjAMRHd/ReS9kaATQ/kI1qpDlLpgKEmw3UoV4t9pBMvpdHr3+iL5TtEGSOFJrnNoQXiaEFYS5ZzqdPStPyGMpFG4'
        '2H+9BCN1i/HMtrknGYkTCqM6Tpb3WDNHUo8g9FpYSJuy2e13PnetP7TVWSiNlCLvrs71WFlSUxwAest59kq2lNp0gBLiI1yp'
        'GVl2+o1YXSoRP/AF7x9DUQ=='
    ),
    'repo/src/tariff/__init__.py': (
        'eNpVjLkKQjEQRft8xTD1I4VWCpYWNgo+tBEJ0UxkIItMRsG/N26Fzb1w7oKIO+XE+gD1wjEClQsXmoN4pQaZlASEfGjARWuX'
        'e+UzNYuIJkrNYIWuVRQ4v+104xTcrzb0bQkkxuyX23G1WcMCcGKndobGOOdTcq6jA35jHAD/H17k84FH8wR+8zlU'
    ),
    'repo/src/tariff/__main__.py': (
        'eNpVjrFuwzAMRHd9BaHJBtogXQ14CJoOXTok3YKAUGuqJWBRBqUY9d9XUrqUG++Oj2etfY4hOJlgZiEgyboNsGz5Owo8BshO'
        '2Xs4Ht4PeHw9WWsNhyVqhrQlY7zGADulpvwZHzeeJ2RZI39SegAlmUiNMRN5CI6lc/q1jm9RqB8MlCl7grESd9W6PA1XYF/l'
        'FThBTQLNiZrSLhZlyd2d3P1/WOnpsr/2fd+iSvmmAvtSoDARxQVChHEEi1jrINp7DXVcfpy3lCm8/HDuWtmC+QUynV+n'
    ),
    'repo/src/tariff/core.py': (
        'eNp1VMtu2zAQvPsrFjzJgeIm7S2p8wk9pEfDsGlpZRORSJWkAhhF/r27S1GSi0QXm+Q+ZmYfSqlXHY09l9B75+mvs6BtDQFj'
        'bLFDG6FxHuIFIWpvmgbQno3FjVJqtVrV2AB54SEa9KH4M2gbTbyWIOf10wroI9PffWsiaOjRG1dDtgNdeReChO9bbZPbZiVu'
        'rxgHbwMUfAl26E7oSxisiaGUpGuBhu/or+JIYXQEjxWadwzJcpMRyC971bCF3V6OTesowBYe0snNWSScsUR26JC9BATlDaRC'
        '3D6OzPirdE8h+Hmnhv4QndpPb9Hx28TWNGJtAvxyFgHbgNAZu5CNn+/hcT1FIBcO8pKwzlknNhvd92jropigOw4h5uUIiw3V'
        'fn0TdQmEiE8Yf/LLbZ6TR/023WTRRqhJVylVAjR2BVr05+uhpV4JRYeRoc08udijhqPvbkrwV4m5eoLRTb0ZW9NRpZiKbpgX'
        '3WTOSmpNF6k7ZvRKd26wMb/AnWD8mMm4TzuLS/9pWzPunWQPJKiE2Y+EqTNsTZMklDNjti+pyyN15KHW1+VIjPZQXbQ/UxEa'
        'mo/sJrNIreqouen6x8M9OUPnbLxspmZOwn0tV0a0EOxhodUCVXlT71m0RHdilpCqPcm4cIZvhO8jqyB7o5Cyl3DSAbMIles6'
        'E3mjzBqkEYciDKfoom7JymNtIncxHdOA01ow9t2ZCsfFcDxy3OOR+5c3h/AmsSpnw9D1ssNmUdlCVxUzepbDDESipYxAY9Qa'
        '2hrOVlR+XiO6umD4z+N2nWTYNA2UWEjvsnh7wc5X3Eyix3qZj7bOJu0dGkbmAy/bRaLFfsn2nuLWhZjejZVJb4c03yV8Txky'
        'puQwgbyfxB3txgb6QvzVP9Hg6T0='
    ),
    'repo/src/tariff/parser.py': (
        'eNp1VcmO3DYQvesrCjpJiCDkPHAfcvAxTuABfBkMethiacxYImWSmnYjyL+niouWXvqiVvHVY61PZVn+iR4tWBQSJmGd0u8g'
        'tIyGbhDOqV51wiujoTcW/HcEL6zqe0D9rjS2ZVkWapyM9fCPM7rorRlBCo9ejQjphN+L4uvnP57/+vIMB6gKoF85ioFIR5TH'
        'n7PQXvlL2cSTWf/Q5qyPI4eXjUqLzqsP3FvN7J2SeJzQKiOzVc7TwIHjkVMha10UhcQejh5/+epDDDPWTwFr0c9Wg/M2mVv6'
        'q6Zq8cjB7bwo76/RkWsSIkIJGQrCUR1Bad8Ale2L0Qjn7xjBobjKwaxnJ04DtkVgjK14p5jP4uLAmTHUkP4hdSQ7hg454Cwa'
        'wgR7iIsYA41XUmHEO0EtIDJ2wA+0FzBkttArHCSckIpPbp5jYeo2Jxaeql94Y/yUh6IBcV7oDmMtGqhOxgwN9IMRvk6l2RSV'
        'HWNU9rIe6nk8URgHrk91W/c6APFXh5OHb3z02VpjH5NTqInyE/z+GJbeIzQ1l4c+zoiruKZrd//mk9jYeN7yfA+h8hy4iX2U'
        'qvOO3qmoA9dIom1zCYMbpfnyGl55gQbaGUYzS+toRj1bXLUpHWdjfEDmiqyH/OsMzZiecU3UnOkWDq+lPlAm7Ftv6sDRi2mi'
        'Oar+3VGVfHZUsnxKi0FUL4vxtW72aNF1ZtZ+j87GG3Rc0x02mm6QUlwIxyrRsn4oZ1gXhK82rox5ra89F+F42uxpwC8nN7dZ'
        'cT5u/K7QK/i/ejs2oYpZEqIQVWelpTk3FPkl9Yi2w9Ji8sYeIB7vRYaO4dOBPYLQVozcbBjb6ZisWX6SClNWHEATJ5KeUe/c'
        'OrDPPE1p5sJ8UmNog1AmG18Xl4rVnLJ2SXje3iLn2xuMYnJQpY6mu2ogLuWDPcgvt6iB9OJNnfLkCxJfii0TkhImykx1UsPA'
        'ShaBHMxefJbQl+VZIt8slENS1AM9fFUvGxbVNfVrXZwfeOEPD1s3I9tANOS53O4MrRN5LOqRVjPi13HJzduv6OJ+7xu3IHEg'
        'Qg6M951Cjm14xLT/Ju5JmCAPZWR5Id4lvbg7j4ivvqu34f2W6xZ4mppj5do/Irz6+F6Vj0F3i8aUrZCyundnvYPm+ciqxtB6'
        'E7i7ol6n574OXmlhvHmRweYWuyrh9UTd5aWcI5T+7BF7kcl5NZuIi/8BUbXl8w=='
    ),
    'repo/src/tariff/report.py': (
        'eNqdV0tv4zYQvvtXEDxRWK2a7akIoFsv7WFbbHszDIWWaIeNRLoiZccw8t87MyT1itMuyotFzoMz37xozvkv5mx1rZh0TnX7'
        '9sqkaVivTKN6bY7sYHvmnxXzsteHA1PmqI0qOOcb3Z1s71ntzunzL2fN5tDbjjXSK687xSIF94Fykv651ftE+B22m0Ap0llt'
        'e5UDY+9Uv9lsGnVgVW8vTqBs9rhhsC7aPzN7UoYOc2bUpQXDSs5zsLG2Ddhe8sEfPv/EM/CNPYNbrQrCuHrlh96w7e1FXQvn'
        'e30S2SMTZ9kOioHPnGfpmDAAtpwFqjYMzCm0V50T2duoMi1kBwbkA3CKn3XtvykJeIpgRLZLXrVWNgKwkVWj++hZb61nJQEz'
        'kQIFlDggBWQK+qnoUAiS+oHxTnnVh8MCw9GCG7irvHr14h0yQTEJoeZbcGbmQAA+aZd1bQfjXQF+8WwCE7IFpDHIBYZSOwsq'
        'OulB8LIFKa/PqvKW7zKmD2x9yFTrFPtqjRoVBou2SZ5u5bs8iBIRdO3gTvEflyIFWDEpmuDsCfLaNt/j7V63kFPHKkqsnY7H'
        '26WNaNRtkRLcQe14/vghPoEORi7FwOJ/EULqO5FTKw3IEAN971YMte067Ttl0J4DpF/UNjufKw0A1bLH8GI6FZixs3TrwboK'
        '6ZRs35Nrse4oQ/MY5zxhmdNdqTpiCBt5deKiTWMviTFGgYADyzr5Ghm2D7vEM+G6mVI0kQg9zMUo9gU2jlIwJGOnjRhJ+VJs'
        '4QdeLVD352BNVqC57BP7krOHLHqyH3TbVDo0WrcueOil3wBGps6qh+4bEonZA3t6SpxPT7Er053YjqMy1th6wLBRRx6bxAfA'
        'AgCrlkMicKU6edVAkbzil7Zm1mbqFiaDPlzFfc1BxeDkUa1KCtixppL2qXCglWLlIsOyuOkgVffITrq3IISlRZviqLyghvyQ'
        'AdRB7u9BGq/9le+mnqaa+zaRK7NZIC/AF9TAd7VShQtSRTttIMamVgKYcia08Xkooiyj+BgoijXX3tp21jT+h/8zbxIKcbvG'
        'QV5IKCUaMG53o+8pscB9B1NWNSJFcN3Sxjpx2yg04YBdBeiYTaHFOL7bpvIILWdixok8swLXXjrMk4fiYTMflwjJZNhLOMOT'
        'OJoA/heobVaWyY8VpsQHikERVOyCRFYU0JKgTAW+LQplVH+8VkQQJJm/T6ycfM2WcSDzP5XMDZ1AcYhfF8JHJuMRjf2PbrkT'
        'uLv3UBMply0wzkRMgbEPLoQAJGR8fPcgIbPKYBXmJrZlsiuZhRbkJJzdFXaFPJ0QPty8Z0moLBEZ2dyw99bLFpoQ+K6haGg7'
        'WqS8bxWphraCupJBKa8W02kqyZjmybbV1E2F9ZgyZj0rSTmQb+OAXg2OYhq5EKU4jxejYM7xdn8WL2tjxUM+A1PwffVqiKgB'
        'eQRwNcwJTaBHWJfUJLySfIvjcOz0BRYdJmPZym7fSHw9wEP47suLprvGGbgYgjeeYgH3pU9EbLwEzqfNWxyL4U+GSCNsNg4/'
        'nnP4lP/1j9++MnxjzIYeCdALpRm6kxuV5qChgd/yx5y6SwWOuvLPfoA0/gdKcANf'
    ),
    'repo/tests/test_visible.py': (
        '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'
    ),
}
_DATA_CACHE: list[Path] = []
_MEMO: dict[str, Any] = {}
_MEMO_LOCKS: dict[str, Any] = {}
_MEMO_GUARD = threading.Lock()


# ---------------------------------------------------------------- plumbing

def _open_tree(root: Path) -> Path:
    """Make a tree the checks built readable by the unprivileged runner."""
    for path in [root, *root.rglob("*")]:
        path.chmod(0o755 if path.is_dir() else 0o644)
    return root


def _scratch(prefix: str) -> Path:
    path = Path(tempfile.mkdtemp(prefix=prefix))
    path.chmod(0o755)
    return path


def _data_dir() -> Path:
    """The agent's /app/ci and /app/repo, rebuilt here: the verifier container never has them."""
    if not _DATA_CACHE:
        root = _scratch("shipped-data-")
        for rel, blob in _SHIPPED_DATA.items():
            target = root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(zlib.decompress(base64.b64decode(blob)))
        _DATA_CACHE.append(_open_tree(root))
    return _DATA_CACHE[0]


def _root_only_tests_present() -> bool:
    try:
        status = Path("/tests").stat()
    except FileNotFoundError:
        return False
    return status.st_uid == 0 and (status.st_mode & 0o077) == 0


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


def _untrusted_command(command: list[str]) -> list[str]:
    if os.name != "posix" and _root_only_tests_present():
        raise RuntimeError("verifier isolation requires POSIX uid/gid dropping")
    if os.name == "posix" and os.geteuid() != 0 and _root_only_tests_present():
        raise RuntimeError("verifier must run as root to isolate submitted code from /tests")
    if os.name == "posix" and os.geteuid() == 0:
        for argument in command:
            _grant_read(argument)
        return [*_SETPRIV, *command]
    return command


def _artifact(name: str) -> Path:
    return OUT_DIR / name


def _load_json(name: str) -> Any:
    return json.loads(_artifact(name).read_text(encoding="utf-8"))


def _memo(key: str, build) -> Any:
    """Compute once per verifier run; a failure is remembered and raised again.

    rewardkit runs checks on several threads, so each key has its own lock: the
    first caller builds (one child process per corpus) and the others wait for
    that one result instead of starting their own copy of the same child.
    """
    if key not in _MEMO:
        with _MEMO_GUARD:
            lock = _MEMO_LOCKS.setdefault(key, threading.RLock())
        with lock:
            if key not in _MEMO:
                try:
                    _MEMO[key] = (True, build())
                except Exception as error:  # remembered so each dependent check fails alike
                    _MEMO[key] = (False, error)
    ok, value = _MEMO[key]
    if not ok:
        raise value
    return value


def _extract_archive() -> Path:
    archive = _artifact("patched-repo.zip")
    assert archive.is_file(), "patched-repo.zip missing"
    dest = _scratch("repo-patch-check-")
    with zipfile.ZipFile(archive) as zf:
        for info in zf.infolist():
            rel = Path(info.filename)
            assert not rel.is_absolute() and ".." not in rel.parts, "unsafe archive member"
            assert not info.filename.endswith("/"), "directory entries are not needed"
            target = dest / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(zf.read(info))
    return _open_tree(dest)


def _repo() -> Path:
    return _memo("repo", _extract_archive)


def _env(repo: Path | None) -> dict[str, str]:
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "PYTHONDONTWRITEBYTECODE": "1", "LC_ALL": "C.UTF-8"}
    if repo is not None:
        env["PYTHONPATH"] = str(repo / "src")
    return env


def _kill_group(process: subprocess.Popen) -> None:
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        return  # the group has already exited


def _group_run(command: list[str], env: dict[str, str], cwd: Path, timeout: float) -> subprocess.CompletedProcess:
    """Run agent code in its own session; its whole process group is killed when the call ends."""
    with subprocess.Popen(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env,
                          cwd=str(cwd), start_new_session=True) as process:
        try:
            stdout, stderr = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            _kill_group(process)
            process.wait()
            raise
        finally:
            _kill_group(process)
    return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)


def _run(command: list[str], env: dict[str, str], cwd: Path) -> subprocess.CompletedProcess:
    return _group_run(_untrusted_command(command), env, cwd, 120)


def _cli(data: Path) -> subprocess.CompletedProcess:
    repo = _repo()
    return _run([sys.executable, "-B", "-m", "tariff", str(data)], _env(repo), _scratch("cwd-"))


_ISOLATED = (
    "import runpy, sys\n"
    "src, data = sys.argv[1], sys.argv[2]\n"
    "sys.path.insert(0, src)\n"
    "sys.argv = ['tariff', data]\n"
    "runpy.run_module('tariff', run_name='__main__', alter_sys=True)\n"
)
_API = (
    "import json, sys\n"
    "sys.path.insert(0, sys.argv[1])\n"
    "import tariff\n"
    "print(json.dumps(tariff.build_invoices(sys.argv[2])))\n"
)


def _write_texts(texts: dict[str, str], folder: Path) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    for name, text in texts.items():
        (folder / name).write_text(text, encoding="utf-8")
    return folder


def _delivered(corpus: str) -> dict[str, Any]:
    """The delivered package's document for one corpus, run the way that corpus is run."""
    def build() -> dict[str, Any]:
        texts = _corpus_texts(corpus)
        if corpus == "relocated":
            base = _scratch("moved-")
            shutil.copytree(_repo(), base / "checkout" / "billing-engine")
            data = _write_texts(texts, base / "feeds" / "cycle-inputs")
            _open_tree(base)
            command = [sys.executable, "-I", "-B", "-c", _ISOLATED,
                       str(base / "checkout" / "billing-engine" / "src"), str(data)]
            done = _run(command, _env(None), _scratch("elsewhere-"))
        elif corpus == "api":
            data = _open_tree(_write_texts(texts, _scratch("api-") / "data"))
            command = [sys.executable, "-I", "-B", "-c", _API, str(_repo() / "src"), str(data)]
            done = _run(command, _env(None), _scratch("elsewhere-"))
        else:
            data = _open_tree(_write_texts(texts, _scratch(f"{corpus}-") / "data"))
            done = _cli(data)
        assert done.returncode == 0, f"{corpus}: exit {done.returncode}: {done.stderr[-400:]}"
        document = json.loads(done.stdout)
        assert isinstance(document, dict) and set(document) == {"invoices", "exceptions"}, "document keys"
        return document
    return _memo(f"doc:{corpus}", build)


def _shipped_texts() -> dict[str, str]:
    ci = _data_dir() / "ci"
    return {name: (ci / name).read_text(encoding="utf-8") for name in INPUT_FILES}


def _shipped_delivered() -> dict[str, Any]:
    def build() -> dict[str, Any]:
        done = _cli(_data_dir() / "ci")
        assert done.returncode == 0, f"shipped: exit {done.returncode}: {done.stderr[-400:]}"
        return json.loads(done.stdout)
    return _memo("doc:shipped", build)


# ---------------------------------------------------------------- reference reading of the contract

def _even_cents(value: Fraction) -> int:
    scaled = value * 100
    whole = scaled.numerator // scaled.denominator
    rest = scaled - whole
    if rest > Fraction(1, 2) or (rest == Fraction(1, 2) and whole % 2 == 1):
        whole += 1
    return whole


def _amount(cents: int) -> str:
    return f"{cents // 100}.{cents % 100:02d}"


class _Ledger:
    """The contract read literally, with exact fractions.

    `off` names quiet rules read the habitual way instead (Q1 estimated reads,
    Q2 standing changes, Q3 several billing rows, Q4 allowance carried, Q5
    several meter rows, U1 plan revisions, D1 paid amounts, D2 cumulative
    reads, and their variants); the planting asserts use it, the checks never
    do."""

    def __init__(self, texts: dict[str, str], off: frozenset = frozenset()):
        self.off = off
        card = json.loads(texts["rate_card.json"], parse_float=Fraction)
        self.plans = card["plans"]
        self.keys: dict[str, str] = {}
        self.periods: dict[str, tuple[date, date, str, Fraction, Fraction]] = {}
        self.rows: dict[str, list] = {}
        for row in csv.DictReader(io.StringIO(texts["billing_periods.csv"])):
            row = {key.strip(): (value or "").strip() for key, value in row.items()}
            entry = (date.fromisoformat(row["start"]), date.fromisoformat(row["end"]),
                     row["plan"], Fraction(row["commitment"]), Fraction(row.get("allowance") or "0"))
            self.periods[row["account"]] = entry
            kept = [] if "Q3" in off else self.rows.get(row["account"], [])
            self.rows[row["account"]] = kept + [entry]
        for entries in self.rows.values():
            entries.sort()
        self.windows: dict[tuple[str, str], tuple[date, date | None]] = {}
        self.spans: dict[tuple[str, str], list] = {}
        for row in csv.DictReader(io.StringIO(texts["accounts.csv"])):
            row = {key.strip(): (value or "").strip() for key, value in row.items()}
            until = date.fromisoformat(row["active_to"]) if row["active_to"] else None
            key = (row["account"], row["meter"])
            self.windows[key] = (date.fromisoformat(row["active_from"]), until)
            kept = [] if "Q5" in off else self.spans.get(key, [])
            self.spans[key] = kept + [self.windows[key]]
        self.reads = [json.loads(line) for line in texts["meter_reads.jsonl"].splitlines() if line.strip()]
        self.paid: dict[tuple[str, date], Fraction] = {}
        for row in csv.DictReader(io.StringIO(texts.get("payments.csv", ""))):
            row = {key.strip(): (value or "").strip() for key, value in row.items()}
            key = (row["account"], date.fromisoformat(row["start"]))
            self.paid[key] = self.paid.get(key, Fraction(0)) + Fraction(row["paid"])
        self.ties: dict[str, int] = {}
        self.passes: dict[str, int] = {}
        self.halves: dict[str, int] = {}

    def _plan_key(self, name: str) -> str:
        if name in self.plans:
            return name
        listed = [key for key, plan in self.plans.items()
                  if name in [code.strip() for code in plan.get("codes", [])]]
        assert len(listed) == 1, f"plan {name!r} names {len(listed)} rate card entries"
        return listed[0]

    def _row(self, account: str, day: date):
        for entry in self.rows.get(account, []):
            if entry[0] <= day <= entry[1]:
                return entry
        return None

    def _estimated(self, read: dict) -> bool:
        return "Q1" not in self.off and read.get("estimated", False) is True

    def _reason(self, account: str, meter: str, day: date, quantity: Any, estimated: bool,
                taken: set, actual: set) -> str | None:
        if type(quantity) is not int or quantity < 0:
            return "malformed_quantity"
        spans = self.spans.get((account, meter))
        if spans is None:
            return "unknown_meter"
        if not any(since <= day and (until is None or day <= until) for since, until in spans):
            return "inactive_meter"
        if self._row(account, day) is None:
            return "outside_period"
        if (account, meter, day, estimated) in taken:
            return "duplicate_read"
        if estimated and (account, meter, day) in actual:
            return "replaced_estimate"
        return None

    def document(self) -> dict[str, Any]:
        self.ties, self.passes, self.halves = {}, {}, {}
        taken: set = set()
        actual: set = set()
        usage: dict[tuple[str, date, str], int] = {}
        exceptions, accepted = [], []
        ordered = [read for read in self.reads if not self._estimated(read)]
        ordered += [read for read in self.reads if self._estimated(read)]
        for read in ordered:
            account, meter = read["account"].strip(), read["meter"].strip()
            day = date.fromisoformat(read["day"].strip())
            estimated = self._estimated(read)
            reason = self._reason(account, meter, day, read["quantity"], estimated, taken, actual)
            if reason is None:
                taken.add((account, meter, day, estimated))
                if not estimated:
                    actual.add((account, meter, day))
                accepted.append((read, account, meter, day))
            else:
                exceptions.append({"read_id": read["read_id"].strip(), "account": account, "reason": reason})
        exceptions.sort(key=lambda row: row["read_id"])
        billed = self._billed(accepted)
        for read, account, meter, day in accepted:
            key = (account, self._row(account, day)[0], meter)
            usage[key] = usage.get(key, 0) + billed[read["read_id"]]
        self.chosen: dict[str, Any] = {}
        for key in sorted(self.plans):
            if "U1" in self.off or not self.plans[key].get("revisions"):
                continue
            fits = [number for number, revision in enumerate(self.plans[key]["revisions"])
                    if self._fits(key, revision["tiers"], usage)]
            if len(fits) == 1 or (fits and "U1first" in self.off):
                self.chosen[key] = self.plans[key]["revisions"][fits[0]]["tiers"]
            elif not fits and "U1nofit" in self.off:
                self.chosen[key] = self.plans[key]["revisions"][0]["tiers"]
        self.ties, self.passes, self.halves = {}, {}, {}
        invoices = []
        for account in sorted(self.rows):
            invoices += self._chain(account, usage, self.chosen)
        return {"invoices": invoices, "exceptions": exceptions}

    def _billed(self, accepted: list) -> dict[str, int]:
        """Billed quantity per read id of the accepted reads."""
        billed, chains = {}, {}
        pool = accepted
        if "D2any" in self.off:
            pool = [(read, read["account"].strip(), read["meter"].strip(), date.fromisoformat(read["day"].strip()))
                    for read in self.reads if type(read["quantity"]) is int and read["quantity"] >= 0]
        for place, (read, account, meter, day) in enumerate(pool):
            if "D2" not in self.off and read.get("cumulative", False) is True:
                scope = self._row(account, day)[0] if "D2row" in self.off else None
                chains.setdefault((account, meter, scope), []).append((day, place, read))
        for read, account, meter, day in accepted:
            billed[read["read_id"]] = read["quantity"]
        for chain in chains.values():
            chain.sort(key=lambda item: item[1] if "D2file" in self.off else item[0])
            for place, (day, _, read) in enumerate(chain):
                if read["read_id"] not in billed:
                    continue
                count = read["quantity"]
                before = chain[place - 1][2]["quantity"] if place else None
                billed[read["read_id"]] = 0 if before is None else count if before > count else count - before
        return billed

    def _fits(self, key: str, tiers: list, usage: dict) -> bool:
        tried = dict(self.chosen)
        tried[key] = tiers
        for account in sorted(self.rows):
            if all(self._plan_key(entry[2]) != key for entry in self.rows[account]):
                continue
            for invoice in self._chain(account, usage, tried):
                paid = self.paid.get((account, date.fromisoformat(invoice["period"]["start"])))
                if self._plan_key(invoice["plan"]) == key and paid is not None and Fraction(invoice["total"]) != paid:
                    return False
        return True

    def _chain(self, account: str, usage: dict, chosen: dict) -> list[dict[str, Any]]:
        invoices, carry, owed = [], Fraction(0), False
        for entry in self.rows[account]:
            invoice, left = self._invoice(account, entry, usage, carry, chosen, owed)
            invoices.append(invoice)
            carry = Fraction(0) if "Q4" in self.off else left
            paid = self.paid.get((account, entry[0]), Fraction(0) if "D1zero" in self.off else None)
            owed = "D1" not in self.off and paid is not None and paid < Fraction(invoice["total"])
        return invoices

    def _charge(self, plan: dict, day: date) -> Fraction:
        charge, since = Fraction(plan["standing_charge"]), None
        if "Q2" in self.off:
            return charge
        for change in plan.get("standing_changes", []):
            when = date.fromisoformat(change["from"].strip())
            if when <= day and (since is None or when > since):
                charge, since = Fraction(change["standing_charge"]), when
        return charge

    def _invoice(self, account: str, entry: tuple, usage: dict, carry: Fraction,
                 chosen: dict | None = None, owed: bool = False) -> tuple[dict[str, Any], Fraction]:
        start, end, plan_name, commitment, allowance = entry
        self.keys[account] = self._plan_key(plan_name)
        plan = self.plans[self.keys[account]]
        tiers = (chosen or {}).get(self.keys[account], plan["tiers"])
        lines, ties, position = [], 0, 0
        for meter in sorted(m for (a, m) in self.spans if a == account):
            quantity, floor = usage.get((account, start, meter), 0), 0
            if "N3" in self.off:
                position = 0
            for number, tier in enumerate(tiers, 1):
                cap = tier["up_to"]
                low = max(position, floor)
                high = position + quantity if cap is None else min(position + quantity, cap)
                if high > low:
                    lines.append([meter, "energy", number, high - low, (high - low) * Fraction(tier["rate"])])
                if cap is None:
                    break
                floor = cap
            position += quantity
            exact, units = Fraction(0), 0
            for since, until in sorted(self.spans[(account, meter)]):
                first, last = max(since, start), end if until is None else min(until, end)
                day = first
                while day <= last:
                    month_end = date(day.year + day.month // 12, day.month % 12 + 1, 1) - timedelta(days=1)
                    exact += self._charge(plan, day) / month_end.day
                    units += 1
                    day = day + timedelta(days=1)
            if units:
                lines.append([meter, "standing", 0, units, exact])
        left, live, passes = allowance + carry, [line for line in lines if line[1] == "energy"], 0
        while left > 0 and live and not ("N1" in self.off and passes):
            passes += 1
            part = left / len(live)
            for line in live:
                take = min(part, line[4])
                line[4] -= take
                left -= take
            live = [line for line in live if line[4] > 0]
        rows, subtotal, halves = [], 0, 0
        for meter, kind, tier, units, exact in lines:
            cents = _even_cents(exact)
            if exact * 100 - (exact * 100).numerator // (exact * 100).denominator == Fraction(1, 2):
                halves += 1
                ties += cents % 2 == 0
            subtotal += cents
            rows.append({"meter": meter, "kind": kind, "tier": tier, "units": units, "amount": _amount(cents)})
        total = subtotal
        if Fraction(subtotal, 100) >= commitment and not owed:
            kept = subtotal * (1 - Fraction(plan["credit_rate"]))
            halves += kept - kept.numerator // kept.denominator == Fraction(1, 2)
            total = _even_cents(Fraction(subtotal, 100) * (1 - Fraction(plan["credit_rate"])))
        self.halves[account] = self.halves.get(account, 0) + halves
        self.ties[account] = self.ties.get(account, 0) + ties
        self.passes[account] = max(self.passes.get(account, 0), passes)
        invoice = {"account": account, "period": {"start": start.isoformat(), "end": end.isoformat()},
                   "plan": plan_name, "lines": rows, "subtotal": _amount(subtotal),
                   "credit": _amount(subtotal - total), "total": _amount(total)}
        return invoice, left


def _expected(corpus: str) -> dict[str, Any]:
    texts = _shipped_texts() if corpus == "shipped" else _corpus_texts(corpus)
    return _memo(f"ref:{corpus}", lambda: _Ledger(texts).document())


# ---------------------------------------------------------------- hidden corpora

def _rate_text(units: int) -> str:
    return f"{units // 10000}.{units % 10000:04d}"


def _tie_units(rate: int, limit: int) -> list[int]:
    """Units whose line lands on half a cent with an even cent below and the binary float product above it."""
    found = []
    for units in range(1, limit):
        value = units * rate
        if value % 100 != 50 or (value // 100) % 2:
            continue
        if Fraction((rate / 10000) * units) > Fraction(value, 10000):
            found.append(units)
    return found


def _tie_rate(rng: random.Random, low: int, high: int, limit: int) -> tuple[int, list[int]]:
    while True:
        rate = rng.randrange(low, high)
        if rate % 4 == 0 or Fraction(rate / 10000) <= Fraction(rate, 10000):
            continue
        units = _tie_units(rate, limit)
        if len(units) >= 3:
            return rate, units


def _card_text(plans: dict[str, dict[str, Any]]) -> str:
    parts = []
    for name, plan in plans.items():
        tiers = ", ".join(
            "{" + f'"up_to": {"null" if cap is None else cap}, "rate": {_rate_text(rate)}' + "}"
            for cap, rate in plan["tiers"])
        codes = "".join(f'"codes": {json.dumps(plan["codes"])}, ' for _ in [0] if "codes" in plan)
        parts.append(f'    "{name}": {{"standing_charge": {_amount(plan["standing"])}, '
                     f'"credit_rate": {plan["credit"]}, {codes}"tiers": [{tiers}]}}')
    return '{\n  "currency": "EUR",\n  "plans": {\n' + ",\n".join(parts) + "\n  }\n}\n"


def _read_line(read: dict[str, Any]) -> str:
    return ('{"read_id": ' + json.dumps(read["read_id"]) + ', "account": ' + json.dumps(read["account"])
            + ', "meter": ' + json.dumps(read["meter"]) + ', "day": ' + json.dumps(read["day"])
            + ', "quantity": ' + read["quantity"]
            + "".join(f', "estimated": {json.dumps(read["estimated"])}' for _ in [0] if "estimated" in read)
            + "".join(', "cumulative": true' for _ in [0] if read.get("cumulative")) + "}")


def _assemble(plans, periods, meters, reads) -> dict[str, str]:
    return {
        "meter_reads.jsonl": "".join(_read_line(read) + "\n" for read in reads),
        "accounts.csv": "account,meter,active_from,active_to\n"
        + "".join(f"{a},{m},{f},{t}\n" for a, m, f, t in meters),
        "billing_periods.csv": "account,start,end,plan,commitment,allowance\n"
        + "".join(f"{a},{s},{e},{p},{c},{w}\n" for a, s, e, p, c, w in periods),
        "rate_card.json": _card_text(plans),
    }


def _period(rng: random.Random, crossing: bool) -> tuple[date, date]:
    if not crossing:
        year, month = rng.choice([2026, 2027]), rng.choice([1, 2, 3, 5, 7, 8, 10, 12])
        start = date(year, month, 1)
        return start, date(year + month // 12, month % 12 + 1, 1) - timedelta(days=1)
    while True:
        start = date(rng.choice([2026, 2027]), rng.randrange(1, 13), rng.randrange(2, 28))
        end = start + timedelta(days=rng.choice([27, 29, 32, 33, 34]) - 1)
        if (end.year, end.month) != (start.year, start.month):
            return start, end


def _split(rng: random.Random, total: int, parts: int) -> list[int]:
    cuts = sorted(rng.sample(range(1, total), parts - 1)) if total > parts else []
    bounds = [0, *cuts, total]
    return [b - a for a, b in zip(bounds, bounds[1:])] if cuts else [total]


def _corpus(seed: int, size: int, reuse: tuple[str, ...],
            levers: frozenset[str]) -> tuple[dict[str, str], dict[str, Any]]:
    """A seed whose rates cannot settle a planted case moves on to the next seed in a fixed sequence."""
    for attempt in range(25):
        try:
            return _corpus_once(seed + 100003 * attempt, size, reuse, levers)
        except AssertionError:
            if attempt == 24:
                raise
    raise AssertionError(seed)


def _corpus_once(seed: int, size: int, reuse: tuple[str, ...],
                 levers: frozenset[str]) -> tuple[dict[str, str], dict[str, Any]]:
    rng = random.Random(seed)
    tag = "".join(rng.choice("KLMNPRSTVW") for _ in range(2))
    plans: dict[str, dict[str, Any]] = {}
    tie_units: dict[str, list[tuple[int, int]]] = {}
    scale_step = rng.randrange(30, 41)
    shared_tiers = "N3" in levers
    for index, credit in enumerate(["0.05", "0.02", "0.06", "0.04"]):
        first = rng.randrange(80, 261) if shared_tiers else rng.randrange(5000, 6001)
        second = first + rng.randrange(200, 501)
        middle, middle_units = _tie_rate(rng, 1800, 2400, second - first)
        last, last_units = _tie_rate(rng, 1150, 1800, 1500)
        if index == 0:
            head, head_units = 80 * scale_step, list(range(60, 1000))
        elif shared_tiers:
            head, head_units = rng.randrange(2400, 3200), []
        else:
            head, head_units = _tie_rate(rng, 2400, 3200, 1000)
        name = f"{tag}-{index + 1}"
        plans[name] = {"standing": rng.randrange(1200, 7000), "credit": credit,
                       "tiers": [(first, head), (second, middle), (None, last)]}
        if shared_tiers:
            tie_units[name] = [(first, u) for u in middle_units] + [(second, u) for u in last_units]
        else:
            tie_units[name] = [(0, u) for u in head_units]
    names = list(plans)
    named = _plant_codes(random.Random(seed * 7 + 11), plans, "L11" in levers)
    accounts = sorted({*reuse, *(f"{tag[0]}{n:04d}" for n in rng.sample(range(1, 10000), size - len(reuse)))})
    credit_ties = {accounts[1]: names[1], accounts[4]: names[2]}
    equal = {accounts[7]: names[3]}
    meter_ids = iter(f"{tag[1]}{n:05d}" for n in rng.sample(range(1, 100000), size * 6))
    read_ids = iter(f"H{n:05d}" for n in rng.sample(range(10000, 100000), size * 40))
    periods, meters, reads, pairs = [], [], [], []
    tuned: dict[str, dict[str, Any]] = {}
    kinds = ["late", "early", "gone"]

    def add(account, meter, day, quantity, pad=False):
        read = {"read_id": next(read_ids), "account": account, "meter": meter, "day": day.isoformat(),
                "quantity": quantity}
        if pad or rng.random() < 0.04:
            read["read_id"], read["account"], read["meter"] = f" {read['read_id']}", f"{account} ", f" {meter}  "
        reads.append(read)
        return read

    for position, account in enumerate(accounts):
        plan_name = credit_ties.get(account) or equal.get(account) or rng.choice(names)
        start, end = _period(rng, "N2" in levers)
        span = (end - start).days + 1
        days = [start + timedelta(days=k) for k in range(span)]
        periods.append([account, start.isoformat(), end.isoformat(), plan_name, None])
        own = sorted(next(meter_ids) for _ in range(4))
        for meter in own[:3]:
            meters.append((account, meter, (start - timedelta(days=rng.randrange(30, 400))).isoformat(), ""))
        quiet = account in credit_ties or account in equal
        kind = "open" if quiet else (kinds[position % 3] if position < 6 else rng.choice(["open", "open", *kinds]))
        since, until = start - timedelta(days=rng.randrange(20, 300)), None
        if kind == "late":
            since = start + timedelta(days=rng.randrange(1, span - 2))
        elif kind == "early":
            until = start + timedelta(days=rng.randrange(0, span - 3))
        elif kind == "gone":
            until = start - timedelta(days=rng.randrange(1, 40))
            since = until - timedelta(days=rng.randrange(20, 200))
        meters.append((account, own[3], since.isoformat(), "" if until is None else until.isoformat()))
        if not quiet and position % 3 == 1:
            # an active meter whose only read is rejected still pays its standing line
            own.append(next(meter_ids))
            meters.append((account, own[4], (start - timedelta(days=rng.randrange(30, 400))).isoformat(), ""))
            add(account, own[4], rng.choice(days), rng.choice(["null", "false", "7.5", "-3"]))
        used: dict[str, set] = {meter: set() for meter in own}
        accepted_first: dict[str, dict[str, Any]] = {}
        prefix, picked = 0, set()
        for meter in own[:3]:
            # each tie meter ends on a line of tie units, counted from the units of the meters before it
            caps, fits = [cap for cap, _ in plans[plan_name]["tiers"]], []
            for floor, units in tie_units[plan_name]:
                top = caps[caps.index(floor) + 1] if floor in caps else None
                quantity = floor + units - prefix if prefix <= floor else units
                if top is None or prefix + quantity <= top:
                    fits.append(quantity)
            quantity = rng.choice([q for q in fits if q not in picked] or fits)
            picked.add(quantity)
            prefix += quantity
            parts = _split(rng, quantity, rng.choice([2, 3]))
            for part, day in zip(parts, rng.sample(days, len(parts))):
                read = add(account, meter, day, str(part))
                used[meter].add(day)
                accepted_first.setdefault(meter, read)
        live = [d for d in days if d >= since and (until is None or d <= until)]
        for day in rng.sample(live, min(len(live), rng.choice([2, 3]))) if kind != "gone" else []:
            add(account, own[3], day, str(rng.randrange(0, 300)))
            used[own[3]].add(day)
        if quiet:
            spare = [d for d in days if d not in used[own[3]]]
            tuned[account] = add(account, own[3], rng.choice(spare), "0")
        # a quoted integer on a day of its own, so reading it would move the energy line
        spare = [d for d in days if d not in used[own[0]]]
        quoted = rng.randrange(20, 90)
        add(account, own[0], rng.choice(spare), json.dumps(rng.choice([str(quoted), f" {quoted} ", f"{quoted} "])))
        # same day, same quantity again on a tie meter
        twin = accepted_first[own[1]]
        pairs.append((twin, add(account, own[1], date.fromisoformat(twin["day"]), twin["quantity"])))
        outside = end + timedelta(days=rng.randrange(1, 6)) if rng.random() < 0.5 else start - timedelta(days=rng.randrange(1, 6))
        add(account, own[1], outside, str(rng.randrange(5, 200)))
        if position % 4 == 0:
            add(account, own[1], outside, str(rng.randrange(5, 200)))
        spare = [d for d in days if d not in used[own[2]]]
        add(account, own[2], rng.choice(spare), rng.choice(["2.5", "12.0", "1E2", "3e1", "true", "false", "null", "-4", "40.00"]))
        stranger = rng.choice([m for (_, m, _, _) in meters if m not in own] or ["Z00000"])
        add(account, stranger, rng.choice(days), rng.choice([str(rng.randrange(1, 90)), json.dumps(str(rng.randrange(1, 90)))]))
        if kind in ("late", "early", "gone"):
            away = start - timedelta(days=3) if kind == "late" else end + timedelta(days=3)
            add(account, own[3], away, str(rng.randrange(1, 90)))
            gap = [d for d in days if d < since or (until is not None and d > until)]
            if gap:
                add(account, own[3], rng.choice(gap), str(rng.randrange(1, 90)))
        if not quiet and kind != "gone" and used[own[3]]:
            day = rng.choice(sorted(used[own[3]]))
            first = next(r for r in reads if r["meter"].strip() == own[3] and r["day"] == day.isoformat())
            pairs.append((first, add(account, own[3], day, str(int(first["quantity"]) + rng.randrange(1, 40)))))
        if kind == "open" and not quiet:
            spare = [d for d in days if d not in used[own[3]]]
            day = rng.choice(spare)
            pairs.append((add(account, own[3], day, "null"), add(account, own[3], day, str(rng.randrange(1, 60)))))
            used[own[3]].add(day)
            day = rng.choice([d for d in days if d not in used[own[3]]])
            pairs.append((add(account, own[3], day, str(rng.randrange(1, 60))), add(account, own[3], day, "-7")))
    add("Q" + tag, "Z" + tag, date(2026, 6, 1), "10")
    if "L11" in levers:
        _name_by_code(random.Random(seed * 7 + 13), plans, periods, named)

    order = list(range(len(reads)))
    rng.shuffle(order)
    reads = [reads[i] for i in order]
    for first, second in pairs:
        a, b = reads.index(first), reads.index(second)
        if a > b:
            reads[a], reads[b] = reads[b], reads[a]

    allowances: dict[str, str] = {}

    def texts_for(chosen: set[str] | None, commitments: dict[str, str]) -> dict[str, str]:
        keep = (lambda account: True) if chosen is None else (lambda account: account in chosen)
        rows = [[*row[:3], named.get(row[0], row[3]), commitments.get(row[0], "0.00"),
                 allowances.get(row[0], "0.00")] for row in periods if keep(row[0])]
        return _assemble(plans, rows, [m for m in meters if keep(m[0])],
                         [r for r in reads if keep(r["account"].strip())])

    def sharing(values: list[Fraction], allowance: Fraction) -> tuple[int, Fraction, Fraction]:
        left, live, passes, after_two = allowance, list(values), 0, Fraction(0)
        while left > 0 and live:
            passes += 1
            part = left / len(live)
            taken = [min(part, value) for value in live]
            left -= sum(taken)
            live = [value - take for value, take in zip(live, taken) if value > take]
            if passes == 2:
                after_two = left
        return passes, after_two, left

    reshared = []
    if "N1" in levers:
        base = _Ledger(texts_for(None, {}))
        for invoice in base.document()["invoices"]:
            account = invoice["account"]
            if account in credit_ties or account in equal or accounts.index(account) % 2:
                continue
            tiers = base.plans[base.keys[account]]["tiers"]
            values = [line["units"] * tiers[line["tier"] - 1]["rate"] for line in invoice["lines"]
                      if line["kind"] == "energy"]
            for _ in range(600):
                cents = rng.randrange(1, int(sum(values) * 100))
                passes, after_two, unused = sharing(values, Fraction(cents, 100))
                if passes >= 3 and after_two >= Fraction(5, 100) and unused == 0:
                    allowances[account] = _amount(cents)
                    reshared.append(account)
                    break
            else:
                raise AssertionError(f"no allowance shared three times for {account}")

    for account, read in tuned.items():
        for quantity in range(0, 600):
            read["quantity"] = str(quantity)
            cents = _cents_of(_Ledger(texts_for({account}, {})).document()["invoices"][0]["subtotal"])
            if account in equal or cents % 50 == 25:
                break
        else:
            raise AssertionError("no settling quantity for a credit tie")
    ledger = _Ledger(texts_for(None, {}))
    subtotals = {inv["account"]: _cents_of(inv["subtotal"]) for inv in ledger.document()["invoices"]}
    commitments = {}
    for account, cents in subtotals.items():
        if account in equal:
            commitments[account] = _amount(cents)
        elif account in credit_ties:
            commitments[account] = _amount(cents - rng.randrange(0, cents // 4))
        else:
            commitments[account] = _amount(int(cents * rng.choice([0.6, 0.75, 0.9, 1.05, 1.2, 1.4])))
    texts = texts_for(None, commitments)
    info = {"plans": plans, "first_plan": names[0], "scale_step": scale_step, "credit_ties": sorted(credit_ties),
            "equal": sorted(equal), "subtotals": subtotals, "ties": dict(ledger.ties), "kinds": None,
            "levers": sorted(levers), "reshared": reshared, "named": dict(named)}
    _assert_bounds(texts, info)
    return texts, info


def _code_text(rng: random.Random, letter: str, taken: set[str]) -> str:
    while True:
        code = f"{letter}{rng.randrange(1000, 10000)}"
        if code not in taken and not any(code.startswith(t) or t.startswith(code) for t in taken):
            taken.add(code)
            return code


def _plant_codes(rng: random.Random, plans: dict[str, dict[str, Any]], naming: bool) -> dict[str, str]:
    """Every corpus card lists fresh tariff codes; one plan lists none and one code carries a space."""
    letter, taken = rng.choice("BDFGHJ"), set()
    names = list(plans)
    bare = rng.choice(names[1:-1])
    for name in names:
        plans[name]["codes"] = [] if name == bare else [_code_text(rng, letter, taken) for _ in range(rng.choice([1, 2]))]
    coded = [n for n in names if plans[n]["codes"]]
    if all(len(plans[n]["codes"]) < 2 for n in coded):
        plans[coded[0]]["codes"].append(_code_text(rng, letter, taken))
    _share_stem(plans, taken)
    padded = rng.choice(coded)
    plans[padded]["codes"][0] = " " + plans[padded]["codes"][0]
    return {}


def _share_stem(plans: dict[str, dict[str, Any]], taken: set[str]) -> None:
    """Two plans list codes that open with the same three characters."""
    first, second = [n for n in plans if plans[n]["codes"]][:2]
    old = plans[second]["codes"][0]
    stem = plans[first]["codes"][0].strip()[:3]
    taken.discard(old.strip())
    for tail in range(10, 100):
        code = f"{stem}{tail}"
        if code != old.strip() and code not in taken and not any(code.startswith(t) or t.startswith(code) for t in taken):
            taken.add(code)
            plans[second]["codes"][0] = old.replace(old.strip(), code)
            return
    raise AssertionError("no free code stem")


def _name_by_code(rng: random.Random, plans: dict[str, dict[str, Any]], periods: list, named: dict[str, str]) -> None:
    """Name about half of the accounts by a code of their own plan, every code at least once."""
    pending = [code for plan in plans.values() for code in plan["codes"]]
    rows = [row for row in periods if plans[row[3]]["codes"]]
    rng.shuffle(rows)
    goal = max(-(-len(periods) * 2 // 5), len(pending))
    for row in rows:
        codes = plans[row[3]]["codes"]
        mine = [code for code in pending if code in codes]
        if mine or len(named) < goal or rng.random() < 0.3:
            code = (mine or [rng.choice(codes)])[0]
            if code in pending:
                pending.remove(code)
            named[row[0]] = code.strip() if rng.random() < 0.85 else f" {code.strip()} "
    assert not pending and len(named) >= goal, (pending, len(named))
    if all(value == value.strip() for value in named.values()):
        first = sorted(named)[0]
        named[first] = f" {named[first]} "


def _assert_codes(ledger: "_Ledger", texts: dict[str, str], info: dict[str, Any]) -> None:
    keys = list(ledger.plans)
    codes = [code.strip() for plan in ledger.plans.values() for code in plan.get("codes", [])]
    assert len(codes) == len(set(codes)) >= 3 and not set(codes) & set(keys)
    folded = {"".join(ch for ch in text.casefold() if ch.isalnum()) for text in keys}
    assert len(folded) == len(keys) and not folded & {code.casefold() for code in codes}
    assert any(not plan.get("codes") for plan in ledger.plans.values())
    assert any(code != code.strip() for plan in ledger.plans.values() for code in plan.get("codes", []))
    named = {a: ledger.periods[a][2] for a in ledger.periods if ledger.periods[a][2] not in ledger.plans}
    if "L11" not in info["levers"]:
        assert not named
        return
    assert len(named) * 10 >= len(ledger.periods) * 4, len(named)
    assert {name for name in named.values()} == set(codes)
    owners = {ledger.keys[a] for a in named}
    assert len(owners) >= 2 and owners - {keys[0]} and owners - {keys[-1]}
    assert any(len(plan.get("codes", [])) >= 2 for plan in ledger.plans.values())
    stems = [{code.strip()[:3] for code in plan.get("codes", [])} for plan in ledger.plans.values()]
    assert any(a & b for i, a in enumerate(stems) for b in stems[i + 1:])
    raw = [line.split(",")[3] for line in texts["billing_periods.csv"].splitlines()[1:]]
    assert any(value != value.strip() for value in raw)


def _renamed(texts: dict[str, str], info: dict[str, Any], seed: int) -> dict[str, str]:
    """Every code renamed in card and billing together, plan order rotated, every file's rows rotated."""
    rng = random.Random(seed)
    letter = rng.choice([c for c in "BDFGHJ" if c not in "".join(info["named"].values())])
    taken: set[str] = set()
    fresh: dict[str, str] = {}
    plans = {}
    for name, plan in info["plans"].items():
        plans[name] = dict(plan, codes=[])
        for code in plan["codes"]:
            fresh[code.strip()] = _code_text(rng, letter, taken)
            plans[name]["codes"].append(code.replace(code.strip(), fresh[code.strip()]))
    before = {code.strip() for plan in plans.values() for code in plan["codes"]}
    _share_stem(plans, taken)
    after = {code.strip() for plan in plans.values() for code in plan["codes"]}
    (gone,), (new,) = before - after, after - before
    fresh = {old: (new if value == gone else value) for old, value in fresh.items()}
    order = list(plans)
    k = rng.randrange(1, len(order))
    plans = {name: plans[name] for name in order[k:] + order[:k]}
    head, *body = texts["billing_periods.csv"].splitlines(keepends=True)
    rows = []
    for line in body:
        cells = line.split(",")
        value = cells[3].strip()
        if value in fresh:
            cells[3] = cells[3].replace(value, fresh[value])
        rows.append(",".join(cells))
    out = {**texts, "billing_periods.csv": head + "".join(rows), "rate_card.json": _card_text(plans)}
    return _rotated(out, seed + 1)


def _cents_of(text: str) -> int:
    whole, cents = text.split(".")
    return int(whole) * 100 + int(cents)


def _assert_bounds(texts: dict[str, str], info: dict[str, Any]) -> None:
    """Every corpus stays inside what the contract promises about its inputs and plants each of its cases."""
    ledger = _Ledger(texts)
    document = ledger.document()
    levers = set(info["levers"])
    for account, (start, end, plan, commitment, allowance) in ledger.periods.items():
        span = (end - start).days + 1
        assert 1 <= span <= 62 and span not in (28, 30, 31) if "N2" in levers else span in (28, 31), account
        if "N2" in levers:
            assert (start.year, start.month) != (end.year, end.month), account
        else:
            assert start.day == 1 and (end + timedelta(days=1)).day == 1, account
        assert (commitment * 100).denominator == 1 and commitment >= 0, account
        assert (allowance * 100).denominator == 1 and allowance >= 0, account
        assert allowance == 0 or account in info["reshared"], account
    for account in info["reshared"]:
        assert ledger.passes[account] >= 3, f"{account} shares its allowance {ledger.passes[account]} times"
    for invoice in document["invoices"]:
        account, plan = invoice["account"], ledger.plans[ledger.keys[invoice["account"]]]
        energy = [line for line in invoice["lines"] if line["kind"] == "energy"]
        units = sum(line["units"] for line in energy)
        if "N3" in levers:
            assert len({line["meter"] for line in energy}) >= 2 and units > plan["tiers"][0]["up_to"], account
        else:
            assert units <= plan["tiers"][0]["up_to"], account
        if account not in info["reshared"] and ("N3" in levers or ledger.keys[account] != info["first_plan"]):
            assert info["ties"][account] >= 3, f"{account} has {info['ties'][account]} half-cent lines"
    assert sum(info["ties"].values()) >= 10
    for plan in ledger.plans.values():
        assert (plan["standing_charge"] * 100).denominator == 1
        assert 0 <= plan["credit_rate"] <= 1 and (plan["credit_rate"] * 10000).denominator == 1
        assert all(tier["rate"] > 0 and (tier["rate"] * 10 ** 8).denominator == 1 for tier in plan["tiers"])
        assert [t["up_to"] for t in plan["tiers"]][-1] is None
    for account in info["credit_ties"]:
        cents = info["subtotals"][account]
        assert cents % 50 == 25 and ledger.periods[account][3] * 100 <= cents, account
    for account in info["equal"]:
        assert ledger.periods[account][3] * 100 == info["subtotals"][account], account
    ids = [json.loads(line)["read_id"].strip() for line in texts["meter_reads.jsonl"].splitlines()]
    assert len(ids) == len(set(ids))
    quoted = {json.loads(line)["account"].strip() for line in texts["meter_reads.jsonl"].splitlines()
              if isinstance(json.loads(line)["quantity"], str)}
    assert set(ledger.periods) <= quoted
    _assert_codes(ledger, texts, info)


def _rescaled(texts: dict[str, str], info: dict[str, Any], seed: int) -> dict[str, str]:
    """Rows shuffled and one plan's first rate multiplied by 1.0375 (83/80), still four decimals."""
    plans = {name: dict(plan) for name, plan in info["plans"].items()}
    first = plans[info["first_plan"]]
    (cap, rate), *rest = first["tiers"]
    assert rate == 80 * info["scale_step"]
    first["tiers"] = [(cap, 83 * info["scale_step"]), *rest]
    lines = texts["meter_reads.jsonl"].splitlines(keepends=True)
    random.Random(seed).shuffle(lines)
    return {**texts, "meter_reads.jsonl": "".join(lines), "rate_card.json": _card_text(plans)}


def _rotated(texts: dict[str, str], seed: int) -> dict[str, str]:
    rng = random.Random(seed)
    out = dict(texts)
    for name in ("meter_reads.jsonl", "accounts.csv", "billing_periods.csv"):
        lines = texts[name].splitlines(keepends=True)
        head, body = (lines[:1], lines[1:]) if name.endswith(".csv") else ([], lines)
        k = rng.randrange(1, len(body))
        out[name] = "".join(head + body[k:] + body[:k])
    return out


_QUIET = ("Q1", "Q2", "Q3", "Q4", "Q5")
_QUIET_SEEDS = {"fresh": H1_SEED, "rescaled": H1_SEED + 1, "relocated": H3_SEED, "rotated": H3_SEED + 1,
                "api": H5_SEED, "recoded": H7_SEED, "renamed": H7_SEED + 1}
_GROUPS = {"estimated": frozenset({"Q1"}), "standing_changes": frozenset({"Q2"}),
           "meter_rows": frozenset({"Q5"}), "billing_rows": frozenset({"Q3"}),
           "allowance_carried": frozenset({"Q3", "Q4"})}


def _month(year: int, month: int, step: int = 0) -> tuple[date, date]:
    year, month = year + (month - 1 + step) // 12, (month - 1 + step) % 12 + 1
    start = date(year, month, 1)
    return start, date(year + month // 12, month % 12 + 1, 1) - timedelta(days=1)


def _quiet_once(texts: dict[str, str], rng: random.Random):
    """Accounts of the five quiet rules (and of pairs of them) added to a corpus on their own ids and plans."""
    base = _Ledger(texts)
    used = {name.upper() for name in [*base.rows, *(m for _, m in base.spans), *base.plans]}
    used |= {read["read_id"].strip().upper() for read in base.reads}
    lead = max(sorted({a[0] for a in base.rows}), key=lambda c: sum(a[0] == c for a in base.rows))
    mlead = max(sorted({m[0] for _, m in base.spans}), key=lambda c: sum(m[0] == c for _, m in base.spans))
    stem = sorted(base.plans)[0].rsplit("-", 1)[0]

    def new_id(prefix: str, width: int) -> str:
        while True:
            value = f"{prefix}{rng.randrange(10 ** width):0{width}d}"
            if value.upper() not in used:
                used.add(value.upper())
                return value

    plans: dict[str, dict[str, Any]] = {}

    def new_plan(changes=()) -> tuple[str, dict[str, Any]]:
        number = 5
        while f"{stem}-{number}".upper() in used:
            number += 1
        name = f"{stem}-{number}"
        used.add(name.upper())
        plans[name] = {"standing": rng.randrange(1500, 6000), "credit": rng.choice(["0.03", "0.05", "0.07"]),
                       "tiers": [(rng.randrange(5000, 6001), rng.randrange(8, 40) * 100),
                                 (None, rng.randrange(5, 30) * 100)], "changes": list(changes)}
        return name, plans[name]

    year = rng.choice([2026, 2027])
    m1, m2 = rng.sample(range(1, 13), 2)
    plain_a, plain_b = new_plan(), new_plan()
    first, after = _month(year, m1), _month(year, m1, 1)
    early = _month(year, m1, -2)[0]
    changed = [(first[0] + timedelta(days=rng.randrange(8, 15)), rng.randrange(1500, 6000)),
               (early + timedelta(days=rng.randrange(0, 20)), rng.randrange(1500, 6000))]
    plan_c = new_plan(changed)
    second = _month(year, m2)
    plan_d = new_plan([(second[0] + timedelta(days=rng.randrange(17, 24)), rng.randrange(1500, 6000)),
                       (_month(year, m2, 7)[0], rng.randrange(1500, 6000)),
                       (second[0] + timedelta(days=rng.randrange(5, 12)), rng.randrange(1500, 6000))])
    blocks: dict[str, list[list]] = {"billing": [], "meters": []}
    reads: list[dict[str, Any]] = []
    before: list[tuple[dict, dict]] = []
    labels: dict[str, frozenset] = {}

    def read(account, meter, day, quantity, estimated=None):
        item = {"read_id": new_id("H", 5), "account": account, "meter": meter, "day": day.isoformat(),
                "quantity": str(quantity)}
        if estimated is not None:
            item["estimated"] = estimated
        reads.append(item)
        return item

    def days(span, count):
        width = (span[1] - span[0]).days + 1
        return [span[0] + timedelta(days=d) for d in rng.sample(range(width), count)]

    def plain(account, meter, span, count):
        for day in days(span, count):
            read(account, meter, day, rng.randrange(5, 60))

    def meter_rows(account, rows):
        meter = new_id(mlead, 5)
        blocks["meters"].append([(account, meter, since.isoformat(), "" if until is None else until.isoformat())
                                 for since, until in rows])
        return meter

    def open_meter(account, start):
        return meter_rows(account, [(start - timedelta(days=rng.randrange(0, 200)), None)])

    def bill(account, entries, kinds):
        blocks["billing"].append([(account, s.isoformat(), e.isoformat(), plan, _amount(commit), _amount(allow))
                                  for s, e, plan, commit, allow in entries])
        labels[account] = frozenset(kinds)

    def commit():
        return rng.choice([0, rng.randrange(100, 2000), 999900])

    def month_of():
        return _month(rng.choice([2026, 2027]), rng.randrange(1, 13))

    def pair(span, account, meter):
        day = days(span, 1)[0]
        guess = read(account, meter, day, rng.randrange(5, 60), True)
        real = read(account, meter, day, rng.randrange(61, 90), rng.choice([None, False]))
        before.append((guess, real))

    def rate_of(plan_name):
        return plans[plan_name]["tiers"][0][1] // 100

    # Q1 estimated reads
    for shape in range(3):
        account, span = new_id(lead, 4), month_of()
        meter = open_meter(account, span[0])
        plain(account, meter, span, 3)
        bill(account, [(*span, plain_a[0], commit(), 0)], {"Q1"})
        spot, other = days(span, 2)
        if shape == 0:
            pair(span, account, meter)
            read(account, meter, other, rng.randrange(5, 60), True)
        elif shape == 1:
            real = read(account, meter, spot, rng.randrange(5, 60), False)
            guess = read(account, meter, spot, rng.randrange(61, 90), True)
            before.append((real, guess))
            read(account, meter, other, rng.randrange(5, 60), True)
            read(account, meter, other, rng.randrange(5, 60), True)
        else:
            read(account, meter, spot, -3)
            read(account, meter, spot, rng.randrange(5, 60), True)
            pair(span, account, meter)
            plain(account, open_meter(account, span[0]), span, 2)
    # Q2 standing changes
    for plan, span in ((plan_c, first), (plan_c, after), (plan_d, second)):
        account = new_id(lead, 4)
        bill(account, [(*span, plan[0], commit(), 0)], {"Q2"})
        for _ in range(rng.randrange(1, 3)):
            plain(account, open_meter(account, span[0]), span, 3)
    # Q3 several billing rows
    for shape in range(2):
        account = new_id(lead, 4)
        spans = [month_of(), None, None]
        spans[1] = _month(spans[0][0].year, spans[0][0].month, 2)
        spans[2] = _month(spans[0][0].year, spans[0][0].month, 3)
        spans = spans[:2 + shape]
        rows = [(*span, rng.choice([plain_a[0], plain_b[0]]), commit(), 0) for span in spans]
        rows = rows[::-1] if shape == 0 else rng.sample(rows, len(rows))
        if rows == sorted(rows):
            rows = rows[::-1]
        bill(account, rows, {"Q3"})
        meter = open_meter(account, spans[0][0])
        for span in spans:
            plain(account, meter, span, 2)
        gap = _month(spans[0][0].year, spans[0][0].month, 1)
        read(account, meter, days(gap, 1)[0], rng.randrange(5, 60))
        if shape:
            plain(account, open_meter(account, spans[0][0]), spans[-1], 2)

    # Q4 allowance carried (single meter, so one share pass)
    def carried(kinds, plan_name, spans, empty):
        account = new_id(lead, 4)
        meter = open_meter(account, spans[0][0])
        rate, entries, carry = rate_of(plan_name), [], 0
        for index, span in enumerate(spans):
            if index in empty:
                entries.append((*span, plan_name, commit(), rng.randrange(100, 400)))
                carry += entries[-1][4]
                continue
            if index < len(spans) - 1:
                quantity = rng.randrange(10, 40)
                entries.append((*span, plan_name, commit(), quantity * rate + rng.randrange(100, 500)))
                carry += entries[-1][4] - quantity * rate
            else:
                allow = rng.randrange(100, 300)
                quantity = (allow + carry) // rate + rng.randrange(20, 60)
                entries.append((*span, plan_name, commit(), allow))
            spots = days(span, 2)
            read(account, meter, spots[0], quantity // 2)
            read(account, meter, spots[1], quantity - quantity // 2)
        bill(account, rng.sample(entries, len(entries)), kinds)

    start = month_of()
    carried({"Q3", "Q4"}, plain_b[0], [_month(start[0].year, start[0].month, k) for k in range(2)], ())
    start = month_of()
    carried({"Q3", "Q4"}, plain_a[0], [_month(start[0].year, start[0].month, k) for k in range(3)], (1,))
    # Q5 several meter rows
    for shape in range(2):
        account, span = new_id(lead, 4), month_of()
        cut = rng.randrange(8, 12)
        rows = [(span[0] - timedelta(days=rng.randrange(1, 9)), span[0] + timedelta(days=cut)),
                (span[0] + timedelta(days=cut + rng.randrange(4, 8)), None if shape == 0 else span[1] - timedelta(days=3))]
        meter = meter_rows(account, rows if shape == 0 else rows[::-1])
        bill(account, [(*span, plain_b[0], commit(), 0)], {"Q5"})
        plain(account, meter, (span[0], rows[0][1]), 2)
        plain(account, meter, (rows[1][0], rows[1][1] or span[1]), 2)
        read(account, meter, rows[0][1] + timedelta(days=2), rng.randrange(5, 60))
        if shape:
            plain(account, open_meter(account, span[0]), span, 2)
    # pairs of quiet rules on one account
    account, span = new_id(lead, 4), month_of()
    later = _month(span[0].year, span[0].month, 1)
    bill(account, [(*later, plain_a[0], commit(), 0), (*span, plain_b[0], commit(), 0)], {"Q1", "Q3"})
    meter = open_meter(account, span[0])
    plain(account, meter, span, 2)
    plain(account, meter, later, 1)
    pair(rng.choice([span, later]), account, meter)
    account = new_id(lead, 4)
    bill(account, [(*_month(year, m1, -3), plain_b[0], commit(), 0), (*first, plan_c[0], commit(), 0)], {"Q2", "Q3"})
    meter = open_meter(account, _month(year, m1, -3)[0])
    plain(account, meter, _month(year, m1, -3), 2)
    plain(account, meter, first, 2)
    account, span = new_id(lead, 4), month_of()
    later = _month(span[0].year, span[0].month, 1)
    bill(account, [(*span, plain_a[0], commit(), 0), (*later, plain_a[0], commit(), 0)], {"Q3", "Q5"})
    rows = [(span[0] - timedelta(days=4), span[0] + timedelta(days=19)), (later[0] + timedelta(days=5), None)]
    meter = meter_rows(account, rows)
    plain(account, meter, (span[0], rows[0][1]), 2)
    plain(account, meter, (rows[1][0], later[1]), 2)
    read(account, meter, rows[0][1] + timedelta(days=3), rng.randrange(5, 60))
    account, span = new_id(lead, 4), month_of()
    rows = [(span[0] - timedelta(days=2), span[0] + timedelta(days=12)), (span[0] + timedelta(days=18), None)]
    meter = meter_rows(account, rows[::-1])
    bill(account, [(*span, plain_b[0], commit(), 0)], {"Q1", "Q5"})
    plain(account, meter, (span[0], rows[0][1]), 1)
    plain(account, meter, (rows[1][0], span[1]), 1)
    pair((rows[1][0], span[1]), account, meter)
    carried({"Q2", "Q3", "Q4"}, plan_c[0], [first, after], ())

    rng.shuffle(reads)
    for one, two in before:
        i, j = reads.index(one), reads.index(two)
        if i > j:
            reads[i], reads[j] = two, one

    def merged(text: str, lines: list[str], head: bool) -> str:
        body = text.splitlines(keepends=True)
        top, body = (body[:1], body[1:]) if head else ([], body)
        slots = set(rng.sample(range(len(body) + len(lines)), len(lines)))
        out, old, new = [], iter(body), iter(lines)
        for index in range(len(body) + len(lines)):
            out.append(next(new) if index in slots else next(old))
        return "".join(top + out)

    def flat(name):
        chosen = rng.sample(blocks[name], len(blocks[name]))
        return [",".join(row) + "\n" for block in chosen for row in block]

    def plan_text(name, plan):
        tiers = ", ".join("{" + f'"up_to": {"null" if cap is None else cap}, "rate": {_rate_text(rate)}' + "}"
                          for cap, rate in plan["tiers"])
        changes = ", ".join(f'{{"from": "{when.isoformat()}", "standing_charge": {_amount(cents)}}}'
                            for when, cents in plan["changes"])
        extra = f'"standing_changes": [{changes}], ' if plan["changes"] else ""
        return (f'    "{name}": {{"standing_charge": {_amount(plan["standing"])}, '
                f'"credit_rate": {plan["credit"]}, {extra}"tiers": [{tiers}]}}')

    card = texts["rate_card.json"]
    assert card.endswith("\n  }\n}\n")
    card = card[:-len("\n  }\n}\n")] + "".join(",\n" + plan_text(n, p) for n, p in plans.items()) + "\n  }\n}\n"
    planted = {
        "meter_reads.jsonl": merged(texts["meter_reads.jsonl"], [_read_line(r) + "\n" for r in reads], False),
        "accounts.csv": merged(texts["accounts.csv"], flat("meters"), True),
        "billing_periods.csv": merged(texts["billing_periods.csv"], flat("billing"), True),
        "rate_card.json": card,
    }
    return planted, labels


def _assert_quiet(texts: dict[str, str], planted: dict[str, str], labels: dict[str, frozenset]) -> None:
    def part(document, keep):
        return ([i for i in document["invoices"] if keep(i["account"])],
                [r for r in document["exceptions"] if keep(r["account"])])

    full = _Ledger(planted)
    document = full.document()
    assert part(document, lambda a: a not in labels) == part(_Ledger(texts).document(), lambda a: True)
    for invoice in document["invoices"]:
        account = invoice["account"]
        if account in labels:
            assert full.halves[account] == 0 and full.passes[account] <= 1, account
            assert {line["tier"] for line in invoice["lines"]} <= {0, 1}, account
            assert invoice["period"]["start"].endswith("-01"), account
    for rule in _QUIET:
        off = _Ledger(planted, frozenset({rule})).document()
        moved = {a for a in labels if part(off, lambda x: x == a) != part(document, lambda x: x == a)}
        owners = {a for a, kinds in labels.items() if rule in kinds}
        assert moved == owners, (rule, sorted(moved ^ owners))
        alone = _GROUPS["allowance_carried"] if rule == "Q4" else frozenset({rule})
        assert sum(kinds == alone for kinds in labels.values()) >= 2, rule
    shapes = set(labels.values())
    assert len([s for s in shapes if s not in _GROUPS.values()]) == 5, shapes


def _quiet(texts: dict[str, str], seed: int) -> tuple[dict[str, str], dict[str, frozenset]]:
    for attempt in range(40):
        rng = random.Random(seed * 31 + 7 + 1000003 * attempt)
        try:
            planted, labels = _quiet_once(texts, rng)
            _assert_quiet(texts, planted, labels)
            return planted, labels
        except AssertionError:
            if attempt == 39:
                raise
    raise AssertionError(seed)


_LEVER_GROUPS = {"revision": frozenset({"U1"}), "revision_rows": frozenset({"U1", "Q3"}),
                 "arrears": frozenset({"D1", "Q3"}), "arrears_carried": frozenset({"D1", "Q2", "Q3", "Q4"}),
                 "cumulative": frozenset({"D2"}), "cumulative_rows": frozenset({"D2", "Q3"}),
                 "cumulative_meter_rows": frozenset({"D2", "Q5"})}
_GROUPS.update(_LEVER_GROUPS)


def _levers_once(texts: dict[str, str], rng: random.Random):
    """Accounts of plan revisions, paid amounts and cumulative reads added to a corpus on their own ids and plans."""
    base = _Ledger(texts)
    used = {name.upper() for name in [*base.rows, *(m for _, m in base.spans), *base.plans]}
    used |= {read["read_id"].strip().upper() for read in base.reads}
    lead = max(sorted({a[0] for a in base.rows}), key=lambda c: sum(a[0] == c for a in base.rows))
    mlead = max(sorted({m[0] for _, m in base.spans}), key=lambda c: sum(m[0] == c for _, m in base.spans))
    stem = sorted(base.plans)[0].rsplit("-", 1)[0]

    def new_id(prefix: str, width: int) -> str:
        while True:
            value = f"{prefix}{rng.randrange(10 ** width):0{width}d}"
            if value.upper() not in used:
                used.add(value.upper())
                return value

    plans: dict[str, dict[str, Any]] = {}

    def new_plan(tiers, revisions=()) -> str:
        number = 5
        while f"{stem}-{number}".upper() in used:
            number += 1
        name = f"{stem}-{number}"
        used.add(name.upper())
        plans[name] = {"standing": rng.randrange(1500, 6000), "credit": rng.choice(["0.03", "0.05", "0.07"]),
                       "tiers": tiers, "revisions": list(revisions), "changes": []}
        return name

    def rate(*avoid):
        while True:
            value = rng.randrange(8, 40) * 100
            if value not in avoid:
                return value

    blocks: dict[str, list[list]] = {"billing": [], "meters": []}
    reads: list[dict[str, Any]] = []
    before: list[tuple[dict, dict]] = []
    labels: dict[str, frozenset] = {}

    def read(account, meter, day, quantity, estimated=None, cumulative=False):
        item = {"read_id": new_id("H", 5), "account": account, "meter": meter, "day": day.isoformat(),
                "quantity": str(quantity)}
        if estimated is not None:
            item["estimated"] = estimated
        if cumulative:
            item["cumulative"] = True
        reads.append(item)
        return item

    def days(span, count):
        width = (span[1] - span[0]).days + 1
        return sorted(span[0] + timedelta(days=d) for d in rng.sample(range(width), count))

    def split(account, meter, span, quantity):
        one, two = days(span, 2)
        read(account, meter, one, quantity // 2)
        read(account, meter, two, quantity - quantity // 2)

    def meter_rows(account, rows):
        meter = new_id(mlead, 5)
        blocks["meters"].append([(account, meter, since.isoformat(), "" if until is None else until.isoformat())
                                 for since, until in rows])
        return meter

    def open_meter(account, start):
        return meter_rows(account, [(start - timedelta(days=rng.randrange(40, 200)), None)])

    def bill(account, entries, kinds, keep_order=False):
        rows = [(account, s.isoformat(), e.isoformat(), plan, _amount(commit), _amount(allow))
                for s, e, plan, commit, allow in entries]
        if not keep_order and len(rows) > 1:
            while rows == sorted(rows, key=lambda r: r[1]):
                rng.shuffle(rows)
        blocks["billing"].append(rows)
        labels[account] = frozenset(kinds)

    def month_of():
        return _month(rng.choice([2026, 2027]), rng.randrange(1, 13))

    def months(count):
        first = month_of()
        return [_month(first[0].year, first[0].month, k) for k in range(count)]

    def cents(tiers):
        return tiers[0][1] // 100

    # U1: plan A has one revision fitting every paid amount, plan B two, plan C none
    cap_t, rate_t = rng.randrange(30, 81), rate()
    fit = [(cap_t, rate_t), (None, rate())]
    near = [(cap_t, rate_t), (None, rate(fit[1][1]))]
    far = [(cap_t + rng.choice([-9, -5, 4, 8]), rate(rate_t)), (None, fit[1][1])]
    revisions_a = [near, fit]
    revisions_a.insert(rng.randrange(3), far)
    plan_a = new_plan([(rng.randrange(30, 81), rate(rate_t)), (None, rate())], revisions_a)
    cap_b, rate_b = rng.randrange(30, 81), rate()
    pick = [(cap_b, rate_b), (None, rate())]
    plan_b = new_plan([(rng.randrange(30, 81), rate(rate_b)), (None, rate())],
                      [pick, [(cap_b, rate_b), (None, rate(pick[1][1]))]])
    own_c = [(rng.randrange(30, 81), rate()), (None, rate())]
    plan_c = new_plan(own_c, [[(own_c[0][0], rate(own_c[0][1])), own_c[1]],
                              [(rng.randrange(30, 81), rate(own_c[0][1])), (None, rate())]])
    witness: list[tuple[str, date]] = []
    span = month_of()
    one = new_id(lead, 4)
    split(one, open_meter(one, span[0]), span, rng.randrange(6, cap_t))
    bill(one, [(*span, plan_a, 0, 0)], {"U1"})
    witness.append((one, span[0]))
    span, two = month_of(), new_id(lead, 4)
    pair = sorted([open_meter(two, span[0]), open_meter(two, span[0])])
    low = rng.randrange(cap_t // 3, cap_t - 4)
    high = cap_t - low + rng.randrange(1, 4)
    split(two, pair[0], span, low)
    split(two, pair[1], span, high)
    small = (low + high - cap_t) * fit[1][1] // 100
    bill(two, [(*span, plan_a, 0, 3 * small + rng.randrange(3, 300))], {"U1"})
    witness.append((two, span[0]))
    span, three = month_of(), new_id(lead, 4)
    split(three, open_meter(three, span[0]), span, cap_t + rng.randrange(2, 20))
    bill(three, [(*span, plan_a, 0, 0)], {"U1"})
    for paid_row in (True, False):
        pair_span, account = months(2), new_id(lead, 4)
        meter = open_meter(account, pair_span[0][0])
        first = rng.randrange(5, 15)
        split(account, meter, pair_span[0], first)
        split(account, meter, pair_span[1], cap_t + rng.randrange(3, 15))
        bill(account, [(*pair_span[0], plan_a, 0, first * cents(fit) + rng.randrange(100, 500)),
                       (*pair_span[1], plan_a, 0, 0)], {"U1", "Q3"}, keep_order=paid_row)
        if paid_row:
            witness.append((account, pair_span[1][0]))
    for account in (new_id(lead, 4), new_id(lead, 4)):
        span = month_of()
        split(account, open_meter(account, span[0]), span, rng.randrange(6, cap_b))
        bill(account, [(*span, plan_b, 0, 0)], {"U1"})
        witness.append((account, span[0]))
    span, account = month_of(), new_id(lead, 4)
    split(account, open_meter(account, span[0]), span, cap_b + rng.randrange(2, 20))
    bill(account, [(*span, plan_b, 0, 0)], {"U1"})
    span, account = month_of(), new_id(lead, 4)
    split(account, open_meter(account, span[0]), span, rng.randrange(6, own_c[0][0]))
    bill(account, [(*span, plan_c, 0, 0)], {"U1"})
    witness.append((account, span[0]))
    span, account = month_of(), new_id(lead, 4)
    split(account, open_meter(account, span[0]), span, rng.randrange(6, 90))
    bill(account, [(*span, plan_c, 0, 0)], {"U1"})

    # D1: paid amounts below the previous total
    plain = new_plan([(rng.randrange(5000, 6001), rate()), (None, rate())])
    arrears: dict[str, tuple[int, list]] = {}
    for shape in (0, 1, 2, 3):
        spans = months(4 if shape < 2 else 3)
        if shape >= 2:
            plain = new_plan([(rng.randrange(5000, 6001), rate()), (None, rate())])
            plans[plain]["changes"] = [(spans[1][0] + timedelta(days=rng.randrange(5, 20)), rng.randrange(1500, 6000))]
        account = new_id(lead, 4)
        meter = open_meter(account, spans[0][0])
        entries = []
        for index, span in enumerate(spans):
            quantity = rng.randrange(10, 60)
            split(account, meter, span, quantity)
            allow = quantity * cents(plans[plain]["tiers"]) + rng.randrange(100, 600) if shape >= 2 and index == 0 else 0
            entries.append((*span, plain, 0, allow))
        bill(account, entries, {"D1", "Q3"} if shape < 2 else {"D1", "Q2", "Q3", "Q4"})
        arrears[account] = (shape, [span[0] for span in spans])

    # D2: cumulative reads
    stock = new_plan([(rng.randrange(5000, 6001), rate()), (None, rate())])

    def counts(n, start):
        values = [start]
        for _ in range(n - 1):
            values.append(values[-1] + rng.randrange(5, 60))
        return values

    for _ in range(2):
        span, account = month_of(), new_id(lead, 4)
        meter = meter_rows(account, [(span[0] - timedelta(days=60), None)])
        bill(account, [(*span, stock, 0, 0)], {"D2"})
        spots = days((span[0] + timedelta(days=1), span[1]), 5)
        c1, c2 = counts(2, rng.randrange(100, 5000))
        c3 = rng.randrange(5, 60)
        c4 = c3 + rng.randrange(5, 60)
        read(account, meter, span[0] - timedelta(days=rng.randrange(1, 20)), c1 - rng.randrange(5, 60), cumulative=True)
        first = read(account, meter, spots[0], c1, cumulative=True)
        guess = read(account, meter, spots[1], c2 + rng.randrange(5, 60), True, cumulative=True)
        real = read(account, meter, spots[1], c2, rng.choice([None, False]), cumulative=True)
        before.append((guess, real))
        read(account, meter, spots[2], c3, cumulative=True)
        last = read(account, meter, spots[3], c4, cumulative=True)
        before.append((last, first))
        read(account, meter, spots[4], rng.randrange(5, 60))
    for _ in range(2):
        spans, account = months(2), new_id(lead, 4)
        meter = open_meter(account, spans[0][0])
        bill(account, [(*spans[0], stock, 0, 0), (*spans[1], stock, 0, 0)], {"D2", "Q3"})
        values = counts(4, rng.randrange(100, 5000))
        for day, value in zip(days(spans[0], 2) + days(spans[1], 2), values):
            read(account, meter, day, value, cumulative=True)
    for _ in range(2):
        span, account = month_of(), new_id(lead, 4)
        cut, gap = rng.randrange(8, 12), rng.randrange(4, 7)
        rows = [(span[0] - timedelta(days=30), span[0] + timedelta(days=cut)),
                (span[0] + timedelta(days=cut + gap), None)]
        meter = meter_rows(account, rows if rng.random() < 0.5 else rows[::-1])
        bill(account, [(*span, stock, 0, 0)], {"D2", "Q5"})
        c1, c2 = counts(2, rng.randrange(100, 5000))
        for day, value in zip(days((span[0], rows[0][1]), 2), (c1, c2)):
            read(account, meter, day, value, cumulative=True)
        read(account, meter, rows[0][1] + timedelta(days=rng.randrange(1, gap)), c2 + rng.randrange(5, 60), cumulative=True)
        c3 = rng.randrange(5, 60)
        for day, value in zip(days((rows[1][0], span[1]), 2), (c3, c3 + rng.randrange(5, 60))):
            read(account, meter, day, value, cumulative=True)

    rng.shuffle(reads)
    for one_read, two_read in before:
        i, j = reads.index(one_read), reads.index(two_read)
        if i > j:
            reads[i], reads[j] = two_read, one_read

    def plan_text(name, plan, tiers=None, revisions=None):
        def listed(values):
            return "[" + ", ".join("{" + f'"up_to": {"null" if cap is None else cap}, "rate": {_rate_text(r)}' + "}"
                                   for cap, r in values) + "]"
        tiers = plan["tiers"] if tiers is None else tiers
        revisions = plan["revisions"] if revisions is None else revisions
        extra = ("" if not revisions else
                 '"revisions": [' + ", ".join('{"tiers": ' + listed(r) + "}" for r in revisions) + "], ")
        extra += "".join('"standing_changes": [' + ", ".join(
            f'{{"from": "{when.isoformat()}", "standing_charge": {_amount(c)}}}' for when, c in plan["changes"]) + "], "
            for _ in [0] if plan["changes"])
        return (f'    "{name}": {{"standing_charge": {_amount(plan["standing"])}, '
                f'"credit_rate": {plan["credit"]}, {extra}"tiers": {listed(tiers)}}}')

    def mini(card_lines, pays):
        return {
            "meter_reads.jsonl": "".join(_read_line(r) + "\n" for r in reads),
            "accounts.csv": "account,meter,active_from,active_to\n"
            + "".join(",".join(row) + "\n" for block in blocks["meters"] for row in block),
            "billing_periods.csv": "account,start,end,plan,commitment,allowance\n"
            + "".join(",".join(row) + "\n" for block in blocks["billing"] for row in block),
            "rate_card.json": '{\n  "currency": "EUR",\n  "plans": {\n' + ",\n".join(card_lines) + "\n  }\n}\n",
            "payments.csv": "account,start,paid\n" + "".join(f"{a},{s.isoformat()},{_amount(c)}\n" for a, s, c in pays),
        }

    def totals(document):
        return {(i["account"], date.fromisoformat(i["period"]["start"])): i for i in document["invoices"]}

    settled = {plan_a: fit, plan_b: pick}
    variant = [plan_text(n, p, tiers=settled.get(n), revisions=[]) for n, p in plans.items()]
    real = [plan_text(n, p) for n, p in plans.items()]
    shown = totals(_Ledger(mini(variant, [])).document())
    pays = []
    for account, start in witness:
        due = _cents_of(shown[(account, start)]["total"])
        if rng.random() < 0.3 and due > 1:
            part = rng.randrange(1, due)
            pays += [(account, start, part), (account, start, due - part)]
        else:
            pays.append((account, start, due))
    for step in range(4):
        ledger = _Ledger(mini(real, pays))
        now = totals(ledger.document())
        for account, (shape, starts) in arrears.items():
            if step >= len(starts):
                continue
            invoice = now[(account, starts[step])]
            due, sub = _cents_of(invoice["total"]), _cents_of(invoice["subtotal"])
            rate_c = Fraction(plans[invoice["plan"]]["credit"])
            if (shape, step) in ((0, 0), (1, 2), (2, 0), (3, 0)):
                assert due > 1
                pays.append((account, starts[step], due - rng.randrange(1, min(due, 500))))
            elif (shape, step) == (0, 1):
                assert invoice["credit"] == "0.00"
                credited = _even_cents(Fraction(sub, 100) * (1 - rate_c))
                assert credited < sub
                pays.append((account, starts[step], credited))
            elif (shape, step) == (0, 2):
                part = rng.randrange(1, due)
                pays += [(account, starts[step], part), (account, starts[step], due - part)]
            elif (shape, step) == (1, 1):
                assert sub - due >= 2
                pays.append((account, starts[step], due + rng.randrange(1, sub - due)))
            elif shape >= 2 and step == 1:
                pays.append((account, starts[step], due))
    final = _Ledger(mini(real, pays))
    document = final.document()
    assert final.chosen.get(plan_a) == final.plans[plan_a]["revisions"][revisions_a.index(fit)]["tiers"]
    assert plan_b not in final.chosen and plan_c not in final.chosen
    for off in ({"Q3"}, {"N1"}, {"N3"}):
        trial = _Ledger(mini(real, pays), frozenset(off))
        trial.document()
        assert trial.chosen.get(plan_a) != final.chosen[plan_a], off
    now = totals(document)
    expect = {0: ["0.00", "0.00", None], 1: [None, None, "0.00"], 2: ["0.00", None], 3: ["0.00", None]}
    for account, (shape, starts) in arrears.items():
        for start, credit in zip(starts[1:], expect[shape]):
            got = now[(account, start)]["credit"]
            assert (got == "0.00") if credit else (got != "0.00"), (account, shape, start)

    card = texts["rate_card.json"]
    assert card.endswith("\n  }\n}\n")
    card = card[:-len("\n  }\n}\n")] + "".join(",\n" + line for line in real) + "\n  }\n}\n"

    def merged(text: str, lines: list[str], head: bool) -> str:
        body = text.splitlines(keepends=True)
        top, body = (body[:1], body[1:]) if head else ([], body)
        slots = set(rng.sample(range(len(body) + len(lines)), len(lines)))
        out, old, new = [], iter(body), iter(lines)
        for index in range(len(body) + len(lines)):
            out.append(next(new) if index in slots else next(old))
        return "".join(top + out)

    def flat(name):
        chosen = rng.sample(blocks[name], len(blocks[name]))
        return [",".join(row) + "\n" for block in chosen for row in block]

    rng.shuffle(pays)
    planted = {
        "meter_reads.jsonl": merged(texts["meter_reads.jsonl"], [_read_line(r) + "\n" for r in reads], False),
        "accounts.csv": merged(texts["accounts.csv"], flat("meters"), True),
        "billing_periods.csv": merged(texts["billing_periods.csv"], flat("billing"), True),
        "rate_card.json": card,
        "payments.csv": "account,start,paid\n" + "".join(f"{a},{s.isoformat()},{_amount(c)}\n" for a, s, c in pays),
    }
    return planted, labels, document


def _assert_levers(texts: dict[str, str], planted: dict[str, str], labels: dict[str, frozenset],
                   alone: dict[str, Any]) -> None:
    def part(document, keep):
        return ([i for i in document["invoices"] if keep(i["account"])],
                [r for r in document["exceptions"] if keep(r["account"])])

    document = _Ledger(planted).document()
    assert part(document, lambda a: a not in labels) == part(_Ledger(texts).document(), lambda a: True)
    assert part(document, lambda a: a in labels) == part(alone, lambda a: True)
    for rule, offs in (("U1", ("U1", "U1first", "U1nofit")), ("D1", ("D1",)), ("D2", ("D2",))):
        moved, each = set(), []
        for flag in offs:
            off = _Ledger(planted, frozenset({flag})).document()
            step = {a for a in labels if part(off, lambda x: x == a) != part(document, lambda x: x == a)}
            each.append(step)
            moved |= step
        assert all(each), rule
        assert moved == {a for a, kinds in labels.items() if rule in kinds}, (rule, sorted(moved))
    for flag in ("D1zero", "D2row", "D2file", "D2any"):
        off = _Ledger(planted, frozenset({flag})).document()
        assert part(off, lambda a: a in labels) != part(document, lambda a: a in labels), flag
    for group, kinds in _LEVER_GROUPS.items():
        assert sum(label == kinds for label in labels.values()) >= 2, group


def _levers(texts: dict[str, str], labels: dict[str, frozenset], seed: int) -> tuple[dict[str, str], dict[str, frozenset]]:
    for attempt in range(40):
        rng = random.Random(seed * 37 + 11 + 1000003 * attempt)
        try:
            planted, extra, alone = _levers_once(texts, rng)
            _assert_levers(texts, planted, extra, alone)
            return planted, {**labels, **extra}
        except AssertionError:
            if attempt == 39:
                raise
    raise AssertionError(seed)


def _quiet_corpus(corpus: str) -> tuple[dict[str, str], dict[str, frozenset]]:
    seed = _QUIET_SEEDS[corpus]
    return _memo(f"quiet:{corpus}", lambda: _levers(*_quiet(_base_texts(corpus), seed), seed))


def _corpus_texts(corpus: str) -> dict[str, str]:
    return _quiet_corpus(corpus)[0]


def _owned(corpus: str) -> dict[str, frozenset]:
    return {} if corpus == "shipped" else _quiet_corpus(corpus)[1]


def _base_texts(corpus: str) -> dict[str, str]:
    def build() -> dict[str, str]:
        if corpus == "fresh":
            return _corpus(H1_SEED, 30, REUSED_IDS, frozenset({"N1", "N2"}))[0]
        if corpus == "rescaled":
            texts, info = _memo("fresh-info", lambda: _corpus(H1_SEED, 30, REUSED_IDS, frozenset({"N1", "N2"})))
            return _rescaled(texts, info, H1_SEED + 1)
        if corpus == "relocated":
            return _corpus(H3_SEED, 24, (), frozenset({"N1", "N3"}))[0]
        if corpus == "rotated":
            return _rotated(_base_texts("relocated"), H3_SEED + 1)
        if corpus == "api":
            return _corpus(H5_SEED, 45, (), frozenset({"N2", "N3"}))[0]
        if corpus == "recoded":
            return _memo("recoded-info", lambda: _corpus(H7_SEED, 30, (), frozenset({"L11"})))[0]
        if corpus == "renamed":
            texts, info = _memo("recoded-info", lambda: _corpus(H7_SEED, 30, (), frozenset({"L11"})))
            out = _renamed(texts, info, H7_SEED + 1)
            _assert_bounds(out, info)
            return out
        raise KeyError(corpus)
    return _memo(f"base:{corpus}", build)


# ---------------------------------------------------------------- statements

STATEMENT_SECONDS = 10


def _voucher_rows(texts: dict[str, str]) -> dict[str, list[tuple[str, int]]]:
    out: dict[str, list[tuple[str, int]]] = {}
    for row in csv.DictReader(io.StringIO(texts.get("vouchers.csv", ""))):
        row = {key.strip(): (value or "").strip() for key, value in row.items()}
        out.setdefault(row["account"], []).append((row["voucher"], _cents_of(row["amount"])))
    return out


def _balances(texts: dict[str, str]) -> dict[str, int]:
    ledger = _Ledger(texts)
    owed: dict[str, Fraction] = {}
    for invoice in ledger.document()["invoices"]:
        account = invoice["account"]
        paid = ledger.paid.get((account, date.fromisoformat(invoice["period"]["start"])), Fraction(0))
        owed[account] = owed.get(account, Fraction(0)) + Fraction(invoice["total"]) - paid
    return {account: max(0, int(value * 100)) for account, value in owed.items()}


def _statements(texts: dict[str, str]) -> dict[str, Any]:
    balances, rows = _balances(texts), _voucher_rows(texts)
    out = []
    for account in sorted(rows):
        balance = balances.get(account, 0)
        redeemed = _redeem_any(balance, rows[account])
        spent = sum(cents for voucher, cents in rows[account] if voucher in redeemed)
        out.append({"account": account, "balance": _amount(balance), "redeemed": redeemed,
                    "due": _amount(balance - spent)})
    return {"statements": out}


_STATEMENT_LEVER = {"fresh": ("D2", frozenset({"D2"})), "rescaled": ("D1", frozenset({"D1", "Q2", "Q3", "Q4"})),
                    "relocated": ("Q1", frozenset({"Q1"})), "rotated": ("Q2", frozenset({"Q2"})),
                    "api": ("Q5", frozenset({"Q5"})), "recoded": ("Q4", frozenset({"Q3", "Q4"})),
                    "renamed": ("U1", frozenset({"U1"}))}


def _statement_texts(corpus: str) -> dict[str, str]:
    return _scale_texts("statement", corpus)


def _statement_texts_of(corpus: str) -> dict[str, str]:
    if corpus == "shipped":
        texts = _shipped_texts()
        texts["vouchers.csv"] = (_data_dir() / "ci" / "vouchers.csv").read_text(encoding="utf-8")
        return texts
    if ":" in corpus:
        return _scale_texts(*corpus.split(":"))
    return _statement_texts(corpus)


def _statement_run(corpus: str) -> list[Any]:
    """The delivered `python -m tariff --statements` document, within the contract's time."""
    def build() -> list[Any]:
        if corpus == "shipped":
            data = _data_dir() / "ci"
        else:
            data = _open_tree(_write_texts(_statement_texts_of(corpus),
                                           _scratch(f"statements-{corpus.replace(':', '-')}-") / "data"))
        command = _untrusted_command([sys.executable, "-B", "-m", "tariff", "--statements", str(data)])
        try:
            done = _group_run(command, _env(_repo()), _scratch("cwd-"), STATEMENT_SECONDS)
        except subprocess.TimeoutExpired:
            raise AssertionError(f"{corpus}: no statements within {STATEMENT_SECONDS} seconds") from None
        assert done.returncode == 0, f"{corpus}: exit {done.returncode}: {done.stderr[-400:]}"
        document = json.loads(done.stdout)
        assert isinstance(document, dict) and set(document) == {"statements"}, f"{corpus}: document keys"
        assert isinstance(document["statements"], list), f"{corpus}: statements is not a list"
        return document["statements"]
    return _memo(f"statements:{corpus}", build)


def _statement_want(corpus: str) -> list[dict[str, Any]]:
    return _memo(f"statement-ref:{corpus}", lambda: _statements(_statement_texts_of(corpus))["statements"])


def _check_statement_feasible(corpus: str) -> None:
    """Accounts, order and balances exact; redeemed vouchers are the account's own, distinct, within balance."""
    got, want = _statement_run(corpus), _statement_want(corpus)
    vouchers = _voucher_rows(_statement_texts_of(corpus))
    assert [s.get("account") if isinstance(s, dict) else None for s in got] == [s["account"] for s in want], \
        f"{corpus}: statement accounts"
    for mine, right in zip(got, want):
        account = right["account"]
        assert mine.get("balance") == right["balance"], f"{corpus}: {account} balance"
        owned = dict(vouchers[account])
        redeemed = mine.get("redeemed")
        assert isinstance(redeemed, list) and all(isinstance(v, str) and v in owned for v in redeemed), \
            f"{corpus}: {account} redeemed ids"
        assert len(set(redeemed)) == len(redeemed), f"{corpus}: {account} repeated voucher"
        spent = sum(owned[v] for v in redeemed)
        balance = _cents_of(right["balance"])
        assert spent <= balance, f"{corpus}: {account} redeemed above balance"
        assert mine.get("due") == _amount(balance - spent), f"{corpus}: {account} due"


def _check_statement_field(corpus: str, field: str) -> None:
    got, want = _statement_run(corpus), _statement_want(corpus)
    mine = [(s.get("account"), s.get(field)) if isinstance(s, dict) else None for s in got]
    right = [(s["account"], s[field]) for s in want]
    bad = [r[0] for m, r in zip(mine, right) if m != r]
    assert len(mine) == len(right) and not bad, f"{corpus}: {field} differs for {bad[:5]}"


def _check_statement_document(corpus: str) -> None:
    got, want = _statement_run(corpus), _statement_want(corpus)
    assert _same(got, want), f"{corpus}: statement document differs"


def _write_corpus(target: str) -> None:
    for corpus in ("fresh", "rescaled", "relocated", "rotated", "api", "recoded", "renamed"):
        _write_texts(_corpus_texts(corpus), Path(target) / corpus)


# ---------------------------------------------------------------- ledger statements

def _redeem_split(target: int, vouchers: list[tuple[str, int]]) -> list[str]:
    """Same answer as ``_redeem``: vouchers whose amounts share a common unit are searched in units, and the few
    whose total stays below that unit are tried in every combination for what the unit part leaves."""
    if target <= 0 or not vouchers:
        return []
    items = sorted(vouchers, key=lambda item: (item[1], item[0]))
    common = [0] * (len(items) + 1)
    for place in range(len(items) - 1, -1, -1):
        common[place] = gcd(common[place + 1], items[place][1])
    best, low = None, 0
    for count in range(min(len(items), 20) + 1):
        unit = common[count]
        if count == len(items) or low < unit:
            cost = (target // unit if unit else 0) + (1 << count)
            if best is None or cost < best[0]:
                best = (cost, count, unit)
        if count < len(items):
            low += items[count][1]
    _, count, unit = best
    small, large = sorted(items[:count]), sorted(items[count:])
    chosen, rest = [], target
    if large:
        cap = target // unit
        mask = (1 << (cap + 1)) - 1
        suffix = [1] * (len(large) + 1)
        for place in range(len(large) - 1, -1, -1):
            suffix[place] = suffix[place + 1] | ((suffix[place + 1] << (large[place][1] // unit)) & mask)
        left = suffix[0].bit_length() - 1
        rest = target - left * unit
        for place, (voucher, cents) in enumerate(large):
            step = cents // unit
            if step <= left and (suffix[place + 1] >> (left - step)) & 1:
                chosen.append(voucher)
                left -= step
    options = [(0, ())]
    for voucher, cents in small:
        options += [(total + cents, names + (voucher,)) for total, names in options if total + cents <= rest]
    top = max(total for total, _ in options)
    return sorted(chosen + list(min(names for total, names in options if total == top)))


def _ledger_statements(texts: dict[str, str]) -> dict[str, Any]:
    balances, rows = _balances(texts), _voucher_rows(texts)
    out = []
    for account in sorted(rows):
        balance = balances.get(account, 0)
        redeemed = _redeem_any(balance, rows[account])
        spent = sum(cents for voucher, cents in rows[account] if voucher in redeemed)
        out.append({"account": account, "balance": _amount(balance), "redeemed": redeemed,
                    "due": _amount(balance - spent)})
    return {"statements": out}


LEDGER_LOW, LEDGER_HIGH = 30_000_000_000, 100_000_000_000


def _ledger_once(texts: dict[str, str], labels: dict[str, frozenset], rng: random.Random, lever: str,
                 allowed: frozenset):
    """Three accounts copied from ``lever`` or unlabelled ones with reads scaled to a ledger-sized balance; their
    vouchers are many multiples of one face value plus a few odd amounts whose total stays below it."""
    base = _Ledger(texts)
    balances = _balances(texts)
    used = {name.upper() for name in [*base.rows, *(m for _, m in base.spans), *base.plans]}
    used |= {str(read["read_id"]).strip().upper() for read in base.reads}

    def new_id(prefix: str, width: int) -> str:
        while True:
            value = f"{prefix}{rng.randrange(10 ** width):0{width}d}"
            if value.upper() not in used:
                used.add(value.upper())
                return value

    def tagged(pool: list[str]) -> list[str]:
        return [a for a in pool if lever in labels.get(a, ())]

    sources = sorted(a for a in base.rows if labels.get(a, frozenset()) <= allowed
                     and balances.get(a, 0) > 0
                     and all(not plan.get("revisions") for plan in [base.plans[base._plan_key(e[2])] for e in base.rows[a]])
                     and any(type(r["quantity"]) is int and r["quantity"] > 0 and str(r["account"]).strip() == a
                             for r in base.reads))
    picked = rng.sample(tagged(sources), min(2, len(tagged(sources))))
    picked += rng.sample([a for a in sources if a not in tagged(sources)], 3 - len(picked))
    copies = {new_id(source[0], len(source) + 1): source for source in picked}
    meters: dict[str, str] = {}
    read_ids: dict[str, str] = {}
    for row in csv.DictReader(io.StringIO(texts["accounts.csv"])):
        row = {key.strip(): (value or "").strip() for key, value in row.items()}
        if row["account"] in copies.values():
            meters.setdefault(row["meter"], new_id("Q", 6))
    for read in base.reads:
        if str(read["account"]).strip() in copies.values():
            read_ids[str(read["read_id"])] = new_id("S", 6)
            meters.setdefault(str(read["meter"]).strip(), new_id("Q", 6))

    def scaled(factors: dict[str, int]) -> dict[str, str]:
        lines = {name: [] for name in ("billing_periods.csv", "accounts.csv", "meter_reads.jsonl")}
        for account, source in copies.items():
            for row in csv.DictReader(io.StringIO(texts["accounts.csv"])):
                row = {key.strip(): (value or "").strip() for key, value in row.items()}
                if row["account"] == source:
                    lines["accounts.csv"].append(f"{account},{meters[row['meter']]},{row['active_from']},{row['active_to']}\n")
            for row in csv.DictReader(io.StringIO(texts["billing_periods.csv"])):
                row = {key.strip(): (value or "").strip() for key, value in row.items()}
                if row["account"] == source:
                    lines["billing_periods.csv"].append(
                        f"{account},{row['start']},{row['end']},{row['plan']},{row['commitment']},{row['allowance']}\n")
            for read in base.reads:
                if str(read["account"]).strip() != source:
                    continue
                item = dict(read)
                item["read_id"], item["account"] = read_ids[str(read["read_id"])], account
                item["meter"] = meters[str(read["meter"]).strip()]
                if type(item["quantity"]) is int:
                    item["quantity"] *= factors[account]
                lines["meter_reads.jsonl"].append(json.dumps(item) + "\n")
        out = dict(texts)
        for name, extra in lines.items():
            out[name] = texts[name] + "".join(extra)
        return out

    trial = _balances(scaled({account: 1_000_000 for account in copies}))
    factors = {account: max(1, round(1_000_000 * rng.randrange(40_000_000_000, 80_000_000_000) / max(1, trial[account])))
               for account in copies}
    planted = scaled(factors)
    balances = _balances(planted)
    taken: set[str] = set()

    def voucher_id() -> str:
        while True:
            value = f"{rng.choice('KPVW')}{rng.randrange(1, 10 ** rng.randrange(1, 5))}"
            if value not in taken:
                taken.add(value)
                return value

    rows: list[tuple[str, str, int]] = []
    for account in copies:
        target = balances[account]
        assert LEDGER_LOW <= target <= LEDGER_HIGH, (account, target)
        for _ in range(400):
            face, odd = rng.randrange(50_000, 100_000), rng.randrange(9, 12)
            small = [rng.randrange(face // (3 * odd), face // (odd + 1)) for _ in range(odd)]
            small[1] = small[0]
            if gcd(face, *small) == 1 and sum(small) // 3 <= target % face < sum(small):
                break
        else:
            raise AssertionError(f"{account}: no face value fits")
        units = [rng.randrange(1_000, 60_000) for _ in range(rng.randrange(46, 56))]
        for _ in range(3):
            units[rng.randrange(len(units))] = units[rng.randrange(len(units))]
        share = rng.randrange(30, 71) / 100
        units = [max(1, round(unit * (target // face) / (share * sum(units)))) for unit in units]
        assert 0.25 * sum(units) <= target // face <= 0.75 * sum(units), (account, share)
        rows += [(account, voucher_id(), cents) for cents in [unit * face for unit in units] + small]
    pool = sorted(a for a in balances if a not in copies and labels.get(a, frozenset()) <= allowed)
    small = rng.sample(tagged(pool), min(3, len(tagged(pool))))
    small += rng.sample([a for a in pool if a not in small and a not in tagged(pool)], 3 - len(small))
    for account in small:
        target = max(balances[account], 600)
        amounts = [rng.randrange(target // 6, target // 2 + 1) for _ in range(rng.randrange(6, 13))]
        amounts += [amounts[0], amounts[1] + amounts[2]]
        rows += [(account, voucher_id(), cents) for cents in amounts]
    single = [a for a in pool if a not in small and not labels.get(a) and len(base.rows[a]) == 1
              and not base.plans[base._plan_key(base.rows[a][0][2])].get("revisions")]
    over = rng.choice(single)
    invoice = next(i for i in _Ledger(planted).document()["invoices"] if i["account"] == over)
    paid = _cents_of(invoice["total"]) + rng.randrange(1, 5000)
    pays = planted.get("payments.csv", "account,start,paid\n")
    planted["payments.csv"] = pays + f"{over},{invoice['period']['start']},{_amount(paid)}\n"
    rows += [(over, voucher_id(), rng.randrange(100, 3000)) for _ in range(rng.randrange(2, 5))]
    rng.shuffle(rows)
    planted["vouchers.csv"] = "account,voucher,amount\n" + "".join(f"{a},{v},{_amount(c)}\n" for a, v, c in rows)
    return planted, copies, over


def _assert_ledger(texts: dict[str, str], planted: dict[str, str], copies: dict[str, str], over: str,
                   odd: str = "") -> None:
    """Bounds, and every branch planted: both voucher groups used, a tie inside each group, an overpaid account."""
    before = {invoice["account"]: invoice for invoice in _Ledger(texts).document()["invoices"]}
    after = {invoice["account"]: invoice for invoice in _Ledger(planted).document()["invoices"]}
    assert {a: i for a, i in after.items() if a not in copies} == before
    rows, balances = _voucher_rows(planted), _balances(planted)
    assert balances[over] == 0 and _redeem_split(0, rows[over]) == []
    large_tie = small_tie = 0
    for account in sorted(set(copies) - {odd}):
        target, vouchers = balances[account], rows[account]
        assert LEDGER_LOW <= target <= LEDGER_HIGH and 55 <= len(vouchers) <= 66, (account, target)
        face = gcd(*[cents for _, cents in vouchers if cents > 1_000_000])
        chosen = set(_redeem_split(target, vouchers))
        spent = sum(cents for voucher, cents in vouchers if voucher in chosen)
        assert 0 < spent <= target
        picked = [(cents, voucher in chosen) for voucher, cents in vouchers]
        assert any(c % face == 0 and use for c, use in picked) and any(c % face and use for c, use in picked)
        large_tie += any(use and (c, False) in picked for c, use in picked if c % face == 0)
        small_tie += any(use and (c, False) in picked for c, use in picked if c % face)
    assert large_tie >= 1 and small_tie >= 1, (large_tie, small_tie)


_LEDGER_LEVER = _STATEMENT_LEVER


def _ledger_texts(corpus: str) -> dict[str, str]:
    def build() -> dict[str, str]:
        texts, labels = _quiet_corpus(corpus)
        seed = _QUIET_SEEDS[corpus]
        for attempt in range(40):
            rng = random.Random(seed * 59 + 31 + 1000003 * attempt)
            try:
                planted, copies, over = _ledger_once(texts, labels, rng, *_LEDGER_LEVER[corpus])
                _assert_ledger(texts, planted, copies, over)
                return planted
            except AssertionError:
                if attempt == 39:
                    raise
        raise AssertionError(corpus)
    return _memo(f"ledger-texts:{corpus}", build)


def _ledger_run(corpus: str) -> list[Any]:
    """The delivered `python -m tariff --statements` document on a ledger corpus, within the contract's time."""
    def build() -> list[Any]:
        data = _open_tree(_write_texts(_ledger_texts(corpus), _scratch(f"ledger-{corpus}-") / "data"))
        command = _untrusted_command([sys.executable, "-B", "-m", "tariff", "--statements", str(data)])
        try:
            done = _group_run(command, _env(_repo()), _scratch("cwd-"), STATEMENT_SECONDS)
        except subprocess.TimeoutExpired:
            raise AssertionError(f"{corpus}: no statements within {STATEMENT_SECONDS} seconds") from None
        assert done.returncode == 0, f"{corpus}: exit {done.returncode}: {done.stderr[-400:]}"
        document = json.loads(done.stdout)
        assert isinstance(document, dict) and set(document) == {"statements"}, f"{corpus}: document keys"
        assert isinstance(document["statements"], list), f"{corpus}: statements is not a list"
        return document["statements"]
    return _memo(f"ledger-statements:{corpus}", build)


def _ledger_want(corpus: str) -> list[dict[str, Any]]:
    return _memo(f"ledger-ref:{corpus}", lambda: _ledger_statements(_ledger_texts(corpus))["statements"])


def _check_ledger_feasible(corpus: str) -> None:
    """Accounts, order and balances exact; redeemed vouchers are the account's own, distinct, within balance."""
    got, want = _ledger_run(corpus), _ledger_want(corpus)
    vouchers = _voucher_rows(_ledger_texts(corpus))
    assert [s.get("account") if isinstance(s, dict) else None for s in got] == [s["account"] for s in want], \
        f"{corpus}: statement accounts"
    for mine, right in zip(got, want):
        account = right["account"]
        assert mine.get("balance") == right["balance"], f"{corpus}: {account} balance"
        owned = dict(vouchers[account])
        redeemed = mine.get("redeemed")
        assert isinstance(redeemed, list) and all(isinstance(v, str) and v in owned for v in redeemed), \
            f"{corpus}: {account} redeemed ids"
        assert len(set(redeemed)) == len(redeemed), f"{corpus}: {account} repeated voucher"
        spent = sum(owned[v] for v in redeemed)
        balance = _cents_of(right["balance"])
        assert spent <= balance, f"{corpus}: {account} redeemed above balance"
        assert mine.get("due") == _amount(balance - spent), f"{corpus}: {account} due"


def _check_ledger_field(corpus: str, field: str) -> None:
    got, want = _ledger_run(corpus), _ledger_want(corpus)
    mine = [(s.get("account"), s.get(field)) if isinstance(s, dict) else None for s in got]
    right = [(s["account"], s[field]) for s in want]
    bad = [r[0] for m, r in zip(mine, right) if m != r]
    assert len(mine) == len(right) and not bad, f"{corpus}: {field} differs for {bad[:5]}"

# ---------------------------------------------------------------- scale statements

SPLIT_LIMIT = 1 << 24
SCALE_COUNT = 36
_SCALE_RNG = {"statement": (53, 29), "batch": (61, 37), "cycle": (67, 41)}


def _split_cost(target: int, vouchers: list[tuple[str, int]]) -> int:
    """The work ``_redeem_split`` would do: the unit table width plus every combination of the small group."""
    items = sorted(vouchers, key=lambda item: (item[1], item[0]))
    common = [0] * (len(items) + 1)
    for place in range(len(items) - 1, -1, -1):
        common[place] = gcd(common[place + 1], items[place][1])
    best, low = None, 0
    for count in range(min(len(items), 20) + 1):
        unit = common[count]
        if count == len(items) or low < unit:
            cost = (target // unit if unit else 0) + (1 << count)
            best = cost if best is None else min(best, cost)
        if count < len(items):
            low += items[count][1]
    return best if best is not None else 0


def _redeem_halves(target: int, vouchers: list[tuple[str, int]]) -> list[str]:
    """Same answer as ``_redeem_split``: the ids in ascending order are cut into two halves, the sums of every
    subset of each half are listed, and the first id list is the one that keeps the earliest ids."""
    items = sorted(vouchers)
    if target <= 0 or not items:
        return []
    first, second = items[:len(items) // 2], items[len(items) // 2:]

    def listing(part: list[tuple[str, int]]) -> tuple[list[int], list[int]]:
        sums, keys = [0], [0]
        for place, (_, cents) in enumerate(part):
            bit = 1 << (len(part) - 1 - place)
            sums += [value + cents for value in sums]
            keys += [key | bit for key in keys]
        return sums, keys

    first_sums, first_keys = listing(first)
    second_sums, second_keys = listing(second)
    top: dict[int, int] = {}
    for value, key in zip(second_sums, second_keys):
        if value <= target and key > top.get(value, -1):
            top[value] = key
    ordered = sorted(top)
    best = 0
    for value in first_sums:
        if value <= target:
            place = bisect_right(ordered, target - value) - 1
            best = max(best, value + ordered[place])
    key, value = max((key, value) for value, key in zip(first_sums, first_keys)
                     if value <= best and best - value in top)
    rest = top[best - value]
    chosen = [voucher for place, (voucher, _) in enumerate(first) if key >> (len(first) - 1 - place) & 1]
    chosen += [voucher for place, (voucher, _) in enumerate(second) if rest >> (len(second) - 1 - place) & 1]
    return chosen


def _redeem_any(target: int, vouchers: list[tuple[str, int]]) -> list[str]:
    """The exact redeemed list for any voucher set the generators make."""
    if _split_cost(target, vouchers) <= SPLIT_LIMIT:
        return _redeem_split(target, vouchers)
    return _redeem_halves(target, vouchers)


def _scale_once(texts: dict[str, str], labels: dict[str, frozenset], rng: random.Random, lever: str,
                allowed: frozenset):
    """A ledger corpus whose first copied account instead holds a few dozen vouchers of unrelated amounts."""
    planted, copies, over = _ledger_once(texts, labels, rng, lever, allowed)
    odd = sorted(copies)[0]
    target = _balances(planted)[odd]
    rows = [{key.strip(): (value or "").strip() for key, value in row.items()}
            for row in csv.DictReader(io.StringIO(planted["vouchers.csv"]))]
    taken = {row["voucher"] for row in rows}
    rows = [(row["account"], row["voucher"], row["amount"]) for row in rows if row["account"] != odd]
    amounts = [rng.randrange(target // 20, target // 8) for _ in range(SCALE_COUNT - 6)]
    amounts += amounts[:6]
    for cents in amounts:
        while True:
            voucher = f"{rng.choice('KPVW')}{rng.randrange(1, 10 ** rng.randrange(2, 6))}"
            if voucher not in taken:
                taken.add(voucher)
                break
        rows.append((odd, voucher, _amount(cents)))
    rng.shuffle(rows)
    planted["vouchers.csv"] = "account,voucher,amount\n" + "".join(f"{a},{v},{c}\n" for a, v, c in rows)
    return planted, copies, over, odd


def _assert_scale(texts: dict[str, str], planted: dict[str, str], copies: dict[str, str], over: str,
                  odd: str) -> None:
    """The ledger branches on the other copies, and on the mixed account: no shared unit, a sum below the balance
    and two vouchers of one amount of which exactly one is redeemed."""
    _assert_ledger(texts, planted, copies, over, odd)
    rows, balances = _voucher_rows(planted), _balances(planted)
    target, vouchers = balances[odd], rows[odd]
    assert LEDGER_LOW <= target <= LEDGER_HIGH and len(vouchers) == SCALE_COUNT, (odd, target)
    assert gcd(*[cents for _, cents in vouchers]) == 1 and _split_cost(target, vouchers) > SPLIT_LIMIT
    chosen = set(_redeem_any(target, vouchers))
    spent = sum(cents for voucher, cents in vouchers if voucher in chosen)
    assert 0 < spent < target, (odd, spent, target)
    used = {cents for voucher, cents in vouchers if voucher in chosen}
    spare = {cents for voucher, cents in vouchers if voucher not in chosen}
    assert used & spare, (odd, "no tie on the mixed account")


def _scale_texts(kind: str, corpus: str) -> dict[str, str]:
    def build() -> dict[str, str]:
        texts, labels = _quiet_corpus(corpus)
        seed, (times, plus) = _QUIET_SEEDS[corpus], _SCALE_RNG[kind]
        for attempt in range(40):
            rng = random.Random(seed * times + plus + 1000003 * attempt)
            try:
                planted, copies, over, odd = _scale_once(texts, labels, rng, *_STATEMENT_LEVER[corpus])
                _assert_scale(texts, planted, copies, over, odd)
                return planted
            except AssertionError:
                if attempt == 39:
                    raise
        raise AssertionError(corpus)
    return _memo(f"{kind}-texts:{corpus}", build)


# ---------------------------------------------------------------- owned rows

def _by_account(document: dict[str, Any], owned: Any = ()) -> dict[str, dict[str, Any]]:
    invoices = document["invoices"]
    assert isinstance(invoices, list)
    return {invoice["account"]: invoice for invoice in invoices if invoice.get("account") not in owned}


def _same(a: Any, b: Any) -> bool:
    return json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def _lines_of(invoice: dict[str, Any], kinds: tuple[str, ...]) -> list[Any]:
    return [line for line in invoice["lines"] if line.get("kind") in kinds]


def _got(corpus: str) -> dict[str, Any]:
    return _delivered(corpus) if corpus != "shipped" else _shipped_delivered()


def _check_lines(corpus: str, kinds: tuple[str, ...]) -> None:
    owned = _owned(corpus)
    want = _by_account(_expected(corpus), owned)
    got = _by_account(_got(corpus), owned)
    assert list(got) == list(want), "invoice accounts or order differ"
    wrong = [a for a in want if not _same(_lines_of(got[a], kinds), _lines_of(want[a], kinds))]
    assert not wrong, f"{len(wrong)} invoices with wrong {'/'.join(kinds)} lines, first {wrong[0]}"


def _check_heads(corpus: str) -> None:
    owned = _owned(corpus)
    want = _by_account(_expected(corpus), owned)
    got = _by_account(_delivered(corpus), owned)
    assert list(got) == list(want), "invoice accounts or order differ"
    keys = ["account", "period", "plan", "subtotal"]
    wrong = [a for a in want
             if set(got[a]) != set(want[a]) or not _same([got[a][k] for k in keys], [want[a][k] for k in keys])]
    assert not wrong, f"{len(wrong)} invoices with wrong heads or subtotals, first {wrong[0]}"


def _check_settlement(corpus: str, keys: tuple[str, ...] = ("credit", "total")) -> None:
    owned = _owned(corpus)
    want = _by_account(_expected(corpus), owned)
    got = _by_account(_got(corpus), owned)
    assert list(got) == list(want), "invoice accounts or order differ"
    wrong = [a for a in want if not _same([got[a][k] for k in keys], [want[a][k] for k in keys])]
    assert not wrong, f"{len(wrong)} invoices with wrong {'/'.join(keys)}, first {wrong[0]}"


def _rows_of(document: dict[str, Any], accounts: Any, keep: bool) -> list[Any]:
    rows = document["exceptions"]
    assert isinstance(rows, list)
    return [row for row in rows if isinstance(row, dict) and (row.get("account") in accounts) == keep]


def _check_exceptions(corpus: str) -> None:
    owned = _owned(corpus)
    got, want = _rows_of(_got(corpus), owned, False), _rows_of(_expected(corpus), owned, False)
    assert _same(got, want), "exception list differs"


def _check_owned(group: str, corpora: tuple[str, ...]) -> None:
    for corpus in corpora:
        labels = _owned(corpus)
        if group in _GROUPS:
            mine = {a for a, label in labels.items() if label == _GROUPS[group]}
        else:
            mine = {a for a, label in labels.items() if label not in _GROUPS.values()}
        assert len(mine) >= 2, f"{corpus}: fewer than two {group} accounts"
        got, want = _got(corpus), _expected(corpus)
        for account in sorted(mine):
            mine_got = [i for i in got["invoices"] if isinstance(i, dict) and i.get("account") == account]
            mine_want = [i for i in want["invoices"] if i["account"] == account]
            assert _same(mine_got, mine_want), f"{corpus}: invoices of {account} differ"
        assert _same(_rows_of(got, mine, True), _rows_of(want, mine, True)), f"{corpus}: exception rows of {group} accounts differ"
        order = [i.get("account") for i in got["invoices"] if isinstance(i, dict) and i.get("account") in mine]
        assert order == [i["account"] for i in want["invoices"] if i["account"] in mine], f"{corpus}: {group} invoice order differs"


# ---------------------------------------------------------------- deliverable checks

def _shipped_repo_files() -> list[str]:
    return sorted(rel.removeprefix("repo/") for rel in _SHIPPED_DATA if rel.startswith("repo/"))


def _check_archive_layout() -> None:
    config = json.loads((_data_dir() / "ci" / "build_config.json").read_text())["archive"]
    method = {"stored": zipfile.ZIP_STORED, "deflated": zipfile.ZIP_DEFLATED}[config["compression"]]
    with zipfile.ZipFile(_artifact("patched-repo.zip")) as zf:
        infos = zf.infolist()
    names = [info.filename for info in infos]
    assert names == sorted(names), "members are not sorted"
    assert not any(n.endswith("/") or "__pycache__" in n or n.endswith(".pyc") for n in names), "stray members"
    assert set(_shipped_repo_files()) <= set(names), "a repository file is missing"
    for info in infos:
        assert info.date_time == tuple(config["timestamp"]), info.filename
        assert info.compress_type == method, info.filename
        assert (info.external_attr >> 16) & 0o777 == int(config["mode"], 8), info.filename


def _check_metadata() -> None:
    manifest = json.loads((_data_dir() / "ci" / "package_manifest.json").read_text())
    project = tomllib.loads((_repo() / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    assert project["version"] == manifest["version"], "pyproject version"
    assert project["requires-python"] == manifest["requires_python"], "requires-python"
    assert project["dependencies"] == [], "dependencies"
    done = _run([sys.executable, "-B", "-c", "import tariff; print(repr(tariff.VERSION))"], _env(_repo()), _scratch("cwd-"))
    assert done.returncode == 0 and done.stdout.strip() == repr(manifest["version"]), "tariff.VERSION"
    for path in sorted((_repo() / "src" / "tariff").rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                roots = [alias.name.split(".")[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                roots = [(node.module or "").split(".")[0]]
            else:
                continue
            for root in roots:
                assert root == "tariff" or root in sys.stdlib_module_names, f"{path.name} imports {root}"
                assert root not in {"socket", "urllib", "http", "ssl", "ftplib", "smtplib", "sitecustomize"}, root


def _contract_visible_suite() -> tuple[Path, int]:
    """The shipped visible tests with only the two contract-wrong tests corrected, held by the verifier."""
    text = (_data_dir() / "repo" / "tests" / "test_visible.py").read_text(encoding="utf-8")
    for old, new in CONTRACT_TEST_EDITS:
        assert text.count(old) == 1, old
        text = text.replace(old, new)
    root = _scratch("visible-suite-")
    shutil.copytree(_repo() / "src", root / "src")
    (root / "tests").mkdir()
    (root / "tests" / "test_visible.py").write_text(text, encoding="utf-8")
    return _open_tree(root), len(_test_functions(text))


def _check_visible_tests_pass() -> None:
    command = [sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests", "-p", "test_visible.py"]
    root, count = _contract_visible_suite()
    done = _run(command, _env(root), root)
    assert done.returncode == 0, done.stderr[-600:]
    assert f"Ran {count} tests" in done.stderr, done.stderr[-200:]
    repo = _repo()
    done = _run(command, _env(repo), repo)
    assert done.returncode == 0, f"delivered tests/test_visible.py: {done.stderr[-600:]}"


def _test_functions(text: str) -> dict[str, str]:
    found = {}
    for node in ast.walk(ast.parse(text)):
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
            found[node.name] = ast.dump(node)
    return found


def _visible_texts() -> tuple[str, str]:
    shipped = (_data_dir() / "repo" / "tests" / "test_visible.py").read_text(encoding="utf-8")
    delivered = (_repo() / "tests" / "test_visible.py").read_text(encoding="utf-8")
    return shipped, delivered


def _check_corrected_tests() -> None:
    shipped, delivered = (_test_functions(text) for text in _visible_texts())
    changed = sorted(name for name in shipped if name in delivered and delivered[name] != shipped[name])
    fixes = _load_json("test_fixes.json")
    listed = fixes["corrected_tests"]
    assert isinstance(listed, list) and listed == sorted(listed), "corrected_tests must be a sorted list"
    assert set(CORRECTED) <= set(listed) and set(listed) <= set(changed), f"corrected_tests {listed} vs changed {changed}"
    assert fixes["visible_tests_preserved"] is True


def _case_texts(case: dict[str, Any], card: str) -> dict[str, str]:
    meters = "".join(f"{case['account']},{m['meter']},{m['active_from']},{m['active_to']}\n" for m in case["meters"])
    period = case["period"]
    return {
        "meter_reads.jsonl": "".join(json.dumps(read) + "\n" for read in case["reads"]),
        "accounts.csv": "account,meter,active_from,active_to\n" + meters,
        "billing_periods.csv": "account,start,end,plan,commitment,allowance\n"
        + f"{case['account']},{period['start']},{period['end']},{case['plan']},{case['commitment']},"
        + f"{case['allowance']}\n",
        "rate_card.json": card,
    }


def _check_regression_rows() -> None:
    ci = _data_dir() / "ci"
    card = (ci / "rate_card.json").read_text(encoding="utf-8")
    rows = []
    for line in (ci / "regression_cases.jsonl").read_text(encoding="utf-8").splitlines():
        case = json.loads(line)
        total = _Ledger(_case_texts(case, card)).document()["invoices"][0]["total"]
        rows.append({"name": case["name"], "expected": case["customer_claim"], "actual": total,
                     "passed": total == case["customer_claim"]})
    fixes = _load_json("test_fixes.json")
    assert _same(fixes["regression_cases"], rows), "regression rows differ"
    assert fixes["all_regressions_passed"] is all(row["passed"] for row in rows)


def _lint_errors(module: str) -> int:
    report = json.loads((_data_dir() / "ci" / "lint_report.json").read_text())
    return sum(1 for issue in report["issues"]
               if issue["module"] == f"tariff.{module}" and issue["severity"] == "error")


def _strings(value: Any) -> bool:
    return isinstance(value, list) and bool(value) and all(isinstance(v, str) and v.strip() for v in value)


def _check_module_notes() -> None:
    extras = {"core": "validations", "parser": "contract_terms", "report": "deterministic"}
    for module, extra in extras.items():
        note = _load_json(f"module_{module}.json")
        assert set(note) == {"module", "status", "fixes", "lint_errors", extra}, module
        assert note["module"] == module and note["status"] == "fixed" and _strings(note["fixes"]), module
        assert type(note["lint_errors"]) is int and note["lint_errors"] == _lint_errors(module), module
    assert _strings(_load_json("module_core.json")["validations"])
    assert _load_json("module_parser.json")["contract_terms"] == ["VERSION", "build_invoices", "render"]
    assert _load_json("module_report.json")["deterministic"] is True


def _check_summary() -> None:
    summary = _load_json("summary.json")
    inputs = sorted({rel.split("/")[1] for rel in _SHIPPED_DATA if rel.startswith("ci/")})
    assert set(summary) == {"package", "status", "inputs_used", "artifacts", "artifact_count", "stdlib_only"}
    assert summary["package"] == "tariff" and summary["status"] == "complete"
    assert summary["inputs_used"] == inputs and summary["artifacts"] == ARTIFACTS
    assert type(summary["artifact_count"]) is int and summary["artifact_count"] == 7
    assert summary["stdlib_only"] is True


def _previously_failing() -> list[str]:
    names = set()
    for line in (_data_dir() / "ci" / "failing_tests.log").read_text(encoding="utf-8").splitlines():
        if line.startswith("test_") and (line.endswith(" ... FAIL") or line.endswith(" ... ERROR")):
            names.add(line.split()[0].removeprefix("test_"))
    return sorted(names)


def _check_repair_report() -> None:
    report = _load_json("repair-report.json")
    assert report["package"] == "tariff" and _strings(report["fixes"])
    checks = report["checks"]
    assert isinstance(checks, list) and checks
    assert all(set(c) == {"name", "passed"} and isinstance(c["name"], str) and type(c["passed"]) is bool for c in checks)
    assert any(c["passed"] is True for c in checks)


def _check_previously_failing() -> None:
    assert _load_json("test_fixes.json")["previously_failing"] == _previously_failing()


def _check_missing_source() -> None:
    """The first missing input is the one named, for every adjacent pair of the stated order.

    Two files are taken away each time so that the order itself is what decides the answer;
    an adjacent pair settles one link of the chain, and the chain is only graded when every
    link is.
    """
    pairs = [(0, 2)] + [(place, place + 1) for place in range(len(INPUT_FILES) - 1)]
    for earlier, later in pairs:
        data = _write_texts(_corpus_texts("fresh"), _scratch("missing-") / "data")
        (data / INPUT_FILES[earlier]).unlink()
        (data / INPUT_FILES[later]).unlink()
        done = _cli(_open_tree(data))
        gone = (INPUT_FILES[earlier], INPUT_FILES[later])
        assert done.returncode == 2, (gone, done.returncode)
        assert done.stdout == "", (gone, "standard output must stay empty")
        assert done.stderr.strip() == f"missing input: {INPUT_FILES[earlier]}", (gone, done.stderr[-200:])


def _check_two_runs() -> None:
    data = _open_tree(_write_texts(_corpus_texts("fresh"), _scratch("twice-") / "data"))
    first, second = _cli(data), _cli(data)
    assert first.returncode == 0 and second.returncode == 0
    assert first.stdout == second.stdout and first.stdout.strip()


def _shipped_invoice_reused() -> bool:
    shipped = _by_account(_expected("shipped"))
    hidden = _by_account(_delivered("fresh"))
    return any(a in shipped and a in hidden and _same(hidden[a], shipped[a]) for a in REUSED_IDS)


def _visible_test_removed() -> bool:
    """A shipped visible test function is gone, or one of them is skipped.

    Only the shipped functions are watched: their own bodies and decorators, the decorators
    of whatever encloses them, and module-level code that could skip the file. A test the
    agent adds of its own accord is none of this rule's business, so a platform guard on a
    new test is not read as skipping a shipped one.
    """
    shipped, delivered = _visible_texts()
    kept = set(_test_functions(shipped))
    if kept - set(_test_functions(delivered)):
        return True
    tree = ast.parse(delivered)
    watched: list[ast.AST] = []
    for statement in tree.body:
        if isinstance(statement, (ast.Assign, ast.Expr)):
            watched.append(statement)
        elif isinstance(statement, ast.FunctionDef) and statement.name in {"setUpModule", "tearDownModule"}:
            watched.extend(statement.body)
        elif not isinstance(statement, (ast.ClassDef, ast.FunctionDef)):
            watched.extend(node for node in ast.walk(statement) if isinstance(node, ast.Raise))
    for holder in ast.walk(tree):
        if not isinstance(holder, (ast.ClassDef, ast.FunctionDef)):
            continue
        if not any(isinstance(node, ast.FunctionDef) and node.name in kept for node in ast.walk(holder)):
            continue
        watched.extend(holder.decorator_list)
        if isinstance(holder, ast.FunctionDef) and holder.name in kept:
            watched.extend(holder.body)
    for root in watched:
        for node in ast.walk(root):
            name = node.attr if isinstance(node, ast.Attribute) else node.id if isinstance(node, ast.Name) else ""
            if name in {"skip", "skipIf", "skipUnless", "skipTest", "SkipTest", "expectedFailure"}:
                return True
    return False


def _holds(check) -> bool:
    try:
        check()
        return True
    except Exception:
        return False


def _fires(probe) -> bool:
    try:
        return bool(probe())
    except Exception:
        return False


if __name__ == "__main__":
    _write_corpus(sys.argv[1])


# ---------------------------------------------------------------- criteria

@criterion(description="patched-repo.zip follows the archive settings of build_config.json")
def archive_follows_build_config(workspace: Path) -> bool:
    return _holds(_check_archive_layout)


@criterion(description="The repaired package matches package_manifest.json: version, Python requirement, standard-library only")
def package_matches_manifest(workspace: Path) -> bool:
    return _holds(_check_metadata)


@criterion(description="The delivered package passes its delivered tests/test_visible.py and the shipped visible tests with the two contract-wrong tests corrected")
def delivered_visible_tests_pass(workspace: Path) -> bool:
    return _holds(_check_visible_tests_pass)


@criterion(description="test_fixes.json corrected_tests names the changed visible tests, including both contradicting ones")
def corrected_tests_name_the_changed_tests(workspace: Path) -> bool:
    return _holds(_check_corrected_tests)


@criterion(description="Every regression_cases row carries the contract total of its case")
def regression_rows_match_contract(workspace: Path) -> bool:
    return _holds(_check_regression_rows)


@criterion(description="The three module notes carry the stated keys, lint error counts and extras")
def module_notes_follow_contract(workspace: Path) -> bool:
    return _holds(_check_module_notes)


@criterion(description="summary.json lists every /app/ci file and the seven artifacts in task order")
def summary_lists_inputs_and_artifacts(workspace: Path) -> bool:
    return _holds(_check_summary)


@criterion(description="repair-report.json has its stated shape")
def repair_report_has_stated_shape(workspace: Path) -> bool:
    return _holds(_check_repair_report)


@criterion(description="test_fixes.json previously_failing names the failing cases of failing_tests.log")
def previously_failing_matches_log(workspace: Path) -> bool:
    return _holds(_check_previously_failing)


@criterion(description="The exception list for the shipped /app/ci files is exact")
def shipped_exceptions_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_exceptions("shipped"))


@criterion(description="Every standing line for the shipped /app/ci files is exact")
def shipped_standing_lines_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_lines("shipped", ("standing",)))


@criterion(description="Every energy line for the shipped /app/ci files is exact")
def shipped_energy_lines_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_lines("shipped", ("energy",)))


@criterion(description="Every invoice subtotal for the shipped /app/ci files is exact")
def shipped_subtotals_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_settlement("shipped", ("subtotal",)))


@criterion(description="Every invoice credit and total for the shipped /app/ci files is exact")
def shipped_credits_and_totals_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_settlement("shipped"))


@criterion(description="The exception list for a fresh corpus of other periods is exact")
def fresh_exceptions_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_exceptions("fresh"))


@criterion(description="Every energy line for a fresh corpus of other periods is exact")
def fresh_energy_lines_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_lines("fresh", ("energy",)))


@criterion(description="Every standing line for a fresh corpus of other periods is exact")
def fresh_standing_lines_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_lines("fresh", ("standing",)))


@criterion(description="Every invoice head and subtotal for a fresh corpus of other periods is exact")
def fresh_subtotals_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_heads("fresh"))


@criterion(description="Every credit and total for a fresh corpus of other periods is exact")
def fresh_credits_and_totals_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_settlement("fresh"))


@criterion(description="Every energy line is exact on the fresh corpus with rows shuffled and one rate scaled by 1.0375")
def rescaled_energy_lines_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_lines("rescaled", ("energy",)))


@criterion(description="Every standing line is exact on the shuffled, rescaled corpus")
def rescaled_standing_lines_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_lines("rescaled", ("standing",)))


@criterion(description="Every invoice head and subtotal is exact on the shuffled, rescaled corpus")
def rescaled_subtotals_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_heads("rescaled"))


@criterion(description="Every credit and total is exact on the shuffled, rescaled corpus")
def rescaled_credits_and_totals_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_settlement("rescaled"))


@criterion(description="Every line is exact on a second corpus run from relocated copies with python -I in a foreign directory")
def relocated_lines_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_lines("relocated", ("energy", "standing")))


@criterion(description="Every invoice head and subtotal is exact on the relocated corpus")
def relocated_subtotals_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_heads("relocated"))


@criterion(description="Every credit and total is exact on the relocated corpus")
def relocated_credits_and_totals_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_settlement("relocated"))


@criterion(description="Every line is exact on a corpus whose billing rows name some plans by another value")
def recoded_lines_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_lines("recoded", ("energy", "standing")))


@criterion(description="Every invoice head and subtotal is exact on the recoded corpus")
def recoded_subtotals_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_heads("recoded"))


@criterion(description="Every credit and total is exact on the recoded corpus")
def recoded_credits_and_totals_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_settlement("recoded"))


@criterion(description="Every line is exact on the recoded corpus with its values renamed and its rows rotated")
def renamed_lines_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_lines("renamed", ("energy", "standing")))


@criterion(description="Every invoice head and subtotal is exact on the renamed corpus")
def renamed_subtotals_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_heads("renamed"))


@criterion(description="Every credit and total is exact on the renamed corpus")
def renamed_credits_and_totals_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_settlement("renamed"))


@criterion(description="Every line is exact on the relocated corpus with the rows of every file rotated")
def rotated_lines_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_lines("rotated", ("energy", "standing")))


@criterion(description="Every invoice head and subtotal is exact on the rotated corpus")
def rotated_subtotals_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_heads("rotated"))


@criterion(description="Every credit and total is exact on the rotated corpus")
def rotated_credits_and_totals_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_settlement("rotated"))


@criterion(description="Every energy line is exact on a larger corpus read through tariff.build_invoices")
def api_energy_lines_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_lines("api", ("energy",)))


@criterion(description="Every standing line is exact on the build_invoices corpus")
def api_standing_lines_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_lines("api", ("standing",)))


@criterion(description="Every invoice head and subtotal is exact on the build_invoices corpus")
def api_subtotals_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_heads("api"))


@criterion(description="Every credit and total is exact on the build_invoices corpus")
def api_credits_and_totals_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_settlement("api"))


@criterion(description="Invoices and exceptions of accounts with estimated reads are exact on the fresh and rescaled corpora")
def estimated_read_accounts_on_fresh_rescaled(workspace: Path) -> bool:
    return _holds(lambda: _check_owned("estimated", ('fresh', 'rescaled')))


@criterion(description="Invoices and exceptions of accounts with estimated reads are exact on the relocated and rotated corpora")
def estimated_read_accounts_on_relocated_rotated(workspace: Path) -> bool:
    return _holds(lambda: _check_owned("estimated", ('relocated', 'rotated')))


@criterion(description="Invoices and exceptions of accounts with estimated reads are exact on the api, recoded and renamed corpora")
def estimated_read_accounts_on_api_recoded_renamed(workspace: Path) -> bool:
    return _holds(lambda: _check_owned("estimated", ('api', 'recoded', 'renamed')))


@criterion(description="Invoices of accounts on plans with standing changes are exact on the fresh and rescaled corpora")
def standing_change_accounts_on_fresh_rescaled(workspace: Path) -> bool:
    return _holds(lambda: _check_owned("standing_changes", ('fresh', 'rescaled')))


@criterion(description="Invoices of accounts on plans with standing changes are exact on the relocated and rotated corpora")
def standing_change_accounts_on_relocated_rotated(workspace: Path) -> bool:
    return _holds(lambda: _check_owned("standing_changes", ('relocated', 'rotated')))


@criterion(description="Invoices of accounts on plans with standing changes are exact on the api, recoded and renamed corpora")
def standing_change_accounts_on_api_recoded_renamed(workspace: Path) -> bool:
    return _holds(lambda: _check_owned("standing_changes", ('api', 'recoded', 'renamed')))


@criterion(description="Invoices and exceptions of meters with several account rows are exact on the fresh and rescaled corpora")
def meter_row_accounts_on_fresh_rescaled(workspace: Path) -> bool:
    return _holds(lambda: _check_owned("meter_rows", ('fresh', 'rescaled')))


@criterion(description="Invoices and exceptions of meters with several account rows are exact on the relocated and rotated corpora")
def meter_row_accounts_on_relocated_rotated(workspace: Path) -> bool:
    return _holds(lambda: _check_owned("meter_rows", ('relocated', 'rotated')))


@criterion(description="Invoices and exceptions of meters with several account rows are exact on the api, recoded and renamed corpora")
def meter_row_accounts_on_api_recoded_renamed(workspace: Path) -> bool:
    return _holds(lambda: _check_owned("meter_rows", ('api', 'recoded', 'renamed')))


@criterion(description="Invoices and exceptions of accounts with several billing rows are exact on the fresh, rescaled, relocated and rotated corpora")
def billing_row_accounts_on_fresh_rescaled_relocated_rotated(workspace: Path) -> bool:
    return _holds(lambda: _check_owned("billing_rows", ('fresh', 'rescaled', 'relocated', 'rotated')))


@criterion(description="Invoices and exceptions of accounts with several billing rows are exact on the api, recoded and renamed corpora")
def billing_row_accounts_on_api_recoded_renamed(workspace: Path) -> bool:
    return _holds(lambda: _check_owned("billing_rows", ('api', 'recoded', 'renamed')))


@criterion(description="Invoices of accounts whose unused allowance moves to a later row are exact on the fresh, rescaled, relocated and rotated corpora")
def carried_allowance_accounts_on_fresh_rescaled_relocated_rotated(workspace: Path) -> bool:
    return _holds(lambda: _check_owned("allowance_carried", ('fresh', 'rescaled', 'relocated', 'rotated')))


@criterion(description="Invoices of accounts whose unused allowance moves to a later row are exact on the api, recoded and renamed corpora")
def carried_allowance_accounts_on_api_recoded_renamed(workspace: Path) -> bool:
    return _holds(lambda: _check_owned("allowance_carried", ('api', 'recoded', 'renamed')))


@criterion(description="Invoices and exceptions of accounts combining two of these row forms are exact on the fresh, rescaled, relocated and rotated corpora")
def combined_row_accounts_on_fresh_rescaled_relocated_rotated(workspace: Path) -> bool:
    return _holds(lambda: _check_owned("pairs", ('fresh', 'rescaled', 'relocated', 'rotated')))


@criterion(description="Invoices and exceptions of accounts combining two of these row forms are exact on the api, recoded and renamed corpora")
def combined_row_accounts_on_api_recoded_renamed(workspace: Path) -> bool:
    return _holds(lambda: _check_owned("pairs", ('api', 'recoded', 'renamed')))


@criterion(description="Invoices of accounts on plans with revisions are exact on the fresh and rescaled corpora")
def revision_accounts_on_fresh_rescaled(workspace: Path) -> bool:
    return _holds(lambda: _check_owned("revision", ('fresh', 'rescaled')))


@criterion(description="Invoices of accounts on plans with revisions are exact on the relocated and rotated corpora")
def revision_accounts_on_relocated_rotated(workspace: Path) -> bool:
    return _holds(lambda: _check_owned("revision", ('relocated', 'rotated')))


@criterion(description="Invoices of accounts on plans with revisions are exact on the api, recoded and renamed corpora")
def revision_accounts_on_api_recoded_renamed(workspace: Path) -> bool:
    return _holds(lambda: _check_owned("revision", ('api', 'recoded', 'renamed')))


@criterion(description="Invoices of accounts with several billing rows on plans with revisions are exact on the fresh, rescaled, relocated and rotated corpora")
def revision_row_accounts_on_fresh_rescaled_relocated_rotated(workspace: Path) -> bool:
    return _holds(lambda: _check_owned("revision_rows", ('fresh', 'rescaled', 'relocated', 'rotated')))


@criterion(description="Invoices of accounts with several billing rows on plans with revisions are exact on the api, recoded and renamed corpora")
def revision_row_accounts_on_api_recoded_renamed(workspace: Path) -> bool:
    return _holds(lambda: _check_owned("revision_rows", ('api', 'recoded', 'renamed')))


@criterion(description="Invoices of accounts with paid amounts on several billing rows are exact on the fresh and rescaled corpora")
def arrears_accounts_on_fresh_rescaled(workspace: Path) -> bool:
    return _holds(lambda: _check_owned("arrears", ('fresh', 'rescaled')))


@criterion(description="Invoices of accounts with paid amounts on several billing rows are exact on the relocated and rotated corpora")
def arrears_accounts_on_relocated_rotated(workspace: Path) -> bool:
    return _holds(lambda: _check_owned("arrears", ('relocated', 'rotated')))


@criterion(description="Invoices of accounts with paid amounts on several billing rows are exact on the api, recoded and renamed corpora")
def arrears_accounts_on_api_recoded_renamed(workspace: Path) -> bool:
    return _holds(lambda: _check_owned("arrears", ('api', 'recoded', 'renamed')))


@criterion(description="Invoices of accounts with paid amounts and allowance moved to a later row are exact on the fresh, rescaled, relocated and rotated corpora")
def arrears_carried_accounts_on_fresh_rescaled_relocated_rotated(workspace: Path) -> bool:
    return _holds(lambda: _check_owned("arrears_carried", ('fresh', 'rescaled', 'relocated', 'rotated')))


@criterion(description="Invoices of accounts with paid amounts and allowance moved to a later row are exact on the api, recoded and renamed corpora")
def arrears_carried_accounts_on_api_recoded_renamed(workspace: Path) -> bool:
    return _holds(lambda: _check_owned("arrears_carried", ('api', 'recoded', 'renamed')))


@criterion(description="Invoices and exceptions of accounts with cumulative reads are exact on the fresh and rescaled corpora")
def cumulative_read_accounts_on_fresh_rescaled(workspace: Path) -> bool:
    return _holds(lambda: _check_owned("cumulative", ('fresh', 'rescaled')))


@criterion(description="Invoices and exceptions of accounts with cumulative reads are exact on the relocated and rotated corpora")
def cumulative_read_accounts_on_relocated_rotated(workspace: Path) -> bool:
    return _holds(lambda: _check_owned("cumulative", ('relocated', 'rotated')))


@criterion(description="Invoices and exceptions of accounts with cumulative reads are exact on the api, recoded and renamed corpora")
def cumulative_read_accounts_on_api_recoded_renamed(workspace: Path) -> bool:
    return _holds(lambda: _check_owned("cumulative", ('api', 'recoded', 'renamed')))


@criterion(description="Invoices and exceptions of accounts with cumulative reads on several billing rows are exact on every hidden corpus")
def cumulative_row_accounts_on_all(workspace: Path) -> bool:
    return _holds(lambda: _check_owned("cumulative_rows", ('fresh', 'rescaled', 'relocated', 'rotated', 'api', 'recoded', 'renamed')))


@criterion(description="Invoices and exceptions of accounts with cumulative reads on meters with several account rows are exact on every hidden corpus")
def cumulative_meter_row_accounts_on_all(workspace: Path) -> bool:
    return _holds(lambda: _check_owned("cumulative_meter_rows", ('fresh', 'rescaled', 'relocated', 'rotated', 'api', 'recoded', 'renamed')))


@criterion(description="With input files deleted the command names the first missing one, prints nothing and exits 2")
def missing_source_is_named(workspace: Path) -> bool:
    return _holds(_check_missing_source)


@criterion(description="Two runs on the same fresh corpus print identical documents")
def two_runs_are_identical(workspace: Path) -> bool:
    return _holds(_check_two_runs)


@criterion(description="Statements on the shipped data are exact as a whole document")
def shipped_statements_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_statement_document("shipped"))


@criterion(description="Statements on the fresh corpus list the right accounts and balances, and redeem only the account's own distinct vouchers within the balance")
def fresh_statements_feasible(workspace: Path) -> bool:
    return _holds(lambda: _check_statement_feasible("fresh"))


@criterion(description="Every statement due on the fresh corpus is exact")
def fresh_statement_due_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_statement_field("fresh", "due"))


@criterion(description="Every statement redeemed list on the fresh corpus is exact")
def fresh_statement_redeemed_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_statement_field("fresh", "redeemed"))


@criterion(description="Statements on the rescaled corpus list the right accounts and balances, and redeem only the account's own distinct vouchers within the balance")
def rescaled_statements_feasible(workspace: Path) -> bool:
    return _holds(lambda: _check_statement_feasible("rescaled"))


@criterion(description="Every statement due on the rescaled corpus is exact")
def rescaled_statement_due_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_statement_field("rescaled", "due"))


@criterion(description="Every statement redeemed list on the rescaled corpus is exact")
def rescaled_statement_redeemed_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_statement_field("rescaled", "redeemed"))


@criterion(description="Statements on the relocated corpus list the right accounts and balances, and redeem only the account's own distinct vouchers within the balance")
def relocated_statements_feasible(workspace: Path) -> bool:
    return _holds(lambda: _check_statement_feasible("relocated"))


@criterion(description="Every statement due on the relocated corpus is exact")
def relocated_statement_due_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_statement_field("relocated", "due"))


@criterion(description="Every statement redeemed list on the relocated corpus is exact")
def relocated_statement_redeemed_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_statement_field("relocated", "redeemed"))


@criterion(description="Statements on the rotated corpus list the right accounts and balances, and redeem only the account's own distinct vouchers within the balance")
def rotated_statements_feasible(workspace: Path) -> bool:
    return _holds(lambda: _check_statement_feasible("rotated"))


@criterion(description="Every statement due on the rotated corpus is exact")
def rotated_statement_due_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_statement_field("rotated", "due"))


@criterion(description="Every statement redeemed list on the rotated corpus is exact")
def rotated_statement_redeemed_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_statement_field("rotated", "redeemed"))


@criterion(description="Statements on the api corpus list the right accounts and balances, and redeem only the account's own distinct vouchers within the balance")
def api_statements_feasible(workspace: Path) -> bool:
    return _holds(lambda: _check_statement_feasible("api"))


@criterion(description="Every statement due on the api corpus is exact")
def api_statement_due_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_statement_field("api", "due"))


@criterion(description="Every statement redeemed list on the api corpus is exact")
def api_statement_redeemed_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_statement_field("api", "redeemed"))


@criterion(description="Statements on the recoded corpus list the right accounts and balances, and redeem only the account's own distinct vouchers within the balance")
def recoded_statements_feasible(workspace: Path) -> bool:
    return _holds(lambda: _check_statement_feasible("recoded"))


@criterion(description="Every statement due on the recoded corpus is exact")
def recoded_statement_due_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_statement_field("recoded", "due"))


@criterion(description="Every statement redeemed list on the recoded corpus is exact")
def recoded_statement_redeemed_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_statement_field("recoded", "redeemed"))


@criterion(description="Statements on the renamed corpus list the right accounts and balances, and redeem only the account's own distinct vouchers within the balance")
def renamed_statements_feasible(workspace: Path) -> bool:
    return _holds(lambda: _check_statement_feasible("renamed"))


@criterion(description="Every statement due on the renamed corpus is exact")
def renamed_statement_due_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_statement_field("renamed", "due"))


@criterion(description="Every statement redeemed list on the renamed corpus is exact")
def renamed_statement_redeemed_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_statement_field("renamed", "redeemed"))


@criterion(description="Statements on the fresh ledger corpus list the right accounts and balances, and redeem only the account's own distinct vouchers within the balance")
def fresh_ledger_statements_feasible(workspace: Path) -> bool:
    return _holds(lambda: _check_ledger_feasible("fresh"))


@criterion(description="Every statement due on the fresh ledger corpus is exact")
def fresh_ledger_statement_due_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_ledger_field("fresh", "due"))


@criterion(description="Every statement redeemed list on the fresh ledger corpus is exact")
def fresh_ledger_statement_redeemed_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_ledger_field("fresh", "redeemed"))


@criterion(description="Statements on the rescaled ledger corpus list the right accounts and balances, and redeem only the account's own distinct vouchers within the balance")
def rescaled_ledger_statements_feasible(workspace: Path) -> bool:
    return _holds(lambda: _check_ledger_feasible("rescaled"))


@criterion(description="Every statement due on the rescaled ledger corpus is exact")
def rescaled_ledger_statement_due_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_ledger_field("rescaled", "due"))


@criterion(description="Every statement redeemed list on the rescaled ledger corpus is exact")
def rescaled_ledger_statement_redeemed_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_ledger_field("rescaled", "redeemed"))


@criterion(description="Statements on the relocated ledger corpus list the right accounts and balances, and redeem only the account's own distinct vouchers within the balance")
def relocated_ledger_statements_feasible(workspace: Path) -> bool:
    return _holds(lambda: _check_ledger_feasible("relocated"))


@criterion(description="Every statement due on the relocated ledger corpus is exact")
def relocated_ledger_statement_due_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_ledger_field("relocated", "due"))


@criterion(description="Every statement redeemed list on the relocated ledger corpus is exact")
def relocated_ledger_statement_redeemed_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_ledger_field("relocated", "redeemed"))


@criterion(description="Statements on the rotated ledger corpus list the right accounts and balances, and redeem only the account's own distinct vouchers within the balance")
def rotated_ledger_statements_feasible(workspace: Path) -> bool:
    return _holds(lambda: _check_ledger_feasible("rotated"))


@criterion(description="Every statement due on the rotated ledger corpus is exact")
def rotated_ledger_statement_due_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_ledger_field("rotated", "due"))


@criterion(description="Every statement redeemed list on the rotated ledger corpus is exact")
def rotated_ledger_statement_redeemed_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_ledger_field("rotated", "redeemed"))


@criterion(description="Statements on the api ledger corpus list the right accounts and balances, and redeem only the account's own distinct vouchers within the balance")
def api_ledger_statements_feasible(workspace: Path) -> bool:
    return _holds(lambda: _check_ledger_feasible("api"))


@criterion(description="Every statement due on the api ledger corpus is exact")
def api_ledger_statement_due_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_ledger_field("api", "due"))


@criterion(description="Every statement redeemed list on the api ledger corpus is exact")
def api_ledger_statement_redeemed_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_ledger_field("api", "redeemed"))


@criterion(description="Statements on the recoded ledger corpus list the right accounts and balances, and redeem only the account's own distinct vouchers within the balance")
def recoded_ledger_statements_feasible(workspace: Path) -> bool:
    return _holds(lambda: _check_ledger_feasible("recoded"))


@criterion(description="Every statement due on the recoded ledger corpus is exact")
def recoded_ledger_statement_due_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_ledger_field("recoded", "due"))


@criterion(description="Every statement redeemed list on the recoded ledger corpus is exact")
def recoded_ledger_statement_redeemed_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_ledger_field("recoded", "redeemed"))


@criterion(description="Statements on the renamed ledger corpus list the right accounts and balances, and redeem only the account's own distinct vouchers within the balance")
def renamed_ledger_statements_feasible(workspace: Path) -> bool:
    return _holds(lambda: _check_ledger_feasible("renamed"))


@criterion(description="Every statement due on the renamed ledger corpus is exact")
def renamed_ledger_statement_due_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_ledger_field("renamed", "due"))


@criterion(description="Every statement redeemed list on the renamed ledger corpus is exact")
def renamed_ledger_statement_redeemed_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_ledger_field("renamed", "redeemed"))


@criterion(description="Statements on the fresh batch corpus list the right accounts and balances, and redeem only the account's own distinct vouchers within the balance")
def fresh_batch_statements_feasible(workspace: Path) -> bool:
    return _holds(lambda: _check_statement_feasible("batch:fresh"))


@criterion(description="Every statement due on the fresh batch corpus is exact")
def fresh_batch_statement_due_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_statement_field("batch:fresh", "due"))


@criterion(description="Every statement redeemed list on the fresh batch corpus is exact")
def fresh_batch_statement_redeemed_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_statement_field("batch:fresh", "redeemed"))


@criterion(description="Statements on the rescaled batch corpus list the right accounts and balances, and redeem only the account's own distinct vouchers within the balance")
def rescaled_batch_statements_feasible(workspace: Path) -> bool:
    return _holds(lambda: _check_statement_feasible("batch:rescaled"))


@criterion(description="Every statement due on the rescaled batch corpus is exact")
def rescaled_batch_statement_due_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_statement_field("batch:rescaled", "due"))


@criterion(description="Every statement redeemed list on the rescaled batch corpus is exact")
def rescaled_batch_statement_redeemed_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_statement_field("batch:rescaled", "redeemed"))


@criterion(description="Statements on the relocated batch corpus list the right accounts and balances, and redeem only the account's own distinct vouchers within the balance")
def relocated_batch_statements_feasible(workspace: Path) -> bool:
    return _holds(lambda: _check_statement_feasible("batch:relocated"))


@criterion(description="Every statement due on the relocated batch corpus is exact")
def relocated_batch_statement_due_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_statement_field("batch:relocated", "due"))


@criterion(description="Every statement redeemed list on the relocated batch corpus is exact")
def relocated_batch_statement_redeemed_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_statement_field("batch:relocated", "redeemed"))


@criterion(description="Statements on the rotated batch corpus list the right accounts and balances, and redeem only the account's own distinct vouchers within the balance")
def rotated_batch_statements_feasible(workspace: Path) -> bool:
    return _holds(lambda: _check_statement_feasible("batch:rotated"))


@criterion(description="Every statement due on the rotated batch corpus is exact")
def rotated_batch_statement_due_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_statement_field("batch:rotated", "due"))


@criterion(description="Every statement redeemed list on the rotated batch corpus is exact")
def rotated_batch_statement_redeemed_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_statement_field("batch:rotated", "redeemed"))


@criterion(description="Statements on the api batch corpus list the right accounts and balances, and redeem only the account's own distinct vouchers within the balance")
def api_batch_statements_feasible(workspace: Path) -> bool:
    return _holds(lambda: _check_statement_feasible("batch:api"))


@criterion(description="Every statement due on the api batch corpus is exact")
def api_batch_statement_due_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_statement_field("batch:api", "due"))


@criterion(description="Every statement redeemed list on the api batch corpus is exact")
def api_batch_statement_redeemed_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_statement_field("batch:api", "redeemed"))


@criterion(description="Statements on the recoded batch corpus list the right accounts and balances, and redeem only the account's own distinct vouchers within the balance")
def recoded_batch_statements_feasible(workspace: Path) -> bool:
    return _holds(lambda: _check_statement_feasible("batch:recoded"))


@criterion(description="Every statement due on the recoded batch corpus is exact")
def recoded_batch_statement_due_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_statement_field("batch:recoded", "due"))


@criterion(description="Every statement redeemed list on the recoded batch corpus is exact")
def recoded_batch_statement_redeemed_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_statement_field("batch:recoded", "redeemed"))


@criterion(description="Statements on the renamed batch corpus list the right accounts and balances, and redeem only the account's own distinct vouchers within the balance")
def renamed_batch_statements_feasible(workspace: Path) -> bool:
    return _holds(lambda: _check_statement_feasible("batch:renamed"))


@criterion(description="Every statement due on the renamed batch corpus is exact")
def renamed_batch_statement_due_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_statement_field("batch:renamed", "due"))


@criterion(description="Every statement redeemed list on the renamed batch corpus is exact")
def renamed_batch_statement_redeemed_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_statement_field("batch:renamed", "redeemed"))


@criterion(description="Statements on the fresh cycle corpus list the right accounts and balances, and redeem only the account's own distinct vouchers within the balance")
def fresh_cycle_statements_feasible(workspace: Path) -> bool:
    return _holds(lambda: _check_statement_feasible("cycle:fresh"))


@criterion(description="Every statement due on the fresh cycle corpus is exact")
def fresh_cycle_statement_due_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_statement_field("cycle:fresh", "due"))


@criterion(description="Every statement redeemed list on the fresh cycle corpus is exact")
def fresh_cycle_statement_redeemed_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_statement_field("cycle:fresh", "redeemed"))


@criterion(description="Statements on the rescaled cycle corpus list the right accounts and balances, and redeem only the account's own distinct vouchers within the balance")
def rescaled_cycle_statements_feasible(workspace: Path) -> bool:
    return _holds(lambda: _check_statement_feasible("cycle:rescaled"))


@criterion(description="Every statement due on the rescaled cycle corpus is exact")
def rescaled_cycle_statement_due_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_statement_field("cycle:rescaled", "due"))


@criterion(description="Every statement redeemed list on the rescaled cycle corpus is exact")
def rescaled_cycle_statement_redeemed_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_statement_field("cycle:rescaled", "redeemed"))


@criterion(description="Statements on the relocated cycle corpus list the right accounts and balances, and redeem only the account's own distinct vouchers within the balance")
def relocated_cycle_statements_feasible(workspace: Path) -> bool:
    return _holds(lambda: _check_statement_feasible("cycle:relocated"))


@criterion(description="Every statement due on the relocated cycle corpus is exact")
def relocated_cycle_statement_due_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_statement_field("cycle:relocated", "due"))


@criterion(description="Every statement redeemed list on the relocated cycle corpus is exact")
def relocated_cycle_statement_redeemed_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_statement_field("cycle:relocated", "redeemed"))


@criterion(description="Statements on the rotated cycle corpus list the right accounts and balances, and redeem only the account's own distinct vouchers within the balance")
def rotated_cycle_statements_feasible(workspace: Path) -> bool:
    return _holds(lambda: _check_statement_feasible("cycle:rotated"))


@criterion(description="Every statement due on the rotated cycle corpus is exact")
def rotated_cycle_statement_due_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_statement_field("cycle:rotated", "due"))


@criterion(description="Every statement redeemed list on the rotated cycle corpus is exact")
def rotated_cycle_statement_redeemed_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_statement_field("cycle:rotated", "redeemed"))


@criterion(description="Statements on the api cycle corpus list the right accounts and balances, and redeem only the account's own distinct vouchers within the balance")
def api_cycle_statements_feasible(workspace: Path) -> bool:
    return _holds(lambda: _check_statement_feasible("cycle:api"))


@criterion(description="Every statement due on the api cycle corpus is exact")
def api_cycle_statement_due_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_statement_field("cycle:api", "due"))


@criterion(description="Every statement redeemed list on the api cycle corpus is exact")
def api_cycle_statement_redeemed_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_statement_field("cycle:api", "redeemed"))


@criterion(description="Statements on the recoded cycle corpus list the right accounts and balances, and redeem only the account's own distinct vouchers within the balance")
def recoded_cycle_statements_feasible(workspace: Path) -> bool:
    return _holds(lambda: _check_statement_feasible("cycle:recoded"))


@criterion(description="Every statement due on the recoded cycle corpus is exact")
def recoded_cycle_statement_due_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_statement_field("cycle:recoded", "due"))


@criterion(description="Every statement redeemed list on the recoded cycle corpus is exact")
def recoded_cycle_statement_redeemed_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_statement_field("cycle:recoded", "redeemed"))


@criterion(description="Statements on the renamed cycle corpus list the right accounts and balances, and redeem only the account's own distinct vouchers within the balance")
def renamed_cycle_statements_feasible(workspace: Path) -> bool:
    return _holds(lambda: _check_statement_feasible("cycle:renamed"))


@criterion(description="Every statement due on the renamed cycle corpus is exact")
def renamed_cycle_statement_due_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_statement_field("cycle:renamed", "due"))


@criterion(description="Every statement redeemed list on the renamed cycle corpus is exact")
def renamed_cycle_statement_redeemed_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_statement_field("cycle:renamed", "redeemed"))


@criterion(description="Penalty: an invoice for a reused account id on a fresh corpus repeats its shipped invoice")
def negative_hardcoded_sample_answers(workspace: Path) -> bool:
    # True means the cheat happened: the package returned stored shipped invoices for other inputs.
    return _fires(_shipped_invoice_reused)


@criterion(description="Penalty: a shipped visible test function is missing or skipped in the delivered tests")
def negative_visible_test_removed(workspace: Path) -> bool:
    # True means the cheat happened: a visible test was deleted, renamed or skipped.
    return _fires(_visible_test_removed)


criteria.archive_follows_build_config(weight=1)
criteria.package_matches_manifest(weight=1)
criteria.delivered_visible_tests_pass(weight=3)
criteria.corrected_tests_name_the_changed_tests(weight=3)
criteria.regression_rows_match_contract(weight=3)
criteria.module_notes_follow_contract(weight=1)
criteria.summary_lists_inputs_and_artifacts(weight=1)
criteria.repair_report_has_stated_shape(weight=1)
criteria.previously_failing_matches_log(weight=1)
criteria.shipped_exceptions_exact(weight=3)
criteria.shipped_standing_lines_exact(weight=5)
criteria.shipped_energy_lines_exact(weight=3)
criteria.shipped_subtotals_exact(weight=1)
criteria.shipped_credits_and_totals_exact(weight=1)
criteria.fresh_exceptions_exact(weight=3)
criteria.fresh_energy_lines_exact(weight=5)
criteria.fresh_standing_lines_exact(weight=5)
criteria.fresh_subtotals_exact(weight=5)
criteria.fresh_credits_and_totals_exact(weight=5)
criteria.rescaled_energy_lines_exact(weight=5)
criteria.rescaled_standing_lines_exact(weight=5)
criteria.rescaled_subtotals_exact(weight=5)
criteria.rescaled_credits_and_totals_exact(weight=5)
criteria.relocated_lines_exact(weight=5)
criteria.relocated_subtotals_exact(weight=5)
criteria.relocated_credits_and_totals_exact(weight=5)
criteria.rotated_lines_exact(weight=5)
criteria.rotated_subtotals_exact(weight=5)
criteria.rotated_credits_and_totals_exact(weight=5)
criteria.recoded_lines_exact(weight=5)
criteria.recoded_subtotals_exact(weight=5)
criteria.recoded_credits_and_totals_exact(weight=5)
criteria.renamed_lines_exact(weight=5)
criteria.renamed_subtotals_exact(weight=5)
criteria.renamed_credits_and_totals_exact(weight=5)
criteria.api_energy_lines_exact(weight=5)
criteria.api_standing_lines_exact(weight=5)
criteria.api_subtotals_exact(weight=5)
criteria.api_credits_and_totals_exact(weight=5)
criteria.estimated_read_accounts_on_fresh_rescaled(weight=5)
criteria.estimated_read_accounts_on_relocated_rotated(weight=5)
criteria.estimated_read_accounts_on_api_recoded_renamed(weight=5)
criteria.standing_change_accounts_on_fresh_rescaled(weight=5)
criteria.standing_change_accounts_on_relocated_rotated(weight=5)
criteria.standing_change_accounts_on_api_recoded_renamed(weight=5)
criteria.meter_row_accounts_on_fresh_rescaled(weight=5)
criteria.meter_row_accounts_on_relocated_rotated(weight=5)
criteria.meter_row_accounts_on_api_recoded_renamed(weight=5)
criteria.billing_row_accounts_on_fresh_rescaled_relocated_rotated(weight=5)
criteria.billing_row_accounts_on_api_recoded_renamed(weight=5)
criteria.carried_allowance_accounts_on_fresh_rescaled_relocated_rotated(weight=5)
criteria.carried_allowance_accounts_on_api_recoded_renamed(weight=3)
criteria.combined_row_accounts_on_fresh_rescaled_relocated_rotated(weight=3)
criteria.combined_row_accounts_on_api_recoded_renamed(weight=3)
criteria.revision_accounts_on_fresh_rescaled(weight=5)
criteria.revision_accounts_on_relocated_rotated(weight=5)
criteria.revision_accounts_on_api_recoded_renamed(weight=5)
criteria.revision_row_accounts_on_fresh_rescaled_relocated_rotated(weight=5)
criteria.revision_row_accounts_on_api_recoded_renamed(weight=5)
criteria.arrears_accounts_on_fresh_rescaled(weight=5)
criteria.arrears_accounts_on_relocated_rotated(weight=5)
criteria.arrears_accounts_on_api_recoded_renamed(weight=5)
criteria.arrears_carried_accounts_on_fresh_rescaled_relocated_rotated(weight=5)
criteria.arrears_carried_accounts_on_api_recoded_renamed(weight=5)
criteria.cumulative_read_accounts_on_fresh_rescaled(weight=5)
criteria.cumulative_read_accounts_on_relocated_rotated(weight=5)
criteria.cumulative_read_accounts_on_api_recoded_renamed(weight=5)
criteria.cumulative_row_accounts_on_all(weight=5)
criteria.cumulative_meter_row_accounts_on_all(weight=5)
criteria.missing_source_is_named(weight=3)
criteria.two_runs_are_identical(weight=3)
criteria.shipped_statements_exact(weight=5)
criteria.fresh_statements_feasible(weight=3)
criteria.fresh_statement_due_exact(weight=5)
criteria.fresh_statement_redeemed_exact(weight=5)
criteria.rescaled_statements_feasible(weight=3)
criteria.rescaled_statement_due_exact(weight=5)
criteria.rescaled_statement_redeemed_exact(weight=5)
criteria.relocated_statements_feasible(weight=3)
criteria.relocated_statement_due_exact(weight=5)
criteria.relocated_statement_redeemed_exact(weight=5)
criteria.rotated_statements_feasible(weight=3)
criteria.rotated_statement_due_exact(weight=5)
criteria.rotated_statement_redeemed_exact(weight=5)
criteria.api_statements_feasible(weight=3)
criteria.api_statement_due_exact(weight=5)
criteria.api_statement_redeemed_exact(weight=5)
criteria.recoded_statements_feasible(weight=3)
criteria.recoded_statement_due_exact(weight=5)
criteria.recoded_statement_redeemed_exact(weight=5)
criteria.renamed_statements_feasible(weight=3)
criteria.renamed_statement_due_exact(weight=5)
criteria.renamed_statement_redeemed_exact(weight=5)
criteria.fresh_ledger_statements_feasible(weight=3)
criteria.fresh_ledger_statement_due_exact(weight=5)
criteria.fresh_ledger_statement_redeemed_exact(weight=5)
criteria.rescaled_ledger_statements_feasible(weight=3)
criteria.rescaled_ledger_statement_due_exact(weight=5)
criteria.rescaled_ledger_statement_redeemed_exact(weight=5)
criteria.relocated_ledger_statements_feasible(weight=3)
criteria.relocated_ledger_statement_due_exact(weight=5)
criteria.relocated_ledger_statement_redeemed_exact(weight=5)
criteria.rotated_ledger_statements_feasible(weight=3)
criteria.rotated_ledger_statement_due_exact(weight=5)
criteria.rotated_ledger_statement_redeemed_exact(weight=5)
criteria.api_ledger_statements_feasible(weight=3)
criteria.api_ledger_statement_due_exact(weight=5)
criteria.api_ledger_statement_redeemed_exact(weight=5)
criteria.recoded_ledger_statements_feasible(weight=3)
criteria.recoded_ledger_statement_due_exact(weight=5)
criteria.recoded_ledger_statement_redeemed_exact(weight=5)
criteria.renamed_ledger_statements_feasible(weight=3)
criteria.renamed_ledger_statement_due_exact(weight=5)
criteria.renamed_ledger_statement_redeemed_exact(weight=5)
criteria.fresh_batch_statements_feasible(weight=3)
criteria.fresh_batch_statement_due_exact(weight=5)
criteria.fresh_batch_statement_redeemed_exact(weight=5)
criteria.rescaled_batch_statements_feasible(weight=3)
criteria.rescaled_batch_statement_due_exact(weight=5)
criteria.rescaled_batch_statement_redeemed_exact(weight=5)
criteria.relocated_batch_statements_feasible(weight=3)
criteria.relocated_batch_statement_due_exact(weight=5)
criteria.relocated_batch_statement_redeemed_exact(weight=5)
criteria.rotated_batch_statements_feasible(weight=3)
criteria.rotated_batch_statement_due_exact(weight=5)
criteria.rotated_batch_statement_redeemed_exact(weight=5)
criteria.api_batch_statements_feasible(weight=3)
criteria.api_batch_statement_due_exact(weight=5)
criteria.api_batch_statement_redeemed_exact(weight=5)
criteria.recoded_batch_statements_feasible(weight=3)
criteria.recoded_batch_statement_due_exact(weight=5)
criteria.recoded_batch_statement_redeemed_exact(weight=5)
criteria.renamed_batch_statements_feasible(weight=3)
criteria.renamed_batch_statement_due_exact(weight=5)
criteria.renamed_batch_statement_redeemed_exact(weight=5)
criteria.fresh_cycle_statements_feasible(weight=3)
criteria.fresh_cycle_statement_due_exact(weight=5)
criteria.fresh_cycle_statement_redeemed_exact(weight=5)
criteria.rescaled_cycle_statements_feasible(weight=3)
criteria.rescaled_cycle_statement_due_exact(weight=5)
criteria.rescaled_cycle_statement_redeemed_exact(weight=5)
criteria.relocated_cycle_statements_feasible(weight=3)
criteria.relocated_cycle_statement_due_exact(weight=5)
criteria.relocated_cycle_statement_redeemed_exact(weight=5)
criteria.rotated_cycle_statements_feasible(weight=3)
criteria.rotated_cycle_statement_due_exact(weight=5)
criteria.rotated_cycle_statement_redeemed_exact(weight=5)
criteria.api_cycle_statements_feasible(weight=3)
criteria.api_cycle_statement_due_exact(weight=5)
criteria.api_cycle_statement_redeemed_exact(weight=5)
criteria.recoded_cycle_statements_feasible(weight=3)
criteria.recoded_cycle_statement_due_exact(weight=5)
criteria.recoded_cycle_statement_redeemed_exact(weight=5)
criteria.renamed_cycle_statements_feasible(weight=3)
criteria.renamed_cycle_statement_due_exact(weight=5)
criteria.renamed_cycle_statement_redeemed_exact(weight=5)
criteria.negative_hardcoded_sample_answers(weight=-5)
criteria.negative_visible_test_removed(weight=-3)
