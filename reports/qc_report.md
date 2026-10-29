# Data quality report

Generated: 2026-10-29 09:18 UTC

## Table sizes

| Table | Rows |
|---|---|
| patient | 1,098 |
| outcome | 1,095 |
| specimen | 3,397 |
| slide | 3,108 |
| molecular_profile | 984 |
| mutation | 89,190 |

## Validation results

Each rule counts the rows that violate it. Errors must be zero; warnings are known data limitations; info rows describe coverage.

| ID | Status | Violations | Rule |
|---|---|---|---|
| E1 | PASS | 0 | Specimen barcode does not start with its patient barcode |
| E2 | PASS | 0 | Sample-type code does not match characters 14-15 of the barcode |
| E3 | PASS | 0 | Slide id does not match the patient and sample type of its specimen |
| E4 | PASS | 0 | Mutation sample differs from the sample of its molecular profile |
| E5 | PASS | 0 | Outcome event does not agree with patient vital status |
| E6 | PASS | 0 | Patient with diagnoses does not have exactly one index diagnosis |
| E7 | PASS | 0 | Mutation end position is before its start position |
| E8 | PASS | 0 | Mutation chromosome is not in the form chr1..chr22, chrX, chrY, chrM |
| E9 | PASS | 0 | Sample with more than one mutation profile |
| W1 | WARN | 3 | Patients with no survival outcome |
| W2 | PASS | 0 | Patients with no tumor specimen |
| W3 | WARN | 32 | Index diagnoses with missing stage |
| W4 | WARN | 3 | Index diagnoses with missing histology |
| W5 | WARN | 131 | Patients with no mutation data |
| W6 | PASS | 0 | Surplus duplicate mutation rows (same sample, gene, position, allele) |
| I1 | INFO | 3,108 | Slides not yet quality-checked (qc_status = 'unchecked') |
| I2 | INFO | 1,097 | Index diagnoses with no ER status recorded |
