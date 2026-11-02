# Notes left with the retired planner

The retired planner was written against an earlier release process and was
believed to do the following. It is recorded here because the next build has to
reproduce what the handbook says, not what this note says, and the two are not
the same.

- It read the component register straight through and kept the last row it saw
  for each component, on the assumption that corrections are appended.
- It costed a unit by multiplying the base cost by every applicable fraction in
  one expression and rounding the result once at the end.
- It took the pool budgets out of the capacity workbook as plain numbers.
- It ranked the dirty units by priority class and admitted them one at a time
  until the pool ran out.
- It broke a dependency cycle at the first edge it came across in the group.
- It took each component's most preferred version that was not withdrawn.
- It treated every declared optional dependency as live.
- It built the contract digest over every interface a component consumes.
- It read the per component cost column that the register carries beside the
  base cost.

Three symptoms were reported against the last candidate and never explained:
the pool summaries did not add up against the workbook, two services shipped
with client versions their own interfaces reject, and a unit that nothing had
touched was rebuilt on one target and reused on another.

## Reported symptom log

| release | unit | symptom | state |
| --- | --- | --- | --- |
| R-PREV | C-0001:T-01 | pool summary does not reconcile against the workbook | open |
| R-PREV | C-0008:T-02 | client version rejected by its own interface | open |
| R-PREV | C-0015:T-03 | untouched unit rebuilt on one target only | open |
| R-PREV | C-0022:T-04 | deferral with no stated cause | open |
| R-PREV | C-0029:T-05 | cycle broken at a different edge than the group names | open |
| R-PREV | C-0036:T-06 | generated client missing from the candidate | open |
| R-PREV | C-0043:T-01 | cost lower than the previous release for the same unit | open |
| R-PREV | C-0050:T-02 | unit published although its review is held | open |
| R-PREV | C-0057:T-03 | pool summary does not reconcile against the workbook | open |
| R-PREV | C-0064:T-04 | client version rejected by its own interface | open |
| R-PREV | C-0071:T-05 | untouched unit rebuilt on one target only | open |
| R-PREV | C-0078:T-06 | deferral with no stated cause | open |
| R-PREV | C-0085:T-01 | cycle broken at a different edge than the group names | open |
| R-PREV | C-0092:T-02 | generated client missing from the candidate | open |
| R-PREV | C-0099:T-03 | cost lower than the previous release for the same unit | open |
| R-PREV | C-0106:T-04 | unit published although its review is held | open |
| R-PREV | C-0113:T-05 | pool summary does not reconcile against the workbook | open |
| R-PREV | C-0120:T-06 | client version rejected by its own interface | open |
| R-PREV | C-0127:T-01 | untouched unit rebuilt on one target only | open |
| R-PREV | C-0134:T-02 | deferral with no stated cause | open |
| R-PREV | C-0141:T-03 | cycle broken at a different edge than the group names | open |
| R-PREV | C-0148:T-04 | generated client missing from the candidate | open |
| R-PREV | C-0155:T-05 | cost lower than the previous release for the same unit | open |
| R-PREV | C-0162:T-06 | unit published although its review is held | open |
| R-PREV | C-0169:T-01 | pool summary does not reconcile against the workbook | open |
| R-PREV | C-0176:T-02 | client version rejected by its own interface | open |
| R-PREV | C-0183:T-03 | untouched unit rebuilt on one target only | open |
| R-PREV | C-0190:T-04 | deferral with no stated cause | open |
| R-PREV | C-0197:T-05 | cycle broken at a different edge than the group names | open |
| R-PREV | C-0204:T-06 | generated client missing from the candidate | open |
| R-PREV | C-0211:T-01 | cost lower than the previous release for the same unit | open |
| R-PREV | C-0218:T-02 | unit published although its review is held | open |
| R-PREV | C-0225:T-03 | pool summary does not reconcile against the workbook | open |
| R-PREV | C-0232:T-04 | client version rejected by its own interface | open |
| R-PREV | C-0239:T-05 | untouched unit rebuilt on one target only | open |
| R-PREV | C-0006:T-06 | deferral with no stated cause | open |
| R-PREV | C-0013:T-01 | cycle broken at a different edge than the group names | open |
| R-PREV | C-0020:T-02 | generated client missing from the candidate | open |
| R-PREV | C-0027:T-03 | cost lower than the previous release for the same unit | open |
| R-PREV | C-0034:T-04 | unit published although its review is held | open |
| R-PREV | C-0041:T-05 | pool summary does not reconcile against the workbook | open |
| R-PREV | C-0048:T-06 | client version rejected by its own interface | open |
| R-PREV | C-0055:T-01 | untouched unit rebuilt on one target only | open |
| R-PREV | C-0062:T-02 | deferral with no stated cause | open |
| R-PREV | C-0069:T-03 | cycle broken at a different edge than the group names | open |
| R-PREV | C-0076:T-04 | generated client missing from the candidate | open |
| R-PREV | C-0083:T-05 | cost lower than the previous release for the same unit | open |
| R-PREV | C-0090:T-06 | unit published although its review is held | open |
| R-PREV | C-0097:T-01 | pool summary does not reconcile against the workbook | open |
| R-PREV | C-0104:T-02 | client version rejected by its own interface | open |
| R-PREV | C-0111:T-03 | untouched unit rebuilt on one target only | open |
| R-PREV | C-0118:T-04 | deferral with no stated cause | open |
| R-PREV | C-0125:T-05 | cycle broken at a different edge than the group names | open |
| R-PREV | C-0132:T-06 | generated client missing from the candidate | open |
| R-PREV | C-0139:T-01 | cost lower than the previous release for the same unit | open |
| R-PREV | C-0146:T-02 | unit published although its review is held | open |
| R-PREV | C-0153:T-03 | pool summary does not reconcile against the workbook | open |
| R-PREV | C-0160:T-04 | client version rejected by its own interface | open |
| R-PREV | C-0167:T-05 | untouched unit rebuilt on one target only | open |
| R-PREV | C-0174:T-06 | deferral with no stated cause | open |
| R-PREV | C-0181:T-01 | cycle broken at a different edge than the group names | open |
| R-PREV | C-0188:T-02 | generated client missing from the candidate | open |
| R-PREV | C-0195:T-03 | cost lower than the previous release for the same unit | open |
| R-PREV | C-0202:T-04 | unit published although its review is held | open |
| R-PREV | C-0209:T-05 | pool summary does not reconcile against the workbook | open |
| R-PREV | C-0216:T-06 | client version rejected by its own interface | open |
| R-PREV | C-0223:T-01 | untouched unit rebuilt on one target only | open |
| R-PREV | C-0230:T-02 | deferral with no stated cause | open |
| R-PREV | C-0237:T-03 | cycle broken at a different edge than the group names | open |
| R-PREV | C-0004:T-04 | generated client missing from the candidate | open |
| R-PREV | C-0011:T-05 | cost lower than the previous release for the same unit | open |
| R-PREV | C-0018:T-06 | unit published although its review is held | open |
| R-PREV | C-0025:T-01 | pool summary does not reconcile against the workbook | open |
| R-PREV | C-0032:T-02 | client version rejected by its own interface | open |
| R-PREV | C-0039:T-03 | untouched unit rebuilt on one target only | open |
| R-PREV | C-0046:T-04 | deferral with no stated cause | open |
| R-PREV | C-0053:T-05 | cycle broken at a different edge than the group names | open |
| R-PREV | C-0060:T-06 | generated client missing from the candidate | open |
| R-PREV | C-0067:T-01 | cost lower than the previous release for the same unit | open |
| R-PREV | C-0074:T-02 | unit published although its review is held | open |
| R-PREV | C-0081:T-03 | pool summary does not reconcile against the workbook | open |
| R-PREV | C-0088:T-04 | client version rejected by its own interface | open |
| R-PREV | C-0095:T-05 | untouched unit rebuilt on one target only | open |
| R-PREV | C-0102:T-06 | deferral with no stated cause | open |
| R-PREV | C-0109:T-01 | cycle broken at a different edge than the group names | open |
| R-PREV | C-0116:T-02 | generated client missing from the candidate | open |
| R-PREV | C-0123:T-03 | cost lower than the previous release for the same unit | open |
| R-PREV | C-0130:T-04 | unit published although its review is held | open |
| R-PREV | C-0137:T-05 | pool summary does not reconcile against the workbook | open |
| R-PREV | C-0144:T-06 | client version rejected by its own interface | open |
| R-PREV | C-0151:T-01 | untouched unit rebuilt on one target only | open |
| R-PREV | C-0158:T-02 | deferral with no stated cause | open |
| R-PREV | C-0165:T-03 | cycle broken at a different edge than the group names | open |
| R-PREV | C-0172:T-04 | generated client missing from the candidate | open |
| R-PREV | C-0179:T-05 | cost lower than the previous release for the same unit | open |
| R-PREV | C-0186:T-06 | unit published although its review is held | open |
| R-PREV | C-0193:T-01 | pool summary does not reconcile against the workbook | open |
| R-PREV | C-0200:T-02 | client version rejected by its own interface | open |
| R-PREV | C-0207:T-03 | untouched unit rebuilt on one target only | open |
| R-PREV | C-0214:T-04 | deferral with no stated cause | open |
| R-PREV | C-0221:T-05 | cycle broken at a different edge than the group names | open |
| R-PREV | C-0228:T-06 | generated client missing from the candidate | open |
| R-PREV | C-0235:T-01 | cost lower than the previous release for the same unit | open |
| R-PREV | C-0002:T-02 | unit published although its review is held | open |
| R-PREV | C-0009:T-03 | pool summary does not reconcile against the workbook | open |
| R-PREV | C-0016:T-04 | client version rejected by its own interface | open |
| R-PREV | C-0023:T-05 | untouched unit rebuilt on one target only | open |
| R-PREV | C-0030:T-06 | deferral with no stated cause | open |
| R-PREV | C-0037:T-01 | cycle broken at a different edge than the group names | open |
| R-PREV | C-0044:T-02 | generated client missing from the candidate | open |
| R-PREV | C-0051:T-03 | cost lower than the previous release for the same unit | open |
| R-PREV | C-0058:T-04 | unit published although its review is held | open |
| R-PREV | C-0065:T-05 | pool summary does not reconcile against the workbook | open |
| R-PREV | C-0072:T-06 | client version rejected by its own interface | open |
| R-PREV | C-0079:T-01 | untouched unit rebuilt on one target only | open |
| R-PREV | C-0086:T-02 | deferral with no stated cause | open |
| R-PREV | C-0093:T-03 | cycle broken at a different edge than the group names | open |
| R-PREV | C-0100:T-04 | generated client missing from the candidate | open |
| R-PREV | C-0107:T-05 | cost lower than the previous release for the same unit | open |
| R-PREV | C-0114:T-06 | unit published although its review is held | open |
| R-PREV | C-0121:T-01 | pool summary does not reconcile against the workbook | open |
| R-PREV | C-0128:T-02 | client version rejected by its own interface | open |
| R-PREV | C-0135:T-03 | untouched unit rebuilt on one target only | open |
| R-PREV | C-0142:T-04 | deferral with no stated cause | open |
| R-PREV | C-0149:T-05 | cycle broken at a different edge than the group names | open |
| R-PREV | C-0156:T-06 | generated client missing from the candidate | open |
| R-PREV | C-0163:T-01 | cost lower than the previous release for the same unit | open |
| R-PREV | C-0170:T-02 | unit published although its review is held | open |
| R-PREV | C-0177:T-03 | pool summary does not reconcile against the workbook | open |
| R-PREV | C-0184:T-04 | client version rejected by its own interface | open |
| R-PREV | C-0191:T-05 | untouched unit rebuilt on one target only | open |
| R-PREV | C-0198:T-06 | deferral with no stated cause | open |
| R-PREV | C-0205:T-01 | cycle broken at a different edge than the group names | open |
| R-PREV | C-0212:T-02 | generated client missing from the candidate | open |
| R-PREV | C-0219:T-03 | cost lower than the previous release for the same unit | open |
| R-PREV | C-0226:T-04 | unit published although its review is held | open |
| R-PREV | C-0233:T-05 | pool summary does not reconcile against the workbook | open |
| R-PREV | C-0240:T-06 | client version rejected by its own interface | open |
| R-PREV | C-0007:T-01 | untouched unit rebuilt on one target only | open |
| R-PREV | C-0014:T-02 | deferral with no stated cause | open |
| R-PREV | C-0021:T-03 | cycle broken at a different edge than the group names | open |
| R-PREV | C-0028:T-04 | generated client missing from the candidate | open |
| R-PREV | C-0035:T-05 | cost lower than the previous release for the same unit | open |
| R-PREV | C-0042:T-06 | unit published although its review is held | open |
| R-PREV | C-0049:T-01 | pool summary does not reconcile against the workbook | open |
| R-PREV | C-0056:T-02 | client version rejected by its own interface | open |
| R-PREV | C-0063:T-03 | untouched unit rebuilt on one target only | open |
| R-PREV | C-0070:T-04 | deferral with no stated cause | open |
| R-PREV | C-0077:T-05 | cycle broken at a different edge than the group names | open |
| R-PREV | C-0084:T-06 | generated client missing from the candidate | open |
| R-PREV | C-0091:T-01 | cost lower than the previous release for the same unit | open |
| R-PREV | C-0098:T-02 | unit published although its review is held | open |
| R-PREV | C-0105:T-03 | pool summary does not reconcile against the workbook | open |
| R-PREV | C-0112:T-04 | client version rejected by its own interface | open |
| R-PREV | C-0119:T-05 | untouched unit rebuilt on one target only | open |
| R-PREV | C-0126:T-06 | deferral with no stated cause | open |
| R-PREV | C-0133:T-01 | cycle broken at a different edge than the group names | open |
| R-PREV | C-0140:T-02 | generated client missing from the candidate | open |
| R-PREV | C-0147:T-03 | cost lower than the previous release for the same unit | open |
| R-PREV | C-0154:T-04 | unit published although its review is held | open |
| R-PREV | C-0161:T-05 | pool summary does not reconcile against the workbook | open |
| R-PREV | C-0168:T-06 | client version rejected by its own interface | open |
| R-PREV | C-0175:T-01 | untouched unit rebuilt on one target only | open |
| R-PREV | C-0182:T-02 | deferral with no stated cause | open |
| R-PREV | C-0189:T-03 | cycle broken at a different edge than the group names | open |
| R-PREV | C-0196:T-04 | generated client missing from the candidate | open |
| R-PREV | C-0203:T-05 | cost lower than the previous release for the same unit | open |
| R-PREV | C-0210:T-06 | unit published although its review is held | open |
| R-PREV | C-0217:T-01 | pool summary does not reconcile against the workbook | open |
| R-PREV | C-0224:T-02 | client version rejected by its own interface | open |
| R-PREV | C-0231:T-03 | untouched unit rebuilt on one target only | open |
| R-PREV | C-0238:T-04 | deferral with no stated cause | open |
| R-PREV | C-0005:T-05 | cycle broken at a different edge than the group names | open |
| R-PREV | C-0012:T-06 | generated client missing from the candidate | open |
| R-PREV | C-0019:T-01 | cost lower than the previous release for the same unit | open |
| R-PREV | C-0026:T-02 | unit published although its review is held | open |
| R-PREV | C-0033:T-03 | pool summary does not reconcile against the workbook | open |
| R-PREV | C-0040:T-04 | client version rejected by its own interface | open |
| R-PREV | C-0047:T-05 | untouched unit rebuilt on one target only | open |
| R-PREV | C-0054:T-06 | deferral with no stated cause | open |
| R-PREV | C-0061:T-01 | cycle broken at a different edge than the group names | open |
| R-PREV | C-0068:T-02 | generated client missing from the candidate | open |
| R-PREV | C-0075:T-03 | cost lower than the previous release for the same unit | open |
| R-PREV | C-0082:T-04 | unit published although its review is held | open |
| R-PREV | C-0089:T-05 | pool summary does not reconcile against the workbook | open |
| R-PREV | C-0096:T-06 | client version rejected by its own interface | open |
| R-PREV | C-0103:T-01 | untouched unit rebuilt on one target only | open |
| R-PREV | C-0110:T-02 | deferral with no stated cause | open |
| R-PREV | C-0117:T-03 | cycle broken at a different edge than the group names | open |
| R-PREV | C-0124:T-04 | generated client missing from the candidate | open |
| R-PREV | C-0131:T-05 | cost lower than the previous release for the same unit | open |
| R-PREV | C-0138:T-06 | unit published although its review is held | open |
| R-PREV | C-0145:T-01 | pool summary does not reconcile against the workbook | open |
| R-PREV | C-0152:T-02 | client version rejected by its own interface | open |
| R-PREV | C-0159:T-03 | untouched unit rebuilt on one target only | open |
| R-PREV | C-0166:T-04 | deferral with no stated cause | open |
| R-PREV | C-0173:T-05 | cycle broken at a different edge than the group names | open |
| R-PREV | C-0180:T-06 | generated client missing from the candidate | open |
| R-PREV | C-0187:T-01 | cost lower than the previous release for the same unit | open |
| R-PREV | C-0194:T-02 | unit published although its review is held | open |
| R-PREV | C-0201:T-03 | pool summary does not reconcile against the workbook | open |
| R-PREV | C-0208:T-04 | client version rejected by its own interface | open |
| R-PREV | C-0215:T-05 | untouched unit rebuilt on one target only | open |
| R-PREV | C-0222:T-06 | deferral with no stated cause | open |
| R-PREV | C-0229:T-01 | cycle broken at a different edge than the group names | open |
| R-PREV | C-0236:T-02 | generated client missing from the candidate | open |
| R-PREV | C-0003:T-03 | cost lower than the previous release for the same unit | open |
| R-PREV | C-0010:T-04 | unit published although its review is held | open |
| R-PREV | C-0017:T-05 | pool summary does not reconcile against the workbook | open |
| R-PREV | C-0024:T-06 | client version rejected by its own interface | open |
| R-PREV | C-0031:T-01 | untouched unit rebuilt on one target only | open |
| R-PREV | C-0038:T-02 | deferral with no stated cause | open |
| R-PREV | C-0045:T-03 | cycle broken at a different edge than the group names | open |
| R-PREV | C-0052:T-04 | generated client missing from the candidate | open |
| R-PREV | C-0059:T-05 | cost lower than the previous release for the same unit | open |
| R-PREV | C-0066:T-06 | unit published although its review is held | open |
