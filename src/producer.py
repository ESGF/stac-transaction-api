from abc import ABC, abstractmethod
import attr
from confluent_kafka import Producer


@attr.s
class BaseProducer(ABC):
    @abstractmethod
    def produce(self, topic, message):
        pass


class StdoutProducer(BaseProducer):
    def produce(self, topic, message):
        print(message)


class KafkaProducer(BaseProducer):
    def __init__(self, config):
        self.producer = Producer(config)
        print("KafkaProducer initialized")

    def produce(self, topic, key, value):
        delivery_reports = []

        def delivery_report(err, msg):
            if err is not None:
                print(f"Delivery failed for message {msg.key()}: {err}")
            else:
                print(f"Message {msg.key()} successfully delivered to {msg.topic()} [{msg.partition()}] at offset {msg.offset()}")
            delivery_reports.append((err, msg))

        self.producer.produce(topic=topic, key=key, value=value, callback=delivery_report)
        self.producer.flush()
        return delivery_reports
