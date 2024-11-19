CREATE STREAM esgfng_stream_flat WITH (KAFKA_TOPIC='esgfng_flat', VALUE_FORMAT='JSON') AS
SELECT  
        data->payload->item->id AS id PRIMARY KEY,
        metadata->auth->requester_data->client_id AS client_id,
        metadata->auth->requester_data->iss AS iss,
        metadata->auth->requester_data->sub AS sub,
        metadata->auth->requester_data->username AS username,
        metadata->auth->requester_data->email AS email,
        data->payload->item->type AS type, 
        data->payload->item->collection AS collection, 
        data->payload->item->`PROPERTIES`->title AS title, 
        data->payload->item->`PROPERTIES`->version AS version
FROM esgfng_stream;