from pyflink.common import WatermarkStrategy, Row
from pyflink.common.typeinfo import Types
from pyflink.datastream import StreamExecutionEnvironment, ProcessFunction
from pyflink.datastream.connectors.pulsar import PulsarSource, PulsarSink, PulsarSerializationSchema, PulsarDeserializationSchema, TopicRouter
import json

class JsonDeserializationSchema(PulsarDeserializationSchema):
    def deserialize(self, message):
        return Row(json.loads(message.data()))

class JsonSerializerSchema(PulsarSerializationSchema):
    def serialize(self, element, timestamp):
        # We need to convert the Row object to a dict first
        return json.dumps(dict(element)).encode('utf-8')

class DynamicTopicRouter(TopicRouter):
    def route(self, element, topic_name):
        # The 'topic_name' here is the base output topic from the sink config.
        # We derive the final topic from the element itself.
        return element.target_topic # Accessing by attribute

class RoutingProcessFunction(ProcessFunction):
    def process_element(self, value, ctx):
        # Basic routing logic:
        # If the prompt contains "code", route to model-b. Otherwise, model-a.
        # A real implementation would be much more sophisticated.
        prompt = value.prompt.lower()
        if "code" in prompt or "python" in prompt or "javascript" in prompt:
            model = "model-b"
        else:
            model = "model-a"
        
        # Assume a simple shard assignment for this example
        shard = "shard-1"
        
        # The base output topic configured in the PulsarSink
        base_output_topic = "persistent://public/default/routed-"
        target_topic = f"{base_output_topic}{model}-{shard}"
        
        # Create a new Row object with the additional fields
        output_row = Row(
            request_id=value.request_id,
            reply_to_topic=value.reply_to_topic,
            prompt=value.prompt,
            model=value.model,
            stream=value.stream,
            conversation_id=value.conversation_id,
            metadata=value.metadata,
            optimized=value.optimized,
            target_shard=shard,
            target_topic=target_topic
        )
        yield output_row

def dynamic_router_job():
    env = StreamExecutionEnvironment.get_execution_environment()
    service_url = "pulsar://localhost:6650"
    admin_url = "http://localhost:8080"
    input_topic = "persistent://public/default/preprocessed-requests"
    output_topic_base = "persistent://public/default/routed-"

    pulsar_source = PulsarSource.builder() \
        .set_service_url(service_url) \
        .set_admin_url(admin_url) \
        .set_start_cursor_from_latest() \
        .set_topics(input_topic) \
        .set_deserialization_schema(JsonDeserializationSchema()) \
        .set_subscription_name("dynamic-router-sub") \
        .build()

    pulsar_sink = PulsarSink.builder() \
        .set_service_url(service_url) \
        .set_admin_url(admin_url) \
        .set_topic_name(output_topic_base) \
        .set_serialization_schema(JsonSerializerSchema()) \
        .set_topic_router(DynamicTopicRouter()) \
        .build()

    ds = env.from_source(pulsar_source, WatermarkStrategy.no_watermarks(), "PulsarSource")
    
    # Define the output type for the process function
    output_type_info = Types.ROW_NAMED(
        ['request_id', 'reply_to_topic', 'prompt', 'model', 'stream', 'conversation_id', 'metadata', 'optimized', 'target_shard', 'target_topic'],
        [Types.STRING(), Types.STRING(), Types.STRING(), Types.STRING(), Types.BOOLEAN(), Types.STRING(), Types.MAP(Types.STRING(), Types.STRING()), Types.BOOLEAN(), Types.STRING(), Types.STRING()]
    )
    
    routed_ds = ds.process(RoutingProcessFunction(), output_type=output_type_info)

    routed_ds.sink_to(pulsar_sink)

    env.execute("Dynamic Router Job")

if __name__ == '__main__':
    dynamic_router_job() 