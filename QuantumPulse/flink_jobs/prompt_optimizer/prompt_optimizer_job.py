from pyflink.common import WatermarkStrategy, Row
from pyflink.common.typeinfo import Types
from pyflink.datastream import StreamExecutionEnvironment
from pyflink.datastream.connectors.pulsar import PulsarSource, PulsarSink, PulsarSerializationSchema, PulsarDeserializationSchema
import json

class JsonDeserializationSchema(PulsarDeserializationSchema):
    def deserialize(self, message):
        # A simple JSON deserializer
        return Row(json.loads(message.data()))

class JsonSerializerSchema(PulsarSerializationSchema):
    def serialize(self, element, timestamp):
        # A simple JSON serializer
        return json.dumps(element).encode('utf-8')

def prompt_optimizer_job():
    env = StreamExecutionEnvironment.get_execution_environment()
    # Replace with actual configuration values from the job submission
    service_url = "pulsar://localhost:6650"
    admin_url = "http://localhost:8080"
    input_topic = "persistent://public/default/inference-requests"
    output_topic = "persistent://public/default/preprocessed-requests"

    pulsar_source = PulsarSource.builder() \
        .set_service_url(service_url) \
        .set_admin_url(admin_url) \
        .set_start_cursor_from_latest() \
        .set_topics(input_topic) \
        .set_deserialization_schema(JsonDeserializationSchema()) \
        .set_subscription_name("prompt-optimizer-sub") \
        .build()

    pulsar_sink = PulsarSink.builder() \
        .set_service_url(service_url) \
        .set_admin_url(admin_url) \
        .set_topic_name(output_topic) \
        .set_serialization_schema(JsonSerializerSchema()) \
        .build()

    # DataStream pipeline
    ds = env.from_source(pulsar_source, WatermarkStrategy.no_watermarks(), "PulsarSource")
    
    # Simple transformation: log and pass through
    # A real job would perform cleaning, tokenization, etc.
    def optimize(row):
        print(f"Optimizing request: {row}")
        # Add a dummy field to show transformation
        row['optimized'] = True
        return row

    optimized_ds = ds.map(optimize, output_type=Types.ROW([
        Types.STRING(), # request_id
        Types.STRING(), # reply_to_topic
        Types.STRING(), # prompt
        Types.STRING(), # model
        Types.BOOLEAN(),# stream
        Types.STRING(), # conversation_id
        Types.MAP(Types.STRING(), Types.STRING()), # metadata
        Types.BOOLEAN() # optimized
    ]))
    
    optimized_ds.sink_to(pulsar_sink)

    env.execute("Prompt Optimizer Job")

if __name__ == '__main__':
    prompt_optimizer_job() 