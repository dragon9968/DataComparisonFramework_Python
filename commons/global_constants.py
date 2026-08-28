import os
from pathlib import Path

class GlobalConstants:
    # Get the project root path (DataComparisonFramework_Python directory)
    PROJECT_PATH = Path(__file__).parent.parent.resolve()
    
    # Define resource paths
    CONFIG_PATH = os.path.join(PROJECT_PATH, "resources", "configs")
    TEST_DATA_PATH = os.path.join(PROJECT_PATH, "resources", "test-data")
    OUTPUT_PATH = os.path.join(PROJECT_PATH, "test-output")
    REPORT_PATH = OUTPUT_PATH

# Default file configuration constants
    DEFAULT_SOURCE_FILE = "data_processed.xlsx"
    DEFAULT_TARGET_FILE = "data_extracted.xlsx"

    @classmethod
    def get_all_module_names(cls) -> list:
        """🔍 Automatically scan all .json files in resources/configs for module names."""
        if not os.path.exists(cls.CONFIG_PATH):
            return []
            
        modules = [
            os.path.splitext(f)[0] 
            for f in os.listdir(cls.CONFIG_PATH) 
            if f.endswith(".json")
        ]
        return modules if modules else ["NO_MODULE_FOUND"]
    
# Run a path check
if __name__ == "__main__":
    print(f"📌 Project Path: {GlobalConstants.PROJECT_PATH}")
    print(f"📌 Config Path:  {GlobalConstants.CONFIG_PATH}")