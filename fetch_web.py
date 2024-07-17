import re
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import time
import json
from concurrent.futures import ThreadPoolExecutor, as_completed

# Clean the extracted text
def clean_text(text):
    text = re.sub(r'\s+', ' ', text).strip()
    text = text.replace(' / ', '/').replace(' /', '/').replace('/ ', '/')
    return text

# Create a headless browser
def create_headless_browser():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    return webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=chrome_options)

# Extract block information from a URL
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

        parameters = []
        if parameters_section:
            # Extract parameters from the nested panel groups within the Parameters section
            outer_panel_group = parameters_section.find('div', class_='panel-group')
            if outer_panel_group:
                parameters = extract_parameters(outer_panel_group)

    finally:
        driver.quit()
    
    
    return block_url, libraries, description_text, parameters

# Extract parameters from panel groups
def extract_parameters(panel_group):
    # Find all panel groups at any level
    all_panel_groups = panel_group.find_all('div', class_='panel-group', recursive=True)
    
    # Filter out panel groups that have child panel groups
    lowest_level_panel_groups = [pg for pg in all_panel_groups if not pg.find('div', class_='panel-group', recursive=True)]
    
    parameters = []

    # Process each lowest level panel group
    for pg in lowest_level_panel_groups:
        # Look for the h4 tag with text "Programmatic Use"
        programmatic_use_header = pg.find('h4', text='Programmatic Use')
        if programmatic_use_header:
            # Find the first table after this header
            next_sibling = programmatic_use_header.find_next_sibling()
            while next_sibling:
                if next_sibling.name == 'table':
                    rows = next_sibling.find_all('tr')
                    parameters.extend(clean_parameters(rows))
                    break
                next_sibling = next_sibling.find_next_sibling()

    return parameters

def clean_parameters(rows):
    cleaned_parameters = []
    current_parameter = {}

    for row in rows:
        strong = row.find('strong')
        if strong:
            key = clean_text(strong.get_text().replace(':', '').strip())  # Clean the key and remove colon
            value = row.get_text().replace(strong.get_text(), "").strip()  # Get the value text without the key

            # Clean up the value string
            value = re.sub(r'\s+', ' ', value)
            value = value.replace('\n', '').replace('\t', '').replace('\"', "'")

            if key.lower().startswith("block parameter") or key.lower().startswith("parameter"):
                key = "Parameter"  # Standardize the key to "Parameter"
                if current_parameter:
                    cleaned_parameters.append(current_parameter)
                current_parameter = {key: value}
            else:
                current_parameter[key] = value
    
    if current_parameter:
        cleaned_parameters.append(current_parameter)

    return cleaned_parameters


# Process block information
def process_block(block_info):
    block_name, block_url = block_info
    _, libraries, description, parameters = extract_block_info(block_url)
    
    document = {
        "block_name": block_name,
        "libraries": libraries,
        "description": description,
        "parameters": parameters,
        "source": block_url
    }
    
    print(f"Completed processing block: {block_name}")  # Debug statement to print the block name
    return document

# Fetch documentation
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
                                

    # Use ThreadPoolExecutor for concurrent processing
    with ThreadPoolExecutor(max_workers=5) as executor:
        future_to_block = {executor.submit(process_block, block_info): block_info for block_info in block_urls}
        for future in as_completed(future_to_block):
            block_info = future_to_block[future]
            try:
                document = future.result()
                documents.append(document)
            except Exception as exc:
                print(f"{block_info} generated an exception: {exc}")

    # Save the collected documents to a JSON file
    output_file = 'data/simulink_data_test2.json'
    with open(output_file, 'w') as f:
        json.dump(documents, f, indent=4)

    print(f"Completed processing {len(documents)} blocks. Results saved to {output_file}")

    driver.quit()

# Run the fetch documentation function
fetch_documentation()
