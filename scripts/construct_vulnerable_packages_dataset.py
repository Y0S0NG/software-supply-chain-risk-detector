import os
import yaml
import random
import requests
import time

# BASE_DIR = "../vulns"
OUTPUT_FILE = "../data/vulnerable_packages.txt"

# vulnerable_packages = set()

# for root, _, files in os.walk(BASE_DIR):
#     for file in files:
#         if not file.endswith(".yaml"):
#             continue
        
#         path = os.path.join(root, file)
        
#         with open(path, "r") as f:
#             data = yaml.safe_load(f)
        
#         # Skip withdrawn vulnerabilities
#         if data.get("withdrawn"):
#             continue
        
#         for affected in data.get("affected", []):
#             pkg = affected.get("package", {}).get("name")
            
#             if not pkg:
#                 continue

#             ecosystem = affected.get("package", {}).get("ecosystem", "")
#             if ecosystem != "PyPI":
#                 continue

#             # Case 1: explicit versions list
#             versions = affected.get("versions", [])
#             for v in versions:
#                 vulnerable_packages.add((pkg, v))
            
# vulnerable_packages = list(vulnerable_packages)

KNOWN_RISKY_FILE = "../data/known_risky_packages.txt"

# Write all discovered vulnerable packages to known_risky_packages.txt
# with open(KNOWN_RISKY_FILE, "w") as f:
#     for pkg, v in vulnerable_packages:
#         f.write(f"{pkg}@{v}\n")

# Read known_risky_packages.txt back into vulnerable_packages (for future use)
with open(KNOWN_RISKY_FILE, "r") as f:
    vulnerable_packages = [tuple(line.strip().rsplit("@", 1)) for line in f if line.strip()]

total_packages_count = 0
valid_packages_count = 0
package_limit = 5000
pkg_indices = list(range(len(vulnerable_packages)))
random.shuffle(pkg_indices)
# write to file
with open(OUTPUT_FILE, "w") as f:
    # random select packages from all 
    for idx in pkg_indices:
        pkg, v = vulnerable_packages[idx]
        total_packages_count += 1
        if total_packages_count % 500 == 0:
            time.sleep(5)
        # Check if this package is available in deps.dev api
        print(f'Checking {pkg}@{v} ...')
        dependencies_url = f'https://api.deps.dev/v3alpha/systems/pypi/packages/{pkg}/versions/{v}:dependencies'
        try:
            response = requests.get(dependencies_url, timeout=15)
        except requests.exceptions.Timeout:
            print(f'  Timeout for {pkg}@{v}, skipping.')
            continue
        # Only use packages available in deps.dev and is not an independent package
        if response.status_code == 200:
            f.write(f"{pkg}@{v}\n")
            valid_packages_count += 1
            if valid_packages_count == package_limit:
                break

print(f"Saved {valid_packages_count} vulnerable package-version pairs.")