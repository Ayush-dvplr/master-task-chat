# Five Original Terminal-Agent Benchmark Ideas: Data Processing and ETL

## Idea 1 — Cold-Chain Evidence Ledger: Reconstructing Shipment History from Conflicting Feeds

### 1. Title and one-sentence pitch

**Cold-Chain Evidence Ledger:** Build a reusable ETL program that reconstructs the defensible custody history of temperature-sensitive shipments from inconsistent manifests, carrier scans, calibrated sensors, corrections, and receiver records, while preserving the distinction between questionable evidence, rejected evidence, and confirmed delivery.

### 2. Setting

A pharmaceutical distribution quality team receives independently generated shipment data from manufacturers, carriers, sensor vendors, regional depots, and receiving facilities. A shipment may be described under different names by different systems, sensors can be replaced during transit, carrier events can arrive out of order, and a later correction can invalidate an earlier scan without erasing its audit history.

The team needs a reproducible record of each shipment's custody and temperature status, with supporting reports by product, destination region, and customer segment. Incorrectly accepting a shipment can release compromised stock; incorrectly rejecting it can interrupt supply. Every decision therefore needs a documented evidence trail.

### 3. Archetype and fixed output mapping

**Archetype:** `data-pipeline`

The program writes all 14 required outputs:

- `out/transform.py`: reusable executable transformation program.
- `out/normalized.jsonl`: normalized shipment-lot records and their derived evidence status, ordered by the specified canonical key.
- `out/summary.json`: input totals, accepted and rejected record counts, delivery and disposition totals, and reconciliation invariants.
- `out/data_quality.json`: parse failures, unresolved references, invalid corrections, sensor-quality failures, and other precisely categorized defects.
- `out/product_summary.json`: accepted and held quantities, excursion classifications, and reconciliation totals by canonical product.
- `out/region_central.json`, `out/region_east.json`, `out/region_north.json`, `out/region_south.json`, and `out/region_west.json`: regional rollups derived from the normalized ledger.
- `out/segment_consumer.json`, `out/segment_corporate.json`, `out/segment_enterprise.json`, and `out/segment_smb.json`: equivalent rollups by the specified customer segment.

The instruction defines the exact schema for every report, including empty groups, null values, integer quantities, fixed decimal strings, sorting, and cross-report reconciliation rules. The program cannot introduce additional output filenames.

### 4. Deliverable program

The agent builds `out/transform.py`, which:

1. Parses all inputs and validates their structural integrity.
2. Canonicalizes product, facility, shipment, lot, and sensor identities.
3. Resolves correction references and reconstructs the valid event history.
4. Normalizes measurements using the applicable sensor calibration.
5. Evaluates custody, routing, temperature, and receiving evidence.
6. Reconciles shipment quantities against receiver records.
7. Produces a canonical stream, summary, quality report, product report, and all nine prescribed regional and segment reports.

On fresh inputs, the program must derive its results from file contents rather than familiar filenames, record counts, embedded examples, or fixed identifiers. It must preserve all valid evidence needed for audit, distinguish rejected inputs from unresolved business decisions, and produce deterministic results.

The normalized ledger contains only the contracted canonical records. Raw rejected rows are represented in the quality report rather than silently disappearing. A held shipment remains a valid normalized business record; it is not equivalent to a malformed input row.

### 5. Input files

The task ships 12 input files in eight standard-library-readable formats. The approximate sizes below describe workload shape, not a difficulty mechanism based on raw volume.

| File | Format and approximate size | Contents and dependencies |
|---|---|---|
| `contract.md` | Markdown, about 250 lines | Normative input contracts, exact output schemas, status definitions, ordering rules, error codes, rounding, and report invariants. Governs every other input and output. |
| `shipment_manifest.csv` | CSV, about 800 rows | Shipment IDs, raw facility and product identifiers, lot references, expected destinations, planned quantities, and route IDs. Provides the initial shipment population. |
| `site_aliases.xml` | XML, about 250 entries | Source-scoped facility aliases and their canonical IDs. Resolves manifest and carrier scan facility references. |
| `site_regions.ini` | INI, about 100 sections | Canonical facility-to-region mappings and explicitly dated assignments. Supplies regional report membership. |
| `route_windows.tsv` | TSV, about 1,500 rows | Ordered route checkpoints, permissible event intervals, and transit constraints. Uses route IDs from the manifest and canonical facility IDs from the alias registry. |
| `carrier_scans.jsonl` | JSONL, about 12,000 events | Pickup, transfer, arrival, departure, and delivery scans, including source event IDs and source-local timestamps. Depends on manifest identities, site aliases, and route definitions. |
| `sensor_devices.ini` | INI, about 350 sections | Sensor identity, assigned shipment or route, sensor type, calibration family, and declared installation intervals. Connects raw readings to calibrated instruments and shipment legs. |
| `sensor_calibration.csv` | CSV, about 600 rows | Calibration coefficients, valid-time intervals, accepted unit codes, and permitted measurement ranges. Depends on the sensor calibration families declared in the registry. |
| `temperature_readings.jsonl` | JSONL, about 20,000 observations | Sensor readings with event time, measurement unit, sensor ID, source sequence, and reading ID. Requires the device registry and applicable calibration. |
| `correction_log.log` | Plain text log, about 1,500 entries | Append-only corrections to named source records, correction references, and correction types. Depends on source event IDs in the carrier and sensor feeds. |
| `lot_policy.json` | JSON, about 1,000 lot/product policies | Lot expiry, allowed temperature bounds, duration limits, and product-specific disposition rules. Depends on canonical product and lot identities. |
| `receipts.sqlite` | SQLite database, about 800 receipts | Receiver-confirmed quantities, destination, receipt reference, and receipt time. Reconciles against the reconstructed custody ledger. |
| `product_catalog.csv` | CSV, about 500 products | Canonical product IDs, report labels, customer segments, and quantity units. Connects normalized records to product and segment reports. |

Every file contributes to a graded output. For example, a policy adjustment can change shipment disposition; a region assignment changes a regional report; the product catalog changes segment membership; and the SQLite receipts change accepted-versus-unreconciled quantities.

Three explicit dependency chains are:

1. `site_aliases.xml` → `shipment_manifest.csv` and `carrier_scans.jsonl` → `route_windows.tsv` validation → corrected custody timeline → normalized shipment record.
2. `sensor_devices.ini` → `sensor_calibration.csv` → `temperature_readings.jsonl` normalization → correction application → excursion classification → lot disposition.
3. `product_catalog.csv` → manifest product resolution → `lot_policy.json` evaluation → `receipts.sqlite` reconciliation → normalized ledger → product, regional, and segment reports.

The task includes no reference report, calibration answer file, or expected-output fixture.

### 6. Spine: dependent processing stages

The required processing spine is:

1. **Ingest:** Parse each format, preserve source identifiers, and classify malformed records.
2. **Resolve identity:** Canonicalize source-scoped shipment, facility, product, lot, and sensor identifiers.
3. **Construct correction graph:** Validate correction targets, supersession references, and correction ordering.
4. **Reconstruct evidence:** Produce the authoritative version of each source event while preserving the audit history.
5. **Normalize measurements and times:** Apply calibration and unit conversion under effective-time rules.
6. **Evaluate custody and exposure:** Check route consistency, elapsed exposure, sensor validity, and lot policy.
7. **Reconcile quantities:** Compare the surviving delivery evidence with the authoritative receipt records.
8. **Classify records:** Assign the specified delivery, hold, rejection, and reconciliation states.
9. **Aggregate and audit:** Generate the normalized stream and reports, then verify the explicitly documented arithmetic and membership invariants.

The grading harness can supply correct intermediate outputs for stages 1–6 when checking later stages. Consequently, failures in identity resolution do not eliminate all credit for independently correct quantity reconciliation or report generation.

### 7. Levers

The normative rules below appear in `contract.md`, supplemented by the named source schemas. They are part of the shipped specification; hidden tests introduce interactions, not undocumented requirements.

#### Lever 1 — Hidden composition (STANDARD A)

**a. Name:** `A — Interacting evidence rules`

**b. Rule and location:** The contract states that a correction is valid only for a valid, source-scoped target; the corrected event must then be evaluated against the target's effective-time calibration, route position, lot policy, and authoritative receipt. Corrections to event contents do not automatically repair unrelated identity or calibration failures. Location: `contract.md`, sections on evidence reconstruction and disposition.

**c. Likely reflex error:** Implement each rule separately and assume that a corrected scan is sufficient to make the whole shipment consistent.

**d. Hidden case:** A correction changes a transfer event's facility reference. That facility has two aliases, the corrected event moves into a different route checkpoint interval, and the corresponding sensor's calibration changes between the original and corrected event times. A receiving record then agrees with the corrected destination but not the original destination. The output fields affected include canonical facility, route-validity status, calibrated exposure, disposition, and regional totals.

**e. Why samples do not reveal the error:** Shipped examples exercise corrections, facility aliases, and effective-time calibration separately. None contains all four dependencies in one shipment.

**f. Independence:** Partially independent. The case is constructed so that identity, route, and sensor decisions can each receive separate credit even when the final disposition is wrong.

#### Lever 2 — Dependent chain (STANDARD B)

**a. Name:** `B — Evidence-to-report dependency chain`

**b. Rule and location:** Reports must be computed from the final normalized ledger; the ledger must be computed from corrected evidence and reconciled receipts, not directly from source row counts. Every stage's contract defines its inputs and outputs. Location: `contract.md`, processing stages and output definitions.

**c. Likely reflex error:** Build several independent aggregations directly from input files, producing reports that appear plausible but disagree with the normalized records.

**d. Hidden case:** Two shipments share a product and region. One becomes held after exposure analysis; the other has a valid corrected receipt quantity. A program that aggregates manifests independently reports both original quantities, while the normalized-ledger-derived product and region reports reflect only the prescribed final states. Affected fields include disposition totals, accepted quantity, held quantity, and reconciliation counts.

**e. Why samples do not reveal the error:** The visible examples' intermediate and final totals happen to agree even when computed through shortcuts. Hidden cases deliberately break those coincidences.

**f. Independence:** High. Each processing stage has separately graded outputs.

#### Lever 3 — Orthogonal reporting populations (STANDARD E)

**a. Name:** `E — Evidence population versus business population`

**b. Rule and location:** `data_quality.json` counts every input row that is rejected or classified as defective, including rows unrelated to any accepted shipment. Business reports count only valid normalized business records and apply the documented inclusion rules for delivered, held, and unreconciled records. Location: `contract.md`, quality and aggregation contracts.

**c. Likely reflex error:** Use a single global population filter for both data-quality counts and business reports.

**d. Hidden case:** One malformed event references a real shipment that is subsequently held for a separate policy reason. The event must contribute to the quality report while the valid shipment must remain in the business population. The quality defect count, held quantity, normalized record count, and product totals change under the incorrect shared filter.

**e. Why samples do not reveal the error:** In shipped examples, invalid rows refer to otherwise irrelevant identifiers and do not overlap valid-but-held shipments.

**f. Independence:** High. The quality and business reports can be tested separately.

#### Lever 4 — Explicit refusal semantics (STANDARD F)

**a. Name:** `F — Invalid evidence must be refused`

**b. Rule and location:** A malformed row, dangling correction target, invalid correction cycle, or calibration reference that cannot be resolved under the contract must be rejected with its specified stable error code. A semantically questionable but structurally valid shipment must instead be retained with a business status. Location: `contract.md`, rejection catalogue and classification rules.

**c. Likely reflex error:** Silently skip malformed rows, crash the entire program, or convert every unresolved case into a generic rejection.

**d. Hidden case:** A valid held shipment has a separate dangling correction entry. The shipment remains in the normalized ledger while the correction receives its prescribed quality error. The reflex implementation either discards the shipment or incorrectly counts the hold as a malformed-record rejection.

**e. Why samples do not reveal the error:** Shipped malformed inputs either affect no valid business object or cause an unambiguous whole-row rejection.

**f. Independence:** High. Most rejection cases require only ingestion and reference validation.

#### Lever 5 — NEW: Corrections are field-scoped and supersession-aware

**a. Name:** `NEW — Field-level correction lineage`

**b. Rule and location:** Every correction specifies the exact fields it may modify. For a given source record and field, only the valid terminal correction in that field's supersession chain supplies the corrected value. A correction to one field neither erases a valid correction to another field nor revives an invalid earlier correction. Cycles and cross-source targets are rejected. Location: `contract.md`, correction model.

**c. Likely reflex error:** Select one “latest correction” for the whole record or apply all correction entries in file order.

**d. Hidden case:** A scan's facility is corrected in one branch and its event time in another. A later facility correction supersedes the earlier facility value but does not supersede the time correction. Whole-record last-write-wins changes the route checkpoint and exposure time; blindly applying every entry restores a facility value that is no longer authoritative. Affected fields include facility, event time, route validity, and custody order.

**e. Why samples do not reveal the error:** Visible correction chains either touch one field or have a single terminal correction affecting all named fields.

**f. Independence:** Medium-high. Correction matching and the audit trail are testable without completing downstream reports.

#### Lever 6 — NEW: Calibration is effective at event time, not file time

**a. Name:** `NEW — Effective-time measurement normalization`

**b. Rule and location:** The calibration row is selected by sensor identity and the measurement's corrected event time. Its unit conversion and calibration formula are applied before exposure evaluation; values are rounded only at the explicitly stated normalization boundary. The file's arrival order has no effect. Location: `contract.md`, measurement contract and `sensor_calibration.csv` schema.

**c. Likely reflex error:** Use the latest calibration row, use ingestion time, or round intermediate conversions.

**d. Hidden case:** A late-arriving reading refers to a period before a sensor was recalibrated. The correct conversion places it inside the allowed temperature range, but the latest calibration places it outside. This changes normalized measurement strings, excursion status, lot disposition, and regional rollups.

**e. Why samples do not reveal the error:** Sample sensor observations fall wholly within a single calibration interval and use unit conversions that do not cross a rounding boundary.

**f. Independence:** High for normalized measurement outputs; medium for downstream disposition outputs.

#### Lever 7 — NEW: Exposure requires a documented evidence pattern

**a. Name:** `NEW — Valid-sample excursion qualification`

**b. Rule and location:** An excursion is qualified only when the specified number of consecutive eligible calibrated readings exceeds the lot's limit and their event-time separation is within the documented maximum gap. Invalid sensor readings do not count toward the sequence and reset it only where the contract explicitly says so. A single extreme reading is not automatically sufficient. Location: `contract.md`, exposure qualification.

**c. Likely reflex error:** Flag any out-of-range sample or count every raw reading equally.

**d. Hidden case:** A shipment contains two valid high readings separated by an ineligible measurement and another high reading outside the permitted time gap. A raw-value counter reaches the threshold, but the eligible consecutive sequence does not. The resulting excursion status, lot disposition, and held quantity differ.

**e. Why samples do not reveal the error:** Sample excursions either have an obviously sufficient consecutive sequence or no out-of-range readings.

**f. Independence:** High when eligible-reading classification is supplied as correct intermediate input; otherwise medium, because it depends on calibration.

### 8. Rejection paths

The contract defines exact error objects and stable reason codes. The following are rejected independently where possible:

- Unparseable input row: `E_PARSE:<file>:<row>`.
- Duplicate source event identifier within its declared source scope: `E_DUPLICATE_SOURCE_ID:<source>:<id>`.
- Unresolvable canonical identity: `E_UNKNOWN_IDENTITY:<entity_type>:<source_id>`.
- Cross-source or missing correction target: `E_CORRECTION_TARGET:<correction_id>`.
- Correction supersession cycle: `E_CORRECTION_CYCLE:<correction_id>`.
- Missing effective calibration: `E_CALIBRATION_MISSING:<sensor_id>:<event_id>`.
- Unknown measurement unit: `E_UNIT_UNKNOWN:<event_id>:<unit>`.

The colon-delimited tokens are literal formatting requirements; identifier escaping and row-number conventions are defined in the contract. Correctly classified business holds are not rejection errors. One bad record must not prevent independent valid records from producing reports.

### 9. Partial-credit plan

Use **51 independent checks**, with 100 weighted points overall. Each check is independently scored, so correct later-stage outputs earn credit even when an earlier stage is wrong.

| Check group | Independent checks | Points | Heavy checks |
|---|---:|---:|---|
| Lever A: combined evidence cases | 7 | 18 | 4 |
| Lever B: chain and reconciliation invariants | 8 | 20 | 5 |
| Lever E: population definitions and report consistency | 7 | 12 | 3 |
| Lever F: exact rejection behavior | 7 | 12 | 3 |
| NEW: field-scoped correction lineage | 8 | 14 | 4 |
| NEW: effective-time normalization | 7 | 12 | 3 |
| NEW: excursion qualification | 7 | 12 | 3 |
| **Total** | **51** | **100** | **25** |

Heavy checks include hidden combinations, exact refusal cases, and reconciliation invariants. Lightweight checks cover single-stage normalization, fixed schemas, sorting, and report membership.

### 10. Reviewer checks on the work log

Require a short work log that records findings and decisions without substituting for the machine-graded outputs. The reviewer checks these 12 statements:

1. The log identifies which source defines canonical facility identities.
2. It distinguishes event time from ingestion or file-arrival time.
3. It explains how the source-level correction history is preserved.
4. It identifies the rule that chooses a calibration for a measurement.
5. It states how a shipment with a valid but unresolved business disposition differs from a malformed row.
6. It names the authoritative population for each family of reports.
7. It records which receipt source controls the quantity reconciliation.
8. It names the source of product and customer-segment membership.
9. It identifies the invariant used to cross-check regional totals against the normalized ledger.
10. It states how a correction cycle is detected and represented.
11. It explains why the absence of an excursion does not by itself prove complete custody evidence.
12. It identifies any source fields retained only for audit and not used to determine business status.

These statements describe concrete properties of a correct solution, not the effort expended or the number of files read. None independently awards points for having correct JSON values.

### 11. Shortcuts and cheats

- **Hardcoding sample results:** Hidden inputs alter identities, correction chains, calibration periods, and policy combinations. Tests invoke the reusable program with fresh files.
- **Special-casing filenames or counts:** Files may be renamed according to an invocation manifest; the contract defines logical roles and schemas.
- **Ignoring a source file:** Each input has fields that affect a graded output. The test suite includes independent changes to each source.
- **Aggregating directly from manifests:** Hidden receipts and corrections make manifest totals disagree with the normalized ledger.
- **Dropping audit information:** Quality checks inspect rejected and invalidly referenced records independently of accepted business rows.
- **Using a single global “bad row” filter:** The accepted, held, and rejected populations are specified and tested separately.
- **Treating arrival order as authoritative:** Fresh fixtures deliberately permute correction and measurement arrival order.
- **Reading expected answers:** No expected-output files or calibration results ship with the task; only normative rules and raw input records are provided.

### 12. Expected scores

Expected ranges assume three approaches: a lazy implementation that approximates basic ETL, a careful-but-hurried implementation that handles obvious rules but defaults to conventional shortcuts, and an expert implementation that follows the entire contract.

| Lever | Lazy agent | Careful-but-hurried agent | Why the benchmark is discriminating |
|---|---:|---:|---|
| A | 0/18 | 2–4/18 | Combined correction, route, calibration, and receipt evidence exposes integration gaps. |
| B | 2/20 | 4–5/20 | Direct source aggregation can look plausible but violates ledger-derived reconciliation. |
| E | 2/12 | 2–3/12 | Data-quality and business populations diverge only in interacting cases. |
| F | 1/12 | 2–3/12 | Exact error objects and the distinction between invalid evidence and business holds need deliberate handling. |
| NEW correction lineage | 0/14 | 1–2/14 | Whole-record last-write-wins misses independent field histories. |
| NEW effective-time calibration | 1/12 | 1–2/12 | Latest-row assumptions fail on late-arriving readings. |
| NEW excursion qualification | 0/12 | 1–2/12 | A raw threshold counter fails on invalid or separated readings. |

**Expected total test score:** lazy 3–7%; careful-but-hurried 13–18%; perfect 100%.

The point is not to make the specification obscure. The low middle score comes from familiar shortcuts that satisfy the visible cases, while the exact implementation remains achievable from the written rules.

### 13. Nearest known benchmark task or textbook problem

Nearest: multi-source ETL, event sourcing, temporal joins, and data-quality reconciliation.

Difference: ordinary ETL exercises generally normalize rows or aggregate clean dimensions. This task requires an audited, field-scoped correction graph, effective-time sensor calibration, a temporally constrained evidence pattern, and different population definitions for quality and business reports. These rules combine in hidden cases rather than appearing only as isolated transformations.

### 14. Solvability argument

An expert can finish within two hours because all file formats are standard-library-accessible, identifiers and correction semantics are explicit, and there are no network dependencies or externally sourced facts. The dependency spine can be implemented in a small set of stages, with intermediate records tested independently.

The expert need not solve an open-ended optimization problem: calibration selection, correction resolution, evidence qualification, status definitions, rejection codes, and report schemas are fully specified. Hidden tests vary compositions and sizes but do not introduce new semantics.

### 15. Biggest risk

The largest fairness risk is accidentally underspecifying how a correction affects the order of route events or how an invalid sensor reading affects a consecutive excursion sequence. The contract must define these cases with explicit state-transition rules and examples that teach the syntax without showing the adversarial combinations.

---

## Idea 2 — Byte-Exact Vendor Archive Recovery: Decoding History Without Destroying Evidence

### 1. Title and one-sentence pitch

**Byte-Exact Vendor Archive Recovery:** Recover normalized records from a documented, compact vendor archive format and build a canonical encoder that preserves unknown extensions, stream-dependent compression context, and exact round trips without confusing byte-level validity with semantic validity.

### 2. Setting

A data engineering team must migrate long-lived telemetry archives after the original vendor software has become unavailable. The archives contain versioned records from logistics equipment and industrial sensors. Some payloads contain valid fields unknown to the current schema, some use compact encoding across multiple frames, and some frames are damaged.

The migration must produce readable normalized records while preserving enough original representation to reproduce every valid archive byte-for-byte. That requirement matters for downstream reprocessing and contractual audit. The team cannot simply decode known values and re-encode them while discarding unfamiliar bytes.

### 3. Archetype and fixed output mapping

**Archetype:** `format-recovery`

The required files are:

- `decode.py`: reusable decoder for the documented archive format.
- `encode.py`: reusable encoder for the same format, using canonical encoding rules while preserving all contracted round-trip information.
- `out/decoded_examples.jsonl`: decoded records from the supplied captures, represented under the exact normalized-record schema.
- `out/format_report.json`: frame inventory, version counts, field-type statistics, and format features observed.
- `out/roundtrip_report.json`: exact-byte round-trip success/failure counts, byte-count totals, and the contracted digest summaries.
- `out/error_analysis.json`: invalid-frame counts and rejection reasons, including the required offset and scope information.

The specification defines the exact output objects, stable key order where required, JSON string escaping, integer representation, byte-hex representation, and sorting. The task must not add output files.

### 4. Deliverable program

The agent implements a decoder and encoder that:

1. Parses the supplied schema and format metadata.
2. Reads the capture index and identifies complete, partial, and damaged frames.
3. Decodes frame headers, versioned layouts, compact integers, escape sequences, dictionaries, and supported field types.
4. Reconstructs per-stream decoding context in the specified order.
5. Exposes known fields as normalized records while retaining all valid unknown extensions.
6. Encodes normalized records using the documented canonical field and frame rules.
7. Performs byte-for-byte round-trip checks on supplied valid captures.
8. Rejects invalid frames with their documented errors and builds the reports.

The decoder must work on new captures. The encoder must be reusable for new records rather than merely emitting the captured original bytes. Where the contract permits multiple semantic encodings, it defines which original representations must be preserved for round-trip exactness and which newly encoded records must use the canonical representation.

### 5. Input files

The task ships 12 files in at least eight standard-library-readable formats.

| File | Format and approximate size | Contents and dependencies |
|---|---|---|
| `format_contract.md` | Markdown, about 300 lines | Normative byte layout, version rules, error offsets, canonical encoding rules, exact report schemas, and round-trip conditions. |
| `schema_registry.json` | JSON, about 50 schema versions | Schema identifiers, version compatibility, and record-family definitions. |
| `field_layouts.csv` | CSV, about 400 entries | Field IDs, types, widths, optionality, and schema-specific positions. References schema identifiers. |
| `symbol_table.tsv` | TSV, about 1,000 entries | Known symbol IDs, text values, and declared dictionary scopes. Used to resolve encoded symbols. |
| `revision_map.ini` | INI, about 100 sections | Version-transition rules and field-ID remappings for supported schema revisions. |
| `escape_rules.xml` | XML, about 80 rules | Escaping and unescaping behavior, reserved byte sequences, and boundary behavior. |
| `crc_profiles.json` | JSON, about 20 profiles | Checksum variants, byte coverage, and initialization parameters. |
| `frame_index.jsonl` | JSONL, about 5,000 entries | Capture offsets, lengths, stream IDs, sequence numbers, and frame references. It governs capture discovery and reporting. |
| `capture_alpha.bin` | Binary, about 1 MB | Valid and invalid archive frames from several streams. |
| `capture_beta.bin` | Binary, about 1.5 MB | Additional frame sequences, including stateful dictionary and delta cases. |
| `transport_errors.log` | Plain text log, about 300 entries | Transport truncation notices and documented damaged-range annotations. Correlates with frame offsets but is not permission to ignore the bytes. |
| `sample_order.txt` | Plain text, about 100 lines | Prescribed ordering of streams and frame processing for stateful decoding and supplied example selection. |

The source of each binary field is defined by the contract. The transport log influences damage classification, the frame index affects stream reconstruction, and the schema and revision metadata affect both decoded values and report statistics.

Three dependency chains are:

1. `schema_registry.json` → `field_layouts.csv` → `revision_map.ini` → field-ID resolution → binary frame decoding → decoded record schema.
2. `symbol_table.tsv` → dictionary references in binary frames → stream-specific dictionary context → escape decoding → normalized text fields.
3. `crc_profiles.json` and `escape_rules.xml` → raw-byte frame validation → decoded payload → canonical encoding → round-trip report and error analysis.

The captures contain data, not expected decoded answers. The task does not ship a reference decoder's output.

### 6. Spine: dependent processing stages

1. **Parse metadata:** Load schemas, field layouts, symbol table, revision map, escaping rules, and checksum profiles.
2. **Locate frames:** Use the frame index to identify frame boundaries and streams.
3. **Validate physical framing:** Verify header structure, declared length, reserved encodings, and checksum according to the documented byte coverage.
4. **Reconstruct stream context:** Apply sequence, dictionary, delta, and reset rules to the correct stream.
5. **Decode values:** Apply escaping, compact-integer decoding, field layout, and schema version.
6. **Resolve revision semantics:** Map source field IDs and values into the normalized schema without losing valid raw extension data.
7. **Encode records:** Emit newly encoded records in canonical form, retaining the required round-trip metadata.
8. **Round-trip verify:** Compare bytes, not just decoded JSON values.
9. **Analyze errors:** Distinguish malformed framing, invalid checksum, unsupported schema version, and invalid stream context.

Later-stage tests can supply already validated frames and metadata interpretations so the encoder, unknown-field preservation, and report logic earn partial credit even if a decoder edge case is missed.

### 7. Levers

#### Lever 1 — Hidden composition (STANDARD A)

**a. Name:** `A — Valid frames with interacting representation rules`

**b. Rule and location:** The format contract explicitly states how checksums, escape sequences, dictionary context, schema revision, and unknown extension fields interact. A physically valid frame can contain a semantically unsupported extension, and an extension must remain unchanged even when known fields are migrated to the normalized schema. Location: `format_contract.md`, decoding and round-trip sections.

**c. Likely reflex error:** Treat successful decoding into known fields as sufficient evidence of an exact round trip.

**d. Hidden case:** A valid frame contains an escaped extension byte sequence, a dictionary reference established earlier in the same stream, and a known field remapped by a schema revision. A decoder that resolves the known value but drops the extension produces apparently correct JSON but fails byte-exact re-encoding. The affected fields include extension bytes, round-trip equality, frame counts, and extension-preservation statistics.

**e. Why samples do not reveal the error:** Shipped frames demonstrate escaping, dictionary references, and revision mapping independently. No visible frame combines all three with unknown extension data.

**f. Independence:** Medium-high. Decoded semantic values and exact byte preservation can be graded independently.

#### Lever 2 — Dependent chain (STANDARD B)

**a. Name:** `B — Byte-layout-to-round-trip chain`

**b. Rule and location:** Only frames that pass physical validation enter semantic decoding. Semantic field interpretation uses the resolved schema revision, and re-encoding uses the specified canonical or preserved representation. Location: `format_contract.md`, processing contract.

**c. Likely reflex error:** Implement decode and encode as unrelated convenience functions, or calculate round-trip success by comparing normalized objects rather than bytes.

**d. Hidden case:** A frame contains a compact integer encoded in a longer but permitted source representation. The decoder yields the correct integer, but the encoder canonicalizes it. The semantic comparison succeeds and a byte comparison fails. The byte-equality count, mismatch offset, and round-trip status change.

**e. Why samples do not reveal the error:** Every ordinary visible integer uses its shortest permitted encoding, so semantic and byte-level comparisons agree.

**f. Independence:** High. Encoding and report comparisons can be tested with known-good decoded inputs.

#### Lever 3 — Component audit and repair (STANDARD C)

**a. Name:** `C — Quiet decoder and encoder defects`

**b. Rule and location:** The shipped partial implementation must be audited against the supplied format contract. The agent must repair documented functional defects rather than treating current behavior as authoritative. The defects include a boundary-handling flaw, a wrong state-reset scope, and loss of a field category on re-encoding. Location: `format_contract.md`, including the supplied implementation audit section.

**c. Likely reflex error:** Patch only the first failing visible example, leaving related defects intact.

**d. Hidden case:** A valid frame starts with a state boundary and contains a zero-width optional field followed by an unknown extension. A patch that only changes frame-length handling decodes the known values, but carries dictionary state incorrectly or drops the extension. The affected fields are decoded values, frame status, extension bytes, and byte-equality status.

**e. Why samples do not reveal the error:** Visible samples exercise each defect's simplest manifestation, not the boundary combination.

**f. Independence:** Medium. Each defect has isolated checks as well as combined checks.

#### Lever 4 — Refusal paths (STANDARD F)

**a. Name:** `F — Structurally invalid frames must be refused`

**b. Rule and location:** Each physical validation error maps to the exact code and offset convention in the contract. A checksum failure must not be reported as an unknown schema, and a truncated frame must not be silently reinterpreted as another valid frame. Location: `format_contract.md`, error catalogue.

**c. Likely reflex error:** Catch every parsing exception and return a generic malformed-record object.

**d. Hidden case:** A frame has a plausible declared length, an unsupported revision, and a checksum that is invalid over the contracted byte range. The required validation order chooses the physically invalid error before schema interpretation. The error code, byte offset, error category count, and rejected-frame count change.

**e. Why samples do not reveal the error:** Visible invalid frames contain one defect at a time.

**f. Independence:** High. Many rejection cases stop before semantic decoding.

#### Lever 5 — NEW: Dictionary state is scoped to a stream, not a file or batch

**a. Name:** `NEW — Stream-local context`

**b. Rule and location:** Each stream maintains its own dictionary and sequence state. Only the contracted reset event clears that state. A file boundary or an invocation batch boundary does not reset a stream, and a reset for one stream cannot reset another. Location: `format_contract.md`, stateful encoding rules.

**c. Likely reflex error:** Reinitialize the decoder for each file, or share one dictionary globally across all frames.

**d. Hidden case:** A stream starts in one capture file and continues in another while a second stream has an independent reset. A dictionary reference is valid only under the first stream's prior context. Resetting per file or globally changes decoded symbol values and subsequent records' exact re-encoding.

**e. Why samples do not reveal the error:** Each visible stream begins and ends within one file, and the sample reset markers align with file boundaries.

**f. Independence:** High when earlier frame validation is supplied; medium when testing full captures.

#### Lever 6 — NEW: Unknown extensions retain their original representation

**a. Name:** `NEW — Opaque extension preservation`

**b. Rule and location:** Unknown extension fields must be retained as ordered opaque bytes, including their length and the ordering relationships specified by the contract. They must not be decoded using guessed types, dropped, sorted by field ID, or reconstructed from their displayed hex text without respecting the original boundaries. Location: `format_contract.md`, extension policy.

**c. Likely reflex error:** Preserve only a dictionary of known fields, or sort all encoded fields during re-encoding.

**d. Hidden case:** Two unknown extension fields have distinct byte payloads and source order that differs from numeric field-ID order. The decoded known attributes are identical under both implementations, but canonical reconstruction with lost original ordering changes the emitted bytes and extension statistics.

**e. Why samples do not reveal the error:** Visible extension examples contain one unknown extension per frame, so dropping or reordering it is not exposed.

**f. Independence:** High. Opaque-byte round-trip checks do not require all semantic values to be correct.

#### Lever 7 — NEW: Escaping is applied before semantic interpretation and within frame boundaries

**a. Name:** `NEW — Framing-aware escape handling`

**b. Rule and location:** Frame-boundary and declared-length parsing occur according to the physical framing specification; escape decoding is applied only to the payload byte ranges specified by the contract. A reserved byte pattern is special only in the exact context described in `escape_rules.xml`. Location: `format_contract.md` and `escape_rules.xml`.

**c. Likely reflex error:** Globally replace reserved byte sequences before identifying frame boundaries, or allow an escape sequence to consume the next frame's header.

**d. Hidden case:** A valid escaped payload ends at the end of a frame while the next frame begins with a byte that resembles an escape continuation. Global replacement corrupts the second header or merges the payloads. Frame offsets, valid frame counts, and the first decoded field in the second frame change.

**e. Why samples do not reveal the error:** Visible escape examples are fully contained within their payloads and do not place a similar byte pattern at an adjacent frame boundary.

**f. Independence:** Medium-high. Framing and byte offsets can be independently validated.

### 8. Rejection paths

Exact errors include:

- `E_HEADER_TRUNCATED@<offset>`
- `E_FRAME_LENGTH@<offset>`
- `E_CHECKSUM@<offset>`
- `E_ESCAPE_SEQUENCE@<offset>`
- `E_STREAM_SEQUENCE@<offset>`
- `E_SCHEMA_UNSUPPORTED@<offset>`
- `E_FIELD_LAYOUT@<offset>`

The contract defines whether offsets are absolute file offsets or frame-relative offsets for each error. It also defines which errors take precedence if a frame has more than one defect. Where a damaged range makes safe frame boundaries impossible, the decoder refuses that range and resumes only at a synchronization point explicitly authorized by the format specification.

### 9. Partial-credit plan

Use **50 independent checks** and 100 weighted points.

| Check group | Independent checks | Points | Heavy checks |
|---|---:|---:|---|
| Lever A: interacting representation rules | 7 | 18 | 4 |
| Lever B: decode, encode, and round-trip chain | 8 | 20 | 5 |
| Lever C: supplied component repairs | 6 | 12 | 3 |
| Lever F: invalid frame handling | 7 | 12 | 3 |
| NEW stream-local context | 8 | 14 | 4 |
| NEW extension preservation | 7 | 14 | 4 |
| NEW framing-aware escaping | 7 | 10 | 3 |
| **Total** | **50** | **100** | **26** |

The most heavily weighted checks cover byte-exact round trips, cross-file stream continuation, invalid-frame precedence, and opaque extension preservation. Separate checks validate known decoded values, report schemas, and frame inventory.

### 10. Reviewer checks on the work log

Require the work log to contain 12 concrete technical findings:

1. It identifies which bytes are covered by each checksum profile.
2. It explains why byte-exact round-trip validity differs from semantic equality.
3. It identifies the dictionary state scope and reset conditions.
4. It states the role of the frame index in processing.
5. It explains how the implementation avoids consuming bytes from a following frame during unescaping.
6. It identifies which decoded data must remain opaque.
7. It distinguishes physical validation from schema interpretation.
8. It states which source metadata controls field-ID migration.
9. It describes how unknown extensions are represented in the decoded record.
10. It identifies the exact point at which canonical encoding is applied.
11. It identifies how frame errors are recorded without changing unrelated stream state.
12. It explains what evidence the round-trip report uses to establish byte equality.

The reviewer verifies reported facts, not effort. These checks are distinct from the machine's direct correctness comparisons.

### 11. Shortcuts and cheats

- **Returning original capture bytes for every encode request:** New records and modified records must be encoded from their content; fresh tests change known fields.
- **Comparing decoded JSON only:** Round-trip tests compare bytes and report the first mismatch as specified.
- **Dropping unknown fields:** Hidden records contain multiple unknown extensions with distinct order and content.
- **Processing files independently:** Hidden streams cross file boundaries.
- **Trusting the transport log as an answer key:** The log describes transport events but does not replace checksums, frame lengths, or contract-defined validation.
- **Hardcoding supported versions:** Hidden inputs include other documented compatible versions and field remappings.
- **Using current decoded output as a reference:** No decoded answer file is shipped. The decoder must infer values from the specification and capture.
- **Ignoring the encoder because the visible examples already exist:** Tests invoke it on fresh normalized records.

### 12. Expected scores

| Lever | Lazy agent | Careful-but-hurried agent | Why |
|---|---:|---:|---|
| A | 0/18 | 2–4/18 | Known values decode correctly, but representation dependencies break round trips. |
| B | 2/20 | 4–5/20 | Semantic equality is easier than exact encoding and byte-level verification. |
| C | 1/12 | 2–3/12 | Patching the visible defect does not repair all component interactions. |
| F | 1/12 | 2–3/12 | Generic errors fail the exact error-order and offset tests. |
| NEW stream context | 0/14 | 1–2/14 | Conventional per-file decoding loses valid cross-file context. |
| NEW extensions | 0/14 | 1–2/14 | Schemaless data is frequently dropped or reordered by otherwise reasonable encoders. |
| NEW escaping | 1/10 | 1–2/10 | Global unescaping corrupts boundary cases that ordinary payloads do not expose. |

**Expected total test score:** lazy 4–8%; careful-but-hurried 13–18%; perfect 100%.

### 13. Nearest known benchmark task or textbook problem

Nearest: binary protocol decoding, lossless serialization, compiler front ends, and canonical encoders.

Difference: ordinary binary-decoder tasks focus on recovering values from isolated frames. This task adds stream-scoped state, unknown-extension preservation, schema revisions, explicit validation precedence, and a bidirectional exactness contract. A decoder that correctly extracts every known field can still fail the central round-trip requirement.

### 14. Solvability argument

The format is artificial but fully specified. All required byte operations, schema lookups, checksums, escaping, and integer conversions are possible using standard Python libraries. The task needs no proprietary knowledge, network access, or unspecified vendor behavior.

The frame index and format rules allow the agent to build the decoder in separable layers. The canonical encoder and the report logic can be tested independently. There is no need to infer the protocol from bytes alone, and no hidden answer file is required.

### 15. Biggest risk

The main fairness risk is an incomplete definition of which original encoding details must be preserved and which may be canonicalized. The contract must distinguish exact re-encoding of decoded captured records from canonical encoding of newly created records, and it must state how invalid frames affect synchronization.

---

## Idea 3 — Data Product Configuration Compiler: Resolve Layered ETL Policies Without Leaking Secrets

### 1. Title and one-sentence pitch

**Data Product Configuration Compiler:** Repair a packaged CLI that compiles source registries, tenant policies, migration mappings, and environment overlays into deterministic ETL deployment profiles while correctly resolving inheritance, deletions, selectors, and all-or-none dependencies.

### 2. Setting

A central analytics platform deploys data connectors and transformations across development and production. Teams define data products, connector bindings, tenant access, schema compatibility, region restrictions, and deployment options in separate configuration feeds.

The existing CLI resolves these feeds into deployment profiles, but it contains several subtle defects. A wrong profile can enable an incompatible connector, remove an inherited restriction, or replace a secret reference with a literal. The platform team needs a corrected reusable CLI and fixed JSON outputs that remain valid when the input registries and policies change.

### 3. Archetype and fixed output mapping

**Archetype:** `cli-config`

The program produces:

- `out/config.json`: resolved base configuration.
- `out/report.json`: deterministic resolution summary and provenance counts.
- `out/tool.zip`: repaired CLI package.
- `out/profile_dev.json`: resolved development profile.
- `out/profile_prod.json`: resolved production profile.
- `out/validation_report.json`: validation findings and exact error classifications.
- `out/summary.json`: counts and cross-profile reconciliation invariants.

The required schemas, sorting, error structure, deterministic ZIP requirements, and resolution semantics are written into `compiler_contract.md`. The fixed output filenames and the number of profiles cannot change.

### 4. Deliverable program

The agent repairs the supplied CLI and ensures it can:

1. Parse the source configuration files and embedded registries.
2. Canonicalize product and connector identifiers.
3. Resolve the documented parent and migration relationships.
4. Apply tenant and environment overlays with distinct missing, null, and empty states.
5. Expand selectors against the declared resource inventory.
6. Resolve connector dependencies and incompatibilities.
7. Validate schemas, regions, access restrictions, and secret references.
8. Emit the resolved configurations and deterministic reports.
9. Run correctly on fresh registries and overlays.

The package must remain an actual reusable CLI. Hardcoded profile JSON files without working resolution logic do not satisfy the task. The output ZIP must contain the repaired program and the minimum files required by the stated package contract.

### 5. Input files

The task ships 12 files, using at least eight formats readable by the Python standard library.

| File | Format and approximate size | Contents and dependencies |
|---|---|---|
| `compiler_contract.md` | Markdown, about 300 lines | Merge semantics, overlay order, validation rules, canonical output schemas, rejection codes, and ZIP requirements. |
| `tool.zip` | ZIP archive containing Python modules | Partially implemented CLI with quiet resolution and validation defects. |
| `defaults.ini` | INI, about 150 keys | Global defaults and baseline deployment settings. |
| `tenants.csv` | CSV, about 500 tenants | Tenant IDs, parent tenancy, assigned data products, and environment eligibility. |
| `connector_registry.json` | JSON, about 500 connectors | Connector capabilities, schema ranges, secret requirements, and incompatibilities. |
| `source_bindings.tsv` | TSV, about 1,200 bindings | Data product to source/connector binding relationships. Depends on connector IDs and product IDs. |
| `environment_overlays.toml` | TOML, about 600 sections | Development and production overrides, explicit deletions, and environment-specific constraints. |
| `schema_versions.xml` | XML, about 150 version entries | Canonical schema identifiers and supported migration relationships. |
| `migration_map.json` | JSON, about 200 migrations | Legacy product and connector IDs that map to current identifiers. |
| `access_policies.jsonl` | JSONL, about 2,000 policy entries | Tenant-scoped allow/deny rules, resource selectors, and regional restrictions. |
| `secret_refs.log` | Plain text log, about 250 references | Declared secret reference names, existence status, and permitted consumer scopes. It contains no actual secret values. |
| `dependency_rules.csv` | CSV, about 350 rows | Connector dependency bundles, conflicts, and required feature declarations. |
| `resource_inventory.tsv` | TSV, about 1,500 resources | The exact inventory against which wildcard and exclusion selectors are evaluated. |

Each file affects resolution or validation. For instance, the resource inventory changes selector expansion; dependency rules change connector activation; tenant records change profile eligibility; schema versions change valid binding resolution; and secret references change validation findings.

Three dependency chains are:

1. `migration_map.json` → `tenants.csv` and `source_bindings.tsv` → `connector_registry.json` → `schema_versions.xml` → resolved connector bindings.
2. `defaults.ini` → `environment_overlays.toml` → tenant- and environment-specific overlays → dependency resolution → development and production profiles.
3. `resource_inventory.tsv` → `access_policies.jsonl` selector expansion → connector access checks → secret-scope validation → `validation_report.json`.

### 6. Spine: dependent processing stages

1. **Parse:** Load defaults, tenants, connector metadata, environment overlays, schema versions, migrations, access policies, dependencies, secret references, and resource inventory.
2. **Canonicalize:** Resolve legacy product and connector identifiers before binding validation.
3. **Build inheritance graph:** Identify parents, validate cycles, and determine the prescribed resolution order.
4. **Apply field-aware overlays:** Resolve absent values, explicit nulls, empty collections, and ordinary values according to the contract.
5. **Expand selectors:** Apply inclusion and exclusion selectors against the supplied resource inventory.
6. **Solve dependency bundles:** Determine compatible connector sets under explicitly stated all-or-none and incompatibility constraints.
7. **Validate each profile:** Enforce schema compatibility, environment eligibility, regional access, and secret-reference restrictions.
8. **Emit and cross-check:** Generate profiles, resolved config, validation findings, resolution report, and the repaired CLI package.

Later-stage tests can provide correct canonical identifiers and inheritance states, allowing dependency resolution and validation to receive credit independently of an earlier migration-mapping mistake.

### 7. Levers

#### Lever 1 — Hidden composition (STANDARD A)

**a. Name:** `A — Migration, overlays, and dependency interactions`

**b. Rule and location:** Legacy identifiers are migrated before overlay merging. Overlays distinguish absent keys, explicit nulls, empty collections, and ordinary values. Dependency resolution operates on the effective merged configuration, not on individual source layers. Location: `compiler_contract.md`, canonicalization, merge, and dependency sections.

**c. Likely reflex error:** Merge each source independently, then resolve connector dependencies using the pre-merge bindings.

**d. Hidden case:** A legacy connector is migrated to a current ID. A child tenant explicitly clears an inherited optional connector list, but a production overlay enables a feature that requires a different connector bundle. The resolution depends on migration, the empty-state meaning, and dependency closure together. Affected fields include binding IDs, effective options, activated connectors, and validation errors.

**e. Why samples do not reveal the error:** Visible samples contain no dependency whose required connector was removed by a post-migration overlay.

**f. Independence:** Medium-high. Migration, merge, and dependency results have separately checked intermediates.

#### Lever 2 — Dependent chain (STANDARD B)

**a. Name:** `B — Compiler-stage dependency`

**b. Rule and location:** Profiles must be derived from canonicalized source configuration after migration, inheritance, and overlay resolution. The validation and summary reports must describe those emitted profiles, not recompute from raw inputs. Location: `compiler_contract.md`, output dependency rules.

**c. Likely reflex error:** Compute report counts from unmerged source rows or derive profile-specific counts before compatibility validation.

**d. Hidden case:** Two tenant bindings collapse into one canonical binding after migration, while one is disallowed in production. A raw-row report counts two bindings; a pre-validation production profile retains both. The canonical binding count, active connector count, and production validation findings differ.

**e. Why samples do not reveal the error:** The visible migration examples are one-to-one, and their source counts equal their canonical counts.

**f. Independence:** High. Each profile and report is tested separately.

#### Lever 3 — Supplied tool audit and repair (STANDARD C)

**a. Name:** `C — Repair the layered configuration resolver`

**b. Rule and location:** The agent must audit and repair the supplied package against the written compiler contract. The package contains multiple defects in overlay state handling, selector scope, and validation provenance. Location: `compiler_contract.md`, package behavior and CLI invocation sections.

**c. Likely reflex error:** Fix the visible merge defect while leaving selector and provenance defects untouched, or bypass the CLI with one-off generation code.

**d. Hidden case:** A resource is inherited by a tenant and excluded by a child policy selector. Its connector also uses an explicit empty option list. A partial repair can resolve the option correctly but keep the excluded resource or emit an invalid provenance explanation. Affected outputs include the profile's resource membership, resolved connector options, and validation report.

**e. Why samples do not reveal the error:** Sample inheritance, selector expansion, and validation cases use separate, uncomplicated configurations.

**f. Independence:** Medium. The three supplied defects have isolated checks, along with combined tests.

#### Lever 4 — Orthogonal configuration states (STANDARD E)

**a. Name:** `E — Missing, null, and empty are different states`

**b. Rule and location:** An absent field inherits according to the documented parent chain; explicit null means clear or disable only when the field's type contract permits it; an empty list is an explicitly present zero-element value and does not trigger default inheritance. Location: `compiler_contract.md`, field-state table.

**c. Likely reflex error:** Use ordinary dictionary updates or truthiness to treat null, empty, and absent values alike.

**d. Hidden case:** A parent has two enabled connectors; a child sets an empty connector list; a production overlay leaves the field absent. The correct child resolution is empty, but the production overlay's absent field follows the stated inheritance rules for its position in the layer sequence. The connector list, dependency errors, and summary counts change under simple truthiness merging.

**e. Why samples do not reveal the error:** Visible overlays either specify nonempty values or omit the field entirely; they do not mix explicit emptiness with later inheritance.

**f. Independence:** High. Merge-state behavior can be graded before dependency solving.

#### Lever 5 — NEW: Selector exclusion is evaluated at a specified scope

**a. Name:** `NEW — Scope-aware selector subtraction`

**b. Rule and location:** Inclusion selectors expand against the full declared resource inventory at the policy scope specified by the contract. Exclusions then remove members from that expanded set for that same policy scope. An exclusion cannot remove resources granted by an unrelated policy unless the policies share an explicit combining scope. Location: `compiler_contract.md`, resource selector semantics.

**c. Likely reflex error:** Globally subtract all exclusion matches after combining every tenant policy, or apply exclusions before resolving inclusion selectors.

**d. Hidden case:** One policy grants a wildcard set; an independent policy grants a single resource; a third policy excludes that resource only inside a narrowly scoped grant. Global subtraction removes a legitimate independent grant. Affected outputs include effective permissions, authorized resource counts, and policy validation findings.

**e. Why samples do not reveal the error:** Visible policies contain simple inclusion selectors or exclusions that do not overlap independent grants.

**f. Independence:** High. Selector expansion and policy combination can be tested separately.

#### Lever 6 — NEW: Dependency bundles are atomic

**a. Name:** `NEW — Atomic connector dependency groups`

**b. Rule and location:** A declared all-or-none connector bundle is effective only when every required member is available and compatible. If any mandatory member cannot be activated, the whole bundle is inactive and receives the specified validation finding. Optional dependencies remain optional. Location: `compiler_contract.md`, dependency resolution.

**c. Likely reflex error:** Greedily activate every connector that appears individually compatible, then flag missing dependencies afterward without reverting the incomplete bundle.

**d. Hidden case:** Two required connectors are available, but the third is excluded by a production region constraint; one of the first two is also independently optional. A greedy implementation retains an invalid partial mandatory bundle. Activated connector IDs, validation codes, and effective feature flags differ.

**e. Why samples do not reveal the error:** Shipped dependency examples have all required members available or are missing exactly one independent optional connector.

**f. Independence:** Medium-high. Dependency closure can be graded using a supplied effective overlay.

#### Lever 7 — NEW: Secret references remain opaque and scope-bound

**a. Name:** `NEW — Secret reference provenance`

**b. Rule and location:** Configurations contain secret reference identifiers, never secret values. A reference is valid only when it exists and its declared consumer scope permits the resolved connector and environment. The compiler preserves the reference identifier and never materializes a value from the log. Location: `compiler_contract.md`, secret policy.

**c. Likely reflex error:** Treat a nonempty reference as universally valid, inline an available placeholder, or validate existence without validating scope.

**d. Hidden case:** A valid secret reference is permitted for development but not production, while the same connector is inherited into both profiles. The development profile remains valid; production receives an error without leaking a value or deleting the reference. The production status, secret validation count, and report provenance change.

**e. Why samples do not reveal the error:** Visible secret references are either valid in both environments or missing in both.

**f. Independence:** High. Secret validation is independent of selector subtraction.

### 8. Rejection paths

The compiler contract specifies exact errors, including:

- `E_PARENT_CYCLE:<canonical_tenant_id>`
- `E_UNKNOWN_CONNECTOR:<connector_id>`
- `E_SCHEMA_INCOMPATIBLE:<binding_id>`
- `E_SELECTOR_UNKNOWN_RESOURCE:<resource_id>`
- `E_DEPENDENCY_BUNDLE_INCOMPLETE:<bundle_id>`
- `E_CONNECTOR_CONFLICT:<sorted_connector_ids>`
- `E_SECRET_MISSING:<reference_id>`
- `E_SECRET_SCOPE:<reference_id>:<environment>`

IDs and multi-ID lists use the documented escaping and sorting rules. The compiler continues across independent tenants and profiles whenever the contract permits, rather than failing the entire run after the first validation issue. Errors involving impossible structural prerequisites stop only the affected resolution branch.

### 9. Partial-credit plan

Use **50 independent checks**, worth 100 points.

| Check group | Independent checks | Points | Heavy checks |
|---|---:|---:|---|
| Lever A: migration/overlay/dependency interactions | 7 | 18 | 4 |
| Lever B: compiler chain and report correctness | 8 | 20 | 5 |
| Lever C: supplied package defects | 6 | 12 | 3 |
| Lever E: three-state merge semantics | 7 | 12 | 3 |
| NEW selector scope | 7 | 12 | 3 |
| NEW atomic dependency bundles | 8 | 14 | 4 |
| NEW secret provenance | 7 | 12 | 3 |
| **Total** | **50** | **100** | **25** |

The heaviest checks cover hidden configuration interactions, profile correctness, dependency closure, and the exact difference between absence and explicit emptiness. Individual checks cover deterministic package structure, correct output schemas, canonical identifiers, and validation error categories.

### 10. Reviewer checks on the work log

The reviewer looks for these 12 concrete statements:

1. The log identifies the source of canonical connector identities.
2. It explains the specified order of migration and overlay application.
3. It distinguishes absent fields from explicit null and empty values.
4. It identifies the inventory used to expand selectors.
5. It explains how independent policy scopes interact.
6. It names the all-or-none behavior for mandatory dependency groups.
7. It identifies the metadata source for secret existence and scope.
8. It states how production differs from development validation.
9. It identifies the authoritative input for tenant inheritance.
10. It explains what information is included in the validation report's provenance.
11. It identifies which report values are derived from final profiles rather than source rows.
12. It states what makes the repaired ZIP reusable on fresh inputs.

These checks validate the work log's descriptions of the actual resolution design, not the mere presence of a README or the fact that a build command was run.

### 11. Shortcuts and cheats

- **Hardcoding two profiles:** Hidden tests add and modify tenant and connector records.
- **Generating JSON without repairing the CLI:** Fresh-input tests invoke the package.
- **Ignoring TOML or XML configuration:** Each source feeds graded profile or validation fields.
- **Treating falsy values as missing:** Empty arrays and explicit nulls appear in hidden combinations.
- **Using one globally flattened policy set:** Hidden selectors overlap across policy scopes.
- **Activating dependencies greedily:** Hidden bundles have multiple required members and conflicting constraints.
- **Embedding secrets or placeholder values:** Contract validation requires opaque references and scope-aware checks.
- **Writing a nondeterministic ZIP:** Tests check the documented package structure and deterministic archive properties.
- **Relying on current row order:** Reordered inputs must produce the same resolved profiles and reports.

### 12. Expected scores

| Lever | Lazy agent | Careful-but-hurried agent | Why |
|---|---:|---:|---|
| A | 0/18 | 2–4/18 | Independent rules pass while post-merge dependencies fail. |
| B | 2/20 | 4–5/20 | Source-derived counts differ from final-profile counts. |
| C | 1/12 | 2–3/12 | One-off fixes leave other resolver defects intact. |
| E | 2/12 | 2–3/12 | Common merge idioms collapse three intentionally distinct states. |
| NEW selector scope | 0/12 | 1–2/12 | Global exclusion subtraction over-removes independent grants. |
| NEW atomic bundles | 1/14 | 2–3/14 | Greedy dependency activation produces invalid partial bundles. |
| NEW secret provenance | 1/12 | 1–2/12 | Existence-only validation misses profile-specific authorization. |

**Expected total test score:** lazy 5–9%; careful-but-hurried 13–18%; perfect 100%.

### 13. Nearest known benchmark task or textbook problem

Nearest: configuration inheritance, policy evaluation, compiler passes, and dependency resolution.

Difference: conventional configuration tasks usually focus on precedence, templating, or schema validation. This benchmark combines configuration state semantics with migration, scope-aware policy selectors, atomic dependency groups, and environment-sensitive secret authorization in a reusable repaired CLI. A flat merge or greedy resolver can pass easy fixtures yet fail the hidden composition.

### 14. Solvability argument

The task uses standard Python libraries for ZIP, CSV, JSON, XML, INI, TOML, TSV, and log parsing. The dependency relations and merge rules are explicit, and the fixed output formats bound the required implementation.

An expert can use a canonical internal representation and separate graph traversal, merge, dependency, and validation stages. The task is difficult because the stages interact, not because the rules must be guessed. The two-hour constraint is credible when the supplied program is small and each quiet defect is localized.

### 15. Biggest risk

The principal risk is ambiguous policy composition: the contract must precisely define how grants, exclusions, inheritance, and all-or-none dependencies interact. It must also clearly identify which selector semantics are local to one policy and which combine across policies. A merely implied scope rule would be unfair.

---

## Idea 4 — Schema Migration Repository Repair: Repairing Transformations Across Long Migration Chains

### 1. Title and one-sentence pitch

**Schema Migration Repository Repair:** Repair a multi-module ETL transformation repository so it selects and applies valid schema migrations over long dependency chains while preserving field semantics, idempotent replay, and exact audit classifications on unseen partner feeds.

### 2. Setting

A data engineering team consolidates operational records from partner systems that have evolved independently. Each partner publishes schema revisions and migration definitions, and historical feeds may have to pass through several revisions before they match the current canonical contract.

The existing repository handles simple upgrades but silently loses field-state distinctions, mishandles some migration prerequisites, and gives unreliable results when several valid paths exist. The team needs a repaired repository that transforms fresh data deterministically and exposes accurate module-level repair and validation reports.

### 3. Archetype and fixed output mapping

**Archetype:** `repo-patch`

The fixed outputs are:

- `out/patched-repo.zip`: the reusable, corrected transformation repository.
- `out/repair-report.json`: the documented defects addressed and their verified behavioral categories.
- `out/module_core.json`: core identity, canonical-record, and reconciliation module report.
- `out/module_parser.json`: parser, schema-reading, and field-state handling report.
- `out/module_report.json`: reporting module validation.
- `out/test_fixes.json`: regression-fix inventory and covered failure classes.
- `out/summary.json`: exact totals and cross-module reconciliation findings.

No further output files may be introduced. The repository must include working transformation logic, not merely the report files or a patched copy of the visible output.

### 4. Deliverable program

The agent repairs the supplied repository so it:

1. Reads source rows from the supported input feeds.
2. Resolves schemas and partner identifiers.
3. Builds a graph of valid migrations.
4. Selects a valid migration plan under the documented objective.
5. Applies migration steps while preserving missing-versus-null semantics and other declared field policies.
6. Applies source corrections and replay rules.
7. Emits canonical records and structured quality findings.
8. Generates the fixed package and module reports.

On fresh inputs, the repository must support schema revisions and migration graphs not present in the visible fixtures, provided they follow the shipped contract. It must not depend on module names, known migration IDs, a precomputed migration path, or existing sample outputs.

### 5. Input files

The task ships 12 input files using at least seven standard-library-readable formats.

| File | Format and approximate size | Contents and dependencies |
|---|---|---|
| `source_repo.zip` | ZIP archive containing Python modules | Multi-layer ETL repository with documented silent defects in parser, migration planner, and report integration. |
| `repository_contract.md` | Markdown, about 300 lines | Canonical schema contract, migration objective, field-state rules, replay semantics, module APIs, exact errors, and output schemas. |
| `schema_versions.json` | JSON, about 60 revisions | Schema IDs, field definitions, source compatibility, and target revision information. |
| `migration_edges.csv` | CSV, about 500 directed edges | Migration source/target revisions, prerequisite conditions, field transformations, and documented loss costs. |
| `field_policy.tsv` | TSV, about 600 entries | Per-field semantics for missing, explicit null, defaults, units, and value-preservation requirements. |
| `partner_aliases.xml` | XML, about 250 aliases | Partner-scoped identifier aliases and their canonical representations. |
| `null_semantics.ini` | INI, about 80 sections | Field-specific null, absence, and default policies. |
| `partner_batches.jsonl` | JSONL, about 5,000 records | Versioned partner data, schema IDs, source record identifiers, and partition metadata. |
| `correction_log.txt` | Plain text, about 1,000 entries | Source-record corrections and correction lineage. |
| `replay_manifest.csv` | CSV, about 700 entries | Batch and record replay identities, payload fingerprints, and previously declared replay status. |
| `report_taxonomy.json` | JSON, about 100 classifications | Quality severity mappings, error categories, and required report grouping. |
| `partner_order.tsv` | TSV, about 80 entries | Contracted partner and batch processing order used by stateful reconciliation. |

Each file contributes to either transformation outputs, module reports, or validation reports. Schema versions and migration edges determine path validity; field policy and null semantics determine the transformed values; aliases and corrections alter canonical record resolution; replay manifests determine idempotency classification; and taxonomy defines error reporting.

Three dependency chains are:

1. `schema_versions.json` → `migration_edges.csv` → migration planner in `source_repo.zip` → `field_policy.tsv` → canonical transformed record.
2. `partner_aliases.xml` → `partner_batches.jsonl` identity resolution → `correction_log.txt` correction validation → `replay_manifest.csv` replay reconciliation → core module and summary reports.
3. `null_semantics.ini` → per-field migration behavior → transformed record values → `report_taxonomy.json` classification → parser, core, and report module outputs.

### 6. Spine: dependent processing stages

1. **Audit the repository:** Identify the existing module boundaries and observable defects.
2. **Parse contracts:** Load schema versions, migration edges, field semantics, aliases, corrections, and replay metadata.
3. **Canonicalize source records:** Resolve source-specific identity and field representations.
4. **Build migration graph:** Identify valid directed transitions and prerequisites.
5. **Choose migration plan:** Select the valid path according to the exact stated objective.
6. **Execute transformations:** Apply migration operations in order and preserve field-state semantics.
7. **Reconcile corrections and replay:** Ensure that valid corrections alter the proper records without causing replay side effects.
8. **Classify outcomes:** Produce canonical records, rejected records, and quality findings using the supplied taxonomy.
9. **Generate and cross-check reports:** Produce the fixed module reports and summary.

The harness checks the migration planner using supplied correct graph states and checks individual transformations with a supplied correct plan. This preserves partial credit for correct transformation semantics independently of a flawed path search.

### 7. Levers

#### Lever 1 — Hidden composition (STANDARD A)

**a. Name:** `A — Migration, field-state, and replay interaction`

**b. Rule and location:** A migration is valid only if its prerequisites hold on the record state produced by earlier steps. Each step applies the field policy for missing and null values. Replay and corrections are resolved after canonical identity, using the exact payload fingerprint and correction rules. Location: `repository_contract.md`, migration, field-state, and replay sections.

**c. Likely reflex error:** Select a migration path based only on revision graph connectivity and apply its operations without considering record state.

**d. Hidden case:** Two migrations are graph-valid, but the preferred path requires a field that is absent in the input record; another path produces that field from an earlier transformation. A correction also changes the replay fingerprint of the resulting record under the documented rule. The affected outputs include chosen migration path, transformed field value, replay status, and quality classification.

**e. Why samples do not reveal the error:** Sample migration paths use prerequisites satisfied by every supplied record, and correction examples do not modify any migration prerequisite.

**f. Independence:** Medium-high. Planner correctness, migration execution, and replay classification have separate checks.

#### Lever 2 — Dependent chain (STANDARD B)

**a. Name:** `B — Graph-to-report dependency`

**b. Rule and location:** Module reports must be derived from actual corrected transformation outcomes. The migration planner's selected path must drive the transformation module, and the transformation module's output must drive quality classifications and summaries. Location: `repository_contract.md`, module contract and output semantics.

**c. Likely reflex error:** Build independent summary counts from input revision IDs or report successful upgrades when the planner has found any path, even if its path was not executed successfully.

**d. Hidden case:** A record has a valid three-step path but fails on the second step because a required field is absent. A planner-only success counter reports a completed migration, while the correct module report classifies the attempted record according to the contract. Affected outputs include completed and failed migration counts, canonical revision, and error category.

**e. Why samples do not reveal the error:** Visible paths are executable in full and therefore make path existence and successful execution coincide.

**f. Independence:** High. Each module's behavior and resulting report can be independently checked.

#### Lever 3 — Audit and repair existing code (STANDARD C)

**a. Name:** `C — Repair the migration repository`

**b. Rule and location:** The supplied repository has documented functional defects; the repaired package must satisfy the contract while retaining the prescribed public interfaces. The instruction describes observable behavior, while the code itself supplies implementation context. Location: `repository_contract.md`, public API and behavior contract.

**c. Likely reflex error:** Reimplement the visible scenario in the driver instead of repairing the reusable modules, or change a single conditional without correcting the shared abstraction.

**d. Hidden case:** A migrated field is correct when the parser is called directly but wrong when the report module obtains the same record through the public pipeline. The defect lies in an intermediate representation shared by multiple modules. The module-specific state, error classification, and final count differ.

**e. Why samples do not reveal the error:** The examples exercise the modules individually and use a path that does not expose the shared representation defect.

**f. Independence:** Medium. Module-level tests award credit separately, but the integration defect affects several modules.

#### Lever 4 — Algorithmic size ladder (STANDARD D)

**a. Name:** `D — Migration graph size ladder`

**b. Rule and location:** Migration paths must follow directed, prerequisite-valid edges. The contract defines an exact path objective, a deterministic tie-break, and the allowed input limits. The largest hidden graph contains exponentially many possible paths if enumerated naively, while dynamic programming over the documented state representation can solve it within the time budget. Location: `repository_contract.md`, planner algorithm contract and graph limits.

**c. Likely reflex error:** Enumerate every migration path and compare complete path sequences, or use the first reachable path found by depth-first search.

**d. Hidden case:** A large layered migration graph has many paths with similar costs. Some edges are invalid for the current record state, and multiple remaining paths have equal primary cost. Enumeration exceeds the operation limit, while a planner using the specified dynamic-programming state and tie-break returns the required route. The selected path, migration status, and completion counts change.

**e. Why samples do not reveal the error:** The visible graphs contain few paths and can be solved by any search method within the time limit.

**f. Independence:** High. Planner checks use direct graph inputs and do not require full ETL output generation.

#### Lever 5 — NEW: Migration optimization is record-state-dependent

**a. Name:** `NEW — State-dependent migration feasibility`

**b. Rule and location:** An edge with declared prerequisites may be applied only when those prerequisites hold on the current intermediate record. Graph-level connectivity is necessary but insufficient for a valid record-specific plan. The planner must consider the documented state signature that determines edge feasibility; it need not enumerate arbitrary data values. Location: `repository_contract.md`, migration prerequisites.

**c. Likely reflex error:** Compute one globally shortest graph path for each source/target schema pair and reuse it for every record.

**d. Hidden case:** Two records share source and target schema revisions but have different field-presence states. A migration edge requiring the same source field is valid for one and invalid for the other. The chosen path, transformed value, and migration outcome differ.

**e. Why samples do not reveal the error:** Visible records of the same schema revision share the same prerequisite fields.

**f. Independence:** Medium-high. Path feasibility is independently checkable from supplied record state.

#### Lever 6 — NEW: Corrections do not erase field-state provenance

**a. Name:** `NEW — Missing/null provenance through migration`

**b. Rule and location:** The normalized state must distinguish an absent field from a field explicitly set to null until the contract-defined transformation intentionally collapses them. A migration default may apply to an absent field but not to an explicit null unless the field policy explicitly says otherwise. Location: `field_policy.tsv`, `null_semantics.ini`, and `repository_contract.md`.

**c. Likely reflex error:** Represent both absent and null values as the same Python value and apply defaults using a simple presence check.

**d. Hidden case:** Two otherwise identical records differ only in whether a field is absent or explicitly null. A migration default should populate one but retain the specified null state in the other. The transformed value, migration feasibility, and quality classification change.

**e. Why samples do not reveal the error:** Sample migration defaults appear only on absent fields; null values occur only on fields with no applicable default.

**f. Independence:** High. Field-state correctness can be checked with a precomputed migration plan.

#### Lever 7 — NEW: Replay identity is fingerprint-sensitive after canonicalization

**a. Name:** `NEW — Canonical replay identity`

**b. Rule and location:** Replay identity uses the source-scoped batch/record key and the payload fingerprint computed at the stage prescribed by the contract. Same identity and same fingerprint is an idempotent replay; same identity and different fingerprint is a conflict; a new identity with an identical payload is not automatically a duplicate. Correction handling follows the explicitly stated fingerprint semantics. Location: `repository_contract.md`, replay rules and `replay_manifest.csv` schema.

**c. Likely reflex error:** Deduplicate by record ID alone or by payload content alone.

**d. Hidden case:** A corrected record retains its source identity but receives a new valid fingerprint. Another record from a different source has identical content but a different source-scoped identity. The correct system classifies one according to the correction/replay policy and retains the other as a separate record. Replay counts and quality classifications differ.

**e. Why samples do not reveal the error:** Visible duplicate cases are repeated records with both identical identity and identical fingerprints.

**f. Independence:** High. Replay identity can be validated after correct canonicalization is supplied.

### 8. Rejection paths

Exact contract-defined errors include:

- `E_SCHEMA_UNKNOWN:<schema_id>`
- `E_MIGRATION_UNREACHABLE:<source_schema>:<target_schema>`
- `E_MIGRATION_PRECONDITION:<edge_id>:<field_id>`
- `E_MIGRATION_CYCLE:<edge_id>`
- `E_RECORD_PARSE:<source>:<record_id>`
- `E_REPLAY_CONFLICT:<source>:<record_id>`
- `E_CORRECTION_INVALID:<correction_id>`

Where the error depends on the current record state, the contract specifies whether it invalidates one migration edge, one candidate path, or the entire record. A record with no valid plan must not be silently marked as migrated or omitted from the report.

### 9. Partial-credit plan

Use **52 independent checks**, worth 100 points.

| Check group | Independent checks | Points | Heavy checks |
|---|---:|---:|---|
| Lever A: hidden migration/state/replay interactions | 7 | 17 | 4 |
| Lever B: pipeline and module report dependencies | 8 | 18 | 4 |
| Lever C: repository repairs | 7 | 12 | 3 |
| Lever D: migration graph size ladder | 7 | 16 | 4 |
| NEW state-dependent feasibility | 8 | 14 | 4 |
| NEW missing/null provenance | 7 | 11 | 3 |
| NEW canonical replay identity | 8 | 12 | 3 |
| **Total** | **52** | **100** | **25** |

The heavy tests include the largest migration graphs, records for which only some edges satisfy prerequisites, shared module defects, and conflict-sensitive replay behavior. Independent checks cover direct module calls, parser behavior, error reporting, package validity, and deterministic report schemas.

### 10. Reviewer checks on the work log

The reviewer checks these 12 statements:

1. The log identifies which module owns migration planning.
2. It explains why graph reachability alone cannot establish record-level feasibility.
3. It names the contract's migration objective and tie-break.
4. It identifies which field states influence migration prerequisites.
5. It describes how absent and explicit-null fields are represented internally.
6. It identifies the source of canonical partner aliases.
7. It states the replay identity components.
8. It explains the stage at which replay fingerprints are interpreted.
9. It names the module responsible for final quality taxonomy.
10. It identifies which module-level reports help separate parser failures from planner failures.
11. It explains why the largest migration graph needs a bounded-state planner instead of enumerating complete paths.
12. It identifies the public execution path that fresh-input tests invoke.

The reviewer reads these as factual statements about the completed repository, rather than rewards for writing a long explanation.

### 11. Shortcuts and cheats

- **Hardcoding known migration paths:** Hidden graphs change edges and prerequisites.
- **Using schema ID alone as the planning state:** Hidden records with the same schemas have different field states.
- **Enumerating every path:** The largest graph exceeds the stated operation budget for naive enumeration.
- **Changing only the report generator:** Fresh tests call the public transformation pipeline and individual modules.
- **Replacing missing and null with one value:** Hidden records differ only by field presence.
- **Deduplicating by ID or content alone:** Hidden replay fixtures separate source identity, fingerprint, and correction semantics.
- **Trusting source row order:** Inputs are permuted where order is declared irrelevant.
- **Returning correct reports but shipping broken code:** The patched ZIP is executed on fresh files and its public interfaces are graded.
- **Reading hidden expected results:** Only schemas, migration definitions, source records, and documented rules ship with the task.

### 12. Expected scores

| Lever | Lazy agent | Careful-but-hurried agent | Why |
|---|---:|---:|---|
| A | 0/17 | 2–4/17 | A schema-only migration choice misses record-state and replay interactions. |
| B | 2/18 | 3–5/18 | Path existence and successful execution are mistakenly treated as equivalent. |
| C | 1/12 | 2–3/12 | Narrow patches do not repair shared module behavior. |
| D | 1/16 | 2–4/16 | Naive path search fails as migration graphs expand. |
| NEW state feasibility | 1/14 | 2–3/14 | One path per schema pair fails for records with different prerequisite states. |
| NEW null provenance | 1/11 | 1–2/11 | Common defaulting logic collapses absence and null. |
| NEW replay identity | 1/12 | 1–2/12 | Conventional deduplication ignores the declared identity components. |

**Expected total test score:** lazy 5–9%; careful-but-hurried 13–18%; perfect 100%.

### 13. Nearest known benchmark task or textbook problem

Nearest: schema evolution, graph-based migration planning, ETL regression repair, and idempotent message processing.

Difference: textbook migration planning usually operates on a graph whose edges are universally applicable. This benchmark makes edge feasibility depend on record state, couples migrations with field-state provenance and replay fingerprints, and requires repairing a real multi-module pipeline under a bounded graph-size contract.

### 14. Solvability argument

The task is solvable because migration constraints, path objectives, and field-state behavior are all defined. The planner does not need to solve a general NP-hard problem; the contract gives a finite state representation and a directed graph structure suited to a bounded dynamic-programming or graph-search solution.

The repository already supplies the module boundaries and public interfaces. The expert can establish correctness stage by stage and use module-level checks for partial credit, without having to understand an unrelated production codebase.

### 15. Biggest risk

The biggest risk is an incomplete formal definition of the migration planner's state and objective. If feasibility depends on undocumented fields, or if the tie-break is implicit, two reasonable implementations may disagree. The contract must expose the complete state signature and an explicit deterministic ordering.

---

## Idea 5 — Ingestion Control-Plane Reconciliation: Driving a Stateful Service to a Verifiable Data State

### 1. Title and one-sentence pitch

**Ingestion Control-Plane Reconciliation:** Operate a local ingestion service through its CLI and HTTP API to ingest partner batches, resolve idempotency and lease conflicts, finalize authoritative data, and produce exact state and transcript reports under deliberately interacting workflow constraints.

### 2. Setting

A central data platform receives scheduled batches from dozens of partner systems. An ingestion service provides staging, schema validation, chunk uploads, batch reconciliation, and final commit operations. A valid upload is not necessarily committed data, and a successful HTTP response may only acknowledge staging or acceptance into a queue.

An operator must use the service's documented control plane to reach a required final state. Duplicate submissions, expired worker leases, corrections, chunk limits, and transaction prerequisites can make a seemingly successful workflow incomplete or inconsistent. The final reports must reflect service state, not simply the number of requests attempted.

### 3. Archetype and fixed output mapping

**Archetype:** `service-interaction`

The task requires all seven fixed outputs:

- `out/final_state.json`: authoritative service state after the prescribed workflows.
- `out/report.json`: reconciliation and validation results for that final state.
- `out/scenario_alpha.json`: outcome and state summary for scenario alpha.
- `out/scenario_beta.json`: outcome and state summary for scenario beta.
- `out/scenario_mode.json`: outcome and state summary for the specified alternate operating mode.
- `out/transcript_summary.json`: deterministic counts of the required CLI and HTTP operations, response classes, and verified state transitions.
- `out/summary.json`: cross-scenario totals and final-state invariants.

The service simulator and task contract define the exact output schemas, state transitions, response interpretation, and reporting rules. The agent may not add output files or claim success based merely on an HTTP status code.

### 4. Deliverable program

The agent must discover, start, and use the supplied local service through its documented CLI and HTTP API. Its workflow must:

1. Load and understand the service contract, inputs, resource limits, and initial state.
2. Normalize the source records and map their identities to the service's accepted identifiers.
3. Construct batches with the required schema and chunk boundaries.
4. Acquire and maintain valid write leases.
5. Submit uploads using the specified idempotency keys and payload semantics.
6. Reconcile accepted, rejected, repeated, and conflicting operations.
7. Apply corrections and finalize batches only when the required prerequisites hold.
8. Retrieve and verify authoritative final state.
9. Emit the fixed scenario and summary reports.

The agent must build a reusable driver or equivalent executable logic that works on fresh input files. Direct mutation of service database files or simulator internals is prohibited. State changes must occur through the exposed interfaces.

### 5. Input files

The task ships 12 inputs in at least seven standard-library-readable formats, in addition to the service simulator package and its API definition.

| File | Format and approximate size | Contents and dependencies |
|---|---|---|
| `service_contract.md` | Markdown, about 300 lines | API and CLI semantics, state machine, ordering, quotas, lease semantics, error codes, exact output schemas, and scenario completion criteria. |
| `service_simulator.zip` | ZIP containing Python service and CLI | Local ingestion control plane with observable state and documented interfaces. |
| `api_schema.json` | JSON | Accepted request/response structures, required fields, and schema versions. |
| `partner_registry.csv` | CSV, about 300 partners | Partner IDs, canonicalization scope, active schemas, and environment or region constraints. |
| `source_aliases.xml` | XML, about 200 mappings | Partner-scoped source identity aliases. |
| `schema_catalog.ini` | INI, about 100 sections | Canonical schema versions and allowed partner/source combinations. |
| `chunk_limits.tsv` | TSV, about 100 entries | Maximum rows and bytes per upload chunk, scoped by schema and operating mode. |
| `batch_alpha.jsonl` | JSONL, about 2,000 records | First partner batch, containing ordinary records, supported updates, and a subset of repeated events. |
| `batch_beta.jsonl` | JSONL, about 2,500 records | Second batch with corrections, replay cases, and cross-source identity interactions. |
| `lease_policy.json` | JSON | Lease durations, permitted renewal behavior, and fencing-token rules. |
| `replay_requests.log` | Plain text log | Declared request identities and replay intents; these establish intended workflows, not precomputed outcomes. |
| `commit_dependencies.csv` | CSV | Batch dependencies, required validation states, and the explicit rules for finalization order. |
| `correction_manifest.tsv` | TSV | Correction references, source record IDs, and required correction scope for the two batches. |

Every source changes a graded result. Chunk limits affect request construction; lease policy governs which writes can commit; commit dependencies constrain finalization; registry and aliases affect canonical IDs; and correction/replay sources affect the final service state and transcript report.

Three dependency chains are:

1. `partner_registry.csv` → `source_aliases.xml` → `schema_catalog.ini` → record normalization → batch upload construction → service-side validation.
2. `lease_policy.json` → lease acquisition and renewal → chunk uploads governed by `chunk_limits.tsv` → batch reconciliation → authoritative committed state.
3. `replay_requests.log` and `correction_manifest.tsv` → source record selection → `commit_dependencies.csv` → required commit order → final state and reconciliation report.

The service's initial state and API responses are observable inputs, but the task does not ship expected final state or a prerecorded answer transcript.

### 6. Spine: dependent processing stages

1. **Discover the service:** Read the contract, identify the exposed endpoints and CLI operations, and obtain the initial state through the supported interface.
2. **Normalize inputs:** Resolve partner and source aliases, validate schema compatibility, and prepare normalized source records.
3. **Plan batches:** Divide records into chunks according to row and byte limits, respecting the explicitly defined boundary conditions.
4. **Establish ownership:** Acquire a write lease and record the fencing token and expiry behavior.
5. **Upload data:** Submit chunks with the correct batch, payload, and idempotency identities.
6. **Resolve outcomes:** Distinguish accepted staging from committed records; reconcile duplicates, payload conflicts, rejected chunks, and corrections.
7. **Finalize:** Respect dependency order, validation results, lease validity, and all documented commit prerequisites.
8. **Verify:** Query the service's authoritative state and compare it against required invariants.
9. **Report:** Produce fixed scenario reports and transcript summaries from the service outcomes.

The grading harness can begin some tests with batches already staged or with valid leases supplied, allowing the finalization logic to earn partial credit separately from the interaction driver. Conversely, successful request submission does not award the points reserved for authoritative committed state.

### 7. Levers

#### Lever 1 — Hidden composition (STANDARD A)

**a. Name:** `A — Lease, idempotency, correction, and commit interaction`

**b. Rule and location:** Writes are valid only under the current lease fencing token; idempotency keys are bound to the documented request identity and payload fingerprint; corrections must target the specified canonical source record; and finalization requires every declared commit prerequisite. Location: `service_contract.md`, write, correction, replay, and commit sections.

**c. Likely reflex error:** Upload every chunk, retry all failures using the same idempotency key, and finalize once all requests appear successful.

**d. Hidden case:** A worker's lease becomes stale between two uploads. A retry uses a previously accepted idempotency key but changes the payload to include a correction. The correction is valid only if separately staged and reconciled before the dependent batch is committed. The affected outputs include accepted chunk count, conflict count, corrected record contents, batch status, and authoritative committed quantity.

**e. Why samples do not reveal the error:** Visible uploads complete under one lease and use either exact payload retries or a separate correction workflow.

**f. Independence:** Medium-high. Lease, replay, correction, and commit outcomes have separate response and state checks.

#### Lever 2 — Dependent chain (STANDARD B)

**a. Name:** `B — Request submission to authoritative state`

**b. Rule and location:** Reports must describe the final state read through the supported service interface. A successful request, staged batch, accepted chunk, or validation result is not equivalent to a completed commit. Location: `service_contract.md`, state machine and report contract.

**c. Likely reflex error:** Count successful upload responses as ingested records or infer committed status from a batch-acceptance response.

**d. Hidden case:** A batch has every chunk accepted, but its required predecessor has not committed. The service reports that the batch is staged and cannot finalize. A shortcut reports it as ingested; the correct final state preserves staging while the committed-record count remains unchanged. The affected batch status, committed count, dependency finding, and scenario summary differ.

**e. Why samples do not reveal the error:** Every visible accepted batch has its dependencies already satisfied, so staging and commit quickly follow one another.

**f. Independence:** High. Final-state queries and report invariants can be checked without testing every request-construction path.

#### Lever 3 — Orthogonal operational constraints (STANDARD E)

**a. Name:** `E — Row limits and byte limits are independent`

**b. Rule and location:** Each upload chunk must satisfy both the maximum number of records and maximum serialized byte length under the exact serialization rules in the contract. Reaching either limit requires a new chunk; a chunk may not exceed the other limit merely because one limit has not been reached. Location: `chunk_limits.tsv` and `service_contract.md`.

**c. Likely reflex error:** Chunk only by record count, or estimate payload bytes from record count rather than the contracted serialization.

**d. Hidden case:** A small group of records contains unusually large text and crosses the byte limit before reaching the row limit. The naive chunk exceeds the service limit and is rejected. Correct chunking changes chunk count, accepted record count, retry count, and the final transcript summary.

**e. Why samples do not reveal the error:** Visible batches use similar-sized records and the row limit is reached before the byte limit.

**f. Independence:** High. Chunk construction can be graded from the input records and service limits alone.

#### Lever 4 — Explicit service refusal behavior (STANDARD F)

**a. Name:** `F — Invalid state transitions must not be hidden by retries`

**b. Rule and location:** The contract defines exact response codes and state effects for stale leases, payload conflicts, missing dependencies, invalid schema bindings, duplicate committed records, and illegal transitions. Repeating a rejected operation does not convert it into a valid one unless a prescribed precondition is repaired. Location: `service_contract.md`, error and state-transition tables.

**c. Likely reflex error:** Retry every non-success response indiscriminately or count a conflict as an idempotent duplicate.

**d. Hidden case:** A retry uses the same idempotency key with a different payload after the original request was accepted. The service's exact conflict behavior differs from an identical-payload replay. A generic retry loop can repeatedly submit the changed payload and misreport it as committed. Error classes, retry counts, batch state, and final records differ.

**e. Why samples do not reveal the error:** Visible retries reproduce identical payloads and use a live lease.

**f. Independence:** High. The response classification is directly testable without a full end-to-end workflow.

#### Lever 5 — NEW: Fencing tokens are monotonic ownership epochs

**a. Name:** `NEW — Stale-worker fencing`

**b. Rule and location:** Each successfully acquired ownership lease receives a fencing token. Once a newer token is issued for the same protected resource, operations carrying older tokens cannot mutate it, even if the older worker previously received a successful response or believes its lease remains valid. Token order and protected scope are explicitly defined. Location: `lease_policy.json` and `service_contract.md`.

**c. Likely reflex error:** Compare the submitted lease's nominal expiry only, or assume a worker retains write authority until it notices expiration.

**d. Hidden case:** Worker A holds token N. Worker B acquires token N+1 after the permitted lease transition. Worker A subsequently submits a chunk that would otherwise fit the row and byte limits. The service refuses A's stale write even if A's local clock still considers its lease valid. The accepted count, rejection class, and final record set change.

**e. Why samples do not reveal the error:** Visible workflows use only one lease owner per resource.

**f. Independence:** High. State-changing requests can be tested with known-issued tokens.

#### Lever 6 — NEW: Idempotency identity binds request identity to payload digest

**a. Name:** `NEW — Payload-bound idempotency`

**b. Rule and location:** Repeating the same idempotency identity with the same normalized payload produces the contract-defined replay result without applying data twice. Reusing that identity with a different normalized payload produces a conflict. Identical payloads under distinct request identities are not automatically equivalent to replays. The stage at which the digest is calculated is explicitly specified. Location: `service_contract.md`, replay contract.

**c. Likely reflex error:** Deduplicate on request ID alone, or hash raw JSON bytes despite the contract defining normalized payload identity.

**d. Hidden case:** The same semantic payload is serialized with a different object key order for a retry, while another request reuses the same identity but modifies a corrected value. Under the specified normalization, the first is an exact replay and the second is a conflict. Affected fields include replay status, conflict count, accepted records, and transcript classifications.

**e. Why samples do not reveal the error:** Visible request bodies use the same serialized representation on every retry, and no visible identity is reused with a changed payload.

**f. Independence:** High when request acceptance is supplied as a known service response.

#### Lever 7 — NEW: Corrections become authoritative only at the specified commit boundary

**a. Name:** `NEW — Staged versus committed correction visibility`

**b. Rule and location:** A correction accepted into a staging batch does not change authoritative records until the batch is validated and committed. Corrections are visible in staged-state queries only where the API contract explicitly exposes them. If the batch is rejected, the authoritative record retains its pre-correction committed value. Location: `service_contract.md`, staged-state and commit semantics.

**c. Likely reflex error:** Treat an accepted correction request as an immediate update to the committed ledger, or assume rejection cannot undo a staged change.

**d. Hidden case:** A correction is accepted into a staged batch but that batch later fails a dependency check. A dependent report must show the original committed value and an uncommitted correction outcome. The shortcut displays the corrected value in `final_state.json` and inflates committed counts.

**e. Why samples do not reveal the error:** Visible corrections are submitted in batches that immediately pass all commit prerequisites.

**f. Independence:** Medium-high. Committed versus staged visibility can be tested using a supplied service state.

### 8. Rejection paths

The contract defines exact service response classes and final-state effects for:

- Invalid lease acquisition or renewal.
- Stale fencing token on a write.
- Chunk that exceeds the contracted row or byte limit.
- Invalid schema or partner binding.
- Reuse of an idempotency key with a different payload.
- Missing commit prerequisite.
- Invalid correction target.
- Illegal batch-state transition.

The agent must distinguish server-side refusal, retryable operational conditions, and deterministic client-side invalid inputs. The exact response body and whether the service mutates state are both part of the contract. Where a request fails, the transcript and final-state reports must reflect the specified outcome rather than infer success from prior attempts.

### 9. Partial-credit plan

Use **52 independent checks**, worth 100 points.

| Check group | Independent checks | Points | Heavy checks |
|---|---:|---:|---|
| Lever A: interacting lease, correction, replay, and commit cases | 7 | 18 | 4 |
| Lever B: authoritative state and dependency chain | 8 | 20 | 5 |
| Lever E: dual chunk constraints | 7 | 12 | 3 |
| Lever F: refusal and retry behavior | 7 | 12 | 3 |
| NEW fencing-token behavior | 8 | 14 | 4 |
| NEW payload-bound idempotency | 8 | 13 | 4 |
| NEW correction visibility at commit | 7 | 11 | 3 |
| **Total** | **52** | **100** | **26** |

Heavy checks require verifying actual server-side state, exact idempotency outcomes, fencing behavior, and correct finalization. Independent checks cover request construction, individual scenario reports, chunk sizes, deterministic response classification, transcript summaries, and final-state schema.

### 10. Reviewer checks on the work log

The reviewer assesses these 12 concrete statements:

1. The log identifies which service interface exposes authoritative committed records.
2. It distinguishes request acknowledgement from committed ingestion.
3. It identifies the protected resource and scope of lease fencing.
4. It explains how the workflow records and reuses idempotency identities.
5. It states the contracted stage for payload normalization and digest calculation.
6. It identifies both chunk constraints and their respective input sources.
7. It explains how the batch dependency file affects finalization order.
8. It identifies the response class that indicates a payload conflict rather than a replay.
9. It states which service query is used to establish the final state.
10. It explains the difference between staged and authoritative correction visibility.
11. It distinguishes service-side refusals from client-side validation findings.
12. It identifies the service-observed evidence used to reconcile the scenario reports.

These checks require the log to communicate concrete operational facts consistent with a correct solution. They are not merely assertions that the agent used a CLI, sent HTTP requests, or waited for the service.

### 11. Shortcuts and cheats

- **Counting requests as records:** Final reports are checked against authoritative service state.
- **Modifying simulator storage directly:** The contract permits mutation only through the exposed CLI and API. The simulator's state and interaction transcript expose prohibited shortcuts.
- **Ignoring lease state:** Fresh tests issue competing tokens and require correct fencing.
- **Retrying every failed request:** The service distinguishes invalid transitions, retryable conditions, and idempotency conflicts.
- **Chunking by rows alone:** Variable record sizes and schema-specific limits exercise both constraints.
- **Treating staging as commit:** Hidden workflows leave batches staged, rejected, or blocked by dependencies.
- **Hashing arbitrary raw JSON bytes:** Fresh retries vary serialization while preserving or changing normalized payloads under the documented rules.
- **Hardcoding endpoint responses:** The service state and generated request identities differ across test scenarios.
- **Writing static report files:** The reports must match the final service state reached by the reusable workflow.

### 12. Expected scores

| Lever | Lazy agent | Careful-but-hurried agent | Why |
|---|---:|---:|---|
| A | 0/18 | 2–4/18 | Successful-looking uploads fail when leases, replay, corrections, and dependencies overlap. |
| B | 2/20 | 4–5/20 | Request counts cannot replace server-observed committed state. |
| E | 1/12 | 2–3/12 | Row-based chunking misses byte-limit failures. |
| F | 1/12 | 2–3/12 | Generic retry behavior confuses conflicts with safe replays. |
| NEW fencing | 0/14 | 1–2/14 | Client-side lease assumptions miss stale-token rejection. |
| NEW idempotency | 1/13 | 1–2/13 | Request ID alone is insufficient when payloads vary. |
| NEW correction visibility | 1/11 | 1–2/11 | Staged acceptance is mistaken for committed truth. |

**Expected total test score:** lazy 4–8%; careful-but-hurried 13–18%; perfect 100%.

### 13. Nearest known benchmark task or textbook problem

Nearest: API integration tests, message ingestion, transaction workflows, and distributed-system idempotency.

Difference: ordinary API exercises usually grade the requested responses or a final resource status. This benchmark ties multiple partner data feeds to a stateful ingestion workflow with fencing tokens, payload-bound idempotency, two independent chunk limits, deferred correction visibility, and commit dependencies. It requires reasoning about what the service actually committed rather than what the client attempted.

### 14. Solvability argument

The service is local, the CLI and HTTP contracts are explicit, and all domain identifiers, limits, schema rules, and state transitions are shipped as input. No external service, credentials, or undocumented network behavior is required.

An expert can inspect the API, build a deterministic interaction driver, use small state queries to verify transitions, and keep separate logic for normalization, chunking, leases, retries, reconciliation, and reporting. Hidden tests vary records and state combinations but remain inside the documented service contract. This makes complete correctness achievable without guessing API behavior.

### 15. Biggest risk

The primary fairness risk is nondeterminism in lease timing or asynchronous processing. The simulator must use a documented logical clock or otherwise deterministic expiry model, and all asynchronous transitions must have a contractual completion or polling condition. A benchmark that silently depends on wall-clock scheduling would penalize a correct solution unfairly.