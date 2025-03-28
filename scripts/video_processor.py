#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Script xử lý hình ảnh thành video có hiệu ứng chuyển động (zoom) cho POV Ai Cập cổ đại.
Sử dụng FFmpeg để tạo hiệu ứng zoom vào từ hình ảnh tĩnh, tạo cảm giác chuyển động.
"""

import os
import json
import time
import logging
import subprocess
import shlex
import tempfile
from pathlib import Path
from typing import List, Dict, Any, Optional, Union, Tuple

# Thêm thư mục gốc vào đường dẫn TRƯỚC khi import modules
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import các module nội bộ
from config import settings
from utils.google_sheets import GoogleSheetsManager
from utils.google_drive import GoogleDriveManager
from utils.ffmpeg_utils import create_zoom_video_from_image
from utils.base64_utils import decode_base64_to_bytes, encode_file_to_base64

# Thiết lập logging
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=settings.LOG_LEVEL,
    format=settings.LOG_FORMAT,
    handlers=[
        logging.FileHandler(settings.LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
    ]
)

class VideoProcessor:
    """
    Lớp xử lý hình ảnh thành video có hiệu ứng zoom.
    """
    
    def __init__(self):
        """
        Khởi tạo VideoProcessor với cấu hình từ settings.
        """
        # Khởi tạo các managers
        self.sheets_manager = GoogleSheetsManager()
        self.drive_manager = GoogleDriveManager()
        
        # Lấy thông tin cấu hình FFmpeg
        self.zoom_filter = settings.FFMPEG_ZOOM_FILTER
        self.video_duration = 5
        self.ffmpeg_codec = settings.FFMPEG_CODEC
        self.pixel_format = settings.FFMPEG_PIXEL_FORMAT
        
        # ID thư mục Google Drive để lưu video
        self.drive_folder_id = "1oFc-Wby1Gm5GKwr1Eygg4zzVfIqIlo0Y"
        
        # Thư mục lưu trữ
        self.temp_dir = settings.TEMP_DIR
        self.images_dir = os.path.join(self.temp_dir, "images")
        self.videos_dir = os.path.join(self.temp_dir, "videos")
        
        # Đảm bảo thư mục tồn tại
        os.makedirs(self.images_dir, exist_ok=True)
        os.makedirs(self.videos_dir, exist_ok=True)
        
        logger.info("Khởi tạo VideoProcessor thành công")
    
    def check_ffmpeg_installed(self) -> bool:
        """
        Kiểm tra FFmpeg đã được cài đặt chưa.
        
        Returns:
            bool: True nếu FFmpeg đã được cài đặt, False nếu chưa
        """
        try:
            result = subprocess.run(['ffmpeg', '-version'], 
                                  stdout=subprocess.PIPE, 
                                  stderr=subprocess.PIPE,
                                  check=False)
            return result.returncode == 0
        except FileNotFoundError:
            logger.error("FFmpeg không được cài đặt trên hệ thống.")
            return False
        except Exception as e:
            logger.error(f"Lỗi khi kiểm tra cài đặt FFmpeg: {str(e)}")
            return False
    
    def load_image_results(self) -> List[Dict[str, Any]]:
        """
        Đọc kết quả tạo hình ảnh từ file hoặc Google Drive.
        
        Returns:
            List[Dict]: Danh sách kết quả tạo hình ảnh
        """
        try:
            # Kiểm tra file từ image_generator - tên đúng là enhanced_image_results.json
            image_file = os.path.join(self.temp_dir, "enhanced_image_results.json")
            if os.path.exists(image_file):
                with open(image_file, 'r', encoding='utf-8') as f:
                    image_results = json.load(f)
                
                logger.info(f"Đã đọc {len(image_results)} kết quả hình ảnh từ file")
                return image_results
            
            # Kiểm tra tên file thay thế
            alt_image_file = os.path.join(self.temp_dir, "image_results.json")
            if os.path.exists(alt_image_file):
                logger.info(f"Sử dụng file thay thế: {alt_image_file}")
                with open(alt_image_file, 'r', encoding='utf-8') as f:
                    image_results = json.load(f)
                
                logger.info(f"Đã đọc {len(image_results)} kết quả hình ảnh từ file thay thế")
                return image_results
            
            # Nếu không tìm thấy file, thử lấy ảnh từ Google Drive
            logger.info("Không tìm thấy file kết quả hình ảnh, thử lấy từ Google Drive")
            drive_images = self.list_images_from_drive()
            
            if drive_images:
                # Chuyển đổi định dạng
                image_results = []
                for i, img in enumerate(drive_images):
                    image_results.append({
                        "file_id": img.get("file_id"),
                        "filename": img.get("filename"),
                        "web_content_link": img.get("web_content_link"),
                        "success": True
                    })
                
                logger.info(f"Đã lấy {len(image_results)} ảnh từ Google Drive")
                return image_results
            
            logger.warning("Không tìm thấy hình ảnh nào để xử lý")
            return []
                
        except Exception as e:
            logger.error(f"Lỗi khi đọc kết quả hình ảnh: {str(e)}")
            return []
    def delete_images_from_drive(self) -> bool:
        """
        Xóa tất cả file ảnh trong thư mục Google Drive sau khi đã tạo video.
        
        Returns:
            bool: True nếu thành công, False nếu có lỗi
        """
        try:
            # Lấy danh sách tất cả file trong folder
            files = self.drive_manager.list_files_in_folder(self.drive_folder_id)
            
            # Lọc chỉ lấy file ảnh
            image_files = [file for file in files if file.get('mimeType', '').startswith('image/')]
            
            if not image_files:
                logger.info("Không có file ảnh nào cần xóa từ Google Drive")
                return True
            
            logger.info(f"Chuẩn bị xóa {len(image_files)} file ảnh từ Google Drive")
            
            # Xóa từng file ảnh
            success_count = 0
            for file in image_files:
                file_id = file.get('id')
                file_name = file.get('name')
                
                try:
                    if self.drive_manager.delete_file(file_id):
                        logger.info(f"Đã xóa file ảnh: {file_name} (ID: {file_id})")
                        success_count += 1
                    else:
                        logger.warning(f"Không thể xóa file ảnh: {file_name} (ID: {file_id})")
                except Exception as file_error:
                    logger.error(f"Lỗi khi xóa file ảnh {file_name}: {str(file_error)}")
            
            logger.info(f"Đã xóa {success_count}/{len(image_files)} file ảnh từ Google Drive")
            return success_count == len(image_files)
        
        except Exception as e:
            logger.error(f"Lỗi khi xóa ảnh từ Google Drive: {str(e)}")
            return False    
    def download_image(self, image_info: Dict[str, Any]) -> Optional[str]:
        """
        Tải hình ảnh từ Google Drive hoặc sử dụng local_path nếu có.
        
        Args:
            image_info: Thông tin về hình ảnh
            
        Returns:
            str: Đường dẫn đến file hình ảnh hoặc None nếu thất bại
        """
        try:
            # Kiểm tra nếu có đường dẫn local
            if "local_path" in image_info and os.path.exists(image_info["local_path"]):
                logger.info(f"Sử dụng file hình ảnh local: {image_info['local_path']}")
                return image_info["local_path"]
            
            # Nếu không, tạo đường dẫn tới thư mục tạm
            filename = image_info.get("filename", f"image_{image_info.get('idea_id', 'unknown')}.png")
            local_path = os.path.join(self.images_dir, filename)
            
            # Kiểm tra nếu file đã tồn tại
            if os.path.exists(local_path):
                logger.info(f"File hình ảnh đã tồn tại: {local_path}")
                return local_path
            
            # Nếu có base64 thì lưu trực tiếp
            if "image_base64" in image_info:
                with open(local_path, 'wb') as f:
                    f.write(decode_base64_to_bytes(image_info["image_base64"]))
                logger.info(f"Đã lưu hình ảnh từ base64: {local_path}")
                return local_path
            
            # Nếu có file_id thì tải từ Google Drive
            if "file_id" in image_info:
                downloaded_path = self.drive_manager.download_file(
                    file_id=image_info["file_id"],
                    output_path=local_path
                )
                if downloaded_path:
                    logger.info(f"Đã tải hình ảnh từ Drive: {downloaded_path}")
                    return downloaded_path
            
            # Nếu có web_content_link thì tải từ URL
            if "web_content_link" in image_info:
                import requests
                response = requests.get(image_info["web_content_link"], timeout=settings.API_TIMEOUT)
                if response.status_code == 200:
                    with open(local_path, 'wb') as f:
                        f.write(response.content)
                    logger.info(f"Đã tải hình ảnh từ URL: {local_path}")
                    return local_path
            
            logger.error(f"Không thể tải hình ảnh: {filename}")
            return None
            
        except Exception as e:
            logger.error(f"Lỗi khi tải hình ảnh: {str(e)}")
            return None
    
    def create_zoom_video(self, image_path: str, output_path: str) -> bool:
        """
        Tạo video từ hình ảnh tĩnh mà không có hiệu ứng zoom.
        Thời lượng video cố định 5 giây.
        
        Args:
            image_path: Đường dẫn đến file hình ảnh
            output_path: Đường dẫn lưu file video
            
        Returns:
            bool: True nếu thành công, False nếu thất bại
        """
        try:
            # Thiết lập lệnh FFmpeg để tạo video từ hình ảnh mà không có hiệu ứng zoom
            # Thời lượng video là 5 giây
            duration = 5  # 5 giây
            
            # Lệnh FFmpeg để giữ nguyên hình ảnh trong 5 giây
            command = [
                'ffmpeg', '-y',
                '-loop', '1',
                '-i', image_path,
                '-c:v', self.ffmpeg_codec,
                '-t', str(duration),
                '-pix_fmt', self.pixel_format,
                '-vf', 'scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2',
                '-r', '30',  # Framerate 30fps
                output_path
            ]
            
            logger.info(f"Đang tạo video từ hình ảnh (không zoom): {image_path}")
            logger.debug(f"Lệnh FFmpeg: {' '.join(command)}")
            
            # Thực thi lệnh
            result = subprocess.run(command, 
                                stdout=subprocess.PIPE, 
                                stderr=subprocess.PIPE,
                                check=False)
            
            # Kiểm tra kết quả
            if result.returncode == 0:
                logger.info(f"Đã tạo video thành công: {output_path}")
                return True
            else:
                error_message = result.stderr.decode('utf-8', errors='ignore')
                logger.error(f"Lỗi khi tạo video: {error_message}")
                return False
                
        except Exception as e:
            logger.error(f"Lỗi khi tạo video: {str(e)}")
            return False
    
    def upload_video_to_drive(self, video_path: str, filename: Optional[str] = None) -> Dict[str, Any]:
        """
        Tải video lên Google Drive và thiết lập quyền chia sẻ.
        
        Args:
            video_path: Đường dẫn đến file video cần tải lên
            filename: Tên file trên Drive (nếu None sẽ dùng tên file gốc)
            
        Returns:
            Dict: Thông tin về video đã tải lên
        """
        try:
            if not os.path.exists(video_path):
                logger.error(f"File video không tồn tại: {video_path}")
                return {}
            
            # Sử dụng tên file gốc nếu không chỉ định
            if filename is None:
                filename = os.path.basename(video_path)
            
            # Tải lên Google Drive - sử dụng folder_id thay vì parent_folder_id
            logger.info(f"Đang tải video lên Google Drive: {filename}")
            file_id = self.drive_manager.upload_file(
                file_path=video_path,
                filename=filename,
                mime_type="video/mp4",
                folder_id=self.drive_folder_id  # Sửa thành folder_id
            )
            
            if not file_id:
                logger.error(f"Không thể tải video lên Google Drive: {filename}")
                return {}
            
            # Thiết lập quyền chia sẻ công khai
            sharing_success = self.drive_manager.share_file(
                file_id=file_id,
                role="reader",
                type="anyone"
            )
            
            # Lấy link truy cập trực tiếp
            web_content_link = self.drive_manager.get_web_content_link(file_id)
            
            # Tạo kết quả
            result = {
                "file_id": file_id,
                "filename": filename,
                "local_path": video_path,
                "web_content_link": web_content_link,
                "shared": sharing_success,
                "drive_folder_id": self.drive_folder_id
            }
            
            logger.info(f"Đã tải video lên Google Drive thành công: {web_content_link}")
            return result
            
        except Exception as e:
            logger.error(f"Lỗi khi tải video lên Google Drive: {str(e)}")
            return {}
    def create_combined_video(self, video_paths: List[str], output_path: str) -> bool:
        """
        Tạo video hoàn chỉnh bằng cách ghép nối nhiều video.
        
        Args:
            video_paths: Danh sách đường dẫn tới các file video
            output_path: Đường dẫn lưu file video đầu ra
            
        Returns:
            bool: True nếu thành công, False nếu thất bại
        """
        try:
            # Tạo file danh sách video tạm thời
            fd, concat_list_path = tempfile.mkstemp(suffix='.txt')
            os.close(fd)
            
            with open(concat_list_path, 'w') as f:
                for video_path in video_paths:
                    if os.path.exists(video_path):
                        # Định dạng theo yêu cầu của FFmpeg concat demuxer
                        f.write(f"file '{video_path}'\n")
            
            # Tạo lệnh FFmpeg để ghép nối video
            command = [
                'ffmpeg', '-y', '-f', 'concat', '-safe', '0',
                '-i', concat_list_path, 
                '-c', 'copy', output_path
            ]
            
            logger.info(f"Đang tạo video hoàn chỉnh từ {len(video_paths)} clip")
            logger.info(f"Lệnh FFmpeg: {' '.join(command)}")
            
            # Thực thi lệnh
            result = subprocess.run(command, 
                                stdout=subprocess.PIPE, 
                                stderr=subprocess.PIPE,
                                check=False)
            
            # Dọn dẹp tệp tạm
            if os.path.exists(concat_list_path):
                os.unlink(concat_list_path)
            
            # Kiểm tra kết quả
            if result.returncode == 0:
                logger.info(f"Đã tạo video hoàn chỉnh thành công: {output_path}")
                return True
            else:
                logger.error(f"Lỗi khi tạo video hoàn chỉnh: {result.stderr.decode('utf-8', errors='ignore')}")
                return False
                
        except Exception as e:
            logger.error(f"Lỗi khi tạo video hoàn chỉnh: {str(e)}")
            return False 
    def list_images_from_drive(self) -> List[Dict[str, Any]]:
        """
        Lấy danh sách các file ảnh từ thư mục Google Drive.
        
        Returns:
            List[Dict]: Danh sách thông tin về các file ảnh
        """
        try:
            # Lấy danh sách tất cả file trong folder
            files = self.drive_manager.list_files_in_folder(self.drive_folder_id)
            
            # Lọc chỉ lấy file ảnh
            image_files = []
            for file in files:
                mime_type = file.get('mimeType', '')
                if mime_type.startswith('image/'):
                    image_files.append({
                        "file_id": file.get('id'),
                        "filename": file.get('name'),
                        "web_content_link": self.drive_manager.get_web_content_link(file.get('id')),
                        "mime_type": mime_type
                    })
            
            logger.info(f"Đã tìm thấy {len(image_files)} file ảnh trên Google Drive")
            return image_files
        
        except Exception as e:
            logger.error(f"Lỗi khi lấy danh sách ảnh từ Google Drive: {str(e)}")
            return []
    def process_single_image(self, image_info: Dict[str, Any], index: int) -> Dict[str, Any]:
        """
        Xử lý một hình ảnh để tạo video và tải lên Drive.
        
        Args:
            image_info: Thông tin về hình ảnh
            index: Chỉ số để đặt tên file
            
        Returns:
            Dict: Kết quả xử lý video
        """
        try:
            # Download hình ảnh nếu cần
            image_path = self.download_image(image_info)
            
            if not image_path:
                logger.error(f"Không thể tải hình ảnh cho xử lý video (index: {index})")
                return {
                    "idea_id": image_info.get("idea_id"),
                    "success": False,
                    "error": "Không thể tải hình ảnh"
                }
            
            # Tạo tên file video
            video_filename = settings.VIDEO_FILENAME_TEMPLATE.format(index=index)
            video_path = os.path.join(self.videos_dir, video_filename)
            
            # Tạo video với hiệu ứng zoom
            success = self.create_zoom_video(image_path, video_path)
            
            if not success:
                return {
                    "idea_id": image_info.get("idea_id"),
                    "success": False,
                    "error": "Không thể tạo video"
                }
            
            # Tải video lên Google Drive
            drive_result = self.upload_video_to_drive(video_path, video_filename)
            
            if not drive_result:
                return {
                    "idea_id": image_info.get("idea_id"),
                    "success": True,
                    "local_path": video_path,
                    "filename": video_filename,
                    "drive_upload_success": False,
                    "error": "Không thể tải lên Google Drive"
                }
            
            # Tạo kết quả
            result = {
                "idea_id": image_info.get("idea_id"),
                "original_prompt": image_info.get("prompt", ""),
                "original_idea": image_info.get("original_idea", ""),
                "original_scene": image_info.get("original_scene", ""),
                "success": True,
                "local_path": video_path,
                "filename": video_filename,
                "drive_upload_success": True,
                **drive_result
            }
            
            logger.info(f"Đã xử lý video thành công cho index {index} (ID: {image_info.get('idea_id')})")
            return result
            
        except Exception as e:
            logger.error(f"Lỗi khi xử lý video cho index {index}: {str(e)}")
            return {
                "idea_id": image_info.get("idea_id"),
                "success": False,
                "error": str(e)
            }
    
    def process_videos(self) -> List[Dict[str, Any]]:
        """
        Xử lý toàn bộ hình ảnh thành video.
        
        Returns:
            List[Dict]: Danh sách kết quả xử lý video
        """
        # Kiểm tra FFmpeg
        if not self.check_ffmpeg_installed():
            logger.error("FFmpeg không được cài đặt, không thể xử lý video")
            return []
        
        # Đọc kết quả hình ảnh
        image_results = self.load_image_results()
        
        if not image_results:
            logger.warning("Không tìm thấy kết quả hình ảnh, không thể xử lý video")
            return []
        
        # Giới hạn số lượng hình ảnh xử lý
        if len(image_results) > settings.MAX_SCENES_PER_VIDEO:
            logger.info(f"Giới hạn còn {settings.MAX_SCENES_PER_VIDEO} hình ảnh")
            image_results = image_results[:settings.MAX_SCENES_PER_VIDEO]
        
        logger.info(f"Đang xử lý video cho {len(image_results)} hình ảnh")
        
        # Xử lý từng hình ảnh
        video_results = []
        video_paths = []
        
        for i, image_info in enumerate(image_results):
            logger.info(f"Đang xử lý video cho hình ảnh {i+1}/{len(image_results)} (ID: {image_info.get('idea_id')})")
            result = self.process_single_image(image_info, i+1)
            video_results.append(result)
            
            if result.get("success", False):
                video_paths.append(result.get("local_path"))
            
            # Thêm độ trễ nhỏ giữa các lần xử lý
            if i < len(image_results) - 1:
                time.sleep(1)
        
        # Tạo video hoàn chỉnh từ tất cả video đã tạo
        if video_paths:
            combined_video_path = os.path.join(self.videos_dir, "combined_pov_video.mp4")
            combined_success = self.create_combined_video(video_paths, combined_video_path)
            
            if combined_success:
                # Tải video hoàn chỉnh lên Google Drive
                combined_result = self.upload_video_to_drive(combined_video_path, "combined_pov_video.mp4")
                
                if combined_result:
                    logger.info(f"Đã tải video hoàn chỉnh lên Google Drive: {combined_result.get('web_content_link')}")
                    # Thêm kết quả video hoàn chỉnh vào danh sách kết quả
                    video_results.append({
                        "type": "combined_video",
                        "filename": "combined_pov_video.mp4",
                        "local_path": combined_video_path,
                        "success": True,
                        "drive_upload_success": True,
                        **combined_result
                    })
        
        # Lưu kết quả vào file tạm thời cho các bước tiếp theo
        output_file = os.path.join(self.temp_dir, "video_results.json")
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(video_results, f, ensure_ascii=False, indent=2)
        
        # Tổng kết
        success_count = sum(1 for r in video_results if r.get("success", False))
        drive_success_count = sum(1 for r in video_results if r.get("drive_upload_success", False))
        
        logger.info(f"Hoàn thành xử lý video: {success_count}/{len(video_results)} thành công")
        logger.info(f"Tải lên Google Drive: {drive_success_count}/{len(video_results)} thành công")
        logger.info(f"Kết quả đã được lưu vào: {output_file}")
        
        return video_results

def main():
    """
    Hàm chính để chạy quy trình xử lý video.
    """
    try:
        logger.info("=== Bắt đầu Quy trình Xử lý Video ===")
        
        # Tạo instance của VideoProcessor
        video_processor = VideoProcessor()
        
        # Thực hiện quy trình xử lý video
        results = video_processor.process_videos()
        
        if not results:
            logger.warning("Không xử lý được video nào")
        else:
            logger.info(f"Đã xử lý thành công {sum(1 for r in results if r.get('success', False))}/{len(results)} video")
            logger.info(f"Tất cả video đã được tải lên thư mục Google Drive: https://drive.google.com/drive/folders/{video_processor.drive_folder_id}")
            
            # Xóa các file ảnh từ Google Drive sau khi đã tạo video
            if video_processor.delete_images_from_drive():
                logger.info("Đã xóa tất cả file ảnh từ Google Drive sau khi tạo video thành công")
            else:
                logger.warning("Có lỗi xảy ra khi xóa file ảnh từ Google Drive")
        
        logger.info("=== Kết thúc Quy trình Xử lý Video ===")
        
        return results
        
    except Exception as e:
        logger.error(f"Lỗi trong quy trình xử lý video: {str(e)}")
        raise

if __name__ == "__main__":
    main()