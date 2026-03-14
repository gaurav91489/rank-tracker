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


import undetected_chromedriver as uc
import platform

@app.post("/run")
def run(data: RequestData):

    options = uc.ChromeOptions()
    
    # Only run in headless mode if not on Windows (i.e., inside Docker / Railway)
    is_linux = platform.system() == "Linux"
    if is_linux:
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--window-size=1920,1080")

    driver = uc.Chrome(options=options, headless=is_linux)

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