# Calibration slice

The engine writes eleven quantities into its captures that no shipped file
states. For each one the set of values it may take is published here, together
with one control figure. The figures are published in an order in which each is
fixed by the quantities the figures ahead of it pin, together with one further
quantity. At least one value of that further quantity reproduces the figure, and
the value the engine used is one of them.

Every control figure is the twelve-character digest this engine stamps over the
material the row names.

| quantity | candidate values | control | the control reads |
| --- | --- | --- | --- |
| `frame_bias_limit` | 4 through 15 | CTRL-A | the frame bias the capture headers carry |
| `weave_seed_offset` | 17 through 30 | CTRL-B | the payload line order inside every block |
| `sentinel_code_value` | 200 through 215 | CTRL-C | the payload bytes once the reserved byte is unwrapped |
| `drift_modulus` | 5 through 16 | CTRL-D | the payload bytes once the block mask is lifted |
| `seal_label_index` | 0 through 11 | CTRL-E | the opening payload of every capture once the label mask is lifted |
| `spin_modulus` | 7 through 18 | CTRL-F | the opening entry of every capture once its bytes are set straight |
| `shadow_pad_base` | 3 through 14 | CTRL-G | every entry of every capture once the padding is set aside |
| `alias_donor_shift` | 1 through 10 | CTRL-H | every entry once the recorded words are read against the right table |
| `echo_window_span` | 2 through 13 | CTRL-I | every entry once the repeated slots take the payload they inherit |
| `cadence_modulus` | 2 through 11 | CTRL-J | the cadence class every surviving unit falls in |
| `upkeep_target_scale` | 11 through 22 | CTRL-K | the upkeep target the engine settles against |

| control | published figure |
| --- | --- |
| CTRL-A | `e06544fda91a` |
| CTRL-B | `6de353b13e0d` |
| CTRL-C | `5ca8d54f2e85` |
| CTRL-D | `d48421311491` |
| CTRL-E | `54619f819922` |
| CTRL-F | `26c44f4c6e4a` |
| CTRL-G | `3e17132d6284` |
| CTRL-H | `e04399bf5857` |
| CTRL-I | `175a8793b874` |
| CTRL-J | `a2e4b1a2a02c` |
| CTRL-K | `a0320f91a53c` |

A candidate is rejected against the first control figure in the order above
that separates it from the value the engine used.

## Fragments each control reads

A control figure is stamped over the list of fragments its row below names, in
the order given there.

For CTRL-A through CTRL-I the list holds one fragment for every capture of the
set, the captures whose flag word is zero included, in ascending capture
ordinal. Each such fragment is the capture ordinal in decimal, a colon, and the
body the row names. A step that undoes a transform acts only on a capture whose
flag word sets that transform's bit; a capture with the bit clear passes
through that step unchanged. Every quantity a step reads takes the value the
figures ahead of it pinned, and the quantity the row pins takes the candidate
under test.

Terms used in the rows:

- A payload list is the payload of every entry line of the capture, block by
  block in the order the block lines appear and line by line inside each
  block, every declared line counted, filler included. Each payload is written
  in lowercase hexadecimal, two digits per byte, and the payloads are joined
  by commas with no spaces.
- To unpack a twelve-byte payload is to read it with the layout in the format
  note: big endian, except that every multi-byte field is little endian inside
  the flipped block of a flipped capture. A payload whose check field does not
  match the ten bytes before it unpacks to nothing.
- An entry text is the tick, the unit index, the kind, the amount and the mark
  of an unpacked payload, each in decimal, joined by solidi with no spaces, as
  in `40/3/1/2400/9`. A payload that unpacks to nothing is written `none`.
- A word entry text is an entry text with the unit word in place of the unit
  index, as in `40/hydra/1/2400/9`.

Each capture's fragment body for CTRL-A through CTRL-I is the following.

- CTRL-A: The frame bias: three times the capture ordinal plus one, taken
  against `frame_bias_limit`, for a padded capture, and `0` for any other. An
  unpadded capture of ordinal 1 gives `1:0`.

- CTRL-B: The payload list once the woven lines of each block stand back in
  place: the line read at restated position p moves to the position the
  finished order records at p. A doubled reserved byte is still written twice.

- CTRL-C: The CTRL-B payload list with every doubled reserved byte written
  once. A payload that holds the reserved byte once on its own, or that does
  not come out at twelve bytes, is written as twenty four zero digits.

- CTRL-D: The CTRL-C payload list with every payload combined by exclusive or
  with its block key, the `drift` mask over the capture ordinal and then the
  block counter.

- CTRL-E: One payload in lowercase hexadecimal: the first payload of block 0
  in the CTRL-D list, combined by exclusive or with the `chain` mask over the
  capture ordinal, 0 and 0 when the capture is chained, and with the mask of
  the label word `seal_label_index` names over the capture ordinal and 0 when
  it is sealed. Its rotation is not undone.

- CTRL-F: One entry text: the CTRL-E payload rotated right by `spin_modulus`
  taken against twelve when the capture is spun, then unpacked as if it stood
  in block 0. The tick is the field as stored, a second difference in a
  stepped capture.

- CTRL-G: The entry text of every entry, joined by commas in entry ordinal
  order. The entries are the CTRL-D payloads block by block, less the filler
  of a shadowed capture, which is the last `shadow_pad_base` less three
  payloads of block 0 (all of block 0 when it holds no more), and entry
  ordinals count them from zero. Each payload in turn is combined by exclusive
  or with the `chain` mask over the capture ordinal and the stored tick and
  amount of the entry before it (0 and 0 for the first entry and for an entry
  after a `none`), then with the mask of the label word `seal_label_index`
  names over the capture ordinal and the entry ordinal, then rotated right by
  the entry ordinal plus one times `spin_modulus` taken against twelve, then
  unpacked in the block it came from. Ticks stand as stored and echoes stand
  as written.

- CTRL-H: The word entry text of every CTRL-G entry, joined by commas in entry
  ordinal order. In a stepped capture the ticks are restored from the stored
  series, a `none` entry counting as a stored 0: the first tick as stored, the
  second the stored value plus the first tick, every later one the stored
  value plus twice the tick before it less the tick before that, each wrapped
  at 65536. The unit index, taken against the length of the list, selects a
  word from the donor capture's header word list rotated left by
  `alias_donor_shift` in an aliased capture, and from the twenty four unit
  words of the charter notes in any other. A `none` entry stays `none`.

- CTRL-I: The CTRL-H word entry texts once every echo, an entry of kind 224,
  is resolved in entry ordinal order. An echo's distance is its entry ordinal
  taken against one less than `echo_window_span`, plus one. It keeps its own
  tick and takes the word, the kind, the amount and the mark of the entry that
  distance earlier, as that entry stands once the echoes before it are
  resolved. An echo whose distance reaches before the first entry, or lands on
  a `none` entry, stays as written.

CTRL-J reads one fragment per surviving canonical unit, in ascending order of
the unit word by character code: the word, a colon and the name of its cadence
class, as in `hydra:steady`.

CTRL-K reads one fragment: the upkeep target written as the charter notes render
a rational, numerator, solidus and denominator in lowest terms, as in `98472/1`.
