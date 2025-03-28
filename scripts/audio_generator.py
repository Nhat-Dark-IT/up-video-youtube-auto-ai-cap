#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Script tạo âm thanh cho video POV về chủ đề Ai Cập cổ đại.
Sử dụng ElevenLabs API để chuyển đổi văn bản thành giọng nói.
"""

import os
import base64
import json
import time
import logging
import requests
import io

from datetime import datetime
from typing import List, Dict, Any, Optional
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
# Import các module nội bộ
from config import settings
from utils.google_sheets import GoogleSheetsManager
from utils.google_drive import GoogleDriveManager
from utils.base64_utils import decode_base64_to_bytes

# Thiết lập logging với encoding để hỗ trợ Unicode
logger = logging.getLogger(__name__)
log_handler = logging.FileHandler(settings.LOG_FILE, encoding='utf-8')
console_handler = logging.StreamHandler()
log_formatter = logging.Formatter(settings.LOG_FORMAT)
log_handler.setFormatter(log_formatter)
console_handler.setFormatter(log_formatter)

logger.setLevel(settings.LOG_LEVEL)
logger.addHandler(log_handler)
logger.addHandler(console_handler)
# Thêm vào phần imports
try:
    from gtts import gTTS
except ImportError:
    logger.warning("Thư viện gTTS chưa được cài đặt. Sẽ được cài đặt khi cần thiết.")

def __init__(self):
    """
    Khởi tạo AudioGenerator với cấu hình từ settings.
    """
    # Khởi tạo các managers
    self.sheets_manager = GoogleSheetsManager()
    self.drive_manager = GoogleDriveManager()
    
    # Thư mục Google Drive để lưu âm thanh
    self.drive_folder_id = "1SXv9rGf_EvC1BBeilAh1QtzquS8A6pti"
    
    # Thư mục lưu trữ
    self.temp_dir = settings.TEMP_DIR
    self.audio_dir = os.path.join(self.temp_dir, "audio")
    
    # Đảm bảo thư mục tồn tại
    os.makedirs(self.audio_dir, exist_ok=True)
    
    logger.info("AudioGenerator khởi tạo thành công (sử dụng Google TTS)")
class AudioGenerator:
    """
    Lớp tạo âm thanh cho video POV sử dụng ElevenLabs API.
    """
    
    def __init__(self):
        """
        Khởi tạo AudioGenerator với cấu hình từ settings.
        """
        # Khởi tạo các managers
        self.sheets_manager = GoogleSheetsManager()
        self.drive_manager = GoogleDriveManager()
        
        # Lấy thông tin API
        self.api_url = settings.ELEVENLABS_URL
        self.api_key = settings.ELEVENLABS_API_KEY
        self.audio_duration = settings.ELEVENLABS_DURATION
        self.prompt_influence = settings.ELEVENLABS_PROMPT_INFLUENCE
        
        # ID thư mục Google Drive để lưu âm thanh
        self.drive_folder_id = "1SXv9rGf_EvC1BBeilAh1QtzquS8A6pti"
        
        # Thư mục lưu trữ
        self.temp_dir = settings.TEMP_DIR
        self.audio_dir = os.path.join(self.temp_dir, "audio")
        
        # Đảm bảo thư mục tồn tại
        os.makedirs(self.audio_dir, exist_ok=True)
        
        logger.info("AudioGenerator initialized successfully")

    def generate_audio(self, text: str, output_filename: str) -> Optional[Dict[str, Any]]:
        """
        Tạo âm thanh từ văn bản sử dụng Google Text-to-Speech (miễn phí).
        
        Args:
            text: Văn bản cần chuyển thành âm thanh
            output_filename: Tên file đầu ra
            
        Returns:
            Dict chứa thông tin về âm thanh hoặc None nếu thất bại
        """
        try:
            # Đảm bảo thư viện gTTS đã được cài đặt
            try:
                from gtts import gTTS
            except ImportError:
                logger.error("Thư viện gTTS chưa được cài đặt. Vui lòng cài đặt: pip install gtts")
                return None
    
            # Đường dẫn đến file đầu ra
            output_path = os.path.join(self.audio_dir, output_filename)
            
            logger.info(f"Đang tạo âm thanh cho văn bản: '{text[:50]}...'")
            
            # Tạo âm thanh từ văn bản
            tts = gTTS(text=text, lang='en', slow=False)
            tts.save(output_path)
            
            # Đọc file để chuyển thành base64
            with open(output_path, "rb") as f:
                audio_data = f.read()
                audio_base64 = base64.b64encode(audio_data).decode('utf-8')
            
            logger.info(f"Đã tạo âm thanh thành công: {output_filename}")
            
            return {
                "filename": output_filename,
                "audio_base64": audio_base64,
                "local_path": output_path,
                "text": text
            }
            
        except Exception as e:
            logger.error(f"Lỗi khi tạo âm thanh: {str(e)}")
            return None

    def upload_to_drive(self, audio_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Tải file âm thanh lên Google Drive và thiết lập quyền chia sẻ.
        
        Args:
            audio_info: Dict chứa thông tin âm thanh
            
        Returns:
            audio_info đã cập nhật với thông tin từ Google Drive
        """
        try:
            # Tải lên Google Drive và chỉ định thư mục đích
            file_id = self.drive_manager.upload_from_base64(
                base64_data=audio_info["audio_base64"],
                filename=audio_info["filename"],
                mime_type="audio/mpeg",
                parent_folder_id=self.drive_folder_id  # Thêm ID thư mục đích
            )
            
            if not file_id:
                logger.error(f"Failed to upload audio to Google Drive: {audio_info['filename']}")
                audio_info["drive_upload_success"] = False
                return audio_info
            
            # Thiết lập quyền chia sẻ công khai
            sharing_success = self.drive_manager.share_file(
                file_id=file_id,
                role="reader",
                type="anyone"
            )
            
            # Lấy link truy cập trực tiếp
            web_content_link = self.drive_manager.get_web_content_link(file_id)
            
            # Cập nhật thông tin âm thanh
            audio_info.update({
                "file_id": file_id,
                "web_content_link": web_content_link,
                "shared": sharing_success,
                "drive_upload_success": True,
                "drive_folder_id": self.drive_folder_id  # Lưu ID thư mục để tham khảo
            })
            
            logger.info(f"Audio uploaded to Google Drive successfully: {web_content_link}")
            return audio_info
            
        except Exception as e:
            logger.error(f"Error uploading audio to Google Drive: {str(e)}")
            audio_info["drive_upload_success"] = False
            audio_info["drive_error"] = str(e)
            return audio_info

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
                    
                if enhanced_data and "enhanced_scenes" in enhanced_data:
                    scene_count = len(enhanced_data["enhanced_scenes"])
                    logger.info(f"Loaded {scene_count} enhanced scenes from file")
                    return enhanced_data
                else:
                    logger.warning("Enhanced scenes file exists but contains no valid scene data")
                    return {}
            else:
                logger.warning(f"Enhanced scenes file not found: {input_file}")
                return {}
                
        except Exception as e:
            logger.error(f"Error loading enhanced scenes: {str(e)}")
            return {}
    
    def process_enhanced_scenes(self) -> List[Dict[str, Any]]:
        """
        Xử lý các cảnh đã tăng cường để tạo âm thanh.
        
        Returns:
            List[Dict]: Kết quả xử lý âm thanh cho từng cảnh
        """
        # Đọc dữ liệu cảnh đã tăng cường
        enhanced_data = self.load_enhanced_scenes()
        
        if not enhanced_data or "enhanced_scenes" not in enhanced_data:
            logger.warning("No enhanced scenes found, falling back to ideas from Google Sheets")
            return self.process_audio_generation()
        
        enhanced_scenes = enhanced_data["enhanced_scenes"]
        
        logger.info(f"Processing audio for {len(enhanced_scenes)} enhanced scenes")
        
        # Xử lý từng cảnh
        results = []
        for i, scene_data in enumerate(enhanced_scenes):
            logger.info(f"Processing audio for scene {i+1}/{len(enhanced_scenes)}")
            
            # Lấy prompt đã tăng cường
            enhanced_prompt = scene_data.get("enhanced_prompt", "")
            original_scene = scene_data.get("original_scene", "")
            
            if not enhanced_prompt:
                logger.warning(f"No enhanced prompt found for scene {i+1}, using original scene")
                enhanced_prompt = original_scene
            
            # Tạo tên file đầu ra
            filename = settings.AUDIO_FILENAME_TEMPLATE.format(index=i+1)
            
            # Tạo âm thanh với cơ chế thử lại
            audio_info = None
            for attempt in range(settings.MAX_RETRIES):
                audio_info = self.generate_audio(enhanced_prompt, filename)
                
                if audio_info:
                    break
                    
                logger.warning(f"Retrying audio creation (attempt {attempt+1}/{settings.MAX_RETRIES})")
                time.sleep(settings.RETRY_DELAY)
            
            if not audio_info:
                results.append({
                    "scene_index": i+1,
                    "original_scene": original_scene,
                    "enhanced_prompt": enhanced_prompt,
                    "success": False,
                    "error": "Failed to create audio after multiple attempts"
                })
                continue
            
            # Thêm thông tin cảnh
            audio_info["scene_index"] = i+1
            audio_info["original_scene"] = original_scene
            audio_info["enhanced_prompt"] = enhanced_prompt
            
            # Tải lên Google Drive
            audio_info = self.upload_to_drive(audio_info)
            audio_info["success"] = True
            
            results.append(audio_info)
            
            # Thêm độ trễ giữa các lần gọi API
            if i < len(enhanced_scenes) - 1:
                time.sleep(1)
        
        # Lưu kết quả vào file
        output_file = os.path.join(self.temp_dir, "enhanced_audio_results.json")
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        # Tổng kết
        success_count = sum(1 for r in results if r.get("success", False))
        
        logger.info(f"Audio generation completed: {success_count}/{len(results)} successful")
        logger.info(f"Results saved to: {output_file}")
        logger.info(f"All audio files uploaded to Google Drive folder: https://drive.google.com/drive/folders/{self.drive_folder_id}")
        
        return results
    
    def process_idea(self, idea: Dict[str, Any], index: int) -> Dict[str, Any]:
        """
        Xử lý một ý tưởng POV để tạo và tải lên âm thanh.
        
        Args:
            idea: Thông tin ý tưởng POV
            index: Chỉ số để tạo tên file
            
        Returns:
            Dict với kết quả xử lý âm thanh
        """
        try:
            # Lấy caption hoặc sử dụng văn bản ý tưởng thay thế
            text = idea.get("Caption", "")
            if not text:
                text = idea.get("Idea", "").replace("POV:", "")
            
            # Tạo tên file đầu ra
            filename = settings.AUDIO_FILENAME_TEMPLATE.format(index=index)
            
            # Tạo âm thanh với cơ chế thử lại
            audio_info = None
            for attempt in range(settings.MAX_RETRIES):
                try:
                    audio_info = self.generate_audio(text, filename)
                    if audio_info:
                        break
                except Exception as e:
                    logger.warning(f"Lỗi khi tạo âm thanh (lần thử {attempt+1}): {str(e)}")
                    time.sleep(settings.RETRY_DELAY)
            
            if not audio_info:
                return {
                    "idea_id": idea.get("ID"),
                    "success": False,
                    "error": "Không thể tạo âm thanh sau nhiều lần thử"
                }
            
            # Thêm thông tin ý tưởng
            audio_info["idea_id"] = idea.get("ID")
            
            # Tải lên Google Drive
            audio_info = self.upload_to_drive(audio_info)
            
            return {
                **audio_info,
                "success": True
            }
            
        except Exception as e:
            logger.error(f"Lỗi khi xử lý âm thanh cho ý tưởng {idea.get('ID')}: {str(e)}")
            return {
                "idea_id": idea.get("ID"),
                "success": False,
                "error": str(e)
            }
    
    def get_ideas_from_sheets(self) -> List[Dict[str, Any]]:
        """
        Lấy ý tưởng POV từ Google Sheets.
        
        Returns:
            List[Dict]: Danh sách các ý tưởng POV
        """
        try:
            # Lấy ý tưởng từ Google Sheets
            ideas = self.sheets_manager.get_ideas_for_production()
            
            # Giới hạn số lượng ý tưởng
            if len(ideas) > settings.MAX_SCENES_PER_VIDEO:
                logger.info(f"Limiting to {settings.MAX_SCENES_PER_VIDEO} ideas")
                ideas = ideas[:settings.MAX_SCENES_PER_VIDEO]
            
            logger.info(f"Found {len(ideas)} ideas from Google Sheets")
            return ideas
            
        except Exception as e:
            logger.error(f"Error getting ideas from Google Sheets: {str(e)}")
            return []
    
    def process_audio_generation(self) -> List[Dict[str, Any]]:
        """
        Thực hiện toàn bộ quy trình tạo âm thanh từ Google Sheets.
        
        Returns:
            List[Dict]: Danh sách kết quả xử lý âm thanh
        """
        # Lấy ý tưởng từ Google Sheets
        ideas = self.get_ideas_from_sheets()
        
        if not ideas:
            logger.warning("No ideas found for audio generation")
            return []
        
        logger.info(f"Processing audio for {len(ideas)} POV ideas")
        
        # Xử lý từng ý tưởng
        results = []
        for i, idea in enumerate(ideas):
            logger.info(f"Processing audio for idea {i+1}/{len(ideas)} (ID: {idea.get('ID')})")
            result = self.process_idea(idea, i+1)
            results.append(result)
            
            # Thêm độ trễ nhỏ giữa các lần gọi API
            if i < len(ideas) - 1:
                time.sleep(1)
        
        # Lưu kết quả vào file
        output_file = os.path.join(self.temp_dir, "audio_results.json")
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        # Tổng kết
        success_count = sum(1 for r in results if r.get("success", False))
        logger.info(f"Audio generation completed: {success_count}/{len(results)} successful")
        logger.info(f"Results saved to: {output_file}")
        logger.info(f"All audio files uploaded to Google Drive folder: https://drive.google.com/drive/folders/{self.drive_folder_id}")
        
        return results

def main():
    """
    Hàm chính để chạy quy trình tạo âm thanh.
    """
    try:
        logger.info("=== Starting Audio Generation Process ===")
        
        # Tạo instance của AudioGenerator
        audio_generator = AudioGenerator()
        
        # Thử xử lý cảnh đã tăng cường trước
        results = audio_generator.process_enhanced_scenes()
        
        # Nếu không có kết quả từ cảnh tăng cường, sẽ tự động fallback trong process_enhanced_scenes
        
        if not results:
            logger.warning("No audio was generated")
        else:
            logger.info(f"Successfully generated {sum(1 for r in results if r.get('success', False))}/{len(results)} audio files")
            logger.info(f"All audio files uploaded to Google Drive folder: https://drive.google.com/drive/folders/{audio_generator.drive_folder_id}")
        
        logger.info("=== Audio Generation Process Completed ===")
        
        return results
        
    except Exception as e:
        logger.error(f"Error in audio generation process: {str(e)}")
        raise

if __name__ == "__main__":
    main()