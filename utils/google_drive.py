#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Module tiện ích tương tác với Google Drive trong hệ thống tạo video POV.
Cung cấp các phương thức để tải lên, chia sẻ, xóa và quản lý file trên Google Drive.
"""

import os
import io
import logging
import time
import base64
from typing import List, Dict, Optional, Union, Any

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseUpload, MediaIoBaseDownload
from google.auth.transport.requests import Request

# Import các module nội bộ
from config import settings
from utils.base64_utils import decode_base64_to_bytes

# Thiết lập logging
logger = logging.getLogger(__name__)

class GoogleDriveManager:
    """
    Lớp quản lý tương tác với Google Drive API.
    """
    
    def __init__(self):
        """
        Khởi tạo GoogleDriveManager với thông tin xác thực từ file cấu hình.
        """
        self.credentials_path = settings.GOOGLE_APPLICATION_CREDENTIALS
        self.api_service_name = "drive"
        self.api_version = "v3"
        self._service = None  # Lazy initialization
        
        logger.debug("Khởi tạo GoogleDriveManager")
    
    @property
    def service(self):
        """
        Lấy dịch vụ Google Drive API, khởi tạo nếu chưa có.
        
        Returns:
            Resource: Đối tượng dịch vụ Google Drive
        """
        if self._service is None:
            try:
                # Nạp thông tin xác thực từ file service account
                credentials = service_account.Credentials.from_service_account_file(
                    self.credentials_path,
                    scopes=['https://www.googleapis.com/auth/drive']
                )
                
                # Tạo dịch vụ API
                self._service = build(
                    self.api_service_name,
                    self.api_version,
                    credentials=credentials,
                    cache_discovery=False
                )
                logger.info("Đã kết nối thành công với Google Drive API")
            except Exception as e:
                logger.error(f"Lỗi khi khởi tạo dịch vụ Google Drive: {str(e)}")
                raise
        
        return self._service
    
    def upload_file(self, file_path: str, filename: Optional[str] = None, 
                   mime_type: Optional[str] = None, folder_id: Optional[str] = None) -> Optional[str]:
        """
        Tải file lên Google Drive.
        
        Args:
            file_path: Đường dẫn tới file cần tải lên
            filename: Tên file trên Drive (nếu khác với tên gốc)
            mime_type: Loại MIME của file (tự phát hiện nếu None)
            folder_id: ID thư mục trên Drive để lưu file (My Drive nếu None)
            
        Returns:
            str: ID của file đã tải lên hoặc None nếu thất bại
        """
        try:
            if not os.path.exists(file_path):
                logger.error(f"File không tồn tại: {file_path}")
                return None
            
            # Sử dụng tên file gốc nếu không chỉ định
            if filename is None:
                filename = os.path.basename(file_path)
            
            # Chuẩn bị metadata
            file_metadata = {
                'name': filename,
            }
            
            # Thêm folder ID nếu có
            if folder_id:
                file_metadata['parents'] = [folder_id]
            
            # Tạo đối tượng media
            media = MediaFileUpload(file_path, mimetype=mime_type, resumable=True)
            
            # Thực hiện tải lên
            file = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id'
            ).execute()
            
            file_id = file.get('id')
            logger.info(f"Đã tải lên thành công file: {filename} (ID: {file_id})")
            return file_id
            
        except Exception as e:
            logger.error(f"Lỗi khi tải file {file_path} lên Google Drive: {str(e)}")
            return None
    # Trong utils/google_drive.py
    
    def list_files_in_folder(self, folder_id: str) -> List[Dict[str, Any]]:
        """
        Lấy danh sách tất cả file trong một thư mục Google Drive.
        
        Args:
            folder_id: ID của thư mục trên Google Drive
            
        Returns:
            List[Dict]: Danh sách thông tin về các file trong thư mục
        """
        try:
            # Truy vấn tất cả các file trong thư mục
            query = f"'{folder_id}' in parents and trashed=false"
            results = self.service.files().list(
                q=query,
                fields="files(id, name, mimeType, createdTime, modifiedTime)",
                pageSize=1000
            ).execute()
            
            files = results.get('files', [])
            return files
        
        except Exception as e:
            logger.error(f"Lỗi khi lấy danh sách file từ thư mục: {str(e)}")
            return []
    
    def delete_file(self, file_id: str) -> bool:
        """
        Xóa một file từ Google Drive.
        
        Args:
            file_id: ID của file cần xóa
            
        Returns:
            bool: True nếu xóa thành công, False nếu có lỗi
        """
        try:
            self.service.files().delete(fileId=file_id).execute()
            return True
        
        except Exception as e:
            logger.error(f"Lỗi khi xóa file từ Google Drive: {str(e)}")
            return False  
    def upload_from_base64(self, base64_data: str, filename: str, mime_type: str = "application/octet-stream", parent_folder_id: str = None) -> Optional[str]:
        """
        Tải lên file từ dữ liệu base64 lên Google Drive.
        
        Args:
            base64_data: Dữ liệu file dạng base64
            filename: Tên file
            mime_type: Loại MIME của file
            parent_folder_id: ID thư mục đích (nếu None thì tải lên thư mục gốc)
            
        Returns:
            str: ID của file đã tải lên, hoặc None nếu có lỗi
        """
        try:
            # Giải mã base64
            file_data = base64.b64decode(base64_data)
            
            # Tạo metadata
            file_metadata = {
                'name': filename
            }
            
            # Thêm thư mục đích nếu được chỉ định
            if parent_folder_id:
                file_metadata['parents'] = [parent_folder_id]
            
            # Tạo media object
            media = MediaIoBaseUpload(
                io.BytesIO(file_data),
                mimetype=mime_type,
                resumable=True
            )
            
            # Tải lên file
            file = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id'
            ).execute()
            
            file_id = file.get('id')
            logger.info(f"Đã tải lên thành công file base64: {filename} (ID: {file_id})")
            
            return file_id
            
        except Exception as e:
            logger.error(f"Lỗi khi tải file base64 lên Google Drive: {str(e)}")
            return None
    
    def share_file(self, file_id: str, role: str = 'reader', 
                  type: str = 'anyone', email: Optional[str] = None) -> bool:
        """
        Chia sẻ file trên Google Drive.
        
        Args:
            file_id: ID của file cần chia sẻ
            role: Quyền của người được chia sẻ ('reader', 'writer', 'commenter')
            type: Loại đối tượng được chia sẻ ('user', 'group', 'domain', 'anyone')
            email: Email người nhận (chỉ cần khi type là 'user' hoặc 'group')
            
        Returns:
            bool: True nếu chia sẻ thành công, False nếu thất bại
        """
        try:
            # Chuẩn bị permission
            permission = {
                'type': type,
                'role': role,
            }
            
            # Thêm email nếu cần
            if email and type in ['user', 'group']:
                permission['emailAddress'] = email
            
            # Thực hiện chia sẻ
            self.service.permissions().create(
                fileId=file_id,
                body=permission,
                fields='id',
                sendNotificationEmail=False
            ).execute()
            
            logger.info(f"Đã chia sẻ file (ID: {file_id}) với quyền {role} cho {type}")
            return True
            
        except Exception as e:
            logger.error(f"Lỗi khi chia sẻ file (ID: {file_id}): {str(e)}")
            return False
    
    def get_web_content_link(self, file_id: str) -> Optional[str]:
        """
        Lấy đường dẫn webContentLink của file trên Google Drive.
        
        Args:
            file_id: ID của file cần lấy link
            
        Returns:
            str: Đường dẫn webContentLink hoặc None nếu thất bại
        """
        try:
            # Lấy thông tin file với trường webContentLink
            file = self.service.files().get(
                fileId=file_id,
                fields='webContentLink'
            ).execute()
            
            # Trả về link hoặc None nếu không có
            web_content_link = file.get('webContentLink')
            if web_content_link:
                logger.debug(f"Đã lấy webContentLink cho file (ID: {file_id})")
                return web_content_link
            else:
                logger.warning(f"Không tìm thấy webContentLink cho file (ID: {file_id})")
                return None
            
        except Exception as e:
            logger.error(f"Lỗi khi lấy webContentLink cho file (ID: {file_id}): {str(e)}")
            return None
    
    def delete_file(self, file_id: str) -> bool:
        """
        Xóa file trên Google Drive.
        
        Args:
            file_id: ID của file cần xóa
            
        Returns:
            bool: True nếu xóa thành công, False nếu thất bại
        """
        try:
            self.service.files().delete(fileId=file_id).execute()
            logger.info(f"Đã xóa file (ID: {file_id})")
            return True
        except Exception as e:
            logger.error(f"Lỗi khi xóa file (ID: {file_id}): {str(e)}")
            return False
    
    def list_files(self, folder_id: Optional[str] = None, query: Optional[str] = None, 
                  page_size: int = 100) -> List[Dict[str, Any]]:
        """
        Liệt kê các file trên Google Drive.
        
        Args:
            folder_id: ID thư mục cần liệt kê (tất cả nếu None)
            query: Truy vấn tìm kiếm (định dạng Google Drive API)
            page_size: Số lượng kết quả tối đa
            
        Returns:
            List[Dict]: Danh sách các file với thông tin
        """
        try:
            # Xây dựng query
            if query is None:
                query = ""
            
            if folder_id:
                if query:
                    query += f" and '{folder_id}' in parents"
                else:
                    query = f"'{folder_id}' in parents"
            
            if query:
                query += " and trashed = false"
            else:
                query = "trashed = false"
            
            # Thực hiện truy vấn
            response = self.service.files().list(
                q=query,
                pageSize=page_size,
                fields="files(id, name, mimeType, webContentLink, webViewLink, createdTime, modifiedTime, size)"
            ).execute()
            
            files = response.get('files', [])
            logger.info(f"Đã tìm thấy {len(files)} file")
            return files
            
        except Exception as e:
            logger.error(f"Lỗi khi liệt kê file trên Google Drive: {str(e)}")
            return []
    
    def create_folder(self, folder_name: str, parent_id: Optional[str] = None) -> Optional[str]:
        """
        Tạo thư mục mới trên Google Drive.
        
        Args:
            folder_name: Tên thư mục cần tạo
            parent_id: ID thư mục cha (My Drive nếu None)
            
        Returns:
            str: ID của thư mục đã tạo hoặc None nếu thất bại
        """
        try:
            # Chuẩn bị metadata
            folder_metadata = {
                'name': folder_name,
                'mimeType': 'application/vnd.google-apps.folder'
            }
            
            # Thêm parent ID nếu có
            if parent_id:
                folder_metadata['parents'] = [parent_id]
            
            # Tạo thư mục
            folder = self.service.files().create(
                body=folder_metadata,
                fields='id'
            ).execute()
            
            folder_id = folder.get('id')
            logger.info(f"Đã tạo thư mục: {folder_name} (ID: {folder_id})")
            return folder_id
            
        except Exception as e:
            logger.error(f"Lỗi khi tạo thư mục {folder_name} trên Google Drive: {str(e)}")
            return None
    
    def get_file_info(self, file_id: str) -> Optional[Dict[str, Any]]:
        """
        Lấy thông tin chi tiết của file trên Google Drive.
        
        Args:
            file_id: ID của file cần lấy thông tin
            
        Returns:
            Dict: Thông tin chi tiết của file hoặc None nếu thất bại
        """
        try:
            file_info = self.service.files().get(
                fileId=file_id,
                fields="id, name, mimeType, webContentLink, webViewLink, size, createdTime, modifiedTime"
            ).execute()
            
            logger.debug(f"Đã lấy thông tin file (ID: {file_id})")
            return file_info
            
        except Exception as e:
            logger.error(f"Lỗi khi lấy thông tin file (ID: {file_id}): {str(e)}")
            return None
    
    def update_file_content(self, file_id: str, file_path: str, mime_type: Optional[str] = None) -> bool:
        """
        Cập nhật nội dung file trên Google Drive.
        
        Args:
            file_id: ID của file cần cập nhật
            file_path: Đường dẫn tới file mới
            mime_type: Loại MIME của file (tự phát hiện nếu None)
            
        Returns:
            bool: True nếu cập nhật thành công, False nếu thất bại
        """
        try:
            if not os.path.exists(file_path):
                logger.error(f"File không tồn tại: {file_path}")
                return False
            
            # Tạo đối tượng media
            media = MediaFileUpload(file_path, mimetype=mime_type, resumable=True)
            
            # Cập nhật file
            self.service.files().update(
                fileId=file_id,
                media_body=media
            ).execute()
            
            logger.info(f"Đã cập nhật nội dung file (ID: {file_id})")
            return True
            
        except Exception as e:
            logger.error(f"Lỗi khi cập nhật nội dung file (ID: {file_id}): {str(e)}")
            return False
    
    def get_or_create_folder(self, folder_name: str, parent_id: Optional[str] = None) -> Optional[str]:
        """
        Lấy ID thư mục nếu đã tồn tại, nếu không thì tạo mới.
        
        Args:
            folder_name: Tên thư mục cần tìm hoặc tạo
            parent_id: ID thư mục cha (My Drive nếu None)
            
        Returns:
            str: ID của thư mục hoặc None nếu thất bại
        """
        try:
            # Xây dựng query
            query = f"name = '{folder_name}' and mimeType = 'application/vnd.google-apps.folder'"
            
            if parent_id:
                query += f" and '{parent_id}' in parents"
            
            query += " and trashed = false"
            
            # Tìm thư mục
            response = self.service.files().list(
                q=query,
                spaces='drive',
                fields='files(id, name)'
            ).execute()
            
            files = response.get('files', [])
            
            # Trả về ID nếu đã tồn tại
            if files:
                logger.info(f"Đã tìm thấy thư mục: {folder_name} (ID: {files[0].get('id')})")
                return files[0].get('id')
            
            # Tạo mới nếu chưa tồn tại
            return self.create_folder(folder_name, parent_id)
            
        except Exception as e:
            logger.error(f"Lỗi khi tìm hoặc tạo thư mục {folder_name}: {str(e)}")
            return None
    
    def download_file(self, file_id: str, output_path: Optional[str] = None) -> Optional[str]:
        """
        Tải file từ Google Drive về máy cục bộ.
        
        Args:
            file_id: ID của file cần tải về
            output_path: Đường dẫn lưu file (tự động tạo nếu None)
            
        Returns:
            str: Đường dẫn tới file đã tải về hoặc None nếu thất bại
        """
        try:
            # Lấy thông tin file để biết tên
            file_info = self.get_file_info(file_id)
            if not file_info:
                return None
            
            # Tạo đường dẫn output nếu chưa có
            if output_path is None:
                output_path = file_info.get('name')
            
            # Tạo thư mục chứa nếu chưa tồn tại
            os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
            
            # Tải file
            request = self.service.files().get_media(fileId=file_id)
            with open(output_path, 'wb') as f:
                downloader = MediaIoBaseDownload(f, request)
                done = False
                while done is False:
                    status, done = downloader.next_chunk()
                    logger.debug(f"Đã tải về {int(status.progress() * 100)}%.")
            
            logger.info(f"Đã tải về file (ID: {file_id}) tới {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"Lỗi khi tải file (ID: {file_id}) về máy: {str(e)}")
            return None
    
    def download_file_as_base64(self, file_id: str) -> Optional[str]:
        """
        Tải file từ Google Drive và trả về dưới dạng chuỗi base64.
        
        Args:
            file_id: ID của file cần tải về
            
        Returns:
            str: Chuỗi base64 của file hoặc None nếu thất bại
        """
        try:
            # Tải file vào bộ nhớ
            request = self.service.files().get_media(fileId=file_id)
            file_buffer = io.BytesIO()
            downloader = MediaIoBaseDownload(file_buffer, request)
            done = False
            while done is False:
                status, done = downloader.next_chunk()
            
            # Chuyển sang base64
            file_buffer.seek(0)
            base64_data = base64.b64encode(file_buffer.read()).decode('utf-8')
            
            logger.info(f"Đã tải về file (ID: {file_id}) dưới dạng base64")
            return base64_data
            
        except Exception as e:
            logger.error(f"Lỗi khi tải file (ID: {file_id}) dưới dạng base64: {str(e)}")
            return None
    
    def is_existing_file(self, filename: str, folder_id: Optional[str] = None) -> Optional[str]:
        """
        Kiểm tra xem file có tồn tại trên Drive không và trả về ID nếu có.
        
        Args:
            filename: Tên file cần kiểm tra
            folder_id: ID thư mục chứa file (My Drive nếu None)
            
        Returns:
            str: ID của file nếu tồn tại, None nếu không tồn tại hoặc có lỗi
        """
        try:
            # Xây dựng query
            query = f"name = '{filename}'"
            
            if folder_id:
                query += f" and '{folder_id}' in parents"
            
            query += " and trashed = false"
            
            # Tìm file
            response = self.service.files().list(
                q=query,
                spaces='drive',
                fields='files(id, name)'
            ).execute()
            
            files = response.get('files', [])
            
            # Trả về ID nếu tồn tại
            if files:
                logger.info(f"Đã tìm thấy file: {filename} (ID: {files[0].get('id')})")
                return files[0].get('id')
            
            # Không tìm thấy
            logger.info(f"Không tìm thấy file: {filename}")
            return None
            
        except Exception as e:
            logger.error(f"Lỗi khi kiểm tra file {filename} trên Google Drive: {str(e)}")
            return None