import os
import json
from commons.global_constants import GlobalConstants
from models.module_config import ModuleConfig

class ConfigReader:

    @staticmethod
    def get_all_module_names() -> list:
        """🔍 Quét toàn bộ file .json trong resources/configs để lấy danh sách Module"""
        if not os.path.exists(GlobalConstants.CONFIG_PATH):
            return []

        modules = [
            os.path.splitext(f)[0] 
            for f in os.listdir(GlobalConstants.CONFIG_PATH) 
            if f.endswith(".json")
        ]
        return modules if modules else ["NO_MODULE_FOUND"]

    @staticmethod
    def load_module_config(config_name: str) -> ModuleConfig:
        file_path = os.path.join(GlobalConstants.CONFIG_PATH, f"{config_name}.json")
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"❌ Không tìm thấy file config tại: {file_path}")

        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        return ModuleConfig(**data)