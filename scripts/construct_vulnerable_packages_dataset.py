import json
import os
import random
import requests
import time

SYSTEM = 'pypi'
KNOWN_RISKY_FILE  = "../data/known_risky_packages.txt"
OUTPUT_FILE       = "../data/vulnerable_packages.txt"
PYPI_CACHE_FILE   = "../data/cache/pypi_cache.json"
DEPS_CACHE_FILE   = "../data/cache/depsdev_deps_cache.json"
PACKAGE_LIMIT     = 5000

os.makedirs("../data/cache", exist_ok=True)

# Load existing caches
def load_cache(path):
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {}

def save_cache(path, cache):
    with open(path, 'w') as f:
        json.dump(cache, f)

pypi_cache  = load_cache(PYPI_CACHE_FILE)
deps_cache  = load_cache(DEPS_CACHE_FILE)

# Read known risky packages
with open(KNOWN_RISKY_FILE, "r") as f:
    vulnerable_packages = [tuple(line.strip().rsplit("@", 1)) for line in f if line.strip()]

pkg_indices = list(range(len(vulnerable_packages)))
random.shuffle(pkg_indices)

total_checked   = 0
valid_count     = 0

with open(OUTPUT_FILE, "w") as f_out:
    for idx in pkg_indices:
        if valid_count == PACKAGE_LIMIT:
            break

        pkg, v = vulnerable_packages[idx]
        key = f"{pkg}@{v}"
        total_checked += 1

        if total_checked % 500 == 0:
            time.sleep(5)

        print(f'Checking {key} ...')

        # --- Filter 1: PyPI API ---
        if key in pypi_cache:
            pypi_data = pypi_cache[key]
        else:
            try:
                r = requests.get(f'https://pypi.org/pypi/{pkg}/{v}/json', timeout=10)
            except requests.exceptions.Timeout:
                print(f'  Timeout on PyPI for {key}, skipping.')
                continue
            if r.status_code != 200:
                print(f'  Not found on PyPI ({r.status_code}), skipping.')
                continue
            pypi_data = r.json()
            pypi_cache[key] = pypi_data
            save_cache(PYPI_CACHE_FILE, pypi_cache)

        # --- Filter 2: deps.dev dependency API ---
        if key in deps_cache:
            deps_data = deps_cache[key]
        else:
            deps_url = f'https://api.deps.dev/v3alpha/systems/{SYSTEM}/packages/{pkg}/versions/{v}:dependencies'
            try:
                r = requests.get(deps_url, timeout=15)
            except requests.exceptions.Timeout:
                print(f'  Timeout on deps.dev for {key}, skipping.')
                continue
            if r.status_code != 200:
                print(f'  Not found on deps.dev ({r.status_code}), skipping.')
                continue
            body = r.json()
            deps_data = {'nodes': body.get('nodes', []), 'edges': body.get('edges', [])}
            deps_cache[key] = deps_data
            save_cache(DEPS_CACHE_FILE, deps_cache)

        f_out.write(f"{key}\n")
        valid_count += 1
        print(f'  [{valid_count}/{PACKAGE_LIMIT}] Saved {key}')

print(f"Done. Checked {total_checked}, saved {valid_count} vulnerable package-version pairs.")
