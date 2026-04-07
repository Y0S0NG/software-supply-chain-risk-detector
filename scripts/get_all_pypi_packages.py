import requests

url = "https://pypi.org/simple/"
headers = {
    "Accept": "application/vnd.pypi.simple.v1+json"
}

resp = requests.get(url, headers=headers)
data = resp.json()

packages = [p["name"] for p in data["projects"]]
print(f"PyPI simple API returns totally {len(packages)} packages")

with open('pypi_packages.txt', 'w') as f:
    for package in packages:
        f.write(f"{package}\n")