import os
from pathlib import Path

class FileUtils:

    @staticmethod
    def create_directory_if_not_exists(directory_path: str) -> None:
        """Create directory if it does not exist."""
        if not os.path.exists(directory_path):
            os.makedirs(directory_path, exist_ok=True)

    @staticmethod
    def resolve_file_path(folder_path: str, default_filename: str) -> str:
        """
        Dynamically resolve the file path in folder_path matching default_filename's stem
        across multiple supported extensions (.xlsx, .xlsm, .xls, .csv).
        """
        if not os.path.exists(folder_path):
            raise FileNotFoundError(f"❌ Test data folder not found at: {folder_path}")

        # Check exact file path first
        exact_path = os.path.join(folder_path, default_filename)
        if os.path.exists(exact_path):
            return exact_path

        # Search for files with matching base name and supported extensions
        stem = Path(default_filename).stem.lower()
        supported_extensions = [".xlsx", ".xlsm", ".xls", ".csv"]

        for file in os.listdir(folder_path):
            file_path = Path(file)
            if file_path.stem.lower() == stem and file_path.suffix.lower() in supported_extensions:
                return os.path.join(folder_path, file)

        raise FileNotFoundError(
            f"❌ Data file with base name '{Path(default_filename).stem}' "
            f"and supported extensions (.xlsx, .xlsm, .xls, .csv) not found at: {folder_path}"
        )