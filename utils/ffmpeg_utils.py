#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Module tiện ích xử lý video với FFmpeg cho hệ thống tạo video POV.
Cung cấp các hàm để thực hiện các tác vụ xử lý video/hình ảnh thông qua FFmpeg.
"""

import os
import subprocess
import logging
import tempfile
import time
import base64
from pathlib import Path
from typing import List, Dict, Optional, Union, Tuple, Any
import shlex
import json
from io import BytesIO

# Import các module nội bộ
from config import settings
from utils.base64_utils import decode_base64_to_bytes, save_base64_to_file_in_memory, encode_file_to_base64

# Thiết lập logging
logger = logging.getLogger(__name__)

def check_ffmpeg_installed() -> bool:
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

def run_ffmpeg_command(command: Union[str, List[str]], timeout: Optional[int] = None) -> Tuple[int, str, str]:
    """
    Chạy lệnh FFmpeg và trả về kết quả.
    
    Args:
        command: Lệnh FFmpeg dưới dạng chuỗi hoặc danh sách các tham số
        timeout: Thời gian chờ tối đa (giây), None cho không giới hạn
    
    Returns:
        Tuple gồm (exit_code, stdout, stderr)
    """
    if isinstance(command, str):
        args = shlex.split(command)
    else:
        args = command
    
    logger.debug(f"Chạy lệnh FFmpeg: {' '.join(args)}")
    
    try:
        process = subprocess.Popen(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )
        
        stdout, stderr = process.communicate(timeout=timeout)
        return process.returncode, stdout, stderr
    
    except subprocess.TimeoutExpired:
        process.kill()
        logger.error(f"Lệnh FFmpeg bị timeout sau {timeout} giây")
        return -1, "", "Timeout"
    
    except Exception as e:
        logger.error(f"Lỗi khi chạy lệnh FFmpeg: {str(e)}")
        return -1, "", str(e)

def create_zoom_video_from_image(image_path: str, output_path: str, 
                               duration: int = 10, zoom_filter: str = "zoompan=z='min(zoom+0.0015,1.5)':d=300") -> bool:
    """
    Tạo video với hiệu ứng zoom từ hình ảnh tĩnh sử dụng FFmpeg.
    
    Args:
        image_path: Đường dẫn đến file hình ảnh
        output_path: Đường dẫn lưu file video
        duration: Thời lượng video (giây)
        zoom_filter: Bộ lọc FFmpeg cho hiệu ứng zoom
        
    Returns:
        bool: True nếu thành công, False nếu thất bại
    """
    try:
        # Tạo lệnh FFmpeg
        command = [
            "ffmpeg",
            "-y",  # Ghi đè output nếu đã tồn tại
            "-loop", "1", # Lặp hình ảnh
            "-i", image_path,  # Đường dẫn hình ảnh đầu vào
            "-vf", zoom_filter,  # Bộ lọc zoom
            "-c:v", "libx264",  # Codec video
            "-t", str(duration),  # Thời lượng video
            "-pix_fmt", "yuv420p",  # Định dạng pixel
            "-preset", "medium",  # Preset mã hóa
            "-profile:v", "high",  # Profile H.264
            "-crf", "23",  # Chất lượng video
            "-movflags", "+faststart",  # Tối ưu cho streaming
            output_path  # Đường dẫn video đầu ra
        ]
        
        # Thực thi lệnh
        logger.info(f"Đang chạy lệnh FFmpeg: {' '.join(command)}")
        result = subprocess.run(command, 
                              stdout=subprocess.PIPE, 
                              stderr=subprocess.PIPE,
                              check=False)
        
        # Kiểm tra kết quả
        if result.returncode == 0:
            logger.info(f"Đã tạo video thành công: {output_path}")
            return True
        else:
            logger.error(f"Lỗi khi tạo video: {result.stderr.decode('utf-8', errors='ignore')}")
            return False
            
    except Exception as e:
        logger.error(f"Lỗi khi tạo video với FFmpeg: {str(e)}")
        return False
def create_zoom_video_from_base64(image_base64: str, 
                                 duration: int = 5,
                                 zoom_filter: Optional[str] = None) -> Optional[str]:
    """
    Tạo video với hiệu ứng zoom từ hình ảnh dạng base64, trả về video dạng base64.
    
    Args:
        image_base64: Chuỗi base64 chứa dữ liệu hình ảnh
        duration: Thời lượng video (giây)
        zoom_filter: Bộ lọc zoom tùy chỉnh
    
    Returns:
        str: Chuỗi base64 của video đã tạo, hoặc None nếu thất bại
    """
    if not zoom_filter:
        zoom_filter = settings.FFMPEG_ZOOM_FILTER
    
    # Tạo tệp tạm thời cho đầu vào và đầu ra
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as input_file, \
         tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as output_file:
        
        try:
            # Lưu hình ảnh base64 vào file tạm
            input_file.write(decode_base64_to_bytes(image_base64))
            input_file.flush()
            input_path = input_file.name
            output_path = output_file.name
            
            # Đóng file trước khi sử dụng với FFmpeg
            input_file.close()
            output_file.close()
            
            # Tạo video
            success = create_zoom_video_from_image(
                input_path, output_path, duration, zoom_filter
            )
            
            if not success:
                logger.error("Không thể tạo video từ hình ảnh base64")
                return None
            
            # Đọc video và chuyển thành base64
            video_base64 = encode_file_to_base64(output_path)
            logger.info(f"Đã tạo video thành công, kích thước base64: {len(video_base64)} bytes")
            return video_base64
            
        except Exception as e:
            logger.error(f"Lỗi khi xử lý video từ hình ảnh base64: {str(e)}")
            return None
        
        finally:
            # Dọn dẹp tệp tạm
            try:
                if os.path.exists(input_path):
                    os.unlink(input_path)
                if os.path.exists(output_path):
                    os.unlink(output_path)
            except Exception as e:
                logger.warning(f"Không thể xóa tệp tạm: {str(e)}")

def process_multiple_images(image_base64_list: List[str], 
                          durations: Union[int, List[int]] = 5) -> List[Dict[str, Any]]:
    """
    Xử lý nhiều hình ảnh base64 và tạo video cho mỗi hình ảnh.
    
    Args:
        image_base64_list: Danh sách các chuỗi base64 của hình ảnh
        durations: Thời lượng video (giây) hoặc danh sách thời lượng cho từng video
    
    Returns:
        List[Dict]: Danh sách các kết quả, mỗi kết quả chứa base64 video và thông tin khác
    """
    results = []
    
    # Chuẩn bị danh sách thời lượng
    if isinstance(durations, int):
        durations = [durations] * len(image_base64_list)
    elif len(durations) < len(image_base64_list):
        durations = durations + [durations[-1]] * (len(image_base64_list) - len(durations))
    
    # Xử lý từng hình ảnh
    for index, (image_base64, duration) in enumerate(zip(image_base64_list, durations)):
        try:
            logger.info(f"Đang xử lý hình ảnh {index+1}/{len(image_base64_list)}")
            
            # Tạo video với hiệu ứng zoom
            video_base64 = create_zoom_video_from_base64(
                image_base64=image_base64,
                duration=duration
            )
            
            if video_base64:
                results.append({
                    'index': index,
                    'video_base64': video_base64,
                    'duration': duration,
                    'success': True
                })
            else:
                results.append({
                    'index': index,
                    'success': False,
                    'error': 'Không thể tạo video'
                })
                
            # Tạm nghỉ để tránh quá tải CPU
            time.sleep(0.1)
            
        except Exception as e:
            logger.error(f"Lỗi khi xử lý hình ảnh {index+1}: {str(e)}")
            results.append({
                'index': index,
                'success': False,
                'error': str(e)
            })
    
    # Tóm tắt kết quả
    success_count = sum(1 for r in results if r.get('success', False))
    logger.info(f"Hoàn thành xử lý {success_count}/{len(image_base64_list)} hình ảnh")
    
    return results

def create_custom_zoom_filter(start_zoom: float = 1.0, 
                             end_zoom: float = 1.5,
                             zoom_speed: float = 0.002,
                             width: int = 540, 
                             height: int = 960) -> str:
    """
    Tạo chuỗi bộ lọc zoom tùy chỉnh cho FFmpeg.
    
    Args:
        start_zoom: Độ zoom ban đầu (1.0 = 100%)
        end_zoom: Độ zoom cuối cùng
        zoom_speed: Tốc độ zoom mỗi khung hình
        width: Chiều rộng đầu ra
        height: Chiều cao đầu ra
    
    Returns:
        str: Chuỗi bộ lọc zoom cho FFmpeg
    """
    return (f"zoompan=z='min(max(1,zoom+{zoom_speed}),{end_zoom})':d=125:s={width}x{height}:"
            f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)',format=yuv420p")

def extract_video_info(video_path: str) -> Dict[str, Any]:
    """
    Trích xuất thông tin về file video sử dụng FFmpeg.
    
    Args:
        video_path: Đường dẫn tới file video
    
    Returns:
        Dict: Thông tin video bao gồm duration, dimensions, codec, vv.
    """
    command = [
        'ffprobe', '-v', 'error', 
        '-show_entries', 'format=duration,size,bit_rate:stream=width,height,codec_name,codec_type',
        '-of', 'json', video_path
    ]
    
    exit_code, stdout, stderr = run_ffmpeg_command(command)
    
    if exit_code != 0:
        logger.error(f"Không thể trích xuất thông tin video: {stderr}")
        return {}
    
    try:
        info = json.loads(stdout)
        
        # Xử lý dữ liệu trả về để dễ sử dụng hơn
        result = {
            'duration': float(info.get('format', {}).get('duration', 0)),
            'size_bytes': int(info.get('format', {}).get('size', 0)),
            'bit_rate': int(info.get('format', {}).get('bit_rate', 0)),
        }
        
        # Trích xuất thông tin các streams
        video_stream = None
        audio_stream = None
        
        for stream in info.get('streams', []):
            if stream.get('codec_type') == 'video' and not video_stream:
                video_stream = stream
            elif stream.get('codec_type') == 'audio' and not audio_stream:
                audio_stream = stream
        
        if video_stream:
            result['width'] = int(video_stream.get('width', 0))
            result['height'] = int(video_stream.get('height', 0))
            result['video_codec'] = video_stream.get('codec_name', 'unknown')
        
        if audio_stream:
            result['audio_codec'] = audio_stream.get('codec_name', 'unknown')
        
        return result
    
    except Exception as e:
        logger.error(f"Lỗi khi phân tích thông tin video: {str(e)}")
        return {}

def extract_frame_from_video(video_path: str, time_position: float = 0, output_path: Optional[str] = None) -> Optional[str]:
    """
    Trích xuất một khung hình từ video tại vị trí thời gian xác định.
    
    Args:
        video_path: Đường dẫn tới file video
        time_position: Vị trí thời gian (giây)
        output_path: Đường dẫn lưu khung hình, nếu None sẽ tạo tạm
    
    Returns:
        str: Đường dẫn tới file hình ảnh hoặc None nếu thất bại
    """
    # Tạo đường dẫn đầu ra nếu chưa có
    temp_file = output_path is None
    if temp_file:
        fd, output_path = tempfile.mkstemp(suffix='.png')
        os.close(fd)
    
    command = [
        'ffmpeg', '-y', '-ss', str(time_position),
        '-i', video_path, '-vframes', '1',
        '-q:v', '2', output_path
    ]
    
    exit_code, stdout, stderr = run_ffmpeg_command(command)
    
    if exit_code != 0:
        logger.error(f"Không thể trích xuất khung hình: {stderr}")
        if temp_file and os.path.exists(output_path):
            os.unlink(output_path)
        return None
    
    logger.info(f"Đã trích xuất khung hình tại {time_position}s ra {output_path}")
    return output_path

def create_video_batch(image_paths: List[str], output_path: str, duration_per_image: int = 5) -> bool:
    """
    Tạo video từ nhiều hình ảnh, mỗi hình ảnh hiển thị trong một khoảng thời gian nhất định.
    
    Args:
        image_paths: Danh sách đường dẫn tới các file hình ảnh
        output_path: Đường dẫn lưu file video đầu ra
        duration_per_image: Thời lượng mỗi hình ảnh (giây)
    
    Returns:
        bool: True nếu thành công, False nếu thất bại
    """
    # Tạo file danh sách hình ảnh tạm thời
    fd, concat_list_path = tempfile.mkstemp(suffix='.txt')
    os.close(fd)
    
    try:
        with open(concat_list_path, 'w') as f:
            for img_path in image_paths:
                # Định dạng theo yêu cầu của FFmpeg concat demuxer
                f.write(f"file '{img_path}'\n")
                f.write(f"duration {duration_per_image}\n")
            
            # Thêm hình ảnh cuối cùng lần nữa (yêu cầu của concat demuxer)
            if image_paths:
                f.write(f"file '{image_paths[-1]}'\n")
        
        command = [
            'ffmpeg', '-y', '-f', 'concat', '-safe', '0',
            '-i', concat_list_path, '-vsync', 'vfr',
            '-pix_fmt', 'yuv420p', output_path
        ]
        
        exit_code, stdout, stderr = run_ffmpeg_command(command)
        
        if exit_code != 0:
            logger.error(f"Không thể tạo video từ danh sách hình ảnh: {stderr}")
            return False
        
        logger.info(f"Đã tạo video từ {len(image_paths)} hình ảnh: {output_path}")
        return True
    
    except Exception as e:
        logger.error(f"Lỗi khi tạo video từ danh sách hình ảnh: {str(e)}")
        return False
    
    finally:
        # Dọn dẹp tệp tạm
        if os.path.exists(concat_list_path):
            os.unlink(concat_list_path)

def add_fade_effects(video_path: str, output_path: str, fade_in_duration: float = 0.5, fade_out_duration: float = 0.5) -> bool:
    """
    Thêm hiệu ứng làm mờ vào đầu và cuối video.
    
    Args:
        video_path: Đường dẫn tới file video đầu vào
        output_path: Đường dẫn lưu file video đầu ra
        fade_in_duration: Thời lượng hiệu ứng fade in (giây)
        fade_out_duration: Thời lượng hiệu ứng fade out (giây)
    
    Returns:
        bool: True nếu thành công, False nếu thất bại
    """
    # Lấy thông tin video để biết thời lượng
    info = extract_video_info(video_path)
    if not info:
        logger.error("Không thể lấy thông tin video để thêm hiệu ứng fade")
        return False
    
    duration = info.get('duration', 0)
    if duration <= fade_in_duration + fade_out_duration:
        logger.warning("Video quá ngắn để thêm hiệu ứng fade, giảm thời lượng fade")
        fade_in_duration = fade_out_duration = min(0.2, duration / 4)
    
    filter_complex = (f"fade=t=in:st=0:d={fade_in_duration},"
                      f"fade=t=out:st={duration-fade_out_duration}:d={fade_out_duration}")
    
    command = [
        'ffmpeg', '-y', '-i', video_path,
        '-vf', filter_complex,
        '-c:a', 'copy', output_path
    ]
    
    exit_code, stdout, stderr = run_ffmpeg_command(command)
    
    if exit_code != 0:
        logger.error(f"Không thể thêm hiệu ứng fade: {stderr}")
        return False
    
    logger.info(f"Đã thêm hiệu ứng fade vào video: {output_path}")
    return True

def combine_video_audio(video_path: str, audio_path: str, output_path: str, audio_volume: float = 1.0) -> bool:
    """
    Kết hợp video và âm thanh thành một file mới.
    
    Args:
        video_path: Đường dẫn tới file video
        audio_path: Đường dẫn tới file âm thanh
        output_path: Đường dẫn lưu file video đầu ra
        audio_volume: Âm lượng âm thanh (1.0 = nguyên bản)
    
    Returns:
        bool: True nếu thành công, False nếu thất bại
    """
    command = [
        'ffmpeg', '-y', '-i', video_path, '-i', audio_path,
        '-filter_complex', f"[1:a]volume={audio_volume}[a]", 
        '-map', '0:v', '-map', '[a]',
        '-c:v', 'copy', '-shortest', output_path
    ]
    
    exit_code, stdout, stderr = run_ffmpeg_command(command)
    
    if exit_code != 0:
        logger.error(f"Không thể kết hợp video và âm thanh: {stderr}")
        return False
    
    logger.info(f"Đã kết hợp video và âm thanh thành: {output_path}")
    return True