from fastapi import FastAPI
from pydantic import BaseModel
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from fastapi.middleware.cors import CORSMiddleware
from rank_tracker import run_tracker

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # allow frontend
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class RequestData(BaseModel):
    domain: str
    phrases: list[str]
    engines: list[str]
    max_pages: int


from selenium.webdriver.chrome.options import Options
import platform

@app.post("/run")
def run(data: RequestData):

    chrome_options = Options()
    
    # Only run in headless mode if not on Windows (i.e., inside Docker / Railway)
    if platform.system() == "Linux":
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)

    # Use stealth exactly as Chrome would be on desktop to avoid bot detection
    try:
        from selenium_stealth import stealth
        stealth(
            driver,
            languages=["en-US", "en"],
            vendor="Google Inc.",
            platform="Win32",
            webgl_vendor="Intel Inc.",
            renderer="Intel Iris OpenGL Engine",
            fix_hairline=True,
        )
    except ImportError:
        pass

    try:
        results = run_tracker(
            driver=driver,
            engines=data.engines,
            phrases=data.phrases,
            target_domain=data.domain
        )
    finally:
        driver.quit()

    return results