GROUNDLINK month end settlement, working papers

This directory is the month end settlement snapshot for a satellite
operator that flies several missions through a shared ground segment.
Different systems recorded different parts of the same passes, so the
papers disagree in places. The settlement is the act of deciding which
record binds, in what order, and what each mission and each station is
owed at the end of it.

Where to start. Read pipeline_contract_overview.md first. It names the
fourteen stages and says which document owns each one. The stage
documents are spec_stage_s01 through spec_stage_s14 and they are the
binding text. interval_and_tiebreak_notes.md, rounding_and_precision.yml
and ordering_dependencies.yaml hold the rules that apply at every stage
rather than at one of them.

What the numbers are. Time is integer seconds. Volume is integer KiB.
Rates are integer milli KiB per second and divide down by the scale in
unit_scaling_rules.json. Credits are integer milli credits. No stage
needs floating point and no stage is permitted to use it.

What is not here. There is no settled answer anywhere in these papers.
The registers are histories, the amendments are logs, and several files
are superseded by later ones. data_lineage.md says which is which.
known_traps_and_footguns.md lists the readings that look right and are
wrong, with the stage each one belongs to.

Three numbers you will need live only in the harder documents. The per
contact cap and the aperture period budget live in the workbook. The
commit lead per station and the outage qualifying floor live in the
operations memo. The precedence exception lives in the directive.

corpus_coverage_sentinel.md says plainly which mechanisms this
particular month leaves no trace of. Read it before you conclude that a
rule does not matter because you saw no example of it.
