import requests
from bs4 import BeautifulSoup
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, JSONResponse
from typing import List, Any
from pydantic import BaseModel
from datetime import datetime
import pandas as pd

# Define base_url
base_url = "https://www.transfermarkt.pt"

# Mapping of Portuguese day abbreviations to English equivalents
day_mapping = {
    'dom': 'Sun',
    'seg': 'Mon',
    'ter': 'Tue',
    'qua': 'Wed',
    'qui': 'Thu',
    'sex': 'Fri',
    'sáb': 'Sat',
}

# Mapping of English month names to Portuguese equivalents
month_mapping = {
    'Jan': 'Jan',
    'Feb': 'Fev',
    'Mar': 'Mar',
    'Apr': 'Abr',
    'May': 'Mai',
    'Jun': 'Jun',
    'Jul': 'Jul',
    'Aug': 'Ago',
    'Sep': 'Set',
    'Oct': 'Out',
    'Nov': 'Nov',
    'Dec': 'Dez',
}

class FixtureDataItem(BaseModel):
    Jornada: str
    Data: str
    Hora: str
    Equipa_da_casa: str
    Resultado: str
    Equipa_visitante: str

class CompetitionDataItem(BaseModel):
    Posição: str
    Linha_Em_Branco: str
    Nome: str
    Jogos: str
    Empates: str
    Pontos: str

class FixtureDataResponse(BaseModel):
    fixture_data: List[FixtureDataItem]
    
class CompetitionDataResponse(BaseModel):
    success: bool
    fixture_data: List[FixtureDataItem] = []
    competition_data: List[CompetitionDataItem] = []
    error_message: str = None

app = FastAPI(title="Calendario das Equipas", swagger_ui_parameters={"defaultModelsExpandDepth": -1})

# Redirect root to Swagger UI
@app.get("/", include_in_schema=False)
def docs_redirect():
    return RedirectResponse(url="/docs")

@app.get("/transfermarkt", response_model=CompetitionDataResponse, summary="ID", tags=["Procurar"])
def scrape_website(id: int = Query(1237, description="ID da equipa transfermarkt")):
    url = f"https://www.transfermarkt.pt/-/spielplan/verein/{id}/saison_id/2023/plus/1#"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"
    }

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'html.parser')
        competition_link_element = soup.select_one('a[href*="/startseite/wettbewerb/"]')
        
        if competition_link_element:
            href_value = competition_link_element['href']
            print(f"Competition Link: {href_value}")

            # Change the URL to '/tabelle/wettbewerb/'
            full_competition_link = f"{base_url}{href_value.replace('/startseite/wettbewerb/', '/tabelle/wettbewerb/')}"
            print(f"Full Competition Link: {full_competition_link}")
            
            # Extract fixture data
            scraped_fixture_data = []

            # Finding all divs with the class 'box'
            boxes = soup.find_all('div', class_='box')

            # Iterating over the divs found
            for i, box in enumerate(boxes, start=1):
                # If it's the 6th box, get the content
                if i == 6:
                    # Finding the table of games within the box
                    table = box.find('table')
                    if table:
                        # Iterating over the rows of the table
                        for row in table.select('tbody tr'):
                            # Extracting relevant data only if the matchday is present
                            jornada = row.select_one('td:nth-of-type(1) a')
                            if jornada:
                                # Parsing and formatting the date
                                data_original = row.select_one('td:nth-of-type(2)').get_text(strip=True)
                                day_abbr = data_original.split(' ')[0].lower()
                                day_abbr_english = day_mapping.get(day_abbr, day_abbr)
                                data_modified = data_original.replace(day_abbr, day_abbr_english)
                                data_obj = datetime.strptime(data_modified, "%a %d/%m/%Y")
                                data_formatada = data_obj.strftime("%d %b. %y").replace(data_obj.strftime("%b"), month_mapping[data_obj.strftime("%b")])

                                hora = row.select_one('td:nth-of-type(3)').get_text(strip=True)
                                equipe_casa = row.select_one('td:nth-of-type(5) a').get_text(strip=True)
                                equipe_visitante = row.select_one('td:nth-of-type(7) a').get_text(strip=True)

                                # Modify the way of getting the result
                                resultado_span = row.select_one('td:nth-of-type(11) span')
                                resultado = resultado_span.get_text(strip=True) if resultado_span else '-'

                                # Append data to the list
                                scraped_fixture_data.append({
                                    "Jornada": jornada.get_text(strip=True),
                                    "Data": data_formatada,
                                    "Hora": hora,
                                    "Equipa_da_casa": equipe_casa,
                                    "Resultado": resultado,
                                    "Equipa_visitante": equipe_visitante
                                })

                        break

            if not full_competition_link:
                raise ValueError("Competition link not found")

            # Define headers within the function
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"
            }

            # Continue with the rest of your code
            response = requests.get(full_competition_link, headers=headers)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')
            div_yw1 = soup.find('div', {'id': 'yw1', 'class': 'grid-view'})
            rows = div_yw1.find_all('tr')

            data = []
            for row in rows:
                cols = row.find_all(['td', 'th'])
                cols = [col.get_text(strip=True) for col in cols]
                data.append(cols)

            df = pd.DataFrame(data)
            df = df.drop([4, 6, 7, 8], axis=1)
            df = df[1:]

            # Convert DataFrame to dictionary
            data_dict = df.to_dict(orient='split')['data']

            # Construct CompetitionDataItem instances
            competition_data_items = []
            for item in data_dict:
                competition_data_items.append(CompetitionDataItem(
                    Posição=item[0],
                    Linha_Em_Branco=item[1],
                    Nome=item[2],
                    Jogos=item[3],
                    Empates=item[4],
                    Pontos=item[5]
                ))

            response_model = CompetitionDataResponse(success=True, fixture_data=scraped_fixture_data, competition_data=competition_data_items)
            return JSONResponse(content=response_model.dict())

    except Exception as e:
        response_model = CompetitionDataResponse(success=False, error_message=str(e))
        return JSONResponse(content=response_model.dict())
