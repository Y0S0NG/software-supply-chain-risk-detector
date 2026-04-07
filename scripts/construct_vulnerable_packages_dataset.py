import os
import yaml

BASE_DIR = "../vulns"
OUTPUT_FILE = "vulnerable_packages.txt"

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

# write to file
with open(OUTPUT_FILE, "w") as f:
    for pkg, v in sorted(results):
        f.write(f"{pkg}@{v}\n")

print(f"Saved {len(results)} vulnerable package-version pairs.")