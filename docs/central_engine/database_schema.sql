-- EcoRadar logical project schema.
-- Target container: one GeoPackage per project for EcoRadar 0.1.
-- Geometry columns should be created through GeoPackage-aware libraries.

CREATE TABLE IF NOT EXISTS study_area (
  id TEXT PRIMARY KEY,
  site_name TEXT NOT NULL,
  municipality TEXT,
  comarca TEXT,
  space_type TEXT NOT NULL,
  diagnostic_objective TEXT NOT NULL,
  boundary_source TEXT NOT NULL,
  crs TEXT NOT NULL,
  area_ha REAL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS land_cover (
  id TEXT PRIMARY KEY,
  source_id TEXT NOT NULL,
  class_code TEXT,
  class_name TEXT NOT NULL,
  area_ha REAL,
  percent_area REAL,
  data_date TEXT,
  resolution TEXT,
  quality_notes TEXT
);

CREATE TABLE IF NOT EXISTS habitats (
  id TEXT PRIMARY KEY,
  source_id TEXT NOT NULL,
  habitat_code TEXT,
  habitat_name TEXT NOT NULL,
  is_hic INTEGER DEFAULT 0,
  is_priority_hic INTEGER DEFAULT 0,
  sensitivity_level TEXT,
  degradation_status TEXT,
  restoration_potential TEXT,
  area_ha REAL,
  data_date TEXT,
  quality_notes TEXT
);

CREATE TABLE IF NOT EXISTS sentinel_indices (
  id TEXT PRIMARY KEY,
  source_id TEXT NOT NULL,
  index_name TEXT NOT NULL,
  date_start TEXT NOT NULL,
  date_end TEXT NOT NULL,
  mean_value REAL,
  min_value REAL,
  max_value REAL,
  anomaly_value REAL,
  raster_path TEXT,
  resolution TEXT,
  quality_notes TEXT
);

CREATE TABLE IF NOT EXISTS species_records (
  id TEXT PRIMARY KEY,
  source_id TEXT NOT NULL,
  scientific_name TEXT NOT NULL,
  common_name TEXT,
  taxon_group TEXT,
  event_date TEXT,
  decimal_latitude REAL,
  decimal_longitude REAL,
  basis_of_record TEXT,
  identification_confidence TEXT,
  is_protected INTEGER DEFAULT 0,
  is_invasive INTEGER DEFAULT 0,
  is_indicator INTEGER DEFAULT 0,
  license TEXT,
  url TEXT,
  quality_notes TEXT
);

CREATE TABLE IF NOT EXISTS field_observations (
  id TEXT PRIMARY KEY,
  observation_date TEXT NOT NULL,
  observer TEXT NOT NULL,
  decimal_latitude REAL,
  decimal_longitude REAL,
  observation_type TEXT NOT NULL,
  species_or_element TEXT,
  habitat TEXT,
  certainty TEXT,
  associated_file TEXT,
  related_indicator TEXT,
  technical_comment TEXT,
  imported_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS human_pressure (
  id TEXT PRIMARY KEY,
  source_id TEXT NOT NULL,
  pressure_type TEXT NOT NULL,
  name TEXT,
  density_value REAL,
  length_m REAL,
  count_value INTEGER,
  conflict_level TEXT,
  data_date TEXT,
  quality_notes TEXT
);

CREATE TABLE IF NOT EXISTS water_points (
  id TEXT PRIMARY KEY,
  source_id TEXT NOT NULL,
  water_type TEXT NOT NULL,
  name TEXT,
  status TEXT,
  fauna_interest TEXT,
  data_date TEXT,
  quality_notes TEXT
);

CREATE TABLE IF NOT EXISTS fire_risk (
  id TEXT PRIMARY KEY,
  source_id TEXT NOT NULL,
  risk_factor TEXT NOT NULL,
  raw_value REAL,
  class_value TEXT,
  data_date TEXT,
  quality_notes TEXT
);

CREATE TABLE IF NOT EXISTS climate_context (
  id TEXT PRIMARY KEY,
  source_id TEXT NOT NULL,
  variable_name TEXT NOT NULL,
  date_start TEXT,
  date_end TEXT,
  raw_value REAL,
  unit TEXT,
  anomaly_value REAL,
  quality_notes TEXT
);

CREATE TABLE IF NOT EXISTS management_actions (
  id TEXT PRIMARY KEY,
  action_type TEXT NOT NULL,
  target_area TEXT,
  problem_statement TEXT NOT NULL,
  expected_ecological_benefit TEXT,
  cost_complexity TEXT,
  priority_level TEXT,
  verification_indicator TEXT,
  notes TEXT
);

CREATE TABLE IF NOT EXISTS indicators (
  id TEXT PRIMARY KEY,
  profile TEXT NOT NULL,
  indicator_name TEXT NOT NULL,
  raw_value REAL,
  raw_unit TEXT,
  normalized_value REAL,
  level TEXT,
  confidence TEXT,
  source_mode TEXT,
  source_ids TEXT,
  recommendation_id TEXT,
  calculated_at TEXT,
  quality_notes TEXT
);

CREATE TABLE IF NOT EXISTS recommendations (
  id TEXT PRIMARY KEY,
  priority_rank INTEGER,
  where_to_act TEXT NOT NULL,
  reason TEXT NOT NULL,
  problem TEXT NOT NULL,
  recommended_action TEXT NOT NULL,
  cost_complexity TEXT,
  expected_ecological_benefit TEXT,
  verification_indicator TEXT,
  confidence TEXT,
  source_ids TEXT
);

CREATE TABLE IF NOT EXISTS source_downloads (
  id TEXT PRIMARY KEY,
  source_id TEXT NOT NULL,
  downloaded_at TEXT NOT NULL,
  official_url TEXT NOT NULL,
  query_fingerprint TEXT NOT NULL,
  raw_output_path TEXT,
  processed_output_path TEXT,
  resolution_or_scale TEXT,
  crs TEXT,
  license TEXT,
  data_quality_notes TEXT,
  UNIQUE(source_id, query_fingerprint)
);

