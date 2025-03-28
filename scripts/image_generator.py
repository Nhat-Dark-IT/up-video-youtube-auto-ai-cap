#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Script tạo hình ảnh POV về các nhân vật lịch sử Ai Cập cổ đại.
Sử dụng Pollinations.ai API để tạo hình ảnh từ prompt, sau đó lưu vào Google Drive.
"""

import os
import json
import time
import base64
import logging
import requests
from typing import List, Dict, Any, Optional, Union
from pathlib import Path
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
# Import các module nội bộ
from config import settings, prompt_templates
from utils.google_sheets import GoogleSheetsManager
from utils.google_drive import GoogleDriveManager
from utils.base64_utils import save_base64_to_file

# Thiết lập logging
logger = logging.getLogger(__name__)
log_handler = logging.FileHandler(settings.LOG_FILE, encoding='utf-8')
console_handler = logging.StreamHandler()
log_formatter = logging.Formatter(settings.LOG_FORMAT)
log_handler.setFormatter(log_formatter)
console_handler.setFormatter(log_formatter)

logger.setLevel(settings.LOG_LEVEL)
logger.addHandler(log_handler)
logger.addHandler(console_handler)

class ImageGenerator:
    """
    Lớp tạo hình ảnh POV từ prompt sử dụng Pollinations API.
    """
    
    def __init__(self):
        """
        Khởi tạo ImageGenerator với cấu hình từ settings.
        """
        # Khởi tạo các managers
        self.sheets_manager = GoogleSheetsManager()
        self.drive_manager = GoogleDriveManager()
        
        # Lấy thông tin cấu hình
        self.pollinations_url = settings.POLLINATIONS_URL
        self.image_width = settings.POLLINATIONS_IMAGE_WIDTH
        self.image_height = settings.POLLINATIONS_IMAGE_HEIGHT
        self.model = settings.POLLINATIONS_MODEL
        self.seed = settings.POLLINATIONS_SEED
        self.nologo = settings.POLLINATIONS_NO_LOGO
        # ID thư mục Google Drive để lưu ảnh
        self.drive_folder_id = "1oFc-Wby1Gm5GKwr1Eygg4zzVfIqIlo0Y"
        logger.info("Khoi tao ImageGenerator thanh cong")
    
    def generate_image_from_prompt(self, prompt: str, index: int = 0) -> Dict[str, Any]:
        """
        Tạo hình ảnh từ prompt sử dụng Pollinations API.
        
        Args:
            prompt: Prompt mô tả hình ảnh cần tạo
            index: Chỉ số để đặt tên file
            
        Returns:
            Dict: Thông tin về hình ảnh đã tạo
        """
        try:
            # Mã hóa URL và tạo URL API
            # Dùng URL nguyên bản thay vì mã hóa vì Pollinations API đã xử lý
            url = self.pollinations_url.format(prompt=prompt)
            
            # Thiết lập tham số query
            params = {
                "width": self.image_width,
                "height": self.image_height,
                "model": self.model,
                "seed": self.seed,
                "nologo": self.nologo
            }
            
            # Thiết lập headers
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
            
            # Tạo tên file
            filename = settings.IMAGE_FILENAME_TEMPLATE.format(index=index)
            local_path = os.path.join(settings.TEMP_DIR, "images", filename)
            
            logger.info(f"Dang tao hinh anh cho prompt: '{prompt[:50]}...'")
            
            # Gọi API với cơ chế retry
            for attempt in range(settings.MAX_RETRIES):
                try:
                    response = requests.get(
                        url,
                        params=params,
                        headers=headers,
                        timeout=settings.API_TIMEOUT
                    )
                    
                    # Kiểm tra lỗi
                    response.raise_for_status()
                    
                    # Lưu hình ảnh vào file tạm thời
                    with open(local_path, 'wb') as f:
                        f.write(response.content)
                    
                    # Mã hóa hình ảnh thành base64 để tiện xử lý
                    image_base64 = base64.b64encode(response.content).decode('utf-8')
                    
                    logger.info(f"Da tao hinh anh thanh cong: {filename}")
                    
                    # Trả về thông tin hình ảnh
                    return {
                        "prompt": prompt,
                        "filename": filename,
                        "local_path": local_path,
                        "image_base64": image_base64,
                        "success": True
                    }
                
                except requests.exceptions.RequestException as e:
                    if attempt < settings.MAX_RETRIES - 1:
                        logger.warning(f"Loi khi tao hinh anh (lan thu {attempt+1}/{settings.MAX_RETRIES}): {str(e)}")
                        time.sleep(settings.RETRY_DELAY)
                    else:
                        logger.error(f"Khong the tao hinh anh sau {settings.MAX_RETRIES} lan thu: {str(e)}")
                        return {
                            "prompt": prompt,
                            "success": False,
                            "error": str(e)
                        }
            
        except Exception as e:
            logger.error(f"Loi khi tao hinh anh: {str(e)}")
            return {
                "prompt": prompt,
                "success": False,
                "error": str(e)
            }
    
    def upload_to_drive(self, image_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Tải hình ảnh lên Google Drive và thiết lập quyền chia sẻ.
        
        Args:
            image_info: Thông tin về hình ảnh
            
        Returns:
            Dict: Thông tin hình ảnh đã cập nhật với link Google Drive
        """
        try:
            if not image_info.get("success", False):
                return image_info
                
            # Tải lên Google Drive và chỉ định thư mục đích
            file_id = self.drive_manager.upload_from_base64(
                base64_data=image_info["image_base64"],
                filename=image_info["filename"],
                mime_type="image/png",
                parent_folder_id=self.drive_folder_id  # Thêm ID thư mục đích
            )
            
            if not file_id:
                logger.error(f"Khong the tai hinh anh len Google Drive: {image_info['filename']}")
                image_info["drive_upload_success"] = False
                return image_info
            
            # Thiết lập quyền chia sẻ công khai
            sharing_success = self.drive_manager.share_file(
                file_id=file_id,
                role="reader",
                type="anyone"
            )
            
            # Lấy link truy cập trực tiếp
            web_content_link = self.drive_manager.get_web_content_link(file_id)
            
            # Cập nhật thông tin hình ảnh
            image_info.update({
                "file_id": file_id,
                "web_content_link": web_content_link,
                "shared": sharing_success,
                "drive_upload_success": True,
                "drive_folder_id": self.drive_folder_id  # Lưu ID thư mục để tham khảo
            })
            
            logger.info(f"Da tai len va chia se hinh anh vao thu muc Google Drive: {web_content_link}")
            return image_info
            
        except Exception as e:
            logger.error(f"Loi khi tai hinh anh len Google Drive: {str(e)}")
            image_info["drive_upload_success"] = False
            image_info["drive_error"] = str(e)
            return image_info
    
    def load_enhanced_scenes(self) -> Dict[str, Any]:
        """
        Đọc các cảnh đã được tăng cường chi tiết từ file.
        
        Returns:
            Dict: Dữ liệu cảnh đã tăng cường
        """
        try:
            # Đường dẫn file kết quả từ scene_prompt_enhancer
            input_file = os.path.join(settings.TEMP_DIR, "enhanced_scene_prompts.json")
            
            # Kiểm tra file tồn tại
            if os.path.exists(input_file):
                with open(input_file, 'r', encoding='utf-8') as f:
                    enhanced_data = json.load(f)
                    
                if enhanced_data and "enhanced_scenes" in enhanced_data and len(enhanced_data["enhanced_scenes"]) > 0:
                    scene_count = len(enhanced_data["enhanced_scenes"])
                    logger.info(f"Da doc {scene_count} canh tang cuong tu file")
                    return enhanced_data
                else:
                    logger.warning("File enhanced_scene_prompts.json ton tai nhung khong co du lieu canh hop le")
                    return {}
            else:
                logger.warning(f"Khong tim thay file canh da tang cuong: {input_file}")
                return {}
                
        except Exception as e:
            logger.error(f"Loi khi doc file canh da tang cuong: {str(e)}")
            return {}
    
    def load_scene_sequence(self) -> Dict[str, Any]:
        """
        Đọc chuỗi cảnh từ file scene_sequences.json nếu không tìm thấy cảnh đã tăng cường.
        
        Returns:
            Dict: Dữ liệu chuỗi cảnh
        """
        try:
            # Đường dẫn file
            input_file = os.path.join(settings.TEMP_DIR, "scene_sequences.json")
            
            # Kiểm tra file tồn tại
            if os.path.exists(input_file):
                with open(input_file, 'r', encoding='utf-8') as f:
                    scene_data = json.load(f)
                    
                if scene_data and "scenes" in scene_data and len(scene_data["scenes"]) > 0:
                    scene_count = len(scene_data["scenes"])
                    logger.info(f"Da doc {scene_count} canh tu file scene_sequences.json")
                    
                    # Chuyển đổi định dạng để tương thích với cấu trúc cảnh đã tăng cường
                    enhanced_data = {
                        "ID": scene_data.get("ID"),
                        "Idea": scene_data.get("Idea", ""),
                        "Environment_Prompt": scene_data.get("Environment_Prompt", ""),
                        "enhanced_scenes": [
                            {
                                "original_scene": scene,
                                "enhanced_prompt": scene
                            } for scene in scene_data.get("scenes", [])
                        ]
                    }
                    return enhanced_data
                else:
                    logger.warning("File scene_sequences.json ton tai nhung khong co du lieu canh hop le")
                    return {}
            else:
                logger.warning(f"Khong tim thay file chuoi canh: {input_file}")
                return {}
                
        except Exception as e:
            logger.error(f"Loi khi doc file chuoi canh: {str(e)}")
            return {}
    
    def load_ideas_from_sheets(self) -> List[Dict[str, Any]]:
        """
        Lấy ý tưởng POV từ Google Sheets để tạo hình ảnh.
        
        Returns:
            List[Dict]: Danh sách ý tưởng POV
        """
        try:
            # Lấy ý tưởng từ Google Sheets
            ideas = self.sheets_manager.get_ideas_for_production()
            
            if not ideas:
                logger.warning("Khong tim thay y tuong nao duoc danh dau de san xuat trong Google Sheets")
                return []
            
            logger.info(f"Da lay {len(ideas)} y tuong tu Google Sheets")
            return ideas
            
        except Exception as e:
            logger.error(f"Loi khi lay y tuong tu Google Sheets: {str(e)}")
            return []
    
    def process_enhanced_scenes(self) -> List[Dict[str, Any]]:
        """
        Xử lý các cảnh đã tăng cường để tạo hình ảnh.
        
        Returns:
            List[Dict]: Kết quả xử lý hình ảnh cho từng cảnh
        """
        # Đọc dữ liệu cảnh đã tăng cường
        enhanced_data = self.load_enhanced_scenes()
        
        if not enhanced_data or "enhanced_scenes" not in enhanced_data:
            logger.warning("Khong tim thay canh da tang cuong, thu tim kiem o scene_sequences.json")
            enhanced_data = self.load_scene_sequence()
            
            if not enhanced_data or "enhanced_scenes" not in enhanced_data:
                logger.warning("Khong tim thay canh nao de tao hinh anh")
                return []
        
        enhanced_scenes = enhanced_data["enhanced_scenes"]
        base_idea = {
            "ID": enhanced_data.get("ID"),
            "Idea": enhanced_data.get("Idea", ""),
            "Environment_Prompt": enhanced_data.get("Environment_Prompt", "")
        }
        
        logger.info(f"Dang tao hinh anh cho {len(enhanced_scenes)} canh")
        
        # Xử lý từng cảnh
        results = []
        for i, scene_data in enumerate(enhanced_scenes):
            logger.info(f"Dang tao hinh anh cho canh {i+1}/{len(enhanced_scenes)}")
            
            # Lấy prompt đã tăng cường
            enhanced_prompt = scene_data.get("enhanced_prompt", "")
            original_scene = scene_data.get("original_scene", "")
            
            if not enhanced_prompt:
                logger.warning(f"Khong tim thay prompt tang cuong cho canh {i+1}")
                continue
            
            # Tạo hình ảnh
            image_info = self.generate_image_from_prompt(enhanced_prompt, i+1)
            
            # Thêm thông tin cảnh
            image_info["idea_id"] = base_idea.get("ID")
            image_info["original_idea"] = base_idea.get("Idea")
            image_info["original_scene"] = original_scene
            image_info["environment_prompt"] = base_idea.get("Environment_Prompt")
            image_info["scene_index"] = i+1
            
            # Tải lên Google Drive
            if image_info.get("success", False):
                image_info = self.upload_to_drive(image_info)
            
            results.append(image_info)
            
            # Thêm độ trễ giữa các lần gọi API
            if i < len(enhanced_scenes) - 1:
                time.sleep(2)
        
        # Lưu kết quả vào file tạm thời cho các bước tiếp theo
        output_file = os.path.join(settings.TEMP_DIR, "enhanced_image_results.json")
        with open(output_file, 'w', encoding='utf-8') as f:
            # Loại bỏ dữ liệu base64 từ kết quả JSON để tránh file quá lớn
            light_results = []
            for result in results:
                result_copy = result.copy()
                if "image_base64" in result_copy:
                    del result_copy["image_base64"]
                light_results.append(result_copy)
            
            json.dump(light_results, f, ensure_ascii=False, indent=2)
        
        # Tổng kết
        success_count = sum(1 for r in results if r.get("success", False))
        drive_success_count = sum(1 for r in results if r.get("drive_upload_success", False))
        
        logger.info(f"Hoan thanh tao hinh anh cho cac canh: {success_count}/{len(results)} thanh cong")
        logger.info(f"Tai len Google Drive: {drive_success_count}/{len(results)} thanh cong")
        logger.info(f"Ket qua da duoc luu vao: {output_file}")
        
        return results
    
    def process_from_sheets(self) -> List[Dict[str, Any]]:
        """
        Tạo hình ảnh trực tiếp từ ý tưởng POV trong Google Sheets.
        
        Returns:
            List[Dict]: Kết quả xử lý hình ảnh
        """
        # Lấy ý tưởng từ Google Sheets
        ideas = self.load_ideas_from_sheets()
        
        if not ideas:
            logger.warning("Khong co y tuong nao de tao hinh anh")
            return []
        
        # Chọn ý tưởng đầu tiên
        idea = ideas[0]
        logger.info(f"Da chon y tuong: ID={idea.get('ID')}, Idea='{idea.get('Idea')[:30]}...'")
        
        # Sử dụng ý tưởng và môi trường làm prompt
        prompt = f"{idea.get('Idea')} {idea.get('Environment_Prompt')}"
        
        # Tạo hình ảnh từ prompt
        image_info = self.generate_image_from_prompt(prompt)
        
        # Thêm thông tin ý tưởng
        image_info["idea_id"] = idea.get("ID")
        image_info["original_idea"] = idea.get("Idea")
        image_info["environment_prompt"] = idea.get("Environment_Prompt")
        
        # Tải lên Google Drive
        if image_info.get("success", False):
            image_info = self.upload_to_drive(image_info)
        
        # Lưu kết quả
        output_file = os.path.join(settings.TEMP_DIR, "sheets_image_result.json")
        with open(output_file, 'w', encoding='utf-8') as f:
            # Loại bỏ dữ liệu base64
            result_copy = image_info.copy()
            if "image_base64" in result_copy:
                del result_copy["image_base64"]
            
            json.dump(result_copy, f, ensure_ascii=False, indent=2)
        
        return [image_info]

def main():
    """
    Hàm chính để chạy quy trình tạo hình ảnh.
    """
    try:
        logger.info("=== Bat dau Quy trinh Tao Hinh anh POV ===")
        
        # Đảm bảo thư mục tạm thời tồn tại
        image_temp_dir = os.path.join(settings.TEMP_DIR, "images")
        os.makedirs(image_temp_dir, exist_ok=True)
        
        # Tạo instance của ImageGenerator
        image_generator = ImageGenerator()
        
        # Thực hiện quy trình tạo hình ảnh từ các cảnh đã tăng cường
        results = image_generator.process_enhanced_scenes()
        
        if not results:
            logger.warning("Khong tao duoc hinh anh nao tu cac canh, thu tao tu Google Sheets...")
            # Thử phương pháp thay thế: tạo hình ảnh từ Google Sheets
            results = image_generator.process_from_sheets()
        
        if not results:
            logger.warning("Khong tao duoc hinh anh nao")
        else:
            logger.info(f"Da tao thanh cong {len(results)} hinh anh")
            logger.info(f"Tat ca hinh anh da duoc tai len thu muc Google Drive: https://drive.google.com/drive/folders/{image_generator.drive_folder_id}")
        
        logger.info("=== Ket thuc Quy trinh Tao Hinh anh POV ===")
        
        return results
        
    except Exception as e:
        logger.error(f"Loi trong quy trinh tao hinh anh: {str(e)}")
        raise

if __name__ == "__main__":
    main()