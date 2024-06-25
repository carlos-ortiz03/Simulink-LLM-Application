# fetch_web.py

from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urljoin
import time
import re
import json
import os

# Function to clean and format the text
def clean_text(text):
    text = re.sub(r'\s+', ' ', text).strip()
    text = text.replace(' / ', '/').replace(' /', '/').replace('/ ', '/')
    return text

# Function to extract HTML content from a BeautifulSoup element
def element_to_html(element):
    return str(element.prettify())

# Recursive function to extract parameters from nested panel groups
def extract_parameters(panel_group):
    parameters = []
    child_panel_groups = panel_group.find_all('div', class_='panel-group', recursive=False)
    if child_panel_groups:
        for child in child_panel_groups:
            parameters.extend(extract_parameters(child))
    else:
        table = panel_group.find('table')
        if table:
            rows_html = [element_to_html(row) for row in table.find_all('tr')]
            parameters.append(rows_html)
    return parameters

# Function to create a headless browser instance
def create_headless_browser():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    return webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=chrome_options)

# Function to extract information from a block page
def extract_block_info(block_url):
    driver = create_headless_browser()
    main_url = 'https://www.mathworks.com/help/simulink/referencelist.html?type=block&s_tid=CRUX_topnav'
    full_url = urljoin(main_url, block_url)
    driver.get(full_url)
    time.sleep(3)  # Adjust this sleep time as necessary

    block_page_source = driver.page_source
    block_soup = BeautifulSoup(block_page_source, 'html.parser')
    
    # Extract library path
    library_paths = block_soup.find_all('div', class_='library_path_container')
    libraries = []
    for path in library_paths:
        spans = path.find_all('span')
        span_texts = [clean_text(span.text) for span in spans]
        libraries.extend(span_texts)
    
    # Find the ref_sect containing the Parameters section
    ref_sects = block_soup.find_all('div', class_='ref_sect')
    parameters_section = None
    for ref_sect in ref_sects:
        h2 = ref_sect.find('h2')
        if h2 and "Parameters" in h2.text:
            parameters_section = ref_sect
            break

    parameters_html_array = []
    if parameters_section:
        # Extract parameters from the nested panel groups within the Parameters section
        outer_panel_group = parameters_section.find('div', class_='panel-group')
        if outer_panel_group:
            parameters_html_array = extract_parameters(outer_panel_group)

    driver.quit()
    return libraries, parameters_html_array

def process_block(block_info):
    block_name, block_url = block_info
    libraries, parameters_html_array = extract_block_info(block_url)
    document = {
        "block_name": block_name,
        "libraries": libraries,
        "parameters": parameters_html_array,
        "source": block_url
    }
    print(f"Finished processing block: {block_name}")
    return document

def fetch_simulink_data():
    # Create a headless browser instance for initial page load
    driver = create_headless_browser()

    # URL of the main webpage that contains links to all the blocks
    main_url = 'https://www.mathworks.com/help/simulink/referencelist.html?type=block&s_tid=CRUX_topnav'

    # Load the webpage using Selenium
    driver.get(main_url)

    # Wait for the page to load completely
    time.sleep(5)  # Adjust this sleep time as necessary

    # Get the page source after JavaScript has rendered the content
    page_source = driver.page_source

    # Use BeautifulSoup to parse the page source
    soup = BeautifulSoup(page_source, 'html.parser')

    # Find the specific div element
    reflist_content = soup.find('div', id='reflist_content')

    block_info_list = []

    if reflist_content:
        table_responsive_divs = reflist_content.find_all('div', class_='table-responsive')
        
        for table_responsive in table_responsive_divs:
            table = table_responsive.find('table', class_='table tablecondensed has_limited_support')
            if table:
                rows = table.find_all('tr')
                for row in rows:
                    term_td = row.find('td', class_='term')
                    description_td = row.find('td', class_='description')
                    
                    if term_td and description_td:
                        links = term_td.find_all('a')
                        if len(links) > 1:  # Ensure there are at least two links
                            link = links[1]  # The second link
                            block_url = link['href']
                            block_name = link.text.strip()
                            block_info_list.append((block_name, block_url))
    else:
        print("Element with id 'reflist_content' not found.")

    # Close the browser
    driver.quit()

    documents = []
    with ThreadPoolExecutor(max_workers=5) as executor:  # Adjust max_workers as needed
        results = executor.map(process_block, block_info_list)
        documents.extend(results)

    # Ensure the 'data' directory exists
    os.makedirs('data', exist_ok=True)

    # Save documents to a JSON file in the 'data' directory
    json_file_path = os.path.join('data', 'simulink_data.json')
    with open(json_file_path, 'w') as f:
        json.dump(documents, f, indent=4)

if __name__ == "__main__":
    fetch_simulink_data()
