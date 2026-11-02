"""Checks for the 5048c412-d327-5667-8375-624261697644 task.

Expected reports are derived here, independently of the reference solution, from the embedded shipped extract and
from held-out extracts that this file generates from fixed seeds in the shipped layout. The delivered program is run
as a subprocess under an unprivileged uid through an audit wrapper; nothing it defines is imported.

Negative checks return True when the bad act happened (the weight is then subtracted).
"""
# pyright: reportUndefinedVariable=false
from __future__ import annotations

from rewardkit import criteria, criterion

_SHIPPED_DATA: dict[str, str] = {
    "basin_cfg.ini": "eNqLLk5NLM7Pi+XKSUxKzVGwVTAyMDLTDTbmKkotyyzOzM+LTy4tyU9LA8oYmnEBAGTVDpM=",
    "bs_map.xml": "eNqdz8EOgjAMANA7X7H0jgIaAoSNg9GjFzSe51xkiduSdRj9e4EDgYMHuLVp+9qW1Ue/yFs6VNZQiDcREGmEfSjzpHC9nMIMKhaUQheCe9FoaTySbsZgITSF1pnizlGZkLe+sU7576QRCEqOPZxESRrWO2ABITOMdLskhUMeA+sLA8Zq22nldsyHcJz5i8T7KXKT6JcbWTo1jnyNkc/uOFu35pl0yTPzHFnwA30Mnr8=",
    "cfg_reference.md": "eNqNVcFu40YMvfsrCOSSALJgb9AW2D2l7S4QYNMETYH2phlLlDQbaUaYGcXx3/dxRnadZLHoTeaQj+TjI31BD9rrkSN70rYhfPWuWdfORm0sjJ5b9mxrXq0uLming7FV3XalsWa1urF0+8cttWbgkh65jsZZUoF1cFZR74YmkBr0jgdFl7Fnyk+UTLT3Jka2ZGx0yDM5H8NVqkJ5fjYBYFU9R9e2iNbJjzv2n4DCpBpTx6rTc2dsF8qxUVcl/YUUOz1oW8NI07GzQK4l1nWf6yftGWAUk7cY3MRexzcxUe8GlkgV6urpQ9m4+kWViYa7xBKdWAqrlaQeT+YQtY0p7XnX5nnJ69HAf8GpZdito2mAaR35JSZSP6bwnnUDqDZwXIqCs8JX1V+XL0N4UUXyA+IzH9A80+BCILTEIfmOsRJLOTWgUrKlquqeRymuG1mKPdp/QIlgvSbjVRlkgEJ75592zj0dKb5vW4OS7ieM+p+7r/Q4eTQUeuaIX63zo47C1Off7m7W17/8XNKfbk/b08ySZ4YWJthDasmkMieKOhAb3lEFZOJn9gdqvN4DBmP/CJKGebR0s6gzESEvJzVqGIX/vYk9xb2jhmsz6iHQpdqUm40iqFVt5SuLdUH89V0B6H/kTg8meg6FMIOcTHYed+wLsniLIgnsAhoG+E+bROmraaW+neX1pDsm0D7LtI7cPvz+5YzB28d7uv6w2WzW25JuMdIUE3q3D6eJNzNKWHosBBiytHxS6tED03/1IEiFZJXZiSqcl0mg2jM95GLf1vh2/n8jdPKu5gCddd+VQJHSSJk6bRPwPLDgNFukle1aZvcOzEKrYdJIKLPBSjm4+TNzEh+ZmBnaueZwlAJmndYLs0rCSwo4io682+cD0xoUUGRzI/sga4QVVPWgQ8j7pZatgrlHF0Iz4hOr2T9DBUZ3TfG/LlEh7B6TJmfJ2ehxgneFsDrnUxPi5WAvlXgHzqrd3HSyKmJ6W1ECKxILkjifp+XYhnyCUJaVtyUdLelEXpdbWYjtZnNVLErJ6XGyaXLBxHz1EtrV6cikqihX9V3PfGgfvHH+7KRDCaP2B8hukpcqv3D5Lf3hmEXm2Qm5MEc/GD5H8LPFqrsIPp94yleidiPYNnKj89bLMZ29FxHDPyulNd2MPaZae2BDWHrGtcfROCSM85h878vVvzYAmEg=",
    "dict_gaugings.md": "eNp1VsFu4zYQvesrBsihW8BRk6IFiuRUtE3RHnaBbe8WLY0k7sqklqTsNeCP7+OQkqVseogljjhvhm/eDHNHf6qp06YjZRpyfNJeW0ONrgOeyl2K4u5u2cNfR+uCL4pfqcsm21LomTwrDz/tgVFb13BD2mC/qsNwIWt43hh6x7x4Z8CS/sWnvCCjjpxA40urT/gBjkdWbcuODSCfiuJKL7DSlaru616VtT9VeXEow21Rl5+Q2YBlcb2/v9/8AWPORDeyP632uknu+SkPbB50zaZmqm3D0Z7XVX6vtjY4tM4eyQcVyVy8onHvg5Ht0ziyi2+tdj6QDnyMVFVsGp8wgv0GIdjFf7Dn5O/BO0r4BoBn48VNXsSrceps9kvsvD5cokOx4hP1rO3xqO49j8qpgLKe1DCxJ+Xp48tv9NPjLw/UcKsNbKjZcUdnHXpS1LNq2IEyw8/Iyi/hgVm1ZzD6Lta4VkYN+HVOA/yMEC6xFj9u6NMGTIiEFkJ25F+bqHF8/n5HFbScQ2xQ5DNZR5XREMU7w0gXMcVeruWDPIM6rE7+vwfbsKn9N6l/B+liC40WZ/BPVD1WSPChkjQeyp+rcqvU3g6Nl6b5+58P78kePjGEPr4VNJZMCEW4CBpsQs3HqlJnSSOtlK6QqnKyMBTOdm69XfQNZyg4fogJpA87OjhWn9PJkoncNLAvZTz8fjtcUfxlwFGOtRMHx57dyWpA9yoI0+QxJKCYxxUxMoHifisFeXimc8+G1gXaEau6X5x/+DHF/5jHFqJX7rQfbFeOuYKjHvl1CWOMXERo8sv11vRXJWPvKhqPVcFngVFI0esQRxEy5Y7djiajv0xCVARE0Of0Iq2gHJOxAQpAqjILE1YcjQ7AKVCqXe6LWDaw1FTP1Fq3mCNmlRJKmaR2zmFXvYpwuSkike0CJ/sEIPrzcQwX0PbBYC7P896DagvQ23lDTOfAmC65hPliqKdg2zYKaLiU9IJNUpFNveVjFNfidaNddz1jzKVAIoc47ZOwZoE2XOtma0MHGQ7ST/wEDmZylggdSrNFEXDZlghRMx2Lj+OjfeVV0u1mM/aNk6RsPzOPPt97Ugw05NwWcv35CLR2kht23YLp7HPn5Zave2U64KOUfcxG1P0eB8+OEHhsZ7OyvLqAo+5W5/Hba3e+YZN40JALqTuK5ECpi+PALUQwhZL+OLG7rIPiTpjQ6xgQaVAc1KBMPf8TMVsH6yGkWvbKYf4DUC/9Bg==",
    "dict_register.md": "eNqNV01v3DYQvftXEPAhWUAWWgQ51D6laG9pizYB2ttqJFESa4pUSGrX/vedGVIStbtGejG8/JiPN28eR/fiL9krH6QTrWqCsgbc693d/f22DnMYrFMBl78OUrirddFZJ+RJulfc9NKdrHKigyaI2ctWKCNq0GAaZXqhvAhoxAcgX5uxFgLU4KWofDDHxjpZ+m9aBVmJYHuJd5w4qzDw7U5p6YUKZO1fqww6Cba8cRX3wYgvf37GX+LD5oQMlOIr1JodciyVGKxuvbAGc7RnMaHHLZ3Vd2P1PBrPzirxPsiXUOxSamwrD8Vq9mhglOngAaNpRdVAaIZRmrC7v65GC2t4C0THUQZYgmSHEjz601BLzYZpkSJv7IxWbLelVt7dfdqSeeexIB7LkooRf4QBgqhqfxxhKl9GXYlenRBmKi5bzq6vsWKUdI3wJGv//PZZsCkpKG0/QYMZzM48so+HlTKPqwVfPTLkOSpSSwaCSrAuF3kNWkl+VMA60I9KQAhO1TOWeUEiZkVh0FHA1GihEs2gdLu4KJnqf0zSEDl9sA56eQmW3W9TouQZmeZkE5B8WBkmC7R0bNJzxBXpNo9Yh85LLgdf2tLBqEbZAzIVnWEg1cv5SMn4svEnpMaA9tBs1cPcy6OxBTHukKrCMMwYAMLEB4SZxxqPo5/YijkfqUwyhcm1qmx99B/KWq20T9H7YskL73oG08lJYx25WE+cRO9gHMEREOQl9njlJ9kc2Uc5tlUp9iDuMUrMO4GeJYUcCRb30Ll17QrYjSSfxHmQkWZZTjGPEfufuGxiI+9tRi4jYaOd2HgafEgxjJQIG8PT0i1hJitXXfQWAxJBdouFmA2qlr8dNWSoc5Qobi0ji7/xZy27mBe2/exO8pV3H2nBXCIJITNW4O1ihQtNgCPlQIaALhbkCam1uTQa9tF7wfXHQ+nCcgiW7XT/bQSJBVlmMSXoKPuLXAg0Y4OAadJKthcXyWKLCFJRYE94Dgdyli7VdjIoR+S8ge9O0RAf69/op2QXrZBY/MqttTbxwuvYPgJ6UAah2Mk5CcjZRDGIfXipC5BpP8c6zjqoSXM9P2YiITpnR/Hw00d87gT+VaZBrUE9KMXvNqIeUyf+PaVXKWpWQrpTL/xyRt37sttEBfKnY/z/QoIwu2Yo4pZsj0irpC6+CDaAPuJzcbjxfi43BBt4XJqpGViViksOXD+kPhOHZnjnt5qh9MgJHBOqfhXVU1Vsj2A6vLrnIKMi3dpZpxIuS2yJveb7RY42/wVmSYRsRUv1xYrsC/fjD7m8i8gcfp7BOZUk3NPzlKW+YVHGaSvnCgeBwoYjg6PpCpIiEOLgveoNU4gZteMYxib3xOVaUX6QdUFsr/OgsD5yDTcBkkLjGpfibxIUY3O3IzxjUts9Oknqc6HIrZU+JrukUWNRnhehTeOgmzW/iUjSX+RkSdEmxIwoijPeqJyzLnI0Nff0ugSaBkKaP/3GYLxW5BNZwdNAkcSZ+Hs1soE+w6vHgGecwx6+zRapVnAvLFcyLU+rB/ynQ0QH2WYy09NYrUVLmVCD0DLiTbTxDR7FZJ+IPZxW4ggNdj3f3+Zs3CRUd0XbnyB0SUZLfuFraJ7n6a1xIkvkEGFsF6gZzF1ifpnrmLEIDHOA3pP81taAV98ICYzs5WtV1y1v8I0Li63sRm+RXSbS4mce70ZJIu0HNS0fJ6s8cBvEIXBplGw3Kn4kAe5hK/dDKks+ovn4vPA50g/+ZzcSpqfr/2lGuf+yYpbjo0KCmKuesA2+RcSUhofXsP9QuZrmOqu1PfvdbPb+Yh47RHm8ng0RpdTbRDyNkfnIhn1E3XUUn/ilpIwjmhU9TxVVugq22t9fXvfvWb2lBjFybyO74cJrONu8sPgxZHEPJS/yi6SJq4bg/we50mG3",
    "glossary.md": "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",
    "gx_a.csv": "eNptj7sOwjAMRXe+JUi14zw88hILEwywIQShqgRBagv8PjFNpCIxneGe3OvUp2fdxPrYXNStOYd4DuraPu7Hro+qf3zRhdiFyfoAhIbUfkMAS7XdTZ0jARGo2NySYKAybiRIkgBI6vq+iMBM0oAVzUqSi0oDohWBaS6J5kpgk9eGVxLQg/ejCY1a4Blzg7MInASv/ep7A5gyMTQwyJu/DcORaBzDSJAkgb3JExq0FYGtXZTrEkzaHSYcoTMjQZLs5QYk/fNNgPJbET4Y7mfd",
    "gx_b.tsv": "eNplzbEKg0AMBuA5vkshuVw8MwqCS6d2qFspWoogKkLx9ZvcdNAlf8hHks88wTKP8N339wHLdlqdjte5PvOk6gdqhAke14Cxhdv9oo14EEYgYwlqXcGaPJg5MwcJYhyJusxYl6yokv7Zj6BvJ47lb1b0EFLjH5ntK3Y=",
    "gx_c.jsonl": "eNqd0s2KwjAUBeC9TyFZj9D7kzTXnTrDbFzpQkFEtA1YkA44wjCI724CVUlDobgLN+HjcG6uqjzv/+rd4V+Nh6p21eXozupjqFxd/vrRRi2WIwIII3/SIGrrj1UZnn+vJTeI4e5UFa4uXJiu5pbsl7oNrpF9+WmzkpmGFeCIxZy1TVjMeJKwHZGD2NiSxzawSSOj8LRHZMAHy6AjFghzSlgxZtaDJaKOJsiXBO8WbAUbFrKYFRatE5YBPvsWTPiMbNtNGOZ3C359NYOtyCBk+kVO2bCtZm8MEasz73Z9tTtals5I",
    "layout_reports.md": "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",
    "lc_register.json": "eNqr5lJQyslMTs1LTi1WslKI5lJQqAZiuCBQTCncx8LYwlVJByxenJyRmgsWDnbWNTeBiqYkloDFjAyMzHQNLIFICSheq4PdOBNDQxdsxlniNM4Un3GWZmbOWI0zxWqcha6xIT7jjCxNnLAZZ2GJwzgj/MYZmDhiM87YGJdxBmDjuBRiuWq5ALLfXUU=",
    "lr_depot.csv": "eNplykEKgCAQQNG9ZxkhZ5F6GjEbYmDUUOv8uSyCv3r8TkemMqDRzZ32UAu0OChkFmGVas7UEkcBXHDVi5mB/7vVBgG9Oq9NOL1n477oNM7Tqgd+nSOE",
    "mt_loss.pdf": "eNpTDXBx0zXUM+EyVDBQyE/K4rKxUdAPqSxIVdB3TixJzMlPV9APSExPLVYwAioIUrCz40rNSwEpNMLQAFGn752ZUqwQbQxSHgs0Jb80r0TBEEmjMVaNILIoFagUYo++b2pKZqJTfoVCtAFQwMzQSMHc0ghsXl4JUFmxgglEXVBqcX5pUTLQYpB5bkBZCMNQwRTqYAiC2W6CZLtPal56SYaCoakZUENmTklqEZDOSSxJdUlNzk9JBekqLilKTczlqrhV2nea65CBgOv3z6KbBVdF5CiZrRON3Wn8W+jyRpdPE/x0f3x3a2laUCDO/H3Ow3cma/qYXFt/cXktWvX5atOEFf4Bb4JlXmYuUv3SKVltLKA/8WRBl4Z25PTnX2W+8n5l4lqmFyCzYflFw62+bvechOd8z1uUw9VY9brnv80KFz6uj/IBqfOUX3PusNe7d1O/+vPuO9OMZgdXXjBoFm/idQwB+QzqTKgfTTFCGBwu+sGlSSVgLkjQUEHfKbE4FSLjkZpTllqSmZyIFFIVRalpXMCg5zKAAwUzU1NjU4U0BYSYpQJEJg8hZmqBIWZoaIohZmRiiCFmYoZkXklRYmZOahHYG8GZVakKwGgKys8HpSZoUiwuSSwqAbvT1NiSS1XV1d+NCwDaROBl",
    "ob_backup.csv": "eNodzksKwzAMBNC9z6KF9bE+J/AxQiAhFNoUCr1/x909hhmha/9e53a/6XPux+O+ttezTR7hxEO4TeEyYhcDNRW03qYqKwl3pCaSxFWL5oxUHMzKNUuw+poF0qEpJGrRpqt2Egkci6626IuOAgcKEfhB+lCw/rPVzfIijo7PKscAg9sPQdgpbQ==",
    "ob_s3.bin": "eNoBgwB8/09CUzMBMjAyNi1TMwAYExCEqB8XGLqoBBYM8Y8CUh5gATxCJn+oHT0AG5ayIRAjCbcHgx0pHy4SEyIPFglPS4oKgQUVEyeOASMErhsTJn9aIAOUICAD2iAUFQboAxEfLi4CBijGGBIGKE8UG3qCC1YGKLUMKgMIkuAYERFt0AiTeGfZ83cgCw==",
    "prior_balance.json": "eNqdjz0PwiAQhnd+BWHWRKht1d3VpYNjQ1tUIoLhwJg0/e9C8SNNXHR83vfuyV2PMCYNB6mBbHAfKPCWg3tTYHGXkQk4rpToyOxVWON1FxdpNkZDasjOWHf6Zmi44rr9qmDLiaIy/mcFLSeKvfj3DfSUEGUA6rOqnQk7YSBf0XKdjRUIDkZHH1uwYl4xkmLjbStifLXiJo0HnC6W+oit12nKWa7hIKwVXX356GlR5mhAD9aSaEk=",
    "rv_log.psv": "eNpNjksKwzAMRPc+jSX5e4JeobsSGtcYgkPrxt3o8LUgAS/nzWhGLb05L0cuNT/KysvzW/bKfdmOpAD5drcYteGWaktcy6YgDhh1tH6CCAMSWrRzUpgnA9z3Ua2kDQOEcGorPpC7/DC0N+ivjtdvVSAhCJZgXiP5S0Okec1JkpxxJ/ykrlAgRe3m8z+obFGi",
    "sc_k2.docx": "eNrVV09v0zAUXylwGBISYjcuVq5T6/7bxqq2k9iGVE0aFRvigKbiOm4bLbEj21nXG1+CC2funJH4ABz5BuxrcOM56Z81bcfSriBSxWlsv9/7vd9zXpzGUfr+xlp4vK+dfW///PEltbZmzqfQ9W5fcM24bp72fabOspeeW9mDBl0wqRzBq1Y+m7MQ41TYDu9UrTenLzPPLaQ04TZxBWdVq8+UtVdbr4QQCIy5qlpdrf0yxop2mUdUVviMw0hbSI9ouJUd7BN6TjoMF3K5bUwjGhltMKxa5YC1SeBqdHgJ3RERyVxloQFf46tqEd93HUo0jOMLbse8ZAYesmAZzlFdx1ebMMHCMz2YkfkOBnavQBnp2Aw1iNTHxINZuCekjW1BAw8sszfDzOAp2m2HspG9QfOloEwpkNxzs6MRjzh8yB+HctfWGxP5LdeffdiE3JrzEXQ1jWrYKKAWzuvr6/ItmN+JFEB+r2Oiug3Zrdt5C0Vy/Rk7UuxgoMsMF7EZgExkh+mqNZ0qo+VEiHFNP377dbUDYprzCXRNQSysbK88hIlkLfduE3x8fUThm7VhDWA8ehscj8jzwM9Q4fkQfMtxHd0PsYYwvXxpCsdzqBRKtHUW7AYqR+u/kMvnwn9m+Q94LJpLGOwOQVqkagWSwxXCzZBAd4UEpmXCudBR1izk0XK9w4UkLRf0BeKoRWCZ9cotYffN1TeNNI2unQTwPPZRyIkh6hKloHCJNtJdhkI3aOSmgo2FaWXYhji65YaXCI/G8SPgGZZ4OHvaJmSRzESxjlFsvhEeUZxD9GQ/Uygkc9qR5GK2LDcY+UEL6t9yRHe3/gJRWNMek9Qh7nJkn+8mFcjzmf1vuBaL/5Gwu6XVC3sXq3UnIU/PuVwRTTwqV9eNX4RVDqqxhArKO8gnErYyGl5hixS8sGYmY28TzwfHTWBAbyxiM0MH0vCCTVhipQi43WwFNmwElsjusZC6m8zzdi7h/GTTi6VlFqsIkoazVVhtOPklwnnLlF5tchI+2cWdJaI5JEmjKSWMpnjn0YwLjmJUNyQOu6J9GB7veM0uO3VvIz3/23R4fE6tzf5SjQPEP37GAFepiU+huGF8hz82LKVn7PcbRw8emuE0/L7C9dNjc/cb/JP7pw==",
    "spec_meter.md": "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",
    "std_balancing.md": "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",
    "std_loss.md": "eNptVMFu2zAMvfsrCPSwFgiCbsf1NAw7DBiwQ3uPGIuxtcqSIcrJ8vcjJdlNi11sQKIeHx8feQffYzjTFUNP4CMzcMZgMdmu+3GmdIVAGQZcBhcGSNTHZBkumClBHjEDQo8BvXxTcmThSPlCFCBfooQzpXN0iWEJVl4gWPKuwHrXk+TcgWQTJAJc8hiTy1fAvo9LyKzYH8idYgKXIcfypGF8EtI0TBTyHl7GFmlppiBUYyihR/SKYqW8mHAguTiVi1aaYLxnvAOOmsqxkJjmJctbPGnZFUrlEAgqxRyRXdh33d0dPFcmeocreNd92yQ8ko9h4LUEfgt3UnGraA/G94dEg2PJuP/DMRgYo7eqiWlBbCScpTnuLMA7mIXbpqpir4FGKrDrGfcjTe1o095YaaiB+5/Pv1Xi6WFVZ2uXtJ3SU1Odiywhyi8IxhVmTNn1i8dUA2sf+FaKxkUf3tZdPCSkDq9f9jb2f42WQ2ujpbGFruJJnAQs5VWVIgaCjEdPcBkjE4yEarIULxBwopqoj36ZAm+F78D0HlnE0+JN42GegLAf4bQkeVQxXM3QGJTm/lJnJdGKu+6lgL+3Z7kCTFRSC8hms8pT5DJTPmjsfrYnU3Uqd2LAxt+7UGRauYkpz47JHsTKmuAwOe+dqZNDbZjkSXVntawSl/Rfb7VuBnhDM6Btv+366gdNo2RlIheWwzxy7eKr89G7nEq9uVhuogHrkUS06QLMVXxdDW20dBplqEi8gjpMxyvI0AyiCs8obr5R+P3sbCNdjm/XUfPSylZqkEZszlndF24nS8ho0TuYFp/d7F1lUmRaprVb/90WivJxR1iZPVshPj8+PrZthq+6AKPaUsrbNGMNqz6R/Wa1gnvD2R5m2auOXQz7yZqHaoqPFGr1W+5tjtqtkitbSELmmPK2KmuGbWfVDN0/jNQgRw==",
    "std_pipeline.md": "eNptVU1v20YQvetXDOBDU0AlpDYI2voUFG5ORYs2QI7WiFx+wOQusbOUrH/fN7NLymnqgwFxvt+8eftAfw2zGwfvqA4+Ra7Tbve5H2T7Se3w6oT6cKXUOxLHEvx3QtcQXwh+85Iohc7BGCv67OIk1LgWGRsavMV0YxDheKOaI/7j0xA3n8mxH3xHV8S7i4tqvhHPs+O4JmhCvUzOJ6l2u4cH+idx50T7fNNPO3RLdNr35KiNYaKgQ/U8eLQFz+i6QRIK8JL6EId0o264IEKr3mAWFy8BnbFH50nozLLGTk4D22F0ezNFN49cO+tJI8N4wShrYB1idHUaghcdZBzUJhTajOASL5iw4YRkuQP9XIIMES0WHTfARR5zUAoRQ5fgvVmJOwwnSR2mfdmTwcVpwfhtKy5pfNlORlYrlpHD7Az6kjyPmvrosDJeOjW51znEJHs6x7B0va667M+7hEAMQWdbKVq6DIKZaQxdHsw+q1/JJhU9cd1nYJU7Zx7Z1xgZUQpcuPqv/Ok6pH6zzBzZsBF6d5LUPOdwOFZTc/o+tw/aAiDNSso6BT0P+yavlkZrnriuw+IVcyOMtru1VEBZa2kyK7O3NeeBDRvi6OgKPiVkfHca+RaW9FyMpbOPcAgoXJZKnJDlpvjpTnFbQsusbJ/080rlBlNLQowuEzBk9n9c6bvbfdGboXQNRk25gy6sR4Dr3dtPtRJTMxgp9RI9HERJqeb7QbQBNwecAiDzch81GH8sDbBbxFY2Zv9M3kUv4Y4KZRhQ4UVK8/QHWBga3RDm9gW4xC+ALSdbdzBtjgkE132f6rYDpC3GxXIU1DyBImtdvbg55QTsCcqBm8MJLcYyHxRtoJul6o58xvPP2MAXPaqi7XZPxpZvKapQZCYZr+7UOTug4CxrmR1hhQ8VfTGerdXPWCYAYbSmUAKDNzuxawLoPnybaEPavZoq59af8g/JOgnvjPo6RPH9jzVTQvoBEtuYSH615bzFOYYO16YdKIrB7wGxm/NFZlWWzDD5ld4rqscj5D3VvWniHjvAofdhXOk+QqeTVduE9pGOP2rkT4f7N8gVDgEfPxxWoYy4jpJvhIBrPgv78D9RPx829YSeNviuJw8RWqazjmYM+XQ8HA7q/ekX/EGTDKxTVcvltHEcz8jEP4hT0dEtX3hc8sX8/ftv9P6ISvkFkyK/JlVMPS4c9fVFfaRT9/p8rpLmVYxP8QId6arZCoVxXN9UvVZlhKxZEp8tgmnG87zeaYOHehqSvrOmo9uB5K5zRinvBcI55vcI3Jmwgu1+8u3slRcmNzAjiNM9ii1TtfsX1ZjnPA==",
    "std_precision.md": "eNo9Us1OhEAMvvMUTbxospIYTYx69rYHo75AlykwcZhiWxb37e3MLnujpd8v3MCHUBc1cgY1zAElNM2XseBAugMTzNqT+KOQxrBg8seRMAD3vZL5FHCaYx5gJukoWwGCM0FiVRC0MgpBzEaDM7XwfiQ51VkmCtEv4Hdhiw6GW4SJMDu7+9lcIATBFXR0njq5IoWro7IqYncQFegPO4MlW0xgI4HwkkOxF02vESHjRPoGmeGIaaECrIfOiubuT8AOFpjZbe5qHL89xIzuvE+M5pT39e2FgUocrdA+DotQ2zTfK1/1zyUU3eDRq7XA3TI5ziv53Fzihc4Y1pETeRsDpmieFVjKevRLoWCjQs8p8aqVbCgNFHdOWDz68ZaoMrrIvn6QTSkIz2doL15Z+QO8dISfmLgKvl5qLeunx4f25Rl+9nCgjr27svGxbf4BylnPdw==",
    "stn_core.sqlite": "eNrt2c9S00AcB/CkDSIqSR3GobFTXMdRYEa02yyh4SSUqqMVsZRBvDBLu9DYdJfZXUCPXLx58jX0NTz4GurVZzAp6Uzbi1cdf5+ZTSf55vfbP7dMt1/VQ83QoZA9qpFn5AzTNB4hZBhGNh0DmXhYQ/em8WdZ40HLmE6KnZuG8yG+AAAAAAAAAAAAf5W3mcnZ+XnzfEbTg4hJdhQqzeR+j2k6cpOtNmprzRpqrq3Xa2gkQgtd9h41a6+baPNlPHbq9fvolEYnbPTh4jtzcrZQMM+f9OdSmupQ8PQnM9I/fYgWlObjndNsn9MeG89aVLc6Pcb12MzJt3nOXjWcn85X57Pz0dHOG2fVQc6E/cP+Zn+xP9nK3otfAAAAAAAAAADwnyrmLHdpprG9FFSW96iU4gw1mGLyVISyGpC8Y7l3krgSlDdOeI+GEdqgvTiZsy33YZKsrJCnIopCrtAuCyXaEiKqBjg/nVYSgrcYb0fxxyyVPE4K1yx3MUm8srfJdIfJltA6bZu/mpb5ZfKCyiheT7+s4t+6Yrm4v9JgZSeKRKsbJ7yL7sUz8nbVJ+6U5d5NXljGwWMayoMTyftdK37+ctrVC0p1yo/aYpDMTabbIHi5prptGq9z6ABw/lJaGWDyPP6ml+ziADCZnbDc20mCy6TZEfKYXWwBF63BkZb83Q6Vh8MdfZLPDtaC8ZpsM47WqQqTHRYzaSEukWdMKXE8fKLENdP9eZ43sj+fXPw3/91wfsUXAAAAAAAAAAAA/KumMtkb16U4U9jPmVm3oBhVgpdLZX9p2/sN7dLcog==",
    "stn_mirror.csv": "eNpdkUtvwjAQhO/9FZEPPW2lOM7Lx1ZQVX0gBFSoJ2SISywcG61N+/frOIBCz9/szuys8wacF15ZszGik7AVThlAKRpl9ptO3y2WD4xSII/YSJM89ZjAVDgPGc3zHtc8AzI5mU4onUxER2Bm0beQpWnkOS2ATN2hEVomC+kk/liFBJb2FFS0YDSaMAbkWSjcntAMa9ayd8lY2fOC8v98SMHKtOdVlQN5sVor45K1VJjMrdVXl5JHFU2D6lU6Z49j0SUwZ72I0yB6C+Yo9TgJY1VMylMg78LsG3sThA64zML0h0Btf5OVwEtbtKRFnM7CnTPpW4k76/24MFqWsYo8D33PpWlCX8OGyxF55LR3WLUWj3IYP+OKx6Y4r4B8am13hzBuDsl9uNI01z7r2ARPSyDrVuD3zVOihhZ1/Byvw+e+BGI4ZaQ5t0XDY/4As+uqjg==",
    "sv_survey.csv": "eNp1VEtuwjAQ3fcsg+SZ8W/ELeAAKGqRWomCBGml3r7OeKIE46y84D37/cL9PLx/wuPn/nv+O3+cbld4jMP4dbs+YLyNw+X0fXk7HhwCOYo7JztkOBx3ImlfDibWgxkiopuQ1CC9x/1CSMkrQZweiCApKI8bXiRFCvoZGXJWpG+Q5bcJkoX2C295CISrsrDxgosrepELMbESYmsa1+LN2OQ9EykhtYQc7GrwrtrM/XgsyKIavCRFSoNcCeSo76Frk7A6immOegtiX5JlZlbMWOkI0KWoROqnHFCMAdFUtM1ZoEsR4LNT5EtzzKsGTEV5ATJXEaFPsChMvRJC1RL7qjW0VCEbJRURJbT6bFuSmbbL5t3YJ1DCRkfVoGyOGDjrCsltKlxFMX8fVLZV50C4oalW/rzlqUihyqP+jCzJSX3hKpI3gqm1LLwStm6ZfF/Ss5Vp/MlXLS91Ps1v+TOZK5NclP0DOLQJig==",
    "tab_h3.xlsx": "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",
    "xw_codes.csv": "eNoljjsOw0AIRHvO4kj8loUTbB8fIEoRuXOKJPcP4PJphjccz9/xepzv7fM9YbG4bPf9ZqywVI0KwgesGc4FgyKTwK7NWTUPL1ClrKFogYgUWN9IYKopOgk0WCaCDTFhpX8UUI8yt82DYYlQ7wilesj1QVDWPCw64dqZ01qAmdC4QGnAHxi/MMI="
}

# ---- extract generator (shared by the REPORTS builder and tests/test_output.py) ----
import io as _io
import json as _json
import sqlite3 as _sqlite3
import zipfile as _zipfile
import zlib as _zlib


class Rng:
    __slots__ = ("state",)

    def __init__(self, seed):
        self.state = seed & 0xFFFFFFFFFFFFFFFF or 0xA0761D6478BD642F

    def _next(self):
        x = self.state
        x ^= (x >> 12) & 0xFFFFFFFFFFFFFFFF
        x ^= (x << 25) & 0xFFFFFFFFFFFFFFFF
        x ^= (x >> 27) & 0xFFFFFFFFFFFFFFFF
        self.state = x
        return (x * 0x2545F4914F6CDD1D) & 0xFFFFFFFFFFFFFFFF

    def rand_int(self, lo, hi):
        return lo + self._next() % (hi - lo + 1)

    def choice(self, seq):
        return seq[self._next() % len(seq)]

    def shuffle(self, items):
        for i in range(len(items) - 1, 0, -1):
            j = self._next() % (i + 1)
            items[i], items[j] = items[j], items[i]

    def sample(self, seq, k):
        pool = list(seq)
        self.shuffle(pool)
        return pool[:k]


STEMS = ["Arden", "Bellcote", "Carrow", "Dunmail", "Elsworth", "Fenwick", "Garnet", "Hollins", "Ingleby", "Jessop",
         "Kestrel", "Langdon", "Marlow", "Nethercott", "Orrin", "Pendle", "Quarry", "Rushmere", "Stanage", "Thorpe",
         "Ullock", "Vale", "Wharfe", "Yarrow", "Ashby", "Brandon", "Coldwell", "Derwent", "Eskdale", "Fairburn"]
KINDS = ["Reservoir", "Dam", "Weir Pool", "Tarn", "Basin", "Tank & Pond"]
BASIN_NAMES = ("North", "South", "West", "East")
SEGMENTS = ("commercial", "public")


def make_pool(seed, regime):
    """One basin from a seed. Reservoirs come back in stored row order."""
    rng = Rng(seed)
    while True:
        n = rng.rand_int(4, 7)
        names = [f"{s} {rng.choice(KINDS)}" for s in rng.sample(STEMS, n)]
        nums = sorted(rng.sample(range(100, 999), n))
        stns = [f"RS-{v}" for v in nums]
        members = [(stns[i], names[i], rng.rand_int(1300, 2300)) for i in range(n)]
        gaugings = []
        for i in range(n):
            for j in range(i + 1, n):
                reps = rng.choice([0, 1, 1, 2, 2, 3]) if regime == "multi" else rng.choice([0, 1, 1, 1])
                for _ in range(reps):
                    a, b = (i, j) if rng.rand_int(0, 1) == 0 else (j, i)
                    gaugings.append((members[a][0], members[b][0], rng.choice([0, 1, 1, 2, 2])))
        cnt = {m[0]: 0 for m in members}
        for a, b, _s in gaugings:
            cnt[a] += 1
            cnt[b] += 1
        if len(gaugings) < n:
            continue
        if regime == "multi" and len(set((min(a, b), max(a, b)) for a, b, _s in gaugings)) == len(gaugings):
            continue
        break
    if regime == "f7":
        rng.shuffle(members)
    if regime == "odd":
        d0, k, b = rng.choice([16, 32, 64]), rng.rand_int(1, 4), rng.rand_int(6, 40)
    elif regime == "pat":
        d0, k, b = rng.choice([24, 32, 48, 64, 80]), rng.rand_int(1, 3), rng.rand_int(12, 40)
    elif regime == "ship":
        d0, k, b = rng.choice([40, 44, 48, 52, 56, 60]), rng.rand_int(2, 6), rng.rand_int(30, 40)
    else:
        d0, k, b = rng.rand_int(10, 95), rng.rand_int(1, 5), rng.rand_int(6, 40)
    return {"members": members, "gaugings": gaugings, "d0": d0, "K": k, "B": b}


def _xml_escape(text):
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def build_xlsx(sheets, parts=None, text_numbers=False, sst_part=None, phonetic=False, inline_rph=False):
    """sheets: list of (name, rows); first row is the header; cells are str or int.
    parts: the worksheet part number of each sheet (default 1, 2, ...); text_numbers: integer cells after
    column A are written as shared strings."""
    parts = list(parts or range(1, len(sheets) + 1))
    strings, index = [], {}

    def sidx(s):
        if s not in index:
            index[s] = len(strings)
            strings.append(s)
        return index[s]

    sheet_xml = []
    for _name, rows in sheets:
        out = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n',
               '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>']
        for r, row in enumerate(rows, start=1):
            out.append(f'<row r="{r}">')
            for c, val in enumerate(row):
                ref = f"{'ABCDEFGH'[c]}{r}"
                if isinstance(val, int) and inline_rph and c > 0 and r > 1:
                    # an inline string whose phonetic run is not part of the cell value
                    out.append(f'<c r="{ref}" t="inlineStr"><is><t>{val}</t><rPh sb="0" eb="{len(str(val))}"><t>{abs(val) % 9 + 1}</t></rPh></is></c>')
                elif isinstance(val, int) and not (text_numbers and c > 0):
                    out.append(f'<c r="{ref}"><v>{val}</v></c>')
                else:
                    out.append(f'<c r="{ref}" t="s"><v>{sidx(str(val))}</v></c>')
            out.append("</row>")
        out.append("</sheetData></worksheet>\n")
        sheet_xml.append("".join(out))
    sst = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n',
           f'<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="{len(strings)}" uniqueCount="{len(strings)}">']
    numeric = {str(v) for _n, rows in sheets for row in rows[1:] for v in row[1:] if isinstance(v, int)} if phonetic else set()
    sst += [f"<si><t>{_xml_escape(s)}</t>" + (f'<rPh sb="0" eb="{len(s)}"><t>{len(s) % 10}</t></rPh>' if s in numeric else "") + "</si>"
            for s in strings]
    sst.append("</sst>\n")
    wb = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n',
          '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
          'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>']
    wb += [f'<sheet name="{_xml_escape(n)}" sheetId="{i + 1}" r:id="rId{i + 1}"/>' for i, (n, _r) in enumerate(sheets)]
    wb.append("</sheets></workbook>\n")
    rels = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n',
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">']
    rels += [f'<Relationship Id="rId{i + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
             f'Target="worksheets/sheet{parts[i]}.xml"/>' for i in range(len(sheets))]
    rels.append(f'<Relationship Id="rId{len(sheets) + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings" Target="{sst_part or "sharedStrings"}.xml"/>')
    rels.append("</Relationships>\n")
    ctypes = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n',
              '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">',
              '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>',
              '<Default Extension="xml" ContentType="application/xml"/>',
              '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>',
              f'<Override PartName="/xl/{sst_part or "sharedStrings"}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/>']
    ctypes += [f'<Override PartName="/xl/worksheets/sheet{k}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>' for k in sorted(parts)]
    ctypes.append("</Types>\n")
    root_rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                 '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                 '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
                 "</Relationships>\n")
    parts_out = sorted((parts[i], x) for i, x in enumerate(sheet_xml))
    parts = [("[Content_Types].xml", "".join(ctypes)), ("_rels/.rels", root_rels), ("xl/workbook.xml", "".join(wb)),
             ("xl/_rels/workbook.xml.rels", "".join(rels)), (f"xl/{sst_part or 'sharedStrings'}.xml", "".join(sst))]
    if sst_part:  # an earlier string table left in the package under the default part name, referenced by nothing
        old = strings[:2] + strings[2:][7:] + strings[2:][:7]
        parts.append(("xl/sharedStrings.xml", "".join(sst[:2] + [f"<si><t>{_xml_escape(x)}</t></si>" for x in old] + sst[-1:])))
    parts += [(f"xl/worksheets/sheet{k}.xml", x) for k, x in parts_out]
    buf = _io.BytesIO()
    with _zipfile.ZipFile(buf, "w", _zipfile.ZIP_STORED) as zf:
        for name, text in parts:
            info = _zipfile.ZipInfo(name, date_time=(2026, 9, 30, 12, 0, 0))
            info.compress_type = _zipfile.ZIP_STORED
            info.external_attr = 0o644 << 16
            zf.writestr(info, text.encode("utf-8"))
    return buf.getvalue()


OFFSET_TABLE = [0, 7, 14, 21, 29, 36, 43, 50, 57, 65, 72, 80, 87, 95, 102, 110, 117, 125, 133, 141, 149, 158, 166,
                175, 184, 193, 202, 211, 220, 230, 240, 251, 262, 273, 284, 296, 309, 322, 336, 351, 366, 383, 401,
                422, 444, 470, 501, 538, 589, 677, 800]


def _stale(text):
    """A plausible earlier value of a positive integer cell: one more, or one less when that stays positive."""
    v = int(text)
    return str(v - 1 if v >= 3 and v % 2 else v + 1)


def _stale_damp(text):
    """An earlier damping percentage: 15 away, kept inside 1 to 100."""
    v = int(text)
    return str(v - 15 if v > 30 else v + 15)


def _docx_cell(text, form):
    run = f"<w:r><w:t>{_xml_escape(text)}</w:t></w:r>"
    old = f"<w:r><w:t>{_xml_escape(_stale(text))}</w:t></w:r>" if form in ("move", "ign") else run
    if form == "alt":  # markup compatibility (ECMA-376 Part 3): a choice and its fallback carry the same run
        return ('<w:p><mc:AlternateContent><mc:Choice Requires="w14">' + run + "</mc:Choice><mc:Fallback>" + run
                + "</mc:Fallback></mc:AlternateContent></w:p>")
    if form == "move":  # a tracked move inside the cell: the moved-from run is no longer current text
        return ('<w:p><w:moveFromRangeStart w:id="1" w:author="registry" w:name="m1"/><w:moveFrom w:id="2" w:author="registry">'
                + old + '</w:moveFrom><w:moveFromRangeEnd w:id="1"/><w:moveToRangeStart w:id="3" w:author="registry" w:name="m1"/>'
                + '<w:moveTo w:id="4" w:author="registry">' + run + '</w:moveTo><w:moveToRangeEnd w:id="3"/></w:p>')
    if form == "req":  # alternate content: a choice requiring a namespace this file's consumer does not understand, then a
        # choice requiring only the WordprocessingML namespace (the first choice the consumer can take), then a fallback
        v = int(text)
        stale2 = str(v - 7 if v > 20 else v + 7)
        return ('<w:p><mc:AlternateContent><mc:Choice Requires="m">' + f"<w:r><w:t>{_xml_escape(_stale_damp(text))}</w:t></w:r>"
                + '</mc:Choice><mc:Choice Requires="w">' + run + "</mc:Choice><mc:Fallback>"
                + f"<w:r><w:t>{_xml_escape(stale2)}</w:t></w:r>" + "</mc:Fallback></mc:AlternateContent></w:p>")
    if form == "hold" and len(text) >= 2:  # an ignorable-namespace element named for content processing: ignored, its content kept
        return ("<w:p><w:r><w:t>" + _xml_escape(text[:-1]) + "</w:t></w:r><ba:hold><w:r><w:t>" + _xml_escape(text[-1:])
                + "</w:t></w:r></ba:hold></w:p>")
    if form == "ign":  # an element of an ignorable namespace no consumer of this file understands: ignored with its content
        return "<w:p>" + run + "<ba:note>" + old + "</ba:note></w:p>"
    return "<w:p>" + run + "</w:p>"


def _rehome(blob, old_main, new_main, stale):
    """Move a package's main part (and its relationship part) to new_main, as the package relationships name it,
    and leave stale parts, referenced by nothing, under the default names."""
    def rels_of(name):
        d, _s, b = name.rpartition("/")
        return (d + "/" if d else "") + "_rels/" + b + ".rels"
    out = _io.BytesIO()
    with _zipfile.ZipFile(_io.BytesIO(blob)) as zin, _zipfile.ZipFile(out, "w", _zipfile.ZIP_STORED) as zout:
        items = []
        for name in zin.namelist():
            data = zin.read(name).decode("utf-8")
            if name == "_rels/.rels":
                data = data.replace(f'Target="{old_main}"', f'Target="{new_main}"')
            elif name == "[Content_Types].xml":
                data = data.replace(f'PartName="/{old_main}"', f'PartName="/{new_main}"')
            name = new_main if name == old_main else rels_of(new_main) if name == rels_of(old_main) else name
            items.append((name, data))
        items += sorted(stale.items())
        for name, data in items:
            info = _zipfile.ZipInfo(name, date_time=(2026, 9, 30, 12, 0, 0))
            info.external_attr = 0o644 << 16
            zout.writestr(info, data.encode("utf-8"))
    return out.getvalue()


def stale_book_parts(off_rows):
    """Last season's workbook under the default main part name: sheet offset at nine tenths, in a part of its own."""
    ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    rel = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    rows = []
    for r, (a, v) in enumerate(off_rows, 1):
        if r == 1:
            cells = f'<c r="A1" t="inlineStr"><is><t>{a}</t></is></c><c r="B1" t="inlineStr"><is><t>{v}</t></is></c>'
        else:
            w = (v * 9) // 10 if v >= 0 else -((-v * 9) // 10)
            cells = f'<c r="A{r}" t="inlineStr"><is><t>{a}</t></is></c><c r="B{r}"><v>{w}</v></c>'
        rows.append(f'<row r="{r}">{cells}</row>')
    head = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
    return {"xl/workbook.xml": head + f'<workbook xmlns="{ns}" xmlns:r="{rel}"><sheets><sheet name="offset" sheetId="1" r:id="rId1"/></sheets></workbook>\n',
            "xl/_rels/workbook.xml.rels": head + '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            f'<Relationship Id="rId1" Type="{rel}/worksheet" Target="worksheets/season2025.xml"/></Relationships>\n',
            "xl/worksheets/season2025.xml": head + f'<worksheet xmlns="{ns}"><sheetData>' + "".join(rows) + "</sheetData></worksheet>\n"}


def build_docx(rows, params=None, form=None, dform=None):
    """A minimal Office Open XML word document: the scheme table, then (params) the basin operating parameters
    table; form "alt", "move" or "ign" writes the patience and round budget of every basin in that markup."""
    w = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    mc = "http://schemas.openxmlformats.org/markup-compatibility/2006"
    w14 = "http://schemas.microsoft.com/office/word/2010/wordml"
    pc = ' mc:ProcessContent="ba:hold"' if dform == "hold" else ""
    body = [f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<w:document xmlns:w="{w}" xmlns:mc="{mc}" xmlns:w14="{w14}" xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math" xmlns:ba="urn:basin-authority:annotations" mc:Ignorable="w14 ba"{pc}><w:body>',
            "<w:p><w:r><w:t>Supply scheme classes of the basin authority</w:t></w:r></w:p>", "<w:tbl>"]
    for row in rows:
        body.append("<w:tr>" + "".join(f"<w:tc>{_docx_cell(c, None)}</w:tc>" for c in row) + "</w:tr>")
    body.append("</w:tbl>")
    if params:
        body += ["<w:p><w:r><w:t>Basin operating parameters</w:t></w:r></w:p>", "<w:tbl>"]
        for k, row in enumerate(params):
            body.append("<w:tr>" + "".join(f"<w:tc>{_docx_cell(c, (form if j >= 2 else dform if j == 1 else None) if k else None)}</w:tc>" for j, c in enumerate(row)) + "</w:tr>")
        body.append("</w:tbl>")
    body.append("<w:sectPr/></w:body></w:document>\n")
    ctypes = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
              '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
              '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
              '<Default Extension="xml" ContentType="application/xml"/>'
              '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
              "</Types>\n")
    rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
            "</Relationships>\n")
    buf = _io.BytesIO()
    with _zipfile.ZipFile(buf, "w", _zipfile.ZIP_STORED) as zf:
        for name, text in (("[Content_Types].xml", ctypes), ("_rels/.rels", rels), ("word/document.xml", "".join(body))):
            info = _zipfile.ZipInfo(name, date_time=(2026, 9, 30, 12, 0, 0))
            info.external_attr = 0o644 << 16
            zf.writestr(info, text.encode("utf-8"))
    return buf.getvalue()


def _pdf_str(text):
    return "(" + text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)") + ")"


def build_pdf(lines, pad=0, split=None, tj=()):
    """A one-page PDF showing one text line per row. Plain form: one Flate content stream, one Tj per line.
    split: index of the first line placed in a second content stream (whose /Length is an indirect object);
    tj: indexes of lines shown by a TJ array of two strings instead of Tj."""
    import zlib as _z
    ops = ["BT", "/F1 10 Tf", "72 760 Td", "12 TL"]
    cut = None
    for k, line in enumerate(lines):
        if k == split:
            cut = len(ops)
        if k in tj:
            h = max(1, len(line) // 2)
            ops.append("[" + _pdf_str(line[:h]) + " 15 " + _pdf_str(line[h:]) + "] TJ T*")
        else:
            ops.append(_pdf_str(line) + " Tj T*")
    ops.append("ET")
    ops.append("%" + "p" * pad)
    chunks = [ops] if cut is None else [ops[:cut], ops[cut:]]
    streams = [_z.compress(("\n".join(c) + "\n").encode("latin-1"), 9) for c in chunks]
    contents = b"4 0 R" if len(streams) == 1 else b"[4 0 R 6 0 R]"
    objs = [b"<< /Type /Catalog /Pages 2 0 R >>",
            b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents " + contents + b" /Resources << /Font << /F1 5 0 R >> >> >>",
            b"<< /Length " + str(len(streams[0])).encode() + b" /Filter /FlateDecode >>\nstream\n" + streams[0] + b"\nendstream",
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    if len(streams) == 2:
        objs.append(b"<< /Length 7 0 R /Filter /FlateDecode >>\nstream\n" + streams[1] + b"\nendstream")
        objs.append(str(len(streams[1])).encode())
    out = bytearray(b"%PDF-1.4\n")
    offs = []
    for i, body in enumerate(objs, start=1):
        offs.append(len(out))
        out += f"{i} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n".encode() + b"0000000000 65535 f \n"
    for o in offs:
        out += f"{o:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(out)


def plain_pdf_rows(raw):
    """The plain reader a solver writes from the shipped file: first stream, Tj lines only."""
    import zlib as _z
    i = raw.index(b"stream\n") + 7
    j = raw.index(b"\nendstream", i)
    shown = [ln[1:-len(") Tj T*")] for ln in _z.decompress(raw[i:j]).decode("latin-1").splitlines()
             if ln.startswith("(") and ln.endswith(") Tj T*")]
    return [tuple(r.split()) for r in shown[shown.index("segment revised_on rate_milli") + 1:]]


def robust_xlsx_offsets(raw):
    """A careful reader that follows the relationships and resolves string cells, but joins every <t> under <si>."""
    import xml.etree.ElementTree as _E
    ns = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    rns = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
    with _zipfile.ZipFile(_io.BytesIO(raw)) as z:
        links = list(_E.fromstring(z.read("xl/_rels/workbook.xml.rels")))
        tgt = {r.get("Id"): r.get("Target") for r in links}
        sst_name = [r.get("Target") for r in links if r.get("Type").endswith("/sharedStrings")][0]
        shared = ["".join(t.text or "" for t in si.iter(ns + "t")) for si in _E.fromstring(z.read("xl/" + sst_name)).iter(ns + "si")]
        sheet = [x for x in _E.fromstring(z.read("xl/workbook.xml")).iter(ns + "sheet") if x.get("name") == "offset"][0]
        rows = _E.fromstring(z.read("xl/" + tgt[sheet.get(rns + "id")])).iter(ns + "row")
        out = {}
        for k, row in enumerate(rows):
            vals = [shared[int(c.find(ns + "v").text)] if c.get("t") == "s" else c.find(ns + "v").text for c in row.iter(ns + "c")]
            if k:
                whole, frac = vals[0].split(".")
                out[int(whole) * 100 + int(frac)] = int(vals[1])
    return out


def robust_docx_params(raw):
    """A careful reader that takes the table by its header and joins every w:t of a cell."""
    import xml.etree.ElementTree as _E
    w = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    with _zipfile.ZipFile(_io.BytesIO(raw)) as z:
        root = _E.fromstring(z.read("word/document.xml"))
    for tbl in root.iter(w + "tbl"):
        rows = [["".join(t.text or "" for t in tc.iter(w + "t")) for tc in tr.iter(w + "tc")] for tr in tbl.iter(w + "tr")]
        if rows[0][0] == "basin":
            return {r[0]: tuple(int(x) for x in r[1:]) for r in rows[1:]}
    raise ValueError("no parameters table")


def plain_xlsx_offsets(raw):
    """The plain reader a solver writes from the shipped file: part sheet1.xml, column B read as a number."""
    import re as _re
    with _zipfile.ZipFile(_io.BytesIO(raw)) as z:
        sst = ["".join(_re.findall(r"<t>([^<]*)</t>", si)) for si in _re.findall(r"<si>(.*?)</si>", z.read("xl/sharedStrings.xml").decode())]
        sheet = z.read("xl/worksheets/sheet1.xml").decode()
    out = {}
    for row in _re.findall(r"<row [^>]*>(.*?)</row>", sheet)[1:]:
        a, b = _re.findall(r"<v>([^<]*)</v>", row)[:2]
        whole, frac = sst[int(a)].split(".")
        out[int(whole) * 100 + int(frac)] = int(b)
    return out


def _sense_text(sa, form):
    """sa = halves drawn by the from-reservoir: 0 (to drew), 1 (neither), 2 (from drew)."""
    if form == "csv":
        return {0: "fwd", 2: "rev", 1: "nil"}[sa]
    if form == "tsv":
        return {0: "0", 2: "1", 1: "0.5"}[sa]
    return {0: "to", 2: "from", 1: "neither"}[sa]


def _day(n):
    """Day n of the season (1 = 2026-07-01); the season is 2026-07-01..2026-09-30."""
    for m, length in ((7, 31), (8, 31), (9, 30)):
        if n <= length:
            return f"2026-{m:02d}-{n:02d}"
        n -= length
    raise ValueError(n)


_RAW_BAD = (b"\r\n", b"TO" + b"DO", b"FIX" + b"ME", b"X" + b"XX", b"PLACE" + b"HOLDER", b"{{", b"__")


def _clean(raw):
    return not any(t in raw for t in _RAW_BAD)


DATUM_CLASS = tuple(range(-95, 100, 5))


def datum_rows(reaches, catch_of, reading, totals):
    """One relation per survey reach: sum over catchments of (stations of c) * d_c lies in [lo, hi]."""
    rows = []
    for grp, total in zip(reaches, totals):
        count = {}
        for stn in grp:
            count[catch_of[stn]] = count.get(catch_of[stn], 0) + 1
        cs = tuple(sorted(count))
        base = total - sum(reading[stn] for stn in grp)
        rows.append((cs, tuple(count[c] for c in cs), base, base + 9))
    return rows


def datum_solutions(rows, cats, limit=2):
    """Every datum assignment in the class that fits all rows, up to limit; None below full rank.

    Exact: any fit meets each of n independent rows at one of its two multiples of 5, so the 2**n basis
    right-hand sides, solved with the basis inverse, list every candidate."""
    from math import lcm
    idx = {c: i for i, c in enumerate(cats)}
    n = len(cats)
    eqs = []
    for cs, ks, lo, _hi in rows:
        vec = [0] * n
        for c, k in zip(cs, ks):
            vec[idx[c]] = k
        eqs.append((vec, -(-lo // 5)))
    basis, inv = _datum_basis([e[0] for e in eqs], n)
    if basis is None:
        return None
    den = lcm(*(x.denominator for row in inv for x in row))
    num = [[int(x * den) for x in row] for row in inv]
    base = [eqs[r][1] for r in basis]
    out = []
    for mask in range(1 << n):
        rhs = [base[j] + ((mask >> j) & 1) for j in range(n)]
        xs = []
        for i in range(n):
            t = sum(num[i][j] * rhs[j] for j in range(n))
            if t % den or not -19 * den <= t <= 19 * den:
                break
            xs.append(t // den)
        else:
            val = {c: 5 * xs[idx[c]] for c in cats}
            if all(lo <= sum(k * val[c] for c, k in zip(cs, ks)) <= hi for cs, ks, lo, hi in rows):
                out.append(val)
                if len(out) >= limit:
                    break
    return out


def _datum_basis(vecs, n):
    """First n independent rows (in order) and the inverse of their matrix in Fractions; (None, None) below full rank."""
    from fractions import Fraction
    basis, ech, kept = [], [], []
    for r, v in enumerate(vecs):
        w = [Fraction(x) for x in v]
        for piv, row in ech:
            if w[piv]:
                f = w[piv] / row[piv]
                w = [a - f * b for a, b in zip(w, row)]
        piv = next((i for i in range(n) if w[i]), None)
        if piv is None:
            continue
        ech.append((piv, w))
        kept.append([Fraction(x) for x in v])
        basis.append(r)
        if len(basis) == n:
            break
    if len(basis) < n:
        return None, None
    m = [row[:] + [Fraction(int(i == j)) for j in range(n)] for i, row in enumerate(kept)]
    for col in range(n):
        piv = next(i for i in range(col, n) if m[i][col] != 0)
        m[col], m[piv] = m[piv], m[col]
        f = m[col][col]
        m[col] = [x / f for x in m[col]]
        for i in range(n):
            if i != col and m[i][col] != 0:
                g = m[i][col]
                m[i] = [x - g * y for x, y in zip(m[i], m[col])]
    return basis, [row[n:] for row in m]


def datum_nearest(rows, cats):
    """Misreading kept for planting: floored totals taken as exact sums on the first independent rows, each datum
    rounded to the nearest member."""
    from fractions import Fraction
    idx = {c: i for i, c in enumerate(cats)}
    vecs = []
    for cs, ks, _lo, _hi in rows:
        vec = [0] * len(cats)
        for c, k in zip(cs, ks):
            vec[idx[c]] = k
        vecs.append(vec)
    basis, inv = _datum_basis(vecs, len(cats))
    if basis is None:
        return None
    out = {}
    for c in cats:
        x = sum(inv[idx[c]][j] * rows[r][2] for j, r in enumerate(basis)) / 5
        whole = abs(x).numerator // abs(x).denominator
        if abs(x) - whole >= Fraction(1, 2):
            whole += 1
        out[c] = 5 * (whole if x >= 0 else -whole)
    return out


def datum_bounds(rows, cats):
    """Each catchment's range narrowed by every row until nothing changes; None when a range empties."""
    lo_b = {c: DATUM_CLASS[0] for c in cats}
    hi_b = {c: DATUM_CLASS[-1] for c in cats}
    changed = True
    while changed:
        changed = False
        for cs, ks, lo, hi in rows:
            for c, k in zip(cs, ks):
                omin = sum(kk * lo_b[x] for x, kk in zip(cs, ks) if x != c)
                omax = sum(kk * hi_b[x] for x, kk in zip(cs, ks) if x != c)
                nlo = max(lo_b[c], -((omax - lo) // k))
                nhi = min(hi_b[c], (hi - omin) // k)
                nlo = DATUM_CLASS[0] + -((DATUM_CLASS[0] - nlo) // 5) * 5
                nhi = DATUM_CLASS[0] + ((nhi - DATUM_CLASS[0]) // 5) * 5
                if nlo > nhi:
                    return None
                if (nlo, nhi) != (lo_b[c], hi_b[c]):
                    lo_b[c], hi_b[c], changed = nlo, nhi, True
    return lo_b, hi_b


def datum_greedy(rows, cats):
    """Naive reading: catchments in code order, first member consistent with the rows already complete, no going back."""
    val = {}
    for c in sorted(cats):
        for m in DATUM_CLASS:
            val[c] = m
            if all(lo <= sum(k * val[x] for x, k in zip(cs, ks)) <= hi for cs, ks, lo, hi in rows if all(x in val for x in cs)):
                break
        else:
            return None
    return val


def datum_bounds_low(rows, cats):
    """Naive reading: narrow each catchment's range by the rows, then take the lowest member left."""
    bounds = datum_bounds(rows, cats)
    return None if bounds is None else dict(bounds[0])


def _zz(n):
    """Zigzag then unsigned LEB128 varint."""
    u = 2 * n if n >= 0 else -2 * n - 1
    out = bytearray()
    while True:
        b = u & 0x7F
        u >>= 7
        if u:
            out.append(b | 0x80)
        else:
            out.append(b)
            return bytes(out)


B_MISREADS = ("dict_r", "dict_dup", "state_c")


def _dec_rec(buf, pos, dic, run, mis=()):
    """One meter record at pos under the spec (mis empty) or under a set of codec misreadings.
    Returns (record, next pos, dictionary, running value); the dictionary list is copied, never changed in place."""
    dic = list(dic)

    def varint(p):
        u = shift = 0
        while True:
            b = buf[p]
            p += 1
            u |= (b & 0x7F) << shift
            shift += 7
            if not b & 0x80:
                return (u // 2 if u % 2 == 0 else -(u + 1) // 2), p

    def gauge(p, ref, keep=True):
        if ref:
            if buf[p] >= len(dic):
                raise ValueError("ref")
            return dic[buf[p]], p + 1
        g = f"G{int.from_bytes(buf[p:p + 2], 'big')}"
        if keep and ("dict_dup" in mis or g not in dic):
            dic.append(g)
        return g, p + 2

    sel = buf[pos]
    pos += 1
    kind = sel >> 6
    if kind == 3:
        raise ValueError("kind")
    if kind == 2:
        old, pos = gauge(pos, sel & 0x20, "dict_r" not in mis)
        new, pos = gauge(pos, sel & 0x08, "dict_r" not in mis)
        return ("R", old, new), pos, dic, run
    if sel & 0x08:
        raise ValueError("bit3")
    g, pos = gauge(pos, sel & 0x20)
    val, pos = varint(pos)
    if sel & 0x10:
        val += run
    if kind == 0 or "state_c" not in mis:
        run = val
    if kind == 1:
        return ("C", g, val, _day(buf[pos])), pos + 1, dic, run
    return ("D", g, val), pos, dic, run


def decode_meter(blob, mis=()):
    """Spec decoder of ob_s3.bin; mis names codec misreadings used only for the generator's asserts."""
    if isinstance(mis, str):
        mis = (mis,)
    if blob[:4] != b"OBS3" or blob[4] != 1:
        raise ValueError("bad header")
    if _zlib.crc32(blob[4:-4]) != int.from_bytes(blob[-4:], "big"):
        raise ValueError("crc")
    label, count, pos = blob[5:12].decode("ascii"), int.from_bytes(blob[12:14], "big"), 14
    dic, run, out, body = [], 0, [], blob[:-4]
    for _n in range(count):
        rec, pos, dic, run = _dec_rec(body, pos, dic, run, mis)
        out.append(rec)
    if pos != len(body):
        raise ValueError("length")
    return label, out


def _meter_spans(blob):
    """(start, end, selector, record, running value before) of every record, under the spec."""
    body, pos, dic, run, out = blob[:-4], 14, [], 0, []
    for _n in range(int.from_bytes(blob[12:14], "big")):
        start, before, dic0 = pos, run, list(dic)
        rec, pos, dic, run = _dec_rec(body, pos, dic, run)
        out.append((start, pos, body[start], rec, before, dic0))
    return out


def _zz_varint(v):
    u = 2 * v if v >= 0 else -2 * v - 1
    out = bytearray()
    while True:
        b = u & 0x7F
        u >>= 7
        out.append(b | (0x80 if u else 0))
        if not u:
            return bytes(out)


def plant_rule_traps(blob, lev, off, step=35):
    if lev.get("dup_read") and not lev.get("_inner"):
        out = plant_rule_traps(blob, dict(lev, dup_read=False), off, step)
        for k in range(3):
            done = {r[1] for r in decode_meter(out)[1] if r[0] == "D"}
            seen = [r[1] for r in decode_meter(out)[1] if r[0] == "D"]
            dupd = {g for g in done if seen.count(g) > 1}
            try:
                out = plant_rule_traps(out, {"dup_read": True, "_inner": True}, set(off) - dupd, step + 5 * k)
            except AssertionError:
                if k == 0:
                    raise
                break
        return out
    """r_bit4: every replacement record gets bit 4 set (meaningless in a replacement, so ignored).
    dup_read: a gauge outside the survey gets an earlier reading record with another value (the last reading counts)."""
    spans = _meter_spans(blob)
    body = bytearray(blob[:-4])
    if lev.get("r_bit4"):
        reps = [sp for sp in spans if sp[3][0] == "R"]
        assert reps, "no replacement record"
        for start, _e, sel, _r, _b, _d in reps:
            body[start] = sel | 0x10
    if lev.get("dup_read"):
        def last_readings(b, mis):
            return {r[1]: r[2] for r in decode_meter(b, mis)[1] if r[0] == "D"}

        base = bytes(body) + (_zlib.crc32(bytes(body[4:])) & 0xFFFFFFFF).to_bytes(4, "big")
        cand = [sp for sp in spans if sp[3][0] == "D" and sp[3][1] in off]
        k0 = len(cand) // 2
        for start, end, sel, rec, before, dic0 in cand[k0:] + cand[:k0]:
            other = rec[2] + (step if rec[2] < 1600 else -step)
            gb = bytes([dic0.index(rec[1])]) if rec[1] in dic0 else int(rec[1][1:]).to_bytes(2, "big")
            dup = bytes([(sel & 0x07) | (0x20 if rec[1] in dic0 else 0)]) + gb + _zz_varint(other)
            trial = bytearray(body)
            if sel & 0x10:  # the record's delta now follows the inserted reading
                glen = 1 if sel & 0x20 else 2
                trial[start:end] = dup + bytes(body[start:start + 1 + glen]) + _zz_varint(rec[2] - other)
            else:
                trial[start:end] = dup + bytes(body[start:end])
            trial[12:14] = (int.from_bytes(trial[12:14], "big") + 1).to_bytes(2, "big")
            out = bytes(trial) + (_zlib.crc32(bytes(trial[4:])) & 0xFFFFFFFF).to_bytes(4, "big")
            ok = True
            for mis in [()] + [(m,) for m in B_MISREADS] + [tuple(B_MISREADS)]:
                try:
                    ok = ok and last_readings(out, mis) == last_readings(base, mis)
                except ValueError:
                    ok = False
            if ok:
                return out
        raise AssertionError("no silent duplicate reading")
    out = bytes(body)
    out += (_zlib.crc32(out[4:]) & 0xFFFFFFFF).to_bytes(4, "big")
    return out


def _rec_forms(rec, dic, run, prng):
    """Candidate byte encodings of one record (literal and absolute forms first), each as bytes."""
    filler = prng.rand_int(0, 7)
    if rec[0] == "R":
        out = []
        for r1 in (0, 1):
            for r2 in (0, 1):
                if (r1 and rec[1] not in dic) or (r2 and rec[2] not in dic):
                    continue
                sel = 0x80 | (0x20 if r1 else 0) | (0x08 if r2 else 0) | filler
                g1 = bytes([dic.index(rec[1])]) if r1 else int(rec[1][1:]).to_bytes(2, "big")
                g2 = bytes([dic.index(rec[2])]) if r2 else int(rec[2][1:]).to_bytes(2, "big")
                out.append(bytes([sel]) + g1 + g2)
        return out
    kind = 0 if rec[0] == "D" else 1
    tail = bytes([int(rec[3][8:]) + {"07": 0, "08": 31, "09": 62}[rec[3][5:7]]]) if kind else b""
    out = []
    for ref in (0, 1):
        if ref and rec[1] not in dic:
            continue
        for delta in (0, 1):
            sel = (kind << 6) | (0x20 if ref else 0) | (0x10 if delta else 0) | (filler & 0x07)
            gb = bytes([dic.index(rec[1])]) if ref else int(rec[1][1:]).to_bytes(2, "big")
            out.append(bytes([sel]) + gb + _zz(rec[2] - run if delta else rec[2]) + tail)
    return out


def _quiet(rec, got, off):
    """A misread record is allowed only when it stays silent: a reading of an off-survey gauge with another value,
    or a correction moved between off-survey gauges."""
    if got == rec:
        return True
    if rec[0] == "D":
        return got[0] == "D" and got[1] == rec[1] and rec[1] in off
    if rec[0] == "C":
        return got[0] == "C" and rec[1] in off and got[1] in off and got[3] == rec[3]
    return False


def encode_meter(prng, label, recs, lev, off=frozenset()):
    """ob_s3.bin from (D, gauge, value) / (C, gauge, value, day) / (R, old, new) records in order.

    Every codec misreading is simulated record by record: an unplanted misreading must decode every record
    exactly; a planted one may misread only silently (see _quiet), and must misread at least one record."""
    full = lev.get("full")
    for _attempt in range(200):
        body = bytearray()
        st = {v: ([], 0) for v in (None,) + B_MISREADS}
        hit = {v: False for v in B_MISREADS}
        for rec in recs:
            dic, run = st[None]
            forms = _rec_forms(rec, dic, run, prng)
            if full:
                forms = forms[:1] + prng.sample(forms[1:], len(forms) - 1)
                forms = forms[1:] + forms[:1]
            chosen = None
            for f in forms[:1] if not full else forms:
                try:
                    res = {v: _dec_rec(f, 0, st[v][0], st[v][1], () if v is None else (v,)) for v in st}
                except (ValueError, IndexError):
                    continue  # a misreading that cannot decode the record is a symptom: form refused
                if res[None][0] != tuple(rec):
                    continue
                if all(res[v][0] == tuple(rec) or (lev.get(v) and _quiet(tuple(rec), res[v][0], off)) for v in B_MISREADS):
                    chosen = (f, res)
                    break
            f, res = chosen
            for v in st:
                st[v] = (res[v][2], res[v][3])
                if v is not None and res[v][0] != tuple(rec):
                    hit[v] = True
            body += f
        if any(lev.get(v) and not hit[v] for v in B_MISREADS):
            continue
        head = b"OBS3" + bytes([1]) + label.encode("ascii") + len(recs).to_bytes(2, "big")
        blob = head + bytes(body)
        blob += _zlib.crc32(blob[4:]).to_bytes(4, "big")
        if any(bad in blob for bad in _RAW_BAD):
            continue
        assert decode_meter(blob)[1] == [tuple(r) for r in recs], "meter round trip"
        return blob
    raise RuntimeError("no meter encoding")


def _datum_reaches(prng, pool, lone, catch_of, opening, right, cats, lev, error):
    """Survey reaches added one at a time until the fit is unique (two fits for survey_twofit); None if it never is."""
    reaches = []
    hub = [x for x in pool if catch_of[x] == max(cats)] if lev.get("scale") else []
    if lone is not None:
        for _k in range(3):
            reaches.append(prng.sample(pool, prng.rand_int(1, 3)) + [lone])
    for _r in range(4 * len(cats) + 8):
        if hub:
            rest = [x for x in pool if x not in hub]
            reaches.append(prng.sample(hub, prng.rand_int(1, 2)) + prng.sample(rest, prng.rand_int(1, 4)))
        else:
            reaches.append(prng.sample(pool, prng.rand_int(2, 5)))
        if len(reaches) < len(cats):
            continue
        totals = [sum(opening[s] for s in g) // 10 * 10 for g in reaches]
        sols = datum_solutions(datum_rows(reaches, catch_of, right, totals), cats, 3)
        if sols is None:
            continue
        if error == "survey_twofit":
            if len(sols) == 2:
                return reaches
            if len(sols) < 2:
                return None
        elif len(sols) == 1:
            for _x in range(lev.get("extra", 0)):
                reaches.append(prng.sample(pool, prng.rand_int(2, 5)))
            return reaches
    return None


def _datum_plan(reg, gauge, catch_of, lev, error):
    """Readings, correction and replacement records, survey reaches and datum offsets of one extract."""
    prng = Rng(lev["seed"] * 7919 + 17)
    stns = [r[0] for r in reg]
    opening = {r[0]: r[3] for r in reg}
    cats = sorted(set(catch_of.values()))
    used = set(gauge.values())
    for _attempt in range(20000):
        datum = {c: prng.choice(DATUM_CLASS) for c in cats}
        right = {s: opening[s] - datum[catch_of[s]] for s in stns}
        read = dict(right)
        recs = []
        sday = prng.rand_int(70, 85)
        retired = {}
        for s in prng.sample(stns, 2):
            num = f"G{prng.rand_int(1000, 9999)}"
            while num in used or num in retired.values():
                num = f"G{prng.rand_int(1000, 9999)}"
            retired[s] = num
        order = prng.sample(stns, len(stns))
        fixed = [s for s in order if s not in retired][:3]
        for s in fixed:
            read[s] = right[s] + prng.choice([-1, 1]) * prng.rand_int(2, 9) * 10
            recs.append(("C", gauge[s], right[s], _day(prng.rand_int(20, sday - 1))))
        spare = [s for s in order if s not in fixed and s not in retired]
        if lev.get("alias"):
            s = sorted(retired)[0]
            read[s] = right[s] + prng.choice([-1, 1]) * prng.rand_int(2, 9) * 10
            recs.append(("C", retired[s], right[s], _day(prng.rand_int(20, sday - 1))))
        late = None
        if lev.get("late_fix"):
            s = late = spare.pop(0)
            recs.append(("C", gauge[s], right[s] + prng.choice([-1, 1]) * prng.rand_int(2, 9) * 10, _day(prng.rand_int(sday + 1, 92))))
        for s, num in sorted(retired.items()):
            recs.append(("R", num, gauge[s]))
        touched = set(fixed) | (set(retired) if lev.get("alias") else set()) | ({late} if late else set())
        lone = fixed[0] if lev.get("raw") else None  # the one survey station of its catchment, so raw readings still fit once
        pool = [x for x in stns if x not in touched and (lone is None or catch_of[x] != catch_of[lone])]
        reaches = _datum_reaches(prng, pool, lone, catch_of, opening, right, cats, lev, error)
        if reaches is None:
            continue
        totals = [sum(opening[s] for s in g) // 10 * 10 for g in reaches]
        if error == "survey_nofit":
            totals[0] += 10
        rows = datum_rows(reaches, catch_of, right, totals)
        sols = datum_solutions(rows, cats, 3) or []
        want = 0 if error == "survey_nofit" else (2 if error == "survey_twofit" else 1)
        if len(sols) != want:
            continue
        order = list(range(len(reaches)))
        prng.shuffle(order)
        hub = max(order, key=lambda i: (len({catch_of[x] for x in reaches[i]}), len(reaches[i])))
        order = [i for i in order if i != hub] + [hub]
        reaches, totals = [reaches[i] for i in order], [totals[i] for i in order]
        rows = [rows[i] for i in order]
        if error not in ("survey_nofit", "survey_twofit"):
            raw = datum_solutions(datum_rows(reaches, catch_of, read, totals), cats, 2)
            if raw is None or len(raw) != 1 or bool(lev.get("raw")) == (raw == [datum]):
                continue
            if len(cats) <= 6 and bool(lev.get("near")) == (datum_nearest(rows, cats) == datum):
                continue
        prng.shuffle(recs)
        seen = {x for g in reaches for x in g}
        off = {gauge[x] for x in stns if x not in seen} | {retired[x] for x in retired if x not in seen}
        return {"datum": datum, "read": read, "recs": recs, "reaches": reaches, "totals": totals, "sday": _day(sday),
                "off": frozenset(off)}
    raise RuntimeError("no datum plan")


RECOVERY_MISREADS = ("alias", "date", "raw") + B_MISREADS


def recovery_fits(blob, survey, gauge, catch_of, mis=(), memo=None):
    """Datum fits (up to 2) of the recovery read with a set of misreadings; None when the reading cannot even run."""
    try:
        recs = decode_meter(blob, tuple(m for m in mis if m in B_MISREADS))[1]
    except (ValueError, IndexError):
        return None
    sday = survey[0][0]
    alias = {} if "alias" in mis else {r[1]: r[2] for r in recs if r[0] == "R"}
    raw = {r[1]: r[2] for r in recs if r[0] == "D"}
    fixed, best = dict(raw), {}
    for r in recs:
        if r[0] == "C" and ("date" in mis or r[3] <= sday):
            g = alias.get(r[1], r[1])
            if r[3] >= best.get(g, ""):
                fixed[g], best[g] = r[2], r[3]
    use = raw if "raw" in mis else fixed
    try:
        reading = {x: use[gauge[x]] for x in catch_of}
    except KeyError:
        return None
    rows = datum_rows([g for _d, g, _t in survey], catch_of, reading, [t for _d, _g, t in survey])
    key = tuple(rows)
    if memo is not None and key in memo:
        return memo[key]
    fits = datum_solutions(rows, sorted(set(catch_of.values())), 2)
    if memo is not None:
        memo[key] = fits
    return fits


def silent_ok(blob, survey, gauge, catch_of):
    """Every misreading of the recovery, alone and combined, still finds exactly one datum assignment."""
    import itertools
    memo = {}
    for n in range(1, len(RECOVERY_MISREADS) + 1):
        for mis in itertools.combinations(RECOVERY_MISREADS, n):
            fits = recovery_fits(blob, survey, gauge, catch_of, mis, memo)
            if fits is None or len(fits) != 1:
                return False
    return True


def _write_register(root, rng, pools, error, label, lev=None):
    queues = {p: list(pools[p]["members"]) for p in BASIN_NAMES}
    reg = []
    while any(queues.values()):
        p = rng.choice([q for q in BASIN_NAMES if queues[q]])
        stn, name, opening = queues[p].pop(0)
        reg.append((stn, name, p, opening))
    catch = {}
    codes = rng.sample(range(10, 99), 8)
    for i, p in enumerate(BASIN_NAMES):
        catch[p] = [f"C{codes[2 * i]}", f"C{codes[2 * i + 1]}"]
    gauge = {}
    gnums = rng.sample(range(1000, 9999), len(reg) + 2)
    for i, r in enumerate(reg):
        gauge[r[0]] = f"G{gnums[i]}"
    stray = None
    if error == "unknown_station":
        stray = (f"RS-{rng.rand_int(100, 999)}", f"{rng.choice(STEMS)} Spill", "West", rng.rand_int(1400, 2000))
    db = root / "stn_core.sqlite"
    if db.exists():
        db.unlink()
    con = _sqlite3.connect(str(db))
    con.execute("PRAGMA page_size = 4096")
    con.execute("CREATE TABLE station (stn TEXT NOT NULL, station_name TEXT NOT NULL, catchment TEXT NOT NULL)")
    con.execute("CREATE TABLE register_meta (key TEXT NOT NULL, value TEXT NOT NULL)")
    for _s, _n, b, _o in reg:
        rng.choice(catch[b])  # the draw is kept so that every later draw of the extract is unchanged
    lev = dict(lev or {})
    crng = Rng(lev["seed"] * 104729 + 3)
    per = {p: [r for r in reg if r[2] == p] for p in BASIN_NAMES}
    extra = lev["cats"] - len(BASIN_NAMES)
    count = {p: 1 for p in BASIN_NAMES}
    while extra > 0:
        p = crng.choice([q for q in BASIN_NAMES if count[q] < len(per[q])])
        count[p] += 1
        extra -= 1
    pool_codes = [c for c in crng.sample(range(10, 99), 40)]
    catch = {}
    for p in BASIN_NAMES:
        catch[p] = [f"C{pool_codes.pop(0)}" for _ in range(count[p])]
    catch_of = {}
    for p in BASIN_NAMES:
        members = crng.sample([r[0] for r in per[p]], len(per[p]))
        for i, stn in enumerate(members):
            catch_of[stn] = catch[p][i] if i < len(catch[p]) else crng.choice(catch[p])
    if lev.get("scale"):
        size = {c: sum(1 for v in catch_of.values() if v == c) for p in BASIN_NAMES for c in catch[p]}
        big, top = max(size, key=lambda c: (size[c], c)), max(size)
        swap = {big: top, top: big}
        catch = {p: [swap.get(c, c) for c in catch[p]] for p in BASIN_NAMES}
        catch_of = {stn: swap.get(c, c) for stn, c in catch_of.items()}
    srows = [(s, n, catch_of[s]) for s, n, _b, _o in reg]
    if error == "dup_station":
        first = srows[0]
        others = [c for c in catch[reg[0][2]] if c != first[2]]
        srows.insert(rng.rand_int(1, len(srows)), (first[0], first[1], others[0] if others else first[2]))
    con.executemany("INSERT INTO station VALUES (?, ?, ?)", srows)
    con.executemany("INSERT INTO register_meta VALUES (?, ?)", [("season", label), ("rows", str(len(reg)))])
    con.commit()
    con.close()
    xw = sorted((gauge[s], s) for s, _n, _b, _o in reg)
    rng.shuffle(xw)
    (root / "xw_codes.csv").write_text("gauge_no,stn\n" + "".join(f"{g},{s}\n" for g, s in xw), encoding="utf-8")
    perm = list(range(len(reg)))
    rng.shuffle(perm)
    for att in range(60):
        plan = _datum_plan(reg, gauge, catch_of, dict(lev, seed=lev["seed"] + 1000003 * att), error)
        rows = [(gauge[reg[i][0]], plan["read"][reg[i][0]]) for i in perm]
        blob = None
        for _order in range(60):
            body = [("D", g, o) for g, o in rows]
            for rec in plan["recs"]:
                body.insert(crng.rand_int(0, len(body)), rec)
            try:
                blob = encode_meter(crng, label, body, lev, plan["off"])
                break
            except RuntimeError:
                continue
        if blob is None:
            continue
        survey = [(plan["sday"], g, t) for g, t in zip(plan["reaches"], plan["totals"])]
        if error in ("survey_nofit", "survey_twofit") or silent_ok(blob, survey, gauge, catch_of):
            break
    else:
        raise RuntimeError("no silent extract")
    if lev.get("r_bit4") or lev.get("dup_read"):
        before = decode_meter(blob)[1]
        blob = next(b for b in (plant_rule_traps(blob, lev, plan["off"], st) for st in range(35, 400, 5))
                    if not any(x in b for x in _RAW_BAD))
        after = decode_meter(blob)[1]
        last = {}
        for r in after:
            if r[0] == "D":
                last[r[1]] = r[2]
        assert [r for r in before if r[0] != "D"] == [r for r in after if r[0] != "D"]
        assert last == {r[1]: r[2] for r in before if r[0] == "D"}, "rule traps changed the spec reading"
    if error == "meter_crc":
        for flip in range(1, 256):
            bad = blob[:-1] + bytes([blob[-1] ^ flip])
            if not any(x in bad for x in _RAW_BAD):
                blob = bad
                break
    (root / "ob_s3.bin").write_bytes(blob)
    old_meter = root / "ob_s3.txt"
    if old_meter.exists():
        old_meter.unlink()
    backup = [(g, o + rng.choice([-40, -25, -10, 10, 25, 40])) for g, o in rows]
    (root / "ob_backup.csv").write_text("gauge_no,reading_ml\n" + "".join(f"{g},{o}\n" for g, o in sorted(backup)), encoding="utf-8")
    order = list(range(len(plan["reaches"])))  # already in file order, the hub row last
    survey = ["reach,surveyed_on,stations,total_ml"]
    for n, i in enumerate(order):
        survey.append(f"SR{n + 1:02d},{plan['sday']},{';'.join(plan['reaches'][i])},{plan['totals'][i]}")
    (root / "sv_survey.csv").write_text("\n".join(survey) + "\n", encoding="utf-8")
    rng.shuffle(list(range(8)))  # kept draw
    items = [(c, p) for p in BASIN_NAMES for c in catch[p]]
    crng.shuffle(items)
    xml = ['<?xml version="1.0" encoding="UTF-8"?>\n<cm:catchments xmlns:cm="urn:basin-authority:catchments" season="' + label + '">\n']
    xml += [f'  <cm:catchment code="{c}"><cm:basin>{p}</cm:basin></cm:catchment>\n' for c, p in items]
    xml.append("</cm:catchments>\n")
    (root / "bs_map.xml").write_text("".join(xml), encoding="utf-8")
    mirror = [[s, n, b, plan["read"][s]] for s, n, b, _o in reg]
    for r in rng.sample(range(len(mirror)), max(2, len(mirror) // 8)):
        mirror[r][3] += rng.choice([-12, -7, -3, 4, 9, 15])
    if stray is not None:
        mirror.append(list(stray))
    mirror.sort(key=lambda r: r[1])
    (root / "stn_mirror.csv").write_text("stn,station_name,basin,reading_ml\n" + "".join(f'{s},"{n}",{b},{o}\n' for s, n, b, o in mirror), encoding="utf-8")
    return stray


def _write_methods(root, rng, boundary, label, lic_days, lic_segs, pad, fixed_rates=None, fmt=None):
    """Returns True when every planted container form is silent under the plain readers and changes a used value."""
    fmt = fmt or {}
    rates = []
    for seg in SEGMENTS:
        rates.append((seg, "2026-01-01", rng.rand_int(9, 16)))
        seg_days = [d for d, s in zip(lic_days, lic_segs) if s == seg]
        if boundary:
            rday = rng.choice(seg_days)
        else:
            rday = rng.choice([d for d in range(4, 90) if d not in lic_days])
        rates.append((seg, _day(rday), rng.rand_int(17, 26)))
    if fixed_rates is not None:
        rates = [(a, b, c) for (a, b, _c), c in zip(rates, fixed_rates)]
    lines = [f"Conveyance loss rates, season {label}", "segment revised_on rate_milli"]
    ok = True
    if fmt.get("pdf_split") or fmt.get("pdf_tj"):
        base = [r for r in rates if r[1] == "2026-01-01"]
        revs = [r for r in rates if r[1] != "2026-01-01"]
        lines += [f"{a} {b} {c}" for a, b, c in base + revs]
        first = 2 + len(base)
        raw = build_pdf(lines, pad, split=first if fmt.get("pdf_split") else None,
                        tj=set(range(first, len(lines))) if fmt.get("pdf_tj") else ())
        plain = plain_pdf_rows(raw)
        seen = {(a, b) for a, b, _c in plain}
        missed = [(a, b) for a, b, _c in revs if (a, b) not in seen]
        used = any(_day(d) >= b and s == a for a, b in missed for d, s in zip(lic_days, lic_segs))
        ok = all((sg, "2026-01-01") in seen for sg in SEGMENTS) and used
    else:
        lines += [f"{a} {b} {c}" for a, b, c in rates]
        raw = build_pdf(lines, pad)
    (root / "mt_loss.pdf").write_bytes(raw)
    depot = [(a, b, c + rng.choice([-3, -2, 2, 3])) for a, b, c in rates]
    (root / "lr_depot.csv").write_text("segment,revised_on,rate_milli\n" + "".join(f"{a},{b},{c}\n" for a, b, c in depot), encoding="utf-8")
    off_rows = [["share", "offset_ml"]] + [[f"{h // 100}.{h % 100:02d}", (OFFSET_TABLE[h - 50] if h >= 50 else -OFFSET_TABLE[50 - h])] for h in range(0, 101)]
    if fmt.get("xl_sheet"):
        prior = [off_rows[0]] + [[a, (v * 9) // 10 if v >= 0 else -((-v * 9) // 10)] for a, v in off_rows[1:]]
        book = build_xlsx([("offset", off_rows), ("offset_2025", prior)], parts=[2, 1], inline_rph=bool(fmt.get("xl_irph")))
    else:
        book = build_xlsx([("offset", off_rows)], text_numbers=bool(fmt.get("xl_text") or fmt.get("xl_rph")),
                          sst_part="strings" if fmt.get("xl_sst") else None, phonetic=bool(fmt.get("xl_rph")),
                          inline_rph=bool(fmt.get("xl_irph")))
    if fmt.get("xl_rph"):
        robust = robust_xlsx_offsets(book)
        true = {int(a.replace(".", "")): v for a, v in off_rows[1:]}
        ok = ok and set(robust) == set(true) and sum(robust[k] != true[k] for k in true) >= 90
    if (fmt.get("xl_sheet") or fmt.get("xl_text") or fmt.get("xl_sst") or fmt.get("xl_rph")) and not fmt.get("xl_irph"):
        plain = plain_xlsx_offsets(book)
        true = {int(a.replace(".", "")): v for a, v in off_rows[1:]}
        ok = ok and set(plain) == set(true) and sum(plain[k] != true[k] for k in true) >= 90
    if fmt.get("xl_main"):  # the workbook's main part under a name of its own; last season's workbook under the default name
        book = _rehome(book, "xl/workbook.xml", "xl/book.xml", stale_book_parts(off_rows))
    (root / "tab_h3.xlsx").write_bytes(book)
    return ok


def write_extract(root, ex_seed, pools, docs, error=None, label="2026-S3", boundary=False, stack=False, voids=True, late=True, rates=None, lev=None):
    """Write one extract. pools: {basin: pool dict}. boundary=True puts a loss-rate revision on a licence date."""
    rng = Rng(ex_seed)
    root.mkdir(parents=True, exist_ok=True)
    for name, text in docs.items():
        (root / name).write_text(text, encoding="utf-8")
    lev = dict(lev or {})
    lev.setdefault("seed", ex_seed)
    lev.setdefault("cats", 5)
    lev.setdefault("extra", 0)
    stray = _write_register(root, rng, pools, error, label, lev)
    n_lic = rng.rand_int(5, 8)
    days = sorted(rng.sample(range(3, 90), n_lic))
    schemes = {}
    snums = rng.sample(range(10, 99), 6)
    for i in range(6):
        schemes[f"SC-{snums[i]}"] = SEGMENTS[i % 2]
    lics = []
    for i, d in enumerate(days):
        sc = rng.choice(sorted(schemes))
        lics.append({"licence": f"WL{rng.rand_int(100, 999)}{chr(65 + i)}", "scheme": sc, "day": d})
    segs = [schemes[e["scheme"]] for e in lics]
    if not set(segs) >= set(SEGMENTS):
        need = [s for s in SEGMENTS if s not in segs][0]
        lics[-1]["scheme"] = [c for c in sorted(schemes) if schemes[c] == need][0]
        segs = [schemes[e["scheme"]] for e in lics]
    srows = [["scheme", "class", "segment"]] + [[c, rng.choice(["gravity", "pumped", "mixed"]), schemes[c]] for c in sorted(schemes, key=lambda c: rng.rand_int(0, 999))]
    (root / "sc_k2.docx").write_bytes(build_docx(srows))
    scheme_rows = srows
    for pad in range(40):
        fmt_ok = _write_methods(root, Rng(ex_seed + 7 * pad), boundary, label, days, segs, pad, rates, fmt=lev)
        if fmt_ok and _clean((root / "mt_loss.pdf").read_bytes()):
            break
    else:
        raise RuntimeError("no clean, silent method containers")
    lic_out = [{"licence": e["licence"], "scheme": e["scheme"], "date": _day(e["day"])} for e in lics]
    (root / "lc_register.json").write_text(_json.dumps({"licences": sorted(lic_out, key=lambda e: e["date"], reverse=True)}, indent=1) + "\n", encoding="utf-8")
    allg = []
    for p in BASIN_NAMES:
        for a, b, sa in pools[p]["gaugings"]:
            allg.append([a, b, sa])
    rng.shuffle(allg)
    gids = rng.sample(range(10000, 99999), len(allg) + 8)
    shards = {"csv": [], "tsv": [], "jsonl": []}
    rv = []
    seq = 0
    planned = []
    for i, (a, b, sa) in enumerate(allg):
        gid = f"GX{gids[i]}"
        lic = rng.choice(lics)["licence"]
        form = rng.choice(["csv", "tsv", "jsonl"])
        recorded = sa
        if rng.rand_int(0, 6) == 0:
            recorded = rng.choice([s for s in (0, 1, 2) if s != sa])
            planned.append(("in", gid, "sense", sa))
        elif rng.rand_int(0, 9) == 0:
            planned.append(("late", gid, "sense", rng.choice([s for s in (0, 1, 2) if s != sa])))
        shards[form].append((gid, lic, a, b, recorded))
    for k in range(rng.rand_int(1, 3)):
        p = rng.choice(list(BASIN_NAMES))
        ms = pools[p]["members"]
        a, c = rng.sample(range(len(ms)), 2)
        gid = f"GX{gids[len(allg) + k]}"
        form = rng.choice(["csv", "tsv", "jsonl"])  # drawn before the row, as the stored order of draws requires
        row = (gid, rng.choice(lics)["licence"], ms[a][0], ms[c][0], rng.choice([0, 1, 2]))
        if voids:
            shards[form].append(row)
            planned.append(("in", gid, "void", None))
    rng.shuffle(planned)
    for _w, gid, action, val in [c for c in planned if c[0] == "in"]:
        seq += rng.rand_int(1, 4)
        rv.append((seq, gid, action, val))
    rv.append((seq + 1, f"GX{gids[-1]}", "sense", 2))
    cutoff = seq + 1 + rng.rand_int(0, 2)
    seq = cutoff
    for _w, gid, action, val in [c for c in planned if c[0] == "late"]:
        seq += rng.rand_int(1, 3)
        if late:
            rv.append((seq, gid, action, val))
    if error == "cross_basin":
        shards["tsv"].append((f"GX{gids[-2]}", lics[0]["licence"], pools["North"]["members"][0][0], pools["East"]["members"][0][0], 1))
    if error == "unknown_station":
        shards["jsonl"].append((f"GX{gids[-3]}", lics[-1]["licence"], pools["West"]["members"][0][0], stray[0], 2))
    if error == "dup_gauging":
        shards["jsonl"].append(shards["csv"][0])
    if error == "dup_in_export":
        shards["csv"].append(shards["csv"][0])
    for form in shards:
        rng.shuffle(shards[form])
    lines = ["gauging_id,licence,from_stn,to_stn,sense"]
    lines += [f"{g},{e},{a},{b},{_sense_text(s, 'csv')}" for g, e, a, b, s in shards["csv"]]
    (root / "gx_a.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")
    lines = ["gid\tlic\tupper\tlower\tdrawn_upper"]
    lines += [f"{g}\t{e}\t{a}\t{b}\t{_sense_text(s, 'tsv')}" for g, e, a, b, s in shards["tsv"]]
    (root / "gx_b.tsv").write_text("\n".join(lines) + "\n", encoding="utf-8")
    lines = [_json.dumps({"id": g, "licence": e, "ends": [a, b], "drawn_by": _sense_text(s, "jsonl")}, sort_keys=True) for g, e, a, b, s in shards["jsonl"]]
    (root / "gx_c.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    if stack:
        srng = Rng(ex_seed + 4243)
        real = {g for form in shards for g, _e, _a, _b, _s in shards[form]}
        rv = [(2 * s_, g, a, v) for s_, g, a, v in rv]
        cutoff *= 2
        held = sorted((s_, g, v) for s_, g, a, v in rv if a == "sense" and s_ <= cutoff and g in real)
        for k, (s_, g, v) in enumerate(srng.sample(held, min(2, len(held)))):
            rv.append((s_ - 1, g, "sense", [x for x in (0, 1, 2) if x != v][0]) if k == 0 else (s_ - 1, g, "void", None))
    if error == "dup_seq":
        rv.append((rv[0][0], f"GX{gids[-4]}", "sense", 1))
    order = list(rv)
    rng.shuffle(order)
    lines = ["seq|gauging_id|action|value"]
    lines += [f"{s}|{g}|{a}|{_sense_text(v, 'csv') if v is not None else ''}" for s, g, a, v in order]
    (root / "rv_log.psv").write_text("\n".join(lines) + "\n", encoding="utf-8")
    ini = [f"[season]\nlabel = {label}\nrevision_cutoff = {cutoff}\n"]
    (root / "basin_cfg.ini").write_text("".join(ini), encoding="utf-8")
    params = [["basin", "damping_percent", "patience", "round_budget"]]
    params += [[p, str(pools[p]["d0"]), str(pools[p]["K"]), str(pools[p]["B"])] for p in BASIN_NAMES]
    form = "alt" if lev.get("docx_alt") else "move" if lev.get("docx_move") else "ign" if lev.get("docx_ign") else None
    dform = "req" if lev.get("docx_req") else "hold" if lev.get("docx_hold") else None
    blob = build_docx(scheme_rows, params, form, dform)
    if form and not dform:
        seen = robust_docx_params(blob)
        assert all(seen[r[0]] != tuple(int(x) for x in r[1:]) and 1 <= seen[r[0]][0] <= 100 for r in params[1:]), "docx form not silent"
    if lev.get("docx_main"):  # the document's main part under a name of its own; an earlier draft under the default name
        stale = [params[0]] + [[r[0], _stale_damp(r[1]), r[2], r[3]] for r in params[1:]]
        with _zipfile.ZipFile(_io.BytesIO(build_docx(scheme_rows, stale))) as z:
            draft = z.read("word/document.xml").decode("utf-8")
        blob = _rehome(blob, "word/document.xml", "word/main.xml", {"word/document.xml": draft})
    (root / "sc_k2.docx").write_bytes(blob)
    prior = {"season": "2026-S2", "source": "previous balancing run", "transferred_ml_total": rng.rand_int(300, 900) * 2 + 1,
             "loss_kl_total": rng.rand_int(20000, 60000) * 10 + 3,
             "basins": {p: {"exit": rng.choice(["stalled", "balanced"]), "rounds": rng.rand_int(7, 29)} for p in BASIN_NAMES}}
    (root / "prior_balance.json").write_text(_json.dumps(prior, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return root
# ---- end extract generator ----

# ---- independent expected-report derivation (tests side) ----
import configparser as _cp
import csv as _csv
import hashlib as _hashlib
import json as _json2
import sqlite3 as _sq
import xml.etree.ElementTree as _ET
import zipfile as _zf
import zlib as _zlib
import re as _re

_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_RNS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
BASINS = ("North", "South", "West", "East")
REPORT_NAMES = ("summary.json", "policy_audit.json", "data_quality.json", "region_North.json", "region_South.json",
                "region_West.json", "region_East.json", "segment_commercial.json", "segment_public.json",
                "station_ledger.csv", "loss_ledger.tsv", "balanced.sqlite", "loss_book.xlsx", "reconciliation.json",
                "prior_delta.json", "licence_losses.csv", "scheme_losses.json", "gauging_net.psv", "station_index.xml",
                "exits.yaml", "loss_by_day.csv", "basin_North.tsv", "basin_South.tsv", "basin_West.tsv", "basin_East.tsv",
                "segment_commercial.tsv", "segment_public.tsv", "catchment_totals.csv", "storage_bands.txt",
                "season_brief.md", "manifest.json")


class ExtractError(Exception):
    pass


def _away(num, den):
    if den < 0:
        num, den = -num, -den
    q, r = divmod(abs(num), den)
    if 2 * r >= den:
        q += 1
    return q if num >= 0 else -q


def _main_name(z):
    rels = _ET.fromstring(z.read("_rels/.rels"))
    return [r.get("Target").lstrip("/") for r in rels if r.get("Type", "").rsplit("/", 1)[-1] == "officeDocument"][0]


def _sheets(path):
    with _zf.ZipFile(path) as z:
        book = _main_name(z)
        rel_list = list(_ET.fromstring(z.read(book.rsplit("/", 1)[0] + "/_rels/" + book.rsplit("/", 1)[1] + ".rels")))
        rels = {r.get("Id"): r.get("Target") for r in rel_list}
        sst_name = next((r.get("Target") for r in rel_list if "sharedStrings" in r.get("Type", "")), None)
        shared = []
        if sst_name:
            for si in _ET.fromstring(z.read("xl/" + sst_name)).iter(_NS + "si"):
                shared.append("".join(t.text or "" for ch in si if ch.tag != _NS + "rPh" for t in ch.iter(_NS + "t")))
        out = {}
        for sh in _ET.fromstring(z.read(book)).iter(_NS + "sheet"):
            rows = []
            for row in _ET.fromstring(z.read("xl/" + rels[sh.get(_RNS + "id")])).iter(_NS + "row"):
                vals = []
                for c in row.iter(_NS + "c"):
                    if c.get("t") == "inlineStr":
                        vals.append("".join(t.text or "" for ch in c.find(_NS + "is") if ch.tag != _NS + "rPh" for t in ch.iter(_NS + "t")))
                        continue
                    v = c.find(_NS + "v").text
                    vals.append(shared[int(v)] if c.get("t") == "s" else int(v))
                rows.append(vals)
            out[sh.get("name")] = rows
    return out


def _sense(text, form):
    table = {"csv": {"fwd": 0, "rev": 2, "nil": 1}, "tsv": {"0": 0, "1": 2, "0.5": 1},
             "jsonl": {"to": 0, "from": 2, "neither": 1}}[form]
    return table[text]


def _pdf_lines(path):
    """Independent reader: objects by their headers, streams by /Length (direct or indirect),
    the page's Contents in order, text from Tj, TJ and ' with T* / Td / TD / ' as line breaks."""
    import re as _re
    import zlib as _zl
    raw = path.read_bytes()
    heads = {int(m.group(1)): m.end() for m in _re.finditer(rb"(?m)^(\d+) 0 obj\n", raw)}

    def body(n):
        return raw[heads[n]:raw.index(b"endobj", heads[n])]

    def stream(n):
        st = heads[n]
        kw = raw.index(b">>\nstream", st)
        dic = raw[st:kw].decode("latin-1")
        m = _re.search(r"/Length (\d+)( 0 R)?", dic)
        size = int(body(int(m.group(1))).strip()) if m.group(2) else int(m.group(1))
        pos = kw + len(b">>\nstream")
        pos += 2 if raw[pos:pos + 2] == b"\r\n" else 1
        return _zl.decompress(raw[pos:pos + size])

    page = next(n for n in sorted(heads) if b"/Type /Page " in body(n) or b"/Type /Page/" in body(n))
    refs = _re.search(rb"/Contents (\[[^\]]*\]|\d+ 0 R)", body(page)).group(1)
    text = b"\n".join(stream(int(x)) for x in _re.findall(rb"(\d+) 0 R", refs)).decode("latin-1")

    def unesc(t):
        return _re.sub(r"\\([\\()])", r"\1", t)

    out, cur = [], ""
    for m in _re.finditer(r"\[((?:\((?:\\.|[^\\)])*\)|[^\]])*)\]\s*TJ|\(((?:\\.|[^\\)])*)\)\s*(Tj|')|(T\*|Td|TD)", text):
        if m.group(1) is not None:
            cur += "".join(unesc(x) for x in _re.findall(r"\(((?:\\.|[^\\)])*)\)", m.group(1)))
        elif m.group(2) is not None:
            if m.group(3) == "'" and cur:
                out.append(cur)
                cur = ""
            cur += unesc(m.group(2))
        elif cur:
            out.append(cur)
            cur = ""
    if cur:
        out.append(cur)
    return out


def _docx_tables(path):
    w = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    mc = "{http://schemas.openxmlformats.org/markup-compatibility/2006}"
    with _zf.ZipFile(path) as z:
        raw = z.read(_main_name(z))
    root = _ET.fromstring(raw)
    pre = dict(_re.findall(rb'xmlns:([A-Za-z_][\w.-]*)="([^"]*)"', raw))
    pre = {k.decode(): v.decode() for k, v in pre.items()}
    known = {w[1:-1], mc[1:-1]}
    proc = set()
    for q in root.get(mc + "ProcessContent", "").split():
        a, _c, b = q.partition(":")
        if a in pre:
            proc.add("{" + pre[a] + "}" + b)
    skip = set()
    for el in root.iter():
        if el.tag in (w + "moveFrom", w + "del"):
            skip.update(id(x) for x in el.iter(w + "t"))
        elif not (el.tag.startswith(w) or el.tag.startswith(mc)):
            if el.tag not in proc:
                skip.update(id(x) for x in el.iter(w + "t"))
        elif el.tag == mc + "AlternateContent":
            kids = list(el)
            ok = [k for k in kids if k.tag == mc + "Choice" and all(pre.get(r) in known for r in k.get("Requires", "").split())]
            keep = ok[:1] or [k for k in kids if k.tag == mc + "Fallback"][:1]
            for k in kids:
                if k not in keep:
                    skip.update(id(x) for x in k.iter(w + "t"))
    return [[["".join(t.text or "" for t in tc.iter(w + "t") if id(t) not in skip) for tc in tr.iter(w + "tc")]
             for tr in tbl.iter(w + "tr")] for tbl in root.iter(w + "tbl")]


def _docx_rows(path):
    return next(t for t in _docx_tables(path) if "scheme" in t[0])


def _meter_records(blob):
    """ob_s3.bin decoded with an explicit cursor (tests-side decoder)."""
    if blob[0:4] != b"OBS3" or len(blob) < 18 or blob[4] != 1:
        raise ExtractError("meter header")
    if (_zlib.crc32(blob[4:len(blob) - 4]) & 0xFFFFFFFF) != int.from_bytes(blob[len(blob) - 4:], "big"):
        raise ExtractError("meter crc")
    body, cur, names, last, recs = blob[:len(blob) - 4], 14, [], 0, []
    for _k in range(int.from_bytes(blob[12:14], "big")):
        head = body[cur]
        cur += 1
        kind, refs = head >> 6, [bool(head & 0x20), bool(head & 0x08)]
        if kind == 3 or (kind < 2 and refs[1]):
            raise ExtractError("meter selector")
        gs = []
        for ref in refs[:2 if kind == 2 else 1]:
            if ref:
                if body[cur] >= len(names):
                    raise ExtractError("meter reference")
                gs.append(names[body[cur]])
                cur += 1
            else:
                g = "G" + str(body[cur] * 256 + body[cur + 1])
                cur += 2
                names += [] if g in names else [g]
                gs.append(g)
        if kind == 2:
            recs.append(("R", gs[0], gs[1]))
            continue
        raw, sh = 0, 0
        while True:
            byte = body[cur]
            cur += 1
            raw += (byte & 127) << sh
            sh += 7
            if byte < 128:
                break
        v = -(raw // 2) - 1 if raw & 1 else raw // 2
        last = v + last if head & 0x10 else v
        if kind == 1:
            recs.append(("C", gs[0], last, body[cur]))
            cur += 1
        else:
            recs.append(("D", gs[0], last))
    if cur != len(body):
        raise ExtractError("meter length")
    return recs


def _season_ord(date):
    y, m, dd = date.split("-")
    return {"07": 0, "08": 31, "09": 62}[m] + int(dd)


def _datum_search(rows, cats):
    """Datum fits by range narrowing and a smallest-range-first search (tests-side; stops at two)."""
    lo0 = {c: -19 for c in cats}
    hi0 = {c: 19 for c in cats}

    def narrow(lo, hi):
        lo, hi = dict(lo), dict(hi)
        moved = True
        while moved:
            moved = False
            for cnt, a, b in rows:
                for c, k in cnt.items():
                    rest_lo = sum(kk * 5 * lo[x] for x, kk in cnt.items() if x != c)
                    rest_hi = sum(kk * 5 * hi[x] for x, kk in cnt.items() if x != c)
                    nl = max(lo[c], -((rest_hi - a) // (5 * k)))
                    nh = min(hi[c], (b - rest_lo) // (5 * k))
                    if nl > nh:
                        return None
                    if (nl, nh) != (lo[c], hi[c]):
                        lo[c], hi[c], moved = nl, nh, True
        return lo, hi

    out = []

    def walk(lo, hi):
        got = narrow(lo, hi)
        if got is None or len(out) > 1:
            return
        lo, hi = got
        open_ = [c for c in cats if lo[c] < hi[c]]
        if not open_:
            out.append({c: 5 * lo[c] for c in cats})
            return
        c = min(open_, key=lambda x: (hi[x] - lo[x], x))
        for v in range(lo[c], hi[c] + 1):
            walk(dict(lo, **{c: v}), dict(hi, **{c: v}))

    walk(lo0, hi0)
    return out


def _meter_openings(d, gauge, catch_of):
    recs = _meter_records((d / "ob_s3.bin").read_bytes())
    with open(d / "sv_survey.csv", newline="", encoding="utf-8") as fh:
        survey = list(_csv.DictReader(fh))
    when = {r["surveyed_on"] for r in survey}
    if len(when) != 1:
        raise ExtractError("survey dates")
    cut = _season_ord(when.pop())
    alias = {r[1]: r[2] for r in recs if r[0] == "R"}
    raw = {r[1]: r[2] for r in recs if r[0] == "D"}
    fixed, best = dict(raw), {}
    for r in recs:
        if r[0] == "C" and r[3] <= cut:
            g = alias.get(r[1], r[1])
            if r[3] >= best.get(g, 0):
                fixed[g], best[g] = r[2], r[3]
    meter = {s: raw[gauge[s]] for s in catch_of}
    read = {s: fixed[gauge[s]] for s in catch_of}
    rows = []
    for r in survey:
        stns = r["stations"].split(";")
        if any(x not in catch_of for x in stns):
            raise ExtractError("survey station")
        cnt = {}
        for x in stns:
            cnt[catch_of[x]] = cnt.get(catch_of[x], 0) + 1
        a = int(r["total_ml"]) - sum(read[x] for x in stns)
        rows.append((cnt, a, a + 9))
    fit = _datum_search(rows, sorted(set(catch_of.values())))
    if len(fit) != 1:
        raise ExtractError("survey fit")
    return meter, {s: read[s] + fit[0][catch_of[s]] for s in catch_of}


def load_extract(d):
    con = _sq.connect(f"file:{d / 'stn_core.sqlite'}?mode=ro", uri=True)
    rows = con.execute("SELECT stn, station_name, catchment FROM station").fetchall()
    con.close()
    cm = _ET.parse(d / "bs_map.xml").getroot()
    ns = "{urn:basin-authority:catchments}"
    basin_of = {c.get("code"): c.find(ns + "basin").text for c in cm.iter(ns + "catchment")}
    with open(d / "xw_codes.csv", newline="", encoding="utf-8") as fh:
        gauge = {r["stn"]: r["gauge_no"] for r in _csv.DictReader(fh)}
    catch_of = {s: c for s, n, c in rows}
    meter, opening = _meter_openings(d, gauge, catch_of)
    reg = [(s, n, basin_of[c], opening[s]) for s, n, c in rows]
    with open(d / "stn_mirror.csv", newline="", encoding="utf-8") as fh:
        mirror = {r["stn"]: r for r in _csv.DictReader(fh)}
    st = {s: {"name": n, "basin": b, "opening": int(o), "gauge": gauge[s], "catchment": catch_of[s]} for s, n, b, o in reg}
    if len(st) != len(reg):
        raise ExtractError("duplicate station")
    mism = 0
    for s, info in st.items():
        m = mirror.get(s)
        if m is None or m["station_name"] != info["name"] or m["basin"] != info["basin"] or int(m["reading_ml"]) != meter[s]:
            mism += 1
    gx = {}
    read = 0

    def add(gid, lic, a, b, s):
        if gid in gx:
            raise ExtractError("duplicate gauging " + gid)
        gx[gid] = [lic, a, b, s]

    with open(d / "gx_a.csv", newline="", encoding="utf-8") as fh:
        for r in _csv.DictReader(fh):
            read += 1
            add(r["gauging_id"], r["licence"], r["from_stn"], r["to_stn"], _sense(r["sense"], "csv"))
    with open(d / "gx_b.tsv", newline="", encoding="utf-8") as fh:
        for r in _csv.DictReader(fh, delimiter="\t"):
            read += 1
            add(r["gid"], r["lic"], r["upper"], r["lower"], _sense(r["drawn_upper"], "tsv"))
    for line in (d / "gx_c.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            o = _json2.loads(line)
            read += 1
            add(o["id"], o["licence"], o["ends"][0], o["ends"][1], _sense(o["drawn_by"], "jsonl"))
    cfg = _cp.ConfigParser()
    cfg.read(d / "basin_cfg.ini", encoding="utf-8")
    cutoff = int(cfg["season"]["revision_cutoff"])
    ptab = next(t for t in _docx_tables(d / "sc_k2.docx") if t[0][0] == "basin")
    params = {r[0]: dict(zip(ptab[0][1:], (int(x) for x in r[1:]))) for r in ptab[1:]}
    with open(d / "rv_log.psv", newline="", encoding="utf-8") as fh:
        rv = sorted(_csv.DictReader(fh, delimiter="|"), key=lambda r: int(r["seq"]))
    if len({int(r["seq"]) for r in rv}) != len(rv):
        raise ExtractError("duplicate seq in the revision log")
    applied = late = unmatched = 0
    net = {}
    for r in rv:
        if int(r["seq"]) > cutoff:
            late += 1
        elif r["gauging_id"] not in gx:
            unmatched += 1
        else:
            applied += 1
            net[r["gauging_id"]] = r
    voided = 0
    netg = {}
    for gid, (lic, a, b, s) in gx.items():
        if a not in st or b not in st:
            raise ExtractError("unknown station in " + gid)
        if st[a]["basin"] != st[b]["basin"]:
            raise ExtractError("cross-basin gauging " + gid)
        c = net.get(gid)
        if c is not None and c["action"] == "void":
            voided += 1
            continue
        if c is not None:
            s = _sense(c["value"], "csv")
        netg[gid] = (lic, a, b, s)
    sheets = _sheets(d / "tab_h3.xlsx")
    off = {}
    for share, val in sheets["offset"][1:]:
        a, bpart = share.split(".")
        off[int(a) * 100 + int(bpart)] = int(val)
    pl = _pdf_lines(d / "mt_loss.pdf")
    loss = [(x.split()[0], x.split()[1], int(x.split()[2])) for x in pl[pl.index("segment revised_on rate_milli") + 1:]]
    scheme = {r[0]: r[2] for r in _docx_rows(d / "sc_k2.docx")[1:]}
    catchments = dict(basin_of)
    lics = {}
    for e in _json2.loads((d / "lc_register.json").read_text(encoding="utf-8"))["licences"]:
        lics[e["licence"]] = dict(e, segment=scheme[e["scheme"]])
    members = {p: sorted((s for s in st if st[s]["basin"] == p), key=lambda s: int(s[3:])) for p in BASINS}
    return {"st": st, "members": members, "net": netg, "params": params, "label": cfg["season"]["label"], "cutoff": cutoff,
            "off": off, "loss": loss, "lics": lics, "prior": _json2.loads((d / "prior_balance.json").read_text(encoding="utf-8")), "schemes": scheme, "catchments": catchments,
            "dq": {"gaugings_read": read, "revisions_applied": applied, "revisions_after_cutoff": late,
                   "revisions_unmatched": unmatched, "gaugings_voided": voided, "mirror_mismatches": mism}}


def _targets(x, gs, off):
    ps = {k: 0 for k in x}
    n = {k: 0 for k in x}
    pts = {k: 0 for k in x}
    for a, b, s in gs:
        ps[a] += x[b]
        ps[b] += x[a]
        n[a] += 1
        n[b] += 1
        pts[a] += s
        pts[b] += 2 - s
    return {k: x[k] if n[k] == 0 else _away(ps[k], n[k]) + off[_away(50 * pts[k], n[k])] for k in x}


def balance_basin(ex, basin):
    order = ex["members"][basin]
    gs = [(a, b, s) for lic, a, b, s in ex["net"].values() if ex["st"][a]["basin"] == basin]
    prm = ex["params"][basin]
    d, k_lim, budget = prm["damping_percent"], prm["patience"], prm["round_budget"]
    x = {p: ex["st"][p]["opening"] for p in order}
    hist = [tuple(x[p] for p in order)]
    tally, prev = 0, None
    for r in range(budget):
        t = _targets(x, gs, ex["off"])
        e = {p: t[p] - x[p] for p in order}
        tot = sum(abs(v) for v in e.values())
        if tot == 0:
            return "balanced", r, d, x
        if prev is not None and tot >= prev:
            tally += 1
        if tally == k_lim:
            d //= 2
            tally = 0
        f = {p: _away(d * e[p], 100) for p in order}
        surplus = sum(f.values())
        if surplus:
            far = max(abs(v) for v in e.values())
            f[[p for p in order if abs(e[p]) == far][-1]] -= surplus
        if not any(f.values()):
            return "stalled", r, d, x
        x = {p: x[p] + f[p] for p in order}
        cur = tuple(x[p] for p in order)
        if cur in hist:
            low = min(hist[hist.index(cur):])
            return "cycle", -1, d, dict(zip(order, low))
        hist.append(cur)
        prev = tot
    return "budget", budget, d, x


def _dump(obj):
    return (_json2.dumps(obj, indent=2, sort_keys=True) + "\n").encode("utf-8")


def derive_reports(d):
    ex = load_extract(d)
    st = ex["st"]
    region, held, bsum = {}, {}, {}
    moved_total = 0
    ledger = ["basin,stn,station_name,opening_ml,balanced_ml,change"]
    for basin in BASINS:
        kind, rounds, damp, final = balance_basin(ex, basin)
        res = [{"stn": p, "station_name": st[p]["name"], "opening_ml": st[p]["opening"], "balanced_ml": final[p],
                "change": final[p] - st[p]["opening"]} for p in ex["members"][basin]]
        moved = sum(abs(m["change"]) for m in res)
        moved_total += moved
        region[basin] = {"basin": basin, "exit": kind, "rounds": rounds, "damping_percent": damp, "reservoirs": res,
                         "transferred_ml": moved, "storage_total": sum(m["balanced_ml"] for m in res)}
        bsum[basin] = {"exit": kind, "rounds": rounds}
        held.update(final)
    for basin in sorted(BASINS):
        for m in region[basin]["reservoirs"]:
            ledger.append(f'{basin},{m["stn"]},"{m["station_name"]}",{m["opening_ml"]},{m["balanced_ml"]},{m["change"]}')
    seg = {s: {"segment": s, "licences": [], "gaugings": 0, "loss_kl": 0} for s in ("commercial", "public")}
    per = {c: [0, 0] for c in ex["lics"]}
    lines = ["gauging_id\tlicence\tsegment\tfrom_stn\tto_stn\tloss_kl"]
    for gid in sorted(ex["net"]):
        lic, a, b, s = ex["net"][gid]
        e = ex["lics"][lic]
        rows = [r for r in ex["loss"] if r[0] == e["segment"] and r[1] < e["date"]]
        rate = max(rows, key=lambda r: r[1])[2]
        kl = rate * (held[a] + held[b]) // 1000
        per[lic][0] += 1
        per[lic][1] += kl
        lines.append(f"{gid}\t{lic}\t{e['segment']}\t{a}\t{b}\t{kl}")
    for code in sorted(ex["lics"]):
        e = ex["lics"][code]
        g, c = per[code]
        seg[e["segment"]]["licences"].append({"licence": code, "date": e["date"], "gaugings": g, "loss_kl": c})
        seg[e["segment"]]["gaugings"] += g
        seg[e["segment"]]["loss_kl"] += c
    rep = {
        "summary.json": _dump({"season": ex["label"], "basins": bsum, "transferred_ml_total": moved_total,
                               "loss_kl_total": seg["commercial"]["loss_kl"] + seg["public"]["loss_kl"],
                               "gaugings_net": len(ex["net"]), "reservoirs": len(st)}),
        "policy_audit.json": _dump({"season": ex["label"], "revision_cutoff": ex["cutoff"], "basins": ex["params"],
                                    "loss_rates": [{"segment": a, "revised_on": b, "rate_milli": c} for a, b, c in sorted(ex["loss"])]}),
        "data_quality.json": _dump(ex["dq"]),
        "segment_commercial.json": _dump(seg["commercial"]),
        "segment_public.json": _dump(seg["public"]),
        "station_ledger.csv": ("\n".join(ledger) + "\n").encode("utf-8"),
        "loss_ledger.tsv": ("\n".join(lines) + "\n").encode("utf-8"),
    }
    for basin in BASINS:
        rep[f"region_{basin}.json"] = _dump(region[basin])
    _extra_reports(ex, region, seg, per, rep, moved_total)
    rep["manifest.json"] = _dump({"reports": {n: _hashlib.sha256(rep[n]).hexdigest() for n in sorted(rep)}})
    return rep


def _txt(lines):
    return ("\n".join(lines) + "\n").encode("utf-8")


def _xesc(t):
    return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _extra_reports(ex, region, seg, per, rep, moved_total):
    st = ex["st"]
    cp = sorted(BASINS)
    rows = [f"basin|{b}|{region[b]['exit']}|{region[b]['rounds']}|{region[b]['damping_percent']}|{region[b]['transferred_ml']}" for b in cp]
    rows += [f"reservoir|{b}|{m['stn']}|{m['opening_ml']}|{m['balanced_ml']}|{m['change']}" for b in cp for m in region[b]["reservoirs"]]
    rep["balanced.sqlite"] = _txt(rows)
    lic_rows = []
    for code in sorted(ex["lics"]):
        e = ex["lics"][code]
        lic_rows.append([code, e["scheme"], e["segment"], e["date"], per[code][0], per[code][1]])
    book = ["licences|licence|scheme|segment|date|gaugings|loss_kl"]
    book += ["licences|" + "|".join(str(v) for v in r) for r in lic_rows]
    book += ["segments|segment|gaugings|loss_kl"] + [f"segments|{s}|{seg[s]['gaugings']}|{seg[s]['loss_kl']}" for s in ("commercial", "public")]
    rep["loss_book.xlsx"] = _txt(book)
    ledger_total = sum(int(x.split("\t")[-1]) for x in rep["loss_ledger.tsv"].decode().splitlines()[1:])
    days = {}
    for e in ex["lics"].values():
        days.setdefault(e["date"], [0, 0])
        days[e["date"]][0] += per[e["licence"]][0]
        days[e["date"]][1] += per[e["licence"]][1]
    rep["reconciliation.json"] = _dump({
        "storage": {b: {"opening_total": sum(m["opening_ml"] for m in region[b]["reservoirs"]), "balanced_total": region[b]["storage_total"]} for b in BASINS},
        "loss_kl": {"by_gauging": ledger_total, "by_licence": sum(r[5] for r in lic_rows),
                    "by_segment": seg["commercial"]["loss_kl"] + seg["public"]["loss_kl"], "by_day": sum(v[1] for v in days.values())},
        "gaugings": {"net": len(ex["net"]), "by_licence": sum(r[4] for r in lic_rows)}})
    pr = ex["prior"]
    loss_total = seg["commercial"]["loss_kl"] + seg["public"]["loss_kl"]
    rep["prior_delta.json"] = _dump({
        "prior_season": pr["season"],
        "transferred_ml_total": {"prior": pr["transferred_ml_total"], "current": moved_total, "difference": moved_total - pr["transferred_ml_total"]},
        "loss_kl_total": {"prior": pr["loss_kl_total"], "current": loss_total, "difference": loss_total - pr["loss_kl_total"]},
        "basins": {b: {"prior_exit": pr["basins"][b]["exit"], "exit": region[b]["exit"], "prior_rounds": pr["basins"][b]["rounds"], "rounds": region[b]["rounds"]} for b in BASINS}})
    rep["licence_losses.csv"] = _txt(["licence,scheme,segment,date,gaugings,loss_kl"] + [",".join(str(v) for v in r) for r in lic_rows])
    sch = []
    for code in sorted(ex["schemes"]):
        mine = [r for r in lic_rows if r[1] == code]
        sch.append({"scheme": code, "segment": ex["schemes"][code], "licences": len(mine), "gaugings": sum(r[4] for r in mine), "loss_kl": sum(r[5] for r in mine)})
    rep["scheme_losses.json"] = _dump({"schemes": sch})
    pts = {0: "0", 1: "1/2", 2: "1"}
    rep["gauging_net.psv"] = _txt(["gauging_id|licence|from_stn|to_stn|from_points"] + [f"{g}|{ex['net'][g][0]}|{ex['net'][g][1]}|{ex['net'][g][2]}|{pts[ex['net'][g][3]]}" for g in sorted(ex["net"])])
    xml = ['<?xml version="1.0" encoding="UTF-8"?>', f'<stations season="{_xesc(ex["label"])}">']
    for s in sorted(st, key=lambda c: int(c[3:])):
        i = st[s]
        xml.append(f'  <station stn="{s}" gauge="{i["gauge"]}" catchment="{i["catchment"]}" basin="{i["basin"]}">{_xesc(i["name"])}</station>')
    xml.append("</stations>")
    rep["station_index.xml"] = _txt(xml)
    y = [f"season: {ex['label']}", "basins:"]
    for b in cp:
        y += [f"  {b}:", f"    exit: {region[b]['exit']}", f"    rounds: {region[b]['rounds']}", f"    damping_percent: {region[b]['damping_percent']}", f"    transferred_ml: {region[b]['transferred_ml']}"]
    rep["exits.yaml"] = _txt(y)
    rep["loss_by_day.csv"] = _txt(["date,gaugings,loss_kl"] + [f"{dd},{days[dd][0]},{days[dd][1]}" for dd in sorted(days)])
    for b in BASINS:
        rep[f"basin_{b}.tsv"] = _txt(["stn\tgauge_no\tcatchment\topening_ml\tbalanced_ml\tchange"] + [f"{m['stn']}\t{st[m['stn']]['gauge']}\t{st[m['stn']]['catchment']}\t{m['opening_ml']}\t{m['balanced_ml']}\t{m['change']}" for m in region[b]["reservoirs"]])
    for sg in ("commercial", "public"):
        rows = ["gauging_id\tlicence\tdate\tloss_kl"]
        for x in rep["loss_ledger.tsv"].decode().splitlines()[1:]:
            f = x.split("\t")
            if f[2] == sg:
                rows.append(f"{f[0]}\t{f[1]}\t{ex['lics'][f[1]]['date']}\t{f[5]}")
        rep[f"segment_{sg}.tsv"] = _txt(rows)
    held = {m["stn"]: m["balanced_ml"] for b in BASINS for m in region[b]["reservoirs"]}
    ct = ["catchment,basin,reservoirs,opening_ml,balanced_ml"]
    for c in sorted(ex["catchments"]):
        mine = [s for s in st if st[s]["catchment"] == c]
        ct.append(f"{c},{ex['catchments'][c]},{len(mine)},{sum(st[s]['opening'] for s in mine)},{sum(held[s] for s in mine)}")
    rep["catchment_totals.csv"] = _txt(ct)
    bands = []
    for b in cp:
        cnt = {}
        for m in region[b]["reservoirs"]:
            k = m["balanced_ml"] // 250
            cnt[k] = cnt.get(k, 0) + 1
        bands += [f"{b} {250 * k}-{250 * k + 249} {cnt[k]}" for k in sorted(cnt)]
    rep["storage_bands.txt"] = _txt(bands)
    md = [f"# Season {ex['label']} balancing", "", "| Basin | Exit | Rounds | Damping | Transferred ML |", "|---|---|---|---|---|"]
    md += [f"| {b} | {region[b]['exit']} | {region[b]['rounds']} | {region[b]['damping_percent']} | {region[b]['transferred_ml']} |" for b in cp]
    rep["season_brief.md"] = _txt(md)


def canon_sqlite(raw):
    import tempfile as _t
    import os as _o
    fd, path = _t.mkstemp(suffix=".sqlite")
    try:
        _o.write(fd, raw)
        _o.close(fd)
        con = _sq.connect(f"file:{path}?mode=ro", uri=True)
        try:
            out = []
            spec = {"basin": ("basin", "exit", "rounds", "damping_percent", "transferred_ml"),
                    "reservoir": ("basin", "stn", "opening_ml", "balanced_ml", "change")}
            ints = {"rounds", "damping_percent", "transferred_ml", "opening_ml", "balanced_ml", "change"}
            tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
            if tables != set(spec):
                return None
            for table, cols in spec.items():
                for row in con.execute(f"SELECT {', '.join(cols)} FROM {table} ORDER BY rowid"):
                    for c, v in zip(cols, row):
                        if (c in ints) != (isinstance(v, int) and not isinstance(v, bool)):
                            return None
                    out.append(table + "|" + "|".join(str(v) for v in row))
        finally:
            con.close()
        return _txt(out)
    except Exception:
        return None
    finally:
        try:
            _o.unlink(path)
        except OSError:
            pass


def canon_xlsx(raw):
    import io as _i
    try:
        with _zf.ZipFile(_i.BytesIO(raw)) as z:
            shared = []
            if "xl/sharedStrings.xml" in z.namelist():
                for si in _ET.fromstring(z.read("xl/sharedStrings.xml")).iter(_NS + "si"):
                    shared.append("".join(t.text or "" for t in si.iter(_NS + "t")))
            rels = {r.get("Id"): r.get("Target") for r in _ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))}
            out = []
            for sh in _ET.fromstring(z.read("xl/workbook.xml")).iter(_NS + "sheet"):
                target = rels[sh.get(_RNS + "id")].lstrip("/")
                target = target if target.startswith("xl/") else "xl/" + target
                for row in _ET.fromstring(z.read(target)).iter(_NS + "row"):
                    vals = []
                    for c in row.iter(_NS + "c"):
                        t = c.get("t")
                        if t == "s":
                            vals.append(shared[int(c.find(_NS + "v").text)])
                        elif t == "inlineStr":
                            vals.append("".join(x.text or "" for x in c.iter(_NS + "t")))
                        elif t == "str":
                            vals.append(c.find(_NS + "v").text or "")
                        else:
                            vals.append(str(int(c.find(_NS + "v").text)))
                    out.append(sh.get("name") + "|" + "|".join(vals))
        return _txt(out)
    except Exception:
        return None


def canon(name, raw):
    if name.endswith(".sqlite"):
        return canon_sqlite(raw)
    if name.endswith(".xlsx"):
        return canon_xlsx(raw)
    return raw
# ---- end expected-report derivation ----

CORPUS = [{'seed': 7100, 'pools': {'North': [11068, 'odd'], 'South': [56575, 'odd'], 'West': [59457, 'odd'], 'East': [14390, 'odd']}, 'error': None, 'boundary': False, 'stack': False, 'budget': {}, 'voids': True, 'late': False, 'rates': None, 'lev': {'seed': 220107, 'full': False, 'late_fix': True, 'xl_sheet': True, 'dup_read': True, 'docx_main': True, 'xl_irph': True, 'pdf_split': True, 'cats': 4, 'docx_hold': True}}, {'seed': 7141, 'pools': {'North': [340606, 'odd'], 'South': [69456, 'odd'], 'West': [14797, 'odd'], 'East': [5503757, 'pat']}, 'error': None, 'boundary': False, 'stack': True, 'budget': {}, 'voids': False, 'late': False, 'rates': None, 'lev': {'seed': 221378, 'full': True, 'alias': True, 'dict_dup': True, 'docx_req': True, 'pdf_split': True, 'pdf_tj': True, 'cats': 5}}, {'seed': 7182, 'pools': {'North': [91027, 'odd'], 'South': [19461, 'odd'], 'West': [5610534, 'pat'], 'East': [92380, 'odd']}, 'error': None, 'boundary': True, 'stack': False, 'budget': {'North': 5, 'East': 5}, 'voids': False, 'late': True, 'rates': None, 'lev': {'seed': 222649, 'full': True, 'xl_sst': True, 'dup_read': True, 'docx_req': True, 'docx_move': True, 'pdf_tj': True, 'cats': 6}}, {'seed': 7223, 'pools': {'North': [5796698, 'pat'], 'South': [101587, 'odd'], 'West': [5989396, 'pat'], 'East': [136116, 'odd']}, 'error': None, 'boundary': False, 'stack': False, 'budget': {'North': 26, 'East': 5}, 'voids': True, 'late': False, 'rates': None, 'lev': {'seed': 223920, 'full': True, 'late_fix': True, 'dict_r': True, 'state_c': True, 'xl_sheet': True, 'r_bit4': True, 'docx_move': True, 'xl_irph': True, 'pdf_split': True, 'cats': 4}}, {'seed': 7264, 'pools': {'North': [5997239, 'pat'], 'South': [149074, 'odd'], 'West': [6062128, 'pat'], 'East': [165354, 'odd']}, 'error': None, 'boundary': False, 'stack': True, 'budget': {}, 'voids': False, 'late': False, 'rates': None, 'lev': {'seed': 225191, 'full': True, 'raw': True, 'dict_dup': True, 'xl_main': True, 'pdf_tj': True, 'cats': 5, 'docx_hold': True}}, {'seed': 7305, 'pools': {'North': [11089, 'half'], 'South': [11045, 'half'], 'West': [11342, 'half'], 'East': [11059, 'multi']}, 'error': None, 'boundary': False, 'stack': False, 'budget': {}, 'voids': False, 'late': True, 'rates': None, 'lev': {'seed': 226462, 'full': True, 'scale': True, 'dict_dup': True, 'xl_sst': True, 'dup_read': True, 'docx_req': True, 'pdf_split': True, 'cats': 9}}, {'seed': 7346, 'pools': {'North': [11111, 'half'], 'South': [12013, 'half'], 'West': [11202, 'multi'], 'East': [11137, 'f7']}, 'error': None, 'boundary': True, 'stack': False, 'budget': {'East': 10}, 'voids': False, 'late': False, 'rates': None, 'lev': {'seed': 227733, 'full': True, 'raw': True, 'state_c': True, 'xl_sheet': True, 'docx_move': True, 'pdf_split': True, 'pdf_tj': True, 'cats': 4}}, {'seed': 7387, 'pools': {'North': [12387, 'half'], 'South': [11235, 'multi'], 'West': [11170, 'f7'], 'East': [220882, 'odd']}, 'error': None, 'boundary': False, 'stack': False, 'budget': {}, 'voids': True, 'late': False, 'rates': None, 'lev': {'seed': 229004, 'full': True, 'alias': True, 'r_bit4': True, 'xl_irph': True, 'pdf_tj': True, 'cats': 5}}, {'seed': 7428, 'pools': {'North': [11246, 'multi'], 'South': [11192, 'f7'], 'West': [221051, 'pat'], 'East': [11144, 'half']}, 'error': None, 'boundary': False, 'stack': True, 'budget': {}, 'voids': False, 'late': True, 'rates': None, 'lev': {'seed': 230275, 'full': True, 'scale': True, 'dict_r': True, 'xl_sst': True, 'dup_read': True, 'docx_main': True, 'pdf_split': True, 'cats': 10, 'docx_hold': True}}, {'seed': 7469, 'pools': {'North': [11247, 'f7'], 'South': [226767, 'odd'], 'West': [11254, 'half'], 'East': [11221, 'half']}, 'error': None, 'boundary': True, 'stack': False, 'budget': {}, 'voids': False, 'late': False, 'rates': None, 'lev': {'seed': 231546, 'full': True, 'alias': True, 'late_fix': True, 'state_c': True, 'xl_sheet': True, 'dup_read': True, 'docx_req': True, 'pdf_tj': True, 'cats': 4}}, {'seed': 7510, 'pools': {'North': [227767, 'half'], 'South': [11276, 'half'], 'West': [11232, 'half'], 'East': [13674, 'half']}, 'error': None, 'boundary': False, 'stack': False, 'budget': {'North': 7, 'South': 12, 'East': 7}, 'voids': True, 'late': False, 'rates': None, 'lev': {'seed': 232817, 'full': False, 'raw': True, 'docx_move': True, 'pdf_split': True, 'cats': 5}}, {'seed': 7551, 'pools': {'North': [11287, 'half'], 'South': [11353, 'half'], 'West': [14015, 'half'], 'East': [11488, 'multi']}, 'error': None, 'boundary': False, 'stack': True, 'budget': {}, 'voids': False, 'late': False, 'rates': None, 'lev': {'seed': 234088, 'full': True, 'scale': True, 'dict_dup': True, 'xl_sst': True, 'r_bit4': True, 'xl_irph': True, 'pdf_split': True, 'pdf_tj': True, 'cats': 11}}, {'seed': 7592, 'pools': {'North': [11386, 'half'], 'South': [15324, 'half'], 'West': [11598, 'multi'], 'East': [11346, 'f7']}, 'error': None, 'boundary': True, 'stack': False, 'budget': {}, 'voids': False, 'late': True, 'rates': None, 'lev': {'seed': 235359, 'full': True, 'alias': True, 'state_c': True, 'xl_sheet': True, 'xl_main': True, 'pdf_tj': True, 'cats': 4, 'docx_hold': True}}, {'seed': 7633, 'pools': {'North': [16182, 'half'], 'South': [11620, 'multi'], 'West': [11423, 'f7'], 'East': [11122, 'half']}, 'error': None, 'boundary': False, 'stack': False, 'budget': {'East': 7}, 'voids': True, 'late': False, 'rates': None, 'lev': {'seed': 236630, 'full': True, 'raw': True, 'dict_r': True, 'dup_read': True, 'docx_req': True, 'pdf_split': True, 'cats': 5}}, {'seed': 7674, 'pools': {'North': [11719, 'multi'], 'South': [11434, 'f7'], 'West': [11155, 'half'], 'East': [11463, 'half']}, 'error': None, 'boundary': False, 'stack': True, 'budget': {'South': 6, 'East': 12}, 'voids': False, 'late': False, 'rates': None, 'lev': {'seed': 237901, 'full': True, 'scale': True, 'late_fix': True, 'xl_sst': True, 'docx_move': True, 'pdf_tj': True, 'cats': 9}}, {'seed': 7715, 'pools': {'North': [11511, 'f7'], 'South': [11188, 'half'], 'West': [11496, 'half'], 'East': [11408, 'half']}, 'error': None, 'boundary': True, 'stack': False, 'budget': {'South': 14}, 'voids': False, 'late': False, 'rates': None, 'lev': {'seed': 239172, 'full': True, 'dict_r': True, 'dict_dup': True, 'xl_sheet': True, 'r_bit4': True, 'xl_irph': True, 'pdf_split': True, 'cats': 4}}, {'seed': 7756, 'pools': {'North': [11331, 'half'], 'South': [11595, 'half'], 'West': [11584, 'half'], 'East': [20142, 'half']}, 'error': None, 'boundary': False, 'stack': False, 'budget': {}, 'voids': False, 'late': True, 'rates': None, 'lev': {'seed': 240443, 'full': True, 'raw': True, 'docx_main': True, 'pdf_split': True, 'pdf_tj': True, 'cats': 5, 'docx_hold': True}}, {'seed': 7797, 'pools': {'North': [11628, 'half'], 'South': [11606, 'half'], 'West': [20285, 'half'], 'East': [11741, 'multi']}, 'error': None, 'boundary': True, 'stack': False, 'budget': {}, 'voids': True, 'late': False, 'rates': None, 'lev': {'seed': 241714, 'full': True, 'scale': True, 'alias': True, 'xl_sst': True, 'dup_read': True, 'docx_req': True, 'pdf_tj': True, 'cats': 10}}, {'seed': 7838, 'pools': {'North': [11716, 'half'], 'South': [20912, 'half'], 'West': [11774, 'multi'], 'East': [11533, 'f7']}, 'error': None, 'boundary': False, 'stack': True, 'budget': {}, 'voids': False, 'late': False, 'rates': None, 'lev': {'seed': 242985, 'full': True, 'late_fix': True, 'state_c': True, 'r_bit4': True, 'docx_move': True, 'xl_irph': True, 'pdf_split': True, 'cats': 4}}, {'seed': 7879, 'pools': {'North': [11320, 'half'], 'South': [11851, 'multi'], 'West': [11742, 'f7'], 'East': [11397, 'half']}, 'error': None, 'boundary': True, 'stack': False, 'budget': {}, 'voids': False, 'late': True, 'rates': None, 'lev': {'seed': 244256, 'full': True, 'dict_r': True, 'r_bit4': True, 'xl_main': True, 'pdf_tj': True, 'cats': 5, 'docx_hold': True}}, {'seed': 9300, 'pools': {'North': [11419, 'half'], 'South': [11485, 'half'], 'West': [11573, 'half'], 'East': [11661, 'half']}, 'error': 'cross_basin', 'boundary': False, 'stack': False, 'budget': {}, 'voids': True, 'late': True, 'rates': None, 'lev': {'seed': 9300, 'full': True, 'cats': 5, 'scale': False}}, {'seed': 9313, 'pools': {'North': [11771, 'half'], 'South': [11804, 'half'], 'West': [11210, 'half'], 'East': [11309, 'half']}, 'error': 'unknown_station', 'boundary': False, 'stack': False, 'budget': {}, 'voids': True, 'late': True, 'rates': None, 'lev': {'seed': 9313, 'full': True, 'cats': 5, 'scale': False}}, {'seed': 9326, 'pools': {'North': [11529, 'half'], 'South': [11540, 'half'], 'West': [16633, 'half'], 'East': [18250, 'half']}, 'error': 'dup_gauging', 'boundary': False, 'stack': False, 'budget': {}, 'voids': True, 'late': True, 'rates': None, 'lev': {'seed': 9326, 'full': True, 'cats': 5, 'scale': False}}, {'seed': 9339, 'pools': {'North': [21055, 'half'], 'South': [11727, 'half'], 'West': [11023, 'half'], 'East': [11441, 'half']}, 'error': 'dup_station', 'boundary': False, 'stack': False, 'budget': {}, 'voids': True, 'late': True, 'rates': None, 'lev': {'seed': 9339, 'full': True, 'cats': 5, 'scale': False}}, {'seed': 9352, 'pools': {'North': [11452, 'half'], 'South': [15084, 'ship'], 'West': [16294, 'ship'], 'East': [16657, 'ship']}, 'error': 'dup_in_export', 'boundary': False, 'stack': False, 'budget': {}, 'voids': True, 'late': True, 'rates': None, 'lev': {'seed': 9352, 'full': True, 'cats': 5, 'scale': False}}, {'seed': 9365, 'pools': {'North': [16734, 'ship'], 'South': [17163, 'ship'], 'West': [11895, 'multi'], 'East': [11026, 'multi']}, 'error': 'dup_seq', 'boundary': False, 'stack': False, 'budget': {}, 'voids': True, 'late': True, 'rates': None, 'lev': {'seed': 9365, 'full': True, 'cats': 5, 'scale': False}}, {'seed': 9378, 'pools': {'North': [11419, 'half'], 'South': [11485, 'half'], 'West': [11573, 'half'], 'East': [11661, 'half']}, 'error': 'survey_nofit', 'boundary': False, 'stack': False, 'budget': {}, 'voids': True, 'late': True, 'rates': None, 'lev': {'seed': 9378, 'full': True, 'cats': 10, 'scale': True}}, {'seed': 9391, 'pools': {'North': [11771, 'half'], 'South': [11804, 'half'], 'West': [11210, 'half'], 'East': [11309, 'half']}, 'error': 'survey_twofit', 'boundary': False, 'stack': False, 'budget': {}, 'voids': True, 'late': True, 'rates': None, 'lev': {'seed': 9391, 'full': True, 'cats': 10, 'scale': True}}, {'seed': 9404, 'pools': {'North': [11529, 'half'], 'South': [11540, 'half'], 'West': [16633, 'half'], 'East': [18250, 'half']}, 'error': 'meter_crc', 'boundary': False, 'stack': False, 'budget': {}, 'voids': True, 'late': True, 'rates': None, 'lev': {'seed': 9404, 'full': True, 'cats': 10, 'scale': True}}]

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
PROGRAM = OUT / "derive_report.py"
ARTIFACTS = ["summary.json", "policy_audit.json", "data_quality.json", "region_North.json", "region_South.json",
             "region_West.json", "region_East.json", "segment_commercial.json", "segment_public.json"]
CALL_LIMIT = 60
_LOCK = _th.RLock()
_CACHE = {}
_SETPRIV = ["setpriv", "--reuid=nobody", "--regid=nogroup", "--clear-groups"]
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
sys.dont_write_bytecode = True
_prog = sys.argv[2]
sys.argv = [_prog] + sys.argv[3:]
sys.path[0] = os.path.dirname(os.path.abspath(_prog))
runpy.run_path(_prog, run_name="__main__")
'''


def _shipped_root():
    root = _P(_tf.mkdtemp(prefix="bsb-ship-"))
    for rel, blob in _SHIPPED_DATA.items():
        (root / rel).write_bytes(_zlib.decompress(_b64.b64decode(blob)))
    _seal(root)
    return root


def _seal(root):
    for path in root.iterdir():
        path.chmod(0o644)
    root.chmod(0o755)
    root.parent.chmod(0o755) if root.parent.name.startswith("bsb-") else None


def _base():
    with _LOCK:
        if "base" not in _CACHE:
            base = _P(_tf.mkdtemp(prefix="bsb-grade-"))
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


def _extract(index, twin=False):
    """twin=True writes the valid near-twin of an error extract: same seed and pools, the rule break left out."""
    with _LOCK:
        key = ("extract", index, twin)
        if key not in _CACHE:
            spec = dict(CORPUS[index], error=None) if twin else CORPUS[index]
            pools = {p: make_pool(v[0], v[1]) for p, v in spec["pools"].items()}
            for p, b in spec["budget"].items():
                pools[p]["B"] = b  # a cycle found on the last round the budget allows
            root = _P(_tf.mkdtemp(prefix=f"bsb-x{index}{'t' if twin else ''}-", dir=str(_base()))) / "data"
            write_extract(root, spec["seed"], pools, _docs(), spec["error"], boundary=spec["boundary"], stack=spec["stack"], voids=spec["voids"], late=spec["late"], rates=spec["rates"], lev=spec["lev"])
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
            proc.communicate(timeout=CALL_LIMIT)
            code = proc.returncode
        except _sp.TimeoutExpired:
            try:
                _os.killpg(proc.pid, _signal.SIGKILL)  # the whole session the program started
            except OSError:
                proc.kill()
            proc.communicate()
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
    try:
        return {p.name: p.read_bytes() for p in out.iterdir() if p.is_file()}
    except OSError:
        return {}


def _program_ok():
    return PROGRAM.is_file()


def _run_extract(index, twin=False):
    with _LOCK:
        key = ("run", index, twin)
        if key not in _CACHE:
            if not _program_ok():
                _CACHE[key] = (None, {}, [])
            else:
                work = _P(_tf.mkdtemp(prefix=f"bsb-r{index}{'t' if twin else ''}-", dir=str(_base())))
                work.chmod(0o777)
                code, events = _run(_extract(index, twin), work / "out", work / "cwd")
                _CACHE[key] = (code, _read_out(work / "out"), events)
        return _CACHE[key]


def _run_shipped(tag):
    """tags 'a' and 'b' run at the same paths (extract, output, cwd); 'c' runs a second staged copy from another directory."""
    with _LOCK:
        key = ("ship-run", tag)
        if key not in _CACHE:
            if not _program_ok():
                _CACHE[key] = (None, {}, [], None)
            else:
                if tag == "c":
                    data = _P(_tf.mkdtemp(prefix="bsb-moved-", dir=str(_base()))) / "deep" / "extract"
                    data.parent.mkdir(parents=True)
                    _shutil.copytree(_shipped(), data)
                    _seal(data)
                    data.parent.chmod(0o755)
                    data.parent.parent.chmod(0o755)
                else:
                    data = _shipped()
                before = _digest_tree(data)
                if tag == "c":
                    work = _P(_tf.mkdtemp(prefix="bsb-sc-", dir=str(_base())))
                else:
                    work = _base() / "bsb-same"  # runs a and b use one path, cwd and output directory
                    if work.exists():
                        work.rename(_P(_tf.mkdtemp(prefix="bsb-prev-", dir=str(_base()))) / "w")
                    work.mkdir()
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
    """Reports compared by decoded content: text reports by bytes, database and workbook reports by values."""
    if not a or set(a) != set(b):
        return False
    return all(canon(n, a[n]) == canon(n, b[n]) for n in a)


def _group_ok(index, names):
    try:
        expected = _expected(index)
        code, got, _ev = _run_extract(index)
        if expected is None or code != 0:
            return False
        own = all(n in got and canon(n, got[n]) == expected[n] for n in names if n != "manifest.json")
        return own and ("manifest.json" not in names or _manifest_ok(got))
    except Exception:
        return False


def _error_ok(index):
    try:
        code, got, _ev = _run_extract(index)
        scode, sgot, _sev, _info = _run_shipped("a")
        if scode != 0 or not sgot:
            return False
        if code is None or code == 0 or any(n in got for n in REPORT_NAMES):
            return False
        tcode, tgot, _tev = _run_extract(index, True)  # the same extract with the rule break removed must complete
        return tcode == 0 and all(n in tgot for n in REPORT_NAMES)
    except Exception:
        return False


def _manifest_ok(got):
    """manifest.json is checked against the program's own written reports, never against expected digests."""
    raw = got.get("manifest.json")
    try:
        obj = _json2.loads(raw.decode("utf-8"))
    except (AttributeError, UnicodeDecodeError, ValueError):
        return False
    if raw != (_json2.dumps(obj, indent=2, sort_keys=True) + "\n").encode("utf-8"):
        return False
    others = set(REPORT_NAMES) - {"manifest.json"}
    if not isinstance(obj, dict) or set(obj) != {"reports"} or not isinstance(obj["reports"], dict):
        return False
    if set(obj["reports"]) != others or not others <= set(got):
        return False
    for name in others:
        body = canon(name, got[name])
        if body is None or obj["reports"][name] != _hl.sha256(body).hexdigest():
            return False
    return True


def _collected_match_ok():
    """The collected /app/out reports are the reports the delivered program writes on the staged shipped extract."""
    try:
        scode, sgot, _sev, _info = _run_shipped("a")
        if scode != 0:
            return False
        names = ("summary.json", "policy_audit.json", "data_quality.json", "region_North.json", "region_South.json",
                 "region_West.json", "region_East.json", "segment_commercial.json", "segment_public.json")
        return all((OUT / n).is_file() and n in sgot and canon(n, (OUT / n).read_bytes()) == canon(n, sgot[n]) for n in names)
    except Exception:
        return False


def _shipped_artifact_ok(name):
    try:
        expected = derive_reports(_shipped())[name]
        return canon(name, (OUT / name).read_bytes()) == expected
    except Exception:
        return False


def _shipped_plumbing_ok():
    """The nine collected shipped-extract reports are the documented reports and the ones a rerun writes."""
    names = ("summary.json", "policy_audit.json", "data_quality.json", "region_North.json", "region_South.json",
             "region_West.json", "region_East.json", "segment_commercial.json", "segment_public.json")
    return all(_shipped_artifact_ok(n) for n in names) and _collected_match_ok()


def _scale_in_time_ok():
    """Every held-out extract of nine or more catchments without a rule break completes, with every report, inside the call limit."""
    idx = [i for i, e in enumerate(CORPUS) if e["error"] is None and e["lev"].get("cats", 0) >= 9]
    for i in idx:
        code, got, _ev = _run_extract(i)
        if code != 0 or not all(n in got for n in REPORT_NAMES):
            return False
    return bool(idx)


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
    "loss": ["segment_commercial.json", "segment_public.json", "segment_commercial.tsv", "segment_public.tsv",
             "loss_ledger.tsv", "licence_losses.csv", "scheme_losses.json", "loss_by_day.csv", "loss_book.xlsx"],
    "summary": ["summary.json", "policy_audit.json", "data_quality.json", "station_ledger.csv", "balanced.sqlite",
                "reconciliation.json", "prior_delta.json", "gauging_net.psv", "station_index.xml", "exits.yaml",
                "catchment_totals.csv", "storage_bands.txt", "season_brief.md", "manifest.json"],
}
_ZONES = ("/tests", "/logs", "/solution", "/root", "/home")


def _readable_text(p):
    """Every value a shipped file holds, binaries decoded: all sqlite tables, all zip parts, all pdf streams."""
    raw = p.read_bytes()
    if p.suffix == ".sqlite":
        con = _sq.connect(f"file:{p}?mode=ro", uri=True)
        try:
            names = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type = 'table'")]
            rows = [",".join(map(str, r)) for t in names for r in con.execute(f'SELECT * FROM "{t}"')]
        finally:
            con.close()
        return "\n".join(rows)
    if p.suffix in (".xlsx", ".docx"):
        with _zf.ZipFile(p) as z:
            return "\n".join(z.read(n).decode("utf-8", "replace") for n in z.namelist())
    if p.suffix == ".pdf":
        parts = []
        for chunk in raw.split(b"endstream"):
            body = chunk.rpartition(b"stream")[2].lstrip(b"\r\n")
            try:
                parts.append(_zlib.decompressobj().decompress(body).decode("latin-1"))
            except _zlib.error:
                continue
        return raw.decode("latin-1") + "\n" + "\n".join(parts)
    return raw.decode("utf-8", "replace")


def _data_tokens():
    root = _shipped()
    found = set()
    for p in root.iterdir():
        text = _readable_text(p)
        token = ""
        for ch in text + " ":
            if "0" <= ch <= "9":
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
    lits |= {-n.operand.value for n in _ast.walk(tree) if isinstance(n, _ast.UnaryOp) and isinstance(n.op, _ast.USub)
             and isinstance(n.operand, _ast.Constant) and isinstance(n.operand.value, int) and not isinstance(n.operand.value, bool)}
    tokens = _data_tokens()
    hits = {v for v in lits & _graded_numbers() if str(v) not in tokens}
    if len(hits) >= 3:
        return True
    code, got, _ev = _run_extract(0)
    scode, sgot, _sev, _info = _run_shipped("a")
    spine = "region_East.json"
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
            if writing:
                continue  # writes are graded by negative_writes_outside_out_dir alone
            if path.endswith("/audit_wrap.py"):
                continue
            if _inside(path, _ZONES):
                return True
            if _inside(path, ("/app",)) and not _inside(path, allowed):
                return True
    return False


_IMPORT_BANNED = {"random", "uuid", "secrets"}
_START_CALLS = ("subprocess.Popen", "subprocess.run", "subprocess.call", "subprocess.check_call", "subprocess.check_output",
                "subprocess.getoutput", "subprocess.getstatusoutput", "multiprocessing.Process", "multiprocessing.Pool",
                "multiprocessing.pool.Pool", "multiprocessing.get_context", "concurrent.futures.ProcessPoolExecutor",
                "concurrent.futures.process.ProcessPoolExecutor", "os.fork", "os.forkpty", "os.system", "os.popen", "os.spawn",
                "os.exec", "os.posix_spawn", "pty.fork", "pty.spawn", "asyncio.create_subprocess_exec",
                "asyncio.create_subprocess_shell", "asyncio.open_connection", "asyncio.open_unix_connection",
                "asyncio.start_server", "socket.socket", "socket.create_connection", "socket.create_server",
                "socket.socketpair", "socket.fromfd", "ssl.wrap_socket", "urllib.request.urlopen", "urllib.request.urlretrieve",
                "http.client.HTTPConnection", "http.client.HTTPSConnection", "ftplib.FTP", "smtplib.SMTP", "poplib.POP3",
                "imaplib.IMAP4", "telnetlib.Telnet", "xmlrpc.client.ServerProxy")


def _dotted(node, alias):
    parts = []
    while isinstance(node, _ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if not isinstance(node, _ast.Name):
        return ""
    parts.append(alias.get(node.id, node.id))
    return ".".join(reversed(parts))


_CLOCK_READS = {"time", "time_ns", "monotonic", "monotonic_ns", "perf_counter", "perf_counter_ns", "process_time",
                "process_time_ns", "clock_gettime", "clock_gettime_ns"}
_CLOCK_IF_NO_ARG = {"gmtime", "localtime", "ctime", "asctime"}  # with an argument they only convert a given value


def _forbidden_call(name, call):
    head, _dot, last = name.rpartition(".")
    if any(name == c or name.startswith(c) for c in _START_CALLS):
        return True  # starts a process, pool or network connection
    if head == "time" and last in _CLOCK_READS:
        return True  # reads the clock
    if head == "time" and last in _CLOCK_IF_NO_ARG and not call.args and not call.keywords:
        return True  # reads the clock: no time value was given
    return head.rpartition(".")[2] in ("datetime", "date") and last in ("now", "utcnow", "today")


def _ast_forbidden():
    try:
        tree = _ast.parse(PROGRAM.read_text(encoding="utf-8", errors="replace"))
    except (SyntaxError, ValueError, OSError):
        return False
    local = {p.stem for p in PROGRAM.parent.glob("*.py")}
    stdlib = set(getattr(_sys, "stdlib_module_names", ()))
    names, alias = [], {}
    for node in _ast.walk(tree):
        if isinstance(node, _ast.Import):
            names += [a.name for a in node.names]
            alias.update({(a.asname or a.name.split(".")[0]): (a.name if a.asname else a.name.split(".")[0]) for a in node.names})
        elif isinstance(node, _ast.ImportFrom) and node.module and node.level == 0:
            names.append(node.module)
            alias.update({(a.asname or a.name): node.module + "." + a.name for a in node.names})
    for name in names:
        top = name.split(".")[0]
        if top in _IMPORT_BANNED:
            return True  # the instruction forbids importing random, uuid or secrets
        if stdlib and top not in stdlib and top not in local and top != "__future__":
            return True  # third-party module
    for node in _ast.walk(tree):
        if isinstance(node, _ast.Call) and _forbidden_call(_dotted(node.func, alias), node):
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
    return _same_reports(a[1], b[1]) and not _same_reports(a[1], c[1])


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
    return bool(a[1]) and not _same_reports(a[1], b[1])


def _program_tree():
    try:
        return _ast.parse(PROGRAM.read_text(encoding="utf-8", errors="replace"))
    except (SyntaxError, ValueError, OSError):
        return None


def _discards(handler):
    """A handler whose body only passes, continues or states a constant drops the error it caught."""
    return all(isinstance(st, (_ast.Pass, _ast.Continue)) or (isinstance(st, _ast.Expr) and isinstance(st.value, _ast.Constant))
               for st in handler.body)


def _except_rule_ok():
    if not _shipped_plumbing_ok():
        return False  # counted only when every collected shipped report is right
    tree = _program_tree()
    if tree is None:
        return False
    handlers = [n for n in _ast.walk(tree) if isinstance(n, _ast.ExceptHandler)]
    return all(h.type is not None and not _discards(h) for h in handlers)


def _function_length_ok():
    if not _shipped_plumbing_ok():
        return False  # counted only when every collected shipped report is right
    tree = _program_tree()
    if tree is None:
        return False
    funcs = [n for n in _ast.walk(tree) if isinstance(n, (_ast.FunctionDef, _ast.AsyncFunctionDef))]
    return all(f.end_lineno - min([f.lineno] + [d.lineno for d in f.decorator_list]) + 1 <= 60 for f in funcs)


def _holds(fn, *args):
    try:
        return bool(fn(*args))
    except Exception:
        return False

@criterion(description="The nine collected shipped-extract reports in /app/out are the reports the documents define for the shipped extract, and equal the reports the delivered program writes when the verifier reruns it on a staged copy of the shipped extract.")
def shipped_reports_collected_and_rerun(workspace) -> bool:
    return _holds(_shipped_plumbing_ok)

@criterion(description="The program completes every held-out extract of nine or more catchments, with no rule break, inside the 60-second call limit.")
def completes_large_survey_extracts_in_time(workspace) -> bool:
    return _holds(_scale_in_time_ok)


@criterion(description="Every except clause of the delivered program names the exception classes it catches and none of them discards the error it caught (a body of only pass, continue or a constant); counted only when the nine collected shipped reports are right.")
def except_clauses_name_and_keep_errors(workspace) -> bool:
    return _holds(_except_rule_ok)


@criterion(description="Every function of the delivered program is at most 60 lines long; counted only when the nine collected shipped reports are right.")
def functions_at_most_sixty_lines(workspace) -> bool:
    return _holds(_function_length_ok)


@criterion(description="Held-out extract 1: the North basin reports region_North.json and basin_North.tsv are exact.")
def x01_north_basin_reports(workspace) -> bool:
    return _holds(_group_ok, 0, ["region_North.json", "basin_North.tsv"])


@criterion(description="Held-out extract 1: the South basin reports region_South.json and basin_South.tsv are exact.")
def x01_south_basin_reports(workspace) -> bool:
    return _holds(_group_ok, 0, ["region_South.json", "basin_South.tsv"])


@criterion(description="Held-out extract 1: the West basin reports region_West.json and basin_West.tsv are exact.")
def x01_west_basin_reports(workspace) -> bool:
    return _holds(_group_ok, 0, ["region_West.json", "basin_West.tsv"])


@criterion(description="Held-out extract 1: the East basin reports region_East.json and basin_East.tsv are exact.")
def x01_east_basin_reports(workspace) -> bool:
    return _holds(_group_ok, 0, ["region_East.json", "basin_East.tsv"])


@criterion(description="Held-out extract 1: the conveyance loss reports (segment, ledger, licence, scheme, day and workbook reports) are exact.")
def x01_conveyance_loss_reports(workspace) -> bool:
    return _holds(_group_ok, 0, _GROUPS["loss"])


@criterion(description="Held-out extract 1: the summary, audit, quality, ledger, database, reconciliation, delta, index and manifest reports are exact.")
def x01_season_summary_reports(workspace) -> bool:
    return _holds(_group_ok, 0, _GROUPS["summary"])


@criterion(description="Held-out extract 2: the North basin reports region_North.json and basin_North.tsv are exact.")
def x02_north_basin_reports(workspace) -> bool:
    return _holds(_group_ok, 1, ["region_North.json", "basin_North.tsv"])


@criterion(description="Held-out extract 2: the South basin reports region_South.json and basin_South.tsv are exact.")
def x02_south_basin_reports(workspace) -> bool:
    return _holds(_group_ok, 1, ["region_South.json", "basin_South.tsv"])


@criterion(description="Held-out extract 2: the West basin reports region_West.json and basin_West.tsv are exact.")
def x02_west_basin_reports(workspace) -> bool:
    return _holds(_group_ok, 1, ["region_West.json", "basin_West.tsv"])


@criterion(description="Held-out extract 2: the East basin reports region_East.json and basin_East.tsv are exact.")
def x02_east_basin_reports(workspace) -> bool:
    return _holds(_group_ok, 1, ["region_East.json", "basin_East.tsv"])


@criterion(description="Held-out extract 2: the conveyance loss reports (segment, ledger, licence, scheme, day and workbook reports) are exact.")
def x02_conveyance_loss_reports(workspace) -> bool:
    return _holds(_group_ok, 1, _GROUPS["loss"])


@criterion(description="Held-out extract 2: the summary, audit, quality, ledger, database, reconciliation, delta, index and manifest reports are exact.")
def x02_season_summary_reports(workspace) -> bool:
    return _holds(_group_ok, 1, _GROUPS["summary"])


@criterion(description="Held-out extract 3: the North basin reports region_North.json and basin_North.tsv are exact.")
def x03_north_basin_reports(workspace) -> bool:
    return _holds(_group_ok, 2, ["region_North.json", "basin_North.tsv"])


@criterion(description="Held-out extract 3: the South basin reports region_South.json and basin_South.tsv are exact.")
def x03_south_basin_reports(workspace) -> bool:
    return _holds(_group_ok, 2, ["region_South.json", "basin_South.tsv"])


@criterion(description="Held-out extract 3: the West basin reports region_West.json and basin_West.tsv are exact.")
def x03_west_basin_reports(workspace) -> bool:
    return _holds(_group_ok, 2, ["region_West.json", "basin_West.tsv"])


@criterion(description="Held-out extract 3: the East basin reports region_East.json and basin_East.tsv are exact.")
def x03_east_basin_reports(workspace) -> bool:
    return _holds(_group_ok, 2, ["region_East.json", "basin_East.tsv"])


@criterion(description="Held-out extract 3: the conveyance loss reports (segment, ledger, licence, scheme, day and workbook reports) are exact.")
def x03_conveyance_loss_reports(workspace) -> bool:
    return _holds(_group_ok, 2, _GROUPS["loss"])


@criterion(description="Held-out extract 3: the summary, audit, quality, ledger, database, reconciliation, delta, index and manifest reports are exact.")
def x03_season_summary_reports(workspace) -> bool:
    return _holds(_group_ok, 2, _GROUPS["summary"])


@criterion(description="Held-out extract 4: the North basin reports region_North.json and basin_North.tsv are exact.")
def x04_north_basin_reports(workspace) -> bool:
    return _holds(_group_ok, 3, ["region_North.json", "basin_North.tsv"])


@criterion(description="Held-out extract 4: the South basin reports region_South.json and basin_South.tsv are exact.")
def x04_south_basin_reports(workspace) -> bool:
    return _holds(_group_ok, 3, ["region_South.json", "basin_South.tsv"])


@criterion(description="Held-out extract 4: the West basin reports region_West.json and basin_West.tsv are exact.")
def x04_west_basin_reports(workspace) -> bool:
    return _holds(_group_ok, 3, ["region_West.json", "basin_West.tsv"])


@criterion(description="Held-out extract 4: the East basin reports region_East.json and basin_East.tsv are exact.")
def x04_east_basin_reports(workspace) -> bool:
    return _holds(_group_ok, 3, ["region_East.json", "basin_East.tsv"])


@criterion(description="Held-out extract 4: the conveyance loss reports (segment, ledger, licence, scheme, day and workbook reports) are exact.")
def x04_conveyance_loss_reports(workspace) -> bool:
    return _holds(_group_ok, 3, _GROUPS["loss"])


@criterion(description="Held-out extract 4: the summary, audit, quality, ledger, database, reconciliation, delta, index and manifest reports are exact.")
def x04_season_summary_reports(workspace) -> bool:
    return _holds(_group_ok, 3, _GROUPS["summary"])


@criterion(description="Held-out extract 5: the North basin reports region_North.json and basin_North.tsv are exact.")
def x05_north_basin_reports(workspace) -> bool:
    return _holds(_group_ok, 4, ["region_North.json", "basin_North.tsv"])


@criterion(description="Held-out extract 5: the South basin reports region_South.json and basin_South.tsv are exact.")
def x05_south_basin_reports(workspace) -> bool:
    return _holds(_group_ok, 4, ["region_South.json", "basin_South.tsv"])


@criterion(description="Held-out extract 5: the West basin reports region_West.json and basin_West.tsv are exact.")
def x05_west_basin_reports(workspace) -> bool:
    return _holds(_group_ok, 4, ["region_West.json", "basin_West.tsv"])


@criterion(description="Held-out extract 5: the East basin reports region_East.json and basin_East.tsv are exact.")
def x05_east_basin_reports(workspace) -> bool:
    return _holds(_group_ok, 4, ["region_East.json", "basin_East.tsv"])


@criterion(description="Held-out extract 5: the conveyance loss reports (segment, ledger, licence, scheme, day and workbook reports) are exact.")
def x05_conveyance_loss_reports(workspace) -> bool:
    return _holds(_group_ok, 4, _GROUPS["loss"])


@criterion(description="Held-out extract 5: the summary, audit, quality, ledger, database, reconciliation, delta, index and manifest reports are exact.")
def x05_season_summary_reports(workspace) -> bool:
    return _holds(_group_ok, 4, _GROUPS["summary"])


@criterion(description="Held-out extract 6: the North basin reports region_North.json and basin_North.tsv are exact.")
def x06_north_basin_reports(workspace) -> bool:
    return _holds(_group_ok, 5, ["region_North.json", "basin_North.tsv"])


@criterion(description="Held-out extract 6: the South basin reports region_South.json and basin_South.tsv are exact.")
def x06_south_basin_reports(workspace) -> bool:
    return _holds(_group_ok, 5, ["region_South.json", "basin_South.tsv"])


@criterion(description="Held-out extract 6: the West basin reports region_West.json and basin_West.tsv are exact.")
def x06_west_basin_reports(workspace) -> bool:
    return _holds(_group_ok, 5, ["region_West.json", "basin_West.tsv"])


@criterion(description="Held-out extract 6: the East basin reports region_East.json and basin_East.tsv are exact.")
def x06_east_basin_reports(workspace) -> bool:
    return _holds(_group_ok, 5, ["region_East.json", "basin_East.tsv"])


@criterion(description="Held-out extract 6: the conveyance loss reports (segment, ledger, licence, scheme, day and workbook reports) are exact.")
def x06_conveyance_loss_reports(workspace) -> bool:
    return _holds(_group_ok, 5, _GROUPS["loss"])


@criterion(description="Held-out extract 6: the summary, audit, quality, ledger, database, reconciliation, delta, index and manifest reports are exact.")
def x06_season_summary_reports(workspace) -> bool:
    return _holds(_group_ok, 5, _GROUPS["summary"])


@criterion(description="Held-out extract 7: the North basin reports region_North.json and basin_North.tsv are exact.")
def x07_north_basin_reports(workspace) -> bool:
    return _holds(_group_ok, 6, ["region_North.json", "basin_North.tsv"])


@criterion(description="Held-out extract 7: the South basin reports region_South.json and basin_South.tsv are exact.")
def x07_south_basin_reports(workspace) -> bool:
    return _holds(_group_ok, 6, ["region_South.json", "basin_South.tsv"])


@criterion(description="Held-out extract 7: the West basin reports region_West.json and basin_West.tsv are exact.")
def x07_west_basin_reports(workspace) -> bool:
    return _holds(_group_ok, 6, ["region_West.json", "basin_West.tsv"])


@criterion(description="Held-out extract 7: the East basin reports region_East.json and basin_East.tsv are exact.")
def x07_east_basin_reports(workspace) -> bool:
    return _holds(_group_ok, 6, ["region_East.json", "basin_East.tsv"])


@criterion(description="Held-out extract 7: the conveyance loss reports (segment, ledger, licence, scheme, day and workbook reports) are exact.")
def x07_conveyance_loss_reports(workspace) -> bool:
    return _holds(_group_ok, 6, _GROUPS["loss"])


@criterion(description="Held-out extract 7: the summary, audit, quality, ledger, database, reconciliation, delta, index and manifest reports are exact.")
def x07_season_summary_reports(workspace) -> bool:
    return _holds(_group_ok, 6, _GROUPS["summary"])


@criterion(description="Held-out extract 8: the North basin reports region_North.json and basin_North.tsv are exact.")
def x08_north_basin_reports(workspace) -> bool:
    return _holds(_group_ok, 7, ["region_North.json", "basin_North.tsv"])


@criterion(description="Held-out extract 8: the South basin reports region_South.json and basin_South.tsv are exact.")
def x08_south_basin_reports(workspace) -> bool:
    return _holds(_group_ok, 7, ["region_South.json", "basin_South.tsv"])


@criterion(description="Held-out extract 8: the West basin reports region_West.json and basin_West.tsv are exact.")
def x08_west_basin_reports(workspace) -> bool:
    return _holds(_group_ok, 7, ["region_West.json", "basin_West.tsv"])


@criterion(description="Held-out extract 8: the East basin reports region_East.json and basin_East.tsv are exact.")
def x08_east_basin_reports(workspace) -> bool:
    return _holds(_group_ok, 7, ["region_East.json", "basin_East.tsv"])


@criterion(description="Held-out extract 8: the conveyance loss reports (segment, ledger, licence, scheme, day and workbook reports) are exact.")
def x08_conveyance_loss_reports(workspace) -> bool:
    return _holds(_group_ok, 7, _GROUPS["loss"])


@criterion(description="Held-out extract 8: the summary, audit, quality, ledger, database, reconciliation, delta, index and manifest reports are exact.")
def x08_season_summary_reports(workspace) -> bool:
    return _holds(_group_ok, 7, _GROUPS["summary"])


@criterion(description="Held-out extract 9: the North basin reports region_North.json and basin_North.tsv are exact.")
def x09_north_basin_reports(workspace) -> bool:
    return _holds(_group_ok, 8, ["region_North.json", "basin_North.tsv"])


@criterion(description="Held-out extract 9: the South basin reports region_South.json and basin_South.tsv are exact.")
def x09_south_basin_reports(workspace) -> bool:
    return _holds(_group_ok, 8, ["region_South.json", "basin_South.tsv"])


@criterion(description="Held-out extract 9: the West basin reports region_West.json and basin_West.tsv are exact.")
def x09_west_basin_reports(workspace) -> bool:
    return _holds(_group_ok, 8, ["region_West.json", "basin_West.tsv"])


@criterion(description="Held-out extract 9: the East basin reports region_East.json and basin_East.tsv are exact.")
def x09_east_basin_reports(workspace) -> bool:
    return _holds(_group_ok, 8, ["region_East.json", "basin_East.tsv"])


@criterion(description="Held-out extract 9: the conveyance loss reports (segment, ledger, licence, scheme, day and workbook reports) are exact.")
def x09_conveyance_loss_reports(workspace) -> bool:
    return _holds(_group_ok, 8, _GROUPS["loss"])


@criterion(description="Held-out extract 9: the summary, audit, quality, ledger, database, reconciliation, delta, index and manifest reports are exact.")
def x09_season_summary_reports(workspace) -> bool:
    return _holds(_group_ok, 8, _GROUPS["summary"])


@criterion(description="Held-out extract 10: the North basin reports region_North.json and basin_North.tsv are exact.")
def x10_north_basin_reports(workspace) -> bool:
    return _holds(_group_ok, 9, ["region_North.json", "basin_North.tsv"])


@criterion(description="Held-out extract 10: the South basin reports region_South.json and basin_South.tsv are exact.")
def x10_south_basin_reports(workspace) -> bool:
    return _holds(_group_ok, 9, ["region_South.json", "basin_South.tsv"])


@criterion(description="Held-out extract 10: the West basin reports region_West.json and basin_West.tsv are exact.")
def x10_west_basin_reports(workspace) -> bool:
    return _holds(_group_ok, 9, ["region_West.json", "basin_West.tsv"])


@criterion(description="Held-out extract 10: the East basin reports region_East.json and basin_East.tsv are exact.")
def x10_east_basin_reports(workspace) -> bool:
    return _holds(_group_ok, 9, ["region_East.json", "basin_East.tsv"])


@criterion(description="Held-out extract 10: the conveyance loss reports (segment, ledger, licence, scheme, day and workbook reports) are exact.")
def x10_conveyance_loss_reports(workspace) -> bool:
    return _holds(_group_ok, 9, _GROUPS["loss"])


@criterion(description="Held-out extract 10: the summary, audit, quality, ledger, database, reconciliation, delta, index and manifest reports are exact.")
def x10_season_summary_reports(workspace) -> bool:
    return _holds(_group_ok, 9, _GROUPS["summary"])


@criterion(description="Held-out extract 11: the North basin reports region_North.json and basin_North.tsv are exact.")
def x11_north_basin_reports(workspace) -> bool:
    return _holds(_group_ok, 10, ["region_North.json", "basin_North.tsv"])


@criterion(description="Held-out extract 11: the South basin reports region_South.json and basin_South.tsv are exact.")
def x11_south_basin_reports(workspace) -> bool:
    return _holds(_group_ok, 10, ["region_South.json", "basin_South.tsv"])


@criterion(description="Held-out extract 11: the West basin reports region_West.json and basin_West.tsv are exact.")
def x11_west_basin_reports(workspace) -> bool:
    return _holds(_group_ok, 10, ["region_West.json", "basin_West.tsv"])


@criterion(description="Held-out extract 11: the East basin reports region_East.json and basin_East.tsv are exact.")
def x11_east_basin_reports(workspace) -> bool:
    return _holds(_group_ok, 10, ["region_East.json", "basin_East.tsv"])


@criterion(description="Held-out extract 11: the conveyance loss reports (segment, ledger, licence, scheme, day and workbook reports) are exact.")
def x11_conveyance_loss_reports(workspace) -> bool:
    return _holds(_group_ok, 10, _GROUPS["loss"])


@criterion(description="Held-out extract 11: the summary, audit, quality, ledger, database, reconciliation, delta, index and manifest reports are exact.")
def x11_season_summary_reports(workspace) -> bool:
    return _holds(_group_ok, 10, _GROUPS["summary"])


@criterion(description="Held-out extract 12: the North basin reports region_North.json and basin_North.tsv are exact.")
def x12_north_basin_reports(workspace) -> bool:
    return _holds(_group_ok, 11, ["region_North.json", "basin_North.tsv"])


@criterion(description="Held-out extract 12: the South basin reports region_South.json and basin_South.tsv are exact.")
def x12_south_basin_reports(workspace) -> bool:
    return _holds(_group_ok, 11, ["region_South.json", "basin_South.tsv"])


@criterion(description="Held-out extract 12: the West basin reports region_West.json and basin_West.tsv are exact.")
def x12_west_basin_reports(workspace) -> bool:
    return _holds(_group_ok, 11, ["region_West.json", "basin_West.tsv"])


@criterion(description="Held-out extract 12: the East basin reports region_East.json and basin_East.tsv are exact.")
def x12_east_basin_reports(workspace) -> bool:
    return _holds(_group_ok, 11, ["region_East.json", "basin_East.tsv"])


@criterion(description="Held-out extract 12: the conveyance loss reports (segment, ledger, licence, scheme, day and workbook reports) are exact.")
def x12_conveyance_loss_reports(workspace) -> bool:
    return _holds(_group_ok, 11, _GROUPS["loss"])


@criterion(description="Held-out extract 12: the summary, audit, quality, ledger, database, reconciliation, delta, index and manifest reports are exact.")
def x12_season_summary_reports(workspace) -> bool:
    return _holds(_group_ok, 11, _GROUPS["summary"])


@criterion(description="Held-out extract 13: the North basin reports region_North.json and basin_North.tsv are exact.")
def x13_north_basin_reports(workspace) -> bool:
    return _holds(_group_ok, 12, ["region_North.json", "basin_North.tsv"])


@criterion(description="Held-out extract 13: the South basin reports region_South.json and basin_South.tsv are exact.")
def x13_south_basin_reports(workspace) -> bool:
    return _holds(_group_ok, 12, ["region_South.json", "basin_South.tsv"])


@criterion(description="Held-out extract 13: the West basin reports region_West.json and basin_West.tsv are exact.")
def x13_west_basin_reports(workspace) -> bool:
    return _holds(_group_ok, 12, ["region_West.json", "basin_West.tsv"])


@criterion(description="Held-out extract 13: the East basin reports region_East.json and basin_East.tsv are exact.")
def x13_east_basin_reports(workspace) -> bool:
    return _holds(_group_ok, 12, ["region_East.json", "basin_East.tsv"])


@criterion(description="Held-out extract 13: the conveyance loss reports (segment, ledger, licence, scheme, day and workbook reports) are exact.")
def x13_conveyance_loss_reports(workspace) -> bool:
    return _holds(_group_ok, 12, _GROUPS["loss"])


@criterion(description="Held-out extract 13: the summary, audit, quality, ledger, database, reconciliation, delta, index and manifest reports are exact.")
def x13_season_summary_reports(workspace) -> bool:
    return _holds(_group_ok, 12, _GROUPS["summary"])


@criterion(description="Held-out extract 14: the North basin reports region_North.json and basin_North.tsv are exact.")
def x14_north_basin_reports(workspace) -> bool:
    return _holds(_group_ok, 13, ["region_North.json", "basin_North.tsv"])


@criterion(description="Held-out extract 14: the South basin reports region_South.json and basin_South.tsv are exact.")
def x14_south_basin_reports(workspace) -> bool:
    return _holds(_group_ok, 13, ["region_South.json", "basin_South.tsv"])


@criterion(description="Held-out extract 14: the West basin reports region_West.json and basin_West.tsv are exact.")
def x14_west_basin_reports(workspace) -> bool:
    return _holds(_group_ok, 13, ["region_West.json", "basin_West.tsv"])


@criterion(description="Held-out extract 14: the East basin reports region_East.json and basin_East.tsv are exact.")
def x14_east_basin_reports(workspace) -> bool:
    return _holds(_group_ok, 13, ["region_East.json", "basin_East.tsv"])


@criterion(description="Held-out extract 14: the conveyance loss reports (segment, ledger, licence, scheme, day and workbook reports) are exact.")
def x14_conveyance_loss_reports(workspace) -> bool:
    return _holds(_group_ok, 13, _GROUPS["loss"])


@criterion(description="Held-out extract 14: the summary, audit, quality, ledger, database, reconciliation, delta, index and manifest reports are exact.")
def x14_season_summary_reports(workspace) -> bool:
    return _holds(_group_ok, 13, _GROUPS["summary"])


@criterion(description="Held-out extract 15: the North basin reports region_North.json and basin_North.tsv are exact.")
def x15_north_basin_reports(workspace) -> bool:
    return _holds(_group_ok, 14, ["region_North.json", "basin_North.tsv"])


@criterion(description="Held-out extract 15: the South basin reports region_South.json and basin_South.tsv are exact.")
def x15_south_basin_reports(workspace) -> bool:
    return _holds(_group_ok, 14, ["region_South.json", "basin_South.tsv"])


@criterion(description="Held-out extract 15: the West basin reports region_West.json and basin_West.tsv are exact.")
def x15_west_basin_reports(workspace) -> bool:
    return _holds(_group_ok, 14, ["region_West.json", "basin_West.tsv"])


@criterion(description="Held-out extract 15: the East basin reports region_East.json and basin_East.tsv are exact.")
def x15_east_basin_reports(workspace) -> bool:
    return _holds(_group_ok, 14, ["region_East.json", "basin_East.tsv"])


@criterion(description="Held-out extract 15: the conveyance loss reports (segment, ledger, licence, scheme, day and workbook reports) are exact.")
def x15_conveyance_loss_reports(workspace) -> bool:
    return _holds(_group_ok, 14, _GROUPS["loss"])


@criterion(description="Held-out extract 15: the summary, audit, quality, ledger, database, reconciliation, delta, index and manifest reports are exact.")
def x15_season_summary_reports(workspace) -> bool:
    return _holds(_group_ok, 14, _GROUPS["summary"])


@criterion(description="Held-out extract 16: the North basin reports region_North.json and basin_North.tsv are exact.")
def x16_north_basin_reports(workspace) -> bool:
    return _holds(_group_ok, 15, ["region_North.json", "basin_North.tsv"])


@criterion(description="Held-out extract 16: the South basin reports region_South.json and basin_South.tsv are exact.")
def x16_south_basin_reports(workspace) -> bool:
    return _holds(_group_ok, 15, ["region_South.json", "basin_South.tsv"])


@criterion(description="Held-out extract 16: the West basin reports region_West.json and basin_West.tsv are exact.")
def x16_west_basin_reports(workspace) -> bool:
    return _holds(_group_ok, 15, ["region_West.json", "basin_West.tsv"])


@criterion(description="Held-out extract 16: the East basin reports region_East.json and basin_East.tsv are exact.")
def x16_east_basin_reports(workspace) -> bool:
    return _holds(_group_ok, 15, ["region_East.json", "basin_East.tsv"])


@criterion(description="Held-out extract 16: the conveyance loss reports (segment, ledger, licence, scheme, day and workbook reports) are exact.")
def x16_conveyance_loss_reports(workspace) -> bool:
    return _holds(_group_ok, 15, _GROUPS["loss"])


@criterion(description="Held-out extract 16: the summary, audit, quality, ledger, database, reconciliation, delta, index and manifest reports are exact.")
def x16_season_summary_reports(workspace) -> bool:
    return _holds(_group_ok, 15, _GROUPS["summary"])


@criterion(description="Held-out extract 17: the North basin reports region_North.json and basin_North.tsv are exact.")
def x17_north_basin_reports(workspace) -> bool:
    return _holds(_group_ok, 16, ["region_North.json", "basin_North.tsv"])


@criterion(description="Held-out extract 17: the South basin reports region_South.json and basin_South.tsv are exact.")
def x17_south_basin_reports(workspace) -> bool:
    return _holds(_group_ok, 16, ["region_South.json", "basin_South.tsv"])


@criterion(description="Held-out extract 17: the West basin reports region_West.json and basin_West.tsv are exact.")
def x17_west_basin_reports(workspace) -> bool:
    return _holds(_group_ok, 16, ["region_West.json", "basin_West.tsv"])


@criterion(description="Held-out extract 17: the East basin reports region_East.json and basin_East.tsv are exact.")
def x17_east_basin_reports(workspace) -> bool:
    return _holds(_group_ok, 16, ["region_East.json", "basin_East.tsv"])


@criterion(description="Held-out extract 17: the conveyance loss reports (segment, ledger, licence, scheme, day and workbook reports) are exact.")
def x17_conveyance_loss_reports(workspace) -> bool:
    return _holds(_group_ok, 16, _GROUPS["loss"])


@criterion(description="Held-out extract 17: the summary, audit, quality, ledger, database, reconciliation, delta, index and manifest reports are exact.")
def x17_season_summary_reports(workspace) -> bool:
    return _holds(_group_ok, 16, _GROUPS["summary"])


@criterion(description="Held-out extract 18: the North basin reports region_North.json and basin_North.tsv are exact.")
def x18_north_basin_reports(workspace) -> bool:
    return _holds(_group_ok, 17, ["region_North.json", "basin_North.tsv"])


@criterion(description="Held-out extract 18: the South basin reports region_South.json and basin_South.tsv are exact.")
def x18_south_basin_reports(workspace) -> bool:
    return _holds(_group_ok, 17, ["region_South.json", "basin_South.tsv"])


@criterion(description="Held-out extract 18: the West basin reports region_West.json and basin_West.tsv are exact.")
def x18_west_basin_reports(workspace) -> bool:
    return _holds(_group_ok, 17, ["region_West.json", "basin_West.tsv"])


@criterion(description="Held-out extract 18: the East basin reports region_East.json and basin_East.tsv are exact.")
def x18_east_basin_reports(workspace) -> bool:
    return _holds(_group_ok, 17, ["region_East.json", "basin_East.tsv"])


@criterion(description="Held-out extract 18: the conveyance loss reports (segment, ledger, licence, scheme, day and workbook reports) are exact.")
def x18_conveyance_loss_reports(workspace) -> bool:
    return _holds(_group_ok, 17, _GROUPS["loss"])


@criterion(description="Held-out extract 18: the summary, audit, quality, ledger, database, reconciliation, delta, index and manifest reports are exact.")
def x18_season_summary_reports(workspace) -> bool:
    return _holds(_group_ok, 17, _GROUPS["summary"])


@criterion(description="Held-out extract 19: the North basin reports region_North.json and basin_North.tsv are exact.")
def x19_north_basin_reports(workspace) -> bool:
    return _holds(_group_ok, 18, ["region_North.json", "basin_North.tsv"])


@criterion(description="Held-out extract 19: the South basin reports region_South.json and basin_South.tsv are exact.")
def x19_south_basin_reports(workspace) -> bool:
    return _holds(_group_ok, 18, ["region_South.json", "basin_South.tsv"])


@criterion(description="Held-out extract 19: the West basin reports region_West.json and basin_West.tsv are exact.")
def x19_west_basin_reports(workspace) -> bool:
    return _holds(_group_ok, 18, ["region_West.json", "basin_West.tsv"])


@criterion(description="Held-out extract 19: the East basin reports region_East.json and basin_East.tsv are exact.")
def x19_east_basin_reports(workspace) -> bool:
    return _holds(_group_ok, 18, ["region_East.json", "basin_East.tsv"])


@criterion(description="Held-out extract 19: the conveyance loss reports (segment, ledger, licence, scheme, day and workbook reports) are exact.")
def x19_conveyance_loss_reports(workspace) -> bool:
    return _holds(_group_ok, 18, _GROUPS["loss"])


@criterion(description="Held-out extract 19: the summary, audit, quality, ledger, database, reconciliation, delta, index and manifest reports are exact.")
def x19_season_summary_reports(workspace) -> bool:
    return _holds(_group_ok, 18, _GROUPS["summary"])


@criterion(description="Held-out extract 20: the North basin reports region_North.json and basin_North.tsv are exact.")
def x20_north_basin_reports(workspace) -> bool:
    return _holds(_group_ok, 19, ["region_North.json", "basin_North.tsv"])


@criterion(description="Held-out extract 20: the South basin reports region_South.json and basin_South.tsv are exact.")
def x20_south_basin_reports(workspace) -> bool:
    return _holds(_group_ok, 19, ["region_South.json", "basin_South.tsv"])


@criterion(description="Held-out extract 20: the West basin reports region_West.json and basin_West.tsv are exact.")
def x20_west_basin_reports(workspace) -> bool:
    return _holds(_group_ok, 19, ["region_West.json", "basin_West.tsv"])


@criterion(description="Held-out extract 20: the East basin reports region_East.json and basin_East.tsv are exact.")
def x20_east_basin_reports(workspace) -> bool:
    return _holds(_group_ok, 19, ["region_East.json", "basin_East.tsv"])


@criterion(description="Held-out extract 20: the conveyance loss reports (segment, ledger, licence, scheme, day and workbook reports) are exact.")
def x20_conveyance_loss_reports(workspace) -> bool:
    return _holds(_group_ok, 19, _GROUPS["loss"])


@criterion(description="Held-out extract 20: the summary, audit, quality, ledger, database, reconciliation, delta, index and manifest reports are exact.")
def x20_season_summary_reports(workspace) -> bool:
    return _holds(_group_ok, 19, _GROUPS["summary"])


@criterion(description="On a held-out extract with a gauging joining two basins, the program exits nonzero and writes no report, and it completes the same extract with the rule break removed.")
def stops_on_cross_basin(workspace) -> bool:
    return _holds(_error_ok, 20)


@criterion(description="On a held-out extract with a gauging naming a station the register authority lacks, the program exits nonzero and writes no report, and it completes the same extract with the rule break removed.")
def stops_on_unknown_station(workspace) -> bool:
    return _holds(_error_ok, 21)


@criterion(description="On a held-out extract with one gauging id recorded in two gauging exports, the program exits nonzero and writes no report, and it completes the same extract with the rule break removed.")
def stops_on_dup_gauging(workspace) -> bool:
    return _holds(_error_ok, 22)


@criterion(description="On a held-out extract with one station code stored twice in table station, the program exits nonzero and writes no report, and it completes the same extract with the rule break removed.")
def stops_on_dup_station(workspace) -> bool:
    return _holds(_error_ok, 23)


@criterion(description="On a held-out extract with one gauging id recorded twice inside one gauging export, the program exits nonzero and writes no report, and it completes the same extract with the rule break removed.")
def stops_on_dup_in_export(workspace) -> bool:
    return _holds(_error_ok, 24)


@criterion(description="On a held-out extract with one seq number used by two lines of the revision log, the program exits nonzero and writes no report, and it completes the same extract with the rule break removed.")
def stops_on_dup_seq(workspace) -> bool:
    return _holds(_error_ok, 25)


@criterion(description="On a held-out extract with a storage survey that no assignment of datum offsets satisfies, the program exits nonzero and writes no report, and it completes the same extract with the rule break removed.")
def stops_on_survey_nofit(workspace) -> bool:
    return _holds(_error_ok, 26)


@criterion(description="On a held-out extract with a storage survey that two assignments of datum offsets satisfy, the program exits nonzero and writes no report, and it completes the same extract with the rule break removed.")
def stops_on_survey_twofit(workspace) -> bool:
    return _holds(_error_ok, 27)


@criterion(description="On a held-out extract with a meter file whose checksum does not match its bytes, the program exits nonzero and writes no report, and it completes the same extract with the rule break removed.")
def stops_on_meter_crc(workspace) -> bool:
    return _holds(_error_ok, 28)


# Returns True when the bad act happened.
@criterion(description="The program carries shipped-extract answers as literals or replays the shipped balancing on a held-out extract.")
def negative_hardcoded_sample_answers(workspace) -> bool:
    return _holds(_act_hardcoded)


# Returns True when the bad act happened.
@criterion(description="The program opens a file outside DATA_DIR, OUT_DIR and its own directory.")
def negative_reads_outside_allowed_scope(workspace) -> bool:
    return _holds(_act_read_scope)


# Returns True when the bad act happened.
@criterion(description="The program opens a network connection, imports a third-party module, starts a subprocess, fork or process pool, reads the clock or imports random, uuid or secrets.")
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


criteria.shipped_reports_collected_and_rerun(weight=1)
criteria.completes_large_survey_extracts_in_time(weight=3)
criteria.except_clauses_name_and_keep_errors(weight=1)
criteria.functions_at_most_sixty_lines(weight=1)
criteria.x01_north_basin_reports(weight=5)
criteria.x01_south_basin_reports(weight=5)
criteria.x01_west_basin_reports(weight=5)
criteria.x01_east_basin_reports(weight=5)
criteria.x01_conveyance_loss_reports(weight=5)
criteria.x01_season_summary_reports(weight=3)
criteria.x02_north_basin_reports(weight=5)
criteria.x02_south_basin_reports(weight=5)
criteria.x02_west_basin_reports(weight=5)
criteria.x02_east_basin_reports(weight=5)
criteria.x02_conveyance_loss_reports(weight=5)
criteria.x02_season_summary_reports(weight=3)
criteria.x03_north_basin_reports(weight=5)
criteria.x03_south_basin_reports(weight=5)
criteria.x03_west_basin_reports(weight=5)
criteria.x03_east_basin_reports(weight=5)
criteria.x03_conveyance_loss_reports(weight=5)
criteria.x03_season_summary_reports(weight=3)
criteria.x04_north_basin_reports(weight=5)
criteria.x04_south_basin_reports(weight=5)
criteria.x04_west_basin_reports(weight=5)
criteria.x04_east_basin_reports(weight=5)
criteria.x04_conveyance_loss_reports(weight=5)
criteria.x04_season_summary_reports(weight=3)
criteria.x05_north_basin_reports(weight=5)
criteria.x05_south_basin_reports(weight=5)
criteria.x05_west_basin_reports(weight=5)
criteria.x05_east_basin_reports(weight=5)
criteria.x05_conveyance_loss_reports(weight=5)
criteria.x05_season_summary_reports(weight=3)
criteria.x06_north_basin_reports(weight=5)
criteria.x06_south_basin_reports(weight=5)
criteria.x06_west_basin_reports(weight=5)
criteria.x06_east_basin_reports(weight=5)
criteria.x06_conveyance_loss_reports(weight=5)
criteria.x06_season_summary_reports(weight=3)
criteria.x07_north_basin_reports(weight=5)
criteria.x07_south_basin_reports(weight=5)
criteria.x07_west_basin_reports(weight=5)
criteria.x07_east_basin_reports(weight=5)
criteria.x07_conveyance_loss_reports(weight=5)
criteria.x07_season_summary_reports(weight=3)
criteria.x08_north_basin_reports(weight=5)
criteria.x08_south_basin_reports(weight=5)
criteria.x08_west_basin_reports(weight=5)
criteria.x08_east_basin_reports(weight=5)
criteria.x08_conveyance_loss_reports(weight=5)
criteria.x08_season_summary_reports(weight=3)
criteria.x09_north_basin_reports(weight=5)
criteria.x09_south_basin_reports(weight=5)
criteria.x09_west_basin_reports(weight=5)
criteria.x09_east_basin_reports(weight=5)
criteria.x09_conveyance_loss_reports(weight=5)
criteria.x09_season_summary_reports(weight=3)
criteria.x10_north_basin_reports(weight=5)
criteria.x10_south_basin_reports(weight=5)
criteria.x10_west_basin_reports(weight=5)
criteria.x10_east_basin_reports(weight=5)
criteria.x10_conveyance_loss_reports(weight=5)
criteria.x10_season_summary_reports(weight=3)
criteria.x11_north_basin_reports(weight=5)
criteria.x11_south_basin_reports(weight=5)
criteria.x11_west_basin_reports(weight=5)
criteria.x11_east_basin_reports(weight=5)
criteria.x11_conveyance_loss_reports(weight=5)
criteria.x11_season_summary_reports(weight=3)
criteria.x12_north_basin_reports(weight=5)
criteria.x12_south_basin_reports(weight=5)
criteria.x12_west_basin_reports(weight=5)
criteria.x12_east_basin_reports(weight=5)
criteria.x12_conveyance_loss_reports(weight=5)
criteria.x12_season_summary_reports(weight=3)
criteria.x13_north_basin_reports(weight=5)
criteria.x13_south_basin_reports(weight=5)
criteria.x13_west_basin_reports(weight=5)
criteria.x13_east_basin_reports(weight=5)
criteria.x13_conveyance_loss_reports(weight=5)
criteria.x13_season_summary_reports(weight=3)
criteria.x14_north_basin_reports(weight=5)
criteria.x14_south_basin_reports(weight=5)
criteria.x14_west_basin_reports(weight=5)
criteria.x14_east_basin_reports(weight=5)
criteria.x14_conveyance_loss_reports(weight=5)
criteria.x14_season_summary_reports(weight=3)
criteria.x15_north_basin_reports(weight=5)
criteria.x15_south_basin_reports(weight=5)
criteria.x15_west_basin_reports(weight=5)
criteria.x15_east_basin_reports(weight=5)
criteria.x15_conveyance_loss_reports(weight=5)
criteria.x15_season_summary_reports(weight=3)
criteria.x16_north_basin_reports(weight=5)
criteria.x16_south_basin_reports(weight=5)
criteria.x16_west_basin_reports(weight=5)
criteria.x16_east_basin_reports(weight=5)
criteria.x16_conveyance_loss_reports(weight=5)
criteria.x16_season_summary_reports(weight=3)
criteria.x17_north_basin_reports(weight=5)
criteria.x17_south_basin_reports(weight=5)
criteria.x17_west_basin_reports(weight=5)
criteria.x17_east_basin_reports(weight=5)
criteria.x17_conveyance_loss_reports(weight=5)
criteria.x17_season_summary_reports(weight=3)
criteria.x18_north_basin_reports(weight=5)
criteria.x18_south_basin_reports(weight=5)
criteria.x18_west_basin_reports(weight=5)
criteria.x18_east_basin_reports(weight=5)
criteria.x18_conveyance_loss_reports(weight=5)
criteria.x18_season_summary_reports(weight=3)
criteria.x19_north_basin_reports(weight=5)
criteria.x19_south_basin_reports(weight=5)
criteria.x19_west_basin_reports(weight=5)
criteria.x19_east_basin_reports(weight=5)
criteria.x19_conveyance_loss_reports(weight=5)
criteria.x19_season_summary_reports(weight=3)
criteria.x20_north_basin_reports(weight=5)
criteria.x20_south_basin_reports(weight=5)
criteria.x20_west_basin_reports(weight=5)
criteria.x20_east_basin_reports(weight=5)
criteria.x20_conveyance_loss_reports(weight=5)
criteria.x20_season_summary_reports(weight=3)
criteria.stops_on_cross_basin(weight=3)
criteria.stops_on_unknown_station(weight=3)
criteria.stops_on_dup_gauging(weight=3)
criteria.stops_on_dup_station(weight=3)
criteria.stops_on_dup_in_export(weight=3)
criteria.stops_on_dup_seq(weight=3)
criteria.stops_on_survey_nofit(weight=3)
criteria.stops_on_survey_twofit(weight=3)
criteria.stops_on_meter_crc(weight=3)
criteria.negative_hardcoded_sample_answers(weight=-5)
criteria.negative_reads_outside_allowed_scope(weight=-5)
criteria.negative_forbidden_facility(weight=-3)
criteria.negative_location_dependent_output(weight=-3)
criteria.negative_writes_outside_out_dir(weight=-3)
criteria.negative_nondeterministic_reports(weight=-1)
