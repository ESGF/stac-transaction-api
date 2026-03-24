CREATE STREAM stac_events_flat AS
  SELECT
    metadata->event_id AS event_id,
    metadata->time AS event_time,
    metadata->request_id AS request_id,
    data->payload->collection_id AS collection_id,
    data->payload->item->id AS item_id,
    data->payload->item->`PROPERTIES`->start_datetime AS start_datetime,
    data->payload->item->`PROPERTIES`->end_datetime AS end_datetime,
    data->payload->item->`PROPERTIES`->cmip6_activity_id AS activity_id,
    data->payload->item->`PROPERTIES`->cmip6_experiment_id AS experiment_id,
    data->payload->item->`PROPERTIES`->cmip6_institution_id AS institution_id,
    data->payload->item->`PROPERTIES`->cmip6_variable AS variable,
    data->payload->item->`PROPERTIES`->cmip6_frequency AS frequency,
    data->payload->item->`PROPERTIES`->project AS project,
    data->payload->item->bbox AS bbox
  FROM stac_events
  EMIT CHANGES;