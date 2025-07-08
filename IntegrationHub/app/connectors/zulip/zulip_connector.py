import zulip
import re
from typing import Dict, Any

def _get_value_from_context(key: str, context: Dict[str, Any]):
    """
    Retrieves a nested value from a dictionary using dot notation.
    e.g., key='user.name' -> context['user']['name']
    """
    try:
        for k in key.split('.'):
            context = context[k]
        return context
    except (KeyError, TypeError):
        return None

def _render_template(template_string: str, context: Dict[str, Any]) -> str:
    """
    Renders a simple template string with values from a context dictionary.
    Replaces all occurrences of `{{ key.path }}` with the corresponding value.
    """
    # Find all placeholders like {{ key.path }}
    placeholders = re.findall(r"\{\{([\w\s\.]*)\}\}", template_string)
    
    for placeholder in placeholders:
        key = placeholder.strip()
        value = _get_value_from_context(key, context)
        # Replace the placeholder with the value, handle non-string values
        template_string = template_string.replace(f"{{{{ {key} }}}}", str(value) if value is not None else "")
        
    return template_string

class ZulipSink:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.client = None

    def write(self, data: Dict[str, Any]):
        """
        Sends a message to the configured Zulip stream and topic.
        The message content is templated with data from the `data` context.
        """
        self.client = zulip.Client(
            email=self.config.get("email"),
            api_key=self.config.get("api_key"),
            site=self.config.get("site")
        )

        message_template = self.config.get("content", "A flow step was triggered.")
        message_content = _render_template(message_template, data)

        request = {
            "type": "stream",
            "to": self.config.get("stream"),
            "topic": self.config.get("topic"),
            "content": message_content,
        }

        result = self.client.send_message(request)
        if result.get("result") != "success":
            raise RuntimeError(f"Failed to send message to Zulip: {result.get('msg')}")

def get_connector(*args, **kwargs):
    return ZulipSink(*args, **kwargs)
