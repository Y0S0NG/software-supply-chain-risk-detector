import json
import os
import random
import requests
import time

SYSTEM         = 'pypi'
PACKAGES_FILE  = "../data/pypi_packages.txt"
OUTPUT_FILE    = "../data/unknown_packages.txt"
PYPI_CACHE_FILE  = "../data/cache/pypi_cache.json"
DEPS_CACHE_FILE  = "../data/cache/depsdev_deps_cache.json"
PACKAGE_LIMIT  = 5000

os.makedirs("../data/cache", exist_ok=True)

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

with open(PACKAGES_FILE, "r") as f:
    packages = [line.strip() for line in f if line.strip()]

print(f"Loaded {len(packages)} packages. Shuffling...")
random.shuffle(packages)

total_checked = 0
valid_count   = 0

with open(OUTPUT_FILE, "w") as f_out:
    for package in packages:
        if valid_count == PACKAGE_LIMIT:
            break

        total_checked += 1
        if total_checked % 500 == 0:
            time.sleep(5)

        # Fetch all versions from deps.dev and pick a random one
        get_package_url = f'https://api.deps.dev/v3alpha/systems/{SYSTEM}/packages/{package}'
        try:
            pkg_response = requests.get(get_package_url, timeout=10)
        except requests.exceptions.Timeout:
            print(f'  Timeout fetching versions for {package}, skipping.')
            continue

        if pkg_response.status_code != 200:
            continue

        versions = [item['versionKey']['version'] for item in pkg_response.json().get('versions', [])]
        if not versions:
            continue

        version = random.choice(versions)
        key = f"{package}@{version}"
        print(f'Checking {key} ...')

        # Check advisory keys (deps.dev getVersion)
        get_version_url = f'https://api.deps.dev/v3alpha/systems/{SYSTEM}/packages/{package}/versions/{version}'
        try:
            ver_response = requests.get(get_version_url, timeout=10)
        except requests.exceptions.Timeout:
            print(f'  Timeout fetching version info for {key}, skipping.')
            continue

        if ver_response.status_code != 200:
            continue

        if ver_response.json().get('advisoryKeys', []):
            print(f'  {key} has known advisories, skipping.')
            continue

        # --- Filter 1: PyPI API ---
        if key in pypi_cache:
            pypi_data = pypi_cache[key]
        else:
            try:
                r = requests.get(f'https://pypi.org/pypi/{package}/{version}/json', timeout=10)
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
            deps_url = f'https://api.deps.dev/v3alpha/systems/{SYSTEM}/packages/{package}/versions/{version}:dependencies'
            try:
                r = requests.get(deps_url, timeout=15)
            except requests.exceptions.Timeout:
                print(f'  Timeout on deps.dev deps for {key}, skipping.')
                continue
            if r.status_code != 200:
                print(f'  Not found on deps.dev deps ({r.status_code}), skipping.')
                continue
            body = r.json()
            deps_data = {'nodes': body.get('nodes', []), 'edges': body.get('edges', [])}
            deps_cache[key] = deps_data
            save_cache(DEPS_CACHE_FILE, deps_cache)

        f_out.write(f"{key}\n")
        valid_count += 1
        print(f'  [{valid_count}/{PACKAGE_LIMIT}] Saved {key}')

print(f"Done. Checked {total_checked} packages, saved {valid_count} unknown/safe package-version pairs.")
