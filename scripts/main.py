#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Script điều khiển chính cho hệ thống tạo video POV tự động về chủ đề Ai Cập cổ đại.
Điều phối toàn bộ quy trình từ tạo ý tưởng đến đăng tải YouTube.
"""

import os
import sys
import time
import argparse
import logging
import json
from typing import Optional, Dict, Any, List, Callable
from datetime import datetime

# Thêm thư mục gốc của dự án vào sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import cấu hình
from config import settings

# Tiếp tục với các import khác...

# Import các module xử lý trong dự án
from scripts.idea_generator import main as generate_ideas
from scripts.image_generator import main as generate_images
from scripts.video_processor import main as process_videos
from scripts.audio_generator import main as generate_audio
from scripts.video_composer import main as compose_video
from scripts.scene_prompt_enhancer import main as scene_prompt_enhancer
from scripts.youtube_publisher import main as publish_youtube
from scripts.scene_sequence_generator import main as generate_scenes

# Thiết lập logging
logging.basicConfig(
    level=settings.LOG_LEVEL,
    format=settings.LOG_FORMAT,
    handlers=[
        logging.FileHandler(settings.LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Định nghĩa các bước trong quy trình
STEPS = {
    "ideas": {
        "name": "Tạo ý tưởng POV",
        "function": generate_ideas,
        "depends_on": None
    },
    "scenes": {  # Bước mới
        "name": "Tạo chuỗi cảnh",
        "function": generate_scenes,
        "depends_on": "ideas"
    },
    "prompts": {
        "name": "Tăng cường prompt",
        "function": scene_prompt_enhancer,
        "depends_on": "scenes"  # Đã thay đổi: phụ thuộc vào scenes thay vì ideas
    },
    "images": {
        "name": "Tạo hình ảnh",
        "function": generate_images,
        "depends_on": "prompts"
    },
    "videos": {
        "name": "Xử lý video",
        "function": process_videos,
        "depends_on": "images"
    },
    "audio": {
        "name": "Tạo âm thanh",
        "function": generate_audio,
        "depends_on": "scenes"  # Đã thay đổi: phụ thuộc vào scenes thay vì ideas
    },
    "compose": {
        "name": "Ghép video",
        "function": compose_video,
        "depends_on": ["videos", "audio"]
    },
    "publish": {
        "name": "Đăng tải YouTube",
        "function": publish_youtube,
        "depends_on": "compose"
    }
}

def setup_environment() -> None:
    """
    Thiết lập môi trường làm việc, tạo các thư mục cần thiết.
    """
    try:
        # Tạo thư mục temp và các thư mục con
        os.makedirs(settings.TEMP_DIR, exist_ok=True)
        os.makedirs(os.path.join(settings.TEMP_DIR, "images"), exist_ok=True)
        os.makedirs(os.path.join(settings.TEMP_DIR, "videos"), exist_ok=True)
        os.makedirs(os.path.join(settings.TEMP_DIR, "audio"), exist_ok=True)
        
        # Tạo thư mục logs và credentials
        os.makedirs(settings.LOGS_DIR, exist_ok=True)
        os.makedirs(settings.CREDENTIALS_DIR, exist_ok=True)
        
        logger.info("Đã thiết lập môi trường làm việc thành công")
    except Exception as e:
        logger.error(f"Lỗi khi thiết lập môi trường làm việc: {str(e)}")
        raise

def clean_temp_directory() -> bool:
    """
    Xóa tất cả các file trong thư mục temp để bắt đầu quy trình mới.
    
    Returns:
        bool: True nếu thành công, False nếu có lỗi
    """
    try:
        if not os.path.exists(settings.TEMP_DIR):
            logger.warning(f"Thư mục temp không tồn tại: {settings.TEMP_DIR}")
            return True
        
        # Đếm tổng số file
        total_files = 0
        for root, dirs, files in os.walk(settings.TEMP_DIR):
            total_files += len(files)
        
        if total_files == 0:
            logger.info(f"Không có file nào trong thư mục temp")
            return True
        
        # Xóa từng file
        deleted_count = 0
        for root, dirs, files in os.walk(settings.TEMP_DIR):
            for file in files:
                file_path = os.path.join(root, file)
                try:
                    os.remove(file_path)
                    deleted_count += 1
                    logger.debug(f"Đã xóa file: {file_path}")
                except Exception as file_error:
                    logger.error(f"Không thể xóa file {file_path}: {str(file_error)}")
        
        logger.info(f"Đã xóa {deleted_count}/{total_files} file trong thư mục temp")
        return deleted_count == total_files
        
    except Exception as e:
        logger.error(f"Lỗi khi xóa files trong thư mục temp: {str(e)}")
        return False

def run_step(step_id: str, retry_count: int = 1) -> Optional[Any]:
    """
    Chạy một bước trong quy trình tạo video.
    
    Args:
        step_id: ID của bước cần chạy
        retry_count: Số lần thử lại nếu bước thất bại
        
    Returns:
        Kết quả của bước hoặc None nếu thất bại
    """
    step = STEPS.get(step_id)
    if not step:
        logger.error(f"Không tìm thấy bước với ID: {step_id}")
        return None
    
    logger.info(f"=== Bắt đầu bước: {step['name']} ({step_id}) ===")
    
    # Kiểm tra các điều kiện tiên quyết
    if step["depends_on"]:
        depends = step["depends_on"]
        if isinstance(depends, str):
            depends = [depends]
        
        for dep in depends:
            dep_result_file = os.path.join(settings.TEMP_DIR, f"{dep}_result.json")
            if not os.path.exists(dep_result_file):
                logger.warning(f"Không tìm thấy kết quả của bước {dep}, bước {step_id} có thể sẽ không hoạt động đúng")
    
    # Thực hiện bước với retry
    for attempt in range(retry_count):
        try:
            logger.info(f"Đang thực hiện bước {step_id} (lần thử {attempt + 1}/{retry_count})")
            result = step["function"]()
            
            # Lưu kết quả vào file nếu result là dict hoặc list
            if result and (isinstance(result, dict) or isinstance(result, list)):
                result_file = os.path.join(settings.TEMP_DIR, f"{step_id}_result.json")
                with open(result_file, 'w', encoding='utf-8') as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)
                logger.info(f"Đã lưu kết quả của bước {step_id} vào file {result_file}")
            
            logger.info(f"=== Kết thúc bước: {step['name']} ({step_id}) - Thành công ===")
            return result
            
        except Exception as e:
            logger.error(f"Lỗi khi thực hiện bước {step_id} (lần thử {attempt + 1}/{retry_count}): {str(e)}")
            if attempt < retry_count - 1:
                wait_time = settings.RETRY_DELAY * (attempt + 1)
                logger.info(f"Thử lại sau {wait_time} giây...")
                time.sleep(wait_time)
            else:
                logger.error(f"=== Kết thúc bước: {step['name']} ({step_id}) - Thất bại sau {retry_count} lần thử ===")
                return None

def run_pipeline(start_step: Optional[str] = None, end_step: Optional[str] = None, retry_count: int = 2, clean_temp: bool = True) -> Dict[str, Any]:
    """
    Chạy toàn bộ hoặc một phần của quy trình tạo video.
    
    Args:
        start_step: Bước bắt đầu (chạy từ đầu nếu None)
        end_step: Bước kết thúc (chạy đến cuối nếu None)
        retry_count: Số lần thử lại mỗi bước nếu thất bại
        clean_temp: Xóa thư mục temp trước khi bắt đầu
        
    Returns:
        Dict: Kết quả của toàn bộ quy trình
    """
    # Thiết lập môi trường
    setup_environment()
    
    # Xóa thư mục temp nếu cần
    if clean_temp and start_step == "ideas":
        logger.info("Xóa thư mục temp trước khi bắt đầu quy trình mới")
        clean_temp_directory()
    
    # Xác định các bước cần chạy
    steps_to_run = list(STEPS.keys())
    
    if start_step and start_step in steps_to_run:
        start_index = steps_to_run.index(start_step)
        steps_to_run = steps_to_run[start_index:]
    
    if end_step and end_step in steps_to_run:
        end_index = steps_to_run.index(end_step)
        steps_to_run = steps_to_run[:end_index + 1]
    
    # Ghi log bắt đầu
    logger.info(f"=== Bắt đầu quy trình tạo video POV (từ {steps_to_run[0]} đến {steps_to_run[-1]}) ===")
    start_time = time.time()
    
    # Chạy từng bước
    results = {}
    success_count = 0
    
    for step_id in steps_to_run:
        result = run_step(step_id, retry_count)
        results[step_id] = {"success": result is not None}
        
        if result is not None:
            success_count += 1
        elif settings.STOP_ON_ERROR:
            logger.error(f"Dừng quy trình do bước {step_id} thất bại")
            break
    
    # Ghi log kết thúc
    end_time = time.time()
    duration = end_time - start_time
    
    logger.info(f"=== Kết thúc quy trình tạo video POV ===")
    logger.info(f"Thời gian thực hiện: {duration:.2f} giây ({duration/60:.2f} phút)")
    logger.info(f"Kết quả: {success_count}/{len(steps_to_run)} bước thành công")
    
    # Tạo bản tóm tắt
    summary = {
        "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        "duration": duration,
        "steps_total": len(steps_to_run),
        "steps_success": success_count,
        "results": results
    }
    
    # Lưu tóm tắt vào file
    summary_file = os.path.join(settings.TEMP_DIR, "pipeline_summary.json")
    with open(summary_file, 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    
    return summary

def parse_arguments():
    """
    Phân tích tham số dòng lệnh.
    
    Returns:
        argparse.Namespace: Tham số đã phân tích
    """
    parser = argparse.ArgumentParser(description='Hệ thống tạo video POV tự động về Ai Cập cổ đại')
    
    parser.add_argument('--step', type=str, choices=STEPS.keys(),
                        help='Chạy một bước cụ thể')
    
    parser.add_argument('--start', type=str, choices=STEPS.keys(),
                        help='Bắt đầu quy trình từ bước này')
    
    parser.add_argument('--end', type=str, choices=STEPS.keys(),
                        help='Kết thúc quy trình ở bước này')
    
    parser.add_argument('--retry', type=int, default=2,
                        help='Số lần thử lại cho mỗi bước (mặc định: 2)')
    
    parser.add_argument('--all', action='store_true',
                        help='Chạy toàn bộ quy trình')
    
    parser.add_argument('--keep-temp', action='store_true',
                        help='Không xóa thư mục temp trước khi bắt đầu')
    
    return parser.parse_args()

def main():
    """
    Hàm chính điều khiển toàn bộ quy trình.
    """
    args = parse_arguments()
    
    try:
        if args.step:
            # Chạy một bước cụ thể
            logger.info(f"Chạy bước đơn lẻ: {args.step}")
            result = run_step(args.step, args.retry)
            return result is not None
            
        elif args.all or (args.start or args.end):
            # Chạy quy trình từ start đến end
            logger.info(f"Chạy quy trình từ '{args.start or 'đầu'}' đến '{args.end or 'cuối'}'")
            summary = run_pipeline(args.start, args.end, args.retry, not args.keep_temp)
            return summary["steps_success"] == summary["steps_total"]
            
        else:
            # Hiển thị hướng dẫn sử dụng nếu không có tham số
            logger.info("Không có tham số, hiển thị hướng dẫn sử dụng")
            print("\nCách sử dụng HỆ THỐNG TẠO VIDEO POV TỰ ĐỘNG:")
            print("================================================")
            print("  python main.py --all                     # Chạy toàn bộ quy trình")
            print("  python main.py --step ideas              # Chạy bước tạo ý tưởng")
            print("  python main.py --step publish            # Chỉ đăng tải lên YouTube")
            print("  python main.py --start images --end compose  # Chạy từ tạo hình ảnh đến ghép video")
            print("  python main.py --all --keep-temp         # Chạy quy trình không xóa thư mục temp")
            print("================================================")
            return True
            
    except Exception as e:
        logger.error(f"Lỗi không xử lý được trong quy trình chính: {str(e)}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)