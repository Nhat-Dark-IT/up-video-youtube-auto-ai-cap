#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Script chạy hệ thống tạo video POV tự động về chủ đề Ai Cập cổ đại trên máy tính cục bộ.
Thiết lập môi trường, xác thực và chạy quy trình tạo video.
"""

import os
import sys
import subprocess
import argparse
import shutil
import time
import logging
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
# Thiết lập đường dẫn cơ bản
BASE_DIR = Path(__file__).resolve().parent
CREDENTIALS_DIR = BASE_DIR / "credentials"
TEMP_DIR = BASE_DIR / "temp"
LOGS_DIR = BASE_DIR / "logs"
ENV_FILE = CREDENTIALS_DIR / ".env"

# Thiết lập logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOGS_DIR / "run_locally.log") if LOGS_DIR.exists() else logging.StreamHandler(),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("run_locally")

def check_python_version():
    """
    Kiểm tra phiên bản Python đã đạt yêu cầu chưa.
    """
    required_version = (3, 8)
    current_version = sys.version_info
    
    if current_version < required_version:
        logger.error(f"Cần Python phiên bản {required_version[0]}.{required_version[1]} trở lên. "
                     f"Phiên bản hiện tại: {current_version[0]}.{current_version[1]}")
        return False
    
    logger.info(f"Đang sử dụng Python {current_version[0]}.{current_version[1]}.{current_version[2]}")
    return True

def check_ffmpeg():
    """
    Kiểm tra FFmpeg đã được cài đặt chưa.
    
    Returns:
        bool: True nếu đã cài đặt, False nếu chưa
    """
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"], 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            check=False
        )
        
        if result.returncode == 0:
            version_output = result.stdout.decode('utf-8').splitlines()[0]
            logger.info(f"Đã tìm thấy FFmpeg: {version_output}")
            return True
        else:
            logger.error("FFmpeg không được cài đặt hoặc không thể truy cập")
            return False
    
    except FileNotFoundError:
        logger.error("FFmpeg không được cài đặt hoặc không có trong PATH")
        return False

def setup_environment():
    """
    Thiết lập môi trường làm việc, tạo các thư mục cần thiết.
    
    Returns:
        bool: True nếu thiết lập thành công, False nếu thất bại
    """
    try:
        # Tạo thư mục cần thiết
        CREDENTIALS_DIR.mkdir(exist_ok=True)
        TEMP_DIR.mkdir(exist_ok=True)
        LOGS_DIR.mkdir(exist_ok=True)
        
        # Tạo các thư mục con trong temp
        (TEMP_DIR / "images").mkdir(exist_ok=True)
        (TEMP_DIR / "videos").mkdir(exist_ok=True)
        (TEMP_DIR / "audio").mkdir(exist_ok=True)
        
        # Kiểm tra file .env
        if not ENV_FILE.exists():
            example_env = CREDENTIALS_DIR / ".env.example"
            if example_env.exists():
                shutil.copy(example_env, ENV_FILE)
                logger.warning(f"Đã tạo file .env từ .env.example. Vui lòng cập nhật các thông tin xác thực trong {ENV_FILE}")
            else:
                logger.error("Không tìm thấy file .env.example để tạo file .env")
                logger.info("Vui lòng tạo file credentials/.env với các thông tin xác thực cần thiết")
        
        # Nạp biến môi trường từ file .env
        load_dotenv(ENV_FILE)
        
        # Kiểm tra file service account
        service_account_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        if service_account_path and not os.path.exists(service_account_path):
            logger.error(f"Không tìm thấy file service account: {service_account_path}")
            logger.info("Vui lòng đặt file service account JSON vào đúng vị trí hoặc cập nhật đường dẫn trong file .env")
        
        logger.info("Đã thiết lập môi trường làm việc thành công")
        return True
        
    except Exception as e:
        logger.error(f"Lỗi khi thiết lập môi trường: {str(e)}")
        return False

def check_dependencies():
    """
    Kiểm tra và cài đặt các thư viện Python cần thiết.
    
    Returns:
        bool: True nếu đã cài đặt đủ thư viện, False nếu có lỗi
    """
    try:
        # Kiểm tra file requirements.txt
        requirements_file = BASE_DIR / "requirements.txt"
        if not requirements_file.exists():
            logger.error(f"Không tìm thấy file requirements.txt")
            return False
        
        # Kiểm tra và cài đặt các thư viện
        logger.info("Kiểm tra các thư viện Python...")
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", str(requirements_file)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False
        )
        
        if result.returncode != 0:
            logger.error(f"Lỗi khi cài đặt thư viện: {result.stderr.decode('utf-8')}")
            return False
        
        logger.info("Đã cài đặt tất cả thư viện cần thiết")
        return True
        
    except Exception as e:
        logger.error(f"Lỗi khi kiểm tra và cài đặt thư viện: {str(e)}")
        return False

def validate_api_keys():
    """
    Kiểm tra các API key cần thiết đã được thiết lập chưa.
    
    Returns:
        bool: True nếu có đủ API key, False nếu thiếu
    """
    required_keys = [
        "GEMINI_API_KEY",
        "ELEVENLABS_API_KEY",
        "CREATOMATE_API_KEY",
        "GOOGLE_SHEETS_SPREADSHEET_ID",
        "GOOGLE_APPLICATION_CREDENTIALS"
    ]
    
    missing_keys = []
    for key in required_keys:
        if not os.getenv(key):
            missing_keys.append(key)
    
    if missing_keys:
        logger.error(f"Thiếu các API key sau: {', '.join(missing_keys)}")
        logger.info("Vui lòng cập nhật các API key trong file credentials/.env")
        return False
    
    # Kiểm tra các key YouTube nếu cần xuất bản
    youtube_keys = ["YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET", "YOUTUBE_REFRESH_TOKEN"]
    missing_youtube_keys = [key for key in youtube_keys if not os.getenv(key)]
    
    if missing_youtube_keys:
        logger.warning(f"Thiếu các API key YouTube: {', '.join(missing_youtube_keys)}")
        logger.warning("Có thể không xuất bản video lên YouTube")
    
    logger.info("Đã xác thực tất cả API key cần thiết")
    return True

def run_step(step_name, skip_prompt=False):
    """
    Chạy một bước cụ thể trong quy trình.
    
    Args:
        step_name: Tên bước cần chạy
        skip_prompt: Bỏ qua xác nhận từ người dùng
        
    Returns:
        int: Mã trạng thái (0 nếu thành công)
    """
    valid_steps = ["ideas", "prompts", "images", "videos", "audio", "compose", "publish", "all"]
    
    if step_name not in valid_steps:
        logger.error(f"Bước không hợp lệ: {step_name}")
        return 1
    
    if not skip_prompt and step_name != "all":
        confirmation = input(f"Bạn có muốn chạy bước '{step_name}'? (y/n): ")
        if confirmation.lower() != 'y':
            logger.info(f"Đã hủy chạy bước '{step_name}'")
            return 0
    
    try:
        if step_name == "all":
            logger.info("Chạy toàn bộ quy trình tạo video...")
            command = [sys.executable, "-m", "scripts.main", "--all"]
        else:
            logger.info(f"Chạy bước: {step_name}...")
            command = [sys.executable, "-m", "scripts.main", "--step", step_name]
        
        process = subprocess.run(command, check=False)
        
        if process.returncode == 0:
            logger.info(f"Đã chạy thành công bước '{step_name}'")
        else:
            logger.error(f"Lỗi khi chạy bước '{step_name}', mã lỗi: {process.returncode}")
        
        return process.returncode
    
    except Exception as e:
        logger.error(f"Lỗi khi chạy bước '{step_name}': {str(e)}")
        return 1

def run_custom_pipeline(start_step, end_step, skip_prompt=False):
    """
    Chạy một phần của quy trình từ start_step đến end_step.
    
    Args:
        start_step: Bước bắt đầu
        end_step: Bước kết thúc
        skip_prompt: Bỏ qua xác nhận từ người dùng
        
    Returns:
        int: Mã trạng thái (0 nếu thành công)
    """
    valid_steps = ["ideas", "prompts", "images", "videos", "audio", "compose", "publish"]
    
    if start_step not in valid_steps or end_step not in valid_steps:
        logger.error(f"Bước không hợp lệ: {start_step} hoặc {end_step}")
        return 1
    
    start_index = valid_steps.index(start_step)
    end_index = valid_steps.index(end_step)
    
    if start_index > end_index:
        logger.error(f"Bước bắt đầu ({start_step}) không thể sau bước kết thúc ({end_step})")
        return 1
    
    if not skip_prompt:
        confirmation = input(f"Bạn có muốn chạy quy trình từ '{start_step}' đến '{end_step}'? (y/n): ")
        if confirmation.lower() != 'y':
            logger.info(f"Đã hủy chạy quy trình")
            return 0
    
    try:
        logger.info(f"Chạy quy trình từ '{start_step}' đến '{end_step}'...")
        command = [sys.executable, "-m", "scripts.main", "--start", start_step, "--end", end_step]
        
        process = subprocess.run(command, check=False)
        
        if process.returncode == 0:
            logger.info(f"Đã chạy thành công quy trình từ '{start_step}' đến '{end_step}'")
        else:
            logger.error(f"Lỗi khi chạy quy trình, mã lỗi: {process.returncode}")
        
        return process.returncode
    
    except Exception as e:
        logger.error(f"Lỗi khi chạy quy trình: {str(e)}")
        return 1

def generate_youtube_tokens():
    """
    Tạo refresh token cho YouTube API bằng OAuth2.
    
    Returns:
        bool: True nếu tạo token thành công, False nếu thất bại
    """
    try:
        logger.info("Bắt đầu quy trình xác thực YouTube...")
        print("\n===== Tạo YouTube Refresh Token =====")
        print("Quy trình này sẽ mở trình duyệt để bạn xác thực với Google.")
        print("Sau khi xác thực, token sẽ được lưu vào file .env")
        
        confirmation = input("Tiếp tục? (y/n): ")
        if confirmation.lower() != 'y':
            logger.info("Đã hủy quy trình xác thực YouTube")
            return False
        
        # Kiểm tra client ID và client secret
        client_id = os.getenv("YOUTUBE_CLIENT_ID")
        client_secret = os.getenv("YOUTUBE_CLIENT_SECRET")
        
        if not client_id or not client_secret:
            logger.error("Thiếu YOUTUBE_CLIENT_ID hoặc YOUTUBE_CLIENT_SECRET trong file .env")
            return False
        
        # Tạo file tạm thời chứa client_secrets.json
        client_secrets = {
            "installed": {
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob", "http://localhost"],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token"
            }
        }
        
        temp_client_secrets_file = TEMP_DIR / "client_secrets.json"
        with open(temp_client_secrets_file, 'w') as f:
            json.dump(client_secrets, f)
        
        # Tạo script tạm thời để lấy token
        token_script = """
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

flow = InstalledAppFlow.from_client_secrets_file(
    'temp/client_secrets.json',
    scopes=SCOPES
)

credentials = flow.run_local_server(port=8080)

print(f"Access Token: {credentials.token}")
print(f"Refresh Token: {credentials.refresh_token}")
"""
        
        temp_token_script = TEMP_DIR / "get_youtube_token.py"
        with open(temp_token_script, 'w') as f:
            f.write(token_script)
        
        # Chạy script để lấy token
        print("\nĐang mở trình duyệt để xác thực với Google...\n")
        process = subprocess.run(
            [sys.executable, str(temp_token_script)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False
        )
        
        if process.returncode != 0:
            logger.error(f"Lỗi khi lấy token: {process.stderr.decode('utf-8')}")
            return False
        
        # Trích xuất refresh token từ output
        output = process.stdout.decode('utf-8')
        refresh_token_line = [line for line in output.splitlines() if "Refresh Token:" in line]
        
        if not refresh_token_line:
            logger.error("Không thể trích xuất refresh token từ output")
            return False
        
        refresh_token = refresh_token_line[0].split("Refresh Token:")[1].strip()
        
        # Cập nhật file .env
        env_content = ""
        with open(ENV_FILE, 'r') as f:
            env_content = f.read()
        
        if "YOUTUBE_REFRESH_TOKEN=" in env_content:
            # Thay thế giá trị token hiện có
            env_lines = env_content.splitlines()
            for i, line in enumerate(env_lines):
                if line.startswith("YOUTUBE_REFRESH_TOKEN="):
                    env_lines[i] = f"YOUTUBE_REFRESH_TOKEN={refresh_token}"
                    break
            env_content = "\n".join(env_lines)
        else:
            # Thêm token mới
            env_content += f"\nYOUTUBE_REFRESH_TOKEN={refresh_token}"
        
        with open(ENV_FILE, 'w') as f:
            f.write(env_content)
        
        # Nạp lại biến môi trường
        os.environ["YOUTUBE_REFRESH_TOKEN"] = refresh_token
        
        # Xóa file tạm
        os.remove(temp_client_secrets_file)
        os.remove(temp_token_script)
        
        logger.info("Đã tạo và lưu YouTube refresh token thành công")
        print("\n✅ Đã tạo và lưu YouTube refresh token thành công!")
        print(f"Token đã được lưu vào file {ENV_FILE}")
        return True
        
    except Exception as e:
        logger.error(f"Lỗi khi tạo YouTube token: {str(e)}")
        return False

def print_menu():
    """
    Hiển thị menu chính.
    """
    print("\n===== Hệ thống tạo video POV tự động về Ai Cập cổ đại =====")
    print("1. Chạy toàn bộ quy trình")
    print("2. Chạy một bước cụ thể")
    print("3. Chạy quy trình tùy chỉnh")
    print("4. Tạo YouTube Refresh Token")
    print("5. Kiểm tra môi trường và cài đặt")
    print("0. Thoát")
    print("============================================================")

def interactive_mode():
    """
    Chạy chế độ tương tác với người dùng.
    """
    while True:
        print_menu()
        choice = input("Nhập lựa chọn của bạn: ")
        
        if choice == "0":
            print("Tạm biệt!")
            break
            
        elif choice == "1":
            run_step("all")
            
        elif choice == "2":
            print("\nCác bước có thể chạy:")
            print("1. ideas - Tạo ý tưởng POV")
            print("2. prompts - Tăng cường prompt")
            print("3. images - Tạo hình ảnh")
            print("4. videos - Xử lý video")
            print("5. audio - Tạo âm thanh")
            print("6. compose - Ghép video")
            print("7. publish - Đăng tải YouTube")
            
            step_choice = input("\nNhập tên bước cần chạy: ")
            valid_steps = ["ideas", "prompts", "images", "videos", "audio", "compose", "publish"]
            
            if step_choice in valid_steps:
                run_step(step_choice)
            else:
                print(f"Bước không hợp lệ: {step_choice}")
                
        elif choice == "3":
            print("\nCác bước trong quy trình:")
            print("1. ideas - Tạo ý tưởng POV")
            print("2. prompts - Tăng cường prompt")
            print("3. images - Tạo hình ảnh")
            print("4. videos - Xử lý video")
            print("5. audio - Tạo âm thanh")
            print("6. compose - Ghép video")
            print("7. publish - Đăng tải YouTube")
            
            start_step = input("\nNhập bước bắt đầu: ")
            end_step = input("Nhập bước kết thúc: ")
            
            valid_steps = ["ideas", "prompts", "images", "videos", "audio", "compose", "publish"]
            if start_step in valid_steps and end_step in valid_steps:
                run_custom_pipeline(start_step, end_step)
            else:
                print(f"Bước không hợp lệ: {start_step} hoặc {end_step}")
                
        elif choice == "4":
            generate_youtube_tokens()
            
        elif choice == "5":
            print("\nĐang kiểm tra môi trường và cài đặt...")
            python_ok = check_python_version()
            ffmpeg_ok = check_ffmpeg()
            env_ok = setup_environment()
            deps_ok = check_dependencies()
            api_ok = validate_api_keys()
            
            print("\n===== Kết quả kiểm tra =====")
            print(f"Python: {'✅ OK' if python_ok else '❌ Không đạt yêu cầu'}")
            print(f"FFmpeg: {'✅ OK' if ffmpeg_ok else '❌ Không tìm thấy'}")
            print(f"Môi trường: {'✅ OK' if env_ok else '❌ Có lỗi'}")
            print(f"Thư viện: {'✅ OK' if deps_ok else '❌ Thiếu thư viện'}")
            print(f"API Keys: {'✅ OK' if api_ok else '❌ Thiếu API key'}")
            
            if all([python_ok, ffmpeg_ok, env_ok, deps_ok, api_ok]):
                print("\n✅ Tất cả đều sẵn sàng! Bạn có thể chạy hệ thống.")
            else:
                print("\n❌ Có một số vấn đề cần khắc phục. Vui lòng xem log để biết thêm chi tiết.")
                
        else:
            print("Lựa chọn không hợp lệ!")
        
        input("\nNhấn Enter để tiếp tục...")

def parse_args():
    """
    Phân tích tham số dòng lệnh.
    
    Returns:
        argparse.Namespace: Các tham số dòng lệnh
    """
    parser = argparse.ArgumentParser(description="Hệ thống tạo video POV tự động về Ai Cập cổ đại")
    
    parser.add_argument("--step", choices=["ideas", "prompts", "images", "videos", "audio", "compose", "publish", "all"],
                        help="Chạy một bước cụ thể trong quy trình")
    
    parser.add_argument("--start", 
                        help="Bước bắt đầu của quy trình (dùng cùng với --end)")
    
    parser.add_argument("--end", 
                        help="Bước kết thúc của quy trình (dùng cùng với --start)")
    
    parser.add_argument("--setup", action="store_true",
                        help="Thiết lập môi trường và kiểm tra cài đặt")
    
    parser.add_argument("--youtube-token", action="store_true",
                        help="Tạo YouTube refresh token")
    
    parser.add_argument("--yes", "-y", action="store_true",
                        help="Tự động xác nhận tất cả các lệnh không cần hỏi")
    
    parser.add_argument("--interactive", "-i", action="store_true",
                        help="Chạy chế độ tương tác với menu")
    
    return parser.parse_args()

def main():
    """
    Hàm chính của script.
    """
    # Tạo thư mục logs nếu chưa tồn tại
    LOGS_DIR.mkdir(exist_ok=True)
    
    args = parse_args()
    
    # Chế độ tương tác
    if args.interactive:
        # Kiểm tra môi trường trước
        setup_environment()
        interactive_mode()
        return 0
    
    # Thiết lập môi trường
    if args.setup or (not any([args.step, args.start, args.end, args.youtube_token])):
        python_ok = check_python_version()
        ffmpeg_ok = check_ffmpeg()
        env_ok = setup_environment()
        deps_ok = check_dependencies()
        api_ok = validate_api_keys()
        
        if all([python_ok, ffmpeg_ok, env_ok, deps_ok, api_ok]):
            logger.info("Môi trường đã sẵn sàng để chạy hệ thống")
        else:
            logger.error("Có vấn đề với môi trường. Vui lòng kiểm tra log để biết thêm chi tiết")
            return 1
    else:
        # Chỉ thiết lập cơ bản nếu không phải --setup
        setup_environment()
    
    # Tạo YouTube token
    if args.youtube_token:
        success = generate_youtube_tokens()
        return 0 if success else 1
    
    # Chạy bước cụ thể
    if args.step:
        return run_step(args.step, skip_prompt=args.yes)
    
    # Chạy quy trình tùy chỉnh
    if args.start and args.end:
        return run_custom_pipeline(args.start, args.end, skip_prompt=args.yes)
    
    # Hiển thị trợ giúp nếu không có tham số
    if not any([args.step, args.start and args.end, args.setup, args.youtube_token]):
        print("Để biết cách sử dụng, chạy: python run_locally.py --help")
        print("Hoặc chạy chế độ tương tác: python run_locally.py --interactive")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())