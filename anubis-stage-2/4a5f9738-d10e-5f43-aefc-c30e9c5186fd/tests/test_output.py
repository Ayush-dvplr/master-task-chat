from __future__ import annotations

import ast
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
from datetime import datetime
from pathlib import Path

from rewardkit import criteria, criterion

# ---------------------------------------------------------------------------
# expected documents and the seeded corpus generator
# ---------------------------------------------------------------------------
_EXPECTED = {'edge': {'data_quality.json': {'assignments_total': 620,
                                'manifest_mismatches': ['assignments_core_2035_03.csv',
                                                        'coordination_decisions_q4.jsonl',
                                                        'guard_windows_south.csv',
                                                        'holder_registry_west.csv',
                                                        'state_events_north.csv',
                                                        'zone_office_log_north_h1.tsv'],
                                'notes': {'ALIAS_RESOLVED': 6,
                                          'CLIPPED_TO_BAND': 147,
                                          'CLIPPED_TO_HORIZON': 458,
                                          'OPEN_ENDED': 6,
                                          'SPLIT_BY_RASTER': 94,
                                          'STATE_ANOMALY': 26,
                                          'WIDTH_MISMATCH': 9,
                                          'ZERO_SPAN': 12,
                                          'ZONE_OF_RECORD_DIFFERS': 42},
                                'rejects': {'BAND_OUTSIDE': 9,
                                            'HOLDER_UNKNOWN': 8,
                                            'PARENT_CYCLE': 9,
                                            'PARENT_RETRACTED': 9,
                                            'PARENT_UNKNOWN': 2,
                                            'RASTER_MISALIGNED': 25,
                                            'SPAN_INVERTED': 18,
                                            'TERM_MISSING': 4,
                                            'UNIT_AMBIGUOUS': 5,
                                            'ZONE_MISMATCH': 15},
                                'retracted': 24,
                                'rows_read_total': 15651,
                                'source_counts': {'assignments_core_2034_11.csv': {'rows_governing': 0,
                                                                                   'rows_read': 602,
                                                                                   'rows_visible': 602},
                                                  'assignments_core_2034_12.csv': {'rows_governing': 0,
                                                                                   'rows_read': 968,
                                                                                   'rows_visible': 968},
                                                  'assignments_core_2035_01.csv': {'rows_governing': 362,
                                                                                   'rows_read': 1012,
                                                                                   'rows_visible': 1012},
                                                  'assignments_core_2035_02.csv': {'rows_governing': 258,
                                                                                   'rows_read': 298,
                                                                                   'rows_visible': 298},
                                                  'assignments_core_2035_03.csv': {'rows_governing': 0,
                                                                                   'rows_read': 200,
                                                                                   'rows_visible': 177},
                                                  'assignments_core_2035_04.csv': {'rows_governing': 0,
                                                                                   'rows_read': 200,
                                                                                   'rows_visible': 0},
                                                  'channel_raster.csv': {'rows_governing': 0,
                                                                         'rows_read': 350,
                                                                         'rows_visible': 0},
                                                  'coordination_decisions_q1.jsonl': {'rows_governing': 346,
                                                                                      'rows_read': 403,
                                                                                      'rows_visible': 395},
                                                  'coordination_decisions_q2.jsonl': {'rows_governing': 31,
                                                                                      'rows_read': 200,
                                                                                      'rows_visible': 189},
                                                  'coordination_decisions_q3.jsonl': {'rows_governing': 62,
                                                                                      'rows_read': 200,
                                                                                      'rows_visible': 200},
                                                  'coordination_decisions_q4.jsonl': {'rows_governing': 57,
                                                                                      'rows_read': 597,
                                                                                      'rows_visible': 597},
                                                  'duty_budget_commercial.csv': {'rows_governing': 0,
                                                                                 'rows_read': 2080,
                                                                                 'rows_visible': 0},
                                                  'duty_budget_public.csv': {'rows_governing': 0,
                                                                             'rows_read': 2080,
                                                                             'rows_visible': 0},
                                                  'guard_exceptions.csv': {'rows_governing': 0,
                                                                           'rows_read': 220,
                                                                           'rows_visible': 0},
                                                  'guard_windows_east.csv': {'rows_governing': 0,
                                                                             'rows_read': 200,
                                                                             'rows_visible': 0},
                                                  'guard_windows_north.csv': {'rows_governing': 0,
                                                                              'rows_read': 200,
                                                                              'rows_visible': 0},
                                                  'guard_windows_south.csv': {'rows_governing': 0,
                                                                              'rows_read': 200,
                                                                              'rows_visible': 0},
                                                  'guard_windows_west.csv': {'rows_governing': 0,
                                                                             'rows_read': 200,
                                                                             'rows_visible': 0},
                                                  'holder_alias_map.csv': {'rows_governing': 0,
                                                                           'rows_read': 220,
                                                                           'rows_visible': 0},
                                                  'holder_registry_east.csv': {'rows_governing': 0,
                                                                               'rows_read': 200,
                                                                               'rows_visible': 0},
                                                  'holder_registry_north.csv': {'rows_governing': 0,
                                                                                'rows_read': 200,
                                                                                'rows_visible': 0},
                                                  'holder_registry_south.csv': {'rows_governing': 0,
                                                                                'rows_read': 200,
                                                                                'rows_visible': 0},
                                                  'holder_registry_west.csv': {'rows_governing': 0,
                                                                               'rows_read': 200,
                                                                               'rows_visible': 0},
                                                  'holder_status_history.csv': {'rows_governing': 0,
                                                                                'rows_read': 398,
                                                                                'rows_visible': 0},
                                                  'precedence_observations.csv': {'rows_governing': 0,
                                                                                  'rows_read': 495,
                                                                                  'rows_visible': 0},
                                                  'register_governing_flags.csv': {'rows_governing': 0,
                                                                                   'rows_read': 240,
                                                                                   'rows_visible': 0},
                                                  'retraction_notices.csv': {'rows_governing': 0,
                                                                             'rows_read': 200,
                                                                             'rows_visible': 0},
                                                  'state_events_east.csv': {'rows_governing': 0,
                                                                            'rows_read': 200,
                                                                            'rows_visible': 0},
                                                  'state_events_north.csv': {'rows_governing': 0,
                                                                             'rows_read': 200,
                                                                             'rows_visible': 0},
                                                  'state_events_south.csv': {'rows_governing': 0,
                                                                             'rows_read': 200,
                                                                             'rows_visible': 0},
                                                  'state_events_west.csv': {'rows_governing': 0,
                                                                            'rows_read': 200,
                                                                            'rows_visible': 0},
                                                  'zone_clock_marks.csv': {'rows_governing': 0,
                                                                           'rows_read': 406,
                                                                           'rows_visible': 0},
                                                  'zone_office_log_east_h1.tsv': {'rows_governing': 5,
                                                                                  'rows_read': 235,
                                                                                  'rows_visible': 235},
                                                  'zone_office_log_east_h2.tsv': {'rows_governing': 150,
                                                                                  'rows_read': 235,
                                                                                  'rows_visible': 229},
                                                  'zone_office_log_north_h1.tsv': {'rows_governing': 4,
                                                                                   'rows_read': 235,
                                                                                   'rows_visible': 235},
                                                  'zone_office_log_north_h2.tsv': {'rows_governing': 151,
                                                                                   'rows_read': 235,
                                                                                   'rows_visible': 229},
                                                  'zone_office_log_south_h1.tsv': {'rows_governing': 5,
                                                                                   'rows_read': 236,
                                                                                   'rows_visible': 236},
                                                  'zone_office_log_south_h2.tsv': {'rows_governing': 150,
                                                                                   'rows_read': 236,
                                                                                   'rows_visible': 230},
                                                  'zone_office_log_west_h1.tsv': {'rows_governing': 6,
                                                                                  'rows_read': 235,
                                                                                  'rows_visible': 235},
                                                  'zone_office_log_west_h2.tsv': {'rows_governing': 149,
                                                                                  'rows_read': 235,
                                                                                  'rows_visible': 230}},
                                'zero_span': 12},
          'policy_audit.json': {'alias_cycles': 2,
                                'alias_fixpoint_depth': 1,
                                'as_of': '2035-03-16T00:00:00Z',
                                'clock_keying': 'utc',
                                'duplicate_tiebreak': 'earliest_recorded_at',
                                'duty': {'carry_forward_end': 160981962880,
                                         'carry_resets': 10,
                                         'holders_audited': 206,
                                         'months_in_deficit': 41,
                                         'top_deficit': [['RTQJ4T', '2035-04', 3256740000],
                                                         ['9LD74C', '2035-04', 2773560000],
                                                         ['RTQJ4T', '2035-03', 2298280000]],
                                         'total_allowance': 207973999640,
                                         'total_consumed': 39621372910},
                                'guard': {'added': 4,
                                          'cancelled': 13,
                                          'occurrences': 894,
                                          'subtracted_area': 484920000},
                                'layer_governing_counts': {'coord': 750, 'core': 657, 'office': 381},
                                'parent_chain_max_depth': 2,
                                'parent_rejects': {'PARENT_CYCLE': 9,
                                                   'PARENT_RETRACTED': 9,
                                                   'PARENT_UNKNOWN': 2},
                                'precedence_exception': {'field_group': 'frequency',
                                                         'layer': 'core',
                                                         'segment': 'public'}},
          'region_East.json': {'area_excess': 21578400300,
                               'area_exclusive': 16353540675,
                               'area_shared': 13217580125,
                               'area_total_assigned': 51149521100,
                               'area_union': 29571120800,
                               'assignments_measurable': 35,
                               'band_area_union': {'B1': 5013360100,
                                                   'B2': 3918600000,
                                                   'B3': 6579360000,
                                                   'B4': 14059800700},
                               'excess_charge_top': [['A-00088', 6287220000],
                                                     ['A-00576', 3525120000],
                                                     ['A-00272', 3349620000]],
                               'guard_occurrences': 223,
                               'guard_subtracted_area': 286560000,
                               'month_area_union': {'2035-02': 6561990700,
                                                    '2035-03': 11676510000,
                                                    '2035-04': 11104560000,
                                                    '2035-05': 228060100},
                               'rectangles': 280,
                               'summer_window_utc': None,
                               'utc_offset_standard_sec': 46800,
                               'utc_offset_summer_sec': 46800,
                               'zone': 'East'},
          'region_North.json': {'area_excess': 10495440275,
                                'area_exclusive': 13388761300,
                                'area_shared': 5864400000,
                                'area_total_assigned': 29748601575,
                                'area_union': 19253161300,
                                'assignments_measurable': 38,
                                'band_area_union': {'B1': 1867950325,
                                                    'B2': 3687120025,
                                                    'B3': 6691050450,
                                                    'B4': 7007040500},
                                'excess_charge_top': [['A-00233', 2328480000],
                                                      ['A-00425', 1684800000],
                                                      ['A-00537', 1537920000]],
                                'guard_occurrences': 223,
                                'guard_subtracted_area': 5400000,
                                'month_area_union': {'2035-02': 4355730575,
                                                     '2035-03': 6743520000,
                                                     '2035-04': 8140860000,
                                                     '2035-05': 13050725},
                                'rectangles': 71,
                                'summer_window_utc': None,
                                'utc_offset_standard_sec': 3600,
                                'utc_offset_summer_sec': 3600,
                                'zone': 'North'},
          'region_South.json': {'area_excess': 9528300350,
                                'area_exclusive': 22884300450,
                                'area_shared': 5756220350,
                                'area_total_assigned': 38168821150,
                                'area_union': 28640520800,
                                'assignments_measurable': 39,
                                'band_area_union': {'B1': 4415040250,
                                                    'B2': 3851100300,
                                                    'B3': 9529920250,
                                                    'B4': 10844460000},
                                'excess_charge_top': [['A-00350', 1981800000],
                                                      ['A-00542', 1636200000],
                                                      ['A-00550', 1035720000]],
                                'guard_occurrences': 224,
                                'guard_subtracted_area': 104760000,
                                'month_area_union': {'2035-01': 32400500,
                                                     '2035-02': 6255810000,
                                                     '2035-03': 9114210000,
                                                     '2035-04': 13238100300},
                                'rectangles': 231,
                                'summer_window_utc': ['2035-03-12T02:00:00Z', '2035-11-05T02:00:00Z'],
                                'utc_offset_standard_sec': -18000,
                                'utc_offset_summer_sec': -14400,
                                'zone': 'South'},
          'region_West.json': {'area_excess': 15539040700,
                               'area_exclusive': 21758040925,
                               'area_shared': 8929440700,
                               'area_total_assigned': 46226522325,
                               'area_union': 30687481625,
                               'assignments_measurable': 41,
                               'band_area_union': {'B1': 4743225200,
                                                   'B2': 5749920075,
                                                   'B3': 7398495150,
                                                   'B4': 12795841200},
                               'excess_charge_top': [['A-00271', 3075840000],
                                                     ['A-00559', 2125440000],
                                                     ['A-00463', 1918080000]],
                               'guard_occurrences': 224,
                               'guard_subtracted_area': 88200000,
                               'month_area_union': {'2035-01': 4050850,
                                                    '2035-02': 6700860000,
                                                    '2035-03': 8825760000,
                                                    '2035-04': 15156810775},
                               'rectangles': 203,
                               'summer_window_utc': None,
                               'utc_offset_standard_sec': -1800,
                               'utc_offset_summer_sec': -1800,
                               'zone': 'West'},
          'segment_commercial.json': {'area_exclusive': 56210403100,
                                      'area_shared': 18349740400,
                                      'area_union': 74560143500,
                                      'assignments_measurable': 96,
                                      'duty_carry_end': 97292793340,
                                      'duty_deficit_months': 24,
                                      'holders': 40,
                                      'segment': 'commercial',
                                      'top_holders': [['SLF9YP', 7848360000],
                                                      ['K626D4', 7819560000],
                                                      ['0CBPWL', 7637220000],
                                                      ['7HVM3B', 5311440000],
                                                      ['P7N8BS', 4354560000]],
                                      'zone_area_union': {'East': 23775840700,
                                                          'North': 12148921100,
                                                          'South': 18760860500,
                                                          'West': 19874521200}},
          'segment_public.json': {'area_exclusive': 46480141450,
                                  'area_shared': 9007200325,
                                  'area_union': 55487341775,
                                  'assignments_measurable': 57,
                                  'duty_carry_end': 63689169540,
                                  'duty_deficit_months': 17,
                                  'holders': 26,
                                  'segment': 'public',
                                  'top_holders': [['PWSFLK', 9190260000],
                                                  ['RTQJ4T', 7974720000],
                                                  ['ENZE3D', 5594400000],
                                                  ['2JMBLP', 5577120400],
                                                  ['9LD74C', 5028480000]],
                                  'zone_area_union': {'East': 16454340300,
                                                      'North': 10929600200,
                                                      'South': 12290040550,
                                                      'West': 15813360725}},
          'summary.json': {'area_excess': 57141181625,
                           'area_exclusive': 74384643350,
                           'area_shared': 33767641175,
                           'area_total_assigned': 165293466150,
                           'area_union': 108152284525,
                           'assignments_measurable': 153,
                           'assignments_total': 620,
                           'cross_segment_shared_area': 21895200750,
                           'excess_charge_total': 57141181625,
                           'guard_subtracted_area': 484920000,
                           'horizon': {'as_of': '2035-03-16T00:00:00Z',
                                       'end': '2035-05-01T00:00:00Z',
                                       'start': '2035-02-01T00:00:00Z'},
                           'rectangles': 785,
                           'segment_area_union': {'commercial': 74560143500, 'public': 55487341775},
                           'segment_share_bp': {'commercial': 5733, 'public': 4267},
                           'shared_ratio_ppm': 312223,
                           'zone_area_union': {'East': 29571120800,
                                               'North': 19253161300,
                                               'South': 28640520800,
                                               'West': 30687481625},
                           'zone_share_bp': {'East': 2734, 'North': 1780, 'South': 2648, 'West': 2838}}},
 'shifted': {'data_quality.json': {'assignments_total': 900,
                                   'manifest_mismatches': ['assignments_core_2033_01.csv',
                                                           'channel_raster.csv',
                                                           'duty_budget_public.csv',
                                                           'holder_alias_map.csv',
                                                           'precedence_observations.csv',
                                                           'state_events_west.csv',
                                                           'zone_office_log_south_h1.tsv'],
                                   'notes': {'ALIAS_RESOLVED': 13,
                                             'CLIPPED_TO_BAND': 37,
                                             'CLIPPED_TO_HORIZON': 339,
                                             'OPEN_ENDED': 0,
                                             'SPLIT_BY_RASTER': 28,
                                             'STATE_ANOMALY': 36,
                                             'WIDTH_MISMATCH': 5,
                                             'ZERO_SPAN': 18,
                                             'ZONE_OF_RECORD_DIFFERS': 57},
                                   'rejects': {'BAND_OUTSIDE': 15,
                                               'HOLDER_UNKNOWN': 11,
                                               'PARENT_CYCLE': 13,
                                               'PARENT_RETRACTED': 13,
                                               'PARENT_UNKNOWN': 5,
                                               'RASTER_MISALIGNED': 39,
                                               'SPAN_INVERTED': 18,
                                               'TERM_MISSING': 0,
                                               'UNIT_AMBIGUOUS': 7,
                                               'ZONE_MISMATCH': 31},
                                   'retracted': 38,
                                   'rows_read_total': 23188,
                                   'source_counts': {'assignments_core_2032_09.csv': {'rows_governing': 0,
                                                                                      'rows_read': 240,
                                                                                      'rows_visible': 240},
                                                     'assignments_core_2032_10.csv': {'rows_governing': 0,
                                                                                      'rows_read': 793,
                                                                                      'rows_visible': 793},
                                                     'assignments_core_2032_11.csv': {'rows_governing': 0,
                                                                                      'rows_read': 625,
                                                                                      'rows_visible': 625},
                                                     'assignments_core_2032_12.csv': {'rows_governing': 0,
                                                                                      'rows_read': 780,
                                                                                      'rows_visible': 780},
                                                     'assignments_core_2033_01.csv': {'rows_governing': 34,
                                                                                      'rows_read': 647,
                                                                                      'rows_visible': 647},
                                                     'assignments_core_2033_02.csv': {'rows_governing': 534,
                                                                                      'rows_read': 809,
                                                                                      'rows_visible': 809},
                                                     'assignments_core_2033_03.csv': {'rows_governing': 332,
                                                                                      'rows_read': 367,
                                                                                      'rows_visible': 367},
                                                     'assignments_core_2033_04.csv': {'rows_governing': 0,
                                                                                      'rows_read': 240,
                                                                                      'rows_visible': 240},
                                                     'assignments_core_2033_05.csv': {'rows_governing': 0,
                                                                                      'rows_read': 240,
                                                                                      'rows_visible': 0},
                                                     'assignments_core_2033_06.csv': {'rows_governing': 0,
                                                                                      'rows_read': 240,
                                                                                      'rows_visible': 0},
                                                     'channel_raster.csv': {'rows_governing': 0,
                                                                            'rows_read': 2400,
                                                                            'rows_visible': 0},
                                                     'coordination_decisions_q1.jsonl': {'rows_governing': 544,
                                                                                         'rows_read': 544,
                                                                                         'rows_visible': 544},
                                                     'coordination_decisions_q2.jsonl': {'rows_governing': 45,
                                                                                         'rows_read': 240,
                                                                                         'rows_visible': 209},
                                                     'coordination_decisions_q3.jsonl': {'rows_governing': 90,
                                                                                         'rows_read': 240,
                                                                                         'rows_visible': 240},
                                                     'coordination_decisions_q4.jsonl': {'rows_governing': 41,
                                                                                         'rows_read': 896,
                                                                                         'rows_visible': 896},
                                                     'duty_budget_commercial.csv': {'rows_governing': 0,
                                                                                    'rows_read': 2080,
                                                                                    'rows_visible': 0},
                                                     'duty_budget_public.csv': {'rows_governing': 0,
                                                                                'rows_read': 2080,
                                                                                'rows_visible': 0},
                                                     'guard_exceptions.csv': {'rows_governing': 0,
                                                                              'rows_read': 260,
                                                                              'rows_visible': 0},
                                                     'guard_windows_east.csv': {'rows_governing': 0,
                                                                                'rows_read': 240,
                                                                                'rows_visible': 0},
                                                     'guard_windows_north.csv': {'rows_governing': 0,
                                                                                 'rows_read': 240,
                                                                                 'rows_visible': 0},
                                                     'guard_windows_south.csv': {'rows_governing': 0,
                                                                                 'rows_read': 240,
                                                                                 'rows_visible': 0},
                                                     'guard_windows_west.csv': {'rows_governing': 0,
                                                                                'rows_read': 240,
                                                                                'rows_visible': 0},
                                                     'holder_alias_map.csv': {'rows_governing': 0,
                                                                              'rows_read': 260,
                                                                              'rows_visible': 0},
                                                     'holder_registry_east.csv': {'rows_governing': 0,
                                                                                  'rows_read': 240,
                                                                                  'rows_visible': 0},
                                                     'holder_registry_north.csv': {'rows_governing': 0,
                                                                                   'rows_read': 240,
                                                                                   'rows_visible': 0},
                                                     'holder_registry_south.csv': {'rows_governing': 0,
                                                                                   'rows_read': 240,
                                                                                   'rows_visible': 0},
                                                     'holder_registry_west.csv': {'rows_governing': 0,
                                                                                  'rows_read': 240,
                                                                                  'rows_visible': 0},
                                                     'holder_status_history.csv': {'rows_governing': 0,
                                                                                   'rows_read': 582,
                                                                                   'rows_visible': 0},
                                                     'precedence_observations.csv': {'rows_governing': 0,
                                                                                     'rows_read': 876,
                                                                                     'rows_visible': 0},
                                                     'register_governing_flags.csv': {'rows_governing': 0,
                                                                                      'rows_read': 334,
                                                                                      'rows_visible': 0},
                                                     'retraction_notices.csv': {'rows_governing': 0,
                                                                                'rows_read': 240,
                                                                                'rows_visible': 0},
                                                     'state_events_east.csv': {'rows_governing': 0,
                                                                               'rows_read': 240,
                                                                               'rows_visible': 0},
                                                     'state_events_north.csv': {'rows_governing': 0,
                                                                                'rows_read': 240,
                                                                                'rows_visible': 0},
                                                     'state_events_south.csv': {'rows_governing': 0,
                                                                                'rows_read': 240,
                                                                                'rows_visible': 0},
                                                     'state_events_west.csv': {'rows_governing': 0,
                                                                               'rows_read': 240,
                                                                               'rows_visible': 0},
                                                     'zone_clock_marks.csv': {'rows_governing': 0,
                                                                              'rows_read': 1560,
                                                                              'rows_visible': 0},
                                                     'zone_office_log_east_h1.tsv': {'rows_governing': 0,
                                                                                     'rows_read': 342,
                                                                                     'rows_visible': 342},
                                                     'zone_office_log_east_h2.tsv': {'rows_governing': 225,
                                                                                     'rows_read': 342,
                                                                                     'rows_visible': 333},
                                                     'zone_office_log_north_h1.tsv': {'rows_governing': 0,
                                                                                      'rows_read': 342,
                                                                                      'rows_visible': 342},
                                                     'zone_office_log_north_h2.tsv': {'rows_governing': 225,
                                                                                      'rows_read': 342,
                                                                                      'rows_visible': 333},
                                                     'zone_office_log_south_h1.tsv': {'rows_governing': 0,
                                                                                      'rows_read': 342,
                                                                                      'rows_visible': 342},
                                                     'zone_office_log_south_h2.tsv': {'rows_governing': 225,
                                                                                      'rows_read': 342,
                                                                                      'rows_visible': 333},
                                                     'zone_office_log_west_h1.tsv': {'rows_governing': 0,
                                                                                     'rows_read': 341,
                                                                                     'rows_visible': 341},
                                                     'zone_office_log_west_h2.tsv': {'rows_governing': 225,
                                                                                     'rows_read': 342,
                                                                                     'rows_visible': 334}},
                                   'zero_span': 18},
             'policy_audit.json': {'alias_cycles': 2,
                                   'alias_fixpoint_depth': 3,
                                   'as_of': '2033-05-01T00:00:00Z',
                                   'clock_keying': 'utc',
                                   'duplicate_tiebreak': 'latest_recorded_at',
                                   'duty': {'carry_forward_end': 678982358700,
                                            'carry_resets': 49,
                                            'holders_audited': 300,
                                            'months_in_deficit': 343,
                                            'top_deficit': [['VKL4HG', '2033-05', 3798800000],
                                                            ['VKL4HG', '2033-06', 3793576000],
                                                            ['VKL4HG', '2033-03', 3452416000]],
                                            'total_allowance': 1004699998300,
                                            'total_consumed': 262986188170},
                                   'guard': {'added': 12,
                                             'cancelled': 42,
                                             'occurrences': 3686,
                                             'subtracted_area': 328896000},
                                   'layer_governing_counts': {'coord': 0, 'core': 2164, 'office': 422},
                                   'parent_chain_max_depth': 2,
                                   'parent_rejects': {'PARENT_CYCLE': 13,
                                                      'PARENT_RETRACTED': 13,
                                                      'PARENT_UNKNOWN': 5},
                                   'precedence_exception': {'field_group': 'frequency',
                                                            'layer': 'office',
                                                            'segment': 'commercial'}},
             'region_East.json': {'area_excess': 41551488000,
                                  'area_exclusive': 200089441720,
                                  'area_shared': 37915776000,
                                  'area_total_assigned': 279556705720,
                                  'area_union': 238005217720,
                                  'assignments_measurable': 133,
                                  'band_area_union': {'B1': 44409600320,
                                                      'B2': 43001712240,
                                                      'B3': 64485504760,
                                                      'B4': 86108400400},
                                  'excess_charge_top': [['A-00088', 12648960000],
                                                        ['A-00676', 4561920000],
                                                        ['A-00340', 3317760000]],
                                  'guard_occurrences': 922,
                                  'guard_subtracted_area': 44064000,
                                  'month_area_union': {'2033-01': 7852645240,
                                                       '2033-02': 10552212000,
                                                       '2033-03': 13020804000,
                                                       '2033-04': 16358364000,
                                                       '2033-05': 17722386000,
                                                       '2033-06': 21913848000,
                                                       '2033-07': 23004216000,
                                                       '2033-08': 25409736000,
                                                       '2033-09': 26398494000,
                                                       '2033-10': 24350220000,
                                                       '2033-11': 25298280000,
                                                       '2033-12': 25782696000,
                                                       '2034-01': 341316480},
                                  'rectangles': 386,
                                  'summer_window_utc': None,
                                  'utc_offset_standard_sec': 34200,
                                  'utc_offset_summer_sec': 34200,
                                  'zone': 'East'},
             'region_North.json': {'area_excess': 16661664020,
                                   'area_exclusive': 229608470110,
                                   'area_shared': 15528096020,
                                   'area_total_assigned': 261798230150,
                                   'area_union': 245136566130,
                                   'assignments_measurable': 175,
                                   'band_area_union': {'B1': 34336944400,
                                                       'B2': 37874304180,
                                                       'B3': 74839716600,
                                                       'B4': 98085600950},
                                   'excess_charge_top': [['A-00153', 4682880000],
                                                         ['A-00621', 1853280000],
                                                         ['A-00029', 1447200000]],
                                   'guard_occurrences': 921,
                                   'guard_subtracted_area': 41580000,
                                   'month_area_union': {'2032-12': 21025180,
                                                        '2033-01': 9249408000,
                                                        '2033-02': 10529784000,
                                                        '2033-03': 15433560000,
                                                        '2033-04': 18546408000,
                                                        '2033-05': 22001580000,
                                                        '2033-06': 20416680000,
                                                        '2033-07': 24690456000,
                                                        '2033-08': 23987412000,
                                                        '2033-09': 24711552000,
                                                        '2033-10': 25967124000,
                                                        '2033-11': 24060924000,
                                                        '2033-12': 25520652950},
                                   'rectangles': 328,
                                   'summer_window_utc': ['2033-03-13T02:00:00Z', '2033-11-06T02:00:00Z'],
                                   'utc_offset_standard_sec': -7200,
                                   'utc_offset_summer_sec': -3600,
                                   'zone': 'North'},
             'region_South.json': {'area_excess': 45601920240,
                                   'area_exclusive': 190545912820,
                                   'area_shared': 38295936240,
                                   'area_total_assigned': 274443769300,
                                   'area_union': 228841849060,
                                   'assignments_measurable': 157,
                                   'band_area_union': {'B1': 33246720320,
                                                       'B2': 41305248420,
                                                       'B3': 63797760320,
                                                       'B4': 90492120000},
                                   'excess_charge_top': [['A-00774', 8294400000],
                                                         ['A-00286', 3283200000],
                                                         ['A-00590', 3248640000]],
                                   'guard_occurrences': 921,
                                   'guard_subtracted_area': 95688000,
                                   'month_area_union': {'2033-01': 7658748620,
                                                        '2033-02': 9620820000,
                                                        '2033-03': 15251994000,
                                                        '2033-04': 15945336000,
                                                        '2033-05': 18690048000,
                                                        '2033-06': 18580032000,
                                                        '2033-07': 24482754000,
                                                        '2033-08': 25666056000,
                                                        '2033-09': 22376304000,
                                                        '2033-10': 26543016000,
                                                        '2033-11': 20882124000,
                                                        '2033-12': 23013072000,
                                                        '2034-01': 131544440},
                                   'rectangles': 318,
                                   'summer_window_utc': ['2033-10-02T03:00:00Z', '2034-04-02T03:00:00Z'],
                                   'utc_offset_standard_sec': 12600,
                                   'utc_offset_summer_sec': 16200,
                                   'zone': 'South'},
             'region_West.json': {'area_excess': 21251520270,
                                  'area_exclusive': 318676500980,
                                  'area_shared': 20649312270,
                                  'area_total_assigned': 360577333520,
                                  'area_union': 339325813250,
                                  'assignments_measurable': 170,
                                  'band_area_union': {'B1': 52226136360,
                                                      'B2': 47654784060,
                                                      'B3': 98444412080,
                                                      'B4': 141000480750},
                                  'excess_charge_top': [['A-00283', 3670272000],
                                                        ['A-00703', 1814400000],
                                                        ['A-00895', 1814400000]],
                                  'guard_occurrences': 922,
                                  'guard_subtracted_area': 147564000,
                                  'month_area_union': {'2033-01': 8255520620,
                                                       '2033-02': 11803968000,
                                                       '2033-03': 19354464000,
                                                       '2033-04': 23343768000,
                                                       '2033-05': 27785124000,
                                                       '2033-06': 33495732000,
                                                       '2033-07': 37515024000,
                                                       '2033-08': 39681648000,
                                                       '2033-09': 34130448000,
                                                       '2033-10': 36715896000,
                                                       '2033-11': 35779248000,
                                                       '2033-12': 31464972630},
                                  'rectangles': 445,
                                  'summer_window_utc': None,
                                  'utc_offset_standard_sec': 0,
                                  'utc_offset_summer_sec': 0,
                                  'zone': 'West'},
             'segment_commercial.json': {'area_exclusive': 617805868190,
                                         'area_shared': 44183232150,
                                         'area_union': 661989100340,
                                         'assignments_measurable': 380,
                                         'duty_carry_end': 404244751040,
                                         'duty_deficit_months': 204,
                                         'holders': 57,
                                         'segment': 'commercial',
                                         'top_holders': [['3EP4BE', 32160240000],
                                                         ['VKL4HG', 30240000140],
                                                         ['X8CJKK', 22581504320],
                                                         ['X566VX', 22386240000],
                                                         ['ZKWEBA', 20778336000]],
                                         'zone_area_union': {'East': 158369329040,
                                                             'North': 144222229390,
                                                             'South': 159787512900,
                                                             'West': 199610029010}},
             'segment_public.json': {'area_exclusive': 450337466160,
                                     'area_shared': 8205120020,
                                     'area_union': 458542586180,
                                     'assignments_measurable': 255,
                                     'duty_carry_end': 274737607660,
                                     'duty_deficit_months': 139,
                                     'holders': 39,
                                     'segment': 'public',
                                     'top_holders': [['T3CHAK', 25712640000],
                                                     ['7L4W65', 23395824000],
                                                     ['FDV5JY', 22778280000],
                                                     ['GVMRN5', 21146400080],
                                                     ['6K68UD', 20387808360]],
                                     'zone_area_union': {'East': 106965936680,
                                                         'North': 110179296740,
                                                         'South': 89188992400,
                                                         'West': 152208360360}},
             'summary.json': {'area_excess': 125066592530,
                              'area_exclusive': 938920325630,
                              'area_shared': 112389120530,
                              'area_total_assigned': 1176376038690,
                              'area_union': 1051309446160,
                              'assignments_measurable': 635,
                              'assignments_total': 900,
                              'cross_segment_shared_area': 69222240360,
                              'excess_charge_total': 125066592530,
                              'guard_subtracted_area': 328896000,
                              'horizon': {'as_of': '2033-05-01T00:00:00Z',
                                          'end': '2034-01-01T00:00:00Z',
                                          'start': '2033-01-01T00:00:00Z'},
                              'rectangles': 1477,
                              'segment_area_union': {'commercial': 661989100340, 'public': 458542586180},
                              'segment_share_bp': {'commercial': 5908, 'public': 4092},
                              'shared_ratio_ppm': 106904,
                              'zone_area_union': {'East': 238005217720,
                                                  'North': 245136566130,
                                                  'South': 228841849060,
                                                  'West': 339325813250},
                              'zone_share_bp': {'East': 2264, 'North': 2332, 'South': 2177, 'West': 3227}}},
 'visible': {'data_quality.json': {'assignments_total': 4000,
                                   'manifest_mismatches': ['assignments_core_2031_02.csv',
                                                           'assignments_core_2031_08.csv',
                                                           'coordination_decisions_q4.jsonl',
                                                           'guard_windows_south.csv',
                                                           'holder_registry_west.csv',
                                                           'state_events_north.csv',
                                                           'zone_office_log_north_h1.tsv'],
                                   'notes': {'ALIAS_RESOLVED': 20,
                                             'CLIPPED_TO_BAND': 325,
                                             'CLIPPED_TO_HORIZON': 1525,
                                             'OPEN_ENDED': 56,
                                             'SPLIT_BY_RASTER': 242,
                                             'STATE_ANOMALY': 178,
                                             'WIDTH_MISMATCH': 46,
                                             'ZERO_SPAN': 71,
                                             'ZONE_OF_RECORD_DIFFERS': 253},
                                   'rejects': {'BAND_OUTSIDE': 67,
                                               'HOLDER_UNKNOWN': 54,
                                               'PARENT_CYCLE': 56,
                                               'PARENT_RETRACTED': 57,
                                               'PARENT_UNKNOWN': 25,
                                               'RASTER_MISALIGNED': 149,
                                               'SPAN_INVERTED': 94,
                                               'TERM_MISSING': 13,
                                               'UNIT_AMBIGUOUS': 58,
                                               'ZONE_MISMATCH': 135},
                                   'retracted': 182,
                                   'rows_read_total': 109747,
                                   'source_counts': {'assignments_core_2030_10.csv': {'rows_governing': 0,
                                                                                      'rows_read': 2060,
                                                                                      'rows_visible': 2060},
                                                     'assignments_core_2030_11.csv': {'rows_governing': 0,
                                                                                      'rows_read': 3013,
                                                                                      'rows_visible': 3013},
                                                     'assignments_core_2030_12.csv': {'rows_governing': 0,
                                                                                      'rows_read': 2571,
                                                                                      'rows_visible': 2571},
                                                     'assignments_core_2031_01.csv': {'rows_governing': 0,
                                                                                      'rows_read': 2853,
                                                                                      'rows_visible': 2853},
                                                     'assignments_core_2031_02.csv': {'rows_governing': 0,
                                                                                      'rows_read': 2467,
                                                                                      'rows_visible': 2467},
                                                     'assignments_core_2031_03.csv': {'rows_governing': 345,
                                                                                      'rows_read': 2742,
                                                                                      'rows_visible': 2742},
                                                     'assignments_core_2031_04.csv': {'rows_governing': 2738,
                                                                                      'rows_read': 3519,
                                                                                      'rows_visible': 3519},
                                                     'assignments_core_2031_05.csv': {'rows_governing': 917,
                                                                                      'rows_read': 2060,
                                                                                      'rows_visible': 2060},
                                                     'assignments_core_2031_06.csv': {'rows_governing': 0,
                                                                                      'rows_read': 2060,
                                                                                      'rows_visible': 2060},
                                                     'assignments_core_2031_07.csv': {'rows_governing': 0,
                                                                                      'rows_read': 2060,
                                                                                      'rows_visible': 0},
                                                     'assignments_core_2031_08.csv': {'rows_governing': 0,
                                                                                      'rows_read': 2060,
                                                                                      'rows_visible': 0},
                                                     'assignments_core_2031_09.csv': {'rows_governing': 0,
                                                                                      'rows_read': 2060,
                                                                                      'rows_visible': 0},
                                                     'channel_raster.csv': {'rows_governing': 0,
                                                                            'rows_read': 2410,
                                                                            'rows_visible': 0},
                                                     'coordination_decisions_q1.jsonl': {'rows_governing': 2600,
                                                                                         'rows_read': 5073,
                                                                                         'rows_visible': 5073},
                                                     'coordination_decisions_q2.jsonl': {'rows_governing': 200,
                                                                                         'rows_read': 2060,
                                                                                         'rows_visible': 2060},
                                                     'coordination_decisions_q3.jsonl': {'rows_governing': 400,
                                                                                         'rows_read': 2060,
                                                                                         'rows_visible': 1925},
                                                     'coordination_decisions_q4.jsonl': {'rows_governing': 184,
                                                                                         'rows_read': 2060,
                                                                                         'rows_visible': 2060},
                                                     'duty_budget_commercial.csv': {'rows_governing': 0,
                                                                                    'rows_read': 5588,
                                                                                    'rows_visible': 0},
                                                     'duty_budget_public.csv': {'rows_governing': 0,
                                                                                'rows_read': 3730,
                                                                                'rows_visible': 0},
                                                     'guard_exceptions.csv': {'rows_governing': 0,
                                                                              'rows_read': 2100,
                                                                              'rows_visible': 0},
                                                     'guard_windows_east.csv': {'rows_governing': 0,
                                                                                'rows_read': 2060,
                                                                                'rows_visible': 0},
                                                     'guard_windows_north.csv': {'rows_governing': 0,
                                                                                 'rows_read': 2060,
                                                                                 'rows_visible': 0},
                                                     'guard_windows_south.csv': {'rows_governing': 0,
                                                                                 'rows_read': 2060,
                                                                                 'rows_visible': 0},
                                                     'guard_windows_west.csv': {'rows_governing': 0,
                                                                                'rows_read': 2060,
                                                                                'rows_visible': 0},
                                                     'holder_alias_map.csv': {'rows_governing': 0,
                                                                              'rows_read': 2100,
                                                                              'rows_visible': 0},
                                                     'holder_registry_east.csv': {'rows_governing': 0,
                                                                                  'rows_read': 2060,
                                                                                  'rows_visible': 0},
                                                     'holder_registry_north.csv': {'rows_governing': 0,
                                                                                   'rows_read': 2060,
                                                                                   'rows_visible': 0},
                                                     'holder_registry_south.csv': {'rows_governing': 0,
                                                                                   'rows_read': 2060,
                                                                                   'rows_visible': 0},
                                                     'holder_registry_west.csv': {'rows_governing': 0,
                                                                                  'rows_read': 2060,
                                                                                  'rows_visible': 0},
                                                     'holder_status_history.csv': {'rows_governing': 0,
                                                                                   'rows_read': 2593,
                                                                                   'rows_visible': 0},
                                                     'precedence_observations.csv': {'rows_governing': 0,
                                                                                     'rows_read': 2958,
                                                                                     'rows_visible': 0},
                                                     'register_governing_flags.csv': {'rows_governing': 0,
                                                                                      'rows_read': 2110,
                                                                                      'rows_visible': 0},
                                                     'retraction_notices.csv': {'rows_governing': 0,
                                                                                'rows_read': 2060,
                                                                                'rows_visible': 0},
                                                     'state_events_east.csv': {'rows_governing': 0,
                                                                               'rows_read': 2060,
                                                                               'rows_visible': 0},
                                                     'state_events_north.csv': {'rows_governing': 0,
                                                                                'rows_read': 2060,
                                                                                'rows_visible': 0},
                                                     'state_events_south.csv': {'rows_governing': 0,
                                                                                'rows_read': 2060,
                                                                                'rows_visible': 0},
                                                     'state_events_west.csv': {'rows_governing': 0,
                                                                               'rows_read': 2060,
                                                                               'rows_visible': 0},
                                                     'zone_clock_marks.csv': {'rows_governing': 0,
                                                                              'rows_read': 2120,
                                                                              'rows_visible': 0},
                                                     'zone_office_log_east_h1.tsv': {'rows_governing': 0,
                                                                                     'rows_read': 2060,
                                                                                     'rows_visible': 2060},
                                                     'zone_office_log_east_h2.tsv': {'rows_governing': 1000,
                                                                                     'rows_read': 2060,
                                                                                     'rows_visible': 2018},
                                                     'zone_office_log_north_h1.tsv': {'rows_governing': 0,
                                                                                      'rows_read': 2060,
                                                                                      'rows_visible': 2060},
                                                     'zone_office_log_north_h2.tsv': {'rows_governing': 1000,
                                                                                      'rows_read': 2060,
                                                                                      'rows_visible': 2017},
                                                     'zone_office_log_south_h1.tsv': {'rows_governing': 0,
                                                                                      'rows_read': 2060,
                                                                                      'rows_visible': 2060},
                                                     'zone_office_log_south_h2.tsv': {'rows_governing': 1000,
                                                                                      'rows_read': 2060,
                                                                                      'rows_visible': 2017},
                                                     'zone_office_log_west_h1.tsv': {'rows_governing': 0,
                                                                                     'rows_read': 2060,
                                                                                     'rows_visible': 2060},
                                                     'zone_office_log_west_h2.tsv': {'rows_governing': 1000,
                                                                                     'rows_read': 2060,
                                                                                     'rows_visible': 2018}},
                                   'zero_span': 71},
             'policy_audit.json': {'alias_cycles': 11,
                                   'alias_fixpoint_depth': 2,
                                   'as_of': '2031-07-01T00:00:00Z',
                                   'clock_keying': 'local_standard',
                                   'duplicate_tiebreak': 'earliest_recorded_at',
                                   'duty': {'carry_forward_end': 3468376348925,
                                            'carry_resets': 281,
                                            'holders_audited': 667,
                                            'months_in_deficit': 1418,
                                            'top_deficit': [['VPHC4S', '2031-10', 32812560000],
                                                            ['KRC6YU', '2031-12', 32739240000],
                                                            ['KRC6YU', '2031-10', 32206250000]],
                                            'total_allowance': 4872059991200,
                                            'total_consumed': 1131969863225},
                                   'guard': {'added': 12,
                                             'cancelled': 42,
                                             'occurrences': 3685,
                                             'subtracted_area': 2608245000},
                                   'layer_governing_counts': {'coord': 5458, 'core': 4499, 'office': 1497},
                                   'parent_chain_max_depth': 2,
                                   'parent_rejects': {'PARENT_CYCLE': 56,
                                                      'PARENT_RETRACTED': 57,
                                                      'PARENT_UNKNOWN': 25},
                                   'precedence_exception': {'field_group': 'time',
                                                            'layer': 'office',
                                                            'segment': 'public'}},
             'region_East.json': {'area_excess': 845478722200,
                                  'area_exclusive': 578174492250,
                                  'area_shared': 400961521400,
                                  'area_total_assigned': 1824614735850,
                                  'area_union': 979136013650,
                                  'assignments_measurable': 572,
                                  'band_area_union': {'B1': 199169281250,
                                                      'B2': 186911371400,
                                                      'B3': 180919441000,
                                                      'B4': 412135920000},
                                  'excess_charge_top': [['A-00080', 26542080000],
                                                        ['A-00088', 25297920000],
                                                        ['A-00128', 24776640000]],
                                  'guard_occurrences': 921,
                                  'guard_subtracted_area': 1605510000,
                                  'month_area_union': {'2031-01': 36225721300,
                                                       '2031-02': 44497080000,
                                                       '2031-03': 70078005000,
                                                       '2031-04': 66844170000,
                                                       '2031-05': 78034635000,
                                                       '2031-06': 83094030000,
                                                       '2031-07': 93612465000,
                                                       '2031-08': 100118475000,
                                                       '2031-09': 99546840000,
                                                       '2031-10': 104968575000,
                                                       '2031-11': 98429175000,
                                                       '2031-12': 102620880000,
                                                       '2032-01': 1065962350},
                                  'rectangles': 2507,
                                  'summer_window_utc': ['2031-04-05T18:00:00Z', '2031-09-27T18:00:00Z'],
                                  'utc_offset_standard_sec': 28800,
                                  'utc_offset_summer_sec': 32400,
                                  'zone': 'East'},
             'region_North.json': {'area_excess': 474528334200,
                                   'area_exclusive': 821287194925,
                                   'area_shared': 359996493225,
                                   'area_total_assigned': 1655812022350,
                                   'area_union': 1181283688150,
                                   'assignments_measurable': 768,
                                   'band_area_union': {'B1': 160293443625,
                                                       'B2': 322961040850,
                                                       'B3': 177192721275,
                                                       'B4': 520836482400},
                                   'excess_charge_top': [['A-00893', 11370240000],
                                                         ['A-02829', 10152000000],
                                                         ['A-03629', 9504000000]],
                                   'guard_occurrences': 922,
                                   'guard_subtracted_area': 154237500,
                                   'month_area_union': {'2031-01': 46739703375,
                                                        '2031-02': 52684222500,
                                                        '2031-03': 75389760000,
                                                        '2031-04': 94463212500,
                                                        '2031-05': 111699450000,
                                                        '2031-06': 105365677500,
                                                        '2031-07': 113055120000,
                                                        '2031-08': 114564735000,
                                                        '2031-09': 113814742500,
                                                        '2031-10': 119604600000,
                                                        '2031-11': 113178285000,
                                                        '2031-12': 120553537500,
                                                        '2032-01': 170642275},
                                   'rectangles': 1562,
                                   'summer_window_utc': ['2031-03-30T00:00:00Z', '2031-10-26T00:00:00Z'],
                                   'utc_offset_standard_sec': 3600,
                                   'utc_offset_summer_sec': 7200,
                                   'zone': 'North'},
             'region_South.json': {'area_excess': 696640864375,
                                   'area_exclusive': 586346222825,
                                   'area_shared': 363318302225,
                                   'area_total_assigned': 1646305389425,
                                   'area_union': 949664525050,
                                   'assignments_measurable': 685,
                                   'band_area_union': {'B1': 185310720900,
                                                       'B2': 178029001350,
                                                       'B3': 180472321100,
                                                       'B4': 405852481700},
                                   'excess_charge_top': [['A-01534', 17625600000],
                                                         ['A-00814', 17452800000],
                                                         ['A-01582', 16640640000]],
                                   'guard_occurrences': 921,
                                   'guard_subtracted_area': 674280000,
                                   'month_area_union': {'2030-12': 120422750,
                                                        '2031-01': 41045220000,
                                                        '2031-02': 45274410000,
                                                        '2031-03': 61789590000,
                                                        '2031-04': 71118900000,
                                                        '2031-05': 77082480000,
                                                        '2031-06': 81161910000,
                                                        '2031-07': 88348410000,
                                                        '2031-08': 92715210000,
                                                        '2031-09': 93235590000,
                                                        '2031-10': 99746100000,
                                                        '2031-11': 96292800000,
                                                        '2031-12': 101733482300},
                                   'rectangles': 1606,
                                   'summer_window_utc': None,
                                   'utc_offset_standard_sec': -10800,
                                   'utc_offset_summer_sec': -10800,
                                   'zone': 'South'},
             'region_West.json': {'area_excess': 731385951525,
                                  'area_exclusive': 811014639275,
                                  'area_shared': 524047549175,
                                  'area_total_assigned': 2066448139975,
                                  'area_union': 1335062188450,
                                  'assignments_measurable': 750,
                                  'band_area_union': {'B1': 233345746075,
                                                      'B2': 276372000900,
                                                      'B3': 207204278275,
                                                      'B4': 618140163200},
                                  'excess_charge_top': [['A-01023', 14472000000],
                                                        ['A-01839', 14256000000],
                                                        ['A-00511', 14074560000]],
                                  'guard_occurrences': 921,
                                  'guard_subtracted_area': 174217500,
                                  'month_area_union': {'2031-01': 54397938975,
                                                       '2031-02': 66107430000,
                                                       '2031-03': 87508575000,
                                                       '2031-04': 100263352500,
                                                       '2031-05': 114672375000,
                                                       '2031-06': 116231355000,
                                                       '2031-07': 128372175000,
                                                       '2031-08': 127065352500,
                                                       '2031-09': 127225282500,
                                                       '2031-10': 140819850000,
                                                       '2031-11': 134607060000,
                                                       '2031-12': 136766970000,
                                                       '2032-01': 1024471975},
                                  'rectangles': 1446,
                                  'summer_window_utc': ['2031-03-08T20:30:00Z', '2031-11-01T20:30:00Z'],
                                  'utc_offset_standard_sec': 19800,
                                  'utc_offset_summer_sec': 23400,
                                  'zone': 'West'},
             'segment_commercial.json': {'area_exclusive': 2218071430400,
                                         'area_shared': 906418106575,
                                         'area_union': 3124489536975,
                                         'assignments_measurable': 1656,
                                         'duty_carry_end': 2072526761745,
                                         'duty_deficit_months': 899,
                                         'holders': 255,
                                         'segment': 'commercial',
                                         'top_holders': [['VPHC4S', 135218160000],
                                                         ['AVGK7W', 65730240300],
                                                         ['X2LWSJ', 59689440000],
                                                         ['22HMDY', 52671600000],
                                                         ['GYQTWN', 52431840000]],
                                         'zone_area_union': {'East': 750505051975,
                                                             'North': 738878404675,
                                                             'South': 685252533550,
                                                             'West': 949853546775}},
             'segment_public.json': {'area_exclusive': 1928101194925,
                                     'area_shared': 389128323175,
                                     'area_union': 2317229518100,
                                     'assignments_measurable': 1119,
                                     'duty_carry_end': 1395849587180,
                                     'duty_deficit_months': 519,
                                     'holders': 171,
                                     'segment': 'public',
                                     'top_holders': [['KRC6YU', 272084400000],
                                                     ['RGB6SB', 62415360000],
                                                     ['MBEM4R', 52263360000],
                                                     ['6EHYQZ', 47142000000],
                                                     ['4FD5GU', 43567200000]],
                                     'zone_area_union': {'East': 486693362400,
                                                         'North': 663251717575,
                                                         'South': 527974922775,
                                                         'West': 639309515350}},
             'summary.json': {'area_excess': 2748033872300,
                              'area_exclusive': 2796822549275,
                              'area_shared': 1648323866025,
                              'area_total_assigned': 7193180287600,
                              'area_union': 4445146415300,
                              'assignments_measurable': 2775,
                              'assignments_total': 4000,
                              'cross_segment_shared_area': 996572639775,
                              'excess_charge_total': 2748033872300,
                              'guard_subtracted_area': 2608245000,
                              'horizon': {'as_of': '2031-07-01T00:00:00Z',
                                          'end': '2032-01-01T00:00:00Z',
                                          'start': '2031-01-01T00:00:00Z'},
                              'rectangles': 7121,
                              'segment_area_union': {'commercial': 3124489536975, 'public': 2317229518100},
                              'segment_share_bp': {'commercial': 5742, 'public': 4258},
                              'shared_ratio_ppm': 370814,
                              'zone_area_union': {'East': 979136013650,
                                                  'North': 1181283688150,
                                                  'South': 949664525050,
                                                  'West': 1335062188450},
                              'zone_share_bp': {'East': 2203, 'North': 2658, 'South': 2136, 'West': 3003}}}}

_UNION_WITHOUT_CUTOFF = 4406036105000
_GUARD_AREA_WITHOUT_EXCEPTIONS = 2644447500

def _load_generator():
    import json
    import os
    import random
    from datetime import datetime, timedelta, timezone

    EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)
    ZONES = ["North", "South", "West", "East"]
    GROUPS = ["identity", "time", "frequency"]
    ALPHA = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


    def ts(text):
        text = text.strip()
        if text.endswith("Z"):
            text = text[:-1]
        if "T" in text:
            fmt = "%Y-%m-%dT%H:%M:%S" if len(text) > 16 else "%Y-%m-%dT%H:%M"
        else:
            fmt = "%Y-%m-%d %H:%M:%S" if len(text) > 13 else "%Y-%m-%d"
        d = datetime.strptime(text, fmt).replace(tzinfo=timezone.utc)
        return int((d - EPOCH).total_seconds())


    def iso(n):
        return (EPOCH + timedelta(seconds=int(n))).strftime("%Y-%m-%dT%H:%M:%SZ")


    def wall(n):
        return (EPOCH + timedelta(seconds=int(n))).strftime("%Y-%m-%d %H:%M:%S")


    def day(n):
        return (EPOCH + timedelta(seconds=int(n))).strftime("%Y-%m-%d")


    def off_text(sec):
        sign = "+" if sec >= 0 else "-"
        a = abs(int(sec))
        return "%s%02d:%02d" % (sign, a // 3600, (a % 3600) // 60)


    def iso_off(utc_sec, off):
        loc = EPOCH + timedelta(seconds=int(utc_sec) + int(off))
        return loc.strftime("%Y-%m-%dT%H:%M:%S") + off_text(off)


    def month_key(n):
        return (EPOCH + timedelta(seconds=int(n))).strftime("%Y-%m")


    def civil(n):
        d = EPOCH + timedelta(seconds=int(n))
        return d.year, d.month, d.day


    def month_start(year, mon):
        return ts("%04d-%02d-01T00:00:00Z" % (year, mon))


    def next_month(year, mon):
        return (year + 1, 1) if mon == 12 else (year, mon + 1)


    def iso_weekday(n):
        return (EPOCH + timedelta(seconds=int(n))).isoweekday()


    # ---------------------------------------------------------------- profiles

    def profile(name):
        if name == "visible":
            return {
                "name": "visible",
                "seed": 70413,
                "n_assign": 4000,
                "horizon": ("2031-01-01T00:00:00Z", "2032-01-01T00:00:00Z"),
                "as_of": "2031-07-01T00:00:00Z",
                "core_months": [(2030, 10), (2030, 11), (2030, 12), (2031, 1), (2031, 2),
                                (2031, 3), (2031, 4), (2031, 5), (2031, 6), (2031, 7),
                                (2031, 8), (2031, 9)],
                "bands": [("B1", 410000, 430000, 25), ("B2", 450000, 470000, 25),
                          ("B3", 862000, 876000, 25), ("B4", 1427000, 1452000, 100)],
                "withdrawn_per_band": 6,
                "rank": ["coord", "core", "office"],
                "exc_segment": "public",
                "exc_group": "time",
                "exc_layer": "office",
                "dup_tiebreak": "earliest",
                "clock_keying": "local_standard",
                "zone_clock": {
                    "North": (3600, 7200, "2031-03-30T01:00", "2031-10-26T01:00"),
                    "South": (-10800, -10800, "", ""),
                    "West": (19800, 23400, "2031-03-09T02:00", "2031-11-02T02:00"),
                    "East": (28800, 32400, "2031-04-06T02:00", "2031-09-28T02:00"),
                },
                "rows_core": 2060,
                "rows_office": 2060,
                "rows_coord": 2060,
                "rows_state": 2060,
                "rows_registry": 2060,
                "rows_alias": 2100,
                "rows_guard": 2060,
                "rows_guard_exc": 2100,
                "rows_flags": 2110,
                "rows_prec": 2210,
                "rows_marks": 2120,
                "rows_status": 2100,
                "rows_retract": 2060,
            }
        if name == "shifted":
            return {
                "name": "shifted",
                "seed": 51217,
                "n_assign": 900,
                "horizon": ("2033-01-01T00:00:00Z", "2034-01-01T00:00:00Z"),
                "as_of": "2033-05-01T00:00:00Z",
                "core_months": [(2032, 9), (2032, 10), (2032, 11), (2032, 12), (2033, 1),
                                (2033, 2), (2033, 3), (2033, 4), (2033, 5), (2033, 6)],
                "bands": [("B1", 406000, 424000, 20), ("B2", 452000, 468000, 20),
                          ("B3", 860000, 872000, 40), ("B4", 1430000, 1450000, 50)],
                "withdrawn_per_band": 4,
                "rank": ["core", "coord", "office"],
                "exc_segment": "commercial",
                "exc_group": "frequency",
                "exc_layer": "office",
                "dup_tiebreak": "latest",
                "clock_keying": "utc",
                "zone_clock": {
                    "North": (-7200, -3600, "2033-03-13T02:00", "2033-11-06T02:00"),
                    "South": (12600, 16200, "2033-10-02T03:00", "2034-04-02T03:00"),
                    "West": (0, 0, "", ""),
                    "East": (34200, 34200, "", ""),
                },
                "rows_core": 240,
                "rows_office": 240,
                "rows_coord": 240,
                "rows_state": 240,
                "rows_registry": 240,
                "rows_alias": 260,
                "rows_guard": 240,
                "rows_guard_exc": 260,
                "rows_flags": 260,
                "rows_prec": 280,
                "rows_marks": 400,
                "rows_status": 260,
                "rows_retract": 240,
            }
        if name == "edge":
            return {
                "name": "edge",
                "seed": 83941,
                "n_assign": 620,
                "horizon": ("2035-02-01T00:00:00Z", "2035-05-01T00:00:00Z"),
                "as_of": "2035-03-16T00:00:00Z",
                "core_months": [(2034, 11), (2034, 12), (2035, 1), (2035, 2), (2035, 3), (2035, 4)],
                "bands": [("B1", 410000, 413000, 25), ("B2", 450000, 453000, 25),
                          ("B3", 862000, 866000, 50), ("B4", 1427000, 1430000, 100)],
                "withdrawn_per_band": 3,
                "rank": ["coord", "office", "core"],
                "exc_segment": "public",
                "exc_group": "frequency",
                "exc_layer": "core",
                "dup_tiebreak": "earliest",
                "clock_keying": "utc",
                "zone_clock": {
                    "North": (3600, 3600, "", ""),
                    "South": (-18000, -14400, "2035-03-12T02:00", "2035-11-05T02:00"),
                    "West": (-1800, -1800, "", ""),
                    "East": (46800, 46800, "", ""),
                },
                "rows_core": 200,
                "rows_office": 200,
                "rows_coord": 200,
                "rows_state": 200,
                "rows_registry": 200,
                "rows_alias": 220,
                "rows_guard": 200,
                "rows_guard_exc": 220,
                "rows_flags": 220,
                "rows_prec": 240,
                "rows_marks": 360,
                "rows_status": 220,
                "rows_retract": 200,
            }
        raise ValueError(name)


    def transitions(p):
        """UTC seconds of the summer window per zone, honouring the keying switch."""
        out = {}
        for z in ZONES:
            std, smr, a, b = p["zone_clock"][z]
            if not a:
                out[z] = (std, smr, None, None)
                continue
            ta, tb = ts(a), ts(b)
            if p["clock_keying"] == "local_standard":
                ta -= std
                tb -= std
            out[z] = (std, smr, ta, tb)
        return out


    def off_at_utc(tr, z, utc_sec):
        std, smr, a, b = tr[z]
        if a is None:
            return std
        if a <= b:
            return smr if a <= utc_sec < b else std
        return smr if (utc_sec >= a or utc_sec < b) else std


    def local_to_utc(tr, z, local_sec):
        """Documented conversion: prefer the offset whose regime contains the instant."""
        std, smr, a, b = tr[z]
        if a is None:
            return local_sec - std
        cand = local_sec - smr
        if off_at_utc(tr, z, cand) == smr:
            return cand
        cand = local_sec - std
        if off_at_utc(tr, z, cand) == std:
            return cand
        return local_sec - std


    # ---------------------------------------------------------------- world

    def build(p):
        rnd = random.Random(p["seed"])
        tr = transitions(p)
        h0, h1 = ts(p["horizon"][0]), ts(p["horizon"][1])
        as_of = ts(p["as_of"])
        w = {"p": p, "tr": tr, "h0": h0, "h1": h1, "as_of": as_of}

        # ---- channel raster
        channels = []
        for band, lo, hi, width in p["bands"]:
            for i in range((hi - lo) // width):
                channels.append([band, i, lo + i * width, lo + (i + 1) * width, "usable"])
        by_band = {}
        for c in channels:
            by_band.setdefault(c[0], []).append(c)
        for band, lo, hi, width in p["bands"]:
            pool = by_band[band]
            picks = set()
            while len(picks) < min(p["withdrawn_per_band"], max(1, len(pool) // 8)):
                picks.add(rnd.randrange(len(pool) // 4, len(pool)))
            for i in sorted(picks):
                pool[i][4] = "withdrawn"
        w["channels"] = channels

        # ---- holders
        n_holders = max(40, p["n_assign"] // 3)
        seen = set()
        holders = []
        while len(holders) < n_holders:
            hid = "".join(rnd.choice(ALPHA) for _ in range(6))
            if hid.startswith("HL") or hid in seen:
                continue
            if len(holders) % 13 == 5:
                hid = "0" + hid[1:]
                if hid in seen:
                    continue
            seen.add(hid)
            holders.append(hid)
        hclass = {}
        for i, hid in enumerate(holders):
            hclass[hid] = "public" if (i % 5 in (0, 3)) else "commercial"
        w["holders"] = holders
        w["hclass"] = hclass

        # ---- alias map
        alias = {}
        alias_rows = []
        for hid in holders[:70]:
            alias_rows.append([hid, hid, day(h0 - 86400 * rnd.randrange(900, 2400)), "no-change"])
        pool = list(holders)
        nchain = max(6, len(holders) // 18)
        for k in range(nchain):
            tgt = pool[rnd.randrange(len(pool))]
            a1 = "".join(rnd.choice(ALPHA) for _ in range(6))
            if a1 in seen or a1.startswith("HL"):
                continue
            seen.add(a1)
            alias[a1] = tgt
            alias_rows.append([a1, tgt, day(h0 - 86400 * rnd.randrange(60, 900)), "merger"])
            if k % 3 == 0:
                a2 = "".join(rnd.choice(ALPHA) for _ in range(6))
                if a2 in seen or a2.startswith("HL"):
                    continue
                seen.add(a2)
                alias[a2] = a1
                alias_rows.append([a2, a1, day(h0 - 86400 * rnd.randrange(60, 900)), "merger"])
                if k % 9 == 0:
                    a3 = "".join(rnd.choice(ALPHA) for _ in range(6))
                    if a3 in seen or a3.startswith("HL"):
                        continue
                    seen.add(a3)
                    alias[a3] = a2
                    alias_rows.append([a3, a2, day(h0 - 86400 * rnd.randrange(60, 900)), "merger"])
        cyc = []
        for k in range(max(2, len(holders) // 120)):
            x = "".join(rnd.choice(ALPHA) for _ in range(6))
            y = "".join(rnd.choice(ALPHA) for _ in range(6))
            if x in seen or y in seen or x == y or x.startswith("HL") or y.startswith("HL"):
                continue
            seen.add(x)
            seen.add(y)
            alias[x] = y
            alias[y] = x
            cyc.append((x, y))
            alias_rows.append([x, y, day(h0 - 86400 * rnd.randrange(60, 900)), "restructure"])
            alias_rows.append([y, x, day(h0 - 86400 * rnd.randrange(60, 900)), "restructure"])
        for hid in holders[:: max(1, len(holders) // 20)]:
            alias_rows.append([hid, hid, day(h0 - 86400 * rnd.randrange(60, 900)), "no-change"])
        for k in range(max(4, len(holders) // 40)):
            a = "".join(rnd.choice(ALPHA) for _ in range(6))
            b = "".join(rnd.choice(ALPHA) for _ in range(6))
            if a in seen or b in seen or a.startswith("HL") or b.startswith("HL"):
                continue
            seen.add(a)
            alias[a] = b
            alias_rows.append([a, b, day(h0 - 86400 * rnd.randrange(60, 900)), "lapsed"])
        while len(alias_rows) < p["rows_alias"]:
            hid = holders[rnd.randrange(len(holders))]
            alias_rows.append([hid, hid, day(h0 - 86400 * rnd.randrange(900, 2400)), "no-change"])
        w["alias"] = alias
        w["alias_rows"] = alias_rows
        w["alias_cycles"] = cyc

        # ---- holder status history
        status_rows = []
        hstatus = {}
        for i, hid in enumerate(holders):
            if i % 9 == 4:
                hstatus[hid] = "provisional"
                status_rows.append([hid, "provisional", day(h0 - 86400 * rnd.randrange(30, 400)), "intake"])
            else:
                status_rows.append([hid, "provisional", day(h0 - 86400 * rnd.randrange(500, 1200)), "intake"])
                status_rows.append([hid, "confirmed", day(h0 - 86400 * rnd.randrange(20, 400)), "review"])
                hstatus[hid] = "confirmed"
            if i >= 60 and i % 17 == 9:
                status_rows.append([hid, "confirmed", day(h1 + 86400 * rnd.randrange(10, 200)), "future"])
        while len(status_rows) < p["rows_status"]:
            hid = holders[rnd.randrange(len(holders))]
            status_rows.append([hid, hstatus[hid], day(h0 - 86400 * rnd.randrange(1200, 2600)), "legacy"])
        w["status_rows"] = status_rows
        w["hstatus"] = hstatus

        # ---- assignments
        usable = [c for c in channels if c[4] == "usable"]
        aids = ["A-%05d" % (i + 1) for i in range(p["n_assign"])]
        w["aids"] = aids
        spec = {}
        for i, aid in enumerate(aids):
            z = ZONES[i % 4]
            nh4 = max(1, len(holders) // 4)
            hid = holders[(i % 4) + 4 * (((i // 4) * 3 + 1) % nh4)]
            band, lo, hi, width = p["bands"][(i // 4) % len(p["bands"])]
            nch = 1 + (i * 5) % 12
            span = (hi - lo) // width
            start = (i * 17) % max(1, span - nch)
            f_low = lo + start * width
            f_high = f_low + nch * width
            a = h0 - 86400 * 20 + 86400 * ((i * 11) % 420)
            dur = 86400 * (3 + (i * 7) % 300)
            b = a + dur
            spec[aid] = {
                "zone": z, "holder": hid, "band": band, "f_low": f_low, "f_high": f_high,
                "ef": a, "et": b, "parent": "", "kind": "plain",
            }
        # dependency graph
        for i, aid in enumerate(aids):
            if i % 14 == 3 and i >= 80:
                par = aids[i - 8]
                if spec[par]["zone"] == spec[aid]["zone"]:
                    spec[aid]["parent"] = par
        for i in range(97, len(aids), 97):
            if i + 4 < len(aids):
                spec[aids[i]]["parent"] = aids[i + 4]
                spec[aids[i + 4]]["parent"] = aids[i]
                spec[aids[i]]["kind"] = "cycle"
                spec[aids[i + 4]]["kind"] = "cycle"
        for i in range(134, len(aids), 131):
            spec[aids[i]]["parent"] = "A-9%04d" % i
            spec[aids[i]]["kind"] = "orphan"
        w["spec"] = spec

        # boundary flavoured edits
        for i, aid in enumerate(aids):
            s = spec[aid]
            if i < 80:
                continue
            if i % 29 == 7:
                s["ef"] = h0
                s["et"] = h1
            if i % 31 == 11:
                s["ef"] = h1 - 1
                s["et"] = h1 + 86400 * 30
            if i % 37 == 13:
                s["ef"] = h0 - 86400 * 40
                s["et"] = h0 + 1
            if i % 41 == 17:
                s["et"] = s["ef"]
                s["kind"] = "zero"
            if i % 43 == 19:
                s["et"] = s["ef"] - 86400
                s["kind"] = "inverted"
            if i % 47 == 23:
                s["f_low"] = 429950 if p["name"] == "visible" else s["f_low"]
                s["f_high"] = 450050 if p["name"] == "visible" else s["f_high"]
                s["kind"] = "gap" if p["name"] == "visible" else s["kind"]
            if i % 53 == 29:
                s["f_low"] = 300000
                s["f_high"] = 300100
                s["kind"] = "outside"
            if i % 59 == 31:
                s["f_high"] = s["f_high"] + 7
                s["kind"] = "misaligned"
            if i % 61 == 37:
                s["holder"] = "ZZ9ZZ9"
                s["kind"] = "nohold"
        bw = {b[0]: b[3] for b in p["bands"]}
        blim = {b[0]: (b[1], b[2]) for b in p["bands"]}
        for i, aid in enumerate(aids):
            s = spec[aid]
            par = s["parent"]
            if not par or par not in spec or s["kind"] != "plain":
                continue
            ps = spec[par]
            if ps["kind"] != "plain":
                continue
            width = bw[ps["band"]]
            lo_b, hi_b = blim[ps["band"]]
            lo = ps["f_low"] + width * (i % 3)
            hi = min(ps["f_high"] + width * (1 + i % 3), hi_b)
            if hi - lo < width:
                lo = max(lo_b, hi - width)
            s["band"] = ps["band"]
            s["f_low"], s["f_high"] = lo, hi
            s["ef"] = ps["ef"] + 86400 * (5 + i % 20)
            s["et"] = ps["et"] + 86400 * (10 + i % 30)

        zrec = {}
        first = {}
        for aid in aids:
            h = spec[aid]["holder"]
            if h not in first:
                first[h] = spec[aid]["zone"]
        for j, hid in enumerate(holders):
            z = first.get(hid, ZONES[j % 4])
            if j % 8 == 3:
                z = ZONES[(ZONES.index(z) + 1) % 4]
            zrec[hid] = z
        w["zrec"] = zrec

        # ---- registry snapshots
        reg_rows = {z: [] for z in ZONES}
        stamp = {}
        for i, hid in enumerate(holders):
            z = zrec[hid]
            stamp[hid] = day(h0 - 86400 * rnd.randrange(40, 300))
            reg_rows[z].append([hid, hclass[hid], z, stamp[hid], hstatus[hid], "primary"])
        for i, hid in enumerate(holders):
            z = zrec[hid]
            if i >= 60 and i % 11 == 6:
                other = ZONES[(ZONES.index(z) + 1) % 4]
                older = day(h0 - 86400 * rnd.randrange(400, 900))
                flip = "public" if hclass[hid] == "commercial" else "commercial"
                reg_rows[other].append([hid, flip, other, older, hstatus[hid], "superseded"])
            if i >= 60 and i % 23 == 14:
                other = ZONES[(ZONES.index(z) + 2) % 4]
                flip = "public" if hclass[hid] == "commercial" else "commercial"
                reg_rows[other].append([hid, flip, other, stamp[hid], hstatus[hid], "concurrent"])
        for z in ZONES:
            while len(reg_rows[z]) < p["rows_registry"]:
                hid = holders[rnd.randrange(len(holders))]
                reg_rows[z].append([hid, hclass[hid], zrec[hid],
                                    day(h0 - 86400 * rnd.randrange(900, 2400)), hstatus[hid], "archive"])
        w["reg_rows"] = reg_rows
        return w


    # ---------------------------------------------------------------- records

    def eff_rank(p, seg, grp):
        base = list(p["rank"])
        if seg == p["exc_segment"] and grp == p["exc_group"]:
            base = [p["exc_layer"]] + [x for x in base if x != p["exc_layer"]]
        return base


    def gov_index(p, recs):
        """Governing record of one layer: top revision, then the derived tiebreak."""
        if not recs:
            return None
        top = max(r["rev"] for r in recs)
        pool = [r for r in recs if r["rev"] == top]
        if p["dup_tiebreak"] == "earliest":
            pool.sort(key=lambda r: (r["rec"], r["idx"]))
        else:
            pool.sort(key=lambda r: (-r["rec"], r["idx"]))
        return pool[0]


    def emit_records(w):
        p = w["p"]
        rnd = random.Random(p["seed"] + 991)
        tr, h0, h1, as_of = w["tr"], w["h0"], w["h1"], w["as_of"]
        spec = w["spec"]
        chan_of = {}
        for c in w["channels"]:
            chan_of.setdefault(c[0], (c[2], c[3] - c[2]))
        band_width = {b[0]: b[3] for b in p["bands"]}
        recs = {"core": [], "office": [], "coord": []}
        flags = []
        prec_obs = []
        retract_rows = []
        months = p["core_months"]
        m0 = ts("%04d-%02d-01T00:00:00Z" % months[0])
        m1 = ts("%04d-%02d-01T00:00:00Z" % next_month(*months[-1]))
        mv = as_of - 86400 * 25

        def ref_form(hid, i):
            pick = i % 7
            if pick == 0:
                return hid.lower()
            if pick == 1:
                return "hl-" + hid.lower()
            if pick == 2:
                return "HL/" + hid
            if pick == 3:
                return hid[:2] + " " + hid[2:4] + " " + hid[4:]
            if pick == 4:
                return "ZQ" + hid
            if pick == 5 and hid.startswith("0"):
                return hid[1:]
            return hid

        alias_inv = {}
        for a in sorted(w["alias"]):
            n, hops, seen = a, 0, set()
            while n in w["alias"] and w["alias"][n] != n and n not in seen:
                seen.add(n)
                n = w["alias"][n]
                hops += 1
                if hops > 6:
                    break
            alias_inv.setdefault(n, []).append((hops, a))
        for t in alias_inv:
            alias_inv[t].sort()

        for i, aid in enumerate(w["aids"]):
            s = spec[aid]
            seg = w["hclass"].get(s["holder"], "commercial")
            has_coord = (i % 20) < 13
            office_freq = (i % 5) != 0
            coord_time = (i % 20) < 9
            coord_ident = (i % 10) < 3
            supply = {
                "core": {"identity": True, "time": True, "frequency": True},
                "office": {"identity": False, "time": True, "frequency": office_freq},
                "coord": {"identity": has_coord and coord_ident, "time": has_coord and coord_time,
                          "frequency": has_coord},
            }
            winner = {}
            for g in GROUPS:
                for layer in eff_rank(p, seg, g):
                    if supply[layer][g]:
                        winner[g] = layer
                        break
                winner.setdefault(g, "core")
            top_layer = None
            for layer in eff_rank(p, seg, "identity"):
                if supply[layer]["identity"]:
                    top_layer = layer
                    break
            top_layer = top_layer or "core"
            retracted = i >= 80 and (i % 26) == 5
            width = band_width.get(s["band"], 25)

            def freq_vals(winning, k):
                if winning:
                    lo, hi = s["f_low"], s["f_high"]
                else:
                    shift = ((k * 3 + 1) % 5 - 2) * width
                    lo, hi = s["f_low"] + shift, s["f_high"] + shift + width * ((k % 3) - 1)
                    if hi <= lo:
                        hi = lo + width
                return lo, hi

            def time_vals(winning, k):
                if winning:
                    return s["ef"], s["et"]
                d = 86400 * (((k * 5 + 3) % 9) - 4)
                e = s["ef"] + d
                t = s["et"] + d + 86400 * ((k % 4) - 1)
                if t < e:
                    t = e + 86400
                return e, t

            # ------- core layer
            ncore = 3 + (i % 4)
            gov_rev = ncore
            for k in range(ncore):
                rev = k + 1
                frac = (k + 1) / float(ncore + 1)
                rec = (int(m0 + (mv - m0) * frac) + 3600 * ((i * 7 + k) % 23)
                       + 86400 * (((i * 13 + k * 5) % 29) - 14))
                win_i = (winner["identity"] == "core" and rev == gov_rev)
                win_t = (winner["time"] == "core" and rev == gov_rev)
                win_f = (winner["frequency"] == "core" and rev == gov_rev)
                lo, hi = freq_vals(win_f, k)
                ef, et = time_vals(win_t, k)
                hid = s["holder"] if win_i else w["holders"][(i * 3 + 1 + k) % len(w["holders"])]
                pool_a = alias_inv.get(s["holder"]) or []
                if win_i and i >= 80 and (i % 5) == 4 and pool_a:
                    hid = pool_a[-1][1] if (i % 3) == 1 else pool_a[0][1]
                par = s["parent"] if win_i else ""
                recs["core"].append({
                    "aid": aid, "layer": "core", "rev": rev, "rec": rec, "idx": len(recs["core"]),
                    "action": "retract" if (retracted and rev == gov_rev and top_layer == "core") else ("grant" if rev == 1 else "amend"),
                    "identity": {"holder_ref": ref_form(hid, i + k), "zone": s["zone"], "parent_id": par},
                    "time": {"ef": ef, "et": et, "open": False, "nulled": False},
                    "freq": {"f_low": lo, "f_high": hi, "bw": hi - lo, "badunit": None, "mismatch": False},
                })
            # duplicate top revision for the tiebreak surface
            if i >= 80 and (i % 6) == 2:
                early = recs["core"][-1]
                late = {"aid": aid, "layer": "core", "rev": early["rev"],
                        "rec": early["rec"] + 3600 * 11, "idx": len(recs["core"]),
                        "action": early["action"], "identity": dict(early["identity"]),
                        "time": None, "freq": None}
                lose_lo = s["f_low"] + width * 2
                lose = {"f_low": lose_lo, "f_high": lose_lo + (s["f_high"] - s["f_low"]),
                        "bw": s["f_high"] - s["f_low"], "badunit": None, "mismatch": False}
                keepf = {"f_low": s["f_low"], "f_high": s["f_high"],
                         "bw": s["f_high"] - s["f_low"], "badunit": None, "mismatch": False}
                loset = {"ef": s["ef"] + 86400 * 3, "et": s["et"] + 86400 * 3,
                         "open": False, "nulled": False}
                keept = {"ef": s["ef"], "et": s["et"], "open": False, "nulled": False}
                if p["dup_tiebreak"] == "earliest":
                    early["freq"], early["time"] = keepf, keept
                    late["freq"], late["time"] = lose, loset
                    won = (True, False)
                else:
                    early["freq"], early["time"] = lose, loset
                    late["freq"], late["time"] = keepf, keept
                    won = (False, True)
                recs["core"].append(late)
                for r, g in ((early, won[0]), (late, won[1])):
                    flags.append([aid, "core", r["rev"], iso(r["rec"]), "true" if g else "false"])
            # a late record that the as of cutoff must hide
            if i >= 80 and (i % 17) == 6:
                recs["core"].append({
                    "aid": aid, "layer": "core", "rev": gov_rev + 2,
                    "rec": as_of + (0 if (i % 34) == 6 else 86400 * (1 + i % 40)),
                    "idx": len(recs["core"]), "action": "amend",
                    "identity": {"holder_ref": ref_form(w["holders"][(i * 5) % len(w["holders"])], i),
                                 "zone": ZONES[(ZONES.index(s["zone"]) + 1) % 4], "parent_id": ""},
                    "time": {"ef": s["ef"] - 86400 * 30, "et": s["et"] + 86400 * 60,
                             "open": False, "nulled": False},
                    "freq": {"f_low": s["f_low"] + width * 6, "f_high": s["f_high"] + width * 6,
                             "bw": s["f_high"] - s["f_low"], "badunit": None, "mismatch": False},
                })

            # ------- office layer
            noff = 2 + (i % 3)
            for k in range(noff):
                rev = k + 1
                frac = (k + 1) / float(noff + 2)
                rec = (int(m0 + (mv - m0) * frac) + 1800 * ((i * 5 + k) % 31)
                       + 86400 * (((i * 11 + k * 3) % 25) - 12))
                win_t = (winner["time"] == "office" and rev == noff)
                win_f = (winner["frequency"] == "office" and rev == noff)
                ef, et = time_vals(win_t, k + 1)
                lo, hi = freq_vals(win_f, k + 2)
                badunit = None
                if win_f and i >= 80 and (i % 71) == 23:
                    badunit = "hz_remainder"
                open_end = win_t and i >= 80 and (i % 19) == 8
                recs["office"].append({
                    "aid": aid, "layer": "office", "rev": rev, "rec": rec, "idx": len(recs["office"]),
                    "action": "retract" if (retracted and rev == noff and top_layer == "office") else "amend",
                    "identity": None,
                    "time": {"ef": ef, "et": None if open_end else et, "open": open_end, "nulled": False},
                    "freq": None if not supply["office"]["frequency"] else
                            {"f_low": lo, "f_high": hi, "bw": hi - lo, "badunit": badunit, "mismatch": False},
                })

            if i >= 80 and (i % 23) == 5:
                recs["office"].append({
                    "aid": aid, "layer": "office", "rev": noff + 2,
                    "rec": as_of + 86400 * (1 + i % 25), "idx": len(recs["office"]),
                    "action": "amend", "identity": None,
                    "time": {"ef": s["ef"] + 86400 * 45, "et": s["et"] - 86400 * 20,
                             "open": False, "nulled": False},
                    "freq": {"f_low": s["f_low"] + width * 3, "f_high": s["f_high"] + width * 3,
                             "bw": s["f_high"] - s["f_low"], "badunit": None, "mismatch": False},
                })

            # ------- coord layer
            if has_coord:
                ncd = 2 + (i % 2)
                for k in range(ncd):
                    rev = k + 1
                    frac = (k + 2) / float(ncd + 3)
                    rec = (int(m0 + (mv - m0) * frac) + 900 * ((i * 11 + k) % 41)
                           + 86400 * (((i * 17 + k * 7) % 23) - 11))
                    win_t = (winner["time"] == "coord" and rev == ncd)
                    win_f = (winner["frequency"] == "coord" and rev == ncd)
                    win_i = (winner["identity"] == "coord" and rev == ncd)
                    ef, et = time_vals(win_t, k + 3)
                    lo, hi = freq_vals(win_f, k + 4)
                    nulled = win_t and i >= 80 and (i % 83) == 19
                    badunit = None
                    if win_f and i >= 80 and (i % 67) == 29:
                        badunit = "missing"
                    elif win_f and i >= 80 and (i % 97) == 41:
                        badunit = "MHz"
                    mismatch = win_f and i >= 80 and (i % 23) == 9
                    hid = s["holder"] if win_i else w["holders"][(i * 7 + k) % len(w["holders"])]
                    recs["coord"].append({
                        "aid": aid, "layer": "coord", "rev": rev, "rec": rec, "idx": len(recs["coord"]),
                        "action": "retract" if (retracted and rev == ncd and top_layer == "coord") else "amend",
                        "identity": None if not supply["coord"]["identity"] else
                                    {"holder_ref": ref_form(hid, i + k + 2), "zone": s["zone"],
                                     "parent_id": s["parent"] if win_i else ""},
                        "time": None if not supply["coord"]["time"] else
                                {"ef": ef, "et": "NULL" if nulled else et, "open": False, "nulled": nulled},
                        "freq": {"f_low": lo, "f_high": hi, "bw": hi - lo, "badunit": badunit,
                                 "mismatch": mismatch},
                    })

            if has_coord and (i % 19) == 4:
                recs["coord"].append({
                    "aid": aid, "layer": "coord", "rev": 9,
                    "rec": as_of + 86400 * (2 + i % 35), "idx": len(recs["coord"]),
                    "action": "amend", "identity": None,
                    "time": {"ef": s["ef"] - 86400 * 12, "et": s["et"] + 86400 * 25,
                             "open": False, "nulled": False},
                    "freq": {"f_low": s["f_low"] + width * 5, "f_high": s["f_high"] + width * 5,
                             "bw": s["f_high"] - s["f_low"], "badunit": None, "mismatch": False},
                })

            for g in GROUPS:
                if (i % 8) == 1 or (seg == p["exc_segment"] and (i % 3) == 0):
                    prec_obs.append([aid, g, winner[g], day(as_of - 86400 * (1 + i % 90))])
            if retracted and (i % 2) == 0:
                retract_rows.append([aid, day(s["ef"] + 86400 * 5), iso(as_of - 86400 * (2 + i % 60)),
                                     "full", "committee"])
            if i >= 80 and (i % 29) == 12:
                retract_rows.append([aid, day(s["ef"] + 86400 * 9), iso(as_of - 86400 * (3 + i % 40)),
                                     "full", "committee"])
                retract_rows.append([aid, day(s["ef"] + 86400 * 9), iso(as_of - 86400 * (1 + i % 30)),
                                     "withdrawn", "committee"])
            if i >= 80 and (i % 31) == 15:
                retract_rows.append([aid, day(s["ef"] + 86400 * 4), iso(as_of + 86400 * (1 + i % 50)),
                                     "full", "committee"])

        w["recs"] = recs
        w["flags"] = flags
        w["prec_obs"] = prec_obs
        w["retract_rows"] = retract_rows
        return w


    # ---------------------------------------------------------------- events

    def emit_events(w):
        p = w["p"]
        rnd = random.Random(p["seed"] + 7717)
        h0, h1, as_of, tr = w["h0"], w["h1"], w["as_of"], w["tr"]
        spec = w["spec"]
        ev = {z: [] for z in ZONES}
        for i, aid in enumerate(w["aids"]):
            s = spec[aid]
            z = s["zone"]
            ef, et = s["ef"], s["et"]
            rec_ok = as_of - 86400 * (5 + i % 120)
            rec_late = as_of + 86400 * (1 + i % 30)
            if i < 80:
                ev[z].append([aid, "activate", iso(ef + 86400 * 2), iso(rec_ok), "zone-desk"])
                continue
            if (i % 7) == 0:
                ev[z].append([aid, "suspend", iso(ef + 86400 * 30), iso(rec_ok), "zone-desk"])
                ev[z].append([aid, "restore", iso(ef + 86400 * 60), iso(rec_ok), "zone-desk"])
            if (i % 11) == 2:
                ev[z].append([aid, "suspend", iso(ef + 86400 * 100), iso(rec_ok), "zone-desk"])
            if (i % 13) == 5:
                ev[z].append([aid, "terminate", iso(ef + 86400 * 150), iso(rec_ok), "registry"])
            if (i % 17) == 3:
                ev[z].append([aid, "restore", iso(ef + 86400 * 20), iso(rec_ok), "zone-desk"])
            if (i % 23) == 8:
                ev[z].append([aid, "suspend", iso(ef + 86400 * 12), iso(rec_ok), "zone-desk"])
                ev[z].append([aid, "suspend", iso(ef + 86400 * 25), iso(rec_ok), "zone-desk"])
                ev[z].append([aid, "restore", iso(ef + 86400 * 44), iso(rec_ok), "zone-desk"])
            if (i % 29) == 9:
                ev[z].append([aid, "suspend", iso(ef - 86400 * 9), iso(rec_ok), "zone-desk"])
                ev[z].append([aid, "restore", iso(ef + 86400 * 18), iso(rec_ok), "zone-desk"])
            if (i % 37) == 12:
                ev[z].append([aid, "suspend", iso(et), iso(rec_ok), "zone-desk"])
            if (i % 19) == 7:
                ev[z].append([aid, "terminate", iso(ef + 86400 * 70), iso(rec_ok), "registry"])
                ev[z].append([aid, "suspend", iso(ef + 86400 * 90), iso(rec_ok), "zone-desk"])
            if (i % 41) == 16:
                ev[z].append([aid, "suspend", iso(ef + 86400 * 15), iso(rec_late), "zone-desk"])
            if (i % 47) == 21:
                ev[z].append([aid, "activate", iso(ef + 86400 * 6), iso(rec_ok), "zone-desk"])
        for z in ZONES:
            pool = [a for a in w["aids"] if spec[a]["zone"] == z]
            k = 0
            while len(ev[z]) < p["rows_state"]:
                aid = pool[k % len(pool)]
                k += 1
                ev[z].append([aid, "activate", iso(spec[aid]["ef"] + 86400 * (1 + k % 9)),
                              iso(as_of - 86400 * (10 + k % 150)), "audit"])
        w["events"] = ev

        # ---- reservations
        guards = {z: [] for z in ZONES}
        bands = p["bands"]
        for zi, z in enumerate(ZONES):
            std, smr, ta, tb = tr[z]
            b = bands[zi % len(bands)]
            b2 = bands[(zi + 2) % len(bands)]
            wd = b[3]
            wd2 = b2[3]
            base = b[1] + wd * (8 + zi * 3)
            base2 = b2[1] + wd2 * (5 + zi * 2)
            lo_d, hi_d = day(h0 - 86400 * 20), day(h1 + 86400 * 20)
            rules = [
                ["G%s-01" % z[0], "daily", "02:15", 75, base, base + wd * 8],
                ["G%s-02" % z[0], "weekly:3", "23:30", 150, base + wd * 10, base + wd * 16],
                ["G%s-03" % z[0], "weekly:6", "21:45", 90, base + wd * 18, base + wd * 26],
                ["G%s-04" % z[0], "monthly:31", "05:00", 240, base2, base2 + wd2 * 8],
                ["G%s-05" % z[0], "monthly:14", "06:30", 120, base2 + wd2 * 10, base2 + wd2 * 14],
                ["G%s-06" % z[0], "daily", "13:00", 45, base2 + wd2 * 16, base2 + wd2 * 22],
                ["G%s-07" % z[0], "weekly:1", "01:30", 60, base + wd * 28, base + wd * 32],
                ["G%s-08" % z[0], "monthly:29", "04:00", 180, base2 + wd2 * 24, base2 + wd2 * 30],
                ["G%s-09" % z[0], "monthly:1", "00:00", 30, base + wd * 34, base + wd * 40],
            ]
            k = 0
            while len(guards[z]) < 90:
                k += 1
                rid = "G%s-%04d" % (z[0], 100 + k)
                recur = ["daily", "weekly:2", "weekly:5", "monthly:7", "monthly:21"][k % 5]
                flo = b[1] + wd * (k % max(2, ((b[2] - b[1]) // wd) - 2))
                far = h0 - 86400 * (400 + k)
                guards[z].append([rid, z, recur, "%02d:%02d" % (k % 24, (k * 7) % 60),
                                  15 + (k % 8) * 15, day(far), day(far + 86400 * 90),
                                  flo, flo + wd, "active" if k % 3 else "retired", "historic"])
            for rid, recur, start, dur, flo, fhi in rules:
                guards[z].append([rid, z, recur, start, dur, lo_d, hi_d, flo, fhi, "active",
                                  "astronomy"])
                guards[z].append([rid + "R", z, recur, start, dur, lo_d, hi_d, flo, fhi,
                                  "retired", "superseded"])
            while len(guards[z]) < p["rows_guard"]:
                k += 1
                rid = "G%s-%04d" % (z[0], 100 + k)
                recur = ["daily", "weekly:2", "weekly:5", "monthly:7", "monthly:21"][k % 5]
                flo = b[1] + wd * (k % max(2, ((b[2] - b[1]) // wd) - 2))
                far = h0 - 86400 * (400 + k)
                guards[z].append([rid, z, recur, "%02d:%02d" % (k % 24, (k * 7) % 60),
                                  15 + (k % 8) * 15, day(far), day(far + 86400 * 90),
                                  flo, flo + wd, "active" if k % 3 else "retired", "historic"])
        w["guards"] = guards

        gexc = []
        for k in range(1, 61):
            z = ZONES[k % 4]
            d = h0 - 86400 * (300 + k)
            gexc.append([z, "G%s-%04d" % (z[0], 100 + (k % 50)), day(d), "cancel", "", "", "historic"])
        for zi, z in enumerate(ZONES):
            for k in range(10):
                d = h0 + 86400 * (17 + k * 29 + zi * 3)
                if d < h1:
                    gexc.append([z, "G%s-01" % z[0], day(d), "cancel", "", "", "maintenance"])
            for k in range(3):
                d = h0 + 86400 * (41 + k * 97 + zi * 5)
                if d < h1:
                    gexc.append([z, "G%s-02" % z[0], day(d), "cancel", "", "", "maintenance"])
            for k in range(3):
                d = h0 + 86400 * (63 + k * 101 + zi * 7)
                if d < h1:
                    gexc.append([z, "G%s-04" % z[0], day(d), "add", "19:00", 60, "campaign"])
        k = 60
        while len(gexc) < p["rows_guard_exc"]:
            k += 1
            z = ZONES[k % 4]
            d = h0 - 86400 * (300 + k)
            gexc.append([z, "G%s-%04d" % (z[0], 100 + (k % 50)), day(d), "cancel", "", "", "historic"])
        w["guard_exc"] = gexc

        # ---- clock marks
        marks = []
        for z in ZONES:
            std, smr, ta, tb = tr[z]
            d = h0
            while d < h1:
                yy, mm, dd = civil(d)
                loc = ts("%04d-%02d-%02dT12:00:00Z" % (yy, mm, dd))
                u = local_to_utc(tr, z, loc)
                marks.append(["register", z, wall(loc), iso(u), "noon-mark"])
                d += 86400
            for t in (ta, tb):
                if t is None:
                    continue
                for off in range(-10800, 10801, 900):
                    u = t + off
                    o = off_at_utc(tr, z, u)
                    marks.append(["register", z, wall(u + o), iso(u), "transition-mark"])
        k = 0
        while len(marks) < p["rows_marks"]:
            k += 1
            z = ZONES[k % 4]
            u = h0 + 86400 * (k % 360) + 3600 * (k % 11)
            marks.append(["neighbour", z, wall(u + 3600 * ((k % 5) - 2)), iso(u), "liaison-mark"])
        w["marks"] = marks
        return w


    def local_month_keys(w, z):
        tr, h0, h1 = w["tr"], w["h0"], w["h1"]
        out = []
        y, m, _ = civil(h0 + off_at_utc(tr, z, h0))
        while True:
            a = local_to_utc(tr, z, month_start(y, m))
            ny, nm = next_month(y, m)
            b = local_to_utc(tr, z, month_start(ny, nm))
            if a >= h1:
                break
            if b > h0:
                out.append(("%04d-%02d" % (y, m), max(a, h0), min(b, h1)))
            y, m = ny, nm
        return out


    def emit_duty(w):
        p = w["p"]
        rows = {"commercial": [], "public": []}
        for i, hid in enumerate(w["holders"]):
            seg = w["hclass"][hid]
            if (i % 2) != 0:
                continue
            keys = local_month_keys(w, w["zrec"][hid])
            for j, (key, a, b) in enumerate(keys):
                allow = 1000000 * (120 + ((i * 7 + j * 13) % 900))
                note = ""
                if i >= 40 and (i + j) % 19 == 5:
                    allow = allow // 60
                    note = "unit=khz_min"
                rows[seg].append([hid, key, allow, note])
            if i >= 40:
                y0 = int(keys[0][0][:4])
                rows[seg].append([hid, "%04d-%02d" % (y0 - 1, 6), 1000 * 300, "out-of-horizon"])
        k = 0
        for seg in ("commercial", "public"):
            pool = [h for h in w["holders"] if w["hclass"][h] == seg]
            while len(rows[seg]) < 2080 and pool:
                k += 1
                hid = pool[k % len(pool)]
                y0 = civil(w["h0"])[0]
                rows[seg].append([hid, "%04d-%02d" % (y0 - 2, 1 + (k % 12)), 1000 * (50 + k % 200),
                                  "archive"])
        w["duty"] = rows
        return w


    # ---------------------------------------------------------------- writers

    def _w(root, name, lines):
        with open(os.path.join(root, name), "w", encoding="utf-8", newline="\n") as fh:
            fh.write("\n".join(lines) + "\n")


    CORE_HEAD = ("assignment_id,revision,recorded_at,action,zone,holder_ref,parent_id,"
                 "effective_from,effective_to,f_low_khz,f_high_khz,bandwidth_khz,desk,remark")
    OFF_HEAD = ("assignment_id\trevision\trecorded_at_local\taction\teffective_from_local\t"
                "effective_to_local\tf_low_hz\tbandwidth_hz\tholder_label\tdesk")


    def write_data(w, root):
        p = w["p"]
        tr, h0, h1, as_of = w["tr"], w["h0"], w["h1"], w["as_of"]
        spec = w["spec"]
        os.makedirs(root, exist_ok=True)
        names = []

        # ---- channel raster
        rows = ["band,channel_index,f_low_khz,f_high_khz,status"]
        for c in w["channels"]:
            rows.append("%s,%d,%d,%d,%s" % (c[0], c[1], c[2], c[3], c[4]))
        _w(root, "channel_raster.csv", rows)
        names.append("channel_raster.csv")

        # ---- core monthly extracts
        buckets = {}
        for mo in p["core_months"]:
            buckets[mo] = []
        order = sorted(buckets)
        for r in w["recs"]["core"]:
            yy, mm, _ = civil(r["rec"])
            key = (yy, mm) if (yy, mm) in buckets else order[-1]
            buckets[key].append(r)
        for mi, mo in enumerate(order):
            rows = [CORE_HEAD]
            pool = sorted(buckets[mo], key=lambda r: (r["rec"], r["idx"]))
            for j, r in enumerate(pool):
                ident = r["identity"]
                tm = r["time"]
                fq = r["freq"]
                fhigh = ""
                if (r["idx"] % 9) != 4:
                    fhigh = str(fq["f_high"] + ((fq["f_high"] - fq["f_low"]) // 4
                                                if (r["idx"] % 13) == 6 else 0))
                rows.append(",".join([
                    r["aid"], str(r["rev"]), iso(r["rec"]), r["action"], ident["zone"],
                    ident["holder_ref"], ident["parent_id"], iso(tm["ef"]),
                    "" if tm["et"] is None else iso(tm["et"]), str(fq["f_low"]), fhigh,
                    str(fq["bw"]), "desk-%d" % (1 + r["idx"] % 9),
                    "restatement" if r["rev"] == 1 and j % 5 == 0 else "entry",
                ]))
            k = 0
            while len(rows) < p["rows_core"] + 1:
                k += 1
                aid = w["aids"][(mi * 977 + k * 7) % len(w["aids"])]
                s = spec[aid]
                rec = month_start(*mo) + 3600 * (k % 600)
                rows.append(",".join([
                    aid, "1", iso(rec), "amend", s["zone"], s["holder"].lower(), "",
                    iso(s["ef"] - 86400 * (1 + k % 5)), iso(s["et"] + 86400 * (1 + k % 7)),
                    str(s["f_low"]), str(s["f_high"]), str(s["f_high"] - s["f_low"]),
                    "desk-%d" % (1 + k % 9), "restatement",
                ]))
            nm = "assignments_core_%04d_%02d.csv" % mo
            _w(root, nm, rows)
            names.append(nm)

        # ---- zone office logs
        for z in ZONES:
            pool = [r for r in w["recs"]["office"] if spec[r["aid"]]["zone"] == z]
            pool.sort(key=lambda r: (r["rec"], r["idx"]))
            half = len(pool) // 2
            parts = [pool[:half], pool[half:]]
            for hi, part in enumerate(parts):
                rows = [OFF_HEAD]
                for r in part:
                    tm, fq = r["time"], r["freq"]
                    o = off_at_utc(tr, z, r["rec"])
                    oe = off_at_utc(tr, z, tm["ef"])
                    ot = off_at_utc(tr, z, tm["et"]) if tm["et"] is not None else 0
                    bw_hz = ""
                    lo_hz = ""
                    if fq is not None:
                        lo_hz = str(fq["f_low"] * 1000)
                        bw_hz = str(fq["bw"] * 1000 + (137 if fq["badunit"] == "hz_remainder" else 0))
                    rows.append("\t".join([
                        r["aid"], str(r["rev"]), wall(r["rec"] + o), r["action"],
                        wall(tm["ef"] + oe),
                        "" if tm["et"] is None else wall(tm["et"] + ot),
                        lo_hz, bw_hz, "holder-%s" % (r["aid"][-3:]), "%s-desk-%d" % (z.lower(), 1 + r["idx"] % 5),
                    ]))
                k = 0
                zp = [a for a in w["aids"] if spec[a]["zone"] == z]
                while len(rows) < p["rows_office"] + 1:
                    k += 1
                    aid = zp[(hi * 389 + k * 11) % len(zp)]
                    s = spec[aid]
                    u = h0 - 86400 * (30 + k % 200) + 3600 * (k % 19)
                    o = off_at_utc(tr, z, u)
                    rows.append("\t".join([
                        aid, "1", wall(u + o), "amend",
                        wall(s["ef"] + off_at_utc(tr, z, s["ef"])),
                        wall(s["et"] + off_at_utc(tr, z, s["et"])),
                        str(s["f_low"] * 1000), str((s["f_high"] - s["f_low"]) * 1000),
                        "holder-%s" % aid[-3:], "%s-desk-6" % z.lower(),
                    ]))
                nm = "zone_office_log_%s_h%d.tsv" % (z.lower(), hi + 1)
                _w(root, nm, rows)
                names.append(nm)

        # ---- coordination decisions
        qs = {1: [], 2: [], 3: [], 4: []}
        for r in w["recs"]["coord"]:
            qs[1 + ((civil(r["rec"])[1] - 1) // 3)].append(r)
        for q in (1, 2, 3, 4):
            rows = []
            for r in sorted(qs[q], key=lambda r: (r["rec"], r["idx"])):
                z = spec[r["aid"]]["zone"]
                o = off_at_utc(tr, z, r["rec"])
                d = {"assignment_id": r["aid"], "revision": r["rev"],
                     "recorded_at": iso_off(r["rec"], o), "action": r["action"],
                     "committee": "coex-%s" % z.lower(), "minute_ref": "M%05d" % (r["idx"] + 1)}
                fq = r["freq"]
                if fq is not None:
                    d["f_low_khz"] = fq["f_low"]
                    if fq["badunit"] == "missing":
                        d["bandwidth"] = fq["bw"]
                    elif fq["badunit"] == "MHz":
                        d["bandwidth"] = fq["bw"]
                        d["bandwidth_unit"] = "MHz"
                    elif (r["idx"] % 3) == 1:
                        d["bandwidth"] = fq["bw"] * 1000
                        d["bandwidth_unit"] = "Hz"
                    else:
                        d["bandwidth"] = fq["bw"]
                        d["bandwidth_unit"] = "kHz"
                    if fq["mismatch"]:
                        d["f_high_khz"] = fq["f_high"] + (fq["f_high"] - fq["f_low"]) // 2
                    elif (r["idx"] % 7) == 3:
                        d["f_high_khz"] = fq["f_high"]
                tm = r["time"]
                if tm is not None:
                    d["effective_from"] = iso_off(tm["ef"], off_at_utc(tr, z, tm["ef"]))
                    if tm["et"] == "NULL":
                        d["effective_to"] = None
                    elif tm["et"] is None:
                        d["effective_to"] = ""
                    else:
                        d["effective_to"] = iso_off(tm["et"], off_at_utc(tr, z, tm["et"]))
                idn = r["identity"]
                if idn is not None:
                    d["holder_ref"] = idn["holder_ref"]
                    d["zone"] = idn["zone"]
                    d["parent_id"] = idn["parent_id"]
                rows.append(json.dumps(d, sort_keys=True))
            k = 0
            while len(rows) < p["rows_coord"]:
                k += 1
                aid = w["aids"][(q * 613 + k * 5) % len(w["aids"])]
                s = spec[aid]
                z = s["zone"]
                u = month_start(civil(h0)[0] - 1, 1 + ((q - 1) * 3 + k % 3)) + 3600 * (k % 500)
                rows.append(json.dumps({
                    "assignment_id": aid, "revision": 1, "recorded_at": iso_off(u, off_at_utc(tr, z, u)),
                    "action": "note", "committee": "coex-%s" % z.lower(),
                    "minute_ref": "N%05d" % k, "f_low_khz": s["f_low"],
                    "bandwidth": s["f_high"] - s["f_low"], "bandwidth_unit": "kHz",
                }, sort_keys=True))
            nm = "coordination_decisions_q%d.jsonl" % q
            _w(root, nm, rows)
            names.append(nm)

        # ---- state events
        for z in ZONES:
            rows = ["assignment_id,event,event_ts,recorded_at,desk"]
            for e in w["events"][z]:
                rows.append(",".join(str(x) for x in e))
            nm = "state_events_%s.csv" % z.lower()
            _w(root, nm, rows)
            names.append(nm)

        # ---- holder registry
        for z in ZONES:
            rows = ["canonical_id,holder_class,zone_of_record,as_of,status_snapshot,note"]
            for r in w["reg_rows"][z]:
                rows.append(",".join(str(x) for x in r))
            nm = "holder_registry_%s.csv" % z.lower()
            _w(root, nm, rows)
            names.append(nm)

        rows = ["alias_id,canonical_id,notice_date,reason"]
        for r in w["alias_rows"]:
            rows.append(",".join(str(x) for x in r))
        _w(root, "holder_alias_map.csv", rows)
        names.append("holder_alias_map.csv")

        rows = ["canonical_id,status,status_from,source"]
        for r in w["status_rows"]:
            rows.append(",".join(str(x) for x in r))
        _w(root, "holder_status_history.csv", rows)
        names.append("holder_status_history.csv")

        rows = ["assignment_id,notice_date,recorded_at,scope,issuer"]
        for k in range(1, 61):
            rows.append(",".join(["A-9%04d" % (5000 + k), day(h0 - 86400 * (100 + k)),
                                  iso(as_of - 86400 * (200 + k % 90)), "full", "liaison"]))
        for r in w["retract_rows"]:
            rows.append(",".join(str(x) for x in r))
        k = 60
        while len(rows) < p["rows_retract"] + 1:
            k += 1
            rows.append(",".join(["A-9%04d" % (5000 + k), day(h0 - 86400 * (100 + k)),
                                  iso(as_of - 86400 * (200 + k % 90)), "full", "liaison"]))
        _w(root, "retraction_notices.csv", rows)
        names.append("retraction_notices.csv")

        for z in ZONES:
            rows = ["rule_id,zone,recurrence,local_start,duration_min,valid_from,valid_to,"
                    "f_lo_khz,f_hi_khz,status,purpose"]
            for r in w["guards"][z]:
                rows.append(",".join(str(x) for x in r))
            nm = "guard_windows_%s.csv" % z.lower()
            _w(root, nm, rows)
            names.append(nm)

        rows = ["zone,rule_id,occurrence_date,kind,local_start,duration_min,note"]
        for r in w["guard_exc"]:
            rows.append(",".join(str(x) for x in r))
        _w(root, "guard_exceptions.csv", rows)
        names.append("guard_exceptions.csv")

        rows = ["assignment_id,layer,revision,recorded_at,governing"]
        for k in range(1, 61):
            aid = w["aids"][(k * 29) % len(w["aids"])]
            rows.append(",".join([aid, "core", "1", iso(as_of - 86400 * (120 + k % 200)), "false"]))
        for r in w["flags"]:
            rows.append(",".join(str(x) for x in r))
        k = 60
        while len(rows) < p["rows_flags"] + 1:
            k += 1
            aid = w["aids"][(k * 29) % len(w["aids"])]
            rows.append(",".join([aid, "core", "1", iso(as_of - 86400 * (120 + k % 200)), "false"]))
        _w(root, "register_governing_flags.csv", rows)
        names.append("register_governing_flags.csv")

        rows = ["assignment_id,field_group,layer_followed,observed_on"]
        for k in range(1, 61):
            rows.append(",".join(["A-9%04d" % (7000 + k), GROUPS[k % 3], p["rank"][k % 3],
                                  day(as_of - 86400 * (150 + k % 120))]))
        for r in w["prec_obs"]:
            rows.append(",".join(str(x) for x in r))
        k = 60
        while len(rows) < p["rows_prec"] + 1:
            k += 1
            rows.append(",".join(["A-9%04d" % (7000 + k), GROUPS[k % 3], p["rank"][k % 3],
                                  day(as_of - 86400 * (150 + k % 120))]))
        _w(root, "precedence_observations.csv", rows)
        names.append("precedence_observations.csv")

        rows = ["jurisdiction,zone,local_stamp,utc_stamp,note"]
        for r in w["marks"]:
            rows.append(",".join(str(x) for x in r))
        _w(root, "zone_clock_marks.csv", rows)
        names.append("zone_clock_marks.csv")

        for seg in ("commercial", "public"):
            rows = ["canonical_id,month,allowance_khz_s,notes"]
            for r in w["duty"][seg]:
                rows.append(",".join(str(x) for x in r))
            nm = "duty_budget_%s.csv" % seg
            _w(root, nm, rows)
            names.append(nm)
        return names


    # ---------------------------------------------------------------- specs

    def write_specs(w, root, data_names):
        p = w["p"]
        h0s, h1s = p["horizon"]
        L = []
        L.append("# Band plan")
        L.append("")
        L.append("The measurable spectrum of the coexistence register is the union of the bands")
        L.append("listed below. Frequency bounds are kilohertz, lower bound inclusive and upper")
        L.append("bound exclusive. Spectrum that falls between two bands is not measurable and")
        L.append("carries no occupancy. The raster column repeats the nominal channel width of")
        L.append("the band; `channel_raster.csv` is the authority for individual channel bounds")
        L.append("and for channel withdrawal.")
        L.append("")
        L.append("| band | f_low_khz | f_high_khz | raster_khz |")
        L.append("| --- | --- | --- | --- |")
        for b in p["bands"]:
            L.append("| %s | %d | %d | %d |" % (b[0], b[1], b[2], b[3]))
        L.append("")
        L.append("A channel whose status in `channel_raster.csv` is `withdrawn` is not")
        L.append("measurable spectrum. A grant that covers withdrawn channels keeps only the")
        L.append("usable runs of its frequency span, so one grant can carry several frequency")
        L.append("runs. A grant whose frequency span meets no usable channel at all is faulty.")
        _w(root, "band_plan.md", L)

        L = ["# Zone clock rules", ""]
        L.append("Each zone keeps a standard offset from universal time. Three zones also keep a")
        L.append("summer offset during an annual window. The window bounds below are wall clock")
        L.append("stamps without a zone marker, so the register publishes them twice a year and")
        L.append("they are not by themselves universal time. Whether a published window bound is")
        L.append("read as a local standard wall clock reading or as a universal time reading is")
        L.append("the same for every zone and for every window bound, and it is settled by")
        L.append("`zone_clock_marks.csv`, which pairs local readings with universal readings.")
        L.append("Only rows whose jurisdiction is `register` are authoritative; rows from the")
        L.append("neighbouring administration are liaison material and bind nothing.")
        L.append("")
        L.append("| zone | standard_offset_sec | summer_offset_sec | summer_from | summer_to |")
        L.append("| --- | --- | --- | --- | --- |")
        for z in ZONES:
            std, smr, a, b = p["zone_clock"][z]
            L.append("| %s | %d | %d | %s | %s |" % (z, std, smr, a or "none", b or "none"))
        L.append("")
        L.append("A zone whose window bounds read `none` keeps its standard offset all year.")
        L.append("Inside the summer window the summer offset applies, lower bound inclusive and")
        L.append("upper bound exclusive, measured on universal time once the window has been")
        L.append("placed on universal time. A local reading that falls in the gap created by a")
        L.append("forward step, or in the overlap created by a backward step, is read with the")
        L.append("standard offset.")
        _w(root, "zone_time_rules.md", L)

        L = ["# Precedence policy", ""]
        L.append("Three source layers describe the same grants. A layer supplies a field group")
        L.append("only when its governing record carries values for that group. The field groups")
        L.append("are `identity` for holder reference, zone and parent, `time` for the effective")
        L.append("bounds, and `frequency` for the frequency bounds. Each group is settled")
        L.append("independently: the governing value for a group comes from the highest ranked")
        L.append("layer that supplies that group for that grant.")
        L.append("")
        L.append("| rank | layer |")
        L.append("| --- | --- |")
        for i, lay in enumerate(p["rank"]):
            L.append("| %d | %s |" % (i + 1, lay))
        L.append("")
        L.append("One documented exception promotes a single layer to rank one for exactly one")
        L.append("licence segment and exactly one field group, and leaves the remaining ranks in")
        L.append("their published order. The register does not restate the exception here. It")
        L.append("records, in `precedence_observations.csv`, the layer the published register")
        L.append("actually followed for a sample of grants and field groups, and the exception")
        L.append("triple of segment, field group and promoted layer follows from that sample.")
        L.append("The exception never touches the `identity` group, so holder resolution and the")
        L.append("licence segment are always settled by the published ranks.")
        L.append("")
        L.append("The governing record of a grant, as opposed to the governing record of a layer,")
        L.append("is the governing record of the highest ranked layer that supplies the grant")
        L.append("`identity` group. Its action decides whether the grant is withdrawn.")
        L.append("")
        L.append("Within one layer a grant may carry several records. The governing record of a")
        L.append("layer is the visible record with the highest revision. When two visible records")
        L.append("share the highest revision the register applies one tiebreak on `recorded_at`,")
        L.append("the same tiebreak everywhere, and `register_governing_flags.csv` records which")
        L.append("of the tied records the published register treated as governing.")
        L.append("")
        L.append("Holder registry conflicts are settled in this order.")
        L.append("")
        L.append("| step | rule |")
        L.append("| --- | --- |")
        L.append("| 1 | the registry row with the latest as_of wins |")
        L.append("| 2 | on a tie the row whose zone_of_record equals the grant zone wins |")
        L.append("| 3 | on a tie the row whose zone_of_record sorts first wins |")
        L.append("")
        L.append("The `status_snapshot` column of a registry row is a convenience copy and binds")
        L.append("nothing. `holder_status_history.csv` is the authority for holder status, read at")
        L.append("the effective start of the grant under test, taking the row with the latest")
        L.append("`status_from` at or before that instant, and on a shared instant the status")
        L.append("that sorts last. A holder with no such row counts as `provisional`.")
        _w(root, "precedence_policy.md", L)

        L = ["# Normalisation rules", ""]
        L.append("## Holder references")
        L.append("")
        L.append("A holder reference in any source becomes a canonical identifier by applying")
        L.append("these steps in order.")
        L.append("")
        L.append("| step | rule |")
        L.append("| --- | --- |")
        L.append("| 1 | fold to upper case |")
        L.append("| 2 | drop every character that is not a letter or a digit |")
        L.append("| 3 | drop a leading HL prefix when one is present |")
        L.append("| 4 | when more than six characters remain keep the last six |")
        L.append("| 5 | when fewer than six characters remain pad on the left with zeros to six |")
        L.append("")
        L.append("`holder_alias_map.csv` then redirects canonical identifiers. Redirection is")
        L.append("applied until no further redirection applies. A redirection that returns to an")
        L.append("identifier already visited forms a cycle, and every member of that cycle")
        L.append("resolves to the member that sorts first. A row that redirects an identifier to")
        L.append("itself changes nothing. A row whose target is unknown to every registry still")
        L.append("applies; the grant then has no registry entry.")
        L.append("")
        L.append("## Effective bounds")
        L.append("")
        L.append("| encoding of effective_to | reading |")
        L.append("| --- | --- |")
        L.append("| an empty field | open ended, so the bound is the horizon end |")
        L.append("| the json null value | the committee deferred the bound, so the grant is faulty |")
        L.append("| a stamp equal to effective_from | a closed grant of zero duration |")
        L.append("| any other stamp | the stamp itself |")
        L.append("")
        L.append("Both effective bounds are half open, lower inclusive and upper exclusive. The")
        L.append("same convention holds for frequency bounds and for every window in this corpus.")
        L.append("")
        L.append("## Frequency bounds")
        L.append("")
        L.append("A record carries a lower bound and a width, and may also carry an explicit")
        L.append("upper bound. When both an explicit upper bound and a width are present and they")
        L.append("disagree the explicit upper bound governs. When no explicit upper bound is")
        L.append("present the upper bound is the lower bound plus the width. A lower bound must")
        L.append("be the lower edge of a channel of the raster and an upper bound must be the")
        L.append("upper edge of a channel of the raster, in either case of any band.")
        L.append("")
        L.append("A zone office log carries only grants filed in the zone named in the file")
        L.append("name, and every stamp in that file is the local time of that zone. A")
        L.append("coordination minute carries its own offset. A national register extract and a")
        L.append("state event file carry universal time.")
        L.append("")
        L.append("`unit_declarations.ini` states the unit and the clock basis of every source")
        L.append("column. A width expressed in hertz that is not a whole number of kilohertz")
        L.append("cannot be converted and makes the grant faulty. A declared unit token outside")
        L.append("the accepted set, or a missing declaration where one is required, also makes")
        L.append("the grant faulty.")
        _w(root, "normalisation_rules.md", L)

        L = ["# Grant state machine", ""]
        L.append("A grant occupies spectrum only while it is active. Every grant starts active at")
        L.append("its effective start. `state_events_<zone>.csv` carries the dated events of the")
        L.append("zone. Events are read in event order and the same visibility cutoff that")
        L.append("applies to source records applies to events.")
        L.append("")
        L.append("| state | event | next state | measurable after |")
        L.append("| --- | --- | --- | --- |")
        L.append("| active | activate | active | yes |")
        L.append("| active | suspend | suspended | no |")
        L.append("| active | restore | active | yes |")
        L.append("| active | terminate | terminated | no |")
        L.append("| suspended | suspend | suspended | no |")
        L.append("| suspended | restore | active | yes |")
        L.append("| suspended | activate | suspended | no |")
        L.append("| suspended | terminate | terminated | no |")
        L.append("| terminated | any | terminated | no |")
        L.append("")
        L.append("A `restore` that reaches a grant that is already active is an anomaly. The")
        L.append("event is ignored and the anomaly is counted. An event stamped before the")
        L.append("effective start takes effect at the effective start. An event stamped at or")
        L.append("after the effective end is ignored. Events that share an instant are read in")
        L.append("the order `terminate`, `suspend`, `restore`, `activate`.")
        _w(root, "state_machine.md", L)

        L = ["# Reason codes", ""]
        L.append("A grant whose governing record is a retraction, or that carries a live")
        L.append("retraction notice, is withdrawn. A withdrawn grant is counted as retracted and")
        L.append("is not examined for faults. `retraction_notices.csv` carries notices with a")
        L.append("scope of `full` and later notices with a scope of `withdrawn` that cancel an")
        L.append("earlier notice of the same grant and notice date. A notice binds only when it")
        L.append("is visible under the cutoff.")
        L.append("")
        L.append("Every remaining grant is tested against the reject codes below in the order")
        L.append("shown. The first code that matches is the only code recorded for that grant.")
        L.append("")
        L.append("| order | code | meaning |")
        L.append("| --- | --- | --- |")
        L.append("| 1 | TERM_MISSING | the governing time group is absent or deferred |")
        L.append("| 2 | SPAN_INVERTED | the effective end precedes the effective start |")
        L.append("| 3 | UNIT_AMBIGUOUS | a governing frequency value cannot be converted exactly |")
        L.append("| 4 | BAND_OUTSIDE | the frequency span meets no usable channel |")
        L.append("| 5 | RASTER_MISALIGNED | a frequency bound is not a channel edge of its band |")
        L.append("| 6 | HOLDER_UNKNOWN | the resolved holder appears in no registry |")
        L.append("| 7 | ZONE_MISMATCH | a provisional holder is filed against another zone |")
        L.append("| 8 | PARENT_UNKNOWN | the parent is absent from the register or sits in another zone |")
        L.append("| 9 | PARENT_CYCLE | the parent chain returns to the grant |")
        L.append("| 10 | PARENT_RETRACTED | the parent is withdrawn or rejected |")
        L.append("")
        L.append("A grant whose holder is filed against a zone other than the grant zone, and")
        L.append("whose holder status is `confirmed`, is not rejected. The difference is recorded")
        L.append("as a note instead.")
        L.append("")
        L.append("Notes are counted but never remove a grant from the measure.")
        L.append("")
        L.append("| note | meaning |")
        L.append("| --- | --- |")
        L.append("| ALIAS_RESOLVED | the holder reference moved through at least one redirection |")
        L.append("| CLIPPED_TO_BAND | a frequency bound was trimmed to a usable channel run |")
        L.append("| CLIPPED_TO_HORIZON | an effective bound was trimmed to the horizon |")
        L.append("| OPEN_ENDED | the effective end was absent and became the horizon end |")
        L.append("| WIDTH_MISMATCH | an explicit upper bound disagreed with the stated width |")
        L.append("| ZONE_OF_RECORD_DIFFERS | the holder is filed against another zone |")
        L.append("| SPLIT_BY_RASTER | the frequency span became more than one usable run |")
        L.append("| STATE_ANOMALY | a restore reached a grant that was already active |")
        L.append("| ZERO_SPAN | the effective bounds are equal |")
        L.append("")
        L.append("A note is recorded only for a grant that passes every reject test. A note is")
        L.append("counted once for each grant it applies to, except STATE_ANOMALY which is")
        L.append("counted once for each ignored event.")
        _w(root, "reason_codes.md", L)

        L = ["# Reservation policy", ""]
        L.append("`guard_windows_<zone>.csv` carries the radio astronomy reservations of the")
        L.append("zone. A row whose status is not `active` is ignored. A reservation occurs on")
        L.append("every local date in the half open range from `valid_from` to `valid_to` that")
        L.append("matches the recurrence token.")
        L.append("")
        L.append("| recurrence token | occurs on |")
        L.append("| --- | --- |")
        L.append("| daily | every local date in range |")
        L.append("| weekly:N | every local date in range whose iso weekday is N |")
        L.append("| monthly:N | every local date in range whose day of month is N |")
        L.append("")
        L.append("A `monthly:N` token produces no occurrence in a month that has no day N. An")
        L.append("occurrence begins at the local start time of the matching local date and runs")
        L.append("for `duration_min` minutes of elapsed time, so only the start needs a clock")
        L.append("conversion. An occurrence is trimmed to the horizon.")
        L.append("")
        L.append("`guard_exceptions.csv` adjusts occurrences. A row of kind `cancel` removes the")
        L.append("occurrence of that rule on that local date. A row of kind `add` creates one")
        L.append("occurrence of that rule on that local date with the local start and duration")
        L.append("given on the exception row. Cancellations are applied before additions.")
        L.append("")
        L.append("Reserved spectrum is subtracted from every grant of the zone, in the frequency")
        L.append("span of the rule and in the time span of the occurrence. Subtraction happens")
        L.append("after the channel trim, the horizon trim and the state intervals, and before")
        L.append("any clipping to a parent grant. The subtracted measure of a zone is the union")
        L.append("measure of the zone before subtraction less the union measure after it.")
        _w(root, "guard_policy.md", L)

        L = ["# Duty policy", ""]
        L.append("A holder named in `duty_budget_<segment>.csv` is audited. The audit runs over")
        L.append("the local calendar months of the zone the holder is filed against, taken from")
        L.append("the registry row with the latest as_of and on a tie the zone name that sorts")
        L.append("first, in")
        L.append("ascending month order, using the month bounds of that zone and not the bounds")
        L.append("of the zone of any individual grant. Months outside the horizon are ignored.")
        L.append("")
        L.append("The occupancy of a holder in a month is the union measure of the final grant")
        L.append("extents of that holder inside the month. Overlapping grants of one holder")
        L.append("count once.")
        L.append("")
        L.append("| quantity | rule |")
        L.append("| --- | --- |")
        L.append("| available | the month allowance plus the carry brought into the month |")
        L.append("| consumed | the smaller of available and occupancy |")
        L.append("| deficit | occupancy less available when positive, otherwise zero |")
        L.append("| carry_out | available less occupancy when positive, otherwise zero |")
        L.append("")
        L.append("The carry leaving a month is zero when the holder has at least one visible")
        L.append("`suspend` event stamped inside that month, whatever the carry would otherwise")
        L.append("have been. The carry entering the first audited month is zero.")
        L.append("")
        L.append("An allowance is stated in kilohertz seconds unless the notes field of the row")
        L.append("reads `unit=khz_min`, in which case the value is kilohertz minutes.")
        L.append("")
        L.append("A month counts as a carry reset when a visible `suspend` event of the holder")
        L.append("falls inside that month and available exceeds occupancy, so a carry that would")
        L.append("otherwise have left the month was forced to zero. A suspend event of any grant")
        L.append("whose resolved holder is the holder counts, whatever became of that grant.")
        _w(root, "duty_policy.md", L)

        L = ["# Output contract", ""]
        L.append("Write nine json documents and one python module under the output directory.")
        L.append("Every json document is a single object, written with sorted keys and two space")
        L.append("indentation, and every measure is an exact integer count of kilohertz seconds.")
        L.append("No floating point value appears in any document.")
        L.append("")
        L.append("## summary.json")
        L.append("")
        L.append("Keys: `horizon` (object with `start`, `end`, `as_of`), `assignments_total`,")
        L.append("`assignments_measurable`, `rectangles`, `area_total_assigned`, `area_union`,")
        L.append("`area_exclusive`, `area_shared`, `area_excess`, `excess_charge_total`,")
        L.append("`shared_ratio_ppm`, `zone_area_union`, `zone_share_bp`, `segment_area_union`,")
        L.append("`segment_share_bp`, `cross_segment_shared_area`, `guard_subtracted_area`.")
        L.append("")
        L.append("`assignments_total` counts the grant identifiers that carry at least one")
        L.append("visible record in at least one of the three grant layers. A grant counts as")
        L.append("measurable when it carries at least one final extent of positive measure, and")
        L.append("`assignments_measurable` counts those grants.")
        L.append("A final extent set is reduced before it is counted. Extents of one grant that")
        L.append("touch in frequency and share both time bounds become one extent, then extents")
        L.append("of one grant that touch in time and share both frequency bounds become one")
        L.append("extent, and the pair of passes repeats until nothing merges.")
        L.append("`rectangles` counts the reduced final extents over every zone. `area_total_assigned`")
        L.append("sums the final extents with multiplicity. `area_union` measures the covered")
        L.append("set, where zone, frequency and time are all coordinates. `area_exclusive`")
        L.append("measures the part of the covered set that exactly one extent covers and")
        L.append("`area_shared` measures the part that at least two extents cover.")
        L.append("`area_excess` is `area_total_assigned` less `area_union`.")
        L.append("`excess_charge_total` sums the charges described below.")
        L.append("`shared_ratio_ppm` scales `area_shared` by `ppm_scale` of `measure_config.ini`,")
        L.append("divides by `area_union`, and rounds once under the configured rounding mode.")
        L.append("`zone_share_bp` and `segment_share_bp` hold integer basis points that sum to")
        L.append("`share_total_bp`, allocated by largest remainder, with ties on the remainder")
        L.append("broken by the ascending key name. Zone shares are taken on `area_union`.")
        L.append("Segment shares are taken on the sum of the two segment union measures, which")
        L.append("exceeds `area_union` by `cross_segment_shared_area`.")
        L.append("")
        L.append("## region_<Zone>.json for North, South, West and East")
        L.append("")
        L.append("Keys: `zone`, `utc_offset_standard_sec`, `utc_offset_summer_sec`,")
        L.append("`summer_window_utc` (a two element list of stamps, or null),")
        L.append("`assignments_measurable`, `rectangles`, `area_total_assigned`, `area_union`,")
        L.append("`area_exclusive`, `area_shared`, `area_excess`, `guard_occurrences`,")
        L.append("`guard_subtracted_area`, `excess_charge_top`, `band_area_union`,")
        L.append("`month_area_union`.")
        L.append("")
        L.append("`band_area_union` maps every band identifier of the band plan to the union")
        L.append("measure inside that band. `month_area_union` maps every local calendar month")
        L.append("of the zone that meets the horizon, keyed `YYYY-MM`, to the union measure")
        L.append("inside that month; the values sum to `area_union`. `excess_charge_top` lists")
        L.append("the `top_excess` highest charged grants of the zone as two element lists of")
        L.append("grant identifier and charge, ordered by descending charge then ascending")
        L.append("identifier. Within any smallest cell of the covered set that carries two or")
        L.append("more extents, the covering grants are ordered by descending final own measure")
        L.append("then ascending identifier; the first keeps the cell and every other covering")
        L.append("grant is charged the measure of the cell.")
        L.append("")
        L.append("## segment_commercial.json and segment_public.json")
        L.append("")
        L.append("Keys: `segment`, `holders`, `assignments_measurable`, `area_union`,")
        L.append("`area_exclusive`, `area_shared`, `zone_area_union`, `top_holders`,")
        L.append("`duty_deficit_months`, `duty_carry_end`. `top_holders` lists the `top_holders`")
        L.append("largest holders of the segment as two element lists of canonical identifier and")
        L.append("union measure, ordered by descending measure then ascending identifier.")
        L.append("`duty_carry_end` sums the carry leaving the last audited month of every audited")
        L.append("holder of the segment. `holders` counts the canonical holders of the segment")
        L.append("that carry at least one measurable grant.")
        L.append("")
        L.append("## policy_audit.json")
        L.append("")
        L.append("Keys: `as_of`, `precedence_exception` (object with `segment`, `field_group`,")
        L.append("`layer`), `duplicate_tiebreak` (one of `earliest_recorded_at` or")
        L.append("`latest_recorded_at`), `clock_keying` (one of `local_standard` or `utc`),")
        L.append("`layer_governing_counts`, `alias_fixpoint_depth`, `alias_cycles`,")
        L.append("`parent_chain_max_depth`, `parent_rejects`, `duty`, `guard`.")
        L.append("")
        L.append("`layer_governing_counts` counts, per layer, the field group decisions that the")
        L.append("layer won across every grant that reached the fault tests.")
        L.append("`alias_fixpoint_depth` is the largest number of redirections applied to any")
        L.append("holder reference seen in the sources. `parent_chain_max_depth` is the longest")
        L.append("acyclic parent chain of a measurable grant, counting the grant itself as one.")
        L.append("`parent_rejects` maps the three parent reject codes to their counts. `duty`")
        L.append("holds `holders_audited`, `months_in_deficit`, `total_allowance`,")
        L.append("`total_consumed`, `carry_forward_end`, `carry_resets` and `top_deficit`, where")
        L.append("`top_deficit` lists the `top_deficit` largest single month deficits as three")
        L.append("element lists of holder, month key and deficit, ordered by descending deficit")
        L.append("then ascending holder then ascending month. `guard` holds `occurrences`,")
        L.append("`cancelled`, `added` and `subtracted_area`.")
        L.append("")
        L.append("## data_quality.json")
        L.append("")
        L.append("Keys: `assignments_total`, `rows_read_total`, `rejects`, `notes`, `retracted`,")
        L.append("`zero_span`, `manifest_mismatches`, `source_counts`.")
        L.append("")
        L.append("`retracted` counts the withdrawn grants and `zero_span` counts the grants")
        L.append("that pass every reject test and whose two effective bounds are equal.")
        L.append("")
        L.append("`rejects` maps every reject code of `reason_codes.md` to its count, including")
        L.append("codes that fired on nothing. `notes` maps every note of `reason_codes.md` to")
        L.append("its count. `source_counts` maps every record file of the corpus to an object")
        L.append("with `rows_read`, the data rows of the file, `rows_visible`, the rows the")
        L.append("cutoff admits, and `rows_governing`, the rows that became a governing record of")
        L.append("their layer; only the three grant layers report the last two figures and every")
        L.append("other record file reports zero for both. `manifest_mismatches` lists, in ascending order, the record files whose")
        L.append("declared row count in `source_manifest.md` differs from `rows_read`.")
        L.append("`rows_read_total` sums `rows_read` over every record file.")
        L.append("")
        L.append("## derive_report.py")
        L.append("")
        L.append("A python module that the registry can rerun. Invoked as")
        L.append("`python3 derive_report.py <corpus_dir> <output_dir>` it must read a corpus laid")
        L.append("out exactly like this one and write the same nine json documents into the")
        L.append("output directory. It must use only the python standard library, must not read")
        L.append("any path outside the corpus directory it is given, must not write outside the")
        L.append("output directory it is given, and must leave the corpus unchanged.")
        _w(root, "output_contract.md", L)

        L = ["# Corpus index", ""]
        L.append("Every record file of the corpus is listed with the source layer it belongs to.")
        L.append("Layer `core` is the national register extract, `office` is the zone office log")
        L.append("and `coord` is the coordination committee minute book. Files with layer")
        L.append("`reference` are tables rather than grant records.")
        L.append("")
        L.append("| file | layer |")
        L.append("| --- | --- |")
        for nm in sorted(data_names):
            if nm.startswith("assignments_core_"):
                lay = "core"
            elif nm.startswith("zone_office_log_"):
                lay = "office"
            elif nm.startswith("coordination_decisions_"):
                lay = "coord"
            else:
                lay = "reference"
            L.append("| %s | %s |" % (nm, lay))
        _w(root, "corpus_index.md", L)

        L = ["# Source manifest", ""]
        L.append("Each record file of the corpus declares the number of data rows it was cut")
        L.append("with, excluding any header line. A declaration is a claim of the issuing desk")
        L.append("and is not always true.")
        L.append("")
        L.append("| file | rows_declared | issuing_desk |")
        L.append("| --- | --- | --- |")
        rnd = random.Random(p["seed"] + 4242)
        for i, nm in enumerate(sorted(data_names)):
            path = os.path.join(root, nm)
            with open(path, "r", encoding="utf-8") as fh:
                n = sum(1 for _ in fh)
            if not nm.endswith(".jsonl"):
                n -= 1
            if i % 6 == 4:
                n += rnd.choice([-3, -1, 1, 2, 5])
            L.append("| %s | %d | desk-%d |" % (nm, n, 1 + i % 7))
        _w(root, "source_manifest.md", L)

        L = ["[horizon]"]
        L.append("start = %s" % h0s)
        L.append("end = %s" % h1s)
        L.append("as_of = %s" % p["as_of"])
        L.append("")
        L.append("[measure]")
        L.append("share_total_bp = 10000")
        L.append("ppm_scale = 1000000")
        L.append("rounding = half_even")
        L.append("shared_multiplicity_min = 2")
        L.append("")
        L.append("[limits]")
        L.append("top_holders = 5")
        L.append("top_excess = 3")
        L.append("top_deficit = 3")
        L.append("")
        L.append("[visibility]")
        L.append("rule = recorded_at strictly before as_of")
        _w(root, "measure_config.ini", L)

        L = ["[assignments_core]"]
        L.append("f_low_column = f_low_khz")
        L.append("f_high_column = f_high_khz")
        L.append("width_column = bandwidth_khz")
        L.append("frequency_unit = khz")
        L.append("clock_basis = utc")
        L.append("")
        L.append("[zone_office_log]")
        L.append("f_low_column = f_low_hz")
        L.append("f_high_column = none")
        L.append("width_column = bandwidth_hz")
        L.append("frequency_unit = hz")
        L.append("clock_basis = zone_local")
        L.append("")
        L.append("[coordination_decisions]")
        L.append("f_low_column = f_low_khz")
        L.append("f_high_column = f_high_khz")
        L.append("width_column = bandwidth")
        L.append("frequency_unit = declared")
        L.append("unit_column = bandwidth_unit")
        L.append("accepted_unit_tokens = kHz,Hz")
        L.append("clock_basis = offset_bearing")
        L.append("")
        L.append("[state_events]")
        L.append("clock_basis = utc")
        L.append("")
        L.append("[guard_windows]")
        L.append("clock_basis = zone_local")
        L.append("")
        L.append("[zone_clock_marks]")
        L.append("local_column = local_stamp")
        L.append("utc_column = utc_stamp")
        L.append("authoritative_jurisdiction = register")
        _w(root, "unit_declarations.ini", L)


    def write_world(root, name="visible"):
        p = profile(name)
        w = build(p)
        w = emit_records(w)
        w = emit_events(w)
        w = emit_duty(w)
        data_names = write_data(w, root)
        write_specs(w, root, data_names)
        return w
    return dict(locals())



# ---------------------------------------------------------------------------
# harness
# ---------------------------------------------------------------------------
_GEN = _load_generator()

ZONES = ["North", "South", "West", "East"]
SEGMENTS = ["commercial", "public"]
DOCS = (["summary.json", "policy_audit.json", "data_quality.json"]
        + ["region_%s.json" % z for z in ZONES]
        + ["segment_%s.json" % s for s in SEGMENTS])
SCRIPT = "derive_report.py"

_SETPRIV = ["setpriv", "--reuid=nobody", "--regid=nogroup", "--clear-groups"]
_SCAN_ROOTS = (Path("/tmp"), Path("/var/tmp"), Path("/dev/shm"))
_MEMO: dict = {}
_LOCK = threading.RLock()


def _memo(key, build):
    with _LOCK:
        if key not in _MEMO:
            try:
                _MEMO[key] = build()
            except Exception:  # a broken tier or run is recorded as missing, never raised into a check
                _MEMO[key] = None
        return _MEMO[key]


def _safe(fn):
    try:
        return bool(fn())
    except Exception:
        return False


def _same(got, want):
    return json.dumps(got, sort_keys=True) == json.dumps(want, sort_keys=True)


def _scratch(prefix):
    path = Path(tempfile.mkdtemp(prefix="bcom-" + prefix))
    path.chmod(0o755)
    return path


def _isolated_uid():
    if os.name != "posix" or os.geteuid() != 0:
        return None
    import pwd
    return pwd.getpwnam("nobody").pw_uid


def _untrusted(cmd):
    if _isolated_uid() is None:
        return cmd
    return _SETPRIV + cmd


def _tier(name):
    def build():
        root = _scratch("tier-%s-" % name)
        _GEN["write_world"](str(root), name)
        for p in [root, *root.rglob("*")]:
            p.chmod(0o755 if p.is_dir() else 0o644)
        return root
    return _memo("tier:%s" % name, build)


def _expect(tier):
    return _EXPECTED.get(tier)


def _delivered(workspace, name):
    def build():
        path = workspace / "out" / name
        if not path.is_file() or path.is_symlink() or path.stat().st_size > 200_000_000:
            return None
        return json.loads(path.read_text(encoding="utf-8"))
    return _memo("got:%s:%s" % (workspace, name), build)


def _delivered_text(workspace, name):
    def build():
        path = workspace / "out" / name
        if not path.is_file() or path.is_symlink() or path.stat().st_size > 200_000_000:
            return None
        return path.read_text(encoding="utf-8")
    return _memo("txt:%s:%s" % (workspace, name), build)


def _snapshot(root):
    return dict((str(p.relative_to(root)), p.read_bytes())
                for p in sorted(root.rglob("*")) if p.is_file())


def _owned_paths(uid, roots, skip):
    found = {}
    for top in roots:
        if not top.is_dir():
            continue
        for dirpath, dirnames, filenames in os.walk(top):
            here = Path(dirpath)
            kept = []
            for name in dirnames:
                path = here / name
                try:
                    info = path.lstat()
                except OSError:
                    continue
                if path in skip:
                    continue
                if info.st_uid == uid:
                    found[str(path)] = info.st_mtime_ns
                if info.st_uid == uid or info.st_mode & 0o001:
                    kept.append(name)
            dirnames[:] = kept
            for name in filenames:
                try:
                    info = (here / name).lstat()
                except OSError:
                    continue
                if info.st_uid == uid:
                    found[str(here / name)] = info.st_mtime_ns
    return found


def _run(workspace, tier):
    return _memo("run:%s:%s" % (workspace, tier), lambda: _run_once(workspace, tier))


def _run_once(workspace, tier):
    report = {"ok": False, "code": None, "outputs": {}, "files": [], "outside": [],
              "inputs_changed": False}
    script = workspace / "out" / SCRIPT
    if not script.is_file() or script.is_symlink():
        return report
    source = _tier(tier)
    if source is None:
        return report
    box = _scratch("run-%s-" % tier)
    prog = box / "prog"
    prog.mkdir()
    prog.chmod(0o755)
    (prog / SCRIPT).write_bytes(script.read_bytes())
    (prog / SCRIPT).chmod(0o644)
    feed = box / "in"
    shutil.copytree(source, feed)
    for p in [feed, *feed.rglob("*")]:
        p.chmod(0o777 if p.is_dir() else 0o666)
    before = _snapshot(feed)
    parent = box / "dest"
    parent.mkdir()
    parent.chmod(0o777)
    dest = parent / "out"
    dest.mkdir()
    dest.chmod(0o777)
    uid = _isolated_uid()
    roots = [*_SCAN_ROOTS, workspace / "out"]
    owned_before = _owned_paths(uid, roots, [feed, dest]) if uid is not None else {}
    env = {"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": str(box),
           "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "PYTHONHASHSEED": "0",
           "PYTHONDONTWRITEBYTECODE": "1"}
    try:
        proc = subprocess.Popen(
            _untrusted([sys.executable, "-I", str(prog / SCRIPT), str(feed), str(dest)]),
            cwd=str(box), env=env, stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    except OSError:
        return report
    try:
        report["code"] = proc.wait(timeout=600)
    except subprocess.TimeoutExpired:
        report["code"] = None
    finally:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
        proc.wait()
    owned_after = _owned_paths(uid, roots, [feed, dest]) if uid is not None else {}
    beside = set(str(p) for p in parent.iterdir() if p != dest)
    report["outside"] = sorted(beside | set(p for p, stamp in owned_after.items()
                                            if owned_before.get(p) != stamp))
    report["inputs_changed"] = _snapshot(feed) != before
    report["files"] = sorted(p.name for p in dest.iterdir()) if dest.is_dir() else []
    for name in DOCS:
        target = dest / name
        if target.is_file() and not target.is_symlink() and target.stat().st_size < 200_000_000:
            try:
                report["outputs"][name] = json.loads(target.read_text(encoding="utf-8"))
            except ValueError:
                report["outputs"][name] = None
    report["ok"] = report["code"] == 0 and all(report["outputs"].get(n) is not None
                                               for n in DOCS)
    return report


def _pick(doc, keys):
    return dict((k, doc.get(k)) for k in keys)


def _without(table, code):
    return dict((k, v) for k, v in table.items() if k != code)


def _shipped_match(workspace, name, keys):
    want = _expect("visible")
    got = _delivered(workspace, name)
    if want is None or got is None:
        return False
    return _same(_pick(got, keys), _pick(want[name], keys))


def _all_zones(workspace, keys):
    want = _expect("visible")
    if want is None:
        return False
    for z in ZONES:
        name = "region_%s.json" % z
        got = _delivered(workspace, name)
        if got is None or not _same(_pick(got, keys), _pick(want[name], keys)):
            return False
    return True


def _all_segments(workspace, keys):
    want = _expect("visible")
    if want is None:
        return False
    for s in SEGMENTS:
        name = "segment_%s.json" % s
        got = _delivered(workspace, name)
        if got is None or not _same(_pick(got, keys), _pick(want[name], keys)):
            return False
    return True


def _heldout_all(workspace, tier):
    want = _expect(tier)
    report = _run(workspace, tier)
    if want is None or not report["ok"]:
        return False
    return all(_same(report["outputs"][n], want[n]) for n in DOCS)


def _floats(node):
    if isinstance(node, float):
        return True
    if isinstance(node, dict):
        return any(_floats(v) for v in node.values())
    if isinstance(node, list):
        return any(_floats(v) for v in node)
    return False


def _utc_month_keys(horizon):
    h0 = datetime.strptime(horizon["start"], "%Y-%m-%dT%H:%M:%SZ")
    h1 = datetime.strptime(horizon["end"], "%Y-%m-%dT%H:%M:%SZ")
    keys = []
    y, m = h0.year, h0.month
    while datetime(y, m, 1) < h1:
        keys.append("%04d-%02d" % (y, m))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return keys


# ---------------------------------------------------------------------------
# positive checks
# ---------------------------------------------------------------------------
@criterion(description="The four union measures and the two derived excess measures in summary.json are exact.")
def summary_core_measures_exact(workspace: Path) -> bool:
    keys = ["area_total_assigned", "area_union", "area_exclusive", "area_shared",
            "area_excess", "excess_charge_total"]
    return _safe(lambda: _shipped_match(workspace, "summary.json", keys))


@criterion(description="The zone and segment union measures in summary.json and in every zone and segment report, the zone shares, the segment shares, the cross segment measure and the shared ratio are exact.")
def summary_shares_and_ratio_exact(workspace: Path) -> bool:
    keys = ["zone_area_union", "zone_share_bp", "segment_area_union", "segment_share_bp",
            "cross_segment_shared_area", "shared_ratio_ppm"]
    return _safe(lambda: _shipped_match(workspace, "summary.json", keys)
                 and _all_zones(workspace, ["area_union"])
                 and _all_segments(workspace, ["area_union"]))


@criterion(description="The precedence exception triple, the duplicate tiebreak and the clock keying in policy_audit.json are exact.")
def policy_withheld_rules_exact(workspace: Path) -> bool:
    keys = ["precedence_exception", "duplicate_tiebreak", "clock_keying"]
    return _safe(lambda: _shipped_match(workspace, "policy_audit.json", keys))


@criterion(description="Every zone report carries the exact local month breakdown and the exact band breakdown.")
def region_month_and_band_breakdown_exact(workspace: Path) -> bool:
    return _safe(lambda: _all_zones(workspace, ["month_area_union", "band_area_union"]))


@criterion(description="The reject tally and the note tally of data_quality.json apart from the zero span note, and the parent reject block of policy_audit.json, are exact for every code of the vocabulary.")
def data_quality_rejects_and_notes_exact(workspace: Path) -> bool:
    def check():
        want = _expect("visible")
        got = _delivered(workspace, "data_quality.json")
        if want is None or got is None:
            return False
        exp = want["data_quality.json"]
        return (_same(got.get("rejects"), exp["rejects"])
                and _same(_without(got.get("notes"), "ZERO_SPAN"), _without(exp["notes"], "ZERO_SPAN"))
                and _shipped_match(workspace, "policy_audit.json", ["parent_rejects"]))
    return _safe(check)


@criterion(description="Run on a corpus the agent never saw the delivered module reproduces all nine documents exactly.")
def script_reproduces_the_shifted_corpus(workspace: Path) -> bool:
    return _safe(lambda: _heldout_all(workspace, "shifted"))


@criterion(description="Run on a boundary dense corpus the agent never saw the delivered module reproduces all nine documents exactly.")
def script_reproduces_the_edge_corpus(workspace: Path) -> bool:
    return _safe(lambda: _heldout_all(workspace, "edge"))


@criterion(description="The grant counts, the extent count and the horizon in summary.json, the grant count of data_quality.json and the as of stamp of policy_audit.json are exact.")
def summary_counts_exact(workspace: Path) -> bool:
    keys = ["assignments_total", "assignments_measurable", "rectangles", "horizon"]
    return _safe(lambda: _shipped_match(workspace, "summary.json", keys)
                 and _shipped_match(workspace, "data_quality.json", ["assignments_total"])
                 and _shipped_match(workspace, "policy_audit.json", ["as_of"]))


@criterion(description="Every zone report carries the exact assigned, exclusive, shared and excess measures, grant count and extent count for its own extents.")
def region_headline_measures_exact(workspace: Path) -> bool:
    keys = ["area_total_assigned", "area_exclusive", "area_shared",
            "area_excess", "assignments_measurable", "rectangles"]
    return _safe(lambda: _all_zones(workspace, keys))


@criterion(description="Every zone report names the exact highest charged grants with their exact charges.")
def region_excess_charge_top_exact(workspace: Path) -> bool:
    return _safe(lambda: _all_zones(workspace, ["excess_charge_top"]))


@criterion(description="Every zone report carries the exact standard offset, summer offset and summer window on universal time.")
def region_clock_fields_exact(workspace: Path) -> bool:
    keys = ["utc_offset_standard_sec", "utc_offset_summer_sec", "summer_window_utc", "zone"]
    return _safe(lambda: _all_zones(workspace, keys))


@criterion(description="Every zone report carries the exact reservation occurrence count and the exact subtracted measure.")
def region_reservation_figures_exact(workspace: Path) -> bool:
    return _safe(lambda: _all_zones(workspace, ["guard_occurrences", "guard_subtracted_area"]))


@criterion(description="Both segment reports carry the exact exclusive, shared and per zone measures, grant count and holder count.")
def segment_measures_exact(workspace: Path) -> bool:
    keys = ["area_exclusive", "area_shared", "zone_area_union",
            "assignments_measurable", "holders"]
    return _safe(lambda: _all_segments(workspace, keys))


@criterion(description="Both segment reports name the exact largest holders with their exact union measures.")
def segment_top_holders_exact(workspace: Path) -> bool:
    return _safe(lambda: _all_segments(workspace, ["top_holders"]))


@criterion(description="The layer decision tally, the alias figures, the parent chain depth and the reservation block of policy_audit.json, with the subtracted reservation measure of summary.json, are exact.")
def policy_audit_graph_and_layers_exact(workspace: Path) -> bool:
    keys = ["layer_governing_counts", "alias_fixpoint_depth", "alias_cycles",
            "parent_chain_max_depth", "guard"]
    return _safe(lambda: _shipped_match(workspace, "policy_audit.json", keys)
                 and _shipped_match(workspace, "summary.json", ["guard_subtracted_area"]))


@criterion(description="The duty block of policy_audit.json, including the largest single month deficits, and the duty figures of both segment reports are exact.")
def policy_audit_duty_block_exact(workspace: Path) -> bool:
    return _safe(lambda: _shipped_match(workspace, "policy_audit.json", ["duty"])
                 and _all_segments(workspace, ["duty_deficit_months", "duty_carry_end"]))


@criterion(description="The per file row tallies, the manifest mismatch list, the total row count, the withdrawn count, the zero span count and the zero span note in data_quality.json are exact.")
def data_quality_source_counts_exact(workspace: Path) -> bool:
    def check():
        want = _expect("visible")
        got = _delivered(workspace, "data_quality.json")
        if want is None or got is None:
            return False
        keys = ["source_counts", "manifest_mismatches", "rows_read_total", "retracted", "zero_span"]
        exp = want["data_quality.json"]
        return (_same(_pick(got, keys), _pick(exp, keys))
                and _same(got.get("notes", {}).get("ZERO_SPAN"), exp["notes"]["ZERO_SPAN"]))
    return _safe(check)


@criterion(description="The nine json documents and the derivation module are present, every document parses as an object, and every document is written with sorted keys and two space indentation.")
def artifacts_present_and_parse(workspace: Path) -> bool:
    def check():
        if not (workspace / "out" / SCRIPT).is_file():
            return False
        for name in DOCS:
            doc = _delivered(workspace, name)
            if not isinstance(doc, dict):
                return False
            text = _delivered_text(workspace, name)
            if text is None or text.strip() != json.dumps(doc, sort_keys=True, indent=2):
                return False
        return True
    return _safe(check)


@criterion(description="No document carries a floating point value and the segment reports both name their segment.")
def documents_are_integer_only_and_named(workspace: Path) -> bool:
    def check():
        for name in DOCS:
            doc = _delivered(workspace, name)
            if doc is None or _floats(doc):
                return False
        return all(_delivered(workspace, "segment_%s.json" % s).get("segment") == s
                   for s in SEGMENTS)
    return _safe(check)


# ---------------------------------------------------------------------------
# negative checks
# ---------------------------------------------------------------------------
@criterion(description="The union measure equals the measure summed with multiplicity, so overlap was treated as additive.")
def negative_area_union_equals_total_assigned(workspace: Path) -> bool:
    # shortcut: adding extent areas instead of measuring the covered set
    def check():
        got = _delivered(workspace, "summary.json")
        want = _expect("visible")
        if got is None or want is None:
            return False
        if want["summary.json"]["area_union"] == want["summary.json"]["area_total_assigned"]:
            return False
        if "area_union" not in got or "area_total_assigned" not in got:
            return False
        return got["area_union"] == got["area_total_assigned"]
    return _safe(check)


@criterion(description="A zone month breakdown is keyed by the universal calendar rather than the local calendar of the zone.")
def negative_region_months_use_utc_calendar(workspace: Path) -> bool:
    # shortcut: bucketing by universal months and skipping the zone offset
    def check():
        want = _expect("visible")
        if want is None:
            return False
        utc_keys = _utc_month_keys(want["summary.json"]["horizon"])
        for z in ZONES:
            name = "region_%s.json" % z
            got = _delivered(workspace, name)
            if got is None or not isinstance(got.get("month_area_union"), dict):
                continue
            right = sorted(want[name]["month_area_union"])
            if right == utc_keys:
                continue
            if sorted(got["month_area_union"]) == utc_keys:
                return True
        return False
    return _safe(check)


@criterion(description="The union measure matches a run that admits records recorded on or after the as of instant.")
def negative_measures_ignore_the_as_of_cutoff(workspace: Path) -> bool:
    # shortcut: reading every source row and skipping the visibility cutoff
    def check():
        got = _delivered(workspace, "summary.json")
        want = _expect("visible")
        if got is None or want is None:
            return False
        if _UNION_WITHOUT_CUTOFF == want["summary.json"]["area_union"]:
            return False
        return got.get("area_union") == _UNION_WITHOUT_CUTOFF
    return _safe(check)


@criterion(description="The subtracted reservation measure matches a run in which the reservation exceptions were never applied.")
def negative_reservation_exceptions_not_applied(workspace: Path) -> bool:
    # shortcut: expanding the recurrences and ignoring guard_exceptions.csv
    def check():
        got = _delivered(workspace, "summary.json")
        want = _expect("visible")
        if got is None or want is None:
            return False
        if want["summary.json"]["guard_subtracted_area"] == _GUARD_AREA_WITHOUT_EXCEPTIONS:
            return False
        return got.get("guard_subtracted_area") == _GUARD_AREA_WITHOUT_EXCEPTIONS
    return _safe(check)


def _reports_shipped_rules(workspace):
    here = _expect("visible")
    there = _expect("shifted")
    report = _run(workspace, "shifted")
    if here is None or there is None or not report["outputs"].get("policy_audit.json"):
        return False
    got = report["outputs"]["policy_audit.json"]
    keys = ["precedence_exception", "duplicate_tiebreak", "clock_keying"]
    mine = _pick(here["policy_audit.json"], keys)
    theirs = _pick(there["policy_audit.json"], keys)
    if _same(mine, theirs):
        return False
    return _same(_pick(got, keys), mine)


def _reports_shipped_figures(workspace):
    here = _expect("visible")
    got = _run(workspace, "edge")["outputs"].get("summary.json")
    if here is None or got is None:
        return False
    return _same(got, here["summary.json"])


@criterion(description="On a corpus the agent never saw the module reports the governing rules of the shipped corpus.")
def negative_hardcoded_sample_answers(workspace: Path) -> bool:
    # shortcut: writing the three derived rules as constants read off the shipped corpus
    return _safe(lambda: _reports_shipped_rules(workspace))


@criterion(description="The module writes the same summary for two different corpora, so its output does not depend on its input; charged only when neither shipped answer check fired.")
def negative_output_independent_of_the_corpus(workspace: Path) -> bool:
    # shortcut: emitting a fixed document set whatever corpus is supplied
    def check():
        if _safe(lambda: _reports_shipped_rules(workspace)) or _safe(lambda: _reports_shipped_figures(workspace)):
            return False
        a = _run(workspace, "shifted")
        b = _run(workspace, "edge")
        da = a["outputs"].get("summary.json")
        db = b["outputs"].get("summary.json")
        if da is None or db is None:
            return False
        return _same(da, db)
    return _safe(check)


@criterion(description="Given a boundary dense corpus the module reported the figures of the shipped corpus, so it read a fixed path; charged only when the shipped rules check did not fire.")
def negative_module_reads_a_fixed_corpus_path(workspace: Path) -> bool:
    # shortcut: hardwiring the shipped corpus location instead of using the first argument
    def check():
        if _safe(lambda: _reports_shipped_rules(workspace)):
            return False
        return _reports_shipped_figures(workspace)
    return _safe(check)


@criterion(description="The module created files outside the output directory it was given.")
def negative_module_writes_outside_the_output_directory(workspace: Path) -> bool:
    # shortcut: caching work in a scratch path outside the requested output directory
    return _safe(lambda: bool(_run(workspace, "shifted")["outside"]))


@criterion(description="The module changed the corpus it was given.")
def negative_module_mutates_the_corpus(workspace: Path) -> bool:
    # shortcut: rewriting the corpus in place rather than reading it
    return _safe(lambda: bool(_run(workspace, "shifted")["inputs_changed"]))


@criterion(description="The output directory holds files beyond the nine documents and the derivation module.")
def negative_output_directory_has_extra_files(workspace: Path) -> bool:
    # shortcut: leaving scratch output beside the graded artifacts
    def check():
        out = workspace / "out"
        if not out.is_dir():
            return False
        allowed = set(DOCS) | set([SCRIPT])
        return bool(set(p.name for p in out.iterdir()) - allowed)
    return _safe(check)


@criterion(description="A delivered document carries a key beyond the ones the output contract fixes for it.")
def negative_documents_carry_extra_keys(workspace: Path) -> bool:
    # shortcut: parking a closing message figure inside a graded document
    def check():
        want = _expect("visible")
        if want is None:
            return False
        for name in DOCS:
            got = _delivered(workspace, name)
            if not isinstance(got, dict):
                continue
            if set(got.keys()) - set(want[name].keys()):
                return True
        return False
    return _safe(check)


@criterion(description="The delivered documents contradict one another, so a measure the contract fixes by an identity disagrees with the parts it is built from.")
def negative_documents_contradict_each_other(workspace: Path) -> bool:
    # shortcut: assembling documents by hand or in separate passes instead of from one measurement
    def check():
        s = _delivered(workspace, "summary.json")
        p = _delivered(workspace, "policy_audit.json")
        q = _delivered(workspace, "data_quality.json")
        regions = dict((z, _delivered(workspace, "region_%s.json" % z)) for z in ZONES)
        segments = dict((g, _delivered(workspace, "segment_%s.json" % g)) for g in SEGMENTS)
        claims = [
            s["area_union"] == s["area_exclusive"] + s["area_shared"],
            s["area_excess"] == s["area_total_assigned"] - s["area_union"],
            sum(s["zone_area_union"].values()) == s["area_union"],
            sum(s["zone_share_bp"].values()) == 10000,
            sum(s["segment_share_bp"].values()) == 10000,
            s["guard_subtracted_area"] == p["guard"]["subtracted_area"],
            s["assignments_total"] == q["assignments_total"],
            s["horizon"]["as_of"] == p["as_of"],
            q["zero_span"] == q["notes"]["ZERO_SPAN"],
            p["parent_rejects"] == dict((c, q["rejects"][c]) for c in p["parent_rejects"]),
            sum(r["guard_subtracted_area"] for r in regions.values()) == p["guard"]["subtracted_area"],
            sum(r["guard_occurrences"] for r in regions.values()) == p["guard"]["occurrences"],
            sum(g["duty_deficit_months"] for g in segments.values()) == p["duty"]["months_in_deficit"],
            sum(g["duty_carry_end"] for g in segments.values()) == p["duty"]["carry_forward_end"],
        ]
        for zone, r in regions.items():
            claims.append(r["area_union"] == r["area_exclusive"] + r["area_shared"])
            claims.append(r["area_excess"] == r["area_total_assigned"] - r["area_union"])
            claims.append(sum(r["month_area_union"].values()) == r["area_union"])
            claims.append(sum(r["band_area_union"].values()) == r["area_union"])
            claims.append(r["area_union"] == s["zone_area_union"][zone])
        for name, g in segments.items():
            claims.append(g["area_union"] == g["area_exclusive"] + g["area_shared"])
            claims.append(g["area_union"] == s["segment_area_union"][name])
            claims.append(sum(g["zone_area_union"].values()) == g["area_union"])
        return not all(claims)
    return _safe(check)


@criterion(description="The delivered derivation module imports a module from outside the python standard library.")
def negative_module_imports_outside_the_standard_library(workspace: Path) -> bool:
    # shortcut: reaching for a third party package the contract rules out
    def check():
        source = _delivered_text(workspace, SCRIPT)
        if source is None:
            return False
        tree = ast.parse(source)
        roots = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                roots.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                roots.add(node.module.split(".")[0])
        return bool(roots - set(sys.stdlib_module_names))
    return _safe(check)


criteria.summary_core_measures_exact(weight=5)
criteria.summary_shares_and_ratio_exact(weight=5)
criteria.policy_withheld_rules_exact(weight=5)
criteria.region_month_and_band_breakdown_exact(weight=5)
criteria.data_quality_rejects_and_notes_exact(weight=5)
criteria.script_reproduces_the_shifted_corpus(weight=5)
criteria.script_reproduces_the_edge_corpus(weight=5)
criteria.summary_counts_exact(weight=3)
criteria.region_headline_measures_exact(weight=3)
criteria.region_excess_charge_top_exact(weight=3)
criteria.region_clock_fields_exact(weight=3)
criteria.region_reservation_figures_exact(weight=3)
criteria.segment_measures_exact(weight=3)
criteria.segment_top_holders_exact(weight=3)
criteria.policy_audit_graph_and_layers_exact(weight=3)
criteria.policy_audit_duty_block_exact(weight=3)
criteria.data_quality_source_counts_exact(weight=3)
criteria.artifacts_present_and_parse(weight=1)
criteria.documents_are_integer_only_and_named(weight=1)
criteria.negative_hardcoded_sample_answers(weight=-5)
criteria.negative_area_union_equals_total_assigned(weight=-3)
criteria.negative_region_months_use_utc_calendar(weight=-3)
criteria.negative_measures_ignore_the_as_of_cutoff(weight=-3)
criteria.negative_reservation_exceptions_not_applied(weight=-3)
criteria.negative_output_independent_of_the_corpus(weight=-3)
criteria.negative_module_reads_a_fixed_corpus_path(weight=-3)
criteria.negative_module_writes_outside_the_output_directory(weight=-1)
criteria.negative_module_mutates_the_corpus(weight=-1)
criteria.negative_output_directory_has_extra_files(weight=-1)
criteria.negative_documents_carry_extra_keys(weight=-1)
criteria.negative_documents_contradict_each_other(weight=-3)
criteria.negative_module_imports_outside_the_standard_library(weight=-1)
