"""Checks for the 43986de8-bb38-5141-98f3-f9f31ce56581 task.

Expected reports are derived here, independently of the reference solution, from the embedded shipped extract and
from held-out extracts that this file generates from fixed seeds in the shipped layout. The delivered program is run
as a subprocess under an unprivileged uid through an audit wrapper; nothing it defines is imported.

Negative checks return True when the bad act happened (the weight is then subtracted).
"""
# pyright: reportUndefinedVariable=false
from __future__ import annotations

from rewardkit import criteria, criterion

_SHIPPED_DATA: dict[str, str] = {
    "adj_log.psv": "eNpdjzFuAzEMBHv+JQCXpETqH/rAIb7CQHJGEMdIwcdHB0cqXHIxs1p97195/z1ye79fb0c+to+fncSzg41LPm7XS75RLdmbiURun/txSW1WQKWeWLBPbGjSTDFvtexVI3QFmj3QBP890go3Mj/bXX2mosxkQzZErDYM2UpomyPA0ig4u4d7nVgZmCusrUfH3Xx85qkBZko4p7FgaXgpZ1QQcFLOdS6DhZHGS8qBSjLC4FgFqkx/K5FpMA==",
    "cat_codes.docx": "eNoL8GZmEWFgYOBgYJhgF3vSX2rDayBvHSMDgzCQjnbOzytJzSuJD6ksSC2O1avIzakN2Ot32EDgXiXXae0uWQkBJ0+rD8ZMzpUNk2s9dd5sflrs/fubRe7LBq7Hd7+vXh/9tkk8+swbpa+f3LYGKczMkPXd+ydiv8n3oALGTQ+UE/W/nygyjSl9XeskFupz5/TOKV8WmM6WZN7QxblSKfkMo5ft5yXCM/xnBNzf9nau2USuoMxTjxTb33G63/ihNK/8a63OpIubRfrdH0266u1x0pp56aMq72/hXsVeAaGVDz68EYoPb7oiLiz25H3D5Hdr9SbPdf3It3OP0wqdv6Kbr5rN8l3h9XX/2dZ5hTJzD26uK/S2lEpZN5l9/TkPBnf7v18T3z2UDkAJm52NLoUbgDwtYNhwA+n4otScYn09ENl73prvkAEP24O5wS73MqPYWgIm63Gs1NZi7xAy782Q8zq0eLs6M7MCm9vt/fanc79vMN6Z6HPMms03lNlRfa+Rn7EF//GvfB6nDmkaVrfziPlc+BhafSjyyabJasJCmh3ePMvmHJ53SUV9i1Ko3QLtyRfdtYs0Fy9zPNF9wcO8dO/Sj3cZ/iVOijPs2JvVwON9oD7Hvs/t0cHTq12n18/54SUS6dI78+Bdd9erq2NFxTTyXx7v/sOJ6jFjFUWxGKCnXrEyMAgCRcvzi1L0U/KTS3OBMQ+K8rVTzua1KAg0vK/lOlwrfvduXvTmXe3LfKvy5RkKQ4ISOB5E3d+Xcffbhfk5wnrMbs8eS3MUW+zTnDnngFXjLoWbVqqcGX1bL+Q6xs2TD9+uUjjv5SzPKwETBGUsp4W3K66f+J1riz+T4+4aDY/ne09qlu5hPnpHivfFh/WOq2fwz9+2lPnWrYgnD2JuOHju8rxsG+qTsSlBZH/L4hm1b892LTY60+3l8fD4zNJjPDffSbtz5l1MfHxdsT/pMgff5sATZy5VLlPxFDk/P6p3WqjRFWmHJTxXwyL6L2csS1huID7P+nBFRJqOxQZ1hafNdo08pzjT5aK2JAv5Cd9pbOsp6irrMz4eXiRnV/FH6Z/Lb0a38w3eht1332v80vwmv/f3W7Om2OYId/Pbb5VnVJ7eYpxRW7N3twT78SkTPup/tTq2tOyG/3q7XXd8xZz5ZnyJLdnuK3XQt6lg79/HV/WLSl5qfLmz7kX4dL37jAHejEwizLhzIAw0MDJgz4/oBqAnU4QBMowoiRZdI3oyQGj8yoglUQR4s7KBpJmBcCdIGTOIBwC9XbGU",
    "cfg_reference.md": "eNplVMFuEzEQve9XjNQDICUrCFKRoFSqWg5IRBUqlwqhXceezZp67e2Mt0n/nrGdNAnNKR4/j9+b97xncB18Z9cTqWiDB8IOCb3Gqjo7g9B1VmNtva2qO9QZ0f4ekWwwf1rogzMMbWeJY2PUcwvKG2id2i/f3stvvlzOb27e1XDooANRWfChjZ6i3NcwPrbHWN4gjgfUqEgNGJEa7hFjO4PYI3ipCdv8fxPoIe+lQj7dRLWqt463sq8irMMTkucMzvvlpGXAbSSl4/H1CUvWoBCdwaZHDyMho4+zHSNnPQqvC2M5ktXxsrl44XgJX+FiIzhhOA0rKZQmhPnyFxzI3Qp0cNPgT7QcEFlRnV051VRVV3AnnJTJkOWPPIBVCA+gGL5dL6/mHz+dg8EuE7UxMQh8NCfRrXSf5QiLXjrJfRQ20O41CevWqGG0ft2I+1rkp9IomUlZSf8pTN40q8msxZScg+Axd5EDsG9Uw613z//ZlE15ZWyeA+/Nql8TSENLjfowMSbybxg4KooCgh0YJNZ4zFT0M+xXJa6nzNN+rkCpzMpwFBzb+OW0xTEelJgrehzKK4APNfySUIFG5zhvcQyEJlljfYoOpMH4NRdrb0UQQWcdclWN8sxkGsnt+i9LGkvgkuZBpmLABOcUceaAW5sDv7NyNxLoKAyyL2VyNtk6+X22SvS7QCX75VXPYBD7YYVSLyF1KLIItJPMmBq+xzT3BxxjPqrDIMbZxC6Is59LajNxgy6q+lkNTr4qY6C4A4upaq2sl/FYCUQMsXlc1JqfjvRJUTkuyUjr8iGC9O5eKRQWi/eL8/nPRV39A/tGu1M=",
    "dict_register.md": "eNp1VE1rG0EMve+vEOSQFtZLQ3so9BRCCyklpUmhRyPvyN6JZ2e2o7Edg398NZrdtVPIwXg1kp6+nnQFj7SxnCjC2pIzYGybbPAYj1V1dQV36IO3LTogvycXBip2XFW/O4I2BuYDui30ODDQnuIR4oRIL0OICdrgdr2HFCB4grCG1BFPOE1VncbQJ+gJvfUbOFWnxWKhP9FK5GUbDMHpnESR1dXR0gcoX+B3/UoilyCwDs6I1Mlfhs1PM0J2drgiJ66XimsuzzVYDzYxhIMHRykX1CLTl6Jm6dR6LW8rSgci/wqDcwK52C7smHJ4Dddiok2Ix6maSS7VvONkVMNNb96X4nY+Jz7Zj+Kb5p7ILE1wDiNDEWs4SHiC8bUGTFIMcoIbdZFkvUYgn7LPKMMoV1VuPjYt78GyBO57BKYBo6RuAL3R6ayaJAYJV2ddDYRtBwebOkDoCPMgYjjkzkxdHYnhsZciypibZw7e6cRYO/j96ecDhNUztQkGgXDWUw1bOkr41fENqAdlAecJ5rHk7HOqOcnCSQaMBIdoZaweUIZJre2F5cZuBLKBr8rkRC8J9uh2NEHN3FY8eUgRPaPuzIwtnbp9uru/n2C0fUrPkZcCG8UnG2Jp6uLcVDWUlB6/3cGnm88fJLe1FC2wqdGd7DqZe6SG/zqbqKpeywX06deP/P0RDMpYUNfNkS6byE7Zpy3j/5bNSHlRbgCcP5dWpjkLucVKnQtul5SMDGaNvXVHNaovAeZdhXll68kLpiVHZzGTUP/ree9rYOvbYrYlGpaDQw+nC315KAcrDJZYm9LbGEOcuJsbPRznCUxnYB7oloYkByOqeq6Nr5VePERhMHdESRKbeKPkVoLNV7JcspGGfzoSltk0k2UOJllEkqGZ8YrUb6k3QRjk5Ur+AxQxACQ=",
    "dict_tx.md": "eNqNVE1v2zAMvftXEOhhKZD4B+w2rDsWGLBedrIZi7a1yJIryfn493uSkyBu13S5RCZF8vHxiQ/04tkGbqJ2llotRpHS+Yv9qSgeHigeKy6bsC+K724YmIKM7DmKooOOPTH1wko8eXcoqY5HW5MOFHuheJNaqzXVik919ijE0+o3fpvn583T0yOcYvezEwcxbhRqnBI4GrExzK6BO6vjpIRcmw08uMlG0pbyLTp4HaNY4kBKGj2wQTudjmFNbBUQaH9GoL1kZF+p1oDMSgG0WwLIIW6KCOGdBGq9G0jH8sLLtoyJlxfefsKKVh+TMrqAsI95YaM5vGEm25Ivt/+WG7ChnDHs7/NBo9PgLjUpRyAyJ4oHd/YngjOlZ+J22qr3zD3dI+7XR7Q15VbbovhG+IPKUH10PpJhrQhsJ/ztEKt4bMpBlfSDm55Q03mVSHRWEqsXBczBc+4QEdaKhP/U6/qabIShd1OQ3hm1NLeTVdp2WY2oyJGCG25Vyt5rdJl6vo1rULNzaO+TwHXq1zoCyqibCWMjdCoesmmMxggqL+1VPleQc9pV3fdVOtUpSz57KcOr0VEgnhSxwO98ti2wQUex927q+nnAIcI7oDDkeLpV45wvMJqAeGUvSIBuH88SaXr2nVQ3z3UnMubS2ZMQHgBdLsK6I85MV0qxZbsDSqhcEr3ZBvJsSrtlw7aRcJHClZsv4cpySC1fpHK1ZSX8i5zl0FYhqsqI6jCNQT3OImP1pzKuK8cksZ8ag7z/9oO8XqeH6ZwfDyDCMQnwk52GLa6vliSkt5+36futgceEVAj1Nm+BbK9JUB156r1L+wbdYD8Inu15Pns2k8zprByW+2Leni1iGPNIUe/gzEk29XyLUpGy+AurxDQc",
    "env_a.csv": "eNpV0M1qhDAYheG9V+EFnEKSLz9mbbGltKUrt0NGIzMgiUy00LtvVOp0dlk8fC8nPnxjuI7+FCJGd/YjOjdjWEKP4H1/WlKPOPlw6or2Uwk070+KMYXzksrJpYRaajRWQRCkMFS0TcVWRZYq1O62A6HBZUZcV7poP6w+Dk1+Ljt389nZ3TEOIbWU2Sl7uNc4Xnv3g1rk8ySwXhNUZdXk51/wQW3RCtwKytEXvkWlqAxSd4lxLAfv097dDjJoaVTeKdmRffZhdiNqwzdEBK60Xmfqe/U/2qISkpQp2jdjjubXJYa8UhEaTiBDsJqpdSXdv/URifyVRMLo4hcwIGq2",
    "env_b.tsv": "eNptj71OxTAMhWfnKe4LINVxfkeoVDEwgZQVValviVSSq7QMvD1JL2JisC3bR9+xY1kYrmljONLRcpwPXkv9fo/n4isvKa/3JjMvUG6czwnnYxfhTRNMLw9opYQ9fpSyXa7MO4zKw4QESKqHJxGe0HWp1tbBjY9LnCvfddKAtAjondQiPFvTdRb1AGstkWvqQGpGXoPUsgEdOREelfkDfvKS4rzB2Didp4wHM6BqvIlOX/Kt/neiNKqFVoMIr8qe1uQ0jHNtEvP7BQJJRCd+AM1kTSI=",
    "env_c.jsonl": "eNqN001LxDAQBuC7v2LpWSGZyeRjb1JdBT2IglcpTXYJaCu1nhb/u00PMtnItsdJCg/vO+mxapvxre19qLabqlauutxU+/7dhyEd7B6viIydD787//fhDiGdRZ+G12sp0tQ1H/PlQ/Rf8xxCuidrp6H/DF3sDtMshUUpfy6Oi7QCa0raEaPvz9JKYkZbAVTAIArYKHILmV9Acfgu7kcuS9SZrARpV9CEK+uWyOt2ltPPoRuZjCeZ0RgSa9pGh0uLvgFzrm2R71kb1CWsV0bO1lxTFrluBu7iSWKayi5gxJWJQTP41kkO+zgbbM9C5aFJWbPG/v+JZXt+ssDtw9C3YYiBVw65Dgh6+rN+AaEeAcI=",
    "fmt_txc.md": "eNqFVktv2zgQvutXDJrDtoBk+LHP5JQNCmwvPXRz6G1LS5RERCINkrLjID9+vxlKthxnsQcHCjnPb74Zzg3F53/KxdZY6tTRDTHLTgcmkCJ8KH+k2nT6Fv+2WlXa5xRbbfkPeV06XwVyVpOqo/akrMPFJKMoegVlv6DPew1L/dBFU2yPUZOxUTfQcDXsP+uKDqaKLfvdmqbQtjLKLrLs5ob+ErdZ9grZOuhIr6PsKzR1V9Fr9loUxekHwSXufsaPg7z/++HLF2KfgX48fn9Y/WAFuV6JiQ4BIj17pL3qBp1Tqbw/GtuQddRrZfmTVX6B+Bq/lDaVbrAxp8EG01jNYXC0X4d+i7S0LV0FxZBl97Drka5gas/yEwIHb2IEWkHv8XdrYqAdjjninDqtQiTWMLUpFaw03g07hO1DvCMtsAqg2yFKvh0rAFU1uW1VIDbamqZl83CEsJWtkrg7zD1DUauyTSYFCJESpwu6pzH2WUYnN67jhEX8xTQvqqHa+T6FcpnyrWgBa9rz9Yv2jpyn3nnNJlsuKoJe7xEmWd2oaPb6pIGbYr0vVguGtlJHsglyqUfgkzCycb1c/1osfy82q9vx+49iuWIXrLbKZwLT4XJ2uJwOi1XCS25Wy5mNzSpx9FvqhCz7zOCNBNnqxtgAsoKrgEB3uowuFXZBfzLaSzG7oo8MWjw4roZG+bgUOcwowUFNGdbe9dCJjjafqGFMzl34UwB+Ffp0SZ1B8qrLYbh2HUwWziIt2qryqfC61h7sTCHglDuqV/6J/fSq45qhUsloTofWICGmEJpB9Qxx6roxgw1H8xspVI7LuKCvbkqflTgk2nClpCAc7oRDPpJ3kgZ9Ek8xM2xQZTTOTomrM88W9DjPeS5sKi6LkFpHdvc45o98tsf/sj21H3zUDGmlSwMcqDINNBB68pea6ow35HaYUjz8xDJnmoPgEEEQEADNeWYJAuOkmngp1b6OZDbHoDhWEbolm+i0bcCjjzxr02iYBsknmbaYOHvduZ1O4hKI4spirs1GYD7vGIH1sqPZ84k08D2T7nRI6M7OLiHZ6lpamMfL+6YvKcj2jUDAz8zOBSNwvJ/j/8WNYTCGIYkbZmycMVqKJb3I5UpUvk2MTJZKbdMAlIwwFq/d5GOQoImq0rRzl+BzP58mVlRPLCNta6LMqzO2Y7BW9TrBGvA1MxTeRXYcN4OVVylEFZPPM45Z9uHxHcUPU2+MF6YHKAbqHZDHmZZ0THrY+cXn3sc1evTEb/F0aDU/8TywGWAjUJ9gvrvo6vxqoqDFbdkNlcYdJs8VodjDCQMpJAtY/RynwHkqTm05Yw+g8DCn+1088kM1tc+odWhdeNsjvYplq2WyzQyBBf6IJcD1O0y1SiiD3QiGGsXkctN0KVUASOBBGlticqTDzNxYR6tlsIvxO9Dq3fAuosKqINLJA+9VKBBn9qaHrnh0SnKk8tvciLuDH8rr1svTI4qshbNvA7899+hyotP8Pj/fr+RSFsOq0pejASUOePDH9e4xrYipoLK81G7w48LG78p8Z9qsC95gAFD5FIY+9e/Dt4dis06P6M51R+t6A2jZT+kAhuWIpLNfOrPFo1H6crPmYY1YIZgWi+UnWX7OC9UIH/fCFP44uNNKe5+uUunGU4BaozBhwk+dY6UtmCuvrB+6k3VjdwO/Mv8C0mv+Pg==",
    "fund_codes.pdf": "eNpTDXBx0zXUM+EyVDBQyE/K4rKxUdAPqSxIVdB3TixJzMlPV9APSExPLVYwAioIUrCz40rNSwEpNMLQAFGn752ZUqwQbQxSHgs0Jb80r0TBEEmjMVaNILIoFagUYo++b2pKZqJTfoVCtAFQwMzQSMHc0ghsXl4JUFmxgglEXVBqcX5pUTLQYpB5bkBZCMNQwRTqYAiC2W6CZLtPal56SYaCobE5UENmTklqEZDOSSxJdUlNzk9JBekqLilKTczlqriVetqbr8lAoOHh3zlJZmqzMpa4KurdmXGCs4rxll8li9WS/t/dmw6//f+0XnOHGVOrw9MF0yLuc4WI9fl+K/sgK7WtZeVV4bkbn8usfH5y0blti7+UluUZlDiZOjWKB+Z+ftzn37P5XnngursFERZbXr7Xeupfe8a41fZUluunzkNCbTv25rOy/2BYp2bqC/IG1E1QD5liBCc4EPSDS5NKwFyQoKGCvlNicSpExiM1pyy1JDM5ESlYKopS07iA4cxlAAcKZqamxqYKaQoIMUsFiEweQszUAkPM0NAUQ8zIxBBDzMTUACFWUpSYmZNaBPZGcGZVqoIZMG7z80FJB5ruiksSi0rA7jQ1MuBSVXX1d+MCAAz/2rE=",
    "glossary.md": "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",
    "hh_core.sqlite": "eNrtmD9sG1UYwO/ssxMn9j0nres6tpszqGoics399d2pDHVSJ2mbOKntmg5AdLXP9RHnHNlOpW60G0wIMYNgAAaEGBgqhg5IIP5tSEggOiCQ6ICQAImFhXv37pykQoKlCKTvJ9l+3//ve+8tz7Ur6/bQ4tq9/q455GQqSdE0dZ7jKIoKuZ8odUDE/TCHZJr6e0LU2SaVwMFsiUJvIJX9hX3ZXQIAAAAAAAAAAAD/NzYj0fTsLN0bmte71o5l7W3vdU1ntIguV8ulepmrl5bWy9xIzc1Zzs3tZq9lcfXytfoC5ynxcv4ZZgwnvB3zMmI3s2ubg9EiciTjSM3NkR+S7qHsA9tpkvX8UjiaTqVo28vetsmHOZITa7g5/L3t9PwMnc5BvvmdEGnxtJek09sfuF/d1mgRPpJupObmDmdZ4Nrmrt29te2Yu4GmZQ+Gfbs53LZb3MVKvbxars4/TY+l83n69qRXLPAIfkNHSgVabu4vMh1KPyo5773N0acU+g09QPfRl+4SAAAAAAAAAAAAAID/KuORMJ0yyqVafZxxVwtPlWv1WDhMpydqm1fra7GQuyxUev1hZ5IO09lzy+VKvVpaJ+//1yj0E/oafYzed5cAAAAAAAAAAAAAAPy7HIswmTy9tsZrYrFi7pi7+33TSDJMJo2Vqixd2bcdZ2IqzGQyWCOpypY17PduFqZCvkqWjY1e3zL3F6ZpJpP1vGRtqW85jumcw+//GHqWQj+jb9Fn6C56E72C7qA9VwUAAAAAAAAAAAAAwD8iGQtnMyvrvKaoBnmKJ8eJRpENhbzXk2NEo6qaTt7myajvI+ma7xPx88i66udh/ChBUMk/Acmw7yOqgh8VIhpRkyQ/iiYa2ZB18qcCfv/n4u9S6Dt0D72Onkfb6Dx6DEXZ79mP2LfZF9nn2E1WZtOJPxL3Ex8m3kq8kGgnVhJnEmPxH+Ofu4EAAAAAAAAAAACPhGyOmU0VNjarizfs9nDQqEmKJEgqL+i8oMxkmXyqsFQtL+7YrUGjJAqeTRR4QTo1w5xOFa5cvbh4fX/A75mDQaOiSiTW4CXhVCaw71lDvmn2rcaGUST2Ii8a+ZPM48Te6XXtlnmrsaEaxKzi8DQOx6VH4UuiHoRLSuEE80SqUCldXhw0O71el29b1qCxIh+4qLkUU0gVtsp1r3teaqx5/Rdxf4KeOc5kSQE3eWNZ1Q9qZ45hE94TbKoqGplack25aZwTl21ZztDsNlaKarAnkjwzhfcrqOjXc20iL6ozySO2VbF40MsMwjac1bNdkLTgDNxmWNwMtuFmVnSSUhB5QT6VwHvkNWM7tnPDHbFsiKO0Ri4+ataz+1YSrWUn8cnjhvY6PcdqXNIO5pRzEzgUn44/Z0XxCyvuOIUY3nwcenjzyUiei6TOjAdXp+8maJQMPdgmUcqNPdQX2US/63wUXwxsDS7GikL2WJDdzmcjzBlS+0a/17T6tlt5TSsGF080Zhns4N3okcOWLgXHKwrZMB7cu5ne4BuyNOpbL4TwaDj68Gg1VR6dpJ6ncYN4tF2rZTfdzSkpfn3JPTP8/j/JvkehX9EP6Cv0CfoAvYNeRS+hO2iI2ugauoSeRGcRh6YRw/7OPmC/Yb9g77kBAAAAAAAAAAAAAPAIiZ8Mp9L4CXt5i1eEeBpLFVVyJV2Pn8CS+7x2JU2Np7C0oRrEdhxLVUVzJVWJH8PSqlgktmksuc96Ik15cbKfM4mlZVUnEvI8dYFUZ7FUkxRiS2DpgqQRW9zzlHUiTXqdiQLpbMLrWhFIXMyrZxRJZ+NenOL3MuZNa/hZoli6pGnEFvGqqzKRGCyVDZFIYS9O9CuEsLSlS6QCjaUlkUz0J54CC+A=",
    "hh_mirror.csv": "eNptU9tum0AUfOcr/AGn0u7Z+2PqlERtU0WpxKtFYO0gUbDAqZS/7yyulzrpA0JoZ2fmzBzi8HvXjG2kfdfH3TBSXz/Hnpr6FA/j9Pb37HVou+Fw/hhibHft2Pf1NNN4jMNyEofTXFRP2lH5/ZNT3tC2nmirLZVSkVSWFEvpi+pO2gTR7B3Nzcs49pt9jDOggUrFpI0hq50pqq3xCWmM8ytZMKSVImWEsUX106gEkY75I1nS5QBtHRSgrBdr2gS66/YngFgsismcBl0oqh9aLJJCGLrFSHVPWycXFHuSxlowPYDhArof+66t3zKXEcSsvC6qG22z+1+x7ZoLF0PNBbJCagx5E9Yhn6BI2zQSrCvG45wRcGU4Cz6/zptjPc85DelJs4OtR895wMM0NnHqUhLqTIcgWLGVRVWqRVEFvP+XGeM+W6MhXHqRobkB+IdzYmk9Grh3y5hOYvJ3qjDH2AepvELvJe5cuK5SS3xoWgZW4HtQ66yPL+MQcyAMM0qxS6BgM+gYT5umnuLZP8hwxtpqVPDVubxq11ywBJwwqScpcgHfunZdRINmpPBKIrPPcm3pgyCjVRk8o83SrkP+uz9LZgGbaxwiOysutlbFtNio3IvEc8su81yZQojSuhTUlyAzBD8nfsJz6klKaESqvSv+AFgN+CY=",
    "layout_reports.md": "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",
    "layout_tables.md": "eNqNVEuP2jAQvvMrRuJQkNIcKrUHWlXaSvSl7aJ2OeyNOMmEGBw7jQ0BqT++M3ZCUnZX3Rux5/H5ezCFtUgVQoO1aZwFoXOohJYFWjeZTKdgW8Q6tr+VdDiZ3MD9z1v6BblwIhUWoZWuBNcacDzHxpCgPqIyNW4KqYVKoBQWXImQGXWotIUkl9Y1MnMJzNbLh/U8giQzOfafHkPimze5UUo0lq6+3a2XX5a/qNhogmtaqLGBflcEUltsHOaQnqFf4CfRan2pA15EGEtzsFgalW/wJN3LMIbKy2djDjofIwu4c1HVUm83hC5D7Z5FfkHwNPQY1uWIZWkJWlWLJlRJUirwHfWQIz/ZNDnNZiBHoQ58rY3rO9KzI4EGVTepMfv4pOyJhNWwKgqZIaxq4uvhxy20ptlzxSAxn9gS0VkGTYQRLL9xEdixSQRtaQhviYKBMCQ5ZrOnceAvekxZNHLASyZ680TXlonhE0neAoqs7LqfUYDe8I+ZwtsQrKiwZ9Ty4TgLJBCeHGSolAU/xfE3I9eHKqWe0RU9gTIWzm2Q9sLuE9JeeAZNEEIoB2W5gmf/R+I+xfHOGs3J/X6/uutyDjMlzubgNl3s4yqfB5mZoD2eWZ9wlSxAgCK2veRMNdRGatcBMoWninFGwwST7pDix6Qaum76tUwGKQ0J1ydBZluKN2/fkX48hwQjEwiv94kky2QlFNx/vXlNNRSOLT2Idwr/UmAP6G0Mn0lBEQToNvGwUQmzzEfh9pWFQipOu3ZkuNA/Ftcju8oI8ftois+g37uAgmZ4r4XD2Xhe1FsqkMZ0ktoiNUecs/sGwWdXW33nxSu+nf5IWBGiOQmrPjCbHymDhEExg95Iw99Z5yLa04UoOHNHMobS5E+gX3vx/Oi6y5qXlJ0VzHbd1Fma89GLRd7ALZ29Bzxicw7jkKIeZnXQC8Q8nvwFn/RL5g==",
    "office.ini": "eNplykEKgzAQRuH9nMILCFOLggtPIiGE+AcD2qQzU0pvr3Xr9n1vrpBcFkcpi5pfwq+Zmo67oeWx5Qdt4VafTDTHIoJoubzUUfxYSckr3ufW/1m/QHVUg4QdBvG6AnbqBX7nkQ4loibj",
    "prior_sweep.json": "eNqd0VELgjAQB/B3P8XYc4FNyuzLxNoOHaxNtpsW4ndv0woE7aHH+9/djxsbMkJoY4OHxmrp6YUMMYmZAIOO628QI3gojDX1gKhB0t2ncbcdyKu0WnOXiENRTa1xnqDAPa5CyPVP6FyxBWSsw+avk4qyWEjehnXpFmQNuA0d2RLqYf1t4im0MvU2VJbnGcreGG3BKSvTMsvZaZ9X03I61QlIceugU/GviO8BWuKCodmYvQCpRHXV",
    "std_codes.md": "eNplUl1LJDEQfJ9fUeCLB7fD3gn64AcseoJwcoKCj0520jMTnEmGpNdx79fbnVlXxaeQpqpSVekDXAZLYLPuKRXFQ0eoDVMb4hbGWzQbb51vUX+gUHfGt4Q18UTkQa8cTc0p400kPNPICL7fwnlwR0mYU0DjhFwWhUo+qV4qR9vACVHQtBiNiN5dXZe44Xkql8yCSbi5/4ej38vlcvELlhrnxYhjxSZkZh08k2ckjmQGFajDMEZKiSwmx51awXUv6XD4v3frH6rNFEusGjlELYEdy3O9qP8EvZCUwBIvDxCarJAf68SRXpoQB1Rnn1u6wDnOErWDmLmoJK/0uYtrQ/06J3sM0UKuG0V9BNbxGEMtpkXu9u8eog38ubxdLY5Ojr/FXwe7RRd6m7TH+ZcwdUF678hYiRbDBGlFAJU6qfJXVe8fXZ3usjabKKFmeOteSC3ttyFvgPK0p/3Um4Ek40rkxxAZU3RMcze7DjLnCz7JysjCyH7MLab9ZumjOhnK4g1xJefc",
    "std_corrections.md": "eNqFkkFypDAMRfecQlVZZNPFBbJK5QZzgUaNBThjLGILOtw+37i6wiSLWYKt5yd9PdGbpiS9eY25adi9X4OO7ZI3mjS4TDYJ9d9XLqRRaJFESe8XCuwd6WrkIznf29U+29m19EfvmXhZhFM5ikoLJ/P9GvBDk5PUnh+m+6RZqMvy0ZFHpeES3STovQqspsNAOF4l9lLIYb8UMudeovNxrMUvZ1fim25C3sgpFKyWEUdHnASN4KPXNZq4tmleqdvUu+5EoCQzCBkIDCJxzFz/D0nnQ6wQvbjzYW7pNVLHM7x+wJbAvdSRzjxGb6uDxvAT/wzzuXjRbT/Ouo3DKt3RMNo1pFCa+CuyVJrzj0fK19kUKdHo0QOskJYhuMPs24YjISV0kUq05drJGXL8D88mZFMSCknY7VRGhv77ieMIGKY8IYzqlxWDLy/8IqYj10qaOQyaZkAQeVkl3MB+eS2hODa+fqwcvO3te0b9EVgm2STtZ+5/VyY/wrpg2zAIAI7hyjAAUY1/Ux8bhPKFs53QbfMF1tUs3Q==",
    "std_ledger.md": "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",
    "std_sweep.md": "eNqdV8uu4zYM3fsrBNxFp4AnP9DV9LGYRVGgM8AsB7JNx+q1JVeUk6ZfXz4kR05up0BXSWyJPCQPD5kX82vwaXoPfjDgLzCHFQxeAdam+TzlryZuHk3wPZgxRAO2n8wUNoQpzIOxY4JoEh2eYTjT18mi6eeAMJh3mIav+vi0DN+fzMdklnABNFe6C2YI82wjmg4SOfJipcAgjyM5hdoVofRwIR/lwv4OT4bxrjbaBRgQTgDJvOvH89cII0Qg+IzBnB37fwjCJTSYbEzOn81gl5U/o03QyqvVJscGBAE/iGGjb91GkaWT+Y1QLg4j2IFyRXER8rRnD6dwRbOtxnmzWH8zoztvUeOT3xHWEBO2FFVvCZHhEG/5th42I8CAYnQH3RqE8wI+taYnpOdAdxhfsh1ByEZPTfPyYn5nuChvKcoEdXEJha0ycQ6EjJBKhJTVDzlWyQ6aMYZFY0tkjbPU2dlSarAEvZv6Du+1vNtJk01KqBQklUy9GexelJ2GbIMd5NocvJl13lBLEzAR0+xC1qkUPwJRFAQI2fBSRvGrOT0YzwYivNdMZNuass82Um2xaT74/RZFRMWMabTzbJyWQx2b7kaUdgSfTXoqloG/eqnZW/C5EbhJrFvYzn5nj2p3oyeTgCku6wyvIcwmuQX0nphszeAubiB7hEpqtS2lOnJAasUx/Gu9Ws0aDOr/bNeCM0OZAd8OrVUOstdVGiI71irkCCpAtsMwbwnYx39wSOryCVIiRaG6VKQlNcHdIfn4G2IwxLNM1JiU5TsGVCManBYfvPZX3CNgnpYLPghpFcLPkTRPDjH5KPam+aVmLoEe9IhyI2eOk6iVYlhHkakKJpJHbiMMVRVE3GqqU2L+3KyWsPZGpWPmrUkjuE5ZVg9nSHglJDsMLEzUiZyxVg5qHRmaHf7YMLHCUMG6FG2fBLsjuQ+JfO9icEBWirj32tWlSQcEcwfToeakDEsgZ3fZl+MS3HzTK0eSKMzRRSyuCIR9zXm9g34zaRUPpNiiFo9pKAyW5noldmgBL3besjp8ovCfWIj8UMSzuFBeUuY80ghiInDXsZMn6jlfU67LwPwtTaKBRejaqpl6DclK/vbHyES9x3CHp4F8Q7uLdxZr1ADrEYl59toZg+lv/UwWSjai4/yzz8xrzsw1RKwlmMMnw3z2ZL4UYuoDDYamFjUSvCFzeQC3T73DVic7Xzg1MlyZpi54rfQKsWf+diCDPYZ11YPDs2+ZfJ3tXwsRNLifNNKmEcSlsnliHTMslZcBS3yRPWiCuRSzfTyMexK/yYX/X3HK2+g89eleZptH4xyu3IcKlXIlKw30IUoM62z7fYfZ73JEsmjdN4q8AB27QJD3QXQuZCEY6r6b7EWKt1G2MG9AeT/Bp+WqFTkIW1LNpoutcpNN0DKaU9hq4oJSSq+SDjqV6Tvz62jSJAskhfQDiaEZt8iKUA0JHhzMFmSxzDND1DBx8kbaXXmxq/pGMvNlKoNHd2fdw3TjEkQPC5dDkXx6mqdSW5qvLdFJEGXZ/FgyhGU3zEPVb0tH+MlQfk2+SHn0RmmZ45VjI+UC68xwB0qSJBzWoAOvirXy8y3ZoZzIskcJYHmpOcp/CIb9r0ChKK0IrQmsN7ok7otJ2Rse9i6dCTWqsoCJkj8uea32EgcvywL/sbG+mlmi3EeDAwsEj021TMBOzT+KgL7h",
    "stmt_fees.csv": "eNpVkEEKwyAQRfdzFoVxxtHOOiC5RShiY6G0kKb3r8kqs5PHf9+v9fVs733Z2sPtffv81u5qv29rW+rgX5hnTxIdISWP6mkcVaAEvqKE6QjmkEwwIhSVKwpJYYo2RacrTJYyFIsiDTcHU6d4uMxq3HSDScxAFh73mpTgqCO06yJMbMQg47FkBrPy+SucTV0O8AdnakX+",
    "sweep_tab.xlsx": "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",
    "tot_q2.csv": "eNpNzEsOwjAMANG9z2Kk1Gl+x+AEKGosUSnU4Ljl+qyoupy3mLYO03Ux/OxVjRXfIv3RpPeqA19ycPsXLLyZ1o7kKN7uhNk7h/M0A9dhp8Y8BaRYYBO158kh+IhUEgzZLxxTIPQ+wZevD08ZCyX4AQYILYE=",
    "tx_a.csv": "eNpVkr1Ow1AMhfc+iyv87+sRCVUICQZaZa9ohy5BgoLg7XGT0DRjdPwd+5zc808Ph/0vHPtveDv25084nD5WO3VMBUb2NeYaHbpNQ2ALhlO/2pGa8FUmgu6REIhQGd6/zsVTa3QdYIPuXh3CfMDVWsisSuHhYP9yakjMcrm/an1TWozuSd7m9YzQvWhdl2g8GTC3+TyF7ikCJEVoNLCUsHkgKp4bWKYMvJv5zGPJDxzQ3+0nuuBYpB/WB/q4vonGTXk64qQ5lSPEjgv7jRpQqOGUr/q5OY+rvWxgLDg5ODL5XEBCtzUBl7E/KVEW6S44kVTpI57YbNHfpX8yqh91MYggngNi2T9bgqDXQxgTcJovEmxZIbNGB51aOUx6W1frw/MRtEH+AwnSjrY=",
    "tx_b.tsv": "eNpllM1y2zAMhM/Mu4gGCBIkju00h06nf6n7AIqlxJo4ksdyDn37QlRiMs7VWi6W34IeOnOc5nPfmfYwtLNpn6eX8WyehrG72QpRFOPAcQPSODS//37dHPfT2OuPNkTz5WYbvfNw0cCq6frx3B5MAKvn/6iImUIRsfl8d7s59udm1556g8iW0mKW2LMvupTN9tNh6Np/BgksyCITDN6VXPBexmjVRKcSYKTiFvNUnWgwBMuQgwFiKhJnfnz6tkrIWb2wSiQwV5Jgvv+82zyepl1/GvrZkLCNeZxzGquk4uz1NHSzWTI7B7F8RTC/brebebefpkPz0KsRi8UMwaGkQh1fqb/B0nF6OINnqspZo18gBLQps0KRmhXluWuHS/K1Hhf5XYdvoFi8TZSRE0uRoKtsEIP1uIgYyMd6Xxaf574bdroMhGj1nMoChJiu67t/mZtjOytQp3ZrORIh1MguQBFk8VINJ6hhQb2ifkGgmqSxKvQp+3TDOIyPjdN9iVbyKntIiQsGvzY9PJxn40SsT4sZQuKyVBizqO4RY7QhZ3NAMV7PzfmdkPV5JlGq18J9sAvJcm4ghIB0TWO9hVFkISOTSFDZSa6pLGsS69ZboNQP0uem1mjRWf20VA76Guua3i2YJ4shj/QUigz5ww1ylYRerh/2a01hybTgT5z8daaT/pNoprBW9B8qghIe",
    "tx_c.bin": "eNoLiXA2LGFQY1jzjomlzNfYSOTONCaGru/MLGWJJmZqcycyMkzJZilzNDSQu7mTieFANlicbTUHw5eDTCxhLkbmIj8PMzO8/szMEhZgYaQz6yIzQ9MbRrAOvVNHGBnmXGJhCXMytFB5U8Gw4zmErbF/FjPDofdAC4tNjQUOszDMWsvCUpZmbCH05gYzw/enjCxhvpZmVv08DNtDWMrSDc3kNj9mZFgaCLbP6gojwz+QQcFGJlK3+pkYZm5kAtst0biYkeHyJ6DdHoYGbMfWsDPM+sMMVqZx+C0jw+x4sBUGN4HObd7ICrbCYZILw59SMFOttYuJ4fJCiG6HNYcYGe43sIItV5l2kpmhcyHEtUwzJjEx3NzHCA4GvqczmBiW/AIq8zMx0Hn6jp3h6h5gwKWZmWo9kGbYEMAS5mppyPX0JSNDNyh8gLaY3ONgaASZC7RE6uZlZobF21jAqiSO+jG8eQsJBZYJnxkZFt0CmpRsasH0+RwTw8d5QJlcU0upVa8YGfqfMYGDV6v1OjPDlc9AnwSZmAv89We4/AioKs/USObOZWaWJWeBNnqYm3Hx1Nx8AQB5d55/",
    "xw_columns.json": "eNqFkUEOgyAQRfeewrA2HqCXIQhjY0OHRtCkMd69DEirLdgVw38M8GCp6poBzly00s7sUi8+8JEUzk9ogKsZn1waBayJzC8nRl37uB80cDSEUpnIhCrEfhzweujSogNNMBZbigCKTzZ0hVoZrcVoEzcPQC6JUhX2BHSWebo2Salr3ZfSzqUkl2DOrqD2ViooksCZyOf6Pz7bKje4eHp8pIOlbG/WoD54niv2RisYCzKnJoPKPQ2KO2R/8I90/vuqtXoBrz3AIA=="
}

# ---- extract generator ----
import io as _io
import json as _json
import random as _random
import sqlite3 as _sqlite3
import zipfile as _zipfile
import zlib as _zlib
from pathlib import Path as _Path

DISTRICTS = ["central", "east", "north", "south", "west"]
SEGMENTS = ["consumer", "corporate", "enterprise", "smb"]
CATEGORIES = ["family", "food", "health", "housing", "leisure", "transport"]
LABEL_CATEGORY = {
    "groceries": "food", "dining": "food", "Rent": "housing", "utilities": "housing", "Garden": "housing",
    "Phone": "housing", "Car": "transport", "bus pass": "transport", "medical": "health", "Dental": "health",
    "insurance": "health", "school fees": "family", "Kids": "family", "pet care": "family", "Holiday": "leisure",
    "Gifts": "leisure",
}
SURNAMES = ["Abara", "Brennan", "Castillo", "Dimitrova", "Eze", "Fontaine", "Gallo", "Haddad", "Ibsen", "Jovanovic",
            "Kaur", "Lindqvist", "Moreau", "Nakamura", "Okafor", "Petrov", "Quinn", "Rahman", "Sato", "Tanaka"]
PERIOD = ("2026-09-01", "2026-09-30")
SHARD_COLS = {
    "env_a.csv": ["env", "file_no", "label", "cat", "fund", "need_usd", "open_c"],
    "env_b.tsv": ["code", "file", "title", "category_code", "funding_code", "need", "opening_cents"],
    "env_c.jsonl": ["id", "folder", "name", "cat_code", "fund_code", "need", "opening"],
}
CANON = ["env_code", "file_no", "label", "category_code", "funding_code", "need_dollars", "opening_cents"]
_STAMP = (2026, 9, 30, 18, 0, 0)
_MARKS = (b"TO" + b"DO", b"FIX" + b"ME", b"X" * 3, b"PLACE" + b"HOLDER", b"{" * 2)


def _day(rng, inside=True):
    if inside:
        return "2026-09-%02d" % rng.randint(1, 30)
    return rng.choice(["2026-08-31", "2026-10-01", "2026-08-30", "2026-10-02"])


def _split(rng, net, parts):
    while True:
        vals = [rng.choice([-1, 1]) * rng.randint(100, 30000) for _ in range(parts - 1)]
        last = net - sum(vals)
        if last != 0 and abs(last) <= 99999:
            return vals + [last]


def _esc(v):
    return str(v).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _zip(members):
    buf = _io.BytesIO()
    with _zipfile.ZipFile(buf, "w", _zipfile.ZIP_DEFLATED) as zf:
        for name, text in members:
            info = _zipfile.ZipInfo(name, date_time=_STAMP)
            info.compress_type = _zipfile.ZIP_DEFLATED
            zf.writestr(info, text.encode("utf-8"))
    return buf.getvalue()


def xlsx_bytes(sheets, remap=False, alt=None):
    """sheets: list of (name, rows); cells are str or int. Inline strings, no shared-strings part.
    remap: worksheet parts are numbered in reverse of the workbook order (ECMA-376 resolves sheets through the relationships)."""
    ns = "http://schemas.openxmlformats.org"
    head = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'

    def cell(ref, v):
        if isinstance(v, int):
            return f'<c r="{ref}"><v>{v}</v></c>'
        return f'<c r="{ref}" t="inlineStr"><is><t>{_esc(v)}</t></is></c>'

    def wrapped(ref, v, other):
        return ('<mc:AlternateContent><mc:Choice Requires="hes">' + cell(ref, other) + "</mc:Choice><mc:Fallback>"
                + cell(ref, v) + "</mc:Fallback></mc:AlternateContent>")

    def sheet_xml(rows, choice=None):
        body = "".join(f'<row r="{i}">' + "".join(wrapped(f"{chr(65 + j)}{i}", v, choice[i - 1][j]) if choice and i > 1 and j == 1
                                                  else cell(f"{chr(65 + j)}{i}", v) for j, v in enumerate(row)) + "</row>"
                       for i, row in enumerate(rows, 1))
        extra = (' xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006" xmlns:hes="urn:household-office:sheet-ext:2026"'
                 if choice else "")
        return head + f'<worksheet xmlns="{ns}/spreadsheetml/2006/main"{extra}><sheetData>{body}</sheetData></worksheet>'

    n = len(sheets)

    def part(i):
        return n + 1 - i if remap else i

    ctype = "application/vnd.openxmlformats-officedocument.spreadsheetml"
    members = [
        ("[Content_Types].xml", head + f'<Types xmlns="{ns}/package/2006/content-types">'
         '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
         '<Default Extension="xml" ContentType="application/xml"/>'
         f'<Override PartName="/xl/workbook.xml" ContentType="{ctype}.sheet.main+xml"/>'
         + "".join(f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="{ctype}.worksheet+xml"/>'
                   for i in range(1, n + 1)) + "</Types>"),
        ("_rels/.rels", head + f'<Relationships xmlns="{ns}/package/2006/relationships">'
         f'<Relationship Id="rId1" Type="{ns}/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
         "</Relationships>"),
        ("xl/workbook.xml", head + f'<workbook xmlns="{ns}/spreadsheetml/2006/main" xmlns:r="{ns}/officeDocument/2006/relationships"><sheets>'
         + "".join(f'<sheet name="{_esc(nm)}" sheetId="{i}" r:id="rId{i}"/>' for i, (nm, _r) in enumerate(sheets, 1))
         + "</sheets></workbook>"),
        ("xl/_rels/workbook.xml.rels", head + f'<Relationships xmlns="{ns}/package/2006/relationships">'
         + "".join(f'<Relationship Id="rId{i}" Type="{ns}/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{part(i)}.xml"/>'
                   for i in range(1, n + 1)) + "</Relationships>"),
    ]
    members += [(f"xl/worksheets/sheet{part(i)}.xml", sheet_xml(rows, alt[1] if alt and alt[0] == nm else None))
                for i, (nm, rows) in enumerate(sheets, 1)]
    return _zip(members)


def _docx(rows, intro, split=False, alt=False, move=False, inline=False, alt_rows=None):
    ns = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    head = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'

    def para(t):
        return f"<w:p><w:r><w:t xml:space=\"preserve\">{_esc(t)}</w:t></w:r></w:p>"

    def alt_cell(t):
        r = f"<w:r><w:t xml:space=\"preserve\">{_esc(t)}</w:t></w:r>"
        stamp = 'w:author="office" w:date="2026-09-30T00:00:00Z"'
        return f"<w:p><w:moveTo w:id=\"1\" {stamp}>{r}</w:moveTo><w:moveFrom w:id=\"2\" {stamp}>{r}</w:moveFrom></w:p>"

    def runs(t):
        if alt:
            r = f"<w:r><w:t xml:space=\"preserve\">{_esc(t)}</w:t></w:r>"
            return (f"<w:p><mc:AlternateContent><mc:Choice Requires=\"w14\">{r}</mc:Choice>"
                    f"<mc:Fallback>{r}</mc:Fallback></mc:AlternateContent></w:p>")
        if inline:
            r = f"<w:r><w:t xml:space=\"preserve\">{_esc(t)}</w:t></w:r>"
            stamp = 'w:author="office" w:date="2026-09-30T00:00:00Z"'
            h = len(t) // 2
            r2 = (f"<w:r><w:t xml:space=\"preserve\">{_esc(t[:h])}</w:t></w:r><w:r><w:t xml:space=\"preserve\">{_esc(t[h:])}</w:t></w:r>"
                  if split and len(t) >= 4 else r)
            return f"<w:p><w:moveTo w:id=\"1\" {stamp}>{r2}</w:moveTo><w:moveFrom w:id=\"2\" {stamp}>{r}</w:moveFrom></w:p>"
        if move:
            r = f"<w:r><w:t xml:space=\"preserve\">{_esc(t)}</w:t></w:r>"
            stamp = 'w:author="office" w:date="2026-09-30T00:00:00Z"'
            return (f"<w:p><w:moveTo w:id=\"1\" {stamp}>{r}</w:moveTo></w:p>"
                    f"<w:p><w:moveFrom w:id=\"2\" {stamp}>{r}</w:moveFrom></w:p>")
        if not split or len(t) < 4:
            return para(t)
        h = len(t) // 2
        return (f"<w:p><w:r><w:t xml:space=\"preserve\">{_esc(t[:h])}</w:t></w:r>"
                f"<w:r><w:t xml:space=\"preserve\">{_esc(t[h:])}</w:t></w:r></w:p>")

    table = "<w:tbl>" + "".join("<w:tr>" + "".join(f"<w:tc>{(alt_cell(c) if alt_rows and k in alt_rows and j else runs(c)) if (j and k) or (split and not (alt or move or inline)) else para(c)}</w:tc>" for j, c in enumerate(row)) + "</w:tr>" for k, row in enumerate(rows)) + "</w:tbl>"
    doc = head + f'<w:document xmlns:w="{ns}" xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006" xmlns:w14="http://schemas.microsoft.com/office/word/2010/wordml" mc:Ignorable="w14"><w:body>' + "".join(para(t) for t in intro) + table + "</w:body></w:document>"
    return _zip([
        ("[Content_Types].xml", head + '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
         '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
         '<Default Extension="xml" ContentType="application/xml"/>'
         '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
         "</Types>"),
        ("_rels/.rels", head + '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
         '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
         "</Relationships>"),
        ("word/document.xml", doc),
    ])


def _content(lines, pad):
    ops = ["BT", "/F1 11 Tf", "72 740 Td"]
    for i, ln in enumerate(lines):
        if i:
            ops.append("0 -16 Td")
        ops.append("(" + ln.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)") + ") Tj")
    ops.append("ET")
    ops.append("%" + "p" * pad)
    return _zlib.compress(("\n".join(ops) + "\n").encode("latin-1"), 9)


def _pdf(lines, pad=0, old=None):
    """old: lines of a superseded first revision; the file then carries an incremental update (ISO 32000-1 7.5.6)
    whose body redefines the content stream object with `lines`."""
    stream = _content(old if old is not None else lines, pad % 200 if old is None else pad // 200)
    objs = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
            b"<< /Length %d /Filter /FlateDecode >>\nstream\n" % len(stream) + stream + b"\nendstream",
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    out = bytearray(b"%PDF-1.4\n")
    offs = []
    for i, body in enumerate(objs, 1):
        offs.append(len(out))
        out += b"%d 0 obj\n" % i + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    for o in offs:
        out += b"%010d 00000 n \n" % o
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, xref)
    if old is not None:
        new = _content(lines, pad % 200)
        off = len(out)
        out += b"4 0 obj\n<< /Length %d /Filter /FlateDecode >>\nstream\n" % len(new) + new + b"\nendstream\nendobj\n"
        xref2 = len(out)
        out += b"xref\n0 1\n0000000000 65535 f \n4 1\n%010d 00000 n \n" % off
        out += b"trailer\n<< /Size %d /Root 1 0 R /Prev %d >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, xref, xref2)
    return bytes(out)


def _clean_pdf(lines, old=None):
    for pad in range(200 if old is None else 40000):
        blob = _pdf(lines, pad, old)
        if b"\r" not in blob and not any(m in blob.upper() for m in _MARKS):
            return blob
    raise ValueError("no clean pdf")


def _sqlite(path, tables):
    if path.exists():
        path.unlink()
    con = _sqlite3.connect(str(path))
    con.execute("PRAGMA page_size=4096")
    for name, cols, rows in tables:
        con.execute(f"CREATE TABLE {name} ({', '.join(cols)})")
        con.executemany(f"INSERT INTO {name} VALUES ({', '.join('?' * len(cols))})", rows)
    con.commit()
    con.close()


RATE_LO, RATE_HI = 12, 50
PLANT_KEYS = ("S1", "S2", "S3", "N", "S23")


def _half_down(num, den):
    q, rem = divmod(num, den)
    return q + (1 if 2 * rem > den else 0)


def _charge(rate, s):
    """Keeping charge on one envelope in whole dollars."""
    return _half_down(rate * s, 1000000)


def _cents(rate, s):
    """Keeping charge on one envelope in whole cents, as the fee statement counts it."""
    return _half_down(rate * s, 10000)


def _rows_of(envs_all, S):
    """Fee statement rows: ("hh", district) or ("fund", funding code) -> [(plan, statement balance)]."""
    rows = {}
    for e in envs_all:
        for key in (("hh", e["dist"]), ("fund", e["fund"]), ("cat", e["cat"])):
            rows.setdefault(key, []).append((e["plan"], S[e["code"]]))
    return rows


def _tables(rows, stated):
    width = RATE_HI - RATE_LO + 1
    out = []
    for key in sorted(rows):
        f = {}
        for p, s in rows[key]:
            col = f.setdefault(p, [0] * width)
            for i in range(width):
                col[i] += _cents(RATE_LO + i, s)
        out.append((stated[key], f))
    return out


def _narrow(tab, dom):
    """Bounds propagation over the statement rows; False when some row cannot be met."""
    changed = True
    while changed:
        changed = False
        for want, f in tab:
            lo = {p: min(f[p][i] for i in dom[p]) for p in f}
            hi = {p: max(f[p][i] for i in dom[p]) for p in f}
            slo, shi = sum(lo.values()), sum(hi.values())
            if not slo <= want <= shi:
                return False
            for p in f:
                keep = [i for i in dom[p] if slo - lo[p] + f[p][i] <= want <= shi - hi[p] + f[p][i]]
                if len(keep) < len(dom[p]):
                    if not keep:
                        return False
                    dom[p] = keep
                    changed = True
                    nlo, nhi = min(f[p][i] for i in keep), max(f[p][i] for i in keep)
                    slo, shi = slo - lo[p] + nlo, shi - hi[p] + nhi
                    lo[p], hi[p] = nlo, nhi
    return True


def _solutions(rows, stated, limit=3):
    """Plan-rate assignments meeting every statement row (at most `limit`)."""
    tab = _tables(rows, stated)
    plans = sorted({p for _w, f in tab for p in f})
    found = []

    def go(dom):
        if len(found) >= limit or not _narrow(tab, dom):
            return
        open_ = [p for p in plans if len(dom[p]) > 1]
        if not open_:
            found.append({p: RATE_LO + dom[p][0] for p in plans})
            return
        p = min(open_, key=lambda q: (len(dom[q]), q))
        for i in dom[p]:
            sub = {q: list(v) for q, v in dom.items()}
            sub[p] = [i]
            go(sub)
    go({p: list(range(RATE_HI - RATE_LO + 1)) for p in plans})
    return found


def _nearest(rows, stated):
    """Least-squares plan rates ignoring the cent rounding, each rounded to the nearest whole basis point."""
    from fractions import Fraction as _Fr
    plans = sorted({p for terms in rows.values() for p, _s in terms})
    ix = {p: i for i, p in enumerate(plans)}
    k = len(plans)
    A, b = [], []
    for key in sorted(rows):
        r = [_Fr(0)] * k
        for p, s in rows[key]:
            r[ix[p]] += _Fr(s, 10000)
        A.append(r)
        b.append(_Fr(stated[key]))
    M = [[sum(row[i] * row[j] for row in A) for j in range(k)] + [sum(row[i] * v for row, v in zip(A, b))] for i in range(k)]
    for c in range(k):
        piv = next((r for r in range(c, k) if M[r][c] != 0), None)
        if piv is None:
            return None
        M[c], M[piv] = M[piv], M[c]
        for r in range(k):
            if r != c and M[r][c] != 0:
                f = M[r][c] / M[c][c]
                M[r] = [x - f * y for x, y in zip(M[r], M[c])]
    out = {}
    for p in plans:
        x = M[ix[p]][k] / M[ix[p]][ix[p]]
        out[p] = min(RATE_HI, max(RATE_LO, _half_down(x.numerator, x.denominator)))
    return out


def _ledger_view(envs_all, rows, stated, stmt, mode):
    """Pre-sweep dollars under one reading. mode: set of readings among S1, S2, S3."""
    S = {e["code"]: e["opening"] for e in envs_all}
    T = dict(S)
    for t in rows:
        if t["kind"] == "bad" or t["kind"] == "outside":
            continue
        env = t["s1env"] if "S1" in mode else t["env"]
        if t["kind"] == "live":
            T[env] += t["cents"]
        base = (t.get("shown", t["cents"]) if "S2" in mode else (t["cents"] if t["kind"] == "live" else 0))
        if "S3" in mode or t["day"] <= stmt:
            S[env] += base
    if min(S.values()) < 0 or min(T.values()) < 0:
        return "error"
    rate_of = {e["code"]: e["rate"] for e in envs_all}
    return {c: T[c] // 100 - _charge(rate_of[c], S[c]) for c in T}, {t["id"]: (t["s1env"] if "S1" in mode else t["env"])
                                                                         for t in rows if t["kind"] == "live"}


def _plan_layout(rng, envs_all, k):
    """k keeping plans: the hub plan (code sorting last) in every household and funding code, the rest private."""
    names = ["KP-%d" % c for c in sorted(rng.sample(range(10, 99), k))]
    hub, private = names[-1], names[:-1]
    plan_of = {}
    for d in DISTRICTS:
        plan_of[rng.choice([e for e in envs_all if e["dist"] == d])["code"]] = hub
    for field in ("fund", "cat"):
        for f in sorted({e[field] for e in envs_all}):
            if not any(plan_of.get(e["code"]) == hub for e in envs_all if e[field] == f):
                plan_of[rng.choice([e for e in envs_all if e[field] == f and e["code"] not in plan_of])["code"]] = hub
    homes = list(DISTRICTS)
    rng.shuffle(homes)
    home = {p: [homes[j % 5]] for j, p in enumerate(private)}
    for j, d in enumerate(homes[len(private):]):
        home[private[j % len(private)]].append(d)
    for p in private:
        for d in home[p]:
            free = [e for e in envs_all if e["dist"] == d and e["code"] not in plan_of]
            if not free:
                raise ValueError("no envelope for plan")
            plan_of[rng.choice(free)["code"]] = p
    for e in envs_all:
        if e["code"] not in plan_of:
            here = [p for p in private if e["dist"] in home[p]] + [hub]
            plan_of[e["code"]] = rng.choice(here)
    return names, plan_of


def _near_moves(near, rate, envs_all, plan):
    """Number of households in which the nearest-ratio rates change some envelope's keeping charge in dollars."""
    return len({e["dist"] for e in envs_all if _charge(near[e["plan"]], plan[e["code"]][0]) != _charge(rate[e["plan"]], plan[e["code"]][0])})


def _rate_plan(rng, households, envs_all, k, plant, error):
    """Draw plans, plan rates, statement day and statement balances until the evidence behaves as planted."""
    for _attempt in range(400):
        try:
            names, plan_of = _plan_layout(rng, envs_all, k)
        except ValueError:
            continue
        rate = {p: rng.randint(RATE_LO, RATE_HI) for p in names}
        twin = None
        if error == "two_fit":
            twin = rng.choice(names[:-1])
            rate[twin] = rng.randint(RATE_LO, RATE_HI - 1)
        stmt_day = rng.randint(18, 26)
        plan, ok = {}, True
        for e in envs_all:
            e["plan"] = plan_of[e["code"]]
            r = rate[e["plan"]]
            x = rng.randint(0, 99)
            if plant.get("S3") and rng.random() < 0.6:
                s = max(0, e["bal"] * 100 + rng.randint(-15000, 15000))
                t = (e["bal"] + _charge(r, s)) * 100 + x
            else:
                s = e["bal"] * 100 + x
                for _ in range(30):
                    nxt = (e["bal"] + _charge(r, s)) * 100 + x
                    if nxt == s:
                        break
                    s = nxt
                else:
                    ok = False
                t = s
            plan[e["code"]] = (s, t, 5000 if e["plan"] == twin else rng.randint(2000, s + 40000))
        if not ok:
            continue
        rows = _rows_of(envs_all, {c: v[2] for c, v in plan.items()})
        stated = {key: sum(_cents(rate[p], s) for p, s in terms) for key, terms in rows.items()}
        if any(len(_solutions({key: rows[key]}, stated, 2)) < 2 for key in rows if key[0] == "hh"):
            continue
        if _nearest(rows, stated) is None:
            continue
        sols = _solutions(rows, stated)
        if error == "two_fit":
            if len(sols) != 2:
                continue
        elif sols != [rate]:
            continue
        elif not plant.get("ERR") and ((_near_moves(_nearest(rows, stated), rate, envs_all, plan) < 1) if plant.get("N")
                                       else _near_moves(_nearest(rows, stated), rate, envs_all, plan) > 0):
            continue
        order = sorted(rows)
        rng.shuffle(order)
        for e in envs_all:
            e["rate"] = rate[e["plan"]]
        return rate, plan_of, "2026-09-%02d" % stmt_day, plan, stated, order
    raise ValueError("no rate plan")


def write_extract(root, seed, households, docs, error=None, plant=None, plan_seed=None, plans=None):
    """households: district -> {"envs": [{"code","label","need","bal"}] in register order, "d", "K", "B"}."""
    plant = dict(plant or {})
    rng = _random.Random(seed)
    root = _Path(root)
    root.mkdir(parents=True, exist_ok=True)
    for name, text in docs.items():
        (root / name).write_text(text, encoding="utf-8")
    fund_codes = dict(zip(rng.sample(["F%d" % i for i in range(10, 99)], 4), SEGMENTS))
    cat_codes = dict(zip(rng.sample(["C%d" % i for i in range(10, 99)], 6), CATEGORIES))
    fund_of = {v: k for k, v in fund_codes.items()}
    cat_of = {v: k for k, v in cat_codes.items()}
    names = rng.sample(SURNAMES, 5)
    dist_ids = rng.sample(range(1, 90), 5)
    hh_codes = rng.sample(range(100, 999), 5)
    district_rows, hh_rows, file_rows = [], [], []
    shard_of, reg, envs_all, hh_of = {}, [], [], {}
    file_nos = rng.sample(range(1000, 9999), 15)
    for i, dist in enumerate(DISTRICTS):
        h = households[dist]
        code_h = "HH-%d" % hh_codes[i]
        hh_of[dist] = code_h
        district_rows.append((dist_ids[i], dist.capitalize() if rng.random() < 0.5 else dist.upper()))
        hh_rows.append((code_h, names[i], dist_ids[i]))
        files = ["FL-%d" % file_nos.pop() for _ in range(rng.randint(1, 3))]
        file_rows += [(f, code_h) for f in files]
        envs = h["envs"]
        cut = sorted(rng.sample(range(len(envs) + 1), 2)) if rng.random() < 0.8 else [len(envs), len(envs)]
        for j, e in enumerate(envs):
            shard = "env_a.csv" if j < cut[0] else ("env_b.tsv" if j < cut[1] else "env_c.jsonl")
            seg = rng.choice(SEGMENTS)
            cat = LABEL_CATEGORY[e["label"]]
            rec = {"code": e["code"], "dist": dist, "file": rng.choice(files), "label": e["label"], "cat": cat_of[cat],
                   "fund": fund_of[seg], "need": e["need"], "bal": e["bal"], "shard": shard, "i": i,
                   "mirror_need": e["need"] + rng.choice([0, 0, 5, -5, 10])}
            envs_all.append(rec)
    since0 = {e["code"]: "2025-%02d-%02d" % (rng.randint(1, 12), rng.randint(1, 28)) for e in envs_all}
    alias_base = {e["code"]: "%s/%s" % (names[e["i"]][:3].upper(), e["label"].replace(" ", "-").lower()) for e in envs_all}
    pair_dists = rng.sample([d for d in DISTRICTS if len(households[d]["envs"]) >= 2], 2)
    pairs = {}
    for dist in pair_dists:
        e1, e2 = rng.sample([e["code"] for e in envs_all if e["dist"] == dist], 2)
        pairs[dist] = (e1, e2, "2026-09-%02d" % rng.randint(6, 16))
    prng = _random.Random(seed * 1000 + 1 if plan_seed is None else plan_seed)
    rate, plan_of, stmt, plan, stated, order = _rate_plan(prng, households, envs_all, plans or 4, plant, error)
    for _attempt in range(300):
        built = _build_rows(rng, envs_all, plan, stmt, pairs, plant, stated, error)
        if built is not None:
            break
    else:
        raise ValueError("no row plan")
    rows, corrections, cutoff, ids, openings = built
    for e in envs_all:
        e["opening"] = openings[e["code"]]
    alias_rows = [(alias_base[c], c, since0[c]) for c in alias_base]
    for dist, (e1, e2, sw) in pairs.items():
        alias_rows.append((alias_base[e1], e2, sw))
        alias_rows.append((alias_base[e1] + "-2", e1, sw))
    codes = [e["code"] for e in envs_all]
    mirror = [[e["code"], e["file"], e["label"], e["cat"], e["fund"], e["mirror_need"], e["opening"]] for e in envs_all]
    shard_rows = {k: [] for k in SHARD_COLS}
    for e in envs_all:
        shard_rows[e["shard"]].append((e["dist"], [e["code"], e["file"], e["label"], e["cat"], e["fund"], e["need"],
                                                   e["opening"]]))
    _write_register(root, shard_rows, rng)
    if error == "unknown_env":
        ghost = "VZ%02d" % rng.randint(10, 99)
        mirror.append([ghost, file_rows[0][0], "Holiday", cat_of["leisure"], fund_of["consumer"], 120, 0])
        rows.append({"env": ghost, "s1env": ghost, "cents": rng.randint(100, 900), "day": "2026-09-%02d" % rng.randint(1, 30),
                     "kind": "live", "id": "T%05d" % ids.pop(), "shard": "a"})
    if error == "bad_correction":
        corrections.append((rng.randint(1, cutoff), "T%05d" % ids.pop(), "void", "-"))
    rng.shuffle(rows)
    if error == "dup_txn":
        t = next(r for r in rows if r["kind"] == "live" and r["shard"] == "a")
        rows.append(dict(t, shard="b"))
    _write_shards(root, rows, _alias_picker(rng, alias_base, pairs), rng, plant, not plant.get("NO23"), error)
    rng.shuffle(corrections)
    (root / "adj_log.psv").write_text("\n".join(["seq|txn|action|value"] + ["%d|%s|%s|%s" % c for c in corrections]) + "\n",
                                      encoding="utf-8")
    rng.shuffle(district_rows)
    rng.shuffle(hh_rows)
    rng.shuffle(file_rows)
    rng.shuffle(alias_rows)
    _sqlite(root / "hh_core.sqlite", [
        ("district", ["district_id INTEGER", "district_name TEXT"], district_rows),
        ("household", ["hh_code TEXT", "family_name TEXT", "district_id INTEGER"], hh_rows),
        ("file", ["file_no TEXT", "hh_code TEXT"], file_rows),
        ("env_alias", ["alias TEXT", "env_code TEXT", "since TEXT"], alias_rows),
        ("keep_plan", ["env_code TEXT", "plan TEXT"], sorted(plan_of.items(), key=lambda kv: rng.random()))])
    rng.shuffle(mirror)
    (root / "hh_mirror.csv").write_text("\n".join([",".join(CANON)] + [",".join(str(v) for v in m) for m in mirror]) + "\n",
                                        encoding="utf-8")
    _write_constants(root, rng, households, fund_codes, cat_codes, cutoff, plant)
    if error == "no_fit":
        stated = _break_fit(_random.Random(seed * 31 + 7), envs_all, plan, stated)
    refs = {key: (hh_of[key[1]] if key[0] == "hh" else key[1]) for key in order}
    through = '"%s"' % stmt if plant.get("Q2") else stmt
    lines = ["client_ref,through,charge_cents"] + ["%s,%s,%d" % (refs[key], through, stated[key]) for key in order]
    (root / "stmt_fees.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return root


def _break_fit(rng, envs_all, plan, stated):
    rows = _rows_of(envs_all, {c: v[2] for c, v in plan.items()})
    for _ in range(200):
        key = rng.choice(sorted(stated))
        trial = dict(stated)
        trial[key] = max(0, stated[key] + rng.choice([-3, -2, -1, 1, 2, 3]))
        if not _solutions(rows, trial, 1):
            return trial
    raise ValueError("no no-fit statement")


def _alias_picker(rng, alias_base, pairs):
    by1 = {e1: (e2, sw) for e1, e2, sw in pairs.values()}
    by2 = {e2: (e1, sw) for e1, e2, sw in pairs.values()}

    def pick(env, day):
        if env in by1:
            return alias_base[env] if day < by1[env][1] else alias_base[env] + "-2"
        if env in by2 and day >= by2[env][1]:
            return rng.choice([alias_base[env], alias_base[by2[env][0]]])
        return alias_base.get(env, env)
    return pick


def _days(rng, lo, hi):
    return "2026-09-%02d" % rng.randint(lo, hi)


def _build_rows(rng, envs_all, plan, stmt, pairs, plant, stated, error=None):
    stmt_n = int(stmt[-2:])
    rows, openings = [], {}
    for e in envs_all:
        s, t, opening = plan[e["code"]]
        openings[e["code"]] = opening
        for amt in _split(rng, s - opening, rng.randint(2, 4)):
            rows.append({"env": e["code"], "cents": amt, "day": _days(rng, 1, stmt_n), "kind": "live"})
        if t != s:
            for amt in _split(rng, t - s, rng.randint(1, 2)):
                rows.append({"env": e["code"], "cents": amt, "day": _days(rng, stmt_n + 1, 30), "kind": "live"})
    codes = [e["code"] for e in envs_all]
    ids = rng.sample(range(10000, 99999), len(rows) + 80)
    for r in rows:
        r["id"] = "T%05d" % ids.pop()
    pre_void = plant.get("S2")
    corrections, extra, cutoff = _noise(rng, rows, codes, ids, stmt_n, pre_void, plant.get("NO23"))
    rows += extra
    by1 = {e1: (e2, sw) for e1, e2, sw in pairs.values()}
    moved = False
    for r in rows:
        r["shard"] = rng.choice("abc")
        r["s1env"] = r["env"]
        if r["env"] in by1 and r["day"] < by1[r["env"]][1]:
            if plant.get("S1") and r["kind"] == "live" and not moved:
                r["shard"] = "b"
            if r["shard"] == "b":
                if not plant.get("S1"):
                    r["shard"] = rng.choice("ac")
                else:
                    r["s1env"] = by1[r["env"]][0]
                    moved = moved or r["kind"] == "live"
    if plant.get("S1") and not moved:
        return None
    envs_view = [{"code": e["code"], "dist": e["dist"], "fund": e["fund"], "cat": e["cat"], "plan": e["plan"], "rate": e["rate"],
                  "opening": openings[e["code"]]}
                 for e in envs_all]
    if error == "two_fit":
        return rows, corrections, cutoff, ids, openings
    truth = _ledger_view(envs_view, rows, stated, stmt, set())
    if truth == "error" or any(truth[0][e["code"]] != e["bal"] for e in envs_all):
        return None
    for key, mode in (("S1", {"S1"}), ("S2", {"S2"}), ("S3", {"S3"})):
        if (_ledger_view(envs_view, rows, stated, stmt, mode) != truth) != bool(plant.get(key)):
            return None
    both = _ledger_view(envs_view, rows, stated, stmt, {"S2", "S3"}) != truth
    if (plant.get("S23") and not both) or (plant.get("NO23") and both):
        return None
    return rows, corrections, cutoff, ids, openings


def _noise(rng, txns, codes, ids, stmt_n, pre_void, small_void=False):
    corrections = []
    cutoff = rng.randint(40, 70)
    seqs = rng.sample(range(1, cutoff + 1), 30)
    late = rng.sample(range(cutoff + 1, cutoff + 40), 12)
    for t in rng.sample(txns, rng.randint(4, 7)):
        wrong = (t["cents"] + (1 if t["cents"] > 0 else -1) * rng.randint(15000, 60000) if pre_void
                 else t["cents"] + rng.choice([-1, 1]) * rng.randint(1, 900))
        if wrong == 0 or (wrong > 0) != (t["cents"] > 0):
            continue
        t["shown"] = wrong
        if rng.random() < 0.4:
            a, b = sorted([seqs.pop(), seqs.pop()])
            corrections.append((a, t["id"], "amend", str(abs(wrong) + rng.randint(1, 50))))
            corrections.append((b, t["id"], "amend", str(abs(t["cents"]))))
        else:
            corrections.append((seqs.pop(), t["id"], "amend", str(abs(t["cents"]))))
    for t in rng.sample(txns, rng.randint(3, 5)):
        if "shown" in t:
            continue
        if rng.random() < 0.5:
            corrections.append((late.pop(), t["id"], "void", "-"))
        else:
            corrections.append((late.pop(), t["id"], "amend", str(abs(t["cents"]) + rng.randint(1, 500))))
    extra = []
    for _ in range(rng.randint(3, 6)):
        day = _days(rng, 1, 30) if pre_void else _days(rng, min(30, stmt_n + 1), 30)
        x = {"env": rng.choice(codes), "cents": rng.choice([-1, 1]) * rng.randint(100, 900 if small_void else 20000),
             "day": day, "kind": "void", "id": "T%05d" % ids.pop()}
        extra.append(x)
        corrections.append((seqs.pop(), x["id"], "void", "-"))
        if rng.random() < 0.3:
            corrections.append((seqs.pop(), x["id"], "amend", str(rng.randint(100, 900))))
    for _ in range(rng.randint(3, 6)):
        extra.append({"env": rng.choice(codes), "cents": rng.choice([-1, 1]) * rng.randint(100, 20000),
                      "day": _day(rng, False), "kind": "outside", "id": "T%05d" % ids.pop()})
    for _ in range(rng.randint(2, 4)):
        extra.append({"env": rng.choice(codes), "cents": None, "day": _day(rng), "kind": "bad", "id": "T%05d" % ids.pop()})
    return corrections, extra, cutoff


def _write_register(root, shard_rows, rng):
    for name, rows in shard_rows.items():
        # interleave households while keeping each household's register order
        queues = {}
        for dist, row in rows:
            queues.setdefault(dist, []).append(row)
        order = [d for d in queues for _ in queues[d]]
        rng.shuffle(order)
        seq = [queues[d].pop(0) for d in order]
        cols = SHARD_COLS[name]
        if name.endswith(".jsonl"):
            text = "".join(_json.dumps(dict(zip(cols, r)), sort_keys=True) + "\n" for r in seq)
        else:
            sep = "," if name.endswith(".csv") else "\t"
            text = "\n".join([sep.join(cols)] + [sep.join(str(v) for v in r) for r in seq]) + "\n"
        (root / name).write_text(text, encoding="utf-8")
    xw = {name: dict(zip(cols, CANON)) for name, cols in SHARD_COLS.items()}
    (root / "xw_columns.json").write_text(_json.dumps(xw, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_constants(root, rng, households, fund_codes, cat_codes, cutoff, plant=None):
    plant = plant or {}
    for _attempt in range(200):
        params = [["district", "damping_percent", "patience", "round_budget"]]
        draft = [["district", "damping_percent", "patience", "round_budget"]]
        for dist in sorted(households, key=lambda k: rng.random()):
            h = households[dist]
            params.append([dist, h["d"], h["K"], h["B"]])
            draft.append([dist, min(99, h["d"] + rng.choice([5, 10, 15])), h["K"] + 1, h["B"] + rng.choice([2, 4])])
        sheet = rng.choice(["sweep_oct", "sweep_live", "sweep_m09"])
        other = "sweep_prev"
        sheets = [(other, draft), (sheet, params)] if rng.random() < 0.5 else [(sheet, params), (other, draft)]
        blob = xlsx_bytes(sheets, remap=bool(plant.get("X1")), alt=(sheet, draft) if plant.get("A3") else None)
        if b"\r\n" not in blob and not any(m in blob.upper() for m in _MARKS):
            break
    else:
        raise ValueError("no clean workbook")
    (root / "sweep_tab.xlsx").write_bytes(blob)
    ini = ["[period]", "first_day = %s" % PERIOD[0], "last_day = %s" % PERIOD[1], "",
           "[corrections]", "cutoff_seq = %d" % cutoff, "", "[sweep]", "parameter_sheet = %s" % sheet, ""]
    if plant.get("OV"):
        orng = _random.Random(cutoff * 7907 + len(households))
        a, b = orng.sample(sorted(households), 2)
        ini += ["[overrides]", "%s_round_budget = %d" % (a, orng.randint(2, 3)),
                "%s_patience = %d" % (b, households[b]["K"] + orng.randint(2, 4)),
                "%s_damping_percent = %d" % (b, max(5, min(95, households[b]["d"] + orng.choice([-25, -20, 20, 25])))), ""]
    (root / "office.ini").write_text("\n".join(ini), encoding="utf-8")
    items = sorted(fund_codes.items(), key=lambda kv: rng.random())
    title = ["Funding code table, household budgeting office"]
    old = None
    if plant.get("P1"):
        segs = [v for _k, v in items]
        old = title + ["%s = %s" % (k, segs[(i + 1) % len(segs)]) for i, (k, _v) in enumerate(items)]
    (root / "fund_codes.pdf").write_bytes(_clean_pdf(title + ["%s = %s" % kv for kv in items], old))
    rows = [["code", "category"]] + [[k, v] for k, v in sorted(cat_codes.items(), key=lambda kv: rng.random())]
    (root / "cat_codes.docx").write_bytes(_docx(rows, ["Envelope category codes"], split=bool(plant.get("D1")), alt=bool(plant.get("A1")),
                                                  move=bool(plant.get("A2")), inline=bool(plant.get("A4")),
                                                  alt_rows={1} if plant.get("A4P") else None))
    prior = {"period": "2026-09", "source": "previous sweep run", "households": {}}
    for dist in DISTRICTS:
        prior["households"][dist] = {"exit": rng.choice(["settled", "stalled", "budget", "cycling"]),
                                     "moved_dollars": rng.randint(40, 900)}
    (root / "prior_sweep.json").write_text(_json.dumps(prior, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tot = ["district,quarter,pool_dollars,moved_dollars"]
    tot += ["%s,2026-Q2,%d,%d" % (d, rng.randint(1000, 9000), rng.randint(10, 999)) for d in DISTRICTS]
    (root / "tot_q2.csv").write_text("\n".join(tot) + "\n", encoding="utf-8")


def _write_shards(root, rows, alias_pick, rng, plant=None, full=True, error=None):
    a = ["txn,day,env,cents,dir"]
    qrng = _random.Random(len(rows) * 7919 + 17)
    b = ["id\tposted\talias\tamount\tkind"]
    c = []
    for t in rows:
        cents = t.get("shown", t["cents"])
        if t["shard"] == "a":
            amt = "n/a" if cents is None else str(abs(cents))
            way = rng.choice(["in", "out"]) if cents is None else ("in" if cents > 0 else "out")
            day = '"%s"' % t["day"] if (plant or {}).get("Q1") else t["day"]
            a.append("%s,%s,%s,%s,%s" % (t["id"], day, t["env"], amt, way))
        elif t["shard"] == "b":
            al = alias_pick(t["env"], t["day"])
            amt = "" if cents is None else "%d.%02d" % (abs(cents) // 100, abs(cents) % 100)
            kind = rng.choice("DS") if cents is None else ("D" if cents > 0 else "S")
            b.append("%s\t%s\t%s\t%s\t%s" % (t["id"], t["day"], al, amt, kind))
        else:
            c.append(t)
    (root / "tx_a.csv").write_text("\n".join(a) + "\n", encoding="utf-8")
    (root / "tx_b.tsv").write_text("\n".join(b) + "\n", encoding="utf-8")
    write_txc(root, rng, c, plant or {}, full, error)
def _day_number(day):
    m, d = int(day[5:7]), int(day[8:10])
    return d if m == 9 else (d - 31 if m == 8 else 30 + d)


def _day_text(n):
    if n <= 0:
        return "2026-08-%02d" % (n + 31)
    if n > 30:
        return "2026-10-%02d" % (n - 30)
    return "2026-09-%02d" % n


def _uvar(n):
    out = bytearray()
    while True:
        low = n & 0x7F
        n >>= 7
        if n:
            out.append(low | 0x80)
        else:
            out.append(low)
            return bytes(out)


def _zz(n):
    return _uvar(n * 2 if n >= 0 else -n * 2 - 1)


def _case(rng, code):
    return rng.choice([code.lower(), code.upper(), code[0].lower() + code[1:]])


def _txc_plan(rng, rows, plant, full):
    """Order shard-c rows into records (mode, row, written code or back-reference)."""
    good = [r for r in rows if r["kind"] != "bad"]
    bad = [r for r in rows if r["kind"] == "bad"]
    recs, written, dic = [], {}, []
    if not full:
        for r in good:
            recs.append((0, r, written.setdefault(r["env"], _case(rng, r["env"]))))
    else:
        groups = {}
        for r in good:
            groups.setdefault(r["env"], []).append(r)
        order = [(env, rs) for env, rs in groups.items()]
        rng.shuffle(order)
        tail = [(env, [rs.pop()]) for env, rs in order if len(rs) >= 2 and rng.random() < 0.6]
        order += tail
        flip = plant.get("DI")
        for env, rs in order:
            i = 0
            while i < len(rs):
                r = rs[i]
                j = next((n for n, c in enumerate(dic) if c.upper() == env.upper()), None)
                k = None if j is None else len(dic) - 1 - j
                if j is not None and (k == j or plant.get("M2")) and rng.random() < 0.7:
                    recs.append((2, r, k))
                else:
                    code = written.setdefault(env, _case(rng, env))
                    if flip and j is not None and code.swapcase() != code:
                        code, flip = code.swapcase(), False
                    recs.append((0, r, code))
                    if j is None:
                        dic.append(code)
                i += 1
                if recs[-1][0] in (0, 2) and i < len(rs) and rng.random() < 0.8:
                    if recs[-1][0] == 2 and not plant.get("M1"):
                        continue
                    recs.append((1, rs[i], None))
                    i += 1
                    while plant.get("M1") and i < len(rs) and rng.random() < 0.5:
                        recs.append((1, rs[i], None))
                        i += 1
    lead = bad[:1] if plant.get("ST") and full else []
    for r in lead:
        spots = [j for j in range(1, len(recs)) if recs[j][0] in (0, 2) and recs[j - 1][1]["env"] != recs[j][1]["env"]]
        if not spots:
            raise ValueError("no malformed lead spot")
        j = rng.choice(spots)
        row = recs[j][1]
        r["env"] = r["s1env"] = row["env"]
        recs[j:j + 1] = [(0, r, written.setdefault(row["env"], _case(rng, row["env"]))), (1, row, None)]
    for r in bad[len(lead):]:
        recs.append((0, r, written.setdefault(r["env"], _case(rng, r["env"]))))
    return recs


def _txc_bytes(recs, filler):
    body = bytearray(b"TXC1" + bytes([filler]) + len(recs).to_bytes(2, "big"))
    prev_n, prev_day = 0, 0
    for mode, r, extra in recs:
        n = int(r["id"][1:])
        cents = r.get("shown", r["cents"])
        day = _day_number(r["day"])
        body.append(mode | (4 if cents is None else 0))
        body += _uvar(n)
        if mode == 0:
            code = extra.encode("ascii")
            body += bytes([len(code)]) + code + _zz(day)
        elif mode == 1:
            body += _zz(day - prev_day)
        else:
            body += bytes([extra]) + _zz(day)
        if cents is not None:
            body += _zz(cents)
        prev_n, prev_day = n, day
    return bytes(body) + _zlib.crc32(bytes(body)).to_bytes(4, "big")


def _read_uvar(blob, pos):
    n = shift = 0
    while True:
        b = blob[pos]
        pos += 1
        n |= (b & 0x7F) << shift
        shift += 7
        if not b & 0x80:
            return n, pos


def _read_zz(blob, pos):
    z, pos = _read_uvar(blob, pos)
    return (z >> 1) ^ -(z & 1), pos


def txc_decode(blob, misread=frozenset()):
    """Rows (id, day, code, cents or None) under the grammar, or under one misreading (ST, M1, M2, DI)."""
    count = int.from_bytes(blob[5:7], "big")
    pos, out, dic = 7, [], []
    prev_n = prev_day = 0
    prev_code = None
    lit = (0, 0, None)
    for _ in range(count):
        sel = blob[pos]
        pos += 1
        mode, bad = sel & 3, bool(sel & 4)
        n, pos = _read_uvar(blob, pos)
        if mode == 0:
            ln = blob[pos]
            code = blob[pos + 1:pos + 1 + ln].decode("ascii")
            pos += 1 + ln
            day, pos = _read_zz(blob, pos)
            if (code if "DI" in misread else code.upper()) not in [(c if "DI" in misread else c.upper()) for c in dic]:
                dic.append(code)
        elif mode == 1:
            dd, pos = _read_zz(blob, pos)
            base_day, code = (lit[1], lit[2]) if "M1" in misread else (prev_day, prev_code)
            day = base_day + dd
        else:
            k = blob[pos]
            pos += 1
            code = dic[k] if "M2" in misread else dic[len(dic) - 1 - k]
            day, pos = _read_zz(blob, pos)
        cents = None
        if not bad:
            cents, pos = _read_zz(blob, pos)
        out.append(("T%05d" % n, _day_text(day), code.upper(), cents))
        if not (bad and "ST" in misread):
            prev_day, prev_code = day, code
        if mode == 0:
            lit = (n, day, code)
    return out


def write_txc(root, rng, rows, plant, full, error=None):
    for _attempt in range(500):
        recs = _txc_plan(rng, rows, plant, full)
        want = [("T%05d" % int(r["id"][1:]), r["day"], r["env"].upper(), r.get("shown", r["cents"])) for r in rows]
        if full and {m for m, _r, _x in recs} != {0, 1, 2}:
            continue
        blob = _txc_bytes(recs, rng.randint(0, 255))
        if b"\r\n" in blob or any(m in blob.upper() for m in _MARKS):
            continue
        truth = txc_decode(blob)
        if sorted(truth) != sorted(want):
            raise ValueError("txc round trip")
        ok = True
        for key in ("ST", "M1", "M2", "DI"):
            try:
                other = txc_decode(blob, {key})
            except (IndexError, UnicodeDecodeError):
                other = None
            if (other != truth) != bool(plant.get(key)):
                ok = False
        if ok:
            break
    else:
        raise ValueError("no txc layout")
    if error == "bad_crc":
        blob = blob[:-4] + bytes([blob[-4] ^ 0x01]) + blob[-3:]
    (root / "tx_c.bin").write_bytes(blob)

# ---- end extract generator ----

"""Independent reference implementation of the 43986de8-bb38-5141-98f3-f9f31ce56581.

Built only from the extract's specification documents (glossary.md, std_*.md,
cfg_reference.md, dict_*.md, layout_*.md).  Exact integer arithmetic only.

Public names: ExtractError, REPORT_NAMES, derive_reports(root), table_values(path).
Every other module-level name carries the ``_x`` prefix so the file can be
pasted into a larger module.
"""

import configparser as _xconfigparser
import csv as _xcsv
import datetime as _xdatetime
import decimal as _xdecimal
import hashlib as _xhashlib
import io as _xio
import json as _xjson
import pathlib as _xpathlib
import posixpath as _xposixpath
import re as _xre
import sqlite3 as _xsqlite3
import xml.etree.ElementTree as _xET
import zipfile as _xzipfile
import zlib as _xzlib


class ExtractError(Exception):
    """The extract breaks one of the rules of the inputs (std_ledger.md)."""


_xDISTRICTS = ["central", "east", "north", "south", "west"]
_xSEGMENTS = ["consumer", "corporate", "enterprise", "smb"]
_xEXITS = ["budget", "cycling", "settled", "stalled"]
_xTX_FILES = ["tx_a.csv", "tx_b.tsv", "tx_c.bin"]
_xREG_FILES = ["env_a.csv", "env_b.tsv", "env_c.jsonl"]

REPORT_NAMES = (
    ["normalized.jsonl", "data_quality.json", "summary.json", "product_summary.json"]
    + ["region_%s.json" % _d for _d in _xDISTRICTS]
    + ["segment_%s.json" % _s for _s in _xSEGMENTS]
    + [
        "sweep_rounds.csv",
        "envelope_final.tsv",
        "moves.csv",
        "exits.xml",
        "prior_delta.yaml",
        "reconciliation.txt",
        "ledger_totals.psv",
        "sweep.sqlite",
        "sweep_book.xlsx",
        "manifest.json",
    ]
)

_xDIGITS = _xre.compile(r"[0-9]+")
_xDOLLARS = _xre.compile(r"([0-9]+)\.([0-9]{2})")
_xNS_MAIN = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_xNS_REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
_xNS_PKG = "{http://schemas.openxmlformats.org/package/2006/relationships}"
_xNS_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


# ---------------------------------------------------------------- arithmetic

def _xround_div(num, den):
    """num/den taken to the nearest integer, exact halves toward zero."""
    if den < 0:
        num, den = -num, -den
    q, r = divmod(abs(num), den)
    if 2 * r > den:
        q += 1
    return q if num >= 0 else -q


def _xcents_to_dollars(cents):
    """Whole dollars by dropping the cents part (truncation toward zero)."""
    q = abs(cents) // 100
    return q if cents >= 0 else -q


# ---------------------------------------------------------------- readers

def _xread_text(path):
    return path.read_text(encoding="utf-8-sig")


def _xread_delimited(path, delim):
    """Header row + data rows as dicts (blank lines skipped)."""
    text = _xread_text(path)
    quoting = _xcsv.QUOTE_NONE if delim == "\t" else _xcsv.QUOTE_MINIMAL
    rows = [r for r in _xcsv.reader(_xio.StringIO(text, newline=""), delimiter=delim, quoting=quoting)]
    rows = [r for r in rows if r and any(c != "" for c in r)]
    if not rows:
        return []
    header = rows[0]
    out = []
    for r in rows[1:]:
        out.append({header[i]: (r[i] if i < len(r) else None) for i in range(len(header))})
    return out


def _xread_jsonl(path):
    out = []
    for line in _xread_text(path).splitlines():
        if line.strip():
            out.append(_xjson.loads(line))
    return out


def _xread_rows(path):
    name = path.name
    if name.endswith(".csv"):
        return _xread_delimited(path, ",")
    if name.endswith(".tsv"):
        return _xread_delimited(path, "\t")
    return _xread_jsonl(path)


def _xxml_text(elem, tag):
    return "".join(t.text or "" for t in elem.iter(tag))


def _xcurrent_text(tc):
    """w:t text that is current: not inside w:moveFrom / w:del, and of mc:AlternateContent only the mc:Fallback."""
    mc = "{http://schemas.openxmlformats.org/markup-compatibility/2006}"
    skip = {_xNS_W + "moveFrom", _xNS_W + "del", mc + "Choice"}
    parent = {c: p for p in tc.iter() for c in p}
    out = []
    for t in tc.iter(_xNS_W + "t"):
        node, ok = t, True
        while node in parent:
            node = parent[node]
            if node.tag in skip:
                ok = False
                break
        if ok:
            out.append(t.text or "")
    return "".join(out)


def _xread_cat_codes(path):
    """cat_codes.docx: one table, header `code`/`category`."""
    with _xzipfile.ZipFile(path) as z:
        root = _xET.fromstring(z.read("word/document.xml"))
    table = next(root.iter(_xNS_W + "tbl"))
    out = {}
    header_seen = False
    for tr in table.iter(_xNS_W + "tr"):
        cells = [_xcurrent_text(tc).strip() for tc in tr.findall(_xNS_W + "tc")]
        if len(cells) < 2:
            continue
        if not header_seen:
            header_seen = True
            if cells[0].lower() == "code" and cells[1].lower() == "category":
                continue
        out[cells[0]] = cells[1]
    return out


def _xpdf_unescape(raw):
    out = bytearray()
    i = 0
    while i < len(raw):
        c = raw[i]
        if c == 0x5C and i + 1 < len(raw):  # backslash
            n = raw[i + 1]
            simple = {ord("n"): 10, ord("r"): 13, ord("t"): 9, ord("b"): 8, ord("f"): 12}
            if n in simple:
                out.append(simple[n])
                i += 2
            elif 0x30 <= n <= 0x37:
                j = i + 1
                digits = b""
                while j < len(raw) and len(digits) < 3 and 0x30 <= raw[j] <= 0x37:
                    digits += bytes([raw[j]])
                    j += 1
                out.append(int(digits, 8) & 0xFF)
                i = j
            elif n in (10, 13):  # line continuation
                i += 2
                if n == 13 and i < len(raw) and raw[i] == 10:
                    i += 1
            else:
                out.append(n)
                i += 2
        else:
            out.append(c)
            i += 1
    return out.decode("latin-1")


def _xpdf_strings(content):
    """Text shown by Tj / TJ / ' / \" operators, one entry per operator."""
    lines = []
    pending = []
    i = 0
    n = len(content)
    while i < n:
        c = content[i]
        if c == 0x28:  # '(' literal string, balanced parentheses
            depth = 1
            j = i + 1
            while j < n and depth:
                if content[j] == 0x5C:
                    j += 2
                    continue
                if content[j] == 0x28:
                    depth += 1
                elif content[j] == 0x29:
                    depth -= 1
                j += 1
            pending.append(_xpdf_unescape(content[i + 1:j - 1]))
            i = j
        elif c == 0x25:  # comment
            while i < n and content[i] not in (10, 13):
                i += 1
        elif content[i:i + 2] == b"Tj" or content[i:i + 2] == b"TJ":
            lines.append("".join(pending))
            pending = []
            i += 2
        elif c in (0x27, 0x22):  # ' and " operators
            lines.append("".join(pending))
            pending = []
            i += 1
        else:
            if c == 0x5B:  # TJ array start: nothing to do, strings collected
                pass
            i += 1
    return lines


def _xread_fund_codes(path):
    data = path.read_bytes()
    # incremental updates: the latest definition of an object in file order is the current one
    defs = {}
    for mm in _xre.finditer(rb"(\d+)\s+0\s+obj", data):
        defs[int(mm.group(1))] = mm.end()
    def obj(num):
        return data[defs[num]:data.find(b"endobj", defs[num])]
    pages = [n for n in defs if b"/Type /Page" in obj(n) and b"/Type /Pages" not in obj(n)]
    cnum = int(_xre.search(rb"/Contents\s+(\d+)\s+0\s+R", obj(pages[0])).group(1))
    m = _xre.search(rb"stream\r?\n", data[defs[cnum]:])
    if not m:
        raise ValueError("no stream in fund_codes.pdf")
    m_end = defs[cnum] + m.end()
    end = data.find(b"endstream", m_end)
    content = _xzlib.decompressobj().decompress(data[m_end:end])
    lines = _xpdf_strings(content)
    out = {}
    for line in lines[1:]:
        if "=" not in line:
            continue
        code, seg = line.split("=", 1)
        out[code.strip()] = seg.strip()
    return out


def _xxlsx_sheets(path):
    """[(sheet name, [[cell text, ...] per row])] in workbook order."""
    with _xzipfile.ZipFile(path) as z:
        wb = _xET.fromstring(z.read("xl/workbook.xml"))
        rels_root = _xET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        rels = {}
        shared_target = None
        for rel in rels_root.iter(_xNS_PKG + "Relationship"):
            target = rel.get("Target")
            if target.startswith("/"):
                full = target.lstrip("/")
            else:
                full = _xposixpath.normpath(_xposixpath.join("xl", target))
            rels[rel.get("Id")] = full
            if rel.get("Type", "").endswith("/sharedStrings"):
                shared_target = full
        shared = []
        if shared_target is not None and shared_target in z.namelist():
            sroot = _xET.fromstring(z.read(shared_target))
            for si in sroot.findall(_xNS_MAIN + "si"):
                shared.append(_xsi_text(si))
        sheets = []
        for sh in wb.iter(_xNS_MAIN + "sheet"):
            target = rels[sh.get(_xNS_REL + "id")]
            sroot = _xET.fromstring(z.read(target))
            sheets.append((sh.get("name"), _xsheet_rows(sroot, shared)))
    return sheets


def _xsi_text(si):
    """Text of a shared/inline string item, skipping phonetic runs."""
    parts = []
    for child in si:
        if child.tag == _xNS_MAIN + "t":
            parts.append(child.text or "")
        elif child.tag == _xNS_MAIN + "r":
            for t in child.findall(_xNS_MAIN + "t"):
                parts.append(t.text or "")
    return "".join(parts)


def _xcol_index(ref):
    letters = "".join(ch for ch in ref if ch.isalpha())
    idx = 0
    for ch in letters.upper():
        idx = idx * 26 + (ord(ch) - 64)
    return idx - 1


def _xnumber_text(raw):
    raw = raw.strip()
    try:
        d = _xdecimal.Decimal(raw)
    except _xdecimal.InvalidOperation:
        return raw
    if d == d.to_integral_value():
        return str(int(d))
    return raw


def _xsheet_rows(sroot, shared):
    rows = []
    for row in sroot.iter(_xNS_MAIN + "row"):
        cells = {}
        next_col = 0
        mcx = "{http://schemas.openxmlformats.org/markup-compatibility/2006}"
        found = list(row.findall(_xNS_MAIN + "c"))
        for blk in row.findall(mcx + "AlternateContent"):
            fb = blk.find(mcx + "Fallback")
            if fb is not None:
                found += fb.findall(_xNS_MAIN + "c")
        found.sort(key=lambda c: _xcol_index(c.get("r")) if c.get("r") else 0)
        for c in found:
            ref = c.get("r")
            col = _xcol_index(ref) if ref else next_col
            next_col = col + 1
            t = c.get("t", "n")
            v = c.find(_xNS_MAIN + "v")
            if t == "inlineStr":
                is_ = c.find(_xNS_MAIN + "is")
                val = _xsi_text(is_) if is_ is not None else ""
            elif t == "s":
                val = shared[int(v.text)]
            elif t == "str":
                val = v.text or "" if v is not None else ""
            elif t == "b":
                val = (v.text or "") if v is not None else ""
            else:
                val = _xnumber_text(v.text or "") if v is not None else ""
            cells[col] = val
        if not cells:
            continue
        width = max(cells) + 1
        vals = [cells.get(i, "") for i in range(width)]
        while vals and vals[-1] == "":
            vals.pop()
        if vals:
            rows.append(vals)
    return rows


# ---------------------------------------------------------------- ledger

def _xload_register(root):
    xw = _xjson.loads(_xread_text(root / "xw_columns.json"))
    envs = []
    for fname in _xREG_FILES:
        mapping = xw[fname]
        for raw in _xread_rows(root / fname):
            rec = {}
            for col, val in raw.items():
                if col in mapping:
                    rec[mapping[col]] = val
            envs.append({
                "code": str(rec["env_code"]).strip(),
                "file_no": str(rec["file_no"]).strip(),
                "label": str(rec["label"]),
                "category_code": str(rec["category_code"]).strip(),
                "funding_code": str(rec["funding_code"]).strip(),
                "need": int(str(rec["need_dollars"]).strip()),
                "opening": int(str(rec["opening_cents"]).strip()),
            })
    return envs


def _xload_core(root):
    uri = "file:" + str((root / "hh_core.sqlite").resolve()) + "?mode=ro"
    con = _xsqlite3.connect(uri, uri=True)
    try:
        districts = {r[0]: str(r[1]) for r in con.execute("SELECT district_id, district_name FROM district")}
        households = {r[0]: (str(r[1]), r[2]) for r in con.execute("SELECT hh_code, family_name, district_id FROM household")}
        files = {str(r[0]): r[1] for r in con.execute("SELECT file_no, hh_code FROM file")}
        aliases = {}
        for r in con.execute("SELECT alias, env_code, since FROM env_alias"):
            aliases.setdefault(str(r[0]), []).append((str(r[2]), str(r[1])))
    finally:
        con.close()
    return districts, households, files, aliases


def _xparse_transactions(root, env_by_key, aliases):
    """Every row of the three exports, in a uniform shape."""
    rows = []
    for fname in _xTX_FILES:
        for raw in (_xread_txc(root / fname) if fname == "tx_c.bin" else _xread_rows(root / fname)):
            if fname == "tx_a.csv":
                txn, day, env_ref = raw.get("txn"), raw.get("day"), raw.get("env")
                amt = raw.get("cents")
                cents = int(amt) if isinstance(amt, str) and _xDIGITS.fullmatch(amt) else None
                sign = 1 if raw.get("dir") == "in" else -1
                env_key = env_ref.upper() if isinstance(env_ref, str) else None
            elif fname == "tx_b.tsv":
                txn, day, alias = raw.get("id"), raw.get("posted"), raw.get("alias")
                amt = raw.get("amount")
                m = _xDOLLARS.fullmatch(amt) if isinstance(amt, str) else None
                cents = int(m.group(1)) * 100 + int(m.group(2)) if m else None
                sign = 1 if raw.get("kind") == "D" else -1
                target = None
                if isinstance(alias, str) and isinstance(day, str):
                    dated = [row for row in aliases.get(alias, []) if row[0] <= day]
                    if dated:
                        target = max(dated)[1]
                env_key = target.upper() if target is not None else None
            else:
                txn, day, code = raw.get("ref"), raw.get("on"), raw.get("code")
                amt = raw.get("minor")
                if isinstance(amt, int) and not isinstance(amt, bool):
                    cents, sign = abs(amt), (-1 if amt < 0 else 1)
                else:
                    cents, sign = None, 1
                env_key = code.upper() if isinstance(code, str) else None
            if env_key is None or env_key not in env_by_key:
                raise ExtractError("%s: transaction %r names no envelope of the register" % (fname, txn))
            rows.append({
                "txn": str(txn),
                "day": day,
                "env": env_by_key[env_key],
                "magnitude": cents,
                "sign": sign,
                "source": fname,
            })
    return rows


def _xread_txc(path):
    """tx_c.bin per fmt_txc.md, as dicts shaped like the old json rows (ref, on, code, minor)."""
    data = path.read_bytes()
    if len(data) < 11 or data[:4] != b"TXC1":
        raise ExtractError("tx_c.bin: bad header")
    if _xzlib.crc32(data[:-4]) & 0xFFFFFFFF != int.from_bytes(data[-4:], "big"):
        raise ExtractError("tx_c.bin: checksum mismatch")
    at = [7]

    def uv():
        out, sh = 0, 0
        while True:
            b = data[at[0]]
            at[0] += 1
            out += (b & 127) << sh
            sh += 7
            if b < 128:
                return out

    def sv():
        z = uv()
        return z // 2 if z % 2 == 0 else -(z + 1) // 2

    def day_of(n):
        return (_xdatetime.date(2026, 8, 31) + _xdatetime.timedelta(days=n)).isoformat()

    rows, table = [], []
    st_day, st_code = 0, None
    for _ in range(int.from_bytes(data[5:7], "big")):
        sel = data[at[0]]
        at[0] += 1
        mode = sel % 4
        st_num = uv()
        if mode == 0:
            ln = data[at[0]]
            code = data[at[0] + 1:at[0] + 1 + ln].decode("ascii")
            at[0] += 1 + ln
            st_day = sv()
            if all(t.lower() != code.lower() for t in table):
                table.append(code)
            st_code = code
        elif mode == 1:
            st_day += sv()
        elif mode == 2:
            pos = data[at[0]]
            at[0] += 1
            st_code = table[-1 - pos]
            st_day = sv()
        else:
            raise ExtractError("tx_c.bin: mode 3")
        minor = "malformed" if sel & 4 else sv()
        rows.append({"ref": "T%05d" % st_num, "on": day_of(st_day), "code": st_code, "minor": minor})
    return rows


def _xload_corrections(root):
    out = []
    for raw in _xread_delimited(root / "adj_log.psv", "|"):
        out.append({
            "seq": int(raw["seq"].strip()),
            "txn": raw["txn"],
            "action": raw["action"].strip(),
            "value": raw.get("value"),
        })
    return out


# ---------------------------------------------------------------- sweep

def _xsweep(envs, rate, patience, budget):
    """envs: list in envelope code order. Returns the household's sweep."""
    needs = [e["need"] for e in envs]
    labels = [e["label"] for e in envs]
    state = [e["presweep"] for e in envs]
    pool = sum(state)
    history = [list(state)]
    strikes = 0
    prev_spread = None
    rounds = []
    exit_kind = None
    final = None
    while True:
        if len(rounds) >= budget:
            exit_kind, final = "budget", list(state)
            break
        claims = [needs[i] + max(0, needs[i] - state[i]) for i in range(len(envs))]
        total_claim = sum(claims)
        if total_claim == 0:
            targets = [0] * len(envs)
        else:
            targets = [_xround_div(pool * c, total_claim) for c in claims]
        gaps = [targets[i] - state[i] for i in range(len(envs))]
        spread = sum(abs(g) for g in gaps)
        if spread == 0:
            exit_kind, final = "settled", list(state)
            break
        # the round runs
        if prev_spread is not None and spread >= prev_spread:
            strikes += 1
            if strikes >= patience:
                rate //= 2
                strikes = 0
        prev_spread = spread
        drafts = [_xround_div(g * rate, 100) for g in gaps]
        posted = list(drafts)
        excess = sum(drafts)
        if excess != 0:
            biggest = max(abs(g) for g in gaps)
            cands = [i for i in range(len(envs)) if abs(gaps[i]) == biggest]
            k = min(cands, key=lambda i: (labels[i], i))
            posted[k] -= excess
        rounds.append({
            "spread": spread,
            "rate": rate,
            "strikes": strikes,
            "posted": sum(p for p in posted if p > 0),
        })
        if all(d == 0 for d in drafts):
            exit_kind, final = "stalled", list(state)
            break
        state = [state[i] + posted[i] for i in range(len(envs))]
        if state in history:
            first = history.index(state)
            final = min(history[first:])
            exit_kind = "cycling"
            break
        history.append(list(state))
    return {
        "exit": exit_kind,
        "rounds": rounds,
        "rate": rate,
        "final": final,
        "pool": pool,
    }


# ---------------------------------------------------------------- formatting

def _xjson_report(obj):
    return (_xjson.dumps(obj, indent=2, sort_keys=True, ensure_ascii=True) + "\n").encode("ascii")


def _xlines(lines):
    return ("".join(line + "\n" for line in lines)).encode("utf-8")


def _xxml_attr(value):
    s = str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    return s.encode("ascii", "xmlcharrefreplace").decode("ascii")


def _xtable_text(tables):
    out = []
    for name, header, rows in tables:
        out.append("table %s: %s\n" % (name, "|".join(header)))
        for row in rows:
            out.append("|".join(str(v) for v in row) + "\n")
    return "".join(out).encode("utf-8")


# ---------------------------------------------------------------- main entry

_xRATE_LO, _xRATE_HI = 12, 50


def _xplan_rows(root, envs, applied):
    """Statement rows as (wanted cents, plan -> cents per rate), the statement-day balances and each envelope's plan."""
    stmt = _xread_delimited(root / "stmt_fees.csv", ",")
    through = stmt[0]["through"].strip()
    uri = "file:" + str((root / "hh_core.sqlite").resolve()) + "?mode=ro"
    con = _xsqlite3.connect(uri, uri=True)
    try:
        plan_of = {str(r[0]): str(r[1]) for r in con.execute("SELECT env_code, plan FROM keep_plan")}
    finally:
        con.close()
    base = {e["code"]: e["opening"] for e in envs}
    for r in applied:
        if r["day"] <= through:
            base[r["env"]["code"]] += r["cents"]
    width = _xRATE_HI - _xRATE_LO + 1
    rows = []
    for r in stmt:
        ref = r["client_ref"].strip()
        tab = {}
        for e in envs:
            if ref in (e["hh"], e["funding_code"], e["category_code"]):
                col = tab.setdefault(plan_of[e["code"]], [0] * width)
                for k in range(width):
                    col[k] += _xround_div((_xRATE_LO + k) * e["opening"], 10000)
        rows.append((int(r["charge_cents"].strip()), tab))
    return rows, base, plan_of


def _xplan_search(rows, limit=2):
    """Fix the plan named on most rows first, then assign the others row by row with residual bounds."""
    width = _xRATE_HI - _xRATE_LO + 1
    count = {}
    for _w, tab in rows:
        for p in tab:
            count[p] = count.get(p, 0) + 1
    hub = max(sorted(count), key=lambda p: count[p])
    order = []
    for _w, tab in sorted(rows, key=lambda row: len(row[1])):
        for p in sorted(tab):
            if p != hub and p not in order:
                order.append(p)
    level_of = {p: i for i, p in enumerate(order)}
    last = [max([level_of[p] for p in tab if p != hub], default=-1) for _w, tab in rows]
    span = []
    for _w, tab in rows:
        lo, hi = [0] * (len(order) + 1), [0] * (len(order) + 1)
        for i in range(len(order) - 1, -1, -1):
            col = tab.get(order[i])
            lo[i] = lo[i + 1] + (min(col) if col else 0)
            hi[i] = hi[i + 1] + (max(col) if col else 0)
        span.append((lo, hi))
    sols = []

    def dfs(i, rest, pick):
        if len(sols) >= limit:
            return
        if i == len(order):
            sols.append(dict(pick))
            return
        p = order[i]
        for k in range(width):
            nxt = list(rest)
            ok = True
            for j, (_w, tab) in enumerate(rows):
                if p in tab:
                    nxt[j] -= tab[p][k]
                    if not span[j][0][i + 1] <= nxt[j] <= span[j][1][i + 1]:
                        ok = False
                        break
            if ok:
                pick[p] = _xRATE_LO + k
                dfs(i + 1, nxt, pick)
                del pick[p]
    for h in range(width):
        rest = [w - (tab[hub][h] if hub in tab else 0) for w, tab in rows]
        if all(span[j][0][0] <= rest[j] <= span[j][1][0] for j in range(len(rows))) and \
                all(rest[j] == 0 for j in range(len(rows)) if last[j] < 0):
            dfs(0, rest, {hub: _xRATE_LO + h})
    return sols


def _xkeeping(root, envs, applied):
    """Keeping charge per envelope, in whole dollars, at the one set of plan rates the fee statement allows."""
    rows, base, plan_of = _xplan_rows(root, envs, applied)
    sols = _xplan_search(rows)
    if len(sols) != 1:
        raise ExtractError("fee statement met by %d sets of plan rates" % len(sols))
    return {e["code"]: _xround_div(sols[0][plan_of[e["code"]]] * base[e["code"]], 1000000) for e in envs}


def derive_reports(root) -> dict:
    root = _xpathlib.Path(root)

    ini = _xconfigparser.ConfigParser(interpolation=None)
    ini.read_string(_xread_text(root / "office.ini"))
    first_day = ini.get("period", "first_day").strip()
    last_day = ini.get("period", "last_day").strip()
    cutoff = int(ini.get("corrections", "cutoff_seq").strip())
    sheet_name = ini.get("sweep", "parameter_sheet").strip()

    # register of record
    envs = _xload_register(root)
    districts, households, files, aliases = _xload_core(root)
    categories = _xread_cat_codes(root / "cat_codes.docx")
    segments = _xread_fund_codes(root / "fund_codes.pdf")
    env_by_key = {}
    for e in envs:
        hh = files[e["file_no"]]
        family, did = households[hh]
        e["hh"] = hh
        e["family"] = family
        e["district"] = districts[did].strip().lower()
        e["category"] = categories[e["category_code"]]
        e["segment"] = segments[e["funding_code"]]
        env_by_key[e["code"].upper()] = e

    # transactions and the rules of the inputs
    tx_rows = _xparse_transactions(root, env_by_key, aliases)
    seen = set()
    for r in tx_rows:
        if r["txn"] in seen:
            raise ExtractError("transaction id %r appears in more than one row" % r["txn"])
        seen.add(r["txn"])
    corrections = _xload_corrections(root)
    for c in corrections:
        if c["seq"] <= cutoff and c["txn"] not in seen:
            raise ExtractError("correction %d names unknown transaction %r" % (c["seq"], c["txn"]))

    # classify rows
    by_txn = {}
    quality = {f: {"rows": 0, "malformed": 0, "out_of_period": 0, "applied": 0, "voided": 0} for f in _xTX_FILES}
    for r in tx_rows:
        q = quality[r["source"]]
        q["rows"] += 1
        if r["magnitude"] is None:
            q["malformed"] += 1
            r["live"] = False
        elif not (isinstance(r["day"], str) and first_day <= r["day"] <= last_day):
            q["out_of_period"] += 1
            r["live"] = False
        else:
            r["live"] = True
            r["voided"] = False
        by_txn[r["txn"]] = r

    # corrections at or below the cutoff, ascending seq
    applied_corr = sorted((c for c in corrections if c["seq"] <= cutoff), key=lambda c: c["seq"])
    for c in applied_corr:
        r = by_txn[c["txn"]]
        if not r["live"] or r["voided"]:
            continue
        if c["action"] == "void":
            r["voided"] = True
        elif c["action"] == "amend":
            r["magnitude"] = int(str(c["value"]).strip())
    applied = []
    for r in tx_rows:
        if r["live"]:
            if r["voided"]:
                quality[r["source"]]["voided"] += 1
            else:
                quality[r["source"]]["applied"] += 1
                r["cents"] = r["sign"] * r["magnitude"]
                applied.append(r)

    # pre-sweep balances
    for e in envs:
        e["applied_cents"] = 0
    for r in applied:
        r["env"]["applied_cents"] += r["cents"]
    keep = _xkeeping(root, envs, applied)
    for e in envs:
        e["presweep"] = _xcents_to_dollars(e["opening"] + e["applied_cents"]) - keep[e["code"]]

    # parameter sheet
    params = {}
    for name, rows in _xxlsx_sheets(root / "sweep_tab.xlsx"):
        if name != sheet_name:
            continue
        header = [h.strip() for h in rows[0]]
        for row in rows[1:]:
            rec = dict(zip(header, row))
            params[rec["district"].strip().lower()] = (
                int(_xnumber_text(rec["damping_percent"])),
                int(_xnumber_text(rec["patience"])),
                int(_xnumber_text(rec["round_budget"])),
            )

    # sweep per district (one household per district)
    hh_by_district = {}
    for hh, (family, did) in households.items():
        dname = districts[did].strip().lower()
        hh_by_district[dname] = (hh, family)
    results = {}
    for d in _xDISTRICTS:
        hh, family = hh_by_district[d]
        members = sorted((e for e in envs if e["hh"] == hh), key=lambda e: e["code"])
        rate, patience, budget = params[d]
        # office.ini governs the round budget where it names one; the sheet governs every other parameter
        if ini.has_option("overrides", "%s_round_budget" % d):
            budget = int(ini.get("overrides", "%s_round_budget" % d).strip())
        res = _xsweep(members, rate, patience, budget)
        for e, f in zip(members, res["final"]):
            e["final"] = f
        res["hh"] = hh
        res["family"] = family
        res["envs"] = members
        res["moved"] = sum(max(0, e["final"] - e["presweep"]) for e in members)
        results[d] = res

    ordered = [e for d in _xDISTRICTS for e in results[d]["envs"]]
    reports = {}

    # normalized.jsonl
    lines = []
    for r in sorted(applied, key=lambda r: r["txn"]):
        lines.append(_xjson.dumps({
            "cents": r["cents"],
            "date": r["day"],
            "district": r["env"]["district"],
            "envelope": r["env"]["code"],
            "source": r["source"],
            "txn": r["txn"],
        }, separators=(",", ":"), sort_keys=True, ensure_ascii=True))
    reports["normalized.jsonl"] = _xlines(lines)

    # data_quality.json
    reports["data_quality.json"] = _xjson_report({
        "exports": quality,
        "corrections": {
            "applied": len(applied_corr),
            "past_cutoff": sum(1 for c in corrections if c["seq"] > cutoff),
        },
    })

    # summary.json
    exits = {k: 0 for k in _xEXITS}
    for d in _xDISTRICTS:
        exits[results[d]["exit"]] += 1
    reports["summary.json"] = _xjson_report({
        "first_day": first_day,
        "last_day": last_day,
        "households": len(_xDISTRICTS),
        "exits": exits,
        "moved_dollars": sum(results[d]["moved"] for d in _xDISTRICTS),
        "transactions_applied": len(applied),
    })

    # product_summary.json
    cats = {}
    for e in ordered:
        c = cats.setdefault(e["category"], {
            "category": e["category"], "envelopes": 0, "presweep_dollars": 0,
            "final_dollars": 0, "moved_in_dollars": 0, "moved_out_dollars": 0,
        })
        c["envelopes"] += 1
        c["presweep_dollars"] += e["presweep"]
        c["final_dollars"] += e["final"]
        c["moved_in_dollars"] += max(0, e["final"] - e["presweep"])
        c["moved_out_dollars"] += max(0, e["presweep"] - e["final"])
    reports["product_summary.json"] = _xjson_report({"categories": [cats[k] for k in sorted(cats)]})

    # region_<district>.json
    for d in _xDISTRICTS:
        res = results[d]
        reports["region_%s.json" % d] = _xjson_report({
            "district": d,
            "household": res["hh"],
            "family_name": res["family"],
            "exit": res["exit"],
            "rounds": len(res["rounds"]),
            "damping_percent": res["rate"],
            "pool_dollars": res["pool"],
            "moved_dollars": res["moved"],
            "envelopes": [{
                "code": e["code"],
                "label": e["label"],
                "category": e["category"],
                "segment": e["segment"],
                "need_dollars": e["need"],
                "presweep_dollars": e["presweep"],
                "final_dollars": e["final"],
            } for e in res["envs"]],
        })

    # hold_<household code>.json, one per household whose sweep ends stalled
    holds = []
    for d in _xDISTRICTS:
        res = results[d]
        if res["exit"] != "stalled":
            continue
        below = [e for e in res["envs"] if e["final"] < e["need"]]
        name = "hold_%s.json" % res["hh"].lower()
        holds.append(name)
        reports[name] = _xjson_report({"district": d, "household": res["hh"], "rounds": len(res["rounds"]),
                                       "short_dollars": sum(e["need"] - e["final"] for e in below),
                                       "envelopes": [{"code": e["code"], "category": e["category"], "segment": e["segment"],
                                                      "short_dollars": e["need"] - e["final"]} for e in below]})

    # segment_<segment>.json
    for s in _xSEGMENTS:
        members = [e for e in ordered if e["segment"].lower() == s]
        seg_name = members[0]["segment"] if members else next(
            (v for v in segments.values() if v.lower() == s), s)
        reports["segment_%s.json" % s] = _xjson_report({
            "segment": seg_name,
            "envelopes": len(members),
            "presweep_dollars": sum(e["presweep"] for e in members),
            "final_dollars": sum(e["final"] for e in members),
            "members": [{"district": e["district"], "code": e["code"], "final_dollars": e["final"]} for e in members],
        })

    # sweep_rounds.csv
    lines = ["district,round,spread,damping_percent,strikes,posted_dollars"]
    for d in _xDISTRICTS:
        for i, rd in enumerate(results[d]["rounds"], 1):
            lines.append("%s,%d,%d,%d,%d,%d" % (d, i, rd["spread"], rd["rate"], rd["strikes"], rd["posted"]))
    reports["sweep_rounds.csv"] = _xlines(lines)

    # envelope_final.tsv
    lines = ["district\tcode\tlabel\tcategory\tsegment\tfinal_dollars"]
    for e in ordered:
        lines.append("\t".join([e["district"], e["code"], e["label"], e["category"], e["segment"], str(e["final"])]))
    reports["envelope_final.tsv"] = _xlines(lines)

    # moves.csv
    lines = ["district,code,label,presweep_dollars,final_dollars,moved_dollars"]
    for e in ordered:
        if e["final"] != e["presweep"]:
            lines.append("%s,%s,%s,%d,%d,%d" % (e["district"], e["code"], e["label"], e["presweep"], e["final"], e["final"] - e["presweep"]))
    reports["moves.csv"] = _xlines(lines)

    # exits.xml
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', "<sweep>"]
    for d in _xDISTRICTS:
        res = results[d]
        lines.append('  <household district="%s" exit="%s" rounds="%s" damping_percent="%s" family_name="%s"/>' % (
            _xxml_attr(d), _xxml_attr(res["exit"]), _xxml_attr(len(res["rounds"])),
            _xxml_attr(res["rate"]), _xxml_attr(res["family"])))
    lines.append("</sweep>")
    reports["exits.xml"] = _xlines(lines)

    # prior_delta.yaml
    prior = _xjson.loads(_xread_text(root / "prior_sweep.json"))["households"]
    prior = {k.strip().lower(): v for k, v in prior.items()}
    reports["prior_delta.yaml"] = _xlines(
        ["%s: %d" % (d, results[d]["moved"] - int(prior[d]["moved_dollars"])) for d in _xDISTRICTS])

    # reconciliation.txt
    reports["reconciliation.txt"] = _xlines([
        "%s pool=%d final=%d moved=%d" % (d, results[d]["pool"], sum(e["final"] for e in results[d]["envs"]), results[d]["moved"])
        for d in _xDISTRICTS])

    # ledger_totals.psv
    lines = ["district|code|applied_cents|presweep_dollars"]
    for e in ordered:
        lines.append("%s|%s|%d|%d" % (e["district"], e["code"], e["applied_cents"], e["presweep"]))
    reports["ledger_totals.psv"] = _xlines(lines)

    # table reports (their table text)
    env_rows = [(e["district"], e["code"], e["final"]) for e in ordered]
    hh_rows = [(d, results[d]["exit"], len(results[d]["rounds"]), results[d]["rate"]) for d in _xDISTRICTS]
    reports["sweep.sqlite"] = _xtable_text([
        ("envelope_final", ["district", "code", "final_dollars"], env_rows),
        ("household_exit", ["district", "exit", "rounds", "damping_percent"], hh_rows),
    ])
    reports["sweep_book.xlsx"] = _xtable_text([
        ("exits", ["district", "exit", "rounds", "damping_percent"], hh_rows),
        ("final", ["district", "code", "final_dollars"], env_rows),
    ])

    # manifest.json
    reports["manifest.json"] = _xjson_report({"reports": [
        {"name": name, "sha256": _xhashlib.sha256(reports[name]).hexdigest()}
        for name in sorted(reports)
    ]})
    return {name: reports[name] for name in REPORT_NAMES + sorted(holds)}


# ---------------------------------------------------------------- delivered tables

def _xsqlite_value(v):
    if v is None:
        return ""
    if isinstance(v, bytes):
        return v.decode("utf-8")
    if isinstance(v, float):
        if v == int(v):
            return str(int(v))
        return repr(v)
    return str(v)


def table_values(path) -> bytes:
    """Table text (layout_tables.md) of a delivered sweep.sqlite or sweep_book.xlsx."""
    path = _xpathlib.Path(path)
    try:
        if path.suffix.lower() == ".sqlite":
            uri = "file:" + str(path.resolve()) + "?mode=ro"
            con = _xsqlite3.connect(uri, uri=True)
            try:
                tables = []
                for name in ("envelope_final", "household_exit"):
                    cur = con.execute('SELECT * FROM "%s" ORDER BY rowid' % name)
                    header = [col[0] for col in cur.description]
                    rows = [[_xsqlite_value(v) for v in row] for row in cur.fetchall()]
                    tables.append((name, header, rows))
            finally:
                con.close()
        elif path.suffix.lower() == ".xlsx":
            tables = []
            for name, rows in _xxlsx_sheets(path):
                if not rows:
                    tables.append((name, [], []))
                else:
                    tables.append((name, rows[0], rows[1:]))
        else:
            raise ValueError("unsupported table report %s" % path.name)
        return _xtable_text(tables)
    except ValueError:
        raise
    except Exception as exc:  # any parse failure
        raise ValueError("cannot read %s: %s" % (path, exc)) from exc

import json as _json2
CORPUS = [{'seed': 40371, 'households': {'central': {'envs': [{'code': 'VB52', 'label': 'Car', 'need': 99, 'bal': 50}, {'code': 'VC75', 'label': 'Dental', 'need': 37, 'bal': 39}, {'code': 'VC16', 'label': 'utilities', 'need': 72, 'bal': 110}, {'code': 'VB80', 'label': 'groceries', 'need': 119, 'bal': 19}, {'code': 'VC15', 'label': 'pet care', 'need': 63, 'bal': 46}], 'd': 85, 'K': 1, 'B': 18}, 'east': {'envs': [{'code': 'VD22', 'label': 'groceries', 'need': 22, 'bal': 22}, {'code': 'VE86', 'label': 'Phone', 'need': 112, 'bal': 77}, {'code': 'VE50', 'label': 'utilities', 'need': 115, 'bal': 95}, {'code': 'VF63', 'label': 'Dental', 'need': 68, 'bal': 0}], 'd': 77, 'K': 1, 'B': 23}, 'north': {'envs': [{'code': 'VH42', 'label': 'utilities', 'need': 293, 'bal': 552}, {'code': 'VJ35', 'label': 'insurance', 'need': 571, 'bal': 234}, {'code': 'VG39', 'label': 'Phone', 'need': 292, 'bal': 258}, {'code': 'VJ92', 'label': 'Gifts', 'need': 208, 'bal': 326}, {'code': 'VH22', 'label': 'Holiday', 'need': 191, 'bal': 51}], 'd': 89, 'K': 1, 'B': 17}, 'south': {'envs': [{'code': 'VM65', 'label': 'Gifts', 'need': 202, 'bal': 275}, {'code': 'VM11', 'label': 'insurance', 'need': 86, 'bal': 170}, {'code': 'VM52', 'label': 'Phone', 'need': 176, 'bal': 166}, {'code': 'VM79', 'label': 'groceries', 'need': 48, 'bal': 38}, {'code': 'VN32', 'label': 'bus pass', 'need': 179, 'bal': 14}], 'd': 87, 'K': 1, 'B': 28}, 'west': {'envs': [{'code': 'VR36', 'label': 'Phone', 'need': 70, 'bal': 134}, {'code': 'VR64', 'label': 'groceries', 'need': 133, 'bal': 109}, {'code': 'VS91', 'label': 'Garden', 'need': 128, 'bal': 190}, {'code': 'VS86', 'label': 'school fees', 'need': 89, 'bal': 1}, {'code': 'VR51', 'label': 'medical', 'need': 92, 'bal': 50}], 'd': 80, 'K': 1, 'B': 16}}, 'error': None, 'plant': {'S1': True, 'M2': True, 'DI': True, 'X1': True, 'A1': True, 'OV': True}, 'plan_seed': 40371001, 'twin_seed': 40371001, 'plans': 4}, {'seed': 40372, 'households': {'central': {'envs': [{'code': 'VC17', 'label': 'Kids', 'need': 104, 'bal': 113}, {'code': 'VB22', 'label': 'Phone', 'need': 36, 'bal': 53}, {'code': 'VC26', 'label': 'utilities', 'need': 70, 'bal': 72}, {'code': 'VB95', 'label': 'Rent', 'need': 130, 'bal': 123}], 'd': 83, 'K': 1, 'B': 23}, 'east': {'envs': [{'code': 'VD65', 'label': 'pet care', 'need': 208, 'bal': 13}, {'code': 'VE73', 'label': 'groceries', 'need': 196, 'bal': 226}, {'code': 'VF50', 'label': 'Rent', 'need': 110, 'bal': 23}, {'code': 'VF39', 'label': 'bus pass', 'need': 161, 'bal': 46}, {'code': 'VD71', 'label': 'Holiday', 'need': 169, 'bal': 302}], 'd': 54, 'K': 2, 'B': 17}, 'north': {'envs': [{'code': 'VG86', 'label': 'medical', 'need': 186, 'bal': 317}, {'code': 'VH85', 'label': 'Kids', 'need': 134, 'bal': 255}, {'code': 'VJ84', 'label': 'Dental', 'need': 59, 'bal': 61}, {'code': 'VJ49', 'label': 'pet care', 'need': 148, 'bal': 246}, {'code': 'VJ58', 'label': 'Garden', 'need': 264, 'bal': 390}, {'code': 'VJ47', 'label': 'utilities', 'need': 267, 'bal': 426}], 'd': 54, 'K': 2, 'B': 8}, 'south': {'envs': [{'code': 'VN41', 'label': 'pet care', 'need': 72, 'bal': 98}, {'code': 'VN11', 'label': 'insurance', 'need': 133, 'bal': 142}, {'code': 'VK58', 'label': 'Rent', 'need': 85, 'bal': 114}, {'code': 'VM61', 'label': 'medical', 'need': 62, 'bal': 71}], 'd': 83, 'K': 1, 'B': 9}, 'west': {'envs': [{'code': 'VR51', 'label': 'groceries', 'need': 97, 'bal': 97}, {'code': 'VR11', 'label': 'dining', 'need': 139, 'bal': 267}, {'code': 'VP83', 'label': 'bus pass', 'need': 111, 'bal': 186}, {'code': 'VR85', 'label': 'Garden', 'need': 152, 'bal': 146}, {'code': 'VS98', 'label': 'school fees', 'need': 296, 'bal': 42}], 'd': 88, 'K': 2, 'B': 16}}, 'error': None, 'plant': {'S2': True, 'M1': True, 'Q1': True, 'A2': True}, 'plan_seed': 40372001, 'twin_seed': 40372001, 'plans': 4}, {'seed': 40373, 'households': {'central': {'envs': [{'code': 'VC12', 'label': 'groceries', 'need': 188, 'bal': 331}, {'code': 'VB13', 'label': 'Holiday', 'need': 39, 'bal': 35}, {'code': 'VC33', 'label': 'Rent', 'need': 116, 'bal': 108}, {'code': 'VA93', 'label': 'school fees', 'need': 148, 'bal': 13}, {'code': 'VB38', 'label': 'Dental', 'need': 108, 'bal': 60}, {'code': 'VB27', 'label': 'dining', 'need': 26, 'bal': 30}], 'd': 92, 'K': 2, 'B': 28}, 'east': {'envs': [{'code': 'VF54', 'label': 'Phone', 'need': 311, 'bal': 492}, {'code': 'VD54', 'label': 'Holiday', 'need': 357, 'bal': 294}, {'code': 'VE73', 'label': 'Gifts', 'need': 91, 'bal': 10}, {'code': 'VE62', 'label': 'Garden', 'need': 529, 'bal': 298}, {'code': 'VD63', 'label': 'Kids', 'need': 588, 'bal': 690}], 'd': 96, 'K': 2, 'B': 17}, 'north': {'envs': [{'code': 'VJ42', 'label': 'Kids', 'need': 113, 'bal': 87}, {'code': 'VJ37', 'label': 'Holiday', 'need': 142, 'bal': 63}, {'code': 'VH30', 'label': 'utilities', 'need': 116, 'bal': 181}, {'code': 'VH16', 'label': 'Rent', 'need': 34, 'bal': 68}], 'd': 66, 'K': 1, 'B': 14}, 'south': {'envs': [{'code': 'VM29', 'label': 'pet care', 'need': 66, 'bal': 51}, {'code': 'VK51', 'label': 'Holiday', 'need': 148, 'bal': 126}, {'code': 'VN44', 'label': 'Rent', 'need': 218, 'bal': 8}, {'code': 'VK22', 'label': 'Kids', 'need': 98, 'bal': 49}, {'code': 'VM84', 'label': 'Garden', 'need': 129, 'bal': 173}], 'd': 80, 'K': 1, 'B': 14}, 'west': {'envs': [{'code': 'VS74', 'label': 'school fees', 'need': 248, 'bal': 484}, {'code': 'VP90', 'label': 'groceries', 'need': 199, 'bal': 154}, {'code': 'VS55', 'label': 'Car', 'need': 170, 'bal': 71}, {'code': 'VP72', 'label': 'Garden', 'need': 175, 'bal': 108}, {'code': 'VS39', 'label': 'insurance', 'need': 202, 'bal': 5}], 'd': 60, 'K': 1, 'B': 9}}, 'error': None, 'plant': {'S3': True, 'N': True, 'ST': True, 'D1': True, 'P1': True, 'OV': True, 'A4': True}, 'plan_seed': 40373004, 'twin_seed': 40373004, 'plans': 6}, {'seed': 40374, 'households': {'central': {'envs': [{'code': 'VB67', 'label': 'bus pass', 'need': 37, 'bal': 53}, {'code': 'VA93', 'label': 'Dental', 'need': 75, 'bal': 55}, {'code': 'VA20', 'label': 'Gifts', 'need': 54, 'bal': 68}, {'code': 'VC66', 'label': 'dining', 'need': 102, 'bal': 9}], 'd': 88, 'K': 2, 'B': 8}, 'east': {'envs': [{'code': 'VD35', 'label': 'Gifts', 'need': 276, 'bal': 377}, {'code': 'VD18', 'label': 'dining', 'need': 284, 'bal': 198}, {'code': 'VE26', 'label': 'utilities', 'need': 240, 'bal': 446}, {'code': 'VD58', 'label': 'medical', 'need': 519, 'bal': 281}], 'd': 59, 'K': 3, 'B': 21}, 'north': {'envs': [{'code': 'VH28', 'label': 'Garden', 'need': 491, 'bal': 492}, {'code': 'VG56', 'label': 'groceries', 'need': 493, 'bal': 511}, {'code': 'VH54', 'label': 'Car', 'need': 65, 'bal': 94}, {'code': 'VJ95', 'label': 'Phone', 'need': 422, 'bal': 240}, {'code': 'VH85', 'label': 'pet care', 'need': 419, 'bal': 316}], 'd': 80, 'K': 3, 'B': 11}, 'south': {'envs': [{'code': 'VM60', 'label': 'Rent', 'need': 310, 'bal': 56}, {'code': 'VN94', 'label': 'pet care', 'need': 233, 'bal': 261}, {'code': 'VM12', 'label': 'utilities', 'need': 99, 'bal': 198}, {'code': 'VM63', 'label': 'Gifts', 'need': 118, 'bal': 101}, {'code': 'VM72', 'label': 'bus pass', 'need': 370, 'bal': 63}, {'code': 'VM56', 'label': 'school fees', 'need': 289, 'bal': 24}], 'd': 56, 'K': 3, 'B': 27}, 'west': {'envs': [{'code': 'VS31', 'label': 'Rent', 'need': 371, 'bal': 41}, {'code': 'VP43', 'label': 'groceries', 'need': 195, 'bal': 126}, {'code': 'VP26', 'label': 'Kids', 'need': 476, 'bal': 810}, {'code': 'VR74', 'label': 'school fees', 'need': 191, 'bal': 4}, {'code': 'VS24', 'label': 'Phone', 'need': 255, 'bal': 270}, {'code': 'VS60', 'label': 'Holiday', 'need': 253, 'bal': 289}], 'd': 62, 'K': 2, 'B': 21}}, 'error': None, 'plant': {'S23': True, 'M1': True, 'Q2': True, 'A1': True}, 'plan_seed': 40374004, 'twin_seed': 40374004, 'plans': 4}, {'seed': 40375, 'households': {'central': {'envs': [{'code': 'VA39', 'label': 'Car', 'need': 259, 'bal': 498}, {'code': 'VA67', 'label': 'Dental', 'need': 379, 'bal': 643}, {'code': 'VB48', 'label': 'school fees', 'need': 178, 'bal': 229}, {'code': 'VB15', 'label': 'utilities', 'need': 512, 'bal': 133}], 'd': 40, 'K': 1, 'B': 25}, 'east': {'envs': [{'code': 'VF27', 'label': 'groceries', 'need': 212, 'bal': 32}, {'code': 'VE83', 'label': 'Gifts', 'need': 229, 'bal': 398}, {'code': 'VE32', 'label': 'medical', 'need': 377, 'bal': 63}, {'code': 'VF90', 'label': 'Phone', 'need': 419, 'bal': 298}, {'code': 'VF83', 'label': 'insurance', 'need': 483, 'bal': 333}], 'd': 53, 'K': 2, 'B': 9}, 'north': {'envs': [{'code': 'VG95', 'label': 'insurance', 'need': 169, 'bal': 284}, {'code': 'VG65', 'label': 'Gifts', 'need': 200, 'bal': 225}, {'code': 'VG89', 'label': 'Phone', 'need': 20, 'bal': 10}, {'code': 'VH15', 'label': 'Holiday', 'need': 114, 'bal': 128}, {'code': 'VJ50', 'label': 'medical', 'need': 259, 'bal': 22}, {'code': 'VH51', 'label': 'Car', 'need': 254, 'bal': 166}], 'd': 70, 'K': 2, 'B': 25}, 'south': {'envs': [{'code': 'VN60', 'label': 'Kids', 'need': 26, 'bal': 4}, {'code': 'VN77', 'label': 'Gifts', 'need': 71, 'bal': 112}, {'code': 'VN68', 'label': 'insurance', 'need': 71, 'bal': 22}, {'code': 'VK82', 'label': 'school fees', 'need': 108, 'bal': 182}, {'code': 'VK41', 'label': 'Dental', 'need': 144, 'bal': 104}, {'code': 'VM37', 'label': 'Rent', 'need': 93, 'bal': 52}], 'd': 55, 'K': 2, 'B': 11}, 'west': {'envs': [{'code': 'VS81', 'label': 'Rent', 'need': 71, 'bal': 45}, {'code': 'VS31', 'label': 'Car', 'need': 125, 'bal': 134}, {'code': 'VR85', 'label': 'Kids', 'need': 58, 'bal': 114}, {'code': 'VS54', 'label': 'bus pass', 'need': 86, 'bal': 74}], 'd': 44, 'K': 1, 'B': 20}}, 'error': None, 'plant': {'S1': True, 'M1': True, 'X1': True, 'A2': True, 'OV': True}, 'plan_seed': 40375001, 'twin_seed': 40375001, 'plans': 4}, {'seed': 40376, 'households': {'central': {'envs': [{'code': 'VC88', 'label': 'groceries', 'need': 291, 'bal': 188}, {'code': 'VB54', 'label': 'Garden', 'need': 83, 'bal': 24}, {'code': 'VC32', 'label': 'Phone', 'need': 106, 'bal': 107}, {'code': 'VC36', 'label': 'Kids', 'need': 228, 'bal': 322}, {'code': 'VB77', 'label': 'Dental', 'need': 166, 'bal': 30}], 'd': 65, 'K': 1, 'B': 9}, 'east': {'envs': [{'code': 'VF14', 'label': 'Kids', 'need': 97, 'bal': 168}, {'code': 'VD19', 'label': 'Phone', 'need': 175, 'bal': 217}, {'code': 'VE28', 'label': 'dining', 'need': 89, 'bal': 77}, {'code': 'VE78', 'label': 'Gifts', 'need': 427, 'bal': 378}, {'code': 'VF31', 'label': 'Holiday', 'need': 178, 'bal': 69}], 'd': 71, 'K': 2, 'B': 15}, 'north': {'envs': [{'code': 'VJ61', 'label': 'Car', 'need': 109, 'bal': 121}, {'code': 'VG77', 'label': 'insurance', 'need': 37, 'bal': 47}, {'code': 'VH67', 'label': 'Holiday', 'need': 52, 'bal': 16}, {'code': 'VH45', 'label': 'Phone', 'need': 102, 'bal': 79}], 'd': 60, 'K': 2, 'B': 20}, 'south': {'envs': [{'code': 'VK57', 'label': 'Gifts', 'need': 227, 'bal': 26}, {'code': 'VN41', 'label': 'Car', 'need': 134, 'bal': 94}, {'code': 'VM22', 'label': 'school fees', 'need': 36, 'bal': 28}, {'code': 'VM23', 'label': 'Dental', 'need': 51, 'bal': 95}, {'code': 'VK38', 'label': 'pet care', 'need': 58, 'bal': 110}], 'd': 69, 'K': 2, 'B': 14}, 'west': {'envs': [{'code': 'VP37', 'label': 'insurance', 'need': 497, 'bal': 306}, {'code': 'VS94', 'label': 'pet care', 'need': 122, 'bal': 51}, {'code': 'VP59', 'label': 'school fees', 'need': 24, 'bal': 12}, {'code': 'VR24', 'label': 'Car', 'need': 582, 'bal': 191}, {'code': 'VR54', 'label': 'Rent', 'need': 410, 'bal': 674}, {'code': 'VR13', 'label': 'dining', 'need': 266, 'bal': 446}], 'd': 55, 'K': 3, 'B': 24}}, 'error': None, 'plant': {'M1': True, 'Q1': True, 'P1': True, 'A4': True}, 'plan_seed': 40376001, 'twin_seed': 40376001, 'plans': 4}, {'seed': 40377, 'households': {'central': {'envs': [{'code': 'VB82', 'label': 'utilities', 'need': 241, 'bal': 278}, {'code': 'VB77', 'label': 'dining', 'need': 300, 'bal': 97}, {'code': 'VB56', 'label': 'Kids', 'need': 249, 'bal': 128}, {'code': 'VA78', 'label': 'Holiday', 'need': 298, 'bal': 465}, {'code': 'VB97', 'label': 'Phone', 'need': 205, 'bal': 221}, {'code': 'VB28', 'label': 'Dental', 'need': 183, 'bal': 250}], 'd': 89, 'K': 1, 'B': 7}, 'east': {'envs': [{'code': 'VE63', 'label': 'Holiday', 'need': 76, 'bal': 48}, {'code': 'VF72', 'label': 'Car', 'need': 94, 'bal': 149}, {'code': 'VD71', 'label': 'Dental', 'need': 23, 'bal': 19}, {'code': 'VD38', 'label': 'Kids', 'need': 48, 'bal': 19}, {'code': 'VF70', 'label': 'school fees', 'need': 31, 'bal': 19}], 'd': 84, 'K': 1, 'B': 9}, 'north': {'envs': [{'code': 'VJ10', 'label': 'Garden', 'need': 110, 'bal': 52}, {'code': 'VJ78', 'label': 'Holiday', 'need': 119, 'bal': 193}, {'code': 'VJ46', 'label': 'medical', 'need': 106, 'bal': 197}, {'code': 'VG54', 'label': 'Rent', 'need': 86, 'bal': 96}, {'code': 'VH89', 'label': 'dining', 'need': 150, 'bal': 16}], 'd': 92, 'K': 2, 'B': 10}, 'south': {'envs': [{'code': 'VM85', 'label': 'insurance', 'need': 525, 'bal': 285}, {'code': 'VN36', 'label': 'dining', 'need': 463, 'bal': 840}, {'code': 'VN14', 'label': 'Car', 'need': 418, 'bal': 777}, {'code': 'VM24', 'label': 'Rent', 'need': 567, 'bal': 197}, {'code': 'VN83', 'label': 'school fees', 'need': 566, 'bal': 695}, {'code': 'VN60', 'label': 'Gifts', 'need': 356, 'bal': 68}], 'd': 93, 'K': 2, 'B': 22}, 'west': {'envs': [{'code': 'VS74', 'label': 'Gifts', 'need': 55, 'bal': 12}, {'code': 'VS11', 'label': 'Dental', 'need': 141, 'bal': 209}, {'code': 'VS70', 'label': 'Phone', 'need': 107, 'bal': 95}, {'code': 'VP80', 'label': 'Garden', 'need': 58, 'bal': 23}, {'code': 'VP62', 'label': 'utilities', 'need': 138, 'bal': 174}, {'code': 'VP65', 'label': 'groceries', 'need': 81, 'bal': 45}], 'd': 93, 'K': 2, 'B': 23}}, 'error': None, 'plant': {'S1': True, 'D1': True, 'P1': True, 'OV': True, 'A4': True}, 'plan_seed': 40377001, 'twin_seed': 40377001, 'plans': 4}, {'seed': 40378, 'households': {'central': {'envs': [{'code': 'VB85', 'label': 'Dental', 'need': 115, 'bal': 189}, {'code': 'VB12', 'label': 'insurance', 'need': 114, 'bal': 1}, {'code': 'VB30', 'label': 'pet care', 'need': 338, 'bal': 439}, {'code': 'VC22', 'label': 'Garden', 'need': 319, 'bal': 143}, {'code': 'VA70', 'label': 'medical', 'need': 493, 'bal': 632}, {'code': 'VC73', 'label': 'Rent', 'need': 504, 'bal': 367}], 'd': 50, 'K': 3, 'B': 26}, 'east': {'envs': [{'code': 'VE48', 'label': 'bus pass', 'need': 24, 'bal': 33}, {'code': 'VF83', 'label': 'dining', 'need': 274, 'bal': 352}, {'code': 'VD92', 'label': 'groceries', 'need': 152, 'bal': 84}, {'code': 'VE65', 'label': 'Kids', 'need': 159, 'bal': 281}, {'code': 'VD44', 'label': 'medical', 'need': 65, 'bal': 63}, {'code': 'VF55', 'label': 'school fees', 'need': 218, 'bal': 185}], 'd': 33, 'K': 3, 'B': 17}, 'north': {'envs': [{'code': 'VH15', 'label': 'Phone', 'need': 115, 'bal': 53}, {'code': 'VH87', 'label': 'Kids', 'need': 40, 'bal': 44}, {'code': 'VH22', 'label': 'groceries', 'need': 66, 'bal': 65}, {'code': 'VH11', 'label': 'school fees', 'need': 95, 'bal': 16}, {'code': 'VH57', 'label': 'bus pass', 'need': 93, 'bal': 163}, {'code': 'VG45', 'label': 'medical', 'need': 135, 'bal': 221}], 'd': 30, 'K': 1, 'B': 8}, 'south': {'envs': [{'code': 'VN23', 'label': 'groceries', 'need': 133, 'bal': 106}, {'code': 'VK74', 'label': 'school fees', 'need': 36, 'bal': 44}, {'code': 'VN81', 'label': 'Holiday', 'need': 547, 'bal': 34}, {'code': 'VK49', 'label': 'medical', 'need': 579, 'bal': 391}, {'code': 'VK12', 'label': 'Dental', 'need': 362, 'bal': 180}], 'd': 62, 'K': 2, 'B': 24}, 'west': {'envs': [{'code': 'VS88', 'label': 'pet care', 'need': 48, 'bal': 44}, {'code': 'VR98', 'label': 'Holiday', 'need': 277, 'bal': 118}, {'code': 'VR31', 'label': 'Rent', 'need': 64, 'bal': 118}, {'code': 'VR64', 'label': 'Car', 'need': 279, 'bal': 71}], 'd': 57, 'K': 3, 'B': 25}}, 'error': None, 'plant': {'S2': True, 'ST': True, 'Q2': True, 'A2': True}, 'plan_seed': 40378002, 'twin_seed': 40378002, 'plans': 7}, {'seed': 40379, 'households': {'central': {'envs': [{'code': 'VA22', 'label': 'Car', 'need': 71, 'bal': 19}, {'code': 'VA27', 'label': 'pet care', 'need': 21, 'bal': 13}, {'code': 'VB51', 'label': 'Holiday', 'need': 241, 'bal': 257}, {'code': 'VA78', 'label': 'utilities', 'need': 94, 'bal': 135}], 'd': 82, 'K': 1, 'B': 27}, 'east': {'envs': [{'code': 'VD49', 'label': 'Kids', 'need': 194, 'bal': 195}, {'code': 'VF92', 'label': 'Rent', 'need': 89, 'bal': 3}, {'code': 'VD98', 'label': 'groceries', 'need': 189, 'bal': 184}, {'code': 'VD34', 'label': 'medical', 'need': 62, 'bal': 107}], 'd': 71, 'K': 1, 'B': 9}, 'north': {'envs': [{'code': 'VG74', 'label': 'Holiday', 'need': 143, 'bal': 180}, {'code': 'VJ41', 'label': 'school fees', 'need': 234, 'bal': 379}, {'code': 'VJ21', 'label': 'bus pass', 'need': 262, 'bal': 22}, {'code': 'VH55', 'label': 'Dental', 'need': 130, 'bal': 193}, {'code': 'VH61', 'label': 'medical', 'need': 300, 'bal': 351}, {'code': 'VH25', 'label': 'groceries', 'need': 272, 'bal': 158}], 'd': 94, 'K': 3, 'B': 16}, 'south': {'envs': [{'code': 'VK88', 'label': 'Dental', 'need': 118, 'bal': 55}, {'code': 'VK65', 'label': 'bus pass', 'need': 146, 'bal': 123}, {'code': 'VN91', 'label': 'utilities', 'need': 97, 'bal': 168}, {'code': 'VK22', 'label': 'insurance', 'need': 50, 'bal': 11}, {'code': 'VN81', 'label': 'Holiday', 'need': 47, 'bal': 57}], 'd': 94, 'K': 1, 'B': 24}, 'west': {'envs': [{'code': 'VR76', 'label': 'groceries', 'need': 84, 'bal': 34}, {'code': 'VP72', 'label': 'Holiday', 'need': 117, 'bal': 148}, {'code': 'VS56', 'label': 'Phone', 'need': 148, 'bal': 70}, {'code': 'VR62', 'label': 'dining', 'need': 149, 'bal': 254}, {'code': 'VS79', 'label': 'Dental', 'need': 110, 'bal': 34}, {'code': 'VR86', 'label': 'Rent', 'need': 130, 'bal': 183}], 'd': 96, 'K': 2, 'B': 17}}, 'error': None, 'plant': {'S3': True, 'M2': True, 'DI': True, 'X1': True, 'A1': True, 'OV': True}, 'plan_seed': 40379001, 'twin_seed': 40379001, 'plans': 4}, {'seed': 40380, 'households': {'central': {'envs': [{'code': 'VB58', 'label': 'insurance', 'need': 85, 'bal': 49}, {'code': 'VA59', 'label': 'utilities', 'need': 93, 'bal': 124}, {'code': 'VB32', 'label': 'Garden', 'need': 32, 'bal': 58}, {'code': 'VA78', 'label': 'groceries', 'need': 86, 'bal': 50}], 'd': 65, 'K': 3, 'B': 22}, 'east': {'envs': [{'code': 'VF89', 'label': 'Garden', 'need': 420, 'bal': 343}, {'code': 'VF43', 'label': 'Phone', 'need': 424, 'bal': 845}, {'code': 'VF72', 'label': 'groceries', 'need': 60, 'bal': 79}, {'code': 'VE82', 'label': 'Kids', 'need': 62, 'bal': 76}, {'code': 'VE66', 'label': 'Rent', 'need': 472, 'bal': 840}], 'd': 50, 'K': 3, 'B': 18}, 'north': {'envs': [{'code': 'VH62', 'label': 'Car', 'need': 269, 'bal': 20}, {'code': 'VJ41', 'label': 'utilities', 'need': 105, 'bal': 12}, {'code': 'VJ20', 'label': 'Dental', 'need': 96, 'bal': 85}, {'code': 'VH58', 'label': 'Garden', 'need': 75, 'bal': 31}, {'code': 'VH39', 'label': 'Holiday', 'need': 285, 'bal': 142}], 'd': 62, 'K': 3, 'B': 24}, 'south': {'envs': [{'code': 'VN61', 'label': 'groceries', 'need': 178, 'bal': 132}, {'code': 'VN34', 'label': 'Garden', 'need': 227, 'bal': 204}, {'code': 'VK45', 'label': 'bus pass', 'need': 79, 'bal': 123}, {'code': 'VM40', 'label': 'pet care', 'need': 170, 'bal': 49}], 'd': 54, 'K': 2, 'B': 18}, 'west': {'envs': [{'code': 'VS92', 'label': 'Kids', 'need': 239, 'bal': 85}, {'code': 'VP11', 'label': 'Rent', 'need': 112, 'bal': 77}, {'code': 'VP19', 'label': 'Phone', 'need': 164, 'bal': 41}, {'code': 'VS78', 'label': 'school fees', 'need': 257, 'bal': 139}, {'code': 'VR29', 'label': 'utilities', 'need': 48, 'bal': 59}, {'code': 'VP48', 'label': 'pet care', 'need': 297, 'bal': 88}], 'd': 50, 'K': 1, 'B': 10}}, 'error': None, 'plant': {'M1': True, 'Q1': True, 'A2': True}, 'plan_seed': 40380003, 'twin_seed': 40380003, 'plans': 4}, {'seed': 40381, 'households': {'central': {'envs': [{'code': 'VA97', 'label': 'Phone', 'need': 105, 'bal': 47}, {'code': 'VB70', 'label': 'Car', 'need': 70, 'bal': 44}, {'code': 'VA12', 'label': 'medical', 'need': 124, 'bal': 208}, {'code': 'VB34', 'label': 'Gifts', 'need': 74, 'bal': 56}, {'code': 'VA87', 'label': 'bus pass', 'need': 69, 'bal': 48}, {'code': 'VB16', 'label': 'dining', 'need': 125, 'bal': 21}], 'd': 68, 'K': 2, 'B': 7}, 'east': {'envs': [{'code': 'VD79', 'label': 'groceries', 'need': 521, 'bal': 346}, {'code': 'VE51', 'label': 'utilities', 'need': 534, 'bal': 903}, {'code': 'VE85', 'label': 'medical', 'need': 212, 'bal': 402}, {'code': 'VF91', 'label': 'school fees', 'need': 258, 'bal': 384}], 'd': 90, 'K': 2, 'B': 18}, 'north': {'envs': [{'code': 'VJ79', 'label': 'Gifts', 'need': 250, 'bal': 271}, {'code': 'VJ98', 'label': 'Kids', 'need': 246, 'bal': 101}, {'code': 'VJ30', 'label': 'Phone', 'need': 514, 'bal': 226}, {'code': 'VH68', 'label': 'medical', 'need': 571, 'bal': 625}, {'code': 'VG21', 'label': 'school fees', 'need': 159, 'bal': 270}], 'd': 54, 'K': 3, 'B': 15}, 'south': {'envs': [{'code': 'VN84', 'label': 'Rent', 'need': 219, 'bal': 360}, {'code': 'VM93', 'label': 'groceries', 'need': 441, 'bal': 587}, {'code': 'VK17', 'label': 'medical', 'need': 563, 'bal': 603}, {'code': 'VK34', 'label': 'Kids', 'need': 115, 'bal': 11}], 'd': 54, 'K': 3, 'B': 6}, 'west': {'envs': [{'code': 'VR32', 'label': 'groceries', 'need': 257, 'bal': 445}, {'code': 'VR79', 'label': 'Phone', 'need': 56, 'bal': 40}, {'code': 'VS18', 'label': 'medical', 'need': 293, 'bal': 512}, {'code': 'VR69', 'label': 'school fees', 'need': 122, 'bal': 88}], 'd': 50, 'K': 3, 'B': 14}}, 'error': None, 'plant': {'S1': True, 'D1': True, 'P1': True, 'OV': True, 'A4': True}, 'plan_seed': 40381001, 'twin_seed': 40381001, 'plans': 4}, {'seed': 40382, 'households': {'central': {'envs': [{'code': 'VC92', 'label': 'Car', 'need': 205, 'bal': 259}, {'code': 'VA89', 'label': 'Holiday', 'need': 125, 'bal': 10}, {'code': 'VB95', 'label': 'school fees', 'need': 269, 'bal': 495}, {'code': 'VC11', 'label': 'Garden', 'need': 157, 'bal': 173}, {'code': 'VC74', 'label': 'pet care', 'need': 286, 'bal': 74}], 'd': 93, 'K': 2, 'B': 22}, 'east': {'envs': [{'code': 'VD30', 'label': 'insurance', 'need': 382, 'bal': 422}, {'code': 'VF88', 'label': 'medical', 'need': 317, 'bal': 228}, {'code': 'VF26', 'label': 'school fees', 'need': 53, 'bal': 18}, {'code': 'VF89', 'label': 'Dental', 'need': 385, 'bal': 594}, {'code': 'VF91', 'label': 'Car', 'need': 423, 'bal': 578}, {'code': 'VF29', 'label': 'Gifts', 'need': 333, 'bal': 4}], 'd': 99, 'K': 2, 'B': 18}, 'north': {'envs': [{'code': 'VJ47', 'label': 'medical', 'need': 197, 'bal': 245}, {'code': 'VH73', 'label': 'Holiday', 'need': 218, 'bal': 119}, {'code': 'VJ85', 'label': 'Rent', 'need': 65, 'bal': 34}, {'code': 'VH52', 'label': 'bus pass', 'need': 169, 'bal': 218}], 'd': 90, 'K': 1, 'B': 12}, 'south': {'envs': [{'code': 'VK59', 'label': 'utilities', 'need': 28, 'bal': 29}, {'code': 'VM42', 'label': 'Kids', 'need': 50, 'bal': 14}, {'code': 'VN56', 'label': 'dining', 'need': 71, 'bal': 21}, {'code': 'VK44', 'label': 'Rent', 'need': 60, 'bal': 102}, {'code': 'VN59', 'label': 'Car', 'need': 102, 'bal': 111}], 'd': 91, 'K': 2, 'B': 14}, 'west': {'envs': [{'code': 'VR52', 'label': 'Phone', 'need': 130, 'bal': 56}, {'code': 'VS82', 'label': 'Dental', 'need': 143, 'bal': 31}, {'code': 'VS22', 'label': 'Rent', 'need': 48, 'bal': 60}, {'code': 'VP19', 'label': 'school fees', 'need': 130, 'bal': 131}, {'code': 'VP56', 'label': 'Garden', 'need': 76, 'bal': 44}], 'd': 60, 'K': 1, 'B': 10}}, 'error': None, 'plant': {'N': True, 'M1': True, 'Q2': True, 'A1': True}, 'plan_seed': 40382002, 'twin_seed': 40382002, 'plans': 8}, {'seed': 40383, 'households': {'central': {'envs': [{'code': 'VA70', 'label': 'school fees', 'need': 312, 'bal': 173}, {'code': 'VB84', 'label': 'insurance', 'need': 421, 'bal': 207}, {'code': 'VC88', 'label': 'medical', 'need': 369, 'bal': 95}, {'code': 'VA58', 'label': 'pet care', 'need': 155, 'bal': 264}], 'd': 85, 'K': 2, 'B': 6}, 'east': {'envs': [{'code': 'VE92', 'label': 'school fees', 'need': 79, 'bal': 7}, {'code': 'VE97', 'label': 'pet care', 'need': 103, 'bal': 3}, {'code': 'VF97', 'label': 'insurance', 'need': 86, 'bal': 96}, {'code': 'VF55', 'label': 'medical', 'need': 134, 'bal': 36}, {'code': 'VE20', 'label': 'bus pass', 'need': 143, 'bal': 278}, {'code': 'VE52', 'label': 'Gifts', 'need': 33, 'bal': 61}], 'd': 94, 'K': 2, 'B': 6}, 'north': {'envs': [{'code': 'VH43', 'label': 'Gifts', 'need': 524, 'bal': 158}, {'code': 'VJ38', 'label': 'insurance', 'need': 21, 'bal': 1}, {'code': 'VJ26', 'label': 'Holiday', 'need': 401, 'bal': 749}, {'code': 'VJ71', 'label': 'Rent', 'need': 467, 'bal': 322}, {'code': 'VJ48', 'label': 'school fees', 'need': 362, 'bal': 537}], 'd': 95, 'K': 3, 'B': 13}, 'south': {'envs': [{'code': 'VK56', 'label': 'medical', 'need': 121, 'bal': 122}, {'code': 'VN67', 'label': 'groceries', 'need': 145, 'bal': 175}, {'code': 'VK64', 'label': 'dining', 'need': 104, 'bal': 23}, {'code': 'VN65', 'label': 'bus pass', 'need': 33, 'bal': 52}, {'code': 'VK60', 'label': 'utilities', 'need': 100, 'bal': 24}], 'd': 49, 'K': 1, 'B': 26}, 'west': {'envs': [{'code': 'VR98', 'label': 'bus pass', 'need': 95, 'bal': 142}, {'code': 'VR73', 'label': 'medical', 'need': 95, 'bal': 106}, {'code': 'VS42', 'label': 'dining', 'need': 424, 'bal': 634}, {'code': 'VP39', 'label': 'Holiday', 'need': 509, 'bal': 268}, {'code': 'VR63', 'label': 'Gifts', 'need': 298, 'bal': 256}, {'code': 'VP66', 'label': 'Dental', 'need': 344, 'bal': 226}], 'd': 74, 'K': 3, 'B': 17}}, 'error': None, 'plant': {'S2': True, 'S1': True, 'M2': True, 'DI': True, 'X1': True, 'A2': True, 'OV': True}, 'plan_seed': 40383001, 'twin_seed': 40383001, 'plans': 4}, {'seed': 40384, 'households': {'central': {'envs': [{'code': 'VB54', 'label': 'Holiday', 'need': 76, 'bal': 20}, {'code': 'VB18', 'label': 'Gifts', 'need': 65, 'bal': 10}, {'code': 'VA90', 'label': 'groceries', 'need': 85, 'bal': 119}, {'code': 'VC98', 'label': 'Car', 'need': 54, 'bal': 21}, {'code': 'VB97', 'label': 'Dental', 'need': 56, 'bal': 53}], 'd': 80, 'K': 2, 'B': 30}, 'east': {'envs': [{'code': 'VE28', 'label': 'Holiday', 'need': 158, 'bal': 39}, {'code': 'VD76', 'label': 'insurance', 'need': 77, 'bal': 56}, {'code': 'VE71', 'label': 'school fees', 'need': 237, 'bal': 146}, {'code': 'VE19', 'label': 'Dental', 'need': 532, 'bal': 351}, {'code': 'VE43', 'label': 'Phone', 'need': 50, 'bal': 97}, {'code': 'VF42', 'label': 'dining', 'need': 162, 'bal': 165}], 'd': 50, 'K': 2, 'B': 23}, 'north': {'envs': [{'code': 'VJ24', 'label': 'Phone', 'need': 309, 'bal': 8}, {'code': 'VG17', 'label': 'Dental', 'need': 507, 'bal': 260}, {'code': 'VG14', 'label': 'Holiday', 'need': 274, 'bal': 115}, {'code': 'VJ34', 'label': 'dining', 'need': 583, 'bal': 439}], 'd': 30, 'K': 3, 'B': 26}, 'south': {'envs': [{'code': 'VM60', 'label': 'Car', 'need': 44, 'bal': 25}, {'code': 'VM94', 'label': 'pet care', 'need': 70, 'bal': 21}, {'code': 'VK74', 'label': 'utilities', 'need': 58, 'bal': 52}, {'code': 'VK60', 'label': 'Phone', 'need': 50, 'bal': 30}, {'code': 'VN82', 'label': 'insurance', 'need': 72, 'bal': 52}, {'code': 'VK57', 'label': 'medical', 'need': 103, 'bal': 166}], 'd': 54, 'K': 2, 'B': 25}, 'west': {'envs': [{'code': 'VP94', 'label': 'Car', 'need': 150, 'bal': 158}, {'code': 'VS68', 'label': 'dining', 'need': 68, 'bal': 76}, {'code': 'VR62', 'label': 'bus pass', 'need': 74, 'bal': 135}, {'code': 'VP83', 'label': 'Phone', 'need': 25, 'bal': 34}], 'd': 75, 'K': 2, 'B': 17}}, 'error': None, 'plant': {'S3': True, 'ST': True, 'N': True, 'Q1': True, 'A1': True}, 'plan_seed': 40384003, 'twin_seed': 40384003, 'plans': 9}, {'seed': 40385, 'households': {'central': {'envs': [{'code': 'VB15', 'label': 'Gifts', 'need': 137, 'bal': 199}, {'code': 'VA69', 'label': 'Phone', 'need': 122, 'bal': 48}, {'code': 'VA81', 'label': 'dining', 'need': 85, 'bal': 92}, {'code': 'VA72', 'label': 'Dental', 'need': 149, 'bal': 60}, {'code': 'VB87', 'label': 'insurance', 'need': 119, 'bal': 40}, {'code': 'VA49', 'label': 'medical', 'need': 42, 'bal': 37}], 'd': 48, 'K': 2, 'B': 12}, 'east': {'envs': [{'code': 'VF37', 'label': 'insurance', 'need': 57, 'bal': 110}, {'code': 'VD41', 'label': 'school fees', 'need': 39, 'bal': 48}, {'code': 'VE20', 'label': 'utilities', 'need': 40, 'bal': 1}, {'code': 'VE66', 'label': 'Rent', 'need': 50, 'bal': 42}, {'code': 'VD61', 'label': 'dining', 'need': 25, 'bal': 19}], 'd': 94, 'K': 1, 'B': 22}, 'north': {'envs': [{'code': 'VJ39', 'label': 'utilities', 'need': 177, 'bal': 112}, {'code': 'VJ47', 'label': 'dining', 'need': 248, 'bal': 64}, {'code': 'VH55', 'label': 'Garden', 'need': 139, 'bal': 118}, {'code': 'VH22', 'label': 'medical', 'need': 80, 'bal': 4}, {'code': 'VG75', 'label': 'Kids', 'need': 275, 'bal': 441}], 'd': 98, 'K': 2, 'B': 7}, 'south': {'envs': [{'code': 'VM77', 'label': 'Dental', 'need': 544, 'bal': 683}, {'code': 'VK88', 'label': 'dining', 'need': 69, 'bal': 86}, {'code': 'VM98', 'label': 'medical', 'need': 210, 'bal': 352}, {'code': 'VM37', 'label': 'bus pass', 'need': 573, 'bal': 341}, {'code': 'VM63', 'label': 'pet care', 'need': 514, 'bal': 803}], 'd': 61, 'K': 2, 'B': 6}, 'west': {'envs': [{'code': 'VS15', 'label': 'Car', 'need': 188, 'bal': 32}, {'code': 'VS68', 'label': 'dining', 'need': 196, 'bal': 59}, {'code': 'VR20', 'label': 'Rent', 'need': 252, 'bal': 80}, {'code': 'VR56', 'label': 'bus pass', 'need': 266, 'bal': 257}, {'code': 'VP38', 'label': 'Kids', 'need': 225, 'bal': 423}, {'code': 'VS17', 'label': 'Holiday', 'need': 149, 'bal': 261}], 'd': 98, 'K': 1, 'B': 16}}, 'error': None, 'plant': {'S23': True, 'M1': True, 'D1': True, 'P1': True, 'OV': True, 'A4P': True}, 'plan_seed': 40385001, 'twin_seed': 40385001, 'plans': 4}, {'seed': 40386, 'households': {'central': {'envs': [{'code': 'VC10', 'label': 'Car', 'need': 152, 'bal': 95}, {'code': 'VC38', 'label': 'Gifts', 'need': 225, 'bal': 243}, {'code': 'VA90', 'label': 'utilities', 'need': 245, 'bal': 279}, {'code': 'VB47', 'label': 'Rent', 'need': 176, 'bal': 77}], 'd': 50, 'K': 2, 'B': 25}, 'east': {'envs': [{'code': 'VE52', 'label': 'bus pass', 'need': 35, 'bal': 35}, {'code': 'VF16', 'label': 'Gifts', 'need': 49, 'bal': 14}, {'code': 'VF29', 'label': 'utilities', 'need': 84, 'bal': 49}, {'code': 'VE69', 'label': 'medical', 'need': 347, 'bal': 325}, {'code': 'VD76', 'label': 'groceries', 'need': 547, 'bal': 456}], 'd': 69, 'K': 2, 'B': 19}, 'north': {'envs': [{'code': 'VG21', 'label': 'dining', 'need': 134, 'bal': 117}, {'code': 'VJ77', 'label': 'Kids', 'need': 127, 'bal': 51}, {'code': 'VJ33', 'label': 'Dental', 'need': 110, 'bal': 99}, {'code': 'VH83', 'label': 'Holiday', 'need': 119, 'bal': 119}], 'd': 66, 'K': 2, 'B': 8}, 'south': {'envs': [{'code': 'VM43', 'label': 'utilities', 'need': 248, 'bal': 257}, {'code': 'VN12', 'label': 'bus pass', 'need': 39, 'bal': 33}, {'code': 'VN10', 'label': 'Car', 'need': 35, 'bal': 36}, {'code': 'VM29', 'label': 'groceries', 'need': 89, 'bal': 103}, {'code': 'VN45', 'label': 'school fees', 'need': 96, 'bal': 78}], 'd': 70, 'K': 3, 'B': 8}, 'west': {'envs': [{'code': 'VS35', 'label': 'utilities', 'need': 28, 'bal': 10}, {'code': 'VR64', 'label': 'Dental', 'need': 274, 'bal': 405}, {'code': 'VP24', 'label': 'bus pass', 'need': 322, 'bal': 320}, {'code': 'VR48', 'label': 'Car', 'need': 467, 'bal': 899}, {'code': 'VP18', 'label': 'Garden', 'need': 526, 'bal': 347}, {'code': 'VS64', 'label': 'Kids', 'need': 82, 'bal': 95}], 'd': 70, 'K': 3, 'B': 15}}, 'error': None, 'plant': {'Q2': True, 'A2': True}, 'plan_seed': 40386001, 'twin_seed': 40386001, 'plans': 4}, {'seed': 40387, 'households': {'central': {'envs': [{'code': 'VB37', 'label': 'medical', 'need': 184, 'bal': 176}, {'code': 'VC41', 'label': 'Kids', 'need': 255, 'bal': 166}, {'code': 'VA50', 'label': 'dining', 'need': 108, 'bal': 131}, {'code': 'VA68', 'label': 'Rent', 'need': 73, 'bal': 102}, {'code': 'VB68', 'label': 'Car', 'need': 20, 'bal': 11}], 'd': 51, 'K': 1, 'B': 24}, 'east': {'envs': [{'code': 'VF80', 'label': 'pet care', 'need': 95, 'bal': 55}, {'code': 'VF49', 'label': 'bus pass', 'need': 100, 'bal': 74}, {'code': 'VE37', 'label': 'Holiday', 'need': 78, 'bal': 147}, {'code': 'VF36', 'label': 'school fees', 'need': 25, 'bal': 8}, {'code': 'VF26', 'label': 'medical', 'need': 145, 'bal': 252}], 'd': 55, 'K': 1, 'B': 7}, 'north': {'envs': [{'code': 'VJ20', 'label': 'Garden', 'need': 54, 'bal': 100}, {'code': 'VG74', 'label': 'Phone', 'need': 201, 'bal': 359}, {'code': 'VG88', 'label': 'school fees', 'need': 291, 'bal': 488}, {'code': 'VG90', 'label': 'Kids', 'need': 155, 'bal': 235}, {'code': 'VH51', 'label': 'Car', 'need': 61, 'bal': 14}], 'd': 34, 'K': 2, 'B': 25}, 'south': {'envs': [{'code': 'VN50', 'label': 'groceries', 'need': 108, 'bal': 59}, {'code': 'VM19', 'label': 'bus pass', 'need': 49, 'bal': 28}, {'code': 'VM89', 'label': 'Garden', 'need': 76, 'bal': 25}, {'code': 'VN18', 'label': 'medical', 'need': 85, 'bal': 112}, {'code': 'VK98', 'label': 'pet care', 'need': 83, 'bal': 101}], 'd': 53, 'K': 3, 'B': 22}, 'west': {'envs': [{'code': 'VR80', 'label': 'Garden', 'need': 196, 'bal': 1}, {'code': 'VS33', 'label': 'pet care', 'need': 34, 'bal': 42}, {'code': 'VP65', 'label': 'groceries', 'need': 370, 'bal': 212}, {'code': 'VP45', 'label': 'Car', 'need': 461, 'bal': 898}, {'code': 'VP96', 'label': 'medical', 'need': 480, 'bal': 145}], 'd': 58, 'K': 3, 'B': 12}}, 'error': None, 'plant': {'S1': True, 'M2': True, 'DI': True, 'X1': True, 'A1': True}, 'plan_seed': 40387001, 'twin_seed': 40387001, 'plans': 4}, {'seed': 40388, 'households': {'central': {'envs': [{'code': 'VA39', 'label': 'Rent', 'need': 428, 'bal': 577}, {'code': 'VC18', 'label': 'Car', 'need': 296, 'bal': 579}, {'code': 'VC89', 'label': 'groceries', 'need': 218, 'bal': 380}, {'code': 'VA95', 'label': 'pet care', 'need': 143, 'bal': 55}], 'd': 44, 'K': 3, 'B': 12}, 'east': {'envs': [{'code': 'VE38', 'label': 'utilities', 'need': 54, 'bal': 27}, {'code': 'VD20', 'label': 'insurance', 'need': 28, 'bal': 0}, {'code': 'VE36', 'label': 'Garden', 'need': 52, 'bal': 84}, {'code': 'VD78', 'label': 'pet care', 'need': 66, 'bal': 15}, {'code': 'VD14', 'label': 'Kids', 'need': 28, 'bal': 54}, {'code': 'VE62', 'label': 'groceries', 'need': 54, 'bal': 80}], 'd': 61, 'K': 2, 'B': 27}, 'north': {'envs': [{'code': 'VH35', 'label': 'medical', 'need': 334, 'bal': 339}, {'code': 'VH48', 'label': 'Dental', 'need': 367, 'bal': 124}, {'code': 'VG76', 'label': 'Garden', 'need': 67, 'bal': 125}, {'code': 'VJ23', 'label': 'Rent', 'need': 272, 'bal': 86}, {'code': 'VH82', 'label': 'Phone', 'need': 83, 'bal': 94}, {'code': 'VJ87', 'label': 'Car', 'need': 321, 'bal': 67}], 'd': 60, 'K': 1, 'B': 28}, 'south': {'envs': [{'code': 'VM87', 'label': 'school fees', 'need': 272, 'bal': 0}, {'code': 'VM53', 'label': 'pet care', 'need': 85, 'bal': 20}, {'code': 'VN90', 'label': 'Phone', 'need': 200, 'bal': 215}, {'code': 'VM62', 'label': 'Holiday', 'need': 219, 'bal': 121}, {'code': 'VN63', 'label': 'groceries', 'need': 161, 'bal': 265}, {'code': 'VM51', 'label': 'Dental', 'need': 47, 'bal': 39}], 'd': 95, 'K': 2, 'B': 6}, 'west': {'envs': [{'code': 'VR15', 'label': 'pet care', 'need': 454, 'bal': 732}, {'code': 'VS57', 'label': 'school fees', 'need': 594, 'bal': 425}, {'code': 'VS27', 'label': 'bus pass', 'need': 461, 'bal': 272}, {'code': 'VR17', 'label': 'Dental', 'need': 281, 'bal': 369}], 'd': 49, 'K': 2, 'B': 25}}, 'error': None, 'plant': {'S2': True, 'M1': True, 'Q1': True, 'A4': True}, 'plan_seed': 40388001, 'twin_seed': 40388001, 'plans': 4}, {'seed': 40389, 'households': {'central': {'envs': [{'code': 'VC30', 'label': 'school fees', 'need': 257, 'bal': 282}, {'code': 'VC48', 'label': 'Phone', 'need': 167, 'bal': 310}, {'code': 'VA56', 'label': 'bus pass', 'need': 190, 'bal': 353}, {'code': 'VA24', 'label': 'Kids', 'need': 213, 'bal': 370}, {'code': 'VA73', 'label': 'Garden', 'need': 199, 'bal': 299}, {'code': 'VA84', 'label': 'dining', 'need': 182, 'bal': 278}], 'd': 32, 'K': 1, 'B': 13}, 'east': {'envs': [{'code': 'VD30', 'label': 'Gifts', 'need': 197, 'bal': 69}, {'code': 'VF86', 'label': 'groceries', 'need': 148, 'bal': 110}, {'code': 'VD19', 'label': 'Kids', 'need': 30, 'bal': 46}, {'code': 'VD10', 'label': 'bus pass', 'need': 46, 'bal': 64}, {'code': 'VE93', 'label': 'Rent', 'need': 81, 'bal': 109}, {'code': 'VD24', 'label': 'Dental', 'need': 61, 'bal': 51}], 'd': 53, 'K': 3, 'B': 20}, 'north': {'envs': [{'code': 'VJ80', 'label': 'medical', 'need': 496, 'bal': 186}, {'code': 'VH47', 'label': 'dining', 'need': 373, 'bal': 618}, {'code': 'VH18', 'label': 'Dental', 'need': 569, 'bal': 1130}, {'code': 'VJ14', 'label': 'Rent', 'need': 74, 'bal': 137}, {'code': 'VJ90', 'label': 'bus pass', 'need': 599, 'bal': 411}, {'code': 'VH38', 'label': 'Garden', 'need': 114, 'bal': 110}], 'd': 63, 'K': 2, 'B': 14}, 'south': {'envs': [{'code': 'VN93', 'label': 'insurance', 'need': 247, 'bal': 51}, {'code': 'VM14', 'label': 'dining', 'need': 134, 'bal': 177}, {'code': 'VK24', 'label': 'Dental', 'need': 148, 'bal': 185}, {'code': 'VK50', 'label': 'medical', 'need': 257, 'bal': 83}, {'code': 'VM50', 'label': 'utilities', 'need': 130, 'bal': 35}], 'd': 35, 'K': 2, 'B': 8}, 'west': {'envs': [{'code': 'VR93', 'label': 'Car', 'need': 395, 'bal': 379}, {'code': 'VP84', 'label': 'Gifts', 'need': 422, 'bal': 691}, {'code': 'VR78', 'label': 'dining', 'need': 142, 'bal': 16}, {'code': 'VR24', 'label': 'Garden', 'need': 346, 'bal': 233}, {'code': 'VP19', 'label': 'pet care', 'need': 347, 'bal': 557}, {'code': 'VR16', 'label': 'Rent', 'need': 269, 'bal': 211}], 'd': 73, 'K': 1, 'B': 6}}, 'error': None, 'plant': {'S3': True, 'M1': True, 'N': True, 'D1': True, 'P1': True}, 'plan_seed': 40389001, 'twin_seed': 40389001, 'plans': 11}, {'seed': 40390, 'households': {'central': {'envs': [{'code': 'VA74', 'label': 'Phone', 'need': 29, 'bal': 5}, {'code': 'VB22', 'label': 'Holiday', 'need': 298, 'bal': 465}, {'code': 'VA60', 'label': 'groceries', 'need': 180, 'bal': 344}, {'code': 'VC34', 'label': 'Kids', 'need': 215, 'bal': 372}], 'd': 70, 'K': 1, 'B': 26}, 'east': {'envs': [{'code': 'VE75', 'label': 'medical', 'need': 139, 'bal': 72}, {'code': 'VF21', 'label': 'Gifts', 'need': 138, 'bal': 131}, {'code': 'VD34', 'label': 'Phone', 'need': 52, 'bal': 56}, {'code': 'VF49', 'label': 'dining', 'need': 46, 'bal': 26}], 'd': 64, 'K': 3, 'B': 28}, 'north': {'envs': [{'code': 'VG14', 'label': 'groceries', 'need': 61, 'bal': 91}, {'code': 'VJ80', 'label': 'insurance', 'need': 39, 'bal': 61}, {'code': 'VH90', 'label': 'Car', 'need': 123, 'bal': 90}, {'code': 'VH58', 'label': 'Garden', 'need': 128, 'bal': 159}, {'code': 'VG57', 'label': 'Holiday', 'need': 116, 'bal': 12}], 'd': 56, 'K': 3, 'B': 21}, 'south': {'envs': [{'code': 'VM35', 'label': 'Phone', 'need': 158, 'bal': 68}, {'code': 'VM88', 'label': 'pet care', 'need': 276, 'bal': 487}, {'code': 'VK47', 'label': 'Garden', 'need': 203, 'bal': 383}, {'code': 'VN24', 'label': 'Gifts', 'need': 219, 'bal': 351}], 'd': 60, 'K': 3, 'B': 19}, 'west': {'envs': [{'code': 'VR18', 'label': 'Car', 'need': 118, 'bal': 64}, {'code': 'VR26', 'label': 'Holiday', 'need': 92, 'bal': 129}, {'code': 'VP33', 'label': 'Garden', 'need': 140, 'bal': 191}, {'code': 'VR15', 'label': 'dining', 'need': 82, 'bal': 5}, {'code': 'VR43', 'label': 'Kids', 'need': 95, 'bal': 58}], 'd': 51, 'K': 2, 'B': 28}}, 'error': None, 'plant': {'S23': True, 'ST': True, 'Q2': True, 'A4': True}, 'plan_seed': 40390001, 'twin_seed': 40390001, 'plans': 4}, {'seed': 40571, 'households': {'central': {'envs': [{'code': 'VA20', 'label': 'pet care', 'need': 116, 'bal': 98}, {'code': 'VA19', 'label': 'medical', 'need': 60, 'bal': 97}, {'code': 'VC17', 'label': 'utilities', 'need': 35, 'bal': 44}, {'code': 'VA36', 'label': 'Car', 'need': 102, 'bal': 139}], 'd': 85, 'K': 1, 'B': 23}, 'east': {'envs': [{'code': 'VF46', 'label': 'insurance', 'need': 188, 'bal': 146}, {'code': 'VD51', 'label': 'groceries', 'need': 66, 'bal': 9}, {'code': 'VF16', 'label': 'Dental', 'need': 24, 'bal': 29}, {'code': 'VE93', 'label': 'Phone', 'need': 128, 'bal': 163}, {'code': 'VF95', 'label': 'school fees', 'need': 163, 'bal': 176}, {'code': 'VD17', 'label': 'Garden', 'need': 289, 'bal': 162}], 'd': 93, 'K': 1, 'B': 10}, 'north': {'envs': [{'code': 'VJ58', 'label': 'Car', 'need': 55, 'bal': 39}, {'code': 'VG36', 'label': 'Garden', 'need': 119, 'bal': 156}, {'code': 'VH72', 'label': 'dining', 'need': 41, 'bal': 43}, {'code': 'VJ51', 'label': 'groceries', 'need': 73, 'bal': 30}, {'code': 'VG28', 'label': 'utilities', 'need': 97, 'bal': 13}, {'code': 'VJ45', 'label': 'Kids', 'need': 31, 'bal': 23}], 'd': 30, 'K': 3, 'B': 7}, 'south': {'envs': [{'code': 'VN52', 'label': 'bus pass', 'need': 46, 'bal': 6}, {'code': 'VM45', 'label': 'Dental', 'need': 281, 'bal': 186}, {'code': 'VN42', 'label': 'Holiday', 'need': 236, 'bal': 98}, {'code': 'VM60', 'label': 'Kids', 'need': 171, 'bal': 25}], 'd': 54, 'K': 3, 'B': 12}, 'west': {'envs': [{'code': 'VR36', 'label': 'Gifts', 'need': 50, 'bal': 43}, {'code': 'VR33', 'label': 'Holiday', 'need': 65, 'bal': 98}, {'code': 'VS82', 'label': 'Dental', 'need': 46, 'bal': 76}, {'code': 'VS20', 'label': 'bus pass', 'need': 108, 'bal': 202}], 'd': 30, 'K': 3, 'B': 30}}, 'error': 'dup_txn', 'plant': {'ERR': True}, 'plan_seed': 40571001, 'twin_seed': 40571001, 'plans': 4}, {'seed': 40572, 'households': {'central': {'envs': [{'code': 'VA72', 'label': 'bus pass', 'need': 259, 'bal': 275}, {'code': 'VA18', 'label': 'groceries', 'need': 121, 'bal': 123}, {'code': 'VC54', 'label': 'utilities', 'need': 30, 'bal': 43}, {'code': 'VB79', 'label': 'Gifts', 'need': 31, 'bal': 26}, {'code': 'VA58', 'label': 'insurance', 'need': 175, 'bal': 102}, {'code': 'VB24', 'label': 'Holiday', 'need': 248, 'bal': 114}], 'd': 80, 'K': 1, 'B': 6}, 'east': {'envs': [{'code': 'VE80', 'label': 'dining', 'need': 142, 'bal': 59}, {'code': 'VF67', 'label': 'insurance', 'need': 60, 'bal': 75}, {'code': 'VF41', 'label': 'Gifts', 'need': 102, 'bal': 187}, {'code': 'VD94', 'label': 'medical', 'need': 30, 'bal': 52}, {'code': 'VF35', 'label': 'Kids', 'need': 95, 'bal': 91}, {'code': 'VE77', 'label': 'Phone', 'need': 65, 'bal': 70}], 'd': 63, 'K': 2, 'B': 23}, 'north': {'envs': [{'code': 'VJ80', 'label': 'school fees', 'need': 114, 'bal': 159}, {'code': 'VJ91', 'label': 'medical', 'need': 314, 'bal': 358}, {'code': 'VH55', 'label': 'Car', 'need': 580, 'bal': 153}, {'code': 'VJ62', 'label': 'dining', 'need': 576, 'bal': 371}, {'code': 'VG60', 'label': 'pet care', 'need': 274, 'bal': 151}], 'd': 32, 'K': 3, 'B': 24}, 'south': {'envs': [{'code': 'VM31', 'label': 'Phone', 'need': 37, 'bal': 24}, {'code': 'VM70', 'label': 'pet care', 'need': 59, 'bal': 15}, {'code': 'VK20', 'label': 'medical', 'need': 25, 'bal': 32}, {'code': 'VK95', 'label': 'Rent', 'need': 44, 'bal': 74}], 'd': 30, 'K': 3, 'B': 6}, 'west': {'envs': [{'code': 'VS90', 'label': 'school fees', 'need': 42, 'bal': 69}, {'code': 'VR12', 'label': 'Dental', 'need': 55, 'bal': 34}, {'code': 'VS54', 'label': 'dining', 'need': 121, 'bal': 134}, {'code': 'VP41', 'label': 'Car', 'need': 23, 'bal': 37}], 'd': 88, 'K': 1, 'B': 23}}, 'error': 'unknown_env', 'plant': {'ERR': True}, 'plan_seed': 40572001, 'twin_seed': 40572001, 'plans': 6}, {'seed': 40573, 'households': {'central': {'envs': [{'code': 'VC82', 'label': 'school fees', 'need': 94, 'bal': 108}, {'code': 'VA22', 'label': 'Gifts', 'need': 97, 'bal': 137}, {'code': 'VA38', 'label': 'utilities', 'need': 138, 'bal': 212}, {'code': 'VB81', 'label': 'medical', 'need': 139, 'bal': 103}, {'code': 'VC77', 'label': 'Phone', 'need': 75, 'bal': 149}, {'code': 'VB91', 'label': 'pet care', 'need': 42, 'bal': 29}], 'd': 75, 'K': 2, 'B': 6}, 'east': {'envs': [{'code': 'VD70', 'label': 'Gifts', 'need': 89, 'bal': 101}, {'code': 'VD27', 'label': 'medical', 'need': 146, 'bal': 123}, {'code': 'VF83', 'label': 'dining', 'need': 118, 'bal': 148}, {'code': 'VF98', 'label': 'utilities', 'need': 80, 'bal': 25}], 'd': 50, 'K': 2, 'B': 16}, 'north': {'envs': [{'code': 'VG43', 'label': 'Car', 'need': 512, 'bal': 659}, {'code': 'VH67', 'label': 'insurance', 'need': 528, 'bal': 755}, {'code': 'VJ77', 'label': 'Phone', 'need': 392, 'bal': 125}, {'code': 'VH93', 'label': 'Rent', 'need': 513, 'bal': 143}, {'code': 'VJ57', 'label': 'Holiday', 'need': 472, 'bal': 495}], 'd': 80, 'K': 1, 'B': 7}, 'south': {'envs': [{'code': 'VM84', 'label': 'Garden', 'need': 81, 'bal': 77}, {'code': 'VK77', 'label': 'Car', 'need': 124, 'bal': 20}, {'code': 'VK25', 'label': 'Holiday', 'need': 41, 'bal': 72}, {'code': 'VN72', 'label': 'insurance', 'need': 145, 'bal': 138}, {'code': 'VK79', 'label': 'pet care', 'need': 60, 'bal': 12}, {'code': 'VN59', 'label': 'school fees', 'need': 109, 'bal': 40}], 'd': 34, 'K': 1, 'B': 7}, 'west': {'envs': [{'code': 'VR79', 'label': 'Phone', 'need': 202, 'bal': 68}, {'code': 'VS45', 'label': 'Holiday', 'need': 142, 'bal': 195}, {'code': 'VP34', 'label': 'medical', 'need': 284, 'bal': 7}, {'code': 'VR73', 'label': 'groceries', 'need': 67, 'bal': 124}, {'code': 'VP83', 'label': 'Car', 'need': 56, 'bal': 71}, {'code': 'VR82', 'label': 'bus pass', 'need': 114, 'bal': 106}], 'd': 47, 'K': 2, 'B': 16}}, 'error': 'bad_correction', 'plant': {'ERR': True, 'A2': True}, 'plan_seed': 40573001, 'twin_seed': 40573001, 'plans': 7}, {'seed': 40394, 'households': {'central': {'envs': [{'code': 'VB67', 'label': 'bus pass', 'need': 37, 'bal': 53}, {'code': 'VA93', 'label': 'Dental', 'need': 75, 'bal': 55}, {'code': 'VA20', 'label': 'Gifts', 'need': 54, 'bal': 68}, {'code': 'VC66', 'label': 'dining', 'need': 102, 'bal': 9}], 'd': 88, 'K': 2, 'B': 8}, 'east': {'envs': [{'code': 'VD35', 'label': 'Gifts', 'need': 276, 'bal': 377}, {'code': 'VD18', 'label': 'dining', 'need': 284, 'bal': 198}, {'code': 'VE26', 'label': 'utilities', 'need': 240, 'bal': 446}, {'code': 'VD58', 'label': 'medical', 'need': 519, 'bal': 281}], 'd': 59, 'K': 3, 'B': 21}, 'north': {'envs': [{'code': 'VH28', 'label': 'Garden', 'need': 491, 'bal': 492}, {'code': 'VG56', 'label': 'groceries', 'need': 493, 'bal': 511}, {'code': 'VH54', 'label': 'Car', 'need': 65, 'bal': 94}, {'code': 'VJ95', 'label': 'Phone', 'need': 422, 'bal': 240}, {'code': 'VH85', 'label': 'pet care', 'need': 419, 'bal': 316}], 'd': 80, 'K': 3, 'B': 11}, 'south': {'envs': [{'code': 'VM60', 'label': 'Rent', 'need': 310, 'bal': 56}, {'code': 'VN94', 'label': 'pet care', 'need': 233, 'bal': 261}, {'code': 'VM12', 'label': 'utilities', 'need': 99, 'bal': 198}, {'code': 'VM63', 'label': 'Gifts', 'need': 118, 'bal': 101}, {'code': 'VM72', 'label': 'bus pass', 'need': 370, 'bal': 63}, {'code': 'VM56', 'label': 'school fees', 'need': 289, 'bal': 24}], 'd': 56, 'K': 3, 'B': 27}, 'west': {'envs': [{'code': 'VS31', 'label': 'Rent', 'need': 371, 'bal': 41}, {'code': 'VP43', 'label': 'groceries', 'need': 195, 'bal': 126}, {'code': 'VP26', 'label': 'Kids', 'need': 476, 'bal': 810}, {'code': 'VR74', 'label': 'school fees', 'need': 191, 'bal': 4}, {'code': 'VS24', 'label': 'Phone', 'need': 255, 'bal': 270}, {'code': 'VS60', 'label': 'Holiday', 'need': 253, 'bal': 289}], 'd': 62, 'K': 2, 'B': 21}}, 'error': 'no_fit', 'plant': {'ERR': True, 'A2': True}, 'plan_seed': 40394001, 'twin_seed': 40394001, 'plans': 8}, {'seed': 40395, 'households': {'central': {'envs': [{'code': 'VB85', 'label': 'Dental', 'need': 115, 'bal': 189}, {'code': 'VB12', 'label': 'insurance', 'need': 114, 'bal': 1}, {'code': 'VB30', 'label': 'pet care', 'need': 338, 'bal': 439}, {'code': 'VC22', 'label': 'Garden', 'need': 319, 'bal': 143}, {'code': 'VA70', 'label': 'medical', 'need': 493, 'bal': 632}, {'code': 'VC73', 'label': 'Rent', 'need': 504, 'bal': 367}], 'd': 50, 'K': 3, 'B': 26}, 'east': {'envs': [{'code': 'VE48', 'label': 'bus pass', 'need': 24, 'bal': 33}, {'code': 'VF83', 'label': 'dining', 'need': 274, 'bal': 352}, {'code': 'VD92', 'label': 'groceries', 'need': 152, 'bal': 84}, {'code': 'VE65', 'label': 'Kids', 'need': 159, 'bal': 281}, {'code': 'VD44', 'label': 'medical', 'need': 65, 'bal': 63}, {'code': 'VF55', 'label': 'school fees', 'need': 218, 'bal': 185}], 'd': 33, 'K': 3, 'B': 17}, 'north': {'envs': [{'code': 'VH15', 'label': 'Phone', 'need': 115, 'bal': 53}, {'code': 'VH87', 'label': 'Kids', 'need': 40, 'bal': 44}, {'code': 'VH22', 'label': 'groceries', 'need': 66, 'bal': 65}, {'code': 'VH11', 'label': 'school fees', 'need': 95, 'bal': 16}, {'code': 'VH57', 'label': 'bus pass', 'need': 93, 'bal': 163}, {'code': 'VG45', 'label': 'medical', 'need': 135, 'bal': 221}], 'd': 30, 'K': 1, 'B': 8}, 'south': {'envs': [{'code': 'VN23', 'label': 'groceries', 'need': 133, 'bal': 106}, {'code': 'VK74', 'label': 'school fees', 'need': 36, 'bal': 44}, {'code': 'VN81', 'label': 'Holiday', 'need': 547, 'bal': 34}, {'code': 'VK49', 'label': 'medical', 'need': 579, 'bal': 391}, {'code': 'VK12', 'label': 'Dental', 'need': 362, 'bal': 180}], 'd': 62, 'K': 2, 'B': 24}, 'west': {'envs': [{'code': 'VS88', 'label': 'pet care', 'need': 48, 'bal': 44}, {'code': 'VR98', 'label': 'Holiday', 'need': 277, 'bal': 118}, {'code': 'VR31', 'label': 'Rent', 'need': 64, 'bal': 118}, {'code': 'VR64', 'label': 'Car', 'need': 279, 'bal': 71}], 'd': 57, 'K': 3, 'B': 25}}, 'error': 'two_fit', 'plant': {'ERR': True, 'P1': True}, 'plan_seed': 40395001, 'twin_seed': 40395001, 'plans': 4}, {'seed': 40396, 'households': {'central': {'envs': [{'code': 'VA70', 'label': 'school fees', 'need': 312, 'bal': 173}, {'code': 'VB84', 'label': 'insurance', 'need': 421, 'bal': 207}, {'code': 'VC88', 'label': 'medical', 'need': 369, 'bal': 95}, {'code': 'VA58', 'label': 'pet care', 'need': 155, 'bal': 264}], 'd': 85, 'K': 2, 'B': 6}, 'east': {'envs': [{'code': 'VE92', 'label': 'school fees', 'need': 79, 'bal': 7}, {'code': 'VE97', 'label': 'pet care', 'need': 103, 'bal': 3}, {'code': 'VF97', 'label': 'insurance', 'need': 86, 'bal': 96}, {'code': 'VF55', 'label': 'medical', 'need': 134, 'bal': 36}, {'code': 'VE20', 'label': 'bus pass', 'need': 143, 'bal': 278}, {'code': 'VE52', 'label': 'Gifts', 'need': 33, 'bal': 61}], 'd': 94, 'K': 2, 'B': 6}, 'north': {'envs': [{'code': 'VH43', 'label': 'Gifts', 'need': 524, 'bal': 158}, {'code': 'VJ38', 'label': 'insurance', 'need': 21, 'bal': 1}, {'code': 'VJ26', 'label': 'Holiday', 'need': 401, 'bal': 749}, {'code': 'VJ71', 'label': 'Rent', 'need': 467, 'bal': 322}, {'code': 'VJ48', 'label': 'school fees', 'need': 362, 'bal': 537}], 'd': 95, 'K': 3, 'B': 13}, 'south': {'envs': [{'code': 'VK56', 'label': 'medical', 'need': 121, 'bal': 122}, {'code': 'VN67', 'label': 'groceries', 'need': 145, 'bal': 175}, {'code': 'VK64', 'label': 'dining', 'need': 104, 'bal': 23}, {'code': 'VN65', 'label': 'bus pass', 'need': 33, 'bal': 52}, {'code': 'VK60', 'label': 'utilities', 'need': 100, 'bal': 24}], 'd': 49, 'K': 1, 'B': 26}, 'west': {'envs': [{'code': 'VR98', 'label': 'bus pass', 'need': 95, 'bal': 142}, {'code': 'VR73', 'label': 'medical', 'need': 95, 'bal': 106}, {'code': 'VS42', 'label': 'dining', 'need': 424, 'bal': 634}, {'code': 'VP39', 'label': 'Holiday', 'need': 509, 'bal': 268}, {'code': 'VR63', 'label': 'Gifts', 'need': 298, 'bal': 256}, {'code': 'VP66', 'label': 'Dental', 'need': 344, 'bal': 226}], 'd': 74, 'K': 3, 'B': 17}}, 'error': 'bad_crc', 'plant': {'ERR': True, 'P1': True}, 'plan_seed': 40396001, 'twin_seed': 40396001, 'plans': 10}]

# ---- verifier harness ----
import ast as _ast
import base64 as _b64
import hashlib as _hl
import os as _os
import shutil as _shutil
import signal as _signal
import subprocess as _sp
import sys as _sys
import tempfile as _tf
import threading as _th
import zlib as _zlib
from pathlib import Path as _P

OUT = _P("/app/out")
PROGRAM = OUT / "transform.py"
ARTIFACTS = ["normalized.jsonl", "summary.json", "data_quality.json", "product_summary.json", "region_central.json",
             "region_east.json", "region_north.json", "region_south.json", "region_west.json", "segment_consumer.json",
             "segment_corporate.json", "segment_enterprise.json", "segment_smb.json"]
TABLE_REPORTS = ("sweep.sqlite", "sweep_book.xlsx")
CALL_LIMIT = 60
_LOCK = _th.RLock()
_CACHE = {}
_SETPRIV = ["setpriv", "--reuid=nobody", "--regid=nogroup", "--clear-groups"]
_BANNED_MODULES = {"random", "uuid", "secrets"}
_CLOCK_READS = {"time", "time_ns", "monotonic", "monotonic_ns", "perf_counter", "perf_counter_ns", "process_time",
                "process_time_ns", "clock_gettime", "clock_gettime_ns"}
_CLOCK_NOARG = {"gmtime", "localtime", "ctime", "asctime"}
_CLOCK_DT = {"now", "utcnow", "today"}
_FORBIDDEN_EVENTS = {"socket.connect", "socket.bind", "subprocess.Popen", "os.fork", "os.forkpty", "os.system",
                     "os.posix_spawn", "os.spawn", "os.exec"}
_WRAPPER = r'''
import json, os, sys, runpy
_fd = int(sys.argv[1])
_log = os.fdopen(_fd, "w", buffering=1)
_watch = {"open", "sqlite3.connect", "os.remove", "os.rename", "os.unlink", "os.rmdir", "os.mkdir", "shutil.rmtree",
          "socket.connect", "socket.bind", "subprocess.Popen", "os.fork", "os.forkpty", "os.system", "os.posix_spawn",
          "os.spawn", "os.exec"}
def _hook(event, args):
    if event not in _watch:
        return
    try:
        items = [a if isinstance(a, (int, str)) else (a.decode("utf-8", "replace") if isinstance(a, bytes) else repr(a)) for a in args]
        _log.write(json.dumps([event, items]) + "\n")
    except (OSError, ValueError, TypeError):
        pass
sys.addaudithook(_hook)
_prog = sys.argv[2]
sys.argv = [_prog] + sys.argv[3:]
sys.path[0] = os.path.dirname(os.path.abspath(_prog))
runpy.run_path(_prog, run_name="__main__")
'''


def _shipped_root():
    root = _P(_tf.mkdtemp(prefix="hes-ship-"))
    for rel, blob in _SHIPPED_DATA.items():
        (root / rel).write_bytes(_zlib.decompress(_b64.b64decode(blob)))
    _seal(root)
    return root


def _seal(root):
    for path in root.iterdir():
        path.chmod(0o644)
    root.chmod(0o755)
    root.parent.chmod(0o755) if root.parent.name.startswith("hes-") else None


def _base():
    with _LOCK:
        if "base" not in _CACHE:
            base = _P(_tf.mkdtemp(prefix="hes-grade-"))
            base.chmod(0o777)
            (base / "audit_wrap.py").write_text(_WRAPPER, encoding="utf-8")
            (base / "audit_wrap.py").chmod(0o644)
            _CACHE["base"] = base
        return _CACHE["base"]


def _shipped():
    with _LOCK:
        if "ship" not in _CACHE:
            _CACHE["ship"] = _shipped_root()
        return _CACHE["ship"]


def _docs():
    root = _shipped()
    return {p.name: p.read_text(encoding="utf-8") for p in sorted(root.glob("*.md"))}


def _extract(index):
    with _LOCK:
        key = ("extract", index)
        if key not in _CACHE:
            spec = CORPUS[index]
            root = _P(_tf.mkdtemp(prefix=f"hes-x{index}-", dir=str(_base()))) / "data"
            write_extract(root, spec["seed"], spec["households"], _docs(), spec["error"], spec["plant"], spec["plan_seed"], spec["plans"])
            _seal(root)
            root.parent.chmod(0o755)
            _CACHE[key] = root
        return _CACHE[key]


def _expected(index):
    with _LOCK:
        key = ("expected", index)
        if key not in _CACHE:
            try:
                _CACHE[key] = derive_reports(_extract(index))
            except ExtractError:
                _CACHE[key] = None
        return _CACHE[key]


def _grant(path):
    try:
        if not str(path).startswith("/app") or not path.exists():
            return
        path.chmod(path.stat().st_mode | (0o555 if path.is_dir() else 0o444))
        for parent in path.parents:
            parent.chmod(parent.stat().st_mode | 0o555)
            if str(parent) == "/app":
                break
    except OSError:
        pass


def _root_only_tests():
    try:
        st = _P("/tests").stat()
    except OSError:
        return False
    return st.st_uid == 0 and (st.st_mode & 0o077) == 0


def _untrusted(cmd):
    if _os.name == "posix" and _os.geteuid() == 0:
        for arg in cmd:
            _grant(_P(arg))
        return [*_SETPRIV, *cmd]
    if _root_only_tests():
        raise RuntimeError("verifier must run as root to isolate submitted code")
    return cmd


def _reap():
    if _os.name != "posix" or _os.geteuid() != 0:
        return
    for proc in _P("/proc").iterdir():
        if not proc.name.isdigit():
            continue
        try:
            status = (proc / "status").read_text()
        except OSError:
            continue
        for line in status.splitlines():
            if line.startswith("Uid:") and line.split()[1] == "65534":
                try:
                    _os.kill(int(proc.name), _signal.SIGKILL)
                except OSError:
                    pass


def _run(data, out, cwd):
    """Run the delivered program through the audit wrapper. Returns (exit code or None, audit events)."""
    out.parent.mkdir(parents=True, exist_ok=True)
    out.parent.chmod(0o777)
    cwd.mkdir(parents=True, exist_ok=True)
    cwd.chmod(0o777)
    rfd, wfd = _os.pipe()
    cmd = _untrusted([_sys.executable, "-B", str(_base() / "audit_wrap.py"), str(wfd), str(PROGRAM), str(data), str(out)])
    env = {"PATH": "/usr/local/bin:/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1", "HOME": str(cwd), "LANG": "C.UTF-8"}
    code = None
    chunks = []
    reader = _th.Thread(target=lambda: chunks.append(_drain(rfd)))
    reader.start()
    try:
        proc = _sp.Popen(cmd, cwd=str(cwd), env=env, pass_fds=(wfd,), stdout=_sp.DEVNULL, stderr=_sp.DEVNULL,
                         start_new_session=True)
        _os.close(wfd)
        wfd = -1
        try:
            code = proc.wait(timeout=CALL_LIMIT)
        except _sp.TimeoutExpired:
            proc.kill()
            proc.wait()
            code = None
    except OSError:
        code = None
    finally:
        if wfd != -1:
            _os.close(wfd)
        _reap()
        reader.join(timeout=30)
    events = []
    for line in b"".join(chunks).decode("utf-8", "replace").splitlines():
        try:
            events.append(_json2.loads(line))
        except ValueError:
            pass
    return code, events


def _drain(fd):
    parts = []
    try:
        while True:
            block = _os.read(fd, 65536)
            if not block:
                break
            parts.append(block)
    finally:
        _os.close(fd)
    return b"".join(parts)


def _read_out(out):
    """Text reports as bytes; table reports as their table text (decoded content)."""
    found = {}
    try:
        paths = [p for p in out.iterdir() if p.is_file()]
    except OSError:
        return {}
    for p in paths:
        if p.name in TABLE_REPORTS:
            try:
                found[p.name] = table_values(p)
            except Exception:
                found[p.name] = b"unreadable"
        else:
            found[p.name] = p.read_bytes()
    return found


def _program_ok():
    return PROGRAM.is_file()


def _run_extract(index):
    with _LOCK:
        key = ("run", index)
        if key not in _CACHE:
            if not _program_ok():
                _CACHE[key] = (None, {}, [])
            else:
                work = _P(_tf.mkdtemp(prefix=f"hes-r{index}-", dir=str(_base())))
                work.chmod(0o777)
                code, events = _run(_extract(index), work / "out", work / "cwd")
                _CACHE[key] = (code, _read_out(work / "out"), events)
                _CACHE[("outdir", index)] = work / "out"
        return _CACHE[key]


def _run_shipped(tag):
    """tag 'a' and 'b' run at the same staged location; 'c' runs a second staged copy from another directory."""
    with _LOCK:
        key = ("ship-run", tag)
        if key not in _CACHE:
            if not _program_ok():
                _CACHE[key] = (None, {}, [], None)
            else:
                if tag == "c":
                    data = _P(_tf.mkdtemp(prefix="hes-moved-", dir=str(_base()))) / "deep" / "extract"
                    data.parent.mkdir(parents=True)
                    _shutil.copytree(_shipped(), data)
                    _seal(data)
                    data.parent.chmod(0o755)
                    data.parent.parent.chmod(0o755)
                else:
                    data = _shipped()
                before = _digest_tree(data)
                work = _P(_tf.mkdtemp(prefix=f"hes-s{tag}-", dir=str(_base())))
                work.chmod(0o777)
                code, events = _run(data, work / ("out" if tag != "c" else "elsewhere") / "o", work / ("cwd" if tag != "c" else "other"))
                _CACHE[key] = (code, _read_out(work / ("out" if tag != "c" else "elsewhere") / "o"), events,
                               (data, work, before == _digest_tree(data)))
        return _CACHE[key]


def _digest_tree(root):
    h = _hl.sha256()
    for p in sorted(root.rglob("*")):
        if p.is_file():
            h.update(p.name.encode())
            h.update(p.read_bytes())
    return h.hexdigest()


def _same_reports(a, b):
    """Text reports by bytes, table reports by decoded content (both already reduced by _read_out)."""
    return bool(a) and a == b


def canon(name, value):
    """Reports arrive already reduced by _read_out (table reports as their table text)."""
    return value


def _group_ok(index, names):
    try:
        expected = _expected(index)
        code, got, _ev = _run_extract(index)
        if expected is None or code != 0:
            return False
        return all(canon(n, got.get(n)) == expected[n] for n in names)
    except Exception:
        return False


def _timed_ok(index):
    """The run on this extract ended by itself within CALL_LIMIT seconds with status 0 (a run over the limit is killed)
    and wrote the five household reports the reference derives."""
    return _group_ok(index, ["region_%s.json" % d for d in ("central", "east", "north", "south", "west")])


def _twin_extract(index):
    """The error extract's valid near-twin: same seed and households, with the defect left out."""
    with _LOCK:
        key = ("twin", index)
        if key not in _CACHE:
            spec = CORPUS[index]
            root = _P(_tf.mkdtemp(prefix=f"hes-t{index}-", dir=str(_base()))) / "data"
            write_extract(root, spec["seed"], spec["households"], _docs(), None, spec["plant"], spec["twin_seed"], spec["plans"])
            _seal(root)
            root.parent.chmod(0o755)
            _CACHE[key] = root
        return _CACHE[key]


def _twin_ok(index):
    """The program exits 0 on the near-twin and writes exactly the reports the documents give for it."""
    with _LOCK:
        key = ("twin-ok", index)
        if key not in _CACHE:
            twin = _twin_extract(index)
            expected = derive_reports(twin)
            work = _P(_tf.mkdtemp(prefix=f"hes-tr{index}-", dir=str(_base())))
            work.chmod(0o777)
            code, _events = _run(twin, work / "out", work / "cwd")
            got = _read_out(work / "out")
            _CACHE[key] = code == 0 and all(canon(n, got.get(n)) == expected[n] for n in REPORT_NAMES)
        return _CACHE[key]


def _hold_ok(index):
    """The set of hold reports equals the set the documents define for this extract, each byte-exact."""
    try:
        expected = _expected(index)
        code, got, _ev = _run_extract(index)
        if expected is None or code != 0:
            return False
        want = {n: v for n, v in expected.items() if n.startswith("hold_")}
        have = {n: v for n, v in got.items() if n.startswith("hold_")}
        return have == want
    except Exception:
        return False


def _error_ok(index):
    try:
        if not _program_ok():
            return False
        code, got, _ev = _run_extract(index)
        if code is None or code == 0 or any(n in got for n in REPORT_NAMES) or any(n.startswith("hold_") for n in got):
            return False
        return _twin_ok(index)
    except Exception:
        return False


def _shipped_run_ok(name):
    try:
        expected = derive_reports(_shipped())[name]
        code, got, _ev, _info = _run_shipped("a")
        return code == 0 and canon(name, got.get(name)) == expected
    except Exception:
        return False


def _shipped_artifact_ok(name):
    try:
        expected = derive_reports(_shipped())[name]
        return (OUT / name).read_bytes() == expected
    except Exception:
        return False


def _inside(path, roots):
    return any(path == r or path.startswith(r.rstrip("/") + "/") for r in roots)


def _open_paths(events, cwd):
    """Yield (real path, writing) for every file the program asked to open."""
    for ev, args in events:
        if ev == "sqlite3.connect":
            target = str(args[0]) if args else ""
            if target in ("", ":memory:") or target.startswith("file::memory:") or "mode=memory" in target:
                continue
            if target.startswith("file:"):
                target = target[5:].split("?")[0]
            yield _os.path.realpath(_os.path.join(cwd, target)), False
        elif ev == "open" and args and isinstance(args[0], str):
            mode = str(args[1]) if len(args) > 1 else "r"
            flags = args[2] if len(args) > 2 and isinstance(args[2], int) else 0
            writing = any(c in mode for c in "wax+") or bool(flags & (_os.O_WRONLY | _os.O_RDWR | _os.O_CREAT))
            yield _os.path.realpath(_os.path.join(cwd, args[0])), writing
        elif ev in ("os.remove", "os.unlink", "os.rename", "os.rmdir", "os.mkdir", "shutil.rmtree") and args and isinstance(args[0], str):
            yield _os.path.realpath(_os.path.join(cwd, args[0])), True


def _scope_events(tag):
    code, got, events, info = _run_shipped(tag)
    if info is None:
        return None
    data, work, _unchanged = info
    cwd = str(work / ("cwd" if tag != "c" else "other"))
    return list(_open_paths(events, cwd)), str(data), str(work), events
# ---- end verifier harness ----


# ---- negatives ----
_GROUPS = {
    "segment": ["segment_consumer.json", "segment_corporate.json", "segment_enterprise.json", "segment_smb.json"],
    "summary": ["summary.json", "product_summary.json", "sweep_rounds.csv", "exits.xml", "prior_delta.yaml",
                "reconciliation.txt", "manifest.json"],
    "tables": ["sweep.sqlite", "sweep_book.xlsx", "envelope_final.tsv", "moves.csv"],
    "aggregate": ["segment_consumer.json", "segment_corporate.json", "segment_enterprise.json", "segment_smb.json",
                  "summary.json", "product_summary.json", "sweep_rounds.csv", "exits.xml", "prior_delta.yaml",
                  "reconciliation.txt", "manifest.json", "sweep.sqlite", "sweep_book.xlsx", "envelope_final.tsv", "moves.csv"],
    "ledger": ["normalized.jsonl", "data_quality.json", "ledger_totals.psv"],
}
_ZONES = ("/tests", "/logs", "/solution", "/root", "/home")


def _data_tokens():
    root = _shipped()
    found = set()
    for p in root.iterdir():
        raw = p.read_bytes()
        if p.suffix == ".sqlite":
            import sqlite3 as _s
            con = _s.connect(f"file:{p}?mode=ro", uri=True)
            names = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")]
            for name in names:
                for row in con.execute(f'SELECT * FROM "{name}"'):
                    for v in row:
                        if isinstance(v, (int, float)) and float(v).is_integer():
                            found.add(str(int(v)))
                        elif v is not None:
                            found.add(str(v))
            con.close()
            continue
        text = raw.decode("utf-8", "replace")
        token = ""
        for ch in text + " ":
            if ch.isdigit():
                token += ch
            else:
                if token:
                    found.add(str(int(token)))
                token = ""
    return found


def _graded_numbers():
    rep = derive_reports(_shipped())
    nums = set()

    def walk(v):
        if isinstance(v, bool):
            return
        if isinstance(v, int) and abs(v) >= 100:
            nums.add(v)
        elif isinstance(v, dict):
            for x in v.values():
                walk(x)
        elif isinstance(v, list):
            for x in v:
                walk(x)

    for name in ARTIFACTS:
        if name.endswith(".json"):
            walk(_json2.loads(rep[name]))
    return nums


def _act_hardcoded():
    if not _program_ok():
        return False
    try:
        tree = _ast.parse(PROGRAM.read_text(encoding="utf-8", errors="replace"))
    except (SyntaxError, ValueError, OSError):
        return False
    lits = {n.value for n in _ast.walk(tree) if isinstance(n, _ast.Constant) and isinstance(n.value, int) and not isinstance(n.value, bool)}
    tokens = _data_tokens()
    hits = {v for v in lits & _graded_numbers() if str(v) not in tokens}
    if len(hits) >= 3:
        return True
    code, got, _ev = _run_extract(0)
    scode, sgot, _sev, _info = _run_shipped("a")
    spine = "region_north.json"
    return code == 0 and scode == 0 and bool(got.get(spine)) and got.get(spine) == sgot.get(spine)


def _act_read_scope():
    if not _program_ok():
        return False
    for tag in ("a", "c"):
        got = _scope_events(tag)
        if got is None:
            continue
        paths, data, work, _events = got
        allowed = (data, work, str(PROGRAM.parent))
        for path, writing in paths:
            if writing or path == ":memory:" or not path.startswith("/"):
                continue
            if path.endswith("/audit_wrap.py"):
                continue
            if _inside(path, _ZONES):
                return True
            if _inside(path, ("/app",)) and not _inside(path, allowed):
                return True
    return False


def _clock_read(tree):
    """True only for a call that reads the clock; conversions of a given value never count."""
    time_mods, time_names, dt_classes = {"time"}, {}, {"datetime", "date"}
    for node in _ast.walk(tree):
        if isinstance(node, _ast.Import):
            for a in node.names:
                if a.name == "time":
                    time_mods.add(a.asname or "time")
        elif isinstance(node, _ast.ImportFrom) and node.level == 0 and node.module == "time":
            for a in node.names:
                time_names[a.asname or a.name] = a.name
        elif isinstance(node, _ast.ImportFrom) and node.level == 0 and node.module == "datetime":
            for a in node.names:
                if a.name in ("datetime", "date"):
                    dt_classes.add(a.asname or a.name)
    for node in _ast.walk(tree):
        if not isinstance(node, _ast.Call):
            continue
        bare = not node.args and not node.keywords
        func = node.func
        if isinstance(func, _ast.Name) and func.id in time_names:
            attr = time_names[func.id]
            if attr in _CLOCK_READS or (attr in _CLOCK_NOARG and bare):
                return True
        elif isinstance(func, _ast.Attribute):
            base = func.value
            label = base.id if isinstance(base, _ast.Name) else (base.attr if isinstance(base, _ast.Attribute) else "")
            if isinstance(base, _ast.Name) and base.id in time_mods:
                if func.attr in _CLOCK_READS or (func.attr in _CLOCK_NOARG and bare):
                    return True
            if func.attr in _CLOCK_DT and (label in dt_classes or label.lower().endswith(("datetime", "date"))):
                return True
    return False


def _ast_forbidden():
    try:
        tree = _ast.parse(PROGRAM.read_text(encoding="utf-8", errors="replace"))
    except (SyntaxError, ValueError, OSError):
        return False
    local = {p.stem for p in PROGRAM.parent.glob("*.py")}
    stdlib = set(getattr(_sys, "stdlib_module_names", ()))
    names = []
    for node in _ast.walk(tree):
        if isinstance(node, _ast.Import):
            names += [a.name for a in node.names]
        elif isinstance(node, _ast.ImportFrom) and node.module and node.level == 0:
            names.append(node.module)
            names += [node.module + "." + a.name for a in node.names]
    if _clock_read(tree):
        return True
    for name in names:
        top = name.split(".")[0]
        if top in _BANNED_MODULES:
            return True
        if stdlib and top not in stdlib and top not in local and top != "__future__":
            return True
    return False


def _act_forbidden():
    if not _program_ok():
        return False
    for tag in ("a", "b", "c"):
        _code, _got, events, _info = _run_shipped(tag)
        if any(ev in _FORBIDDEN_EVENTS for ev, _args in events):
            return True
    return _ast_forbidden()


def _act_location():
    if not _program_ok():
        return False
    a, b, c = _run_shipped("a"), _run_shipped("b"), _run_shipped("c")
    if a[0] != 0 or b[0] != 0 or c[0] != 0:
        return False
    return _same_reports(a[1], b[1]) and a[1] != c[1]


def _act_writes():
    if not _program_ok():
        return False
    for tag in ("a", "c"):
        code, got, events, info = _run_shipped(tag)
        if info is None:
            continue
        data, work, unchanged = info
        if not unchanged:
            return True
        out = str(work / ("out" if tag != "c" else "elsewhere") / "o")
        cwd = str(work / ("cwd" if tag != "c" else "other"))
        for path, writing in _open_paths(events, cwd):
            if writing and not _inside(path, (out, "/dev")):
                return True
    return False


def _act_nondeterministic():
    if not _program_ok():
        return False
    if _act_forbidden():
        return False
    a, b = _run_shipped("a"), _run_shipped("b")
    if a[0] != 0 or b[0] != 0:
        return False
    return a[1] != b[1]


def _program_tree():
    """The delivered program's syntax tree, once it writes every shipped artifact as the documents define it."""
    if not _program_ok() or not all(_shipped_artifact_ok(n) for n in ARTIFACTS):
        return None
    try:
        return _ast.parse(PROGRAM.read_text(encoding="utf-8", errors="replace"))
    except (SyntaxError, ValueError, OSError):
        return None


def _except_clauses_ok():
    """Every except clause names the classes it catches and does something with the error (not only pass/continue)."""
    tree = _program_tree()
    if tree is None:
        return False
    for node in _ast.walk(tree):
        if isinstance(node, _ast.ExceptHandler):
            if node.type is None:
                return False
            if all(isinstance(st, (_ast.Pass, _ast.Continue)) or (isinstance(st, _ast.Expr) and isinstance(st.value, _ast.Constant))
                   for st in node.body):
                return False
    return True


def _functions_short():
    """Every function of the program is at most 60 lines long."""
    tree = _program_tree()
    if tree is None:
        return False
    return all(n.end_lineno - n.lineno + 1 <= 60 for n in _ast.walk(tree)
               if isinstance(n, (_ast.FunctionDef, _ast.AsyncFunctionDef)))


def _holds(fn, *args):
    try:
        return bool(fn(*args))
    except Exception:
        return False


@criterion(description="The shipped-extract artifact /app/out/normalized.jsonl equals the report the documents define for the shipped extract.")
def shipped_normalizedl(workspace) -> bool:
    return _holds(_shipped_artifact_ok, "normalized.jsonl")


@criterion(description="The shipped-extract artifact /app/out/summary.json equals the report the documents define for the shipped extract.")
def shipped_summary(workspace) -> bool:
    return _holds(_shipped_artifact_ok, "summary.json")


@criterion(description="The shipped-extract artifact /app/out/data_quality.json equals the report the documents define for the shipped extract.")
def shipped_data_quality(workspace) -> bool:
    return _holds(_shipped_artifact_ok, "data_quality.json")


@criterion(description="The shipped-extract artifact /app/out/product_summary.json equals the report the documents define for the shipped extract.")
def shipped_product_summary(workspace) -> bool:
    return _holds(_shipped_artifact_ok, "product_summary.json")


@criterion(description="The shipped-extract artifact /app/out/region_central.json equals the report the documents define for the shipped extract.")
def shipped_region_central(workspace) -> bool:
    return _holds(_shipped_artifact_ok, "region_central.json")


@criterion(description="The shipped-extract artifact /app/out/region_east.json equals the report the documents define for the shipped extract.")
def shipped_region_east(workspace) -> bool:
    return _holds(_shipped_artifact_ok, "region_east.json")


@criterion(description="The shipped-extract artifact /app/out/region_north.json equals the report the documents define for the shipped extract.")
def shipped_region_north(workspace) -> bool:
    return _holds(_shipped_artifact_ok, "region_north.json")


@criterion(description="The shipped-extract artifact /app/out/region_south.json equals the report the documents define for the shipped extract.")
def shipped_region_south(workspace) -> bool:
    return _holds(_shipped_artifact_ok, "region_south.json")


@criterion(description="The shipped-extract artifact /app/out/region_west.json equals the report the documents define for the shipped extract.")
def shipped_region_west(workspace) -> bool:
    return _holds(_shipped_artifact_ok, "region_west.json")


@criterion(description="The shipped-extract artifact /app/out/segment_consumer.json equals the report the documents define for the shipped extract.")
def shipped_segment_consumer(workspace) -> bool:
    return _holds(_shipped_artifact_ok, "segment_consumer.json")


@criterion(description="The shipped-extract artifact /app/out/segment_corporate.json equals the report the documents define for the shipped extract.")
def shipped_segment_corporate(workspace) -> bool:
    return _holds(_shipped_artifact_ok, "segment_corporate.json")


@criterion(description="The shipped-extract artifact /app/out/segment_enterprise.json equals the report the documents define for the shipped extract.")
def shipped_segment_enterprise(workspace) -> bool:
    return _holds(_shipped_artifact_ok, "segment_enterprise.json")


@criterion(description="The shipped-extract artifact /app/out/segment_smb.json equals the report the documents define for the shipped extract.")
def shipped_segment_smb(workspace) -> bool:
    return _holds(_shipped_artifact_ok, "segment_smb.json")


@criterion(description="Held-out extract 1: the central household report region_central.json is byte-exact.")
def x01_central_household_sweep_report(workspace) -> bool:
    return _holds(_group_ok, 0, ["region_central.json"])


@criterion(description="Held-out extract 1: the east household report region_east.json is byte-exact.")
def x01_east_household_sweep_report(workspace) -> bool:
    return _holds(_group_ok, 0, ["region_east.json"])


@criterion(description="Held-out extract 1: the north household report region_north.json is byte-exact.")
def x01_north_household_sweep_report(workspace) -> bool:
    return _holds(_group_ok, 0, ["region_north.json"])


@criterion(description="Held-out extract 1: the south household report region_south.json is byte-exact.")
def x01_south_household_sweep_report(workspace) -> bool:
    return _holds(_group_ok, 0, ["region_south.json"])


@criterion(description="Held-out extract 1: the west household report region_west.json is byte-exact.")
def x01_west_household_sweep_report(workspace) -> bool:
    return _holds(_group_ok, 0, ["region_west.json"])


@criterion(description="Held-out extract 1: the program writes exactly the hold reports the documents define for the extract (one per household whose sweep ends stalled, none for the others), each byte-exact.")
def x01_hold_reports(workspace) -> bool:
    return _holds(_hold_ok, 0)


@criterion(description="Held-out extract 1: the segment, summary, category, round log, exits, prior delta, reconciliation and manifest reports are byte-exact and the sweep database, sweep workbook, envelope final table and moves table match in content.")
def x01_aggregate_reports(workspace) -> bool:
    return _holds(_group_ok, 0, _GROUPS["aggregate"])


@criterion(description="Held-out extract 1: the canonical ledger, data quality and ledger totals reports are byte-exact.")
def x01_ledger_reports(workspace) -> bool:
    return _holds(_group_ok, 0, _GROUPS["ledger"])


@criterion(description="Held-out extract 2: the central household report region_central.json is byte-exact.")
def x02_central_household_sweep_report(workspace) -> bool:
    return _holds(_group_ok, 1, ["region_central.json"])


@criterion(description="Held-out extract 2: the east household report region_east.json is byte-exact.")
def x02_east_household_sweep_report(workspace) -> bool:
    return _holds(_group_ok, 1, ["region_east.json"])


@criterion(description="Held-out extract 2: the north household report region_north.json is byte-exact.")
def x02_north_household_sweep_report(workspace) -> bool:
    return _holds(_group_ok, 1, ["region_north.json"])


@criterion(description="Held-out extract 2: the south household report region_south.json is byte-exact.")
def x02_south_household_sweep_report(workspace) -> bool:
    return _holds(_group_ok, 1, ["region_south.json"])


@criterion(description="Held-out extract 2: the west household report region_west.json is byte-exact.")
def x02_west_household_sweep_report(workspace) -> bool:
    return _holds(_group_ok, 1, ["region_west.json"])


@criterion(description="Held-out extract 2: the segment, summary, category, round log, exits, prior delta, reconciliation and manifest reports are byte-exact and the sweep database, sweep workbook, envelope final table and moves table match in content.")
def x02_aggregate_reports(workspace) -> bool:
    return _holds(_group_ok, 1, _GROUPS["aggregate"])


@criterion(description="Held-out extract 3: the central household report region_central.json is byte-exact.")
def x03_central_household_sweep_report(workspace) -> bool:
    return _holds(_group_ok, 2, ["region_central.json"])


@criterion(description="Held-out extract 3: the east household report region_east.json is byte-exact.")
def x03_east_household_sweep_report(workspace) -> bool:
    return _holds(_group_ok, 2, ["region_east.json"])


@criterion(description="Held-out extract 3: the north household report region_north.json is byte-exact.")
def x03_north_household_sweep_report(workspace) -> bool:
    return _holds(_group_ok, 2, ["region_north.json"])


@criterion(description="Held-out extract 3: the south household report region_south.json is byte-exact.")
def x03_south_household_sweep_report(workspace) -> bool:
    return _holds(_group_ok, 2, ["region_south.json"])


@criterion(description="Held-out extract 3: the west household report region_west.json is byte-exact.")
def x03_west_household_sweep_report(workspace) -> bool:
    return _holds(_group_ok, 2, ["region_west.json"])


@criterion(description="Held-out extract 3: the program writes exactly the hold reports the documents define for the extract (one per household whose sweep ends stalled, none for the others), each byte-exact.")
def x03_hold_reports(workspace) -> bool:
    return _holds(_hold_ok, 2)


@criterion(description="Held-out extract 3: the segment, summary, category, round log, exits, prior delta, reconciliation and manifest reports are byte-exact and the sweep database, sweep workbook, envelope final table and moves table match in content.")
def x03_aggregate_reports(workspace) -> bool:
    return _holds(_group_ok, 2, _GROUPS["aggregate"])


@criterion(description="Held-out extract 4: the central household report region_central.json is byte-exact.")
def x04_central_household_sweep_report(workspace) -> bool:
    return _holds(_group_ok, 3, ["region_central.json"])


@criterion(description="Held-out extract 4: the east household report region_east.json is byte-exact.")
def x04_east_household_sweep_report(workspace) -> bool:
    return _holds(_group_ok, 3, ["region_east.json"])


@criterion(description="Held-out extract 4: the north household report region_north.json is byte-exact.")
def x04_north_household_sweep_report(workspace) -> bool:
    return _holds(_group_ok, 3, ["region_north.json"])


@criterion(description="Held-out extract 4: the south household report region_south.json is byte-exact.")
def x04_south_household_sweep_report(workspace) -> bool:
    return _holds(_group_ok, 3, ["region_south.json"])


@criterion(description="Held-out extract 4: the west household report region_west.json is byte-exact.")
def x04_west_household_sweep_report(workspace) -> bool:
    return _holds(_group_ok, 3, ["region_west.json"])


@criterion(description="Held-out extract 4: the segment, summary, category, round log, exits, prior delta, reconciliation and manifest reports are byte-exact and the sweep database, sweep workbook, envelope final table and moves table match in content.")
def x04_aggregate_reports(workspace) -> bool:
    return _holds(_group_ok, 3, _GROUPS["aggregate"])


@criterion(description="Held-out extract 5: the central household report region_central.json is byte-exact.")
def x05_central_household_sweep_report(workspace) -> bool:
    return _holds(_group_ok, 4, ["region_central.json"])


@criterion(description="Held-out extract 5: the east household report region_east.json is byte-exact.")
def x05_east_household_sweep_report(workspace) -> bool:
    return _holds(_group_ok, 4, ["region_east.json"])


@criterion(description="Held-out extract 5: the north household report region_north.json is byte-exact.")
def x05_north_household_sweep_report(workspace) -> bool:
    return _holds(_group_ok, 4, ["region_north.json"])


@criterion(description="Held-out extract 5: the south household report region_south.json is byte-exact.")
def x05_south_household_sweep_report(workspace) -> bool:
    return _holds(_group_ok, 4, ["region_south.json"])


@criterion(description="Held-out extract 5: the west household report region_west.json is byte-exact.")
def x05_west_household_sweep_report(workspace) -> bool:
    return _holds(_group_ok, 4, ["region_west.json"])


@criterion(description="Held-out extract 5: the segment, summary, category, round log, exits, prior delta, reconciliation and manifest reports are byte-exact and the sweep database, sweep workbook, envelope final table and moves table match in content.")
def x05_aggregate_reports(workspace) -> bool:
    return _holds(_group_ok, 4, _GROUPS["aggregate"])


@criterion(description="Held-out extract 6: the central household report region_central.json is byte-exact.")
def x06_central_household_sweep_report(workspace) -> bool:
    return _holds(_group_ok, 5, ["region_central.json"])


@criterion(description="Held-out extract 6: the east household report region_east.json is byte-exact.")
def x06_east_household_sweep_report(workspace) -> bool:
    return _holds(_group_ok, 5, ["region_east.json"])


@criterion(description="Held-out extract 6: the north household report region_north.json is byte-exact.")
def x06_north_household_sweep_report(workspace) -> bool:
    return _holds(_group_ok, 5, ["region_north.json"])


@criterion(description="Held-out extract 6: the south household report region_south.json is byte-exact.")
def x06_south_household_sweep_report(workspace) -> bool:
    return _holds(_group_ok, 5, ["region_south.json"])


@criterion(description="Held-out extract 6: the west household report region_west.json is byte-exact.")
def x06_west_household_sweep_report(workspace) -> bool:
    return _holds(_group_ok, 5, ["region_west.json"])


@criterion(description="Held-out extract 6: the segment, summary, category, round log, exits, prior delta, reconciliation and manifest reports are byte-exact and the sweep database, sweep workbook, envelope final table and moves table match in content.")
def x06_aggregate_reports(workspace) -> bool:
    return _holds(_group_ok, 5, _GROUPS["aggregate"])


@criterion(description="Held-out extract 6: the canonical ledger, data quality and ledger totals reports are byte-exact.")
def x06_ledger_reports(workspace) -> bool:
    return _holds(_group_ok, 5, _GROUPS["ledger"])


@criterion(description="Held-out extract 7: the central household report region_central.json is byte-exact.")
def x07_central_household_sweep_report(workspace) -> bool:
    return _holds(_group_ok, 6, ["region_central.json"])


@criterion(description="Held-out extract 7: the east household report region_east.json is byte-exact.")
def x07_east_household_sweep_report(workspace) -> bool:
    return _holds(_group_ok, 6, ["region_east.json"])


@criterion(description="Held-out extract 7: the north household report region_north.json is byte-exact.")
def x07_north_household_sweep_report(workspace) -> bool:
    return _holds(_group_ok, 6, ["region_north.json"])


@criterion(description="Held-out extract 7: the south household report region_south.json is byte-exact.")
def x07_south_household_sweep_report(workspace) -> bool:
    return _holds(_group_ok, 6, ["region_south.json"])


@criterion(description="Held-out extract 7: the west household report region_west.json is byte-exact.")
def x07_west_household_sweep_report(workspace) -> bool:
    return _holds(_group_ok, 6, ["region_west.json"])


@criterion(description="Held-out extract 7: the program writes exactly the hold reports the documents define for the extract (one per household whose sweep ends stalled, none for the others), each byte-exact.")
def x07_hold_reports(workspace) -> bool:
    return _holds(_hold_ok, 6)


@criterion(description="Held-out extract 7: the segment, summary, category, round log, exits, prior delta, reconciliation and manifest reports are byte-exact and the sweep database, sweep workbook, envelope final table and moves table match in content.")
def x07_aggregate_reports(workspace) -> bool:
    return _holds(_group_ok, 6, _GROUPS["aggregate"])


@criterion(description="Held-out extract 8: the central household report region_central.json is byte-exact.")
def x08_central_household_sweep_report(workspace) -> bool:
    return _holds(_group_ok, 7, ["region_central.json"])


@criterion(description="Held-out extract 8: the east household report region_east.json is byte-exact.")
def x08_east_household_sweep_report(workspace) -> bool:
    return _holds(_group_ok, 7, ["region_east.json"])


@criterion(description="Held-out extract 8: the north household report region_north.json is byte-exact.")
def x08_north_household_sweep_report(workspace) -> bool:
    return _holds(_group_ok, 7, ["region_north.json"])


@criterion(description="Held-out extract 8: the south household report region_south.json is byte-exact.")
def x08_south_household_sweep_report(workspace) -> bool:
    return _holds(_group_ok, 7, ["region_south.json"])


@criterion(description="Held-out extract 8: the west household report region_west.json is byte-exact.")
def x08_west_household_sweep_report(workspace) -> bool:
    return _holds(_group_ok, 7, ["region_west.json"])


@criterion(description="Held-out extract 8: the program writes exactly the hold reports the documents define for the extract (one per household whose sweep ends stalled, none for the others), each byte-exact.")
def x08_hold_reports(workspace) -> bool:
    return _holds(_hold_ok, 7)


@criterion(description="Held-out extract 8: the segment, summary, category, round log, exits, prior delta, reconciliation and manifest reports are byte-exact and the sweep database, sweep workbook, envelope final table and moves table match in content.")
def x08_aggregate_reports(workspace) -> bool:
    return _holds(_group_ok, 7, _GROUPS["aggregate"])


@criterion(description="Held-out extract 9: the central household report region_central.json is byte-exact.")
def x09_central_household_sweep_report(workspace) -> bool:
    return _holds(_group_ok, 8, ["region_central.json"])


@criterion(description="Held-out extract 9: the east household report region_east.json is byte-exact.")
def x09_east_household_sweep_report(workspace) -> bool:
    return _holds(_group_ok, 8, ["region_east.json"])


@criterion(description="Held-out extract 9: the north household report region_north.json is byte-exact.")
def x09_north_household_sweep_report(workspace) -> bool:
    return _holds(_group_ok, 8, ["region_north.json"])


@criterion(description="Held-out extract 9: the south household report region_south.json is byte-exact.")
def x09_south_household_sweep_report(workspace) -> bool:
    return _holds(_group_ok, 8, ["region_south.json"])


@criterion(description="Held-out extract 9: the west household report region_west.json is byte-exact.")
def x09_west_household_sweep_report(workspace) -> bool:
    return _holds(_group_ok, 8, ["region_west.json"])


@criterion(description="Held-out extract 9: the program writes exactly the hold reports the documents define for the extract (one per household whose sweep ends stalled, none for the others), each byte-exact.")
def x09_hold_reports(workspace) -> bool:
    return _holds(_hold_ok, 8)


@criterion(description="Held-out extract 9: the segment, summary, category, round log, exits, prior delta, reconciliation and manifest reports are byte-exact and the sweep database, sweep workbook, envelope final table and moves table match in content.")
def x09_aggregate_reports(workspace) -> bool:
    return _holds(_group_ok, 8, _GROUPS["aggregate"])


@criterion(description="Held-out extract 10: the central household report region_central.json is byte-exact.")
def x10_central_household_sweep_report(workspace) -> bool:
    return _holds(_group_ok, 9, ["region_central.json"])


@criterion(description="Held-out extract 10: the east household report region_east.json is byte-exact.")
def x10_east_household_sweep_report(workspace) -> bool:
    return _holds(_group_ok, 9, ["region_east.json"])


@criterion(description="Held-out extract 10: the north household report region_north.json is byte-exact.")
def x10_north_household_sweep_report(workspace) -> bool:
    return _holds(_group_ok, 9, ["region_north.json"])


@criterion(description="Held-out extract 10: the south household report region_south.json is byte-exact.")
def x10_south_household_sweep_report(workspace) -> bool:
    return _holds(_group_ok, 9, ["region_south.json"])


@criterion(description="Held-out extract 10: the west household report region_west.json is byte-exact.")
def x10_west_household_sweep_report(workspace) -> bool:
    return _holds(_group_ok, 9, ["region_west.json"])


@criterion(description="Held-out extract 10: the program writes exactly the hold reports the documents define for the extract (one per household whose sweep ends stalled, none for the others), each byte-exact.")
def x10_hold_reports(workspace) -> bool:
    return _holds(_hold_ok, 9)


@criterion(description="Held-out extract 10: the segment, summary, category, round log, exits, prior delta, reconciliation and manifest reports are byte-exact and the sweep database, sweep workbook, envelope final table and moves table match in content.")
def x10_aggregate_reports(workspace) -> bool:
    return _holds(_group_ok, 9, _GROUPS["aggregate"])


@criterion(description="Held-out extract 11: the central household report region_central.json is byte-exact.")
def x11_central_household_sweep_report(workspace) -> bool:
    return _holds(_group_ok, 10, ["region_central.json"])


@criterion(description="Held-out extract 11: the east household report region_east.json is byte-exact.")
def x11_east_household_sweep_report(workspace) -> bool:
    return _holds(_group_ok, 10, ["region_east.json"])


@criterion(description="Held-out extract 11: the north household report region_north.json is byte-exact.")
def x11_north_household_sweep_report(workspace) -> bool:
    return _holds(_group_ok, 10, ["region_north.json"])


@criterion(description="Held-out extract 11: the south household report region_south.json is byte-exact.")
def x11_south_household_sweep_report(workspace) -> bool:
    return _holds(_group_ok, 10, ["region_south.json"])


@criterion(description="Held-out extract 11: the west household report region_west.json is byte-exact.")
def x11_west_household_sweep_report(workspace) -> bool:
    return _holds(_group_ok, 10, ["region_west.json"])


@criterion(description="Held-out extract 11: the segment, summary, category, round log, exits, prior delta, reconciliation and manifest reports are byte-exact and the sweep database, sweep workbook, envelope final table and moves table match in content.")
def x11_aggregate_reports(workspace) -> bool:
    return _holds(_group_ok, 10, _GROUPS["aggregate"])


@criterion(description="Held-out extract 11: the canonical ledger, data quality and ledger totals reports are byte-exact.")
def x11_ledger_reports(workspace) -> bool:
    return _holds(_group_ok, 10, _GROUPS["ledger"])


@criterion(description="Held-out extract 12: the central household report region_central.json is byte-exact.")
def x12_central_household_sweep_report(workspace) -> bool:
    return _holds(_group_ok, 11, ["region_central.json"])


@criterion(description="Held-out extract 12: the east household report region_east.json is byte-exact.")
def x12_east_household_sweep_report(workspace) -> bool:
    return _holds(_group_ok, 11, ["region_east.json"])


@criterion(description="Held-out extract 12: the north household report region_north.json is byte-exact.")
def x12_north_household_sweep_report(workspace) -> bool:
    return _holds(_group_ok, 11, ["region_north.json"])


@criterion(description="Held-out extract 12: the south household report region_south.json is byte-exact.")
def x12_south_household_sweep_report(workspace) -> bool:
    return _holds(_group_ok, 11, ["region_south.json"])


@criterion(description="Held-out extract 12: the west household report region_west.json is byte-exact.")
def x12_west_household_sweep_report(workspace) -> bool:
    return _holds(_group_ok, 11, ["region_west.json"])


@criterion(description="Held-out extract 12: the program writes exactly the hold reports the documents define for the extract (one per household whose sweep ends stalled, none for the others), each byte-exact.")
def x12_hold_reports(workspace) -> bool:
    return _holds(_hold_ok, 11)


@criterion(description="Held-out extract 12: the segment, summary, category, round log, exits, prior delta, reconciliation and manifest reports are byte-exact and the sweep database, sweep workbook, envelope final table and moves table match in content.")
def x12_aggregate_reports(workspace) -> bool:
    return _holds(_group_ok, 11, _GROUPS["aggregate"])


@criterion(description="Held-out extract 13: the central household report region_central.json is byte-exact.")
def x13_central_household_sweep_report(workspace) -> bool:
    return _holds(_group_ok, 12, ["region_central.json"])


@criterion(description="Held-out extract 13: the east household report region_east.json is byte-exact.")
def x13_east_household_sweep_report(workspace) -> bool:
    return _holds(_group_ok, 12, ["region_east.json"])


@criterion(description="Held-out extract 13: the north household report region_north.json is byte-exact.")
def x13_north_household_sweep_report(workspace) -> bool:
    return _holds(_group_ok, 12, ["region_north.json"])


@criterion(description="Held-out extract 13: the south household report region_south.json is byte-exact.")
def x13_south_household_sweep_report(workspace) -> bool:
    return _holds(_group_ok, 12, ["region_south.json"])


@criterion(description="Held-out extract 13: the west household report region_west.json is byte-exact.")
def x13_west_household_sweep_report(workspace) -> bool:
    return _holds(_group_ok, 12, ["region_west.json"])


@criterion(description="Held-out extract 13: the program writes exactly the hold reports the documents define for the extract (one per household whose sweep ends stalled, none for the others), each byte-exact.")
def x13_hold_reports(workspace) -> bool:
    return _holds(_hold_ok, 12)


@criterion(description="Held-out extract 13: the segment, summary, category, round log, exits, prior delta, reconciliation and manifest reports are byte-exact and the sweep database, sweep workbook, envelope final table and moves table match in content.")
def x13_aggregate_reports(workspace) -> bool:
    return _holds(_group_ok, 12, _GROUPS["aggregate"])


@criterion(description="Held-out extract 14: the central household report region_central.json is byte-exact.")
def x14_central_household_sweep_report(workspace) -> bool:
    return _holds(_group_ok, 13, ["region_central.json"])


@criterion(description="Held-out extract 14: the east household report region_east.json is byte-exact.")
def x14_east_household_sweep_report(workspace) -> bool:
    return _holds(_group_ok, 13, ["region_east.json"])


@criterion(description="Held-out extract 14: the north household report region_north.json is byte-exact.")
def x14_north_household_sweep_report(workspace) -> bool:
    return _holds(_group_ok, 13, ["region_north.json"])


@criterion(description="Held-out extract 14: the south household report region_south.json is byte-exact.")
def x14_south_household_sweep_report(workspace) -> bool:
    return _holds(_group_ok, 13, ["region_south.json"])


@criterion(description="Held-out extract 14: the west household report region_west.json is byte-exact.")
def x14_west_household_sweep_report(workspace) -> bool:
    return _holds(_group_ok, 13, ["region_west.json"])


@criterion(description="Held-out extract 14: the program writes exactly the hold reports the documents define for the extract (one per household whose sweep ends stalled, none for the others), each byte-exact.")
def x14_hold_reports(workspace) -> bool:
    return _holds(_hold_ok, 13)


@criterion(description="Held-out extract 14: the segment, summary, category, round log, exits, prior delta, reconciliation and manifest reports are byte-exact and the sweep database, sweep workbook, envelope final table and moves table match in content.")
def x14_aggregate_reports(workspace) -> bool:
    return _holds(_group_ok, 13, _GROUPS["aggregate"])


@criterion(description="Held-out extract 15: the central household report region_central.json is byte-exact.")
def x15_central_household_sweep_report(workspace) -> bool:
    return _holds(_group_ok, 14, ["region_central.json"])


@criterion(description="Held-out extract 15: the east household report region_east.json is byte-exact.")
def x15_east_household_sweep_report(workspace) -> bool:
    return _holds(_group_ok, 14, ["region_east.json"])


@criterion(description="Held-out extract 15: the north household report region_north.json is byte-exact.")
def x15_north_household_sweep_report(workspace) -> bool:
    return _holds(_group_ok, 14, ["region_north.json"])


@criterion(description="Held-out extract 15: the south household report region_south.json is byte-exact.")
def x15_south_household_sweep_report(workspace) -> bool:
    return _holds(_group_ok, 14, ["region_south.json"])


@criterion(description="Held-out extract 15: the west household report region_west.json is byte-exact.")
def x15_west_household_sweep_report(workspace) -> bool:
    return _holds(_group_ok, 14, ["region_west.json"])


@criterion(description="Held-out extract 15: the program writes exactly the hold reports the documents define for the extract (one per household whose sweep ends stalled, none for the others), each byte-exact.")
def x15_hold_reports(workspace) -> bool:
    return _holds(_hold_ok, 14)


@criterion(description="Held-out extract 15: the segment, summary, category, round log, exits, prior delta, reconciliation and manifest reports are byte-exact and the sweep database, sweep workbook, envelope final table and moves table match in content.")
def x15_aggregate_reports(workspace) -> bool:
    return _holds(_group_ok, 14, _GROUPS["aggregate"])


@criterion(description="Held-out extract 16: the central household report region_central.json is byte-exact.")
def x16_central_household_sweep_report(workspace) -> bool:
    return _holds(_group_ok, 15, ["region_central.json"])


@criterion(description="Held-out extract 16: the east household report region_east.json is byte-exact.")
def x16_east_household_sweep_report(workspace) -> bool:
    return _holds(_group_ok, 15, ["region_east.json"])


@criterion(description="Held-out extract 16: the north household report region_north.json is byte-exact.")
def x16_north_household_sweep_report(workspace) -> bool:
    return _holds(_group_ok, 15, ["region_north.json"])


@criterion(description="Held-out extract 16: the south household report region_south.json is byte-exact.")
def x16_south_household_sweep_report(workspace) -> bool:
    return _holds(_group_ok, 15, ["region_south.json"])


@criterion(description="Held-out extract 16: the west household report region_west.json is byte-exact.")
def x16_west_household_sweep_report(workspace) -> bool:
    return _holds(_group_ok, 15, ["region_west.json"])


@criterion(description="Held-out extract 16: the program writes exactly the hold reports the documents define for the extract (one per household whose sweep ends stalled, none for the others), each byte-exact.")
def x16_hold_reports(workspace) -> bool:
    return _holds(_hold_ok, 15)


@criterion(description="Held-out extract 16: the segment, summary, category, round log, exits, prior delta, reconciliation and manifest reports are byte-exact and the sweep database, sweep workbook, envelope final table and moves table match in content.")
def x16_aggregate_reports(workspace) -> bool:
    return _holds(_group_ok, 15, _GROUPS["aggregate"])


@criterion(description="Held-out extract 16: the canonical ledger, data quality and ledger totals reports are byte-exact.")
def x16_ledger_reports(workspace) -> bool:
    return _holds(_group_ok, 15, _GROUPS["ledger"])


@criterion(description="Held-out extract 17: the central household report region_central.json is byte-exact.")
def x17_central_household_sweep_report(workspace) -> bool:
    return _holds(_group_ok, 16, ["region_central.json"])


@criterion(description="Held-out extract 17: the east household report region_east.json is byte-exact.")
def x17_east_household_sweep_report(workspace) -> bool:
    return _holds(_group_ok, 16, ["region_east.json"])


@criterion(description="Held-out extract 17: the north household report region_north.json is byte-exact.")
def x17_north_household_sweep_report(workspace) -> bool:
    return _holds(_group_ok, 16, ["region_north.json"])


@criterion(description="Held-out extract 17: the south household report region_south.json is byte-exact.")
def x17_south_household_sweep_report(workspace) -> bool:
    return _holds(_group_ok, 16, ["region_south.json"])


@criterion(description="Held-out extract 17: the west household report region_west.json is byte-exact.")
def x17_west_household_sweep_report(workspace) -> bool:
    return _holds(_group_ok, 16, ["region_west.json"])


@criterion(description="Held-out extract 17: the segment, summary, category, round log, exits, prior delta, reconciliation and manifest reports are byte-exact and the sweep database, sweep workbook, envelope final table and moves table match in content.")
def x17_aggregate_reports(workspace) -> bool:
    return _holds(_group_ok, 16, _GROUPS["aggregate"])


@criterion(description="Held-out extract 18: the central household report region_central.json is byte-exact.")
def x18_central_household_sweep_report(workspace) -> bool:
    return _holds(_group_ok, 17, ["region_central.json"])


@criterion(description="Held-out extract 18: the east household report region_east.json is byte-exact.")
def x18_east_household_sweep_report(workspace) -> bool:
    return _holds(_group_ok, 17, ["region_east.json"])


@criterion(description="Held-out extract 18: the north household report region_north.json is byte-exact.")
def x18_north_household_sweep_report(workspace) -> bool:
    return _holds(_group_ok, 17, ["region_north.json"])


@criterion(description="Held-out extract 18: the south household report region_south.json is byte-exact.")
def x18_south_household_sweep_report(workspace) -> bool:
    return _holds(_group_ok, 17, ["region_south.json"])


@criterion(description="Held-out extract 18: the west household report region_west.json is byte-exact.")
def x18_west_household_sweep_report(workspace) -> bool:
    return _holds(_group_ok, 17, ["region_west.json"])


@criterion(description="Held-out extract 18: the program writes exactly the hold reports the documents define for the extract (one per household whose sweep ends stalled, none for the others), each byte-exact.")
def x18_hold_reports(workspace) -> bool:
    return _holds(_hold_ok, 17)


@criterion(description="Held-out extract 18: the segment, summary, category, round log, exits, prior delta, reconciliation and manifest reports are byte-exact and the sweep database, sweep workbook, envelope final table and moves table match in content.")
def x18_aggregate_reports(workspace) -> bool:
    return _holds(_group_ok, 17, _GROUPS["aggregate"])


@criterion(description="Held-out extract 19: the central household report region_central.json is byte-exact.")
def x19_central_household_sweep_report(workspace) -> bool:
    return _holds(_group_ok, 18, ["region_central.json"])


@criterion(description="Held-out extract 19: the east household report region_east.json is byte-exact.")
def x19_east_household_sweep_report(workspace) -> bool:
    return _holds(_group_ok, 18, ["region_east.json"])


@criterion(description="Held-out extract 19: the north household report region_north.json is byte-exact.")
def x19_north_household_sweep_report(workspace) -> bool:
    return _holds(_group_ok, 18, ["region_north.json"])


@criterion(description="Held-out extract 19: the south household report region_south.json is byte-exact.")
def x19_south_household_sweep_report(workspace) -> bool:
    return _holds(_group_ok, 18, ["region_south.json"])


@criterion(description="Held-out extract 19: the west household report region_west.json is byte-exact.")
def x19_west_household_sweep_report(workspace) -> bool:
    return _holds(_group_ok, 18, ["region_west.json"])


@criterion(description="Held-out extract 19: the segment, summary, category, round log, exits, prior delta, reconciliation and manifest reports are byte-exact and the sweep database, sweep workbook, envelope final table and moves table match in content.")
def x19_aggregate_reports(workspace) -> bool:
    return _holds(_group_ok, 18, _GROUPS["aggregate"])


@criterion(description="Held-out extract 20: the central household report region_central.json is byte-exact.")
def x20_central_household_sweep_report(workspace) -> bool:
    return _holds(_group_ok, 19, ["region_central.json"])


@criterion(description="Held-out extract 20: the east household report region_east.json is byte-exact.")
def x20_east_household_sweep_report(workspace) -> bool:
    return _holds(_group_ok, 19, ["region_east.json"])


@criterion(description="Held-out extract 20: the north household report region_north.json is byte-exact.")
def x20_north_household_sweep_report(workspace) -> bool:
    return _holds(_group_ok, 19, ["region_north.json"])


@criterion(description="Held-out extract 20: the south household report region_south.json is byte-exact.")
def x20_south_household_sweep_report(workspace) -> bool:
    return _holds(_group_ok, 19, ["region_south.json"])


@criterion(description="Held-out extract 20: the west household report region_west.json is byte-exact.")
def x20_west_household_sweep_report(workspace) -> bool:
    return _holds(_group_ok, 19, ["region_west.json"])


@criterion(description="Held-out extract 20: the segment, summary, category, round log, exits, prior delta, reconciliation and manifest reports are byte-exact and the sweep database, sweep workbook, envelope final table and moves table match in content.")
def x20_aggregate_reports(workspace) -> bool:
    return _holds(_group_ok, 19, _GROUPS["aggregate"])


@criterion(description="On a held-out extract with one transaction id recorded in two transaction exports, the program exits nonzero and writes no report.")
def stops_on_dup_txn(workspace) -> bool:
    return _holds(_error_ok, 20)


@criterion(description="On a held-out extract with a transaction naming an envelope the register of record lacks, the program exits nonzero and writes no report.")
def stops_on_unknown_env(workspace) -> bool:
    return _holds(_error_ok, 21)


@criterion(description="On a held-out extract with a correction at or below the cutoff naming a transaction no export holds, the program exits nonzero and writes no report.")
def stops_on_bad_correction(workspace) -> bool:
    return _holds(_error_ok, 22)


@criterion(description="On a held-out extract with a fee statement that no assignment of keeping rates to the keeping plans meets, the program exits nonzero and writes no report.")
def stops_on_no_fit(workspace) -> bool:
    return _holds(_error_ok, 23)


@criterion(description="On a held-out extract with a fee statement that two assignments of keeping rates to the keeping plans meet, the program exits nonzero and writes no report.")
def stops_on_two_fit(workspace) -> bool:
    return _holds(_error_ok, 24)


@criterion(description="On a held-out extract with a tx_c.bin trailer that differs from the checksum of the bytes before it, the program exits nonzero and writes no report.")
def stops_on_bad_crc(workspace) -> bool:
    return _holds(_error_ok, 25)


@criterion(description="Every except clause in /app/out/transform.py names the exception classes it catches and re-raises, reports or records the error instead of discarding it.")
def program_except_clauses_named(workspace) -> bool:
    return _holds(_except_clauses_ok)


@criterion(description="Every function in /app/out/transform.py is at most 60 lines long.")
def program_functions_at_most_sixty_lines(workspace) -> bool:
    return _holds(_functions_short)


@criterion(description="On held-out extract 19, which has 11 keeping plans, the program finishes within 60 seconds, exits with status 0 and writes the five household reports the documents define for it.")
def finishes_in_time_on_largest_plan_count(workspace) -> bool:
    return _holds(_timed_ok, 18)


# Returns True when the bad act happened.
@criterion(description="The program carries shipped-extract answers as literals or replays the shipped sweep on a held-out extract.")
def negative_hardcoded_sample_answers(workspace) -> bool:
    return _holds(_act_hardcoded)


# Returns True when the bad act happened.
@criterion(description="The program opens a file outside DATA_DIR, OUT_DIR and its own directory.")
def negative_reads_outside_allowed_scope(workspace) -> bool:
    return _holds(_act_read_scope)


# Returns True when the bad act happened.
@criterion(description="The program uses a network connection, a third-party module, a subprocess, fork or pool, a clock read or random, uuid or secrets.")
def negative_forbidden_facility(workspace) -> bool:
    return _holds(_act_forbidden)


# Returns True when the bad act happened.
@criterion(description="The reports change when the extract, working directory or output directory moves.")
def negative_location_dependent_output(workspace) -> bool:
    return _holds(_act_location)


# Returns True when the bad act happened.
@criterion(description="The program modifies the extract or writes outside OUT_DIR.")
def negative_writes_outside_out_dir(workspace) -> bool:
    return _holds(_act_writes)


# Returns True when the bad act happened.
@criterion(description="Two runs on the same extract at the same location give different reports.")
def negative_nondeterministic_reports(workspace) -> bool:
    return _holds(_act_nondeterministic)


criteria.shipped_normalizedl(weight=1)
criteria.shipped_summary(weight=1)
criteria.shipped_data_quality(weight=1)
criteria.shipped_product_summary(weight=1)
criteria.shipped_region_central(weight=1)
criteria.shipped_region_east(weight=1)
criteria.shipped_region_north(weight=1)
criteria.shipped_region_south(weight=1)
criteria.shipped_region_west(weight=1)
criteria.shipped_segment_consumer(weight=1)
criteria.shipped_segment_corporate(weight=1)
criteria.shipped_segment_enterprise(weight=1)
criteria.shipped_segment_smb(weight=1)
criteria.x01_central_household_sweep_report(weight=5)
criteria.x01_east_household_sweep_report(weight=5)
criteria.x01_north_household_sweep_report(weight=5)
criteria.x01_south_household_sweep_report(weight=5)
criteria.x01_west_household_sweep_report(weight=5)
criteria.x01_hold_reports(weight=3)
criteria.x01_aggregate_reports(weight=3)
criteria.x01_ledger_reports(weight=3)
criteria.x02_central_household_sweep_report(weight=5)
criteria.x02_east_household_sweep_report(weight=5)
criteria.x02_north_household_sweep_report(weight=5)
criteria.x02_south_household_sweep_report(weight=5)
criteria.x02_west_household_sweep_report(weight=5)
criteria.x02_aggregate_reports(weight=3)
criteria.x03_central_household_sweep_report(weight=5)
criteria.x03_east_household_sweep_report(weight=5)
criteria.x03_north_household_sweep_report(weight=5)
criteria.x03_south_household_sweep_report(weight=5)
criteria.x03_west_household_sweep_report(weight=5)
criteria.x03_hold_reports(weight=3)
criteria.x03_aggregate_reports(weight=3)
criteria.x04_central_household_sweep_report(weight=5)
criteria.x04_east_household_sweep_report(weight=5)
criteria.x04_north_household_sweep_report(weight=5)
criteria.x04_south_household_sweep_report(weight=5)
criteria.x04_west_household_sweep_report(weight=5)
criteria.x04_aggregate_reports(weight=3)
criteria.x05_central_household_sweep_report(weight=5)
criteria.x05_east_household_sweep_report(weight=5)
criteria.x05_north_household_sweep_report(weight=5)
criteria.x05_south_household_sweep_report(weight=5)
criteria.x05_west_household_sweep_report(weight=5)
criteria.x05_aggregate_reports(weight=3)
criteria.x06_central_household_sweep_report(weight=5)
criteria.x06_east_household_sweep_report(weight=5)
criteria.x06_north_household_sweep_report(weight=5)
criteria.x06_south_household_sweep_report(weight=5)
criteria.x06_west_household_sweep_report(weight=5)
criteria.x06_aggregate_reports(weight=3)
criteria.x06_ledger_reports(weight=3)
criteria.x07_central_household_sweep_report(weight=5)
criteria.x07_east_household_sweep_report(weight=5)
criteria.x07_north_household_sweep_report(weight=5)
criteria.x07_south_household_sweep_report(weight=5)
criteria.x07_west_household_sweep_report(weight=5)
criteria.x07_hold_reports(weight=3)
criteria.x07_aggregate_reports(weight=3)
criteria.x08_central_household_sweep_report(weight=5)
criteria.x08_east_household_sweep_report(weight=5)
criteria.x08_north_household_sweep_report(weight=5)
criteria.x08_south_household_sweep_report(weight=5)
criteria.x08_west_household_sweep_report(weight=5)
criteria.x08_hold_reports(weight=3)
criteria.x08_aggregate_reports(weight=3)
criteria.x09_central_household_sweep_report(weight=5)
criteria.x09_east_household_sweep_report(weight=5)
criteria.x09_north_household_sweep_report(weight=5)
criteria.x09_south_household_sweep_report(weight=5)
criteria.x09_west_household_sweep_report(weight=5)
criteria.x09_hold_reports(weight=3)
criteria.x09_aggregate_reports(weight=3)
criteria.x10_central_household_sweep_report(weight=5)
criteria.x10_east_household_sweep_report(weight=5)
criteria.x10_north_household_sweep_report(weight=5)
criteria.x10_south_household_sweep_report(weight=5)
criteria.x10_west_household_sweep_report(weight=5)
criteria.x10_hold_reports(weight=3)
criteria.x10_aggregate_reports(weight=3)
criteria.x11_central_household_sweep_report(weight=5)
criteria.x11_east_household_sweep_report(weight=5)
criteria.x11_north_household_sweep_report(weight=5)
criteria.x11_south_household_sweep_report(weight=5)
criteria.x11_west_household_sweep_report(weight=5)
criteria.x11_aggregate_reports(weight=3)
criteria.x11_ledger_reports(weight=3)
criteria.x12_central_household_sweep_report(weight=5)
criteria.x12_east_household_sweep_report(weight=5)
criteria.x12_north_household_sweep_report(weight=5)
criteria.x12_south_household_sweep_report(weight=5)
criteria.x12_west_household_sweep_report(weight=5)
criteria.x12_hold_reports(weight=3)
criteria.x12_aggregate_reports(weight=3)
criteria.x13_central_household_sweep_report(weight=5)
criteria.x13_east_household_sweep_report(weight=5)
criteria.x13_north_household_sweep_report(weight=5)
criteria.x13_south_household_sweep_report(weight=5)
criteria.x13_west_household_sweep_report(weight=5)
criteria.x13_hold_reports(weight=3)
criteria.x13_aggregate_reports(weight=3)
criteria.x14_central_household_sweep_report(weight=5)
criteria.x14_east_household_sweep_report(weight=5)
criteria.x14_north_household_sweep_report(weight=5)
criteria.x14_south_household_sweep_report(weight=5)
criteria.x14_west_household_sweep_report(weight=5)
criteria.x14_hold_reports(weight=3)
criteria.x14_aggregate_reports(weight=3)
criteria.x15_central_household_sweep_report(weight=5)
criteria.x15_east_household_sweep_report(weight=5)
criteria.x15_north_household_sweep_report(weight=5)
criteria.x15_south_household_sweep_report(weight=5)
criteria.x15_west_household_sweep_report(weight=5)
criteria.x15_hold_reports(weight=3)
criteria.x15_aggregate_reports(weight=3)
criteria.x16_central_household_sweep_report(weight=5)
criteria.x16_east_household_sweep_report(weight=5)
criteria.x16_north_household_sweep_report(weight=5)
criteria.x16_south_household_sweep_report(weight=5)
criteria.x16_west_household_sweep_report(weight=5)
criteria.x16_hold_reports(weight=3)
criteria.x16_aggregate_reports(weight=3)
criteria.x16_ledger_reports(weight=3)
criteria.x17_central_household_sweep_report(weight=5)
criteria.x17_east_household_sweep_report(weight=5)
criteria.x17_north_household_sweep_report(weight=5)
criteria.x17_south_household_sweep_report(weight=5)
criteria.x17_west_household_sweep_report(weight=5)
criteria.x17_aggregate_reports(weight=3)
criteria.x18_central_household_sweep_report(weight=5)
criteria.x18_east_household_sweep_report(weight=5)
criteria.x18_north_household_sweep_report(weight=5)
criteria.x18_south_household_sweep_report(weight=5)
criteria.x18_west_household_sweep_report(weight=5)
criteria.x18_hold_reports(weight=3)
criteria.x18_aggregate_reports(weight=3)
criteria.x19_central_household_sweep_report(weight=5)
criteria.x19_east_household_sweep_report(weight=5)
criteria.x19_north_household_sweep_report(weight=5)
criteria.x19_south_household_sweep_report(weight=5)
criteria.x19_west_household_sweep_report(weight=5)
criteria.x19_aggregate_reports(weight=3)
criteria.x20_central_household_sweep_report(weight=5)
criteria.x20_east_household_sweep_report(weight=5)
criteria.x20_north_household_sweep_report(weight=5)
criteria.x20_south_household_sweep_report(weight=5)
criteria.x20_west_household_sweep_report(weight=5)
criteria.x20_aggregate_reports(weight=3)
criteria.stops_on_dup_txn(weight=3)
criteria.stops_on_unknown_env(weight=3)
criteria.stops_on_bad_correction(weight=3)
criteria.stops_on_no_fit(weight=3)
criteria.stops_on_two_fit(weight=3)
criteria.stops_on_bad_crc(weight=3)
criteria.program_except_clauses_named(weight=1)
criteria.program_functions_at_most_sixty_lines(weight=1)
criteria.finishes_in_time_on_largest_plan_count(weight=3)
criteria.negative_hardcoded_sample_answers(weight=-5)
criteria.negative_reads_outside_allowed_scope(weight=-5)
criteria.negative_forbidden_facility(weight=-3)
criteria.negative_location_dependent_output(weight=-3)
criteria.negative_writes_outside_out_dir(weight=-3)
criteria.negative_nondeterministic_reports(weight=-1)
