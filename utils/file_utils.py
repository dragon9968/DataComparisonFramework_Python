import os
import shutil

class FileUtils:
    @staticmethod
    def create_directory_if_not_exists(dir_path: str) -> None:
        """Tự động tạo thư mục nếu chưa tồn tại"""
        if not os.path.exists(dir_path):
            os.makedirs(dir_path, exist_ok=True)

    @staticmethod
    def clean_directory(dir_path: str) -> None:
        """Dọn dẹp xóa sạch các file cũ trong thư mục (dùng trước khi xuất report mới)"""
        if os.path.exists(dir_path):
            for filename in os.listdir(dir_path):
                file_path = os.path.join(dir_path, filename)
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)