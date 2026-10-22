-- TCGA-BRCA integration schema
DROP TABLE IF EXISTS mutation, molecular_profile, slide, specimen,
    treatment, outcome, diagnosis, patient, ref_sample_type,
    ingestion_log CASCADE;

-- Lookup: TCGA sample-type codes (characters 14-15 of a barcode)
CREATE TABLE ref_sample_type (
    code        CHAR(2) PRIMARY KEY,
    description TEXT NOT NULL,
    is_tumor    BOOLEAN NOT NULL
);

INSERT INTO ref_sample_type (code, description, is_tumor) VALUES
    ('01', 'Primary Solid Tumor', TRUE),
    ('02', 'Recurrent Solid Tumor', TRUE),
    ('06', 'Metastatic', TRUE),
    ('10', 'Blood Derived Normal', FALSE),
    ('11', 'Solid Tissue Normal', FALSE);

-- One row per person
CREATE TABLE patient (
    patient_barcode TEXT PRIMARY KEY,           -- e.g. TCGA-A1-A0SB
    gdc_case_id     UUID UNIQUE,
    project_id      TEXT NOT NULL DEFAULT 'TCGA-BRCA',
    gender          TEXT,
    race            TEXT,
    ethnicity       TEXT,
    vital_status    TEXT CHECK (vital_status IN ('Alive', 'Dead')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Disease-level facts (a patient can in principle have several)
CREATE TABLE diagnosis (
    diagnosis_id           SERIAL PRIMARY KEY,
    patient_barcode        TEXT NOT NULL
        REFERENCES patient (patient_barcode) ON DELETE CASCADE,
    primary_diagnosis      TEXT,
    ajcc_pathologic_stage  TEXT,
    age_at_diagnosis_days  INTEGER CHECK (age_at_diagnosis_days >= 0),
    er_status              TEXT,
    pr_status              TEXT,
    her2_status            TEXT,
    pam50_subtype          TEXT
);

-- Treatments given for a diagnosis
CREATE TABLE treatment (
    treatment_id      SERIAL PRIMARY KEY,
    diagnosis_id      INTEGER NOT NULL
        REFERENCES diagnosis (diagnosis_id) ON DELETE CASCADE,
    treatment_type    TEXT,
    therapeutic_agent TEXT,
    days_to_start     INTEGER
);

-- Clean survival data: one row per patient
CREATE TABLE outcome (
    patient_barcode TEXT PRIMARY KEY
        REFERENCES patient (patient_barcode) ON DELETE CASCADE,
    os_time_days    INTEGER NOT NULL CHECK (os_time_days >= 0),
    os_event        SMALLINT NOT NULL CHECK (os_event IN (0, 1)),
    -- os_event = 1: died (time = days_to_death)
    -- os_event = 0: censored (time = days_to_last_follow_up)
    source_note     TEXT
);

-- A physical sample taken from a patient
CREATE TABLE specimen (
    sample_barcode  TEXT PRIMARY KEY,           -- e.g. TCGA-A1-A0SB-01A
    patient_barcode TEXT NOT NULL
        REFERENCES patient (patient_barcode) ON DELETE CASCADE,
    sample_type_code CHAR(2) NOT NULL
        REFERENCES ref_sample_type (code),
    gdc_sample_id   UUID
);

-- A scanned pathology slide from a sample
CREATE TABLE slide (
    slide_id        TEXT PRIMARY KEY,           -- slide submitter_id
    sample_barcode  TEXT NOT NULL
        REFERENCES specimen (sample_barcode) ON DELETE CASCADE,
    gdc_file_id     UUID UNIQUE,
    file_name       TEXT,
    file_size_bytes BIGINT CHECK (file_size_bytes >= 0),
    slide_type      TEXT,                       -- DX / TS / BS
    magnification   NUMERIC,
    width_px        INTEGER,
    height_px       INTEGER,
    tissue_fraction NUMERIC CHECK (tissue_fraction BETWEEN 0 AND 1),
    blur_score      NUMERIC,
    qc_status       TEXT CHECK (qc_status IN ('pass', 'fail', 'unchecked'))
        DEFAULT 'unchecked'
);

-- One molecular assay result file for a sample
CREATE TABLE molecular_profile (
    profile_id      SERIAL PRIMARY KEY,
    sample_barcode  TEXT NOT NULL
        REFERENCES specimen (sample_barcode) ON DELETE CASCADE,
    assay_type      TEXT NOT NULL CHECK (assay_type IN
        ('mutation', 'expression', 'copy_number', 'methylation')),
    gdc_file_id     UUID,
    file_name       TEXT,
    workflow        TEXT
);

-- Somatic mutations, one row per variant
CREATE TABLE mutation (
    mutation_id            BIGSERIAL PRIMARY KEY,
    profile_id             INTEGER NOT NULL
        REFERENCES molecular_profile (profile_id) ON DELETE CASCADE,
    sample_barcode         TEXT NOT NULL
        REFERENCES specimen (sample_barcode) ON DELETE CASCADE,
    hugo_symbol            TEXT NOT NULL,
    chromosome             TEXT,
    start_position         BIGINT,
    end_position           BIGINT,
    variant_classification TEXT,
    variant_type           TEXT,
    ref_allele             TEXT,
    tumor_allele           TEXT,
    hgvsp_short            TEXT
);

-- Provenance: what ran, when, how many rows
CREATE TABLE ingestion_log (
    run_id      SERIAL PRIMARY KEY,
    step        TEXT NOT NULL,
    source      TEXT,
    rows_in     INTEGER,
    rows_out    INTEGER,
    status      TEXT NOT NULL,
    message     TEXT,
    run_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Indexes on foreign keys and common filters
CREATE INDEX idx_diagnosis_patient   ON diagnosis (patient_barcode);
CREATE INDEX idx_specimen_patient    ON specimen (patient_barcode);
CREATE INDEX idx_slide_sample        ON slide (sample_barcode);
CREATE INDEX idx_profile_sample      ON molecular_profile (sample_barcode);
CREATE INDEX idx_mutation_sample     ON mutation (sample_barcode);
CREATE INDEX idx_mutation_gene       ON mutation (hugo_symbol);
