CREATE STREAM esgfng_stream (
    metadata STRUCT<
        auth STRUCT<
            requester_data STRUCT<
                client_id VARCHAR,
                iss VARCHAR,
                sub VARCHAR,
                username VARCHAR,
                email VARCHAR
            >
        >
    >,
    data STRUCT<
        payload STRUCT<
            collection_id VARCHAR,
            method VARCHAR,
            item STRUCT<
                id VARCHAR,
                type VARCHAR,
                collection VARCHAR,
                `PROPERTIES` STRUCT<
                    version VARCHAR
                >
            >
        >
    >
)
WITH (KAFKA_TOPIC='esgfng', VALUE_FORMAT='JSON');