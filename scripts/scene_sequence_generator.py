#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Script tạo chuỗi cảnh từ ý tưởng POV về Ai Cập cổ đại.
Lấy ý tưởng từ Google Sheets và tạo chuỗi prompt chi tiết theo trình tự.
"""

import os
import sys
import json
import logging
from typing import List, Dict, Any, Optional

# Thêm thư mục gốc vào đường dẫn
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import thư viện AI
import google.generativeai as genai

# Import module nội bộ
from config import settings, prompt_templates
from utils.google_sheets import GoogleSheetsManager

# Thiết lập logging
logger = logging.getLogger(__name__)
log_handler = logging.FileHandler(settings.LOG_FILE, encoding='utf-8')
console_handler = logging.StreamHandler(sys.stdout)
log_formatter = logging.Formatter(settings.LOG_FORMAT)
log_handler.setFormatter(log_formatter)
console_handler.setFormatter(log_formatter)

logger.setLevel(settings.LOG_LEVEL)
logger.addHandler(log_handler)
logger.addHandler(console_handler)

class SceneSequenceGenerator:
    """
    Lớp tạo chuỗi cảnh từ ý tưởng POV.
    """
    
    def __init__(self):
        """
        Khởi tạo SceneSequenceGenerator với cấu hình từ settings.
        """
        # Khởi tạo Google Sheets manager
        self.sheets_manager = GoogleSheetsManager()
        
        # Cấu hình Gemini API
        if settings.GEMINI_API_KEY:
            genai.configure(api_key=settings.GEMINI_API_KEY)
            self.gemini_available = True
        else:
            logger.warning("Không tìm thấy GEMINI_API_KEY. Khả năng tạo cảnh có thể bị hạn chế.")
            self.gemini_available = False
            
        # Tải template prompt tạo chuỗi cảnh
        self.scene_template = prompt_templates.SCENE_SEQUENCE_PROMPT
        
        logger.info("Khởi tạo SceneSequenceGenerator thành công")
        
    def get_production_ideas(self) -> List[Dict[str, Any]]:
        """
        Lấy ý tưởng POV đánh dấu để sản xuất từ Google Sheets.
        
        Returns:
            List[Dict]: Danh sách ý tưởng POV sẵn sàng để sản xuất
        """
        try:
            # Lấy ý tưởng từ Google Sheets
            ideas = self.sheets_manager.get_ideas_for_production()
            
            if not ideas:
                logger.warning("Không tìm thấy ý tưởng nào được đánh dấu để sản xuất")
                return []
            
            logger.info(f"Đã tìm thấy {len(ideas)} ý tưởng được đánh dấu để sản xuất")
            return ideas
            
        except Exception as e:
            logger.error(f"Lỗi khi lấy ý tưởng sản xuất: {str(e)}")
            return []
            
    def generate_scene_sequence(self, idea: Dict[str, Any]) -> Dict[str, Any]:
        """
        Tạo chuỗi cảnh từ một ý tưởng POV.
        
        Args:
            idea: Dictionary chứa thông tin ý tưởng POV
            
        Returns:
            Dict: Ý tưởng với chuỗi cảnh đã thêm vào
        """
        if not self.gemini_available:
            logger.error("Không thể tạo chuỗi cảnh khi không có Gemini API")
            return idea
            
        try:
            # Trích xuất ý tưởng POV gốc
            pov_idea = idea.get("Idea", "").replace("POV:", "").strip()
            
            if not pov_idea:
                logger.warning(f"Tìm thấy ý tưởng POV trống cho ID {idea.get('ID')}")
                return idea
                
            # Sửa prompt để yêu cầu đúng 5 cảnh
            prompt = self.scene_template.replace("{pov_idea}", pov_idea)
            prompt = prompt.replace("5-7 distinct scenes", "exactly 5 distinct scenes")
            
            # Gọi Gemini API
            logger.info(f"Đang tạo chuỗi cảnh cho: '{pov_idea[:50]}...'")
            model = genai.GenerativeModel('gemini-2.0-flash-thinking-exp-01-21')
            response = model.generate_content(prompt)
            
            if not response.text:
                logger.error("Không nhận được phản hồi từ Gemini API")
                return idea
                
            # Xử lý phản hồi thành danh sách cảnh
            scenes = self._parse_scene_sequence(response.text)
            
            # Đảm bảo chỉ có 5 cảnh
            if len(scenes) > 5:
                scenes = scenes[:5]
            
            # Thêm cảnh vào ý tưởng
            idea["scenes"] = scenes
            idea["scene_count"] = len(scenes)
            
            logger.info(f"Đã tạo {len(scenes)} cảnh cho ý tưởng: '{pov_idea[:30]}...'")
            return idea
            
        except Exception as e:
            logger.error(f"Lỗi khi tạo chuỗi cảnh: {str(e)}")
            return idea
            
    def _parse_scene_sequence(self, response_text: str) -> List[str]:
        """
        Phân tích chuỗi cảnh từ phản hồi API.
        
        Args:
            response_text: Phản hồi văn bản từ Gemini API
            
        Returns:
            List[str]: Danh sách prompt cảnh
        """
        try:
            # Tách theo dòng và lọc bỏ dòng trống
            lines = response_text.strip().split('\n')
            scenes = [line.strip() for line in lines if line.strip()]
            
            # Lọc bỏ các dòng có vẻ là tiêu đề (không chứa POV)
            scenes = [scene for scene in scenes if not scene.startswith('#') and not scene.startswith('-')]
            
            # Đảm bảo tất cả các cảnh bắt đầu bằng "POV:"
            for i in range(len(scenes)):
                if not scenes[i].startswith("POV:"):
                    scenes[i] = f"POV: {scenes[i]}"
                    
            return scenes
            
        except Exception as e:
            logger.error(f"Lỗi khi phân tích chuỗi cảnh: {str(e)}")
            return []
            
    def process_selected_idea(self) -> Dict[str, Any]:
        """
        Xử lý một ý tưởng được chọn từ danh sách để sản xuất và tạo chuỗi cảnh.
        Chọn ý tưởng đầu tiên từ trên xuống có trạng thái "for production".
        
        Returns:
            Dict: Ý tưởng với chuỗi cảnh đã tạo
        """
        # Lấy ý tưởng được đánh dấu để sản xuất
        ideas = self.get_production_ideas()
        
        if not ideas:
            logger.warning("Không có ý tưởng nào để xử lý")
            return {}
            
        # Chọn ý tưởng đầu tiên từ danh sách (theo thứ tự từ trên xuống)
        selected_idea = ideas[0]
        logger.info(f"Đã chọn ý tưởng: ID={selected_idea.get('ID')}, Idea='{selected_idea.get('Idea')[:30]}...'")
        
        # Tạo chuỗi cảnh cho ý tưởng được chọn
        enhanced_idea = self.generate_scene_sequence(selected_idea)
        
        # Đảm bảo chỉ giữ đúng 5 cảnh
        if enhanced_idea.get("scenes") and len(enhanced_idea.get("scenes")) > 5:
            enhanced_idea["scenes"] = enhanced_idea["scenes"][:5]
            enhanced_idea["scene_count"] = 5
            logger.info(f"Đã giới hạn còn 5 cảnh cho ý tưởng đã chọn")
        
        # Lưu kết quả vào file tạm thời cho các bước tiếp theo
        output_file = os.path.join(settings.TEMP_DIR, "scene_sequences.json")
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(enhanced_idea, f, ensure_ascii=False, indent=2)
            
        logger.info(f"Đã lưu chuỗi cảnh vào file: {output_file}")
        
        return enhanced_idea
# Trong scene_sequence_generator.py
# Trong scene_sequence_generator.py
def process_n8n_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Xử lý dữ liệu từ node N8n Google Sheets.
    
    Args:
        data: Dữ liệu từ N8n
        
    Returns:
        Dict: Kết quả xử lý
    """
    try:
        # Trích xuất ý tưởng từ dữ liệu N8n
        idea = {
            "ID": data.get("ID", ""),
            "Idea": data.get("Idea", ""),
            "Environment_Prompt": data.get("Environment_Prompt", "")
        }
        
        # Tạo chuỗi cảnh
        generator = SceneSequenceGenerator()
        enhanced_idea = generator.generate_scene_sequence(idea)
        
        return enhanced_idea
        
    except Exception as e:
        logger.error(f"Lỗi khi xử lý dữ liệu N8n: {str(e)}")
        return {"error": str(e)}
def main():
    """
    Hàm chính để chạy quy trình tạo chuỗi cảnh.
    """
    try:
        logger.info("=== Bắt đầu Quy trình Tạo Chuỗi Cảnh ===")
        
        # Tạo instance của SceneSequenceGenerator
        scene_generator = SceneSequenceGenerator()
        
        # Xử lý một ý tưởng được chọn và tạo chuỗi cảnh
        enhanced_idea = scene_generator.process_selected_idea()
        
        if enhanced_idea:
            logger.info(f"Đã tạo thành công chuỗi cảnh cho ý tưởng: '{enhanced_idea.get('Idea', '')[:30]}...'")
            
            # In mẫu của các cảnh đã tạo
            if enhanced_idea.get("scenes"):
                logger.info(f"Danh sách {len(enhanced_idea.get('scenes', []))} cảnh đã tạo:")
                for i, scene in enumerate(enhanced_idea.get("scenes", [])):
                    logger.info(f"  Cảnh {i+1}: {scene}")
        else:
            logger.warning("Không tạo được chuỗi cảnh nào")
            
        logger.info("=== Kết thúc Quy trình Tạo Chuỗi Cảnh ===")
        
        return enhanced_idea
        
    except Exception as e:
        logger.error(f"Lỗi trong quy trình tạo chuỗi cảnh: {str(e)}")
        raise

if __name__ == "__main__":
    main()
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    