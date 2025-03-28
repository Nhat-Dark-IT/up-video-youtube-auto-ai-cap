#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Script tạo ý tưởng POV về các nhân vật lịch sử Ai Cập cổ đại.
Sử dụng Gemini API để tạo ý tưởng sáng tạo, sau đó lưu vào Google Sheets.
"""

import os
import sys
import json
import time
import logging
import random
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple, Union

# Thêm thư mục gốc của dự án vào đường dẫn tìm kiếm module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import các thư viện AI
import google.generativeai as genai

# Import các module nội bộ
from config import settings, prompt_templates
from utils.google_sheets import GoogleSheetsManager

# Thiết lập logging với UTF-8 encoding để hỗ trợ tiếng Việt
logger = logging.getLogger(__name__)
log_handler = logging.FileHandler(settings.LOG_FILE, encoding='utf-8')
console_handler = logging.StreamHandler(sys.stdout)  # Sử dụng stdout trực tiếp
log_formatter = logging.Formatter(settings.LOG_FORMAT)
log_handler.setFormatter(log_formatter)
console_handler.setFormatter(log_formatter)

logger.setLevel(settings.LOG_LEVEL)
logger.addHandler(log_handler)
logger.addHandler(console_handler)

class IdeaGenerator:
    """
    Lớp tạo ý tưởng POV về các nhân vật lịch sử Ai Cập cổ đại.
    """
    
    def __init__(self):
        """
        Khởi tạo IdeaGenerator với cấu hình từ settings.
        """
        # Khởi tạo Google Sheets manager
        self.sheets_manager = GoogleSheetsManager()
        
        # Cấu hình Gemini API
        if settings.GEMINI_API_KEY:
            genai.configure(api_key=settings.GEMINI_API_KEY)
            self.gemini_available = True
        else:
            logger.warning("Khong tim thay GEMINI_API_KEY. Mot so chuc nang co the khong hoat dong.")
            self.gemini_available = False
    
    def generate_ideas_with_gemini(self, count: int = 5) -> List[Dict[str, Any]]:
        """
        Tạo ý tưởng sử dụng Google Gemini API.
        
        Args:
            count: Số lượng ý tưởng cần tạo
        
        Returns:
            List[Dict]: Danh sách các ý tưởng POV
        """
        if not self.gemini_available:
            logger.error("Khong the su dung Gemini API vi thieu API key")
            return []
        
        try:
            # Tạo prompt với số lượng ý tưởng cần thiết
            prompt = prompt_templates.GENERATE_POV_IDEAS_PROMPT
            
            # Chọn model
            model = genai.GenerativeModel('gemini-2.0-flash-thinking-exp-01-21')
            
            # Gọi API
            logger.info(f"Dang tao {count} y tuong POV voi Gemini API")
            response = model.generate_content(prompt)
            
            if not response.text:
                logger.error("Khong nhan duoc phan hoi tu Gemini API")
                return []
            
            # Xử lý phản hồi để trích xuất ý tưởng
            ideas = self._parse_gemini_response(response.text)
            
            # Giới hạn số lượng ý tưởng
            if len(ideas) > count:
                ideas = ideas[:count]
            
            # Lấy ID tiếp theo từ Google Sheets
            try:
                next_id = self.sheets_manager.get_next_available_id()
            except:
                next_id = 1  # Default nếu không lấy được từ Sheets
            
            # Cập nhật ID cho các ý tưởng
            for i, idea in enumerate(ideas):
                idea["ID"] = str(next_id + i)
            
            logger.info(f"Da tao {len(ideas)} y tuong POV voi Gemini API")
            return ideas
            
        except Exception as e:
            logger.error(f"Loi khi tao y tuong voi Gemini API: {str(e)}")
            return []
    
    def _parse_gemini_response(self, response_text: str) -> List[Dict[str, Any]]:
        """
        Phân tích phản hồi từ Gemini API để lấy danh sách ý tưởng.
        
        Args:
            response_text: Văn bản phản hồi từ API
        
        Returns:
            List[Dict]: Danh sách các ý tưởng đã xử lý
        """
        ideas = []
        
        try:
            # In ra phản hồi đầy đủ để debug
            logger.debug(f"Phan hoi API: {response_text}")
            
            # Xử lý escape sequences
            processed_text = response_text.replace('\\t', '\t')
            
            # Phân tích từng dòng
            lines = processed_text.strip().split('\n')
            
            for i, line in enumerate(lines):
                # Bỏ qua dòng trống
                if not line.strip():
                    continue
                
                # Phân tách theo tab thực sự
                fields = line.split('\t')
                
                # Kiểm tra số trường
                if len(fields) < 7:
                    logger.warning(f"Dong {i+1} khong du truong ({len(fields)}/7): {line}")
                    # Đảm bảo có đủ 7 trường
                    while len(fields) < 7:
                        fields.append("")
                
                # Tạo ý tưởng
                idea = {
                    "ID": fields[0].strip() if fields[0].strip().isdigit() else str(i+1),
                    "Idea": fields[1].strip(),
                    "Hashtag": fields[2].strip() if len(fields) > 2 and fields[2].strip() else "#POV #AncientEgypt #History",
                    "Caption": fields[3].strip() if len(fields) > 3 and fields[3].strip() else "Experience ancient Egypt",
                    "Production": "for production",
                    "Environment_Prompt": fields[5].strip() if len(fields) > 5 and fields[5].strip() else "Ancient Egyptian setting",
                    "Status_Publishing": "pending"
                }
                
                # Đảm bảo Idea bắt đầu bằng "POV:"
                if not idea["Idea"].startswith("POV:"):
                    idea["Idea"] = "POV: " + idea["Idea"]
                
                # Thêm ý tưởng vào danh sách
                ideas.append(idea)
                
                # Log chi tiết ý tưởng
                logger.debug(f"Y tuong {i+1} da duoc phan tich: {idea}")
            
            # Log tổng hợp kết quả
            logger.debug(f"Da phan tich duoc {len(ideas)} y tuong")
            
            return ideas
            
        except Exception as e:
            logger.error(f"Loi khi phan tich phan hoi tu Gemini: {str(e)}")
            return []
    
    def generate_ideas(self, count: int = 5) -> List[Dict[str, Any]]:
        """
        Tạo ý tưởng POV sử dụng Gemini API.
        
        Args:
            count: Số lượng ý tưởng cần tạo
            
        Returns:
            List[Dict]: Danh sách các ý tưởng POV
        """
        # Chỉ sử dụng Gemini, không sử dụng OpenAI
        if self.gemini_available:
            ideas = self.generate_ideas_with_gemini(count)
            if ideas:
                return ideas
        
        # Nếu không thành công, báo lỗi
        logger.error("Khong the tao y tuong voi Gemini API")
        return []
    
    def save_ideas_to_sheets(self, ideas: List[Dict[str, Any]]) -> bool:
        """
        Lưu danh sách ý tưởng vào Google Sheets.
        
        Args:
            ideas: Danh sách ý tưởng cần lưu
            
        Returns:
            bool: True nếu lưu thành công, False nếu có lỗi
        """
        if not ideas:
            logger.warning("Khong co y tuong nao de luu vao Google Sheets")
            return False
        
        try:
            # In ra dữ liệu trước khi gửi lên sheets để debug
            for i, idea in enumerate(ideas):
                logger.debug(f"Du lieu truoc khi gui len sheets ({i+1}): {idea}")
    
            # Đảm bảo các trường quan trọng
            for idea in ideas:
                # Đảm bảo các trường bắt buộc luôn có giá trị
                if not idea.get("Hashtag"):
                    idea["Hashtag"] = "#POV #AncientEgypt #History"
                if not idea.get("Caption"):
                    idea["Caption"] = "Experience ancient Egypt"
                if not idea.get("Production"):
                    idea["Production"] = "for production"
                if not idea.get("Status_Publishing"):
                    idea["Status_Publishing"] = "pending"
            
            # Thêm ý tưởng vào sheets
            success = self.sheets_manager.append_new_ideas(ideas)
            
            if success:
                logger.info(f"Da luu {len(ideas)} y tuong vao Google Sheets")
            else:
                logger.error("Khong the luu y tuong vao Google Sheets")
            
            return success
            
        except Exception as e:
            logger.error(f"Loi khi luu y tuong vao Google Sheets: {str(e)}")
            return False
    
    def process_idea_generation(self, count: int = 5) -> List[Dict[str, Any]]:
        """
        Thực hiện toàn bộ quy trình tạo ý tưởng.
        
        Args:
            count: Số lượng ý tưởng cần tạo
            
        Returns:
            List[Dict]: Danh sách các ý tưởng đã tạo
        """
        # Tạo ý tưởng
        ideas = self.generate_ideas(count)
        
        if not ideas:
            logger.error("Khong the tao y tuong POV")
            return []
        
        # Lưu ý tưởng vào Google Sheets
        success = self.save_ideas_to_sheets(ideas)
        
        if not success:
            logger.warning("Y tuong da duoc tao nhung khong the luu vao Google Sheets")
        
        # Lưu kết quả vào file tạm thời
        try:
            # Đảm bảo thư mục temp tồn tại
            os.makedirs(settings.TEMP_DIR, exist_ok=True)
            
            output_file = os.path.join(settings.TEMP_DIR, "idea_results.json")
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(ideas, f, ensure_ascii=False, indent=2)
            logger.info(f"Da luu ket qua vao file: {output_file}")
        except Exception as e:
            logger.error(f"Khong the luu ket qua vao file tam thoi: {str(e)}")
        
        return ideas

def main():
    """
    Hàm chính để chạy quy trình tạo ý tưởng.
    """
    try:
        logger.info("=== Bat dau Quy trinh Tao Y tuong POV ===")
        
        # Tạo instance của IdeaGenerator
        idea_generator = IdeaGenerator()
        
        # Thực hiện quy trình tạo ý tưởng
        count = settings.MAX_SCENES_PER_VIDEO
        ideas = idea_generator.process_idea_generation(count)
        
        # Tổng kết kết quả
        if ideas:
            logger.info(f"Tao thanh cong {len(ideas)} y tuong POV")
            for i, idea in enumerate(ideas):
                # Hiển thị ý tưởng đầy đủ
                full_idea = idea.get('Idea', '')
                # Cắt bớt nếu quá dài để dễ đọc trong log
                if len(full_idea) > 100:
                    full_idea = full_idea[:100] + "..."
                logger.info(f"Y tuong {i+1}: {full_idea}")
                logger.info(f"  - Hashtag: {idea.get('Hashtag', '')}")
                logger.info(f"  - Caption: {idea.get('Caption', '')}")
                logger.info(f"  - Environment: {idea.get('Environment_Prompt', '')}")
        else:
            logger.error("Khong tao duoc y tuong nao")
        
        logger.info("=== Ket thuc Quy trinh Tao Y tuong POV ===")
        
        return ideas
        
    except Exception as e:
        logger.error(f"Loi trong quy trinh tao y tuong: {str(e)}")
        raise

if __name__ == "__main__":
    main()