from pydantic import BaseModel, Field
from typing import List, Dict, Any, Literal

class UITable(BaseModel):
    ui_component: Literal["table"] = "table"
    headers: List[str]
    rows: List[Dict[str, Any]]

# A Union of all possible UI components can be created for type hinting
UIComponentModel = UITable 