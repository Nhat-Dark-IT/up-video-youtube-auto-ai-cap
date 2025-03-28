#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Script đăng tải video POV về Ai Cập cổ đại lên YouTube.
Sử dụng YouTube API để tải lên video đã tạo và thiết lập metadata.
"""

import os
import json
import time
import logging
import googleapiclient.discovery
import googleapiclient.errors
import googleapiclient.http
from datetime import datetime
from typing import List, Dict, Any, Optional, Union
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import sys

# Thêm thư mục gốc vào đường dẫn
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import các module nội bộ
from config import settings
from utils.google_sheets import GoogleSheetsManager
from utils.google_drive import GoogleDriveManager

# Thiết lập logging với UTF-8 cho hỗ trợ tiếng Việt
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=settings.LOG_LEVEL,
    format=settings.LOG_FORMAT,
    handlers=[
        logging.FileHandler(settings.LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
    ]
)

class YouTubePublisher:
    """
    Lớp quản lý việc đăng tải video lên YouTube.
    """
    
    def __init__(self):
        """
        Khởi tạo YouTubePublisher với cấu hình từ settings.
        """
        # Khởi tạo các managers
        self.sheets_manager = GoogleSheetsManager()
        self.drive_manager = GoogleDriveManager()
        
        # Thư mục lưu trữ
        self.temp_dir = settings.TEMP_DIR
        
        # Đảm bảo thư mục credentials tồn tại
        if not os.path.exists(settings.CREDENTIALS_DIR):
            os.makedirs(settings.CREDENTIALS_DIR, exist_ok=True)
        
        # ID thư mục Google Drive chứa video
        self.drive_folder_id = "1oFc-Wby1Gm5GKwr1Eygg4zzVfIqIlo0Y"
        
        # Thiết lập YouTube API
        self._youtube = None
        self.client_id = settings.YOUTUBE_CLIENT_ID
        self.client_secret = settings.YOUTUBE_CLIENT_SECRET
        self.refresh_token = settings.YOUTUBE_REFRESH_TOKEN
        
        logger.info("Khởi tạo YouTubePublisher thành công")
    
    @property
    def youtube(self):
        """
        Truy cập tới service YouTube API, khởi tạo nếu cần.
        Ưu tiên sử dụng token đã lưu trước đó.
        
        Returns:
            googleapiclient.discovery.Resource: Service YouTube API
        """
        if self._youtube is None:
            try:
                # Đường dẫn đến file token
                token_file = os.path.join(settings.CREDENTIALS_DIR, 'youtube_token.json')
                
                # Kiểm tra nếu token file tồn tại
                if os.path.exists(token_file):
                    logger.info(f"Đang sử dụng token từ file: {token_file}")
                    
                    with open(token_file, 'r') as f:
                        token_data = json.load(f)
                    
                    # Tạo credentials từ token data
                    credentials = Credentials.from_authorized_user_info(
                        token_data, 
                        scopes=["https://www.googleapis.com/auth/youtube.upload"]
                    )
                    
                    # Nếu token hết hạn, làm mới nó
                    if credentials.expired and credentials.refresh_token:
                        logger.info("Token hết hạn, đang làm mới...")
                        credentials.refresh(Request())
                        
                        # Lưu token đã làm mới
                        with open(token_file, 'w') as f:
                            token_json = credentials.to_json()
                            f.write(token_json)
                        logger.info("Đã làm mới và lưu token")
                
                # Nếu không có token file, thử dùng client secret
                else:
                    # Xác định đường dẫn đến file client secret
                    client_secret_file = 'client_secret_606032748089-3fkpfi3tg094atrhp3b92nd8cda8623c.apps.googleusercontent.com.json'
                    
                    if not os.path.exists(client_secret_file):
                        client_secret_file = os.path.join(settings.CREDENTIALS_DIR, 'client_secret.json')
                    
                    logger.info(f"Sử dụng file client secret: {client_secret_file}")
                    
                    # Tạo flow xác thực
                    flow = InstalledAppFlow.from_client_secrets_file(
                        client_secret_file,
                        scopes=["https://www.googleapis.com/auth/youtube.upload"]
                    )
                    
                    # Chạy flow xác thực
                    credentials = flow.run_local_server(port=0)
                    logger.info("Đã xác thực thành công qua trình duyệt local")
                    
                    # Lưu token để sử dụng lần sau
                    with open(token_file, 'w') as f:
                        f.write(credentials.to_json())
                    logger.info(f"Đã lưu token vào: {token_file}")
                
                # Khởi tạo service YouTube API
                self._youtube = googleapiclient.discovery.build(
                    "youtube", "v3", credentials=credentials, cache_discovery=False
                )
                logger.info("Đã khởi tạo kết nối thành công tới YouTube API")
                    
            except Exception as e:
                logger.error(f"Lỗi khi khởi tạo kết nối tới YouTube API: {str(e)}")
                raise
                
        return self._youtube
    
    def load_composition_result(self) -> Dict[str, Any]:
        """
        Đọc kết quả của bước ghép video từ file.
        
        Returns:
            Dict: Kết quả ghép video hoặc dict rỗng nếu có lỗi
        """
        try:
            result_file = os.path.join(self.temp_dir, "composition_result.json")
            if not os.path.exists(result_file):
                logger.warning(f"Không tìm thấy file kết quả ghép video: {result_file}")
                return {}
            
            with open(result_file, 'r', encoding='utf-8') as f:
                result = json.load(f)
            
            logger.info(f"Đã đọc kết quả ghép video từ {result_file}")
            return result
        except Exception as e:
            logger.error(f"Lỗi khi đọc file kết quả ghép video: {str(e)}")
            return {}
    
    def find_latest_video_from_drive(self) -> Optional[Dict[str, Any]]:
        """
        Tìm video mới nhất trong thư mục Google Drive.
        
        Returns:
            Dict: Thông tin về video mới nhất hoặc None nếu không tìm thấy
        """
        try:
            # Lấy danh sách tất cả file trong thư mục
            files = self.drive_manager.list_files_in_folder(self.drive_folder_id)
            
            # Lọc và sắp xếp các file video theo thời gian tạo (mới nhất đầu tiên)
            video_files = [
                file for file in files 
                if file.get('mimeType', '').startswith('video/') and 
                'final_video_' in file.get('name', '')
            ]
            
            if not video_files:
                logger.warning("Không tìm thấy file video nào trong thư mục Google Drive")
                return None
            
            # Sắp xếp theo thời gian tạo (mới nhất đầu tiên)
            video_files.sort(key=lambda x: x.get('createdTime', ''), reverse=True)
            
            latest_video = video_files[0]
            file_id = latest_video.get('id')
            filename = latest_video.get('name')
            
            # Lấy webContentLink
            web_content_link = self.drive_manager.get_web_content_link(file_id)
            
            video_info = {
                "file_id": file_id,
                "filename": filename,
                "web_content_link": web_content_link,
                "from_drive": True
            }
            
            logger.info(f"Đã tìm thấy video mới nhất trên Drive: {filename} (ID: {file_id})")
            return video_info
        
        except Exception as e:
            logger.error(f"Lỗi khi tìm video mới nhất từ Drive: {str(e)}")
            return None
    
    def download_video_from_drive(self, video_info: Dict[str, Any]) -> Optional[str]:
        """
        Tải video từ Google Drive về máy local.
        
        Args:
            video_info: Thông tin về video trên Drive
            
        Returns:
            str: Đường dẫn đến file video đã tải về hoặc None nếu thất bại
        """
        try:
            file_id = video_info.get("file_id")
            filename = video_info.get("filename")
            
            if not file_id:
                logger.error("Không có file_id để tải video từ Drive")
                return None
            
            # Đường dẫn để lưu file
            output_path = os.path.join(self.temp_dir, filename)
            
            # Tải file từ Drive
            downloaded_path = self.drive_manager.download_file(
                file_id=file_id,
                output_path=output_path
            )
            
            if downloaded_path:
                logger.info(f"Đã tải video từ Drive: {downloaded_path}")
                return downloaded_path
            else:
                logger.error(f"Không thể tải video từ Drive: {file_id}")
                return None
                
        except Exception as e:
            logger.error(f"Lỗi khi tải video từ Drive: {str(e)}")
            return None
    
    def get_video_for_publishing(self) -> Optional[Dict[str, Any]]:
        """
        Lấy thông tin video cần đăng tải lên YouTube.
        
        Returns:
            Dict: Thông tin về video cần đăng tải hoặc None nếu không tìm thấy
        """
        try:
            # Thử đọc kết quả ghép video trước
            composition_result = self.load_composition_result()
            
            if composition_result and composition_result.get("success", False):
                # Lấy đường dẫn video từ kết quả ghép
                video_path = composition_result.get("video_path")
                
                # Kiểm tra file có tồn tại không
                if video_path and os.path.exists(video_path):
                    logger.info(f"Đã tìm thấy video local từ kết quả ghép: {video_path}")
                    
                    # Lấy thông tin Drive từ kết quả
                    drive_result = composition_result.get("drive_result", {})
                    
                    return {
                        "local_path": video_path,
                        "file_id": drive_result.get("file_id"),
                        "filename": os.path.basename(video_path),
                        "web_content_link": drive_result.get("web_content_link")
                    }
                else:
                    logger.warning(f"File video local không tồn tại: {video_path}")
            else:
                logger.warning("Không tìm thấy kết quả ghép video thành công")
            
            # Nếu không tìm thấy từ kết quả ghép, thử tìm từ Drive
            video_info = self.find_latest_video_from_drive()
            
            if not video_info:
                logger.error("Không tìm thấy video nào để đăng tải")
                return None
            
            # Tải video từ Drive nếu cần
            local_path = self.download_video_from_drive(video_info)
            
            if local_path:
                video_info["local_path"] = local_path
                return video_info
            else:
                logger.error("Không thể tải video từ Drive")
                return None
                
        except Exception as e:
            logger.error(f"Lỗi khi lấy video cho đăng tải: {str(e)}")
            return None
    
    def get_publishing_ideas(self) -> List[Dict[str, Any]]:
        """
        Lấy danh sách các ý tưởng cần đăng tải lên YouTube.
        
        Returns:
            List[Dict]: Danh sách các ý tưởng cần xuất bản
        """
        try:
            # Lấy ý tưởng từ Google Sheets
            ideas = self.sheets_manager.get_ideas_for_publishing()
            
            if not ideas:
                logger.warning("Không tìm thấy ý tưởng nào ở trạng thái 'for publishing', sẽ không đăng tải")
                return []
            else:
                logger.info(f"Đã tìm thấy {len(ideas)} ý tưởng cần xuất bản")
            
            return ideas
        except Exception as e:
            logger.error(f"Lỗi khi lấy ý tưởng cần xuất bản: {str(e)}")
            return []
    
    def prepare_video_metadata(self, idea: Dict[str, Any]) -> Dict[str, Any]:
        """
        Chuẩn bị metadata cho video dựa trên ý tưởng.
        
        Args:
            idea: Thông tin ý tưởng
            
        Returns:
            Dict: Metadata cho việc tải video lên YouTube
        """
        try:
            # Lấy thông tin cần thiết từ ý tưởng
            pov_idea = idea.get("Idea", "").replace("POV:", "").strip()
            hashtags = idea.get("Hashtag", "").strip()
            caption = idea.get("Caption", "").strip()
            
            # Tạo tiêu đề video
            title = f"POV: {pov_idea[:80]}" if len(pov_idea) > 0 else "Ancient Egypt POV Experience"
            
            # Tạo mô tả video
            description = f"""POV Experience: {pov_idea}

{caption}

Experience ancient Egypt through the eyes of its people. This immersive first-person POV video takes you back in time to witness the wonders of ancient Egyptian civilization.

#AncientEgypt #POV #HistoryExperience {hashtags}
"""
            
            # Tạo tags
            tags = ["Ancient Egypt", "POV", "History", "Experience"]
            if hashtags:
                # Thêm hashtags vào tags, loại bỏ dấu # và khoảng trắng
                tags.extend([tag.strip().replace('#', '') for tag in hashtags.split() if tag.strip()])
            
            # Tạo metadata
            metadata = {
                "title": title,
                "description": description,
                "tags": tags,
                "categoryId": "22",  # People & Blogs
                "privacyStatus": "public"
            }
            
            logger.info(f"Đã chuẩn bị metadata cho video: {title}")
            return metadata
        except Exception as e:
            logger.error(f"Lỗi khi chuẩn bị metadata video: {str(e)}")
            return {
                "title": "Ancient Egypt POV Experience",
                "description": "Experience the wonders of ancient Egypt in first-person view.",
                "tags": ["Ancient Egypt", "POV", "History"],
                "categoryId": "22",
                "privacyStatus": "public"
            }
    
    def upload_video_to_youtube(self, video_path: str, metadata: Dict[str, Any]) -> Optional[str]:
        """
        Tải video lên YouTube với metadata đã chuẩn bị.
        
        Args:
            video_path: Đường dẫn tới file video
            metadata: Metadata cho video
            
        Returns:
            str: ID của video đã tải lên hoặc None nếu thất bại
        """
        if not os.path.exists(video_path):
            logger.error(f"File video không tồn tại: {video_path}")
            return None
        
        # Chuẩn bị body request
        body = {
            "snippet": {
                "title": metadata["title"],
                "description": metadata["description"],
                "tags": metadata["tags"],
                "categoryId": metadata["categoryId"]
            },
            "status": {
                "privacyStatus": metadata["privacyStatus"],
                "selfDeclaredMadeForKids": False
            }
        }
        
        # Tạo media upload request
        try:
            # Khởi tạo insert request
            insert_request = self.youtube.videos().insert(
                part=",".join(body.keys()),
                body=body,
                media_body=googleapiclient.http.MediaFileUpload(
                    video_path, 
                    mimetype="video/mp4", 
                    resumable=True
                )
            )
            
            # Thực hiện upload với cơ chế resumable
            response = None
            logger.info(f"Bắt đầu tải video lên YouTube: {os.path.basename(video_path)}")
            
            while response is None:
                try:
                    status, response = insert_request.next_chunk()
                    if status:
                        # Hiển thị tiến độ
                        percent = int(status.progress() * 100)
                        logger.info(f"Tải lên: {percent}%")
                except googleapiclient.errors.HttpError as e:
                    if e.resp.status in [500, 502, 503, 504]:
                        # Thử lại trong trường hợp lỗi server
                        logger.warning(f"Lỗi server {e.resp.status}. Thử lại sau 5 giây.")
                        time.sleep(5)
                    else:
                        logger.error(f"Lỗi HTTP khi tải video: {str(e)}")
                        return None
                except Exception as e:
                    logger.error(f"Lỗi khi tải video: {str(e)}")
                    return None
            
            if response:
                video_id = response.get("id")
                logger.info(f"Đã tải lên thành công video lên YouTube với ID: {video_id}")
                return video_id
            
            return None
        except Exception as e:
            logger.error(f"Lỗi khi tạo insert request: {str(e)}")
            return None
    
    def update_video_link(self, idea_id: Union[str, int, None], video_url: str) -> bool:
        """
        Cập nhật link YouTube cho một ý tưởng.
        """
        try:
            # Lấy tất cả dữ liệu từ sheet
            range_name = f"{self.sheets_manager.sheet_name}!{settings.IDEAS_SHEET_RANGE}"
            values = self.sheets_manager.get_values(range_name)
            
            if not values or len(values) < 2:
                logger.warning(f"Không tìm thấy dữ liệu trong range {range_name}")
                return False
            
            # Tìm vị trí cột link-youtube
            headers = values[0]
            youtube_col_index = None
            
            for i, header in enumerate(headers):
                header_lower = header.lower()
                if header_lower == "link-youtube":
                    youtube_col_index = i
                    logger.info(f"Tìm thấy cột 'link-youtube' ở vị trí {i}")
                    break
            
            # Thêm cột link-youtube nếu chưa có
            if youtube_col_index is None:
                headers.append("link-youtube")
                youtube_col_index = len(headers) - 1
                
                # Cập nhật header
                update_result = self.sheets_manager.update_values(
                    f"{self.sheets_manager.sheet_name}!A1:{chr(65 + len(headers) - 1)}1",
                    [headers]
                )
                
                if update_result > 0:
                    logger.info(f"Đã thêm cột link-youtube ở vị trí {youtube_col_index}")
                else:
                    logger.error("Không thể thêm cột link-youtube")
                    return False
            
            # Tìm hàng để cập nhật
            row_index = None
            
            # Nếu có ID, ưu tiên tìm theo ID
            if idea_id:
                id_col_index = -1
                for i, header in enumerate(headers):
                    if header.upper() == "ID":
                        id_col_index = i
                        break
                        
                if id_col_index != -1:
                    for i, row in enumerate(values[1:], 1):
                        if len(row) > id_col_index and str(row[id_col_index]).strip() == str(idea_id).strip():
                            row_index = i
                            logger.info(f"Tìm thấy hàng với ID {idea_id} ở vị trí {row_index+1}")
                            break
            
            # Nếu không tìm thấy theo ID, tìm theo trạng thái "for publishing"
            if row_index is None:
                status_col_index = -1
                for i, header in enumerate(headers):
                    if header == "Status Publishing" or header == "Status_Publishing":
                        status_col_index = i
                        break
                        
                if status_col_index != -1:
                    for i, row in enumerate(values[1:], 1):
                        if len(row) > status_col_index and str(row[status_col_index]).lower() == "for publishing":
                            row_index = i
                            logger.info(f"Tìm thấy hàng với trạng thái 'for publishing' ở vị trí {row_index+1}")
                            break
            
            if row_index is None:
                logger.error("Không thể tìm thấy hàng để cập nhật link YouTube")
                return False
            
            # Cập nhật link YouTube
            update_range = f"{self.sheets_manager.sheet_name}!{chr(65+youtube_col_index)}{row_index+1}"
            logger.info(f"Cập nhật link YouTube vào ô {update_range}: {video_url}")
            
            update_result = self.sheets_manager.update_values(update_range, [[video_url]])
            
            if update_result > 0:
                logger.info(f"Đã cập nhật thành công link YouTube vào ô {update_range}")
                return True
            else:
                logger.error(f"Không thể cập nhật link YouTube vào ô {update_range}")
                return False
        
        except Exception as e:
            logger.error(f"Lỗi khi cập nhật link YouTube: {str(e)}")
            return False
    def clean_temp_directory(self) -> bool:
        """
        Xóa tất cả các file trong thư mục temp.
        
        Returns:
            bool: True nếu xóa thành công tất cả file, False nếu có lỗi
        """
        try:
            # Đảm bảo thư mục temp tồn tại
            if not os.path.exists(self.temp_dir):
                logger.warning(f"Thư mục temp không tồn tại: {self.temp_dir}")
                return False
            
            # Đếm tổng số file
            total_files = 0
            for root, dirs, files in os.walk(self.temp_dir):
                total_files += len(files)
            
            if total_files == 0:
                logger.info(f"Không có file nào trong thư mục temp: {self.temp_dir}")
                return True
            
            # Xóa từng file
            deleted_count = 0
            for root, dirs, files in os.walk(self.temp_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    try:
                        os.remove(file_path)
                        deleted_count += 1
                        logger.debug(f"Đã xóa file: {file_path}")
                    except Exception as file_error:
                        logger.error(f"Không thể xóa file {file_path}: {str(file_error)}")
            
            # Kiểm tra xem đã xóa hết chưa
            if deleted_count == total_files:
                logger.info(f"Đã xóa tất cả {deleted_count} file trong thư mục temp")
                return True
            else:
                logger.warning(f"Đã xóa {deleted_count}/{total_files} file trong thư mục temp")
                return False
            
        except Exception as e:
            logger.error(f"Lỗi khi xóa files trong thư mục temp: {str(e)}")
            return False
        
    def update_publishing_status(self, idea_id: Union[str, int], status: str) -> bool:
        """
        Cập nhật trạng thái xuất bản cho một ý tưởng.
        
        Args:
            idea_id: ID của ý tưởng cần cập nhật
            status: Trạng thái mới ('pending', 'for publishing', 'published')
            
        Returns:
            bool: True nếu cập nhật thành công, False nếu thất bại
        """
        try:
            # Lấy tất cả dữ liệu từ sheet
            range_name = f"{self.sheet_name}!{settings.IDEAS_SHEET_RANGE}"
            values = self.get_values(range_name)
            
            if not values or len(values) < 2:
                logger.warning(f"Không tìm thấy dữ liệu trong range {range_name}")
                return False
            
            # Tìm vị trí cột Status Publishing (kiểm tra cả hai biến thể)
            headers = values[0]
            status_col_index = None
            
            for i, header in enumerate(headers):
                if header == "Status Publishing" or header == "Status_Publishing":
                    status_col_index = i
                    logger.info(f"Đã tìm thấy cột trạng thái xuất bản: {header} (vị trí {i})")
                    break
            
            if status_col_index is None:
                logger.warning("Không tìm thấy cột Status Publishing hoặc Status_Publishing")
                return False
            
            # Tìm dòng có ID tương ứng
            id_col_index = -1
            for i, header in enumerate(headers):
                if header.upper() == "ID":
                    id_col_index = i
                    break
            
            if id_col_index == -1:
                logger.error("Không tìm thấy cột ID trong sheet")
                return False
            
            row_index = None
            for i, row in enumerate(values[1:], 1):  # Bỏ qua header
                if len(row) > id_col_index:
                    current_id = str(row[id_col_index]).strip()
                    idea_id_str = str(idea_id).strip()
                    
                    if current_id == idea_id_str:
                        row_index = i
                        logger.info(f"Đã tìm thấy hàng {i+1} có ID {current_id}")
                        break
            
            if row_index is None:
                logger.warning(f"Không tìm thấy ý tưởng với ID {idea_id}")
                return False
            
            # Cập nhật trạng thái
            row = values[row_index]
            if len(row) <= status_col_index:
                row = row + [''] * (status_col_index - len(row) + 1)
            
            old_status = row[status_col_index] if status_col_index < len(row) else ""
            
            # Cập nhật trực tiếp ô chứa trạng thái
            update_range = f"{self.sheet_name}!{chr(65+status_col_index)}{row_index+1}"
            result = self.update_values(update_range, [[status]])
            
            logger.info(f"Đã cập nhật trạng thái xuất bản cho ý tưởng ID {idea_id}: '{old_status}' -> '{status}'")
            return result > 0
            
        except Exception as e:
            logger.error(f"Lỗi khi cập nhật trạng thái xuất bản cho ý tưởng ID {idea_id}: {str(e)}")
            return False
    def process_youtube_publishing(self) -> Dict[str, Any]:
        """
        Thực hiện toàn bộ quy trình đăng tải video lên YouTube.
        
        Returns:
            Dict: Kết quả của quy trình đăng tải
        """
        try:

            # Lấy ý tưởng cần xuất bản trước
            ideas = self.get_publishing_ideas()
            if not ideas:
                logger.info("Không có ý tưởng nào ở trạng thái 'for publishing', bỏ qua việc đăng tải")
                return {
                    "success": False, 
                    "error": "Không có ý tưởng nào ở trạng thái 'for publishing'",
                    "skip_upload": True
                }
            
            # Lấy ý tưởng đầu tiên
            idea = ideas[0]
            idea_id = None
            
            # Tìm ID ý tưởng (thử nhiều trường hợp vì Google Sheet có thể trả về key khác nhau)
            if "ID" in idea:
                idea_id = idea.get("ID")
            elif "id" in idea:
                idea_id = idea.get("id")
            else:
                # Tìm key có tên chứa "id" không phân biệt hoa thường
                for key in idea:
                    if key.lower() == "id":
                        idea_id = idea.get(key)
                        break
            
            # Nếu vẫn không tìm thấy ID, thử lấy từ status_publishing
            if not idea_id:
                # Tìm row có status "for publishing"
                range_name = f"{self.sheets_manager.sheet_name}!{settings.IDEAS_SHEET_RANGE}"
                values = self.sheets_manager.get_values(range_name)
                if values and len(values) > 1:
                    headers = values[0]
                    id_col = None
                    status_col = None
                    
                    # Xác định cột ID và Status
                    for i, header in enumerate(headers):
                        if header.lower() == "id":
                            id_col = i
                        if "status" in header.lower() and "publishing" in header.lower():
                            status_col = i
                    
                    # Tìm hàng có status "for publishing"
                    if id_col is not None and status_col is not None:
                        for i, row in enumerate(values[1:], 1):
                            if len(row) > status_col and row[status_col].lower() == "for publishing":
                                if len(row) > id_col:
                                    idea_id = row[id_col]
                                    logger.info(f"Đã xác định được ID ý tưởng từ Google Sheet: {idea_id}")
                                    break
            
            # Log thông tin ID ý tưởng
            if idea_id:
                logger.info(f"Sử dụng ý tưởng có ID: {idea_id}")
            else:
                logger.warning("Không xác định được ID ý tưởng, sẽ không thể cập nhật Google Sheet")
            
            # Lấy thông tin video cần đăng tải
            video_info = self.get_video_for_publishing()
            
            if not video_info or "local_path" not in video_info:
                logger.error("Không tìm thấy video để đăng tải")
                return {"success": False, "error": "Không tìm thấy video để đăng tải"}
            
            # Lấy đường dẫn video
            video_path = video_info["local_path"]
            
            # Chuẩn bị metadata
            metadata = self.prepare_video_metadata(idea)
            
            # Tải video lên YouTube
            video_id = self.upload_video_to_youtube(video_path, metadata)
            
            if not video_id:
                logger.error("Không thể tải video lên YouTube")
                return {"success": False, "error": "Không thể tải video lên YouTube"}
            
            # Cập nhật trạng thái ý tưởng nếu có ID
            update_success = False
            # Đoạn code trong process_youtube_publishing cần sửa:
            # Cập nhật trạng thái ý tưởng nếu có ID
            if idea_id:
                video_url = f"https://www.youtube.com/watch?v={video_id}"
                logger.info(f"Cập nhật ý tưởng ID={idea_id} với link={video_url}")
                
                # Thực hiện cập nhật và ghi log chi tiết
                update_success = self.update_idea_status(idea_id, video_id, "published")
                
                # Kiểm tra thêm sau khi update để xác nhận kết quả
                if update_success:
                    logger.info(f"✅ Đã cập nhật thành công ý tưởng ID={idea_id}: Link YouTube và/hoặc trạng thái")
                else:
                    logger.error(f"❌ Cập nhật thất bại hoàn toàn cho ID={idea_id}")
                    
                    # Làm bước cuối cùng: cập nhật trực tiếp vào Google Sheet
                    try:
                        sheet_url = f"https://docs.google.com/spreadsheets/d/{settings.GOOGLE_SHEET_ID}/edit"
                        logger.warning(f"Vui lòng cập nhật thủ công tại Google Sheet: {sheet_url}")
                        logger.warning(f"Thông tin cập nhật: ID={idea_id}, YouTube URL={video_url}, Status=published")
                    except:
                        pass
            else:
                logger.warning("Không có ID ý tưởng để cập nhật")
            
            # Xóa tất cả file audio sau khi đăng tải thành công
            self.delete_audio_files_from_drive()
            
            # Tạo kết quả
            result = {
                "success": True,
                "video_id": video_id,
                "video_url": f"https://www.youtube.com/watch?v={video_id}",
                "idea_id": idea_id,
                "update_status_success": update_success
            }
            
            # Lưu kết quả vào file
            output_file = os.path.join(self.temp_dir, "youtube_result.json")
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            
            logger.info(f"Đã lưu kết quả đăng tải lên YouTube vào: {output_file}")
            self.delete_videos_from_drive()           
            # Xóa tất cả file trong thư mục temp sau khi đăng tải thành công
            if self.clean_temp_directory():
                logger.info("Đã xóa tất cả file trong thư mục temp sau khi đăng tải thành công")
            else:
                logger.warning("Một số file trong thư mục temp không thể xóa")
            
            return result
        except Exception as e:
            logger.error(f"Lỗi trong quy trình đăng tải YouTube: {str(e)}")
            return {"success": False, "error": str(e)}
        
    def update_production_status(self, idea_id: Union[str, int], status: str = "done") -> bool:
        """
        Cập nhật trạng thái sản xuất cho một ý tưởng.
        
        Args:
            idea_id: ID của ý tưởng cần cập nhật
            status: Trạng thái sản xuất mới (mặc định: "done")
            
        Returns:
            bool: True nếu cập nhật thành công, False nếu thất bại
        """
        try:
            # Lấy tất cả dữ liệu từ sheet
            range_name = f"{self.sheets_manager.sheet_name}!{settings.IDEAS_SHEET_RANGE}"
            values = self.sheets_manager.get_values(range_name)
            
            if not values or len(values) < 2:
                logger.warning(f"Không tìm thấy dữ liệu trong range {range_name}")
                return False
            
            # Tìm vị trí cột Production
            headers = values[0]
            production_col_index = None
            
            for i, header in enumerate(headers):
                if header == "Production":
                    production_col_index = i
                    logger.info(f"Tìm thấy cột Production ở vị trí {i}")
                    break
            
            if production_col_index is None:
                logger.warning("Không tìm thấy cột Production trong sheet")
                return False
            
            # Tìm dòng có ID tương ứng
            id_col_index = -1
            for i, header in enumerate(headers):
                if header.upper() == "ID":
                    id_col_index = i
                    break
            
            if id_col_index == -1:
                logger.error("Không tìm thấy cột ID trong sheet")
                return False
            
            row_index = None
            for i, row in enumerate(values[1:], 1):  # Bỏ qua header
                if len(row) > id_col_index and str(row[id_col_index]).strip() == str(idea_id).strip():
                    row_index = i
                    logger.info(f"Đã tìm thấy hàng {i+1} có ID {idea_id}")
                    break
            
            if row_index is None:
                logger.warning(f"Không tìm thấy ý tưởng với ID {idea_id}")
                return False
            
            # Lấy giá trị cũ của Production (nếu có)
            old_status = ""
            if len(values[row_index]) > production_col_index:
                old_status = values[row_index][production_col_index]
            
            # Cập nhật trạng thái Production
            update_range = f"{self.sheets_manager.sheet_name}!{chr(65+production_col_index)}{row_index+1}"
            result = self.sheets_manager.update_values(update_range, [[status]])
            
            logger.info(f"Đã cập nhật trạng thái Production cho ý tưởng ID {idea_id}: '{old_status}' -> '{status}'")
            return result > 0
            
        except Exception as e:
            logger.error(f"Lỗi khi cập nhật trạng thái Production cho ý tưởng ID {idea_id}: {str(e)}")
            return False
    def update_idea_status(self, idea_id: Union[str, int], video_id: str, status: str = "published") -> bool:
        """
        Cập nhật trạng thái và link video cho một ý tưởng.
        """
        try:
            # Tạo URL YouTube
            video_url = f"https://www.youtube.com/watch?v={video_id}"
            logger.info(f"Cập nhật ý tưởng ID={idea_id} với link YouTube={video_url} và trạng thái={status}")
            
            # Cập nhật link video - thử trực tiếp với update_video_link
            link_success = self.update_video_link(idea_id, video_url)
            
            if link_success:
                logger.info(f"Đã cập nhật link YouTube thành công cho ý tưởng ID {idea_id}")
            else:
                logger.error(f"Không thể cập nhật link YouTube cho ý tưởng ID {idea_id}")
                
                # Thử cập nhật qua GoogleSheetsManager như một phương pháp dự phòng
                try:
                    link_success = self.sheets_manager.update_video_link(idea_id, video_url)
                    if link_success:
                        logger.info(f"Phương pháp dự phòng: Đã cập nhật link YouTube cho ý tưởng ID {idea_id}")
                except Exception as e:
                    logger.error(f"Lỗi khi cập nhật link YouTube (phương pháp dự phòng): {str(e)}")
            
            # Cập nhật trạng thái publishing
            status_success = False
            try:
                status_success = self.sheets_manager.update_publishing_status(idea_id, status)
                if status_success:
                    logger.info(f"Đã cập nhật trạng thái xuất bản thành '{status}' cho ý tưởng ID {idea_id}")
                else:
                    logger.warning(f"Không thể cập nhật trạng thái xuất bản cho ý tưởng ID {idea_id}")
            except Exception as e:
                logger.error(f"Lỗi khi cập nhật trạng thái xuất bản: {str(e)}")
            
            # Cập nhật trạng thái Production thành "done"
            production_success = False
            try:
                production_success = self.update_production_status(idea_id, "done")
                if production_success:
                    logger.info(f"Đã cập nhật trạng thái Production thành 'done' cho ý tưởng ID {idea_id}")
                else:
                    logger.warning(f"Không thể cập nhật trạng thái Production cho ý tưởng ID {idea_id}")
            except Exception as e:
                logger.error(f"Lỗi khi cập nhật trạng thái Production: {str(e)}")
            
            # Trả về True nếu ít nhất một trong ba thao tác thành công
            return link_success or status_success or production_success
            
        except Exception as e:
            logger.error(f"Lỗi tổng thể khi cập nhật ý tưởng ID {idea_id}: {str(e)}")
            return False
    def delete_audio_files_from_drive(self) -> bool:
        """
        Xóa tất cả file audio trong thư mục Google Drive chứa audio.
        
        Returns:
            bool: True nếu xóa thành công, False nếu có lỗi
        """
        try:
            # ID thư mục Drive chứa audio
            audio_folder_id = "1SXv9rGf_EvC1BBeilAh1QtzquS8A6pti"
            
            # Lấy danh sách tất cả file trong thư mục
            files = self.drive_manager.list_files_in_folder(audio_folder_id)
            
            # Lọc chỉ lấy file audio
            audio_files = [file for file in files if file.get('mimeType', '').startswith('audio/')]
            
            if not audio_files:
                logger.info("Không có file audio nào cần xóa từ Google Drive")
                return True
            
            logger.info(f"Chuẩn bị xóa {len(audio_files)} file audio từ Google Drive")
            
            # Xóa từng file audio
            success_count = 0
            for file in audio_files:
                file_id = file.get('id')
                file_name = file.get('name')
                
                try:
                    if self.drive_manager.delete_file(file_id):
                        logger.info(f"Đã xóa file audio: {file_name} (ID: {file_id})")
                        success_count += 1
                    else:
                        logger.warning(f"Không thể xóa file audio: {file_name} (ID: {file_id})")
                except Exception as file_error:
                    logger.error(f"Lỗi khi xóa file audio {file_name}: {str(file_error)}")
            
            logger.info(f"Đã xóa {success_count}/{len(audio_files)} file audio từ Google Drive")
            return success_count == len(audio_files)
        
        except Exception as e:
            logger.error(f"Lỗi khi xóa audio từ Google Drive: {str(e)}")
            return False
        
    def delete_videos_from_drive(self, keep_latest: bool = False) -> bool:
        """
        Xóa tất cả file video trong thư mục Google Drive chứa video.
        
        Args:
            keep_latest: Nếu True, giữ lại video mới nhất. Mặc định False - xóa tất cả video
            
        Returns:
            bool: True nếu xóa thành công, False nếu có lỗi
        """
        try:
            # ID thư mục Drive chứa video
            video_folder_id = "1oFc-Wby1Gm5GKwr1Eygg4zzVfIqIlo0Y"
            
            # Lấy danh sách tất cả file trong thư mục
            files = self.drive_manager.list_files_in_folder(video_folder_id)
            
            # Lọc chỉ lấy file video
            video_files = [file for file in files if file.get('mimeType', '').startswith('video/')]
            
            if not video_files:
                logger.info("Không có file video nào cần xóa từ Google Drive")
                return True
            
            # Sắp xếp theo thời gian tạo (mới nhất đầu tiên) để biết video mới nhất (nếu cần giữ lại)
            video_files.sort(key=lambda x: x.get('createdTime', ''), reverse=True)
            
            # Nếu keep_latest=True, giữ lại video mới nhất
            files_to_delete = video_files
            if keep_latest and len(video_files) > 0:
                latest_video = video_files[0]
                files_to_delete = video_files[1:]
                logger.info(f"Giữ lại video mới nhất: {latest_video.get('name')} (ID: {latest_video.get('id')})")
            else:
                logger.info("Xóa tất cả video không giữ lại video nào")
            
            if not files_to_delete:
                logger.info("Không có video nào cần xóa")
                return True
            
            logger.info(f"Chuẩn bị xóa {len(files_to_delete)} file video từ Google Drive")
            
            # Xóa từng file video
            success_count = 0
            for file in files_to_delete:
                file_id = file.get('id')
                file_name = file.get('name')
                
                try:
                    if self.drive_manager.delete_file(file_id):
                        logger.info(f"Đã xóa file video: {file_name} (ID: {file_id})")
                        success_count += 1
                    else:
                        logger.warning(f"Không thể xóa file video: {file_name} (ID: {file_id})")
                except Exception as file_error:
                    logger.error(f"Lỗi khi xóa file video {file_name}: {str(file_error)}")
            
            logger.info(f"Đã xóa {success_count}/{len(files_to_delete)} file video từ Google Drive")
            return success_count == len(files_to_delete)
        
        except Exception as e:
            logger.error(f"Lỗi khi xóa video từ Google Drive: {str(e)}")
            return False
def main():
    """
    Hàm chính để chạy quy trình đăng tải video lên YouTube.
    """
    try:
        logger.info("=== Bắt đầu Quy trình Đăng tải YouTube ===")
        
        # Tạo instance của YouTubePublisher
        youtube_publisher = YouTubePublisher()
        
        # Thực hiện quy trình đăng tải YouTube
        result = youtube_publisher.process_youtube_publishing()
        
        if result.get("skip_upload", False):
            logger.info("Bỏ qua việc đăng tải video lên YouTube do không có ý tưởng ở trạng thái 'for publishing'")
        elif result.get("success", False):
            video_url = result.get("video_url", "")
            idea_id = result.get("idea_id", "")
            logger.info(f"Đã đăng tải thành công video lên YouTube: {video_url}")
            if idea_id:
                logger.info(f"Đã cập nhật trạng thái 'published' cho ý tưởng ID: {idea_id}")
            logger.info("Đã xóa các file audio từ Google Drive")
        else:
            error = result.get("error", "Lỗi không xác định")
            logger.error(f"Không thể đăng tải video lên YouTube: {error}")
        
        logger.info("=== Kết thúc Quy trình Đăng tải YouTube ===")
        
        return result
    except Exception as e:
        logger.error(f"Lỗi trong quy trình đăng tải YouTube: {str(e)}")
        raise

if __name__ == "__main__":
    main()