import requests

# url = "https://api.osv.dev/v1/query"
# payload = {
#     "version": "3.1.4",
#     "package": {
#         "name": "jinja2",
#         "ecosystem": "PyPI"
#     }
# }

# response = requests.post(url, json=payload)

# print("Status code:", response.status_code)
# print(response.json())

metadata_url = "https://pypi.org/pypi/scikit-learn/1.8.0/json"
response = requests.get(metadata_url).json()
print(response.keys())
for key in response.keys():
    print(f"Key {key}: ")
    if isinstance(response[key], dict):
        for sub_key in response[key].keys():
            print(f"Subkey {sub_key}")

