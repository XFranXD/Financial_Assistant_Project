import os
import gspread
from google.oauth2.service_account import Credentials
from utils.logger import get_logger
from contracts.paper_trading_schema import SHEET_COLUMNS, SHEET_NAME

log = get_logger(__name__)

_client = None
_spreadsheet = None
_sheet = None

def _get_sheet() -> gspread.Worksheet | None:
    global _client, _spreadsheet, _sheet
    
    if _sheet is not None:
        return _sheet

    creds_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    sheet_id = os.environ.get("GOOGLE_SHEETS_ID")

    if not creds_json or not sheet_id:
        log.error("Missing Google Sheets credentials in environment variables.")
        return None

    try:
        import json
        creds_dict = json.loads(creds_json)
        scopes = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive"
        ]
        credentials = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        _client = gspread.authorize(credentials)
        _spreadsheet = _client.open_by_key(sheet_id)
        _sheet = _spreadsheet.worksheet(SHEET_NAME)
        return _sheet
    except Exception as e:
        log.error(f"Failed to authenticate or open sheet: {e}")
        _client = None
        _spreadsheet = None
        _sheet = None
        return None

def ensure_headers() -> bool:
    sheet = _get_sheet()
    if sheet is None:
        return False
        
    try:
        rows = sheet.get_all_values()
        if not rows:
            sheet.append_row(SHEET_COLUMNS, value_input_option="RAW")
            return True
            
        header_row = rows[0]
        if header_row != SHEET_COLUMNS:
            log.error(f"Header mismatch detected. Expected: {SHEET_COLUMNS}, Found: {header_row}")
            return False
            
        return True
    except Exception as e:
        log.error(f"Failed to ensure headers: {e}")
        return False

def read_all_trades() -> list[dict]:
    """
    Reads all rows from the sheet (excluding header row 1).
    All values returned are raw strings. Normalization is caller's responsibility.
    """
    sheet = _get_sheet()
    if sheet is None:
        return []
        
    try:
        rows = sheet.get_all_values()
        if not rows or len(rows) <= 1:
            return []
            
        trades = []
        for index, row_values in enumerate(rows[1:], start=2):
            padded_values = row_values + [""] * (len(SHEET_COLUMNS) - len(row_values))
            trade = dict(zip(SHEET_COLUMNS, padded_values))
            trade["row_index"] = index
            trades.append(trade)
            
        return trades
    except Exception as e:
        log.error(f"Failed to read all trades: {e}")
        return []

def write_rows(rows: list[dict]) -> bool:
    sheet = _get_sheet()
    if sheet is None or not rows:
        return False
        
    try:
        list_of_lists = []
        for row_dict in rows:
            row_list = []
            for col in SHEET_COLUMNS:
                val = row_dict.get(col, "")
                if val is None:
                    row_list.append("")
                elif isinstance(val, bool):
                    row_list.append(str(val))
                else:
                    row_list.append(str(val))
            list_of_lists.append(row_list)
            
        sheet.append_rows(list_of_lists, value_input_option="RAW")
        return True
    except Exception as e:
        log.error(f"Failed to write rows: {e}")
        return False

def update_rows(rows: list[dict]) -> bool:
    sheet = _get_sheet()
    if sheet is None or not rows:
        return False
        
    try:
        cells_to_update = []
        for row_dict in rows:
            row_idx = row_dict.get("row_index")
            if not row_idx:
                continue
                
            for col_idx, col_name in enumerate(SHEET_COLUMNS, start=1):
                val = row_dict.get(col_name, "")
                if val is None:
                    str_val = ""
                elif isinstance(val, bool):
                    str_val = str(val)
                else:
                    str_val = str(val)
                    
                cells_to_update.append(gspread.models.Cell(row=row_idx, col=col_idx, value=str_val))
                
        if cells_to_update:
            sheet.update_cells(cells_to_update, value_input_option="RAW")
            
        return True
    except Exception as e:
        log.error(f"Failed to update rows: {e}")
        return False
