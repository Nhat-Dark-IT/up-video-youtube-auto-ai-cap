#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Module tiện ích tương tác với Google Sheets trong hệ thống tạo video POV.
Cung cấp các phương thức để đọc, ghi, cập nhật dữ liệu trong Google Sheets
để theo dõi quá trình sản xuất video.
"""

import os
import logging
import time
from typing import List, Dict, Optional, Any, Tuple, Union

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Import các module nội bộ
from config import settings

# Thiết lập logging
logger = logging.getLogger(__name__)

class GoogleSheetsManager:
    """
    Lớp quản lý tương tác với Google Sheets API.
    """
    
    def __init__(self, spreadsheet_id: Optional[str] = None, credentials_path: Optional[str] = None):
        """
        Khởi tạo GoogleSheetsManager với thông tin xác thực và ID của spreadsheet.
        
        Args:
            spreadsheet_id: ID của Google Sheets cần thao tác (nếu None sẽ lấy từ settings)
            credentials_path: Đường dẫn đến file credentials (nếu None sẽ lấy từ settings)
        """
        self.spreadsheet_id = spreadsheet_id or settings.GOOGLE_SHEETS_SPREADSHEET_ID
        self.credentials_path = credentials_path or settings.GOOGLE_APPLICATION_CREDENTIALS
        self.api_service_name = "sheets"
        self.api_version = "v4"
        self._service = None  # Lazy initialization
        
        # Tên sheet mặc định
        self.sheet_name = settings.SHEET_NAME
        
        # Cột map theo settings
        self.columns = settings.COLUMNS
        
        logger.debug(f"Khởi tạo GoogleSheetsManager với spreadsheet ID: {self.spreadsheet_id}")
    
    @property
    def service(self):
        """
        Lấy dịch vụ Google Sheets API, khởi tạo nếu chưa có.
        
        Returns:
            Resource: Đối tượng dịch vụ Google Sheets
        """
        if self._service is None:
            try:
                # Nạp thông tin xác thực từ file service account
                credentials = service_account.Credentials.from_service_account_file(
                    self.credentials_path,
                    scopes=['https://www.googleapis.com/auth/spreadsheets']
                )
                
                # Tạo dịch vụ API
                self._service = build(
                    self.api_service_name,
                    self.api_version,
                    credentials=credentials,
                    cache_discovery=False
                )
                logger.info("Đã kết nối thành công với Google Sheets API")
            except Exception as e:
                logger.error(f"Lỗi khi khởi tạo dịch vụ Google Sheets: {str(e)}")
                raise
        
        return self._service
    
    def get_values(self, range_name: str) -> List[List[Any]]:
        """
        Lấy dữ liệu từ range trong Google Sheets.
        
        Args:
            range_name: Range cần lấy dữ liệu (vd: 'Sheet1!A1:D10')
            
        Returns:
            List[List[Any]]: Dữ liệu từ range
        """
        try:
            # Thực hiện request
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range=range_name
            ).execute()
            
            # Lấy giá trị từ kết quả
            values = result.get('values', [])
            logger.debug(f"Đã lấy {len(values)} dòng từ range {range_name}")
            return values
            
        except Exception as e:
            logger.error(f"Lỗi khi lấy dữ liệu từ range {range_name}: {str(e)}")
            return []
    def update_values(self, range_name: str, values: List[List[Any]], 
                     value_input_option: str = "RAW") -> int:
        """
        Cập nhật dữ liệu vào range trong Google Sheets.
        
        Args:
            range_name: Range cần cập nhật (vd: 'Sheet1!A1:D10')
            values: Dữ liệu cần cập nhật
            value_input_option: Cách xử lý dữ liệu đầu vào ('RAW' hoặc 'USER_ENTERED')
            
        Returns:
            int: Số ô đã cập nhật
        """
        try:
            body = {
                'values': values
            }
            
            # Thực hiện request
            result = self.service.spreadsheets().values().update(
                spreadsheetId=self.spreadsheet_id,
                range=range_name,
                valueInputOption=value_input_option,
                body=body
            ).execute()
            
            # Lấy số ô đã cập nhật
            updated_cells = result.get('updatedCells', 0)
            logger.info(f"Đã cập nhật {updated_cells} ô trong range {range_name}")
            return updated_cells
            
        except Exception as e:
            logger.error(f"Lỗi khi cập nhật dữ liệu vào range {range_name}: {str(e)}")
            return 0
    
    def append_values(self, range_name: str, values: List[List[Any]],
                     value_input_option: str = "RAW") -> int:
        """
        Thêm dữ liệu vào cuối range trong Google Sheets.
        
        Args:
            range_name: Range cần thêm dữ liệu (vd: 'Sheet1!A:D')
            values: Dữ liệu cần thêm
            value_input_option: Cách xử lý dữ liệu đầu vào ('RAW' hoặc 'USER_ENTERED')
            
        Returns:
            int: Số dòng đã thêm
        """
        try:
            body = {
                'values': values
            }
            
            # Thực hiện request
            result = self.service.spreadsheets().values().append(
                spreadsheetId=self.spreadsheet_id,
                range=range_name,
                valueInputOption=value_input_option,
                body=body,
                insertDataOption="INSERT_ROWS"
            ).execute()
            
            # Lấy thông tin về số dòng đã thêm
            updates = result.get('updates', {})
            updated_rows = updates.get('updatedRows', 0)
            logger.info(f"Đã thêm {updated_rows} dòng vào range {range_name}")
            return updated_rows
            
        except Exception as e:
            logger.error(f"Lỗi khi thêm dữ liệu vào range {range_name}: {str(e)}")
            return 0
    
    def clear_values(self, range_name: str) -> int:
        """
        Xóa dữ liệu trong range của Google Sheets.
        
        Args:
            range_name: Range cần xóa dữ liệu (vd: 'Sheet1!A1:D10')
            
        Returns:
            int: Số ô đã xóa
        """
        try:
            # Thực hiện request
            result = self.service.spreadsheets().values().clear(
                spreadsheetId=self.spreadsheet_id,
                range=range_name
            ).execute()
            
            # Lấy thông tin về số ô đã xóa
            cleared_range = result.get('clearedRange', '')
            logger.info(f"Đã xóa dữ liệu trong range {cleared_range}")
            
            # Parse range để ước tính số ô đã xóa
            try:
                # Tách phần range (ví dụ: 'Sheet1!A1:D10' -> 'A1:D10')
                cell_range = cleared_range.split('!')[1] if '!' in cleared_range else cleared_range
                
                # Tách các phần start và end (ví dụ: 'A1:D10' -> 'A1', 'D10')
                start, end = cell_range.split(':')
                
                # Tách thành cột và dòng (ví dụ: 'A1' -> 'A', '1')
                start_col, start_row = ''.join(filter(str.isalpha, start)), int(''.join(filter(str.isdigit, start)))
                end_col, end_row = ''.join(filter(str.isalpha, end)), int(''.join(filter(str.isdigit, end)))
                
                # Tính số dòng và số cột
                num_rows = end_row - start_row + 1
                
                # Chuyển đổi cột từ chữ sang số (A=1, B=2, ...)
                start_col_num = sum((ord(c) - 64) * (26 ** i) for i, c in enumerate(reversed(start_col.upper())))
                end_col_num = sum((ord(c) - 64) * (26 ** i) for i, c in enumerate(reversed(end_col.upper())))
                num_cols = end_col_num - start_col_num + 1
                
                return num_rows * num_cols
            except Exception:
                return 0
            
        except Exception as e:
            logger.error(f"Lỗi khi xóa dữ liệu trong range {range_name}: {str(e)}")
            return 0
    
    def get_sheet_properties(self) -> List[Dict[str, Any]]:
        """
        Lấy thông tin về các sheet trong spreadsheet.
        
        Returns:
            List[Dict]: Danh sách các sheet với thông tin
        """
        try:
            # Thực hiện request
            result = self.service.spreadsheets().get(
                spreadsheetId=self.spreadsheet_id,
                fields="sheets.properties"
            ).execute()
            
            # Lấy thông tin các sheet
            sheets = result.get('sheets', [])
            sheet_properties = [sheet.get('properties', {}) for sheet in sheets]
            
            logger.debug(f"Đã tìm thấy {len(sheet_properties)} sheet trong spreadsheet")
            return sheet_properties
            
        except Exception as e:
            logger.error(f"Lỗi khi lấy thông tin sheet: {str(e)}")
            return []
    
    def convert_to_dict_list(self, values: List[List[Any]]) -> List[Dict[str, Any]]:
        """
        Chuyển đổi dữ liệu dạng danh sách thành danh sách các dict với header.
        
        Args:
            values: Dữ liệu dạng danh sách từ Google Sheets (dòng đầu là header)
            
        Returns:
            List[Dict]: Danh sách các dict với key là header
        """
        if not values or len(values) < 2:
            return []
        
        headers = values[0]
        result = []
        
        for row in values[1:]:
            # Đảm bảo row có đủ phần tử
            row_extended = row + [''] * (len(headers) - len(row))
            
            # Tạo dict với key là header
            row_dict = {headers[i]: row_extended[i] for i in range(len(headers))}
            result.append(row_dict)
        
        return result
    
    def convert_from_dict_list(self, dict_list: List[Dict[str, Any]], headers: Optional[List[str]] = None) -> List[List[Any]]:
        """
        Chuyển đổi danh sách các dict thành dữ liệu dạng danh sách để ghi vào Google Sheets.
        
        Args:
            dict_list: Danh sách các dict cần chuyển đổi
            headers: Danh sách các header (nếu None sẽ lấy từ keys của dict đầu tiên)
            
        Returns:
            List[List]: Dữ liệu dạng danh sách (dòng đầu là header)
        """
        if not dict_list:
            return []
        
        # Lấy headers nếu chưa có
        if headers is None:
            headers = list(dict_list[0].keys())
        
        # Tạo danh sách kết quả với header
        result = [headers]
        
        # Thêm dữ liệu từ mỗi dict
        for item in dict_list:
            row = [item.get(header, '') for header in headers]
            result.append(row)
        
        return result
    
    def get_ideas_for_production(self) -> List[Dict[str, Any]]:
        """
        Lấy danh sách các ý tưởng đang ở trạng thái "for production".
        
        Returns:
            List[Dict]: Danh sách các ý tưởng POV cần sản xuất
        """
        try:
            # Lấy tất cả dữ liệu từ sheet
            range_name = f"{self.sheet_name}!{settings.IDEAS_SHEET_RANGE}"
            values = self.get_values(range_name)
            
            if not values:
                logger.warning(f"Không tìm thấy dữ liệu trong range {range_name}")
                return []
            
            # Chuyển đổi thành danh sách dict
            all_ideas = self.convert_to_dict_list(values)
            
            # Lọc các ý tưởng có trạng thái "for production"
            production_ideas = [
                idea for idea in all_ideas 
                if idea.get('Production') == settings.STATUS_FOR_PRODUCTION
            ]
            
            logger.info(f"Đã tìm thấy {len(production_ideas)} ý tưởng cần sản xuất")
            return production_ideas
            
        except Exception as e:
            logger.error(f"Lỗi khi lấy ý tưởng cần sản xuất: {str(e)}")
            return []
    
    def get_ideas_for_publishing(self) -> List[Dict[str, Any]]:
        """
        Lấy danh sách các ý tưởng đang ở trạng thái "for publishing".
        
        Returns:
            List[Dict]: Danh sách các ý tưởng POV cần xuất bản
        """
        try:
            # Lấy tất cả dữ liệu từ sheet
            range_name = f"{self.sheet_name}!{settings.IDEAS_SHEET_RANGE}"
            values = self.get_values(range_name)
            
            if not values:
                logger.warning(f"Không tìm thấy dữ liệu trong range {range_name}")
                return []
            
            # Chuyển đổi thành danh sách dict
            all_ideas = self.convert_to_dict_list(values)
            
            # Lọc các ý tưởng có trạng thái "for publishing"
            publishing_ideas = []
            for idea in all_ideas:
                # Kiểm tra cả hai tên cột có thể xuất hiện trong sheet
                status = idea.get('Status Publishing', '')
                if not status:
                    status = idea.get('Status_Publishing', '')
                
                if status.lower() == settings.STATUS_FOR_PUBLISHING.lower():
                    publishing_ideas.append(idea)
            
            logger.info(f"Đã tìm thấy {len(publishing_ideas)} ý tưởng cần xuất bản")
            return publishing_ideas
            
        except Exception as e:
            logger.error(f"Lỗi khi lấy ý tưởng cần xuất bản: {str(e)}")
            return []
    
    def update_video_link(self, idea_id: Union[str, int], video_url: str) -> bool:
        """
        Cập nhật link video cho một ý tưởng.
        
        Args:
            idea_id: ID của ý tưởng cần cập nhật
            video_url: URL của video đã tạo
            
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
            
            # Tìm vị trí cột VIDEO_URL
            headers = values[0]
            video_url_col_index = None
            
            for i, header in enumerate(headers):
                if header == "VIDEO_URL":
                    video_url_col_index = i
                    break
            
            # Thêm cột VIDEO_URL nếu chưa có
            if video_url_col_index is None:
                headers.append("VIDEO_URL")
                video_url_col_index = len(headers) - 1
                
                # Cập nhật header
                self.update_values(
                    f"{self.sheet_name}!A1:{chr(65 + len(headers) - 1)}1",
                    [headers]
                )
                
                # Mở rộng các dòng khác
                for i in range(1, len(values)):
                    if len(values[i]) < len(headers):
                        values[i] = values[i] + [''] * (len(headers) - len(values[i]))
            
            # Tìm dòng có ID tương ứng
            id_col_index = headers.index("ID") if "ID" in headers else 0
            row_index = None
            
            for i, row in enumerate(values[1:], 1):
                if str(row[id_col_index]) == str(idea_id):
                    row_index = i
                    break
            
            if row_index is None:
                logger.warning(f"Không tìm thấy ý tưởng với ID {idea_id}")
                return False
            
            # Cập nhật URL video
            row_values = values[row_index]
            if len(row_values) <= video_url_col_index:
                row_values = row_values + [''] * (video_url_col_index - len(row_values) + 1)
            
            row_values[video_url_col_index] = video_url
            
            # Cập nhật dòng vào sheet
            update_range = f"{self.sheet_name}!A{row_index + 1}:{chr(65 + len(row_values) - 1)}{row_index + 1}"
            self.update_values(update_range, [row_values])
            
            # Cập nhật trạng thái xuất bản
            status_col_index = headers.index("Status_Publishing") if "Status_Publishing" in headers else None
            
            if status_col_index is not None:
                row_values[status_col_index] = settings.STATUS_FOR_PUBLISHING
                
                # Cập nhật lại dòng
                self.update_values(update_range, [row_values])
                
            logger.info(f"Đã cập nhật URL video cho ý tưởng ID {idea_id}: {video_url}")
            return True
            
        except Exception as e:
            logger.error(f"Lỗi khi cập nhật URL video cho ý tưởng ID {idea_id}: {str(e)}")
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
            id_col_index = headers.index("ID") if "ID" in headers else 0
            row_index = None
            
            for i, row in enumerate(values[1:], 1):
                if len(row) > id_col_index and str(row[id_col_index]) == str(idea_id):
                    row_index = i
                    break
            
            if row_index is None:
                logger.warning(f"Không tìm thấy ý tưởng với ID {idea_id}")
                return False
            
            # Cập nhật trạng thái
            row_values = values[row_index]
            if len(row_values) <= status_col_index:
                row_values = row_values + [''] * (status_col_index - len(row_values) + 1)
            
            row_values[status_col_index] = status
            
            # Cập nhật dòng vào sheet
            update_range = f"{self.sheet_name}!A{row_index + 1}:{chr(65 + len(row_values) - 1)}{row_index + 1}"
            self.update_values(update_range, [row_values])
            
            logger.info(f"Đã cập nhật trạng thái xuất bản cho ý tưởng ID {idea_id}: {status}")
            return True
            
        except Exception as e:
            logger.error(f"Lỗi khi cập nhật trạng thái xuất bản cho ý tưởng ID {idea_id}: {str(e)}")
            return False
    
    def append_new_ideas(self, ideas: List[Dict[str, Any]]) -> bool:
        """
        Thêm danh sách ý tưởng mới vào cuối sheet, tự động thêm ID tăng dần.
        
        Args:
            ideas: Danh sách các ý tưởng cần thêm
            
        Returns:
            bool: True nếu thêm thành công, False nếu thất bại
        """
        try:
            if not ideas:
                logger.warning("Không có ý tưởng nào để thêm vào")
                return False
            
            # Lấy header từ sheet hiện tại hoặc định nghĩa
            range_name = f"{self.sheet_name}!{settings.IDEAS_SHEET_RANGE}"
            current_values = self.get_values(range_name)
            
            if current_values and len(current_values) > 0:
                headers = current_values[0]
            else:
                # Sử dụng header mặc định nếu sheet trống
                headers = ["ID", "Idea", "Hashtag", "Caption", "Production", "Environment_Prompt", "Status_Publishing"]
            
            # Log headers để debug
            logger.debug(f"Headers trong sheet: {headers}")
            
            # Xác định vị trí cột ID trong headers
            id_column_index = -1
            for i, header in enumerate(headers):
                if header.upper() == "ID":
                    id_column_index = i
                    logger.info(f"Đã tìm thấy cột ID ở vị trí {i}")
                    break
            
            # Nếu không tìm thấy cột ID, thêm cột ID vào đầu
            if id_column_index == -1:
                headers.insert(0, "ID")
                id_column_index = 0
                logger.info("Đã thêm cột ID vào vị trí đầu tiên")
                
                # Cập nhật header trong sheet
                self.update_values(
                    f"{self.sheet_name}!A1:{chr(65 + len(headers) - 1)}1",
                    [headers]
                )
            
            # Lấy ID lớn nhất hiện có - cải thiện cách tìm ID
            next_id = self.get_next_available_id()
            logger.info(f"Bắt đầu thêm ý tưởng mới với ID: {next_id}")
            
            # Chuẩn bị dữ liệu để thêm vào
            rows = []
            starting_id = next_id
            for idea_index, idea in enumerate(ideas):
                # Tạo một hàng với đúng thứ tự các cột từ headers
                row = []
                current_id = starting_id + idea_index
                
                for col_index, header in enumerate(headers):
                    # Xử lý đặc biệt cho cột ID
                    if col_index == id_column_index:
                        row.append(str(current_id))  # Thêm ID theo thứ tự
                        continue
                        
                    # Map giữa header trong sheet và key trong dictionary
                    if header == "Idea":
                        row.append(idea.get("Idea", ""))
                    elif header == "Hashtag":
                        row.append(idea.get("Hashtag", ""))
                    elif header == "Caption":
                        row.append(idea.get("Caption", ""))
                    elif header == "Production":
                        row.append(idea.get("Production", "for production"))
                    elif header == "Environment_Prompt":
                        row.append(idea.get("Environment_Prompt", ""))
                    elif header == "Status Publishing" or header == "Status_Publishing":
                        row.append(idea.get("Status Publishing", "pending"))
                    else:
                        # Trường hợp header khác, tìm key không phân biệt hoa thường
                        found = False
                        for key, value in idea.items():
                            if key.lower() == header.lower():
                                row.append(value)
                                found = True
                                break
                        if not found:
                            row.append("")
                
                logger.debug(f"Dòng dữ liệu mới: ID={current_id}, dữ liệu={row}")
                rows.append(row)
            
            # Thêm vào sheet
            result = self.append_values(range_name, rows)
            end_id = starting_id + len(ideas) - 1
            
            if result > 0:
                logger.info(f"Đã thêm {len(ideas)} ý tưởng mới vào sheet với ID từ {starting_id} đến {end_id}")
                return True
            else:
                logger.error(f"Không thể thêm ý tưởng mới vào sheet")
                return False
                
        except Exception as e:
            logger.error(f"Lỗi khi thêm ý tưởng mới: {str(e)}")
            return False
    
    def find_idea_by_id(self, idea_id: Union[str, int]) -> Optional[Dict[str, Any]]:
        """
        Tìm một ý tưởng theo ID.
        
        Args:
            idea_id: ID của ý tưởng cần tìm
            
        Returns:
            Dict: Thông tin của ý tưởng hoặc None nếu không tìm thấy
        """
        try:
            # Lấy tất cả dữ liệu từ sheet
            range_name = f"{self.sheet_name}!{settings.IDEAS_SHEET_RANGE}"
            values = self.get_values(range_name)
            
            if not values or len(values) < 2:
                logger.warning(f"Không tìm thấy dữ liệu trong range {range_name}")
                return None
            
            # Chuyển đổi thành danh sách dict
            all_ideas = self.convert_to_dict_list(values)
            
            # Tìm ý tưởng có ID tương ứng
            for idea in all_ideas:
                if str(idea.get('ID', '')) == str(idea_id):
                    return idea
            
            logger.warning(f"Không tìm thấy ý tưởng với ID {idea_id}")
            return None
            
        except Exception as e:
            logger.error(f"Lỗi khi tìm ý tưởng với ID {idea_id}: {str(e)}")
            return None
    
    def get_next_available_id(self) -> int:
        """
        Lấy ID tiếp theo có thể sử dụng bằng cách tìm ID lớn nhất trong sheet.
        
        Returns:
            int: ID tiếp theo (lớn nhất + 1)
        """
        try:
            # Lấy tất cả dữ liệu từ sheet
            range_name = f"{self.sheet_name}!{settings.IDEAS_SHEET_RANGE}"
            values = self.get_values(range_name)
            
            if not values or len(values) < 2:
                logger.info("Sheet trống hoặc chỉ có header, bắt đầu với ID = 1")
                return 1
            
            # Tìm vị trí cột ID
            headers = values[0]
            id_column_index = -1
            for i, header in enumerate(headers):
                if header.upper() == "ID":
                    id_column_index = i
                    break
            
            if id_column_index == -1:
                logger.warning("Không tìm thấy cột ID, bắt đầu với ID = 1")
                return 1
            
            # Tìm ID lớn nhất
            max_id = 0
            for row in values[1:]:  # Bỏ qua dòng header
                if len(row) > id_column_index:
                    try:
                        # Loại bỏ khoảng trắng và chuyển đổi sang số
                        id_str = row[id_column_index].strip()
                        if id_str and id_str.isdigit():
                            id_value = int(id_str)
                            max_id = max(max_id, id_value)
                    except (ValueError, TypeError, IndexError) as e:
                        logger.debug(f"Bỏ qua giá trị ID không hợp lệ: {str(e)}")
            
            next_id = max_id + 1
            logger.info(f"ID lớn nhất hiện có: {max_id}, ID tiếp theo: {next_id}")
            return next_id
            
        except Exception as e:
            logger.error(f"Lỗi khi lấy ID tiếp theo: {str(e)}")
            return 1