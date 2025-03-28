# config/settings.py
import os
import logging
from dotenv import load_dotenv
import pathlib
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
# =============================================================================
# Basic Configuration
# =============================================================================

# Load environment variables
load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.dirname(__file__)), 'credentials', '.env'))

# Base paths
BASE_DIR = pathlib.Path(__file__).parent.parent.absolute()
TEMP_DIR = BASE_DIR / "temp"
CREDENTIALS_DIR = BASE_DIR / "credentials"
LOGS_DIR = BASE_DIR / "logs"

# Create necessary directories
TEMP_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)
(TEMP_DIR / "images").mkdir(exist_ok=True)
(TEMP_DIR / "videos").mkdir(exist_ok=True)
(TEMP_DIR / "audio").mkdir(exist_ok=True)

# =============================================================================
# API Keys & Authentication
# =============================================================================

# AI Models
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Media Generation
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
CREATOMATE_API_KEY = os.getenv("CREATOMATE_API_KEY")

# Google APIs
GOOGLE_SHEETS_SPREADSHEET_ID = os.getenv("GOOGLE_SHEETS_SPREADSHEET_ID")
GOOGLE_APPLICATION_CREDENTIALS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

# YouTube
YOUTUBE_CLIENT_ID = os.getenv("YOUTUBE_CLIENT_ID")
YOUTUBE_CLIENT_SECRET = os.getenv("YOUTUBE_CLIENT_SECRET")
YOUTUBE_REFRESH_TOKEN = os.getenv("YOUTUBE_REFRESH_TOKEN")

# =============================================================================
# Media Generation Settings
# =============================================================================

# Image Generation (Pollinations.ai)
POLLINATIONS_IMAGE_WIDTH = 540
POLLINATIONS_IMAGE_HEIGHT = 960
POLLINATIONS_MODEL = "flux"  # Model used for image generation
POLLINATIONS_SEED = 42  # Fixed seed for reproducibility
POLLINATIONS_URL = "https://image.pollinations.ai/prompt/{prompt}"
POLLINATIONS_NO_LOGO = True

# Audio Generation (ElevenLabs)
ELEVENLABS_URL = "https://api.elevenlabs.io/v1/sound-generation"
ELEVENLABS_DURATION = 5  # seconds
ELEVENLABS_PROMPT_INFLUENCE = 0.6
ELEVENLABS_VOICE_ID = "default"  # Use default voice

# FFmpeg Video Settings
FFMPEG_ZOOM_FILTER = "zoompan=z='if(lte(zoom,1.0),1.0,min(zoom+0.002,2.0))':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=125:s=540x960"
FFMPEG_VIDEO_DURATION = 5  # seconds
FFMPEG_CODEC = "libx264"
FFMPEG_PIXEL_FORMAT = "yuv420p"

# Video Composition (Creatomate)
CREATOMATE_TEMPLATE_ID = "7ce095d3-6364-40b8-8031-a20d17158584"
CREATOMATE_API_URL = "https://api.creatomate.com/v1/renders"
CREATOMATE_OUTPUT_FORMAT = "mp4"
CREATOMATE_OUTPUT_QUALITY = "high"

# =============================================================================
# File & Output Settings
# =============================================================================

# File Naming
IMAGE_FILENAME_TEMPLATE = "images_{index:03d}.png"
VIDEO_FILENAME_TEMPLATE = "video_{index:03d}.mp4"
AUDIO_FILENAME_TEMPLATE = "audio_{index:03d}.mp3"
FINAL_VIDEO_FILENAME = "final_video_{timestamp}.mp4"

# Video settings
MAX_SCENES_PER_VIDEO = 5
VIDEO_RESOLUTION = (540, 960)  # width, height

# =============================================================================
# Google Sheets Configuration
# =============================================================================

# Sheet Names
SHEET_NAME = "youtube"  # Default sheet name
IDEAS_SHEET_RANGE = "A:G"  # Range for storing ideas
VIDEOS_SHEET_RANGE = "A:I"  # Range for tracking videos

# Column Definitions
COLUMNS = {
    "ID": 0,
    "IDEA": 1,
    "HASHTAG": 2,
    "CAPTION": 3,
    "PRODUCTION": 4,
    "ENVIRONMENT_PROMPT": 5,
    "STATUS_PUBLISHING": 6,
    "VIDEO_URL": 7
}

# Status Values
STATUS_PENDING = "pending"
STATUS_FOR_PRODUCTION = "for production"
STATUS_FOR_PUBLISHING = "for publishing"
STATUS_PUBLISHED = "published"

# =============================================================================
# General Application Settings
# =============================================================================

# Retry Mechanism
MAX_RETRIES = 5
RETRY_DELAY = 3  # seconds

# Logging Configuration
LOG_LEVEL = logging.INFO
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_FILE = LOGS_DIR / "app.log"

# Timeouts
API_TIMEOUT = 60  # seconds
FFMPEG_TIMEOUT = 300  # seconds
UPLOAD_TIMEOUT = 600  # seconds

# Workflow Settings
RUN_IDEA_GENERATION = True
RUN_PROMPT_ENHANCEMENT = True
RUN_IMAGE_GENERATION = True
RUN_VIDEO_PROCESSING = True
RUN_AUDIO_GENERATION = True
RUN_VIDEO_COMPOSITION = True
RUN_YOUTUBE_UPLOAD = True
# Cấu hình FFmpeg
FFMPEG_ZOOM_FILTER = "zoompan=z='min(zoom+0.0015,1.5)':d=300"
FFMPEG_VIDEO_DURATION = 10  # Thời lượng video (giây)
FFMPEG_CODEC = "libx264"  # Codec mã hóa video
FFMPEG_PIXEL_FORMAT = "yuv420p"  # Định dạng pixel
VIDEO_FILENAME_TEMPLATE = "pov_video_{index:03d}.mp4"  # Template tên file video
MAX_SCENES_PER_VIDEO = 5  # Số cảnh tối đa trong một video
# Theme and Content
POV_THEME = "Ancient Egyptian"
POV_CATEGORIES = ["Pharaoh", "Scribe", "Priest", "Craftsman", "Soldier", "Merchant"]
# Thư mục chứa thông tin xác thực
CREDENTIALS_DIR = os.path.join(BASE_DIR, "credentials")
