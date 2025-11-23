from datetime import datetime
from langchain.tools import tool

@tool
def get_today_date() -> str:
  """Get today's date in YYYY-MM-DD format."""
  
  return datetime.now().strftime("%Y-%m-%d")