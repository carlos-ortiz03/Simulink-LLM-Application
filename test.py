import json

# Load the JSON file
json_file_path = './data/simulink_data.json'

with open(json_file_path, 'r') as file:
    data = json.load(file)

# Get the length of the array
num_documents = len(data)

print(f"Number of JSON objects in the file: {num_documents}")