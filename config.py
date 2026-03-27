from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseSettings):
    # App
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000

    # Supabase
    supabase_url: str = ""
    supabase_key: str = ""          # anon key — safe for reads
    supabase_service_key: str = ""  # service role key — used for writes

    # Gemini
    gemini_api_key: str = ""

    # HuggingFace
    huggingface_token: str = ""

    # News API (newsapi.org)
    news_api_key: str = ""

    # SEC EDGAR base URL
    sec_edgar_url: str = "https://efts.sec.gov/LATEST/search-index?q={query}&dateRange=custom&startdt={start}&enddt={end}&forms=10-K,10-Q"

    # OpenInsider base URL
    open_insider_url: str = "http://openinsider.com/screener?s={ticker}&o=&pl=&ph=&ll=&lh=&fd=730&fdr=&td=0&tdr=&fdlyl=&fdlyh=&daysago=&xp=1&xs=1&vl=&vh=&ocl=&och=&sic1=-1&sicl=100&sich=9999&grp=0&nfl=&nfh=&nil=&nih=&nol=&noh=&v2l=&v2h=&oc2l=&oc2h=&sortcol=0&cnt=40&action=1"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
