from pydantic import BaseModel

class ColumnMapping(BaseModel):
    source_column: str
    target_column: str
    rule_type: str = "DIRECT"
    is_key: bool = False