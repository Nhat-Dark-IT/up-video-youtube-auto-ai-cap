#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Script tăng cường chi tiết cho các cảnh POV để chuẩn bị tạo hình ảnh.
Lấy chuỗi cảnh đã tạo và bổ sung chi tiết để tạo prompt hình ảnh chất lượng cao.
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

class ScenePromptEnhancer:
    """
    Lớp tăng cường chi tiết cho các cảnh POV.
    """
    
    def __init__(self):
        """
        Khởi tạo ScenePromptEnhancer với cấu hình từ settings.
        """
        # Cấu hình Gemini API
        if settings.GEMINI_API_KEY:
            genai.configure(api_key=settings.GEMINI_API_KEY)
            self.gemini_available = True
        else:
            logger.warning("Không tìm thấy GEMINI_API_KEY. Khả năng tăng cường chi tiết có thể bị hạn chế.")
            self.gemini_available = False
            
        # Tải template prompt tạo chi tiết cảnh
        self.detail_template = prompt_templates.SCENE_DETAIL_PROMPT
        
        logger.info("Khởi tạo ScenePromptEnhancer thành công")
    
    def load_scene_sequence(self) -> Dict[str, Any]:
        """
        Đọc chuỗi cảnh từ file kết quả của scene_sequence_generator.
        
        Returns:
            Dict: Ý tưởng với chuỗi cảnh
        """
        try:
            # Đường dẫn file kết quả từ scene_sequence_generator
            input_file = os.path.join(settings.TEMP_DIR, "scene_sequences.json")
            
            # Kiểm tra file tồn tại
            if os.path.exists(input_file):
                with open(input_file, 'r', encoding='utf-8') as f:
                    idea_with_scenes = json.load(f)
                    
                logger.info(f"Đã đọc ý tưởng với {idea_with_scenes.get('scene_count', 0)} cảnh từ file")
                return idea_with_scenes
            else:
                logger.warning(f"Không tìm thấy file chuỗi cảnh: {input_file}")
                return {}
                
        except Exception as e:
            logger.error(f"Lỗi khi đọc file chuỗi cảnh: {str(e)}")
            return {}
    
    def enhance_scene_prompt(self, scene: str, environment_desc: str) -> str:
        """
        Tăng cường chi tiết cho một cảnh cụ thể.
        
        Args:
            scene: Mô tả cảnh gốc
            environment_desc: Mô tả môi trường
            
        Returns:
            str: Prompt chi tiết cho cảnh
        """
        if not self.gemini_available:
            return self._simple_enhance(scene, environment_desc)
            
        try:
            # Chuẩn bị prompt template
            prompt = self.detail_template.replace("{scene_input}", scene)
            prompt = prompt.replace("{environment_desc}", environment_desc)
            
            # Gọi Gemini API
            logger.info(f"Đang tăng cường chi tiết cho cảnh: '{scene[:50]}...'")
            model = genai.GenerativeModel('gemini-1.5-flash')
            response = model.generate_content(prompt)
            
            if not response.text:
                logger.error("Không nhận được phản hồi từ Gemini API")
                return self._simple_enhance(scene, environment_desc)
                
            # Xử lý phản hồi
            enhanced_prompt = response.text.strip()
            
            # Kiểm tra độ dài và cắt ngắn nếu cần
            if len(enhanced_prompt) > 450:
                logger.warning(f"Prompt quá dài ({len(enhanced_prompt)} ký tự), đang cắt ngắn còn 450 ký tự")
                enhanced_prompt = enhanced_prompt[:450]
            
            logger.info(f"Đã tăng cường chi tiết thành công: '{enhanced_prompt[:50]}...'")
            return enhanced_prompt
            
        except Exception as e:
            logger.error(f"Lỗi khi tăng cường chi tiết cảnh: {str(e)}")
            return self._simple_enhance(scene, environment_desc)
    
    def _simple_enhance(self, scene: str, environment_desc: str) -> str:
        """
        Tăng cường đơn giản không sử dụng API.
        
        Args:
            scene: Mô tả cảnh gốc
            environment_desc: Mô tả môi trường
            
        Returns:
            str: Prompt được tăng cường đơn giản
        """
        # Trích xuất nội dung chính từ cảnh
        if scene.startswith("POV:"):
            scene_content = scene[4:].strip()
        else:
            scene_content = scene
            
        # Trích xuất hành động chính
        action_words = ["gripping", "running", "reaching", "holding", "walking", "stumbling", 
                      "climbing", "lifting", "turning", "stepping", "pushing", "pulling"]
                      
        # Tìm từ hành động trong cảnh
        found_action = None
        for action in action_words:
            if action in scene_content.lower():
                found_action = action
                break
                
        if not found_action:
            found_action = "reaching"  # Hành động mặc định
            
        # Tạo phần foreground
        foreground = f"First person view POV GoPro shot of hands {found_action} "
        
        # Tạo phần background
        background = f"In the background, {environment_desc}"
        
        # Kết hợp lại với chi tiết bổ sung
        enhanced_prompt = f"{foreground}{scene_content}. {background}. Hyper-realistic, cinematic quality, 8k resolution, golden hour lighting, detailed textures, immersive perspective."
        
        # Đảm bảo giới hạn 450 ký tự
        if len(enhanced_prompt) > 450:
            enhanced_prompt = enhanced_prompt[:450]
            
        logger.info(f"Đã tạo prompt đơn giản: '{enhanced_prompt[:50]}...'")
        return enhanced_prompt
    
    def process_all_scenes(self) -> Dict[str, Any]:
        """
        Xử lý tất cả các cảnh trong chuỗi và tăng cường chi tiết.
        
        Returns:
            Dict: Ý tưởng với các cảnh đã tăng cường
        """
        # Đọc ý tưởng với chuỗi cảnh
        idea_with_scenes = self.load_scene_sequence()
        
        if not idea_with_scenes or not idea_with_scenes.get("scenes"):
            logger.warning("Không tìm thấy cảnh nào để xử lý")
            return {}
            
        scenes = idea_with_scenes.get("scenes", [])
        environment_desc = idea_with_scenes.get("Environment_Prompt", "Ancient Egyptian setting")
        
        logger.info(f"Đang xử lý {len(scenes)} cảnh để tăng cường chi tiết")
        
        # Tạo chi tiết cho từng cảnh
        enhanced_scenes = []
        for i, scene in enumerate(scenes):
            logger.info(f"Đang xử lý cảnh {i+1}/{len(scenes)}")
            enhanced_prompt = self.enhance_scene_prompt(scene, environment_desc)
            enhanced_scenes.append({
                "original_scene": scene,
                "enhanced_prompt": enhanced_prompt
            })
            
        # Cập nhật ý tưởng với các cảnh đã tăng cường
        idea_with_scenes["enhanced_scenes"] = enhanced_scenes
        
        # Lưu kết quả vào file tạm thời cho các bước tiếp theo
        output_file = os.path.join(settings.TEMP_DIR, "enhanced_scene_prompts.json")
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(idea_with_scenes, f, ensure_ascii=False, indent=2)
            
        logger.info(f"Đã lưu cảnh đã tăng cường vào file: {output_file}")
        
        return idea_with_scenes

def main():
    """
    Hàm chính để chạy quy trình tăng cường chi tiết cảnh.
    """
    try:
        logger.info("=== Bắt đầu Quy trình Tăng cường Chi Tiết Cảnh ===")
        
        # Tạo instance của ScenePromptEnhancer
        enhancer = ScenePromptEnhancer()
        
        # Xử lý tất cả các cảnh
        enhanced_idea = enhancer.process_all_scenes()
        
        if enhanced_idea and enhanced_idea.get("enhanced_scenes"):
            enhanced_scenes = enhanced_idea.get("enhanced_scenes", [])
            logger.info(f"Đã tăng cường thành công {len(enhanced_scenes)} cảnh")
            
            # In mẫu của các cảnh đã tăng cường
            for i, scene_data in enumerate(enhanced_scenes[:2]):  # Chỉ hiển thị 2 cảnh đầu
                logger.info(f"\nCảnh {i+1}:")
                logger.info(f"  Gốc: {scene_data.get('original_scene')}")
                logger.info(f"  Tăng cường: {scene_data.get('enhanced_prompt')}")
        else:
            logger.warning("Không tăng cường được cảnh nào")
            
        logger.info("=== Kết thúc Quy trình Tăng cường Chi Tiết Cảnh ===")
        
        return enhanced_idea
        
    except Exception as e:
        logger.error(f"Lỗi trong quy trình tăng cường chi tiết cảnh: {str(e)}")
        raise

if __name__ == "__main__":
    main()