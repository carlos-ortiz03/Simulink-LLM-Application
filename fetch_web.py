import re
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import time
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

# Next step: clean the html tags from the parameters

# do however, allow lists to be interpreted as lists through some kind of delimiter or formatting

# in parameters, have parameter descriptions as well

# Look into why they are all 1 parameter

def clean_text(text):
    text = re.sub(r'\s+', ' ', text).strip()
    text = text.replace(' / ', '/').replace(' /', '/').replace('/ ', '/')
    return text

def create_headless_browser():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    return webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=chrome_options)

def extract_block_info(block_url):
    driver = create_headless_browser()
    try:
        driver.get(block_url)
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
        
        # Extract description
        description_div = block_soup.find('div', class_='refsect1 description')
        description_text = ""
        if description_div:
            description_text = clean_text(description_div.get_text())

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

    finally:
        driver.quit()
    
    return block_url, libraries, description_text, parameters_html_array

def extract_parameters(panel_group):
    parameters = []
    # Look for the h4 tag with text "Programmatic Use"
    programmatic_use_header = panel_group.find('h4', text='Programmatic Use')
    if programmatic_use_header:
        # Find the first table after this header
        next_sibling = programmatic_use_header.find_next_sibling()
        while next_sibling:
            if next_sibling.name == 'table':
                rows_html = [str(row) for row in next_sibling.find_all('tr')]
                parameters.append(rows_html)
                break
            next_sibling = next_sibling.find_next_sibling()
    return parameters

def process_block(block_info):
    block_name, block_url = block_info
    _, libraries, description, parameters_html_array = extract_block_info(block_url)
    
    document = {
        "block_name": block_name,
        "libraries": libraries,
        "description": description,
        "parameters": parameters_html_array,
        "source": block_url
    }
    
    print(f"Completed processing block: {block_name}")  # Debug statement to print the block name
    return document

def fetch_documentation():
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

    # Find the navigation bar
    nav_siblings = soup.find('ul', id='nav_siblings')
    if not nav_siblings:
        print("Navigation bar with id 'nav_siblings' not found.")
        driver.quit()
        return

    nav_items = nav_siblings.find_all('li', recursive=False)
    if len(nav_items) != 4:
        print(f"Expected 4 navigation items, but found {len(nav_items)}")
        driver.quit()
        return
    else:
        print(f"Found {len(nav_items)} navigation items")

    documents = []
    block_urls = []
    for current_index, nav_item in enumerate(nav_items):
        nav_link = nav_item.find('a', recursive=False)
        if not nav_link:
            print(f"No link found in navigation item {current_index + 1}")
            continue

        section_url = urljoin(main_url, nav_link['href'])
        section_name = nav_link.text.strip().lower().replace(' ', '_')

        if current_index == 0:
            print(f"Processing initial section: {section_name}, URL: {section_url}")
        else:
            print(f"Processing section: {section_name}, URL: {section_url}")
            driver.get(section_url)
            time.sleep(5)  # Adjust this sleep time as necessary

        section_page_source = driver.page_source
        section_soup = BeautifulSoup(section_page_source, 'html.parser')
        
        # Find the specific div element containing the blocks
        reflist_content = section_soup.find('div', id='reflist_content')
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
                                block_url = urljoin(section_url, link['href'])  # Ensure the block URL is absolute
                                block_name = link.text.strip()
                                block_info = (block_name, block_url)
                                
                                block_urls.append(block_info)
        else:
            print(f"Element with id 'reflist_content' not found in section {nav_link.text.strip()}.")

    driver.quit()

    # Use ThreadPoolExecutor for multithreading
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(process_block, block_info): block_info for block_info in block_urls}
        for future in as_completed(futures):
            try:
                document = future.result()
                documents.append(document)
            except Exception as e:
                block_info = futures[future]
                print(f"Error processing block {block_info[0]}: {e}")

    # Ensure the 'data' directory exists
    os.makedirs('data', exist_ok=True)

    # Save documents to a JSON file in the 'data' directory
    json_file_path = os.path.join('data', 'simulink_data_test.json')
    with open(json_file_path, 'w') as f:
        json.dump(documents, f, indent=4)

if __name__ == "__main__":
    fetch_documentation()
