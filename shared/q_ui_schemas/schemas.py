from pydantic import BaseModel, Field
from typing import List, Dict, Any, Literal, Union

class UITable(BaseModel):
    ui_component: Literal["table"] = "table"
    headers: List[str]
    rows: List[Dict[str, Any]]

class UIForm(BaseModel):
    ui_component: Literal["form"] = "form"
    schema: Dict[str, Any]

# A Union of all possible UI components can be created for type hinting
UIComponentModel = Union[UITable, UIForm] 