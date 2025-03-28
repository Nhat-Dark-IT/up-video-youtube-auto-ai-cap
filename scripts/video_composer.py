#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Script ghép hình ảnh và âm thanh để tạo video hoàn chỉnh về chủ đề Ai Cập cổ đại.
Sử dụng Creatomate API để kết hợp các tài nguyên đã tạo thành video POV có hiệu ứng.
"""

import os
import json
import time
import logging
import requests
import base64
import sys
from typing import List, Dict, Any, Optional, Union
from datetime import datetime
# Thêm vào phần import
import subprocess
# Thêm thư mục gốc vào đường dẫn
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
# Thêm vào phần import
import time
import tempfile
from datetime import datetime, timedelta
# Import các module nội bộ
from config import settings
from utils.google_sheets import GoogleSheetsManager
from utils.google_drive import GoogleDriveManager
from utils.base64_utils import save_base64_to_file

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

class VideoComposer:
    """
    Lớp ghép các tài nguyên hình ảnh và âm thanh để tạo video hoàn chỉnh.
    """
    
    def __init__(self):
        """
        Khởi tạo VideoComposer với cấu hình từ settings.
        """
        # Khởi tạo các managers
        self.sheets_manager = GoogleSheetsManager()
        self.drive_manager = GoogleDriveManager()
        
        # Lấy thông tin cấu hình Creatomate
        self.api_key = settings.CREATOMATE_API_KEY
        self.template_id = settings.CREATOMATE_TEMPLATE_ID
        self.api_url = settings.CREATOMATE_API_URL
        
        # ID thư mục Google Drive để lưu video
        self.drive_folder_id = "1oFc-Wby1Gm5GKwr1Eygg4zzVfIqIlo0Y"
        
        # Thư mục lưu trữ
        self.temp_dir = settings.TEMP_DIR
        
        logger.info("Khởi tạo VideoComposer thành công")
    
    def load_audio_results(self) -> List[Dict[str, Any]]:
        """
        Đọc kết quả tạo âm thanh từ file.
        
        Returns:
            List[Dict]: Danh sách kết quả tạo âm thanh
        """
        try:
            # Ưu tiên đọc từ enhanced_audio_results.json trước
            enhanced_audio_file = os.path.join(self.temp_dir, "enhanced_audio_results.json")
            if os.path.exists(enhanced_audio_file):
                with open(enhanced_audio_file, 'r', encoding='utf-8') as f:
                    audio_results = json.load(f)
                logger.info(f"Đã đọc {len(audio_results)} kết quả âm thanh đã tăng cường")
                return audio_results
            
            # Nếu không có, đọc từ audio_results.json
            audio_file = os.path.join(self.temp_dir, "audio_results.json")
            if not os.path.exists(audio_file):
                logger.warning(f"Không tìm thấy file kết quả âm thanh: {audio_file}")
                return []
            
            with open(audio_file, 'r', encoding='utf-8') as f:
                audio_results = json.load(f)
            
            logger.info(f"Đã đọc {len(audio_results)} kết quả âm thanh")
            return audio_results
            
        except Exception as e:
            logger.error(f"Lỗi khi đọc kết quả âm thanh: {str(e)}")
            return []
    
    def add_caption_to_video_with_image(self, video_path: str, output_path: str, caption: str) -> bool:
        """
        Thêm phụ đề tĩnh vào video bằng cách tạo hình ảnh PNG và chồng lên video.
        Phiên bản cải tiến với phụ đề lớn hơn và khoảng cách tốt hơn.
        
        Args:
            video_path: Đường dẫn đến file video
            output_path: Đường dẫn để lưu video có phụ đề
            caption: Nội dung phụ đề cần hiển thị
            
        Returns:
            bool: True nếu thành công, False nếu thất bại
        """
        try:
            from PIL import Image, ImageDraw, ImageFont
            
            # Tạo hình ảnh phụ đề
            width, height = 1920, 1080  # Tăng chiều cao để chứa font lớn hơn và khoảng cách tốt hơn
            img = Image.new('RGBA', (width, height), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            
            # Vẽ hình nền với độ trong suốt cao hơn để phụ đề nổi bật hơn
            draw.rectangle([(0, height-280), (width, height)], fill=(0, 0, 0, 180))
            
            # Cố gắng tải font hệ thống - sử dụng default nếu không tìm thấy
            try:
                # Tăng kích thước font từ 48 lên 60
                font = ImageFont.truetype("Arial", 500)
            except:
                font = ImageFont.load_default()
            
            # Chuẩn bị văn bản - giới hạn độ dài và chia thành hai dòng nếu cần
            if len(caption) > 50:
                # Chia văn bản thành 2 dòng
                words = caption.split()
                mid_idx = len(words) // 2
                line1 = " ".join(words[:mid_idx])
                line2 = " ".join(words[mid_idx:])
                
                # Vẽ văn bản 2 dòng với font lớn và khoảng cách tăng lên
                # Tăng khoảng cách giữa 2 dòng (từ 70px lên 110px)
                draw.text((width//2, height-100), line1, fill=(255, 255, 255, 255), font=font, anchor="mm")
                draw.text((width//2, height-70), line2, fill=(255, 255, 255, 255), font=font, anchor="mm")
            else:
                # Vẽ văn bản 1 dòng với font lớn hơn
                draw.text((width//2, height-120), caption, fill=(255, 255, 255, 255), font=font, anchor="mm")
            
            # Lưu hình ảnh phụ đề
            subtitle_image = os.path.join(self.temp_dir, f"subtitle_{int(time.time())}.png")
            img.save(subtitle_image)
            
            # Thêm hình ảnh phụ đề vào video
            command = [
                'ffmpeg', '-y',
                '-i', video_path,
                '-i', subtitle_image,
                '-filter_complex', '[0:v][1:v]overlay=0:main_h-overlay_h[outv]',
                '-map', '[outv]',
                '-map', '0:a',
                '-c:a', 'copy',
                output_path
            ]
            
            logger.info(f"Thêm phụ đề lớn dạng hình ảnh vào video: '{caption[:30]}...' nếu dài")
            result = subprocess.run(command, capture_output=True, text=True)
            
            # Xóa file tạm
            if os.path.exists(subtitle_image):
                os.remove(subtitle_image)
            
            if result.returncode != 0:
                logger.error(f"Lỗi khi thêm phụ đề hình ảnh: {result.stderr}")
                # Sao chép video gốc khi có lỗi
                import shutil
                shutil.copy(video_path, output_path)
                logger.warning(f"Sao chép video không có phụ đề do lỗi overlay")
                return False
            
            logger.info(f"Đã thêm phụ đề vào video thành công: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Lỗi khi thêm phụ đề hình ảnh: {str(e)}")
            # Sao chép video gốc khi có lỗi
            try:
                import shutil
                shutil.copy(video_path, output_path)
                logger.warning(f"Sao chép video không có phụ đề sau lỗi: {str(e)}")
                return True
            except:
                return False
        
    def get_media_duration(self, file_path: str) -> float:
        """
        Lấy thời lượng của file media bằng FFmpeg.
        
        Args:
            file_path: Đường dẫn đến file media
            
        Returns:
            float: Thời lượng tính bằng giây hoặc 0 nếu thất bại
        """
        try:
            command = [
                'ffprobe', 
                '-v', 'error', 
                '-show_entries', 'format=duration', 
                '-of', 'default=noprint_wrappers=1:nokey=1', 
                file_path
            ]
            
            result = subprocess.run(command, capture_output=True, text=True)
            if result.returncode == 0:
                duration = float(result.stdout.strip())
                return duration
            else:
                logger.error(f"Lỗi khi lấy thời lượng: {result.stderr}")
                return 0
        except Exception as e:
            logger.error(f"Lỗi khi lấy thông tin thời lượng file: {str(e)}")
            return 0
    def add_subtitles_to_video(video_path: str, subtitle_path: str, output_path: str) -> bool:
        """
        Thêm phụ đề vào video bằng FFmpeg.
        
        Args:
            video_path: Đường dẫn đến file video
            subtitle_path: Đường dẫn đến file phụ đề VTT
            output_path: Đường dẫn để lưu video có phụ đề
            
        Returns:
            bool: True nếu thành công, False nếu thất bại
        """
        try:
            # Tạo lệnh FFmpeg để thêm phụ đề vào video
            command = [
                'ffmpeg', '-y',
                '-i', video_path,
                '-vf', f"subtitles='{subtitle_path}'",
                '-c:a', 'copy',
                output_path
            ]
            
            logger.info(f"Đang thêm phụ đề VTT vào video")
            
            # Thực thi lệnh FFmpeg
            result = subprocess.run(command, capture_output=True, text=True)
            
            if result.returncode != 0:
                logger.error(f"Lỗi khi thêm phụ đề vào video: {result.stderr}")
                
                # Phương pháp dự phòng nếu subtitles filter không hoạt động
                logger.info("Thử phương pháp thay thế với -c:s mov_text codec")
                command_alt = [
                    'ffmpeg', '-y',
                    '-i', video_path,
                    '-i', subtitle_path,
                    '-c:v', 'copy',
                    '-c:a', 'copy',
                    '-c:s', 'mov_text',
                    '-metadata:s:s:0', 'language=eng',
                    output_path
                ]
                
                result_alt = subprocess.run(command_alt, capture_output=True, text=True)
                if result_alt.returncode != 0:
                    logger.error(f"Lỗi phương pháp thay thế: {result_alt.stderr}")
                    
                    # Sao chép file gốc nếu tất cả phương pháp thất bại
                    import shutil
                    shutil.copy(video_path, output_path)
                    logger.warning("Không thể thêm phụ đề, đã sao chép video gốc")
                    return False
            
            logger.info(f"Đã thêm phụ đề vào video thành công: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Lỗi khi thêm phụ đề vào video: {str(e)}")
            return False
        
    def load_video_results(self) -> List[Dict[str, Any]]:
        """
        Đọc kết quả tạo video từ file.
        
        Returns:
            List[Dict]: Danh sách kết quả tạo video
        """
        try:
            video_file = os.path.join(self.temp_dir, "video_results.json")
            if not os.path.exists(video_file):
                # Thử tải kết quả hình ảnh nếu không có video
                logger.warning(f"Không tìm thấy file kết quả video, tìm kiếm kết quả hình ảnh thay thế")
                return self.load_image_results()
            
            with open(video_file, 'r', encoding='utf-8') as f:
                video_results = json.load(f)
            
            logger.info(f"Đã đọc {len(video_results)} kết quả video")
            return video_results
            
        except Exception as e:
            logger.error(f"Lỗi khi đọc kết quả video: {str(e)}")
            return []
    
    def load_scene_sequences(self) -> List[str]:
        """
        Đọc chuỗi cảnh đã được tạo trước đó từ scene_sequence_generator.py.
        
        Returns:
            List[str]: Danh sách các cảnh theo thứ tự
        """
        try:
            scene_file = os.path.join(self.temp_dir, "scene_sequences.json")
            if not os.path.exists(scene_file):
                logger.warning(f"Không tìm thấy file chuỗi cảnh: {scene_file}")
                return []
            
            with open(scene_file, 'r', encoding='utf-8') as f:
                scene_data = json.load(f)
            
            # Kiểm tra xem file có chứa danh sách cảnh không
            if "scenes" in scene_data and isinstance(scene_data["scenes"], list):
                scenes = scene_data["scenes"]
                logger.info(f"Đã đọc {len(scenes)} cảnh từ scene_sequence_generator")
                return scenes
            else:
                logger.warning("File chuỗi cảnh không chứa dữ liệu cảnh hợp lệ")
                return []
                
        except Exception as e:
            logger.error(f"Lỗi khi đọc chuỗi cảnh: {str(e)}")
            return []
    def load_image_results(self) -> List[Dict[str, Any]]:
        """
        Đọc kết quả tạo hình ảnh từ file.
        
        Returns:
            List[Dict]: Danh sách kết quả tạo hình ảnh
        """
        try:
            # Ưu tiên đọc từ enhanced_image_results.json trước
            enhanced_image_file = os.path.join(self.temp_dir, "enhanced_image_results.json")
            if os.path.exists(enhanced_image_file):
                with open(enhanced_image_file, 'r', encoding='utf-8') as f:
                    image_results = json.load(f)
                logger.info(f"Đã đọc {len(image_results)} kết quả hình ảnh đã tăng cường")
                return image_results
            
            # Nếu không có, đọc từ image_results.json
            image_file = os.path.join(self.temp_dir, "image_results.json")
            if not os.path.exists(image_file):
                logger.warning(f"Không tìm thấy file kết quả hình ảnh: {image_file}")
                return []
            
            with open(image_file, 'r', encoding='utf-8') as f:
                image_results = json.load(f)
            
            logger.info(f"Đã đọc {len(image_results)} kết quả hình ảnh")
            return image_results
            
        except Exception as e:
            logger.error(f"Lỗi khi đọc kết quả hình ảnh: {str(e)}")
            return []
    
    def prepare_composition_data(self, video_results: List[Dict[str, Any]], audio_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Chuẩn bị dữ liệu cho quá trình ghép video.
        
        Args:
            video_results: Danh sách kết quả video/hình ảnh
            audio_results: Danh sách kết quả âm thanh
            
        Returns:
            Dict: Dữ liệu đã chuẩn bị cho API Creatomate
        """
        try:
            # Lấy các URL cho các scene
            scene_titles = []
            video_urls = []
            sound_urls = []
            
            # Ưu tiên lấy văn bản cảnh từ scene_sequence_generator
            scene_sequences = self.load_scene_sequences()
            
            # Giới hạn số lượng scene
            max_scenes = min(len(video_results), len(audio_results), settings.MAX_SCENES_PER_VIDEO)
            logger.info(f"Chuẩn bị ghép {max_scenes} cảnh video")
            
            # Xử lý các scene
            for i in range(max_scenes):
                # Lấy văn bản cảnh từ scene_sequences nếu có
                if scene_sequences and i < len(scene_sequences):
                    scene_title = scene_sequences[i].replace("POV:", "").strip()
                    logger.info(f"Sử dụng văn bản cảnh {i+1} từ scene_sequence_generator: '{scene_title[:30]}...'")
                else:
                    # Fallback: Lấy caption hoặc ý tưởng cho tiêu đề
                    scene_title = audio_results[i].get('text', '')
                    if not scene_title and 'original_idea' in video_results[i]:
                        scene_title = video_results[i]['original_idea'].replace('POV:', '').strip()
                    logger.info(f"Fallback: Sử dụng văn bản từ audio/video results: '{scene_title[:30]}...'")
                
                scene_titles.append(scene_title)
                
                # Lấy URL video
                video_url = video_results[i].get('web_content_link', '')
                if not video_url:
                    logger.warning(f"Không tìm thấy URL video cho cảnh {i+1}")
                    return {}
                video_urls.append(video_url)
                
                # Lấy URL âm thanh
                sound_url = audio_results[i].get('web_content_link', '')
                if not sound_url:
                    logger.warning(f"Không tìm thấy URL âm thanh cho cảnh {i+1}")
                    return {}
                sound_urls.append(sound_url)
            
            # Đảm bảo có đủ 5 phần tử cho template
            while len(scene_titles) < 5:
                scene_titles.append("")
            while len(video_urls) < 5:
                video_urls.append(video_urls[-1] if video_urls else "")
            while len(sound_urls) < 5:
                sound_urls.append(sound_urls[-1] if sound_urls else "")
            
            # Tạo payload cho Creatomate API
            composition_data = {
                "template_id": self.template_id,
                "modifications": {
                    "Audio-1.source": sound_urls[0],
                    "Audio-2.source": sound_urls[1],
                    "Audio-3.source": sound_urls[2],
                    "Audio-4.source": sound_urls[3],
                    "Audio-5.source": sound_urls[4],
                    
                    "Video-1.source": video_urls[0],
                    "Video-2.source": video_urls[1],
                    "Video-3.source": video_urls[2],
                    "Video-4.source": video_urls[3],
                    "Video-5.source": video_urls[4],
                    
                    "Text-1.text": scene_titles[0],
                    "Text-2.text": scene_titles[1],
                    "Text-3.text": scene_titles[2],
                    "Text-4.text": scene_titles[3],
                    "Text-5.text": scene_titles[4]
                }
            }
            
            logger.info("Đã chuẩn bị dữ liệu ghép video thành công")
            return composition_data
            
        except Exception as e:
            logger.error(f"Lỗi khi chuẩn bị dữ liệu ghép video: {str(e)}")
            return {}
    
    def create_video_with_creatomate(self, composition_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Gọi Creatomate API để ghép video.
        
        Args:
            composition_data: Dữ liệu đã chuẩn bị cho API
            
        Returns:
            Dict: Kết quả từ API Creatomate
        """
        try:
            # Thiết lập headers API
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
            
            # Gọi API với cơ chế retry
            logger.info("Đang gọi Creatomate API để ghép video...")
            
            for attempt in range(settings.MAX_RETRIES):
                try:
                    response = requests.post(
                        self.api_url,
                        headers=headers,
                        json=composition_data,
                        timeout=60
                    )
                    
                    # Kiểm tra lỗi HTTP
                    response.raise_for_status()
                    
                    # Xử lý phản hồi
                    result = response.json()
                    
                    # Nếu API trả về danh sách kết quả, lấy phần tử đầu tiên
                    if isinstance(result, list) and len(result) > 0:
                        result = result[0]
                        
                    # Kiểm tra xem có ID và URL không
                    if 'id' in result and 'url' in result:
                        status = result.get('status', '')
                        
                        # Ghi nhận job ID 
                        job_id = result.get('id')
                        logger.info(f"Đã nhận được job ID từ Creatomate: {job_id}, trạng thái: {status}")
                        
                        # Nếu là 'planned' hoặc 'processing', đợi hoàn thành
                        if status in ['planned', 'processing']:
                            # Thử đợi và kiểm tra trạng thái
                            max_polling_attempts = 10
                            for polling_attempt in range(max_polling_attempts):
                                logger.info(f"Đang đợi Creatomate hoàn thành xử lý ({polling_attempt+1}/{max_polling_attempts})...")
                                time.sleep(15)  # Đợi 15 giây
                                
                                # Giả sử video đã được tạo, thử tiếp
                                break
                                
                            # Coi như thành công nếu có URL    
                            return result
                        elif status == 'completed':
                            logger.info(f"Creatomate đã xử lý thành công")
                            return result
                        else:
                            logger.warning(f"Trạng thái không mong đợi từ Creatomate: {status}")
                            return result  # Vẫn trả về kết quả để thử tải
                    else:
                        logger.error(f"Phản hồi từ Creatomate thiếu thông tin: {result}")
                        if attempt < settings.MAX_RETRIES - 1:
                            time.sleep(settings.RETRY_DELAY)
                        else:
                            return {'error': 'Phản hồi không đầy đủ từ Creatomate API'}
                
                except requests.exceptions.RequestException as e:
                    logger.error(f"Lỗi kết nối đến Creatomate API (lần thử {attempt+1}/{settings.MAX_RETRIES}): {str(e)}")
                    if attempt < settings.MAX_RETRIES - 1:
                        time.sleep(settings.RETRY_DELAY)
                    else:
                        return {'error': f'Lỗi kết nối: {str(e)}'}
            
            return {'error': f'Không thể kết nối đến Creatomate API sau {settings.MAX_RETRIES} lần thử'}
            
        except Exception as e:
            logger.error(f"Lỗi khi gọi Creatomate API: {str(e)}")
            return {'error': str(e)}
    def add_text_to_video(self, video_path: str, output_path: str, text: str) -> bool:
        """
        Thêm văn bản vào video bằng FFmpeg, sử dụng phương pháp đơn giản nhất.
        
        Args:
            video_path: Đường dẫn đến file video gốc
            output_path: Đường dẫn đến file đầu ra
            text: Văn bản cần hiển thị
            
        Returns:
            bool: True nếu thành công, False nếu thất bại
        """
        try:
            # Đảm bảo thư mục tồn tại
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # Tạo ASS file (Advanced SubStation Alpha) - định dạng phụ đề tiên tiến
            ass_path = os.path.join(self.temp_dir, f"subtitle_{int(time.time())}.ass")
            
            # Tạo nội dung ASS file đơn giản
            ass_content = f"""[Script Info]
    ScriptType: v4.00+
    PlayResX: 1920
    PlayResY: 1080
    
    [V4+ Styles]
    Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
    Style: Default,Arial,28,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,0,0,0,0,100,100,0,0,1,2,0,2,10,10,30,1
    
    [Events]
    Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
    Dialogue: 0,0:00:00.00,0:05:00.00,Default,,0,0,0,,{text}
    """
            
            # Ghi vào file ASS
            with open(ass_path, 'w', encoding='utf-8') as f:
                f.write(ass_content)
                
            # Tạo lệnh FFmpeg để nhúng phụ đề ASS
            command = [
                'ffmpeg', '-y',
                '-i', video_path,
                '-vf', f"ass={ass_path}",
                '-c:a', 'copy',
                output_path
            ]
            
            logger.info(f"Đang thêm văn bản vào video với phương pháp ASS: '{text[:50]}...' nếu dài")
            
            # Thực thi lệnh FFmpeg
            result = subprocess.run(command, capture_output=True, text=True)
            
            # Xóa file tạm thời
            if os.path.exists(ass_path):
                os.remove(ass_path)
                
            if result.returncode != 0:
                logger.error(f"Lỗi khi thêm phụ đề ASS: {result.stderr}")
                
                # Phương pháp dự phòng siêu đơn giản: hardcode text vào video
                simple_command = [
                    'ffmpeg', '-y',
                    '-i', video_path,
                    '-vf', f"drawtext=text='{text}':fontcolor=white:fontsize=24:box=1:boxcolor=black@0.5:x=(w-text_w)/2:y=h-text_h-20",
                    '-c:a', 'copy',
                    output_path
                ]
                
                try:
                    logger.info("Thử phương pháp hardcode text đơn giản")
                    subprocess.run(simple_command, check=True, capture_output=True)
                    logger.info("Phương pháp hardcode text thành công")
                    return True
                except Exception as e:
                    logger.error(f"Lỗi khi sử dụng phương pháp hardcode text: {str(e)}")
                    
                    # Trong trường hợp tất cả phương pháp đều thất bại, chỉ sao chép video
                    try:
                        import shutil
                        shutil.copy(video_path, output_path)
                        logger.info(f"Đã sao chép video không có phụ đề: {output_path}")
                        return True
                    except Exception as copy_error:
                        logger.error(f"Không thể sao chép video: {str(copy_error)}")
                        return False
                    
            logger.info(f"Đã thêm phụ đề vào video thành công: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Lỗi khi thêm phụ đề vào video: {str(e)}")
            
            # Nếu có lỗi, sao chép file gốc
            try:
                import shutil
                shutil.copy(video_path, output_path)
                logger.info(f"Đã sao chép video không có phụ đề sau lỗi: {output_path}")
                return True
            except:
                return False
    def overlay_simple_text(self, video_path: str, output_path: str, text: str) -> bool:
        """
        Thêm văn bản vào video bằng cách tạo overlay rất đơn giản
        
        Args:
            video_path: Đường dẫn đến file video gốc
            output_path: Đường dẫn đến file đầu ra
            text: Văn bản cần hiển thị
            
        Returns:
            bool: True nếu thành công, False nếu thất bại
        """
        try:
            # Rút gọn text nếu quá dài
            short_text = text[:50] + "..." if len(text) > 50 else text
            
            # Lọc bỏ các ký tự đặc biệt
            safe_text = ''.join(c if c.isalnum() or c.isspace() else ' ' for c in short_text)
            
            # Tạo lệnh FFmpeg với filter text rất đơn giản
            command = [
                'ffmpeg', '-y',
                '-i', video_path,
                '-vf', f"drawbox=x=0:y=ih-40:w=iw:h=40:color=black@0.5:t=fill,drawtext=text='{safe_text}':fontcolor=white:fontsize=24:x=(w-tw)/2:y=h-th-10",
                '-c:a', 'copy',
                output_path
            ]
            
            logger.info(f"Đang thêm văn bản đơn giản vào video: '{safe_text}'")
            
            # Thực thi lệnh
            subprocess.run(command, check=True)
            return True
        except Exception as e:
            logger.error(f"Lỗi khi overlay text đơn giản: {str(e)}")
            # Sao chép file gốc nếu thất bại
            try:
                import shutil
                shutil.copy(video_path, output_path)
                return True
            except:
                return False       
    def add_text_to_video_simple(self, video_path: str, output_path: str, text: str) -> bool:
        """
        Phương pháp đơn giản để thêm phụ đề vào video.
        """
        try:
            # Tạo file text tạm thời
            text_file = os.path.join(self.temp_dir, "subtitle.txt")
            with open(text_file, 'w', encoding='utf-8') as f:
                f.write(text)
            
            # Sử dụng FFmpeg với subtitles filter từ file văn bản
            command = [
                'ffmpeg', '-y',
                '-i', video_path,
                '-vf', f"drawtext=fontfile=Arial:fontcolor=white:fontsize=24:bordercolor=black:borderw=1:text='{text}':x=(w-text_w)/2:y=h-text_h-20",
                '-c:a', 'copy',
                output_path
            ]
            
            # Thực thi lệnh
            subprocess.run(command, check=True)
            
            # Xóa file tạm
            if os.path.exists(text_file):
                os.remove(text_file)
                
            return True
        except Exception as e:
            logger.error(f"Lỗi khi thêm phụ đề (phương pháp đơn giản): {str(e)}")
            
            # Nếu thất bại, chỉ sao chép file gốc
            try:
                import shutil
                shutil.copy(video_path, output_path)
                return True
            except:
                return False
    def combine_video_and_audio(self, video_path: str, audio_path: str, output_path: str) -> bool:
        """
        Kết hợp video và âm thanh bằng FFmpeg, đảm bảo độ dài video phù hợp với audio.
        """
        try:
            # Lấy thời lượng của audio và video
            audio_duration = self.get_media_duration(audio_path)
            video_duration = self.get_media_duration(video_path)
            
            if audio_duration <= 0 or video_duration <= 0:
                logger.error(f"Không thể xác định thời lượng audio ({audio_duration}s) hoặc video ({video_duration}s)")
                return False
            
            logger.info(f"Thời lượng audio: {audio_duration:.2f}s, video: {video_duration:.2f}s")
            
            # Tạo đường dẫn tạm thời cho video đã được điều chỉnh
            temp_dir = os.path.dirname(output_path)
            temp_video = os.path.join(temp_dir, f"temp_adjusted_{int(time.time())}.mp4")
            
            # Danh sách files tạm cần xóa sau khi hoàn thành
            temp_files = []
            
            try:
                if abs(audio_duration - video_duration) <= 0.5:
                    # Nếu chênh lệch không đáng kể, sử dụng video gốc
                    adjusted_video_path = video_path
                    logger.info("Độ dài video và audio gần bằng nhau, không cần điều chỉnh")
                elif audio_duration > video_duration:
                    # Trường hợp audio dài hơn video: lặp video hoặc kéo dài video
                    logger.info(f"Audio ({audio_duration:.2f}s) dài hơn video ({video_duration:.2f}s), đang điều chỉnh...")
                    
                    # Tính số lần lặp cần thiết và phần dư
                    repeat_count = int(audio_duration / video_duration)
                    remainder = audio_duration % video_duration
                    
                    if repeat_count <= 1:
                        # Kéo dài video bằng cách làm chậm
                        speed_factor = video_duration / audio_duration
                        command = [
                            'ffmpeg', '-y',
                            '-i', video_path,
                            '-filter:v', f'setpts={1/speed_factor}*PTS',
                            '-an',
                            temp_video
                        ]
                        logger.info(f"Điều chỉnh tốc độ video với hệ số: {speed_factor:.4f}")
                        subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
                    else:
                        # Lặp lại video nhiều lần
                        # Tạo file danh sách tạm thời cho concat
                        concat_list = os.path.join(temp_dir, f"concat_list_{int(time.time())}.txt")
                        temp_files.append(concat_list)
                        
                        # Xử lý phần dư trước nếu cần
                        trim_video = None
                        if remainder > 0:
                            trim_video = os.path.join(temp_dir, f"trim_{int(time.time())}.mp4")
                            temp_files.append(trim_video)
                            
                            trim_command = [
                                'ffmpeg', '-y',
                                '-i', video_path,
                                '-ss', '0',
                                '-t', str(remainder),
                                '-c', 'copy',
                                trim_video
                            ]
                            subprocess.run(trim_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
                        
                        # Ghi file danh sách
                        with open(concat_list, 'w', encoding='utf-8') as f:
                            for _ in range(repeat_count):
                                f.write(f"file '{os.path.abspath(video_path)}'\n")
                            if trim_video:
                                f.write(f"file '{os.path.abspath(trim_video)}'\n")
                        
                        # Ghép nối các đoạn video
                        command = [
                            'ffmpeg', '-y',
                            '-f', 'concat',
                            '-safe', '0',
                            '-i', concat_list,
                            '-c', 'copy',
                            temp_video
                        ]
                        logger.info(f"Lặp lại video {repeat_count} lần và thêm {remainder:.2f}s")
                        subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
                    
                    adjusted_video_path = temp_video
                else:
                    # Trường hợp video dài hơn audio: cắt video
                    logger.info(f"Video ({video_duration:.2f}s) dài hơn audio ({audio_duration:.2f}s), đang cắt...")
                    command = [
                        'ffmpeg', '-y',
                        '-i', video_path,
                        '-t', str(audio_duration),
                        '-c:v', 'copy',
                        '-an',
                        temp_video
                    ]
                    subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
                    adjusted_video_path = temp_video
                
                # Kết hợp video đã điều chỉnh với âm thanh
                command = [
                    'ffmpeg', '-y',
                    '-i', adjusted_video_path,
                    '-i', audio_path,
                    '-map', '0:v',
                    '-map', '1:a',
                    '-c:v', 'copy',
                    output_path
                ]
                
                logger.info(f"Đang kết hợp video và âm thanh: {os.path.basename(video_path)} + {os.path.basename(audio_path)}")
                subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
                
                logger.info(f"Đã kết hợp video và âm thanh thành công: {output_path}")
                return True
                
            finally:
                # Xóa các file tạm
                for temp_file in temp_files:
                    if os.path.exists(temp_file):
                        try:
                            os.remove(temp_file)
                        except:
                            pass
                
                # Xóa file video đã điều chỉnh nếu khác video gốc
                if 'adjusted_video_path' in locals() and adjusted_video_path != video_path and os.path.exists(adjusted_video_path):
                    try:
                        os.remove(adjusted_video_path)
                    except:
                        pass
                
        except subprocess.CalledProcessError as e:
            logger.error(f"Lỗi khi chạy lệnh FFmpeg: {e.stderr if hasattr(e, 'stderr') else str(e)}")
            return False
        except Exception as e:
            logger.error(f"Lỗi khi kết hợp video và âm thanh: {str(e)}")
            return False   
    def concatenate_videos(self, video_paths: List[str], output_path: str) -> bool:
        """
        Ghép nối các video bằng FFmpeg.
        
        Args:
            video_paths: Danh sách đường dẫn đến các file video
            output_path: Đường dẫn đến file đầu ra
            
        Returns:
            bool: True nếu thành công, False nếu thất bại
        """
        try:
            # Tạo file danh sách tạm thời
            list_file_path = os.path.join(self.temp_dir, 'video_list.txt')
            
            with open(list_file_path, 'w', encoding='utf-8') as f:
                for video_path in video_paths:
                    if os.path.exists(video_path):
                        # Sử dụng dạng file syntax của FFmpeg
                        f.write(f"file '{os.path.abspath(video_path)}'\n")
            
            # Tạo lệnh FFmpeg để ghép nối video
            command = [
                'ffmpeg', '-y',
                '-f', 'concat',
                '-safe', '0',
                '-i', list_file_path,
                '-c', 'copy',
                output_path
            ]
            
            logger.info(f"Đang ghép nối {len(video_paths)} video")
            
            # Thực thi lệnh FFmpeg
            result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            # Xóa file danh sách tạm thời
            if os.path.exists(list_file_path):
                os.remove(list_file_path)
            
            if result.returncode != 0:
                logger.error(f"Lỗi khi ghép nối video: {result.stderr.decode('utf-8', errors='ignore')}")
                return False
            
            logger.info(f"Đã ghép nối video thành công: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Lỗi khi ghép nối video: {str(e)}")
            return False
    def download_from_drive(self, file_info: Dict[str, Any], output_path: str) -> bool:
        """
        Tải file từ Google Drive.
        
        Args:
            file_info: Thông tin về file trên Drive
            output_path: Đường dẫn để lưu file
            
        Returns:
            bool: True nếu thành công, False nếu thất bại
        """
        try:
            # Lấy file_id hoặc web_content_link
            file_id = file_info.get('file_id')
            web_content_link = file_info.get('web_content_link')
            
            if file_id:
                # Tải file bằng Google Drive API
                downloaded_path = self.drive_manager.download_file(file_id, output_path)
                return os.path.exists(downloaded_path)
            elif web_content_link:
                # Tải file từ web_content_link
                response = requests.get(web_content_link, timeout=settings.API_TIMEOUT)
                response.raise_for_status()
                
                with open(output_path, 'wb') as f:
                    f.write(response.content)
                    
                return os.path.exists(output_path)
                
            logger.error("Không tìm thấy file_id hoặc web_content_link")
            return False
            
        except Exception as e:
            logger.error(f"Lỗi khi tải file từ Google Drive: {str(e)}")
            return False
    def download_and_process_video(self, creatomate_result: Dict[str, Any]) -> Optional[str]:
        """
        Tải video từ kết quả Creatomate và xử lý nếu cần.
        
        Args:
            creatomate_result: Kết quả từ Creatomate API
            
        Returns:
            str: Đường dẫn đến file video hoặc None nếu thất bại
        """
        try:
            # Kiểm tra kết quả
            if 'error' in creatomate_result:
                logger.error(f"Không thể tải video vì có lỗi trước đó: {creatomate_result['error']}")
                return None
            
            # Lấy URL video từ kết quả
            video_url = creatomate_result.get('url')
            if not video_url:
                logger.error("Không tìm thấy URL video trong kết quả Creatomate")
                return None
            
            logger.info(f"Tìm thấy URL video từ Creatomate: {video_url}")
            
            # Tạo tên file với timestamp
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_filename = settings.FINAL_VIDEO_FILENAME.format(timestamp=timestamp)
            output_path = os.path.join(self.temp_dir, output_filename)
            
            # Tải video - thử nhiều lần vì video có thể đang được tạo
            max_download_attempts = 10
            logger.info(f"Đang cố gắng tải video từ: {video_url}")
            
            for attempt in range(max_download_attempts):
                try:
                    response = requests.get(video_url, timeout=settings.API_TIMEOUT)
                    
                    if response.status_code == 404:
                        # Video đang được tạo, đợi và thử lại
                        logger.info(f"Video đang được tạo, đợi và thử lại ({attempt+1}/{max_download_attempts})...")
                        time.sleep(15)  # Đợi 15 giây
                        continue
                    
                    response.raise_for_status()
                    
                    # Lưu video
                    with open(output_path, 'wb') as f:
                        f.write(response.content)
                        
                    logger.info(f"Đã tải và lưu video thành công: {output_path}")
                    return output_path
                    
                except requests.exceptions.RequestException as e:
                    if "404" in str(e):
                        # Video đang được tạo, đợi và thử lại
                        logger.info(f"Video đang được tạo, đợi và thử lại ({attempt+1}/{max_download_attempts})...")
                        time.sleep(15)  # Đợi 15 giây
                        continue
                    else:
                        logger.error(f"Lỗi khi tải video (lần thử {attempt+1}/{max_download_attempts}): {str(e)}")
                        if attempt < max_download_attempts - 1:
                            time.sleep(settings.RETRY_DELAY)
                        else:
                            return None
            
            logger.error(f"Không thể tải video sau {max_download_attempts} lần thử")
            return None
            
        except Exception as e:
            logger.error(f"Lỗi khi tải và xử lý video: {str(e)}")
            return None

    def delete_individual_videos_from_drive(self, final_video_id: str) -> bool:
        """
        Xóa tất cả video đơn lẻ trên Drive sau khi tạo video ghép thành công,
        ngoại trừ video ghép vừa tải lên.
        
        Args:
            final_video_id: ID của video ghép cuối cùng cần giữ lại
            
        Returns:
            bool: True nếu thành công, False nếu có lỗi
        """
        try:
            # Lấy danh sách tất cả file trong folder
            files = self.drive_manager.list_files_in_folder(self.drive_folder_id)
            
            # Lọc chỉ lấy file video
            video_files = [file for file in files if file.get('mimeType', '').startswith('video/')]
            
            if not video_files:
                logger.info("Không có file video nào cần xóa từ Google Drive")
                return True
            
            logger.info(f"Chuẩn bị xóa các video đơn lẻ từ Google Drive (giữ lại video ghép {final_video_id})")
            
            # Xóa từng file video, trừ video cuối cùng
            success_count = 0
            ignored_count = 0
            
            for file in video_files:
                file_id = file.get('id')
                file_name = file.get('name')
                
                # Bỏ qua video ghép cuối cùng
                if file_id == final_video_id:
                    logger.info(f"Giữ lại video ghép cuối cùng: {file_name} (ID: {file_id})")
                    ignored_count += 1
                    continue
                    
                # Chỉ xóa video đơn lẻ, nhận biết qua tên file
                if "pov_video_" in file_name:
                    try:
                        if self.drive_manager.delete_file(file_id):
                            logger.info(f"Đã xóa video đơn lẻ: {file_name} (ID: {file_id})")
                            success_count += 1
                        else:
                            logger.warning(f"Không thể xóa video đơn lẻ: {file_name} (ID: {file_id})")
                    except Exception as file_error:
                        logger.error(f"Lỗi khi xóa video {file_name}: {str(file_error)}")
                else:
                    logger.info(f"Bỏ qua file không phải video đơn lẻ: {file_name}")
                    ignored_count += 1
            
            logger.info(f"Đã xóa {success_count} video đơn lẻ, giữ lại {ignored_count} video")
            return True
            
        except Exception as e:
            logger.error(f"Lỗi khi xóa video đơn lẻ từ Google Drive: {str(e)}")
            return False
    def upload_final_video_to_drive(self, video_path: str) -> Dict[str, Any]:
        """
        Tải video lên Google Drive.
        
        Args:
            video_path: Đường dẫn đến file video
            
        Returns:
            Dict: Thông tin về video đã tải lên
        """
        try:
            if not os.path.exists(video_path):
                logger.error(f"File video không tồn tại: {video_path}")
                return {}
            
            # Tạo tên file trên Drive
            filename = os.path.basename(video_path)
            
            # Tải lên Google Drive với thư mục cụ thể
            logger.info(f"Đang tải video lên Google Drive: {filename}")
            file_id = self.drive_manager.upload_file(
                file_path=video_path,
                filename=filename,
                mime_type="video/mp4",
                folder_id=self.drive_folder_id
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
                "web_content_link": web_content_link,
                "shared": sharing_success,
                "local_path": video_path,
                "drive_folder_id": self.drive_folder_id
            }
            
            logger.info(f"Đã tải video lên Google Drive thành công: {web_content_link}")
            return result
            
        except Exception as e:
            logger.error(f"Lỗi khi tải video lên Google Drive: {str(e)}")
            return {}
    
    def update_video_link_in_sheets(self, video_info: Dict[str, Any], video_results: List[Dict[str, Any]]) -> bool:
        """
        Cập nhật link video vào Google Sheets ở hàng đầu tiên tìm thấy.
        Cập nhật cả link video ở cột Final_Output và đặt Status Publishing thành "for publishing".
        
        Args:
            video_info: Thông tin video đã tải lên
            video_results: Danh sách kết quả video gốc
                
        Returns:
            bool: True nếu cập nhật thành công, False nếu thất bại
        """
        try:
            if not video_info or 'web_content_link' not in video_info:
                logger.error("Không có thông tin video để cập nhật vào Sheets")
                return False
            
            # Lấy link video cần cập nhật
            video_link = video_info['web_content_link']
            logger.info(f"Chuẩn bị cập nhật link video: {video_link}")
            
            # Lấy tất cả dữ liệu từ sheet
            range_name = f"{self.sheets_manager.sheet_name}!{settings.IDEAS_SHEET_RANGE}"
            values = self.sheets_manager.get_values(range_name)
            
            if not values or len(values) < 2:
                logger.warning(f"Không tìm thấy dữ liệu trong range {range_name}")
                return False
            
            # Tìm vị trí các cột cần cập nhật
            headers = values[0]
            final_output_col_index = None
            status_publishing_col_index = None
            
            for i, header in enumerate(headers):
                if header == "Final_Output":
                    final_output_col_index = i
                    logger.info(f"Tìm thấy cột Final_Output ở vị trí {i}")
                elif header == "Status Publishing" or header == "Status_Publishing":
                    status_publishing_col_index = i
                    logger.info(f"Tìm thấy cột Status Publishing ở vị trí {i}")
            
            # Nếu không tìm thấy cột Final_Output, thử thêm vào
            if final_output_col_index is None:
                headers.append("Final_Output")
                final_output_col_index = len(headers) - 1
                
                # Cập nhật header
                self.sheets_manager.update_values(
                    f"{self.sheets_manager.sheet_name}!A1:{chr(65 + len(headers) - 1)}1",
                    [headers]
                )
                logger.info(f"Đã thêm cột Final_Output ở vị trí {final_output_col_index}")
                
                # Mở rộng các dòng khác
                for i in range(1, len(values)):
                    if len(values[i]) < len(headers):
                        values[i] = values[i] + [''] * (len(headers) - len(values[i]))
            
            # Nếu không tìm thấy cột Status Publishing, thử thêm vào
            if status_publishing_col_index is None:
                headers.append("Status Publishing")
                status_publishing_col_index = len(headers) - 1
                
                # Cập nhật header
                self.sheets_manager.update_values(
                    f"{self.sheets_manager.sheet_name}!A1:{chr(65 + len(headers) - 1)}1",
                    [headers]
                )
                logger.info(f"Đã thêm cột Status Publishing ở vị trí {status_publishing_col_index}")
                
                # Mở rộng các dòng khác
                for i in range(1, len(values)):
                    if len(values[i]) < len(headers):
                        values[i] = values[i] + [''] * (len(headers) - len(values[i]))
            
            # Tìm hàng đầu tiên từ trên xuống để cập nhật
            row_index = None
            id_col_index = headers.index("ID") if "ID" in headers else 0
            
            for i, row in enumerate(values[1:], 1):
                # Kiểm tra nếu hàng có đủ dữ liệu
                if len(row) <= max(id_col_index, final_output_col_index, status_publishing_col_index):
                    row = row + [''] * (max(id_col_index, final_output_col_index, status_publishing_col_index) + 1 - len(row))
                
                # Lấy giá trị hiện tại của cột Final_Output và Status Publishing
                current_final_output = row[final_output_col_index] if final_output_col_index < len(row) else ""
                current_status = row[status_publishing_col_index] if status_publishing_col_index < len(row) else ""
                
                # Nếu Final_Output trống và Status Publishing không phải "published", chọn hàng này
                if not current_final_output and current_status != "published":
                    row_index = i
                    idea_id = row[id_col_index] if id_col_index < len(row) else f"Row_{i+1}"
                    logger.info(f"Đã tìm thấy hàng đầu tiên cần cập nhật: hàng {i+1}, ID: {idea_id}")
                    break
            
            if row_index is None:
                logger.warning("Không tìm thấy hàng nào phù hợp để cập nhật")
                return False
            
            # Cập nhật link video và trạng thái
            row_values = values[row_index]
            
            # Đảm bảo row_values đủ dài
            if len(row_values) <= max(final_output_col_index, status_publishing_col_index):
                row_values = row_values + [''] * (max(final_output_col_index, status_publishing_col_index) + 1 - len(row_values))
            
            # Cập nhật giá trị
            row_values[final_output_col_index] = video_link
            row_values[status_publishing_col_index] = "for publishing"
            
            # Cập nhật dòng vào sheet
            update_range = f"{self.sheets_manager.sheet_name}!A{row_index + 1}:{chr(65 + len(row_values) - 1)}{row_index + 1}"
            update_success = self.sheets_manager.update_values(update_range, [row_values]) > 0
            
            if update_success:
                idea_id = row_values[id_col_index] if id_col_index < len(row_values) else f"Row_{row_index+1}"
                logger.info(f"Đã cập nhật link video và trạng thái 'for publishing' cho hàng {row_index+1} (ID: {idea_id})")
            else:
                logger.error(f"Không thể cập nhật hàng {row_index+1}")
            
            return update_success
            
        except Exception as e:
            logger.error(f"Lỗi khi cập nhật link video vào Google Sheets: {str(e)}")
            return False
    
    def process_video_composition(self) -> Dict[str, Any]:
        """
        Thực hiện toàn bộ quy trình ghép video với FFmpeg.
        
        Returns:
            Dict: Kết quả của quá trình ghép video
        """
        try:
            # Đọc kết quả từ các bước trước
            audio_results = self.load_audio_results()
            video_results = self.load_video_results()
            
            if not audio_results:
                logger.error("Không tìm thấy kết quả âm thanh, không thể tiếp tục")
                return {"success": False, "error": "Không có kết quả âm thanh"}
                
            if not video_results:
                logger.error("Không tìm thấy kết quả video, không thể tiếp tục")
                return {"success": False, "error": "Không có kết quả video"}
            
            # Lấy chuỗi cảnh nếu có
            scenes = self.load_scene_sequences()
            
            # Giới hạn số lượng scene
            max_scenes = min(len(video_results), len(audio_results), settings.MAX_SCENES_PER_VIDEO)
            logger.info(f"Chuẩn bị ghép {max_scenes} cảnh video")
            
            # Xử lý từng cặp video-audio
            temp_video_paths = []
            
            for i in range(max_scenes):
                try:
                    # Lấy văn bản cảnh từ audio để làm phụ đề
                    audio_text = ""
                    if i < len(audio_results):
                        # Ưu tiên sử dụng text từ audio_results
                        audio_text = audio_results[i].get('text', '')
                    
                    # Nếu không có text từ audio, thử dùng scene title
                    if not audio_text and scenes and i < len(scenes):
                        audio_text = scenes[i].replace("POV:", "").strip()
                    elif not audio_text and 'original_idea' in video_results[i]:
                        audio_text = video_results[i]['original_idea'].replace('POV:', '').strip()
                    
                    # Đảm bảo có nội dung phụ đề
                    if not audio_text:
                        audio_text = f"Scene {i+1}"
                    
                    # Tạo các đường dẫn file tạm thời
                    temp_video = os.path.join(self.temp_dir, f"temp_video_{i}.mp4")
                    temp_audio = os.path.join(self.temp_dir, f"temp_audio_{i}.mp3")
                    temp_combined = os.path.join(self.temp_dir, f"temp_combined_{i}.mp4")
                    temp_with_text = os.path.join(self.temp_dir, f"temp_with_text_{i}.mp4")
                    
                    # Tải video và audio
                    if not self.download_from_drive(video_results[i], temp_video) or not self.download_from_drive(audio_results[i], temp_audio):
                        logger.error(f"Không thể tải video hoặc âm thanh cho cảnh {i+1}")
                        continue
                    
                    # Kết hợp video và âm thanh
                    if not self.combine_video_and_audio(temp_video, temp_audio, temp_combined):
                        logger.error(f"Không thể kết hợp video và âm thanh cho cảnh {i+1}")
                        continue
                    
                    # Thêm phụ đề bằng phương pháp hình ảnh
                    success = self.add_caption_to_video_with_image(temp_combined, temp_with_text, audio_text)
                    if not success:
                        logger.warning(f"Không thể thêm phụ đề cho cảnh {i+1}, sử dụng video không phụ đề")
                        import shutil
                        shutil.copy(temp_combined, temp_with_text)
                    
                    # Thêm vào danh sách video để ghép nối
                    temp_video_paths.append(temp_with_text)
                    logger.info(f"Đã xử lý xong cảnh {i+1}: {audio_text[:30]}...")
                    
                except Exception as e:
                    logger.error(f"Lỗi khi xử lý cảnh {i+1}: {str(e)}")
                    continue
            
            if not temp_video_paths:
                logger.error("Không có video nào được xử lý thành công")
                return {"success": False, "error": "Không có video nào được xử lý thành công"}
            
            # Tạo tên file đầu ra với timestamp
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            final_output = os.path.join(self.temp_dir, settings.FINAL_VIDEO_FILENAME.format(timestamp=timestamp))
            
            # Ghép nối các video
            if not self.concatenate_videos(temp_video_paths, final_output):
                logger.error("Không thể ghép nối các video")
                return {"success": False, "error": "Không thể ghép nối các video"}
            
            # Tải video lên Google Drive
            drive_result = self.upload_final_video_to_drive(final_output)
            
            if not drive_result:
                logger.error("Không thể tải video lên Google Drive")
                return {
                    "success": True, 
                    "video_path": final_output,
                    "drive_upload_success": False
                }
            
            # Xóa các video đơn lẻ trên Drive, giữ lại video ghép
            if drive_result.get("file_id"):
                delete_success = self.delete_individual_videos_from_drive(drive_result["file_id"])
                if delete_success:
                    logger.info("Đã xóa các video đơn lẻ từ Google Drive")
                else:
                    logger.warning("Không thể xóa hết các video đơn lẻ từ Google Drive")
            
            # Cập nhật link video vào Google Sheets
            sheets_update = self.update_video_link_in_sheets(drive_result, video_results)
            
            # Xóa các file tạm
            for path in temp_video_paths:
                try:
                    if os.path.exists(path):
                        os.remove(path)
                except Exception:
                    pass
            
            # Lưu kết quả vào file
            result = {
                "success": True,
                "video_path": final_output,
                "drive_result": drive_result,
                "sheets_update_success": sheets_update
            }
            
            # Lưu kết quả vào file JSON
            output_file = os.path.join(self.temp_dir, "composition_result.json")
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
                
            logger.info(f"Đã lưu kết quả ghép video vào: {output_file}")
            
            return result
            
        except Exception as e:
            logger.error(f"Lỗi trong quá trình ghép video: {str(e)}")
            return {"success": False, "error": str(e)}
    def add_simple_caption(self, video_path: str, output_path: str, caption: str) -> bool:
        """
        Phương pháp đơn giản nhất để thêm phụ đề vào video sử dụng drawtext đơn giản.
        
        Args:
            video_path: Đường dẫn đến file video gốc
            output_path: Đường dẫn đến file đầu ra
            caption: Nội dung phụ đề
            
        Returns:
            bool: True nếu thành công, False nếu thất bại
        """
        try:
            # Rút gọn caption để tránh các ký tự đặc biệt
            safe_caption = caption[:50]  # Chỉ lấy 50 ký tự đầu tiên
            safe_caption = ''.join(c if c.isalnum() or c.isspace() else ' ' for c in safe_caption)
            
            # Sử dụng FFmpeg với cấu hình tối giản
            command = [
                'ffmpeg', '-y',
                '-i', video_path,
                '-vf', f"drawbox=y=ih-40:h=40:color=black@0.5:t=fill,drawtext=text='{safe_caption}':fontsize=24:fontcolor=white:x=(w-tw)/2:y=h-20",
                '-c:a', 'copy',
                output_path
            ]
            
            # Thực thi lệnh FFmpeg và bỏ qua output
            subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            # Kiểm tra xem file đã được tạo chưa
            if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                return True
            
            # Sao chép file gốc nếu không thành công
            import shutil
            shutil.copy(video_path, output_path)
            return True
            
        except Exception as e:
            # Sao chép file gốc khi có lỗi
            try:
                import shutil
                shutil.copy(video_path, output_path)
                return True
            except:
                return False
def main():
    """
    Hàm chính để chạy quy trình ghép video.
    """
    try:
        logger.info("=== Bắt đầu Quy trình Ghép Video ===")
        
        # Tạo instance của VideoComposer
        video_composer = VideoComposer()
        
        # Thực hiện quy trình ghép video
        result = video_composer.process_video_composition()
        
        if result.get("success", False):
            video_path = result.get("video_path", "")
            logger.info(f"Đã ghép video thành công: {video_path}")
            
            # Kiểm tra upload lên Drive
            if result.get("drive_result", {}).get("web_content_link"):
                logger.info(f"URL video trên Drive: {result['drive_result']['web_content_link']}")
        else:
            error = result.get("error", "Lỗi không xác định")
            logger.error(f"Không thể ghép video: {error}")
        
        logger.info("=== Kết thúc Quy trình Ghép Video ===")
        
        return result
        
    except Exception as e:
        logger.error(f"Lỗi trong quy trình ghép video: {str(e)}")
        raise

if __name__ == "__main__":
    main()