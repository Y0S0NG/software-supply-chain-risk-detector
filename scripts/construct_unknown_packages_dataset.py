import random
import requests
import time

SYSTEM = 'pypi'
PACKAGES_FILE = "../data/pypi_packages.txt"
OUTPUT_FILE = "../data/unknown_packages.txt"
PACKAGE_LIMIT = 5000

with open(PACKAGES_FILE, "r") as f:
    packages = [line.strip() for line in f if line.strip()]

print(f"Loaded {len(packages)} packages. Shuffling...")
random.shuffle(packages)

total_checked = 0
valid_count = 0

with open(OUTPUT_FILE, "w") as f_out:
    for package in packages:
        if valid_count == PACKAGE_LIMIT:
            break

        total_checked += 1
        if total_checked % 500 == 0:
            time.sleep(5)

        # Fetch all versions for this package
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

        # Pick a random version
        version = random.choice(versions)
        print(f'Checking {package}@{version} ...')

        # Call getVersion to check advisoryKeys
        get_version_url = f'https://api.deps.dev/v3alpha/systems/{SYSTEM}/packages/{package}/versions/{version}'
        try:
            ver_response = requests.get(get_version_url, timeout=10)
        except requests.exceptions.Timeout:
            print(f'  Timeout fetching version info for {package}@{version}, skipping.')
            continue

        if ver_response.status_code != 200:
            continue

        advisory_keys = ver_response.json().get('advisoryKeys', [])
        if len(advisory_keys) > 0:
            print(f'  {package}@{version} has known advisories, skipping.')
            continue

        f_out.write(f"{package}@{version}\n")
        valid_count += 1
        print(f'  [{valid_count}/{PACKAGE_LIMIT}] Saved {package}@{version}')

print(f"Done. Checked {total_checked} packages, saved {valid_count} unknown/safe package-version pairs.")
