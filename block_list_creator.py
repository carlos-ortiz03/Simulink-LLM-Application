import json
import pickle

# Path to the JSON file
json_file_path = './data/simulink_data_test2.json'
# Path to the pickle file
pickle_file_path = './data/block_types.pkl'

# Load JSON data from the file
with open(json_file_path, 'r') as file:
    data = json.load(file)

# Extract block names and store them in a list
block_types = [item['block_name'] for item in data]

# Print the list of block names (optional, for verification)
print(block_types)

# Save the list to a file using pickle
with open(pickle_file_path, 'wb') as file:
    pickle.dump(block_types, file)

print(f"Block types have been written to {pickle_file_path}")
