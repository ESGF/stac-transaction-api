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
            item STRUCT<
                id VARCHAR,
                type VARCHAR,
                collection VARCHAR,
                start_datetime VARCHAR,
                `PROPERTIES` STRUCT<
                    title VARCHAR,
                    version VARCHAR
                >
            >
        >
    >
)
WITH (KAFKA_TOPIC='esgfng', VALUE_FORMAT='JSON');