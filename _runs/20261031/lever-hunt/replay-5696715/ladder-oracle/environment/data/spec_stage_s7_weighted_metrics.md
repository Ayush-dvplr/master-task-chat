# S7 Weighted Metrics

Compute weighted precision, recall and F-beta per stratum from weighted TP, FP,
FN. The OVERALL precision and recall are ratios of the weighted totals across
all weighted matches, and the overall F-beta is computed from those overall
figures - never by averaging per-stratum F-beta. The MACRO precision and recall
are weight-share-weighted means of the per-stratum figures.
