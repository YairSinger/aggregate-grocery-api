from typing import List, Dict, Type
from app.pipeline.base_scraper import ScraperBase
from app.pipeline.cerberus_browser_scraper import CerberusBrowserScraper
from app.pipeline.shufersal_scraper import ShufersalScraper

class ScraperFactory:
    _scrapers: Dict[str, Type[ScraperBase]] = {
        "Shufersal": ShufersalScraper,
        "RamiLevy": CerberusBrowserScraper,
        "Victory": CerberusBrowserScraper,
        "Yohananof": CerberusBrowserScraper,
    }

    _configs = {
        "Shufersal": {},
        "RamiLevy": {"username": "RamiLevi"},
        "Victory": {"username": "Victory"},
        "Yohananof": {"username": "yohananof"},
    }

    @classmethod
    def get_scraper(cls, chain_name: str, download_dir: str = "downloads") -> ScraperBase:
        if chain_name not in cls._scrapers:
            raise ValueError(f"Unknown chain: {chain_name}")
            
        scraper_class = cls._scrapers[chain_name]
        config = cls._configs[chain_name]
        
        if scraper_class == CerberusBrowserScraper:
            return CerberusBrowserScraper(chain_name, config["username"], download_dir)
        else:
            return ShufersalScraper(download_dir)
