import os
import yaml
import random
import requests
import time

BASE_DIR = "../vulns"
OUTPUT_FILE = "../data/vulnerable_packages.txt"

results = set()

for root, _, files in os.walk(BASE_DIR):
    for file in files:
        if not file.endswith(".yaml"):
            continue
        
        path = os.path.join(root, file)
        
        with open(path, "r") as f:
            data = yaml.safe_load(f)
        
        # Skip withdrawn vulnerabilities
        if data.get("withdrawn"):
            continue
        
        for affected in data.get("affected", []):
            pkg = affected.get("package", {}).get("name")
            
            if not pkg:
                continue
            
            # Case 1: explicit versions list
            versions = affected.get("versions", [])
            for v in versions:
                results.add((pkg, v))

results = random.sample(list(results), 5000)
counter = 0
# write to file
with open(OUTPUT_FILE, "w") as f:
    for pkg, v in sorted(results):
        counter +=1
        if counter % 500 == 0:
            time.sleep(5)
        # Check if this package is available in deps.dev api
        print(f'Checking {pkg}@{v} ...')
        dependencies_url = f'https://api.deps.dev/v3alpha/systems/pypi/packages/{pkg}/versions/{v}:dependencies'
        response = requests.get(dependencies_url)
        # Only use packages available in deps.dev and is not an independent package
        if response.status_code == 200:
            if len(response.json()['nodes']) > 1:
                f.write(f"{pkg}@{v}\n")

print(f"Saved {len(results)} vulnerable package-version pairs.")