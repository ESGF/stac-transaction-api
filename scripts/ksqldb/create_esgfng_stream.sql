-- Create stream for STAC metadata events
CREATE STREAM stac_events (
  metadata STRUCT<
    auth STRUCT<
      auth_policy_id VARCHAR,
      requester_data STRUCT<
        client_id VARCHAR,
        iss VARCHAR,
        sub VARCHAR
      >
    >,
    event_id VARCHAR,
    publisher STRUCT<
      package VARCHAR,
      version VARCHAR
    >,
    request_id VARCHAR,
    time VARCHAR,
    schema_version VARCHAR
  >,
  data STRUCT<
    type VARCHAR,
    payload STRUCT<
      method VARCHAR,
      collection_id VARCHAR,
      item STRUCT<
        type VARCHAR,
        stac_version VARCHAR,
        stac_extensions ARRAY<VARCHAR>,
        id VARCHAR,
        geometry STRUCT<
          type VARCHAR,
          coordinates ARRAY<ARRAY<ARRAY<VARCHAR>>>
        >,
        bbox ARRAY<VARCHAR>,
        collection VARCHAR,
        links ARRAY<STRUCT<
          rel VARCHAR,
          type VARCHAR,
          href VARCHAR
        >>,
        `PROPERTIES` STRUCT<
          datetime VARCHAR,
          start_datetime VARCHAR,
          end_datetime VARCHAR,
          access ARRAY<VARCHAR>,
          pid VARCHAR,
          project VARCHAR,
          version VARCHAR,
          retracted BOOLEAN,
          cmip6_activity_id VARCHAR,
          cmip6_cf_standard_name VARCHAR,
          cmip6_citation_url VARCHAR,
          cmip6_data_specs_version VARCHAR,
          cmip6_experiment_id VARCHAR,
          cmip6_experiment_title VARCHAR,
          cmip6_frequency VARCHAR,
          cmip6_further_info_url VARCHAR,
          cmip6_grid VARCHAR,
          cmip6_grid_label VARCHAR,
          cmip6_institution_id VARCHAR,
          cmip6_member_id VARCHAR,
          cmip6_mip_era VARCHAR,
          cmip6_nominal_resolution VARCHAR,
          cmip6_product VARCHAR,
          cmip6_realm ARRAY<VARCHAR>,
          cmip6_source_id VARCHAR,
          cmip6_source_type ARRAY<VARCHAR>,
          cmip6_table_id VARCHAR,
          cmip6_variable VARCHAR,
          cmip6_variable_long_name VARCHAR,
          cmip6_variable_units VARCHAR,
          cmip6_variant_label VARCHAR
        >,
        assets MAP<VARCHAR, STRUCT<
          href VARCHAR,
          description VARCHAR,
          type VARCHAR,
          roles ARRAY<VARCHAR>,
          alternate_name VARCHAR,
          file_size BIGINT,
          file_checksum VARCHAR
        >>
      >
    >
  >
) WITH (
  KAFKA_TOPIC='stac-events',
  VALUE_FORMAT='JSON'
);