from typing import List, Optional, Union, Dict
from pydantic import BaseModel, ConfigDict, Field, AliasChoices
from commons.global_constants import GlobalConstants
from models.column_mapping import ColumnMapping

class ModuleConfig(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    module_name: str = Field(validation_alias=AliasChoices("moduleName", "module_name"))
    
    # Use defaults from GlobalConstants instead of hard-coded strings
    source_file: str = Field(
        default=GlobalConstants.DEFAULT_SOURCE_FILE, 
        validation_alias=AliasChoices("sourceFile", "source_file")
    )
    target_file: str = Field(
        default=GlobalConstants.DEFAULT_TARGET_FILE, 
        validation_alias=AliasChoices("targetFile", "target_file")
    )
    
    expected_sheet_name: Optional[str] = Field(default=None, validation_alias=AliasChoices("expectedSheetName", "expected_sheet_name"))
    actual_sheet_name: Optional[str] = Field(default=None, validation_alias=AliasChoices("actualSheetName", "actual_sheet_name"))
    
    key_columns: Union[str, List[str], None] = Field(default=None, validation_alias=AliasChoices("keyColumns", "key_columns"))
    compare_columns: List[str] = Field(default=[], validation_alias=AliasChoices("compareColumns", "compare_columns"))
    mappings: List[ColumnMapping] = Field(default=[], validation_alias=AliasChoices("mappings", "columnMappings", "column_mappings"))

    # ➕ Load valueMappings from JSON
    value_mappings: Dict[str, Dict[str, str]] = Field(
        default={}, 
        validation_alias=AliasChoices("valueMappings", "value_mappings")
    )