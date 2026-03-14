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

@app.post("/run")
def run(data: RequestData):

    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)

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