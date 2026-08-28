from typing import Any, Dict
from pydantic import BaseModel, Field

class DataRecord(BaseModel):
    row_index: int
    data: Dict[str, Any] = Field(default_factory=dict)

    def get_value(self, column_name: str) -> Any:
        """Get the value of a column in the data row."""
        return self.data.get(column_name)

    def set_value(self, column_name: str, value: Any) -> None:
        """Set the value of a column in the data row."""
        self.data[column_name] = value