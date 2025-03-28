#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Module tiện ích xử lý dữ liệu base64 trong hệ thống tạo video POV.
Cung cấp các hàm để mã hóa, giải mã và xử lý dữ liệu dưới dạng base64.
"""

import os
import base64
import re
import logging
from io import BytesIO
from typing import Optional, Union, Tuple, Dict
from pathlib import Path
import mimetypes

# Thiết lập logging
logger = logging.getLogger(__name__)

# Ánh xạ các định dạng phổ biến
MIME_EXTENSIONS = {
    'image/png': '.png',
    'image/jpeg': '.jpg',
    'image/jpg': '.jpg',
    'video/mp4': '.mp4',
    'audio/mpeg': '.mp3',
    'audio/mp3': '.mp3',
}

# Ánh xạ ngược lại từ phần mở rộng tới MIME type
EXTENSION_MIME = {v: k for k, v in MIME_EXTENSIONS.items()}


def encode_file_to_base64(file_path: str) -> str:
    """
    Mã hóa file thành chuỗi base64.
    
    Args:
        file_path: Đường dẫn đến file cần mã hóa
        
    Returns:
        Chuỗi base64 đã mã hóa
        
    Raises:
        FileNotFoundError: Nếu file không tồn tại
    """
    try:
        with open(file_path, 'rb') as file:
            file_data = file.read()
            encoded_data = base64.b64encode(file_data).decode('utf-8')
            return encoded_data
    except FileNotFoundError:
        logger.error(f"Không tìm thấy file: {file_path}")
        raise
    except Exception as e:
        logger.error(f"Lỗi khi mã hóa file {file_path}: {str(e)}")
        raise


def decode_base64_to_bytes(base64_data: str) -> bytes:
    """
    Giải mã chuỗi base64 thành dữ liệu bytes.
    
    Args:
        base64_data: Chuỗi base64 cần giải mã
        
    Returns:
        Dữ liệu bytes sau khi giải mã
        
    Raises:
        ValueError: Nếu chuỗi base64 không hợp lệ
    """
    try:
        # Xóa header nếu có (ví dụ: data:image/png;base64,)
        if ',' in base64_data:
            base64_data = base64_data.split(',')[1]
        
        # Giải mã chuỗi base64
        decoded_data = base64.b64decode(base64_data)
        return decoded_data
    except Exception as e:
        logger.error(f"Lỗi khi giải mã chuỗi base64: {str(e)}")
        raise ValueError(f"Chuỗi base64 không hợp lệ: {str(e)}")


def save_base64_to_file(base64_data: str, output_path: str, mime_type: Optional[str] = None) -> str:
    """
    Lưu dữ liệu base64 vào file trên đĩa.
    
    Args:
        base64_data: Chuỗi base64 cần lưu
        output_path: Đường dẫn file đầu ra
        mime_type: Loại MIME của dữ liệu (tùy chọn)
        
    Returns:
        Đường dẫn đầy đủ đến file đã lưu
        
    Raises:
        IOError: Nếu không thể ghi file
    """
    try:
        # Tạo thư mục chứa nếu chưa tồn tại
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        
        # Giải mã base64
        decoded_data = decode_base64_to_bytes(base64_data)
        
        # Ghi dữ liệu vào file
        with open(output_path, 'wb') as file:
            file.write(decoded_data)
            
        logger.debug(f"Đã lưu dữ liệu base64 vào file: {output_path}")
        return output_path
    except Exception as e:
        logger.error(f"Lỗi khi lưu dữ liệu base64 vào file {output_path}: {str(e)}")
        raise IOError(f"Không thể lưu file: {str(e)}")


def save_base64_to_file_in_memory(base64_data: str, filename: Optional[str] = None, 
                                  mime_type: Optional[str] = None) -> BytesIO:
    """
    Lưu dữ liệu base64 vào đối tượng BytesIO (lưu trong bộ nhớ).
    
    Args:
        base64_data: Chuỗi base64 cần lưu
        filename: Tên file (chỉ để truy xuất thông tin, không ghi ra đĩa)
        mime_type: Loại MIME của dữ liệu (tùy chọn)
        
    Returns:
        Đối tượng BytesIO chứa dữ liệu đã giải mã
    """
    try:
        # Giải mã base64
        decoded_data = decode_base64_to_bytes(base64_data)
        
        # Tạo đối tượng BytesIO
        buffer = BytesIO(decoded_data)
        
        # Đặt tên cho buffer để tiện theo dõi (nếu cần)
        if filename:
            buffer.name = filename
            
        return buffer
    except Exception as e:
        logger.error(f"Lỗi khi lưu dữ liệu base64 vào bộ nhớ: {str(e)}")
        raise


def extract_mime_from_base64(base64_data: str) -> Optional[str]:
    """
    Trích xuất loại MIME từ chuỗi base64 (nếu có header).
    
    Args:
        base64_data: Chuỗi base64 cần trích xuất
        
    Returns:
        Loại MIME hoặc None nếu không tìm thấy
    """
    try:
        # Tìm kiếm header trong chuỗi base64
        mime_match = re.match(r'data:([^;]+);base64,', base64_data)
        if mime_match:
            return mime_match.group(1)
        return None
    except Exception as e:
        logger.error(f"Lỗi khi trích xuất MIME từ chuỗi base64: {str(e)}")
        return None


def get_extension_from_mime(mime_type: str) -> str:
    """
    Lấy phần mở rộng file từ loại MIME.
    
    Args:
        mime_type: Loại MIME cần chuyển đổi
        
    Returns:
        Phần mở rộng file (ví dụ: '.png', '.mp4')
    """
    return MIME_EXTENSIONS.get(mime_type, mimetypes.guess_extension(mime_type) or '.bin')


def guess_mime_from_base64_content(base64_data: str) -> str:
    """
    Đoán loại MIME từ nội dung chuỗi base64.
    
    Args:
        base64_data: Chuỗi base64 cần phân tích
        
    Returns:
        Loại MIME đoán được hoặc 'application/octet-stream' nếu không xác định được
    """
    try:
        # Giải mã và kiểm tra một số byte đầu tiên
        decoded_data = decode_base64_to_bytes(base64_data)
        
        # Kiểm tra signature của file
        if decoded_data.startswith(b'\x89PNG\r\n\x1a\n'):
            return 'image/png'
        elif decoded_data.startswith(b'\xff\xd8\xff'):
            return 'image/jpeg'
        elif decoded_data.startswith(b'\x1aE\xdf\xa3'):
            return 'video/webm'
        elif decoded_data[4:12] == b'ftypmp4':
            return 'video/mp4'
        elif decoded_data.startswith(b'ID3') or decoded_data.startswith(b'\xff\xfb'):
            return 'audio/mpeg'
            
        # Mặc định nếu không xác định được
        return 'application/octet-stream'
    except Exception as e:
        logger.error(f"Lỗi khi đoán loại MIME từ nội dung base64: {str(e)}")
        return 'application/octet-stream'


def is_valid_base64(base64_data: str) -> bool:
    """
    Kiểm tra chuỗi base64 có hợp lệ không.
    
    Args:
        base64_data: Chuỗi base64 cần kiểm tra
        
    Returns:
        True nếu hợp lệ, False nếu không
    """
    # Loại bỏ header nếu có
    if ',' in base64_data:
        base64_data = base64_data.split(',')[1]
    
    # Kiểm tra độ dài và các ký tự hợp lệ
    try:
        # Thêm padding nếu thiếu
        padding = 4 - (len(base64_data) % 4) if len(base64_data) % 4 else 0
        base64_data += '=' * padding
        
        # Kiểm tra xem có giải mã được không
        base64.b64decode(base64_data)
        return True
    except Exception:
        return False


def create_data_uri(base64_data: str, mime_type: str) -> str:
    """
    Tạo URI dữ liệu từ chuỗi base64 và loại MIME.
    
    Args:
        base64_data: Chuỗi base64 (không có header)
        mime_type: Loại MIME của dữ liệu
        
    Returns:
        Chuỗi URI dữ liệu hoàn chỉnh (data:[<MIME-type>];base64,<data>)
    """
    # Loại bỏ header nếu đã có
    if ',' in base64_data:
        base64_data = base64_data.split(',')[1]
        
    return f"data:{mime_type};base64,{base64_data}"


def get_file_size_from_base64(base64_data: str) -> int:
    """
    Tính kích thước file (byte) từ chuỗi base64.
    
    Args:
        base64_data: Chuỗi base64 cần tính kích thước
        
    Returns:
        Kích thước file tính bằng byte
    """
    # Loại bỏ header nếu có
    if ',' in base64_data:
        base64_data = base64_data.split(',')[1]
    
    # Tính kích thước theo công thức
    padding = base64_data.count('=')
    return (len(base64_data) * 3 // 4) - padding


def convert_image_format(base64_data: str, target_format: str = 'png') -> str:
    """
    Chuyển đổi định dạng ảnh base64 (ví dụ từ JPEG sang PNG).
    
    Args:
        base64_data: Chuỗi base64 ảnh gốc
        target_format: Định dạng đích ('png', 'jpeg',...)
        
    Returns:
        Chuỗi base64 của ảnh đã chuyển đổi
    """
    try:
        from PIL import Image
        
        # Tạo đối tượng BytesIO từ base64
        buffer = save_base64_to_file_in_memory(base64_data)
        
        # Mở ảnh bằng Pillow
        image = Image.open(buffer)
        
        # Chuyển đổi và lưu vào buffer mới
        output = BytesIO()
        image.save(output, format=target_format.upper())
        output.seek(0)
        
        # Mã hóa lại thành base64
        converted_base64 = base64.b64encode(output.read()).decode('utf-8')
        
        # Thêm header MIME phù hợp
        mime_type = f'image/{target_format.lower()}'
        return create_data_uri(converted_base64, mime_type)
    except ImportError:
        logger.error("Thư viện Pillow không được cài đặt. Không thể chuyển đổi ảnh.")
        raise
    except Exception as e:
        logger.error(f"Lỗi khi chuyển đổi định dạng ảnh: {str(e)}")
        raise