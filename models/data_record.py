from typing import Any, Dict
from pydantic import BaseModel, Field

class DataRecord(BaseModel):
    row_index: int
    data: Dict[str, Any] = Field(default_factory=dict)

    def get_value(self, column_name: str) -> Any:
        """Lấy giá trị của một cột trong dòng dữ liệu"""
        return self.data.get(column_name)

    def set_value(self, column_name: str, value: Any) -> None:
        """Gán giá trị cho một cột trong dòng dữ liệu"""
        self.data[column_name] = value