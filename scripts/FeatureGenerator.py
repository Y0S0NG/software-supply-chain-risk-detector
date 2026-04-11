import csv
import os
from collections import deque
from datetime import datetime, timezone
from httpx import HTTPError
import requests

# Ordered list of all package-level feature names (must match get_package_metadata return keys)
PACKAGE_FEATURE_NAMES = [
    'num_authors', 'num_maintainers', 'num_roles', 'has_organization',
    'has_license', 'yanked', 'has_sdist', 'has_sig',
    'num_dependencies', 'has_requires_python',
    'num_releases', 'days_since_first_release', 'days_since_last_release', 'dev_status_level',
    'description_length', 'num_classifiers', 'num_project_urls', 'has_homepage',
    'num_wheel_dists', 'total_dist_size_kb',
]
_CACHE_COLUMNS = ['package', 'version'] + PACKAGE_FEATURE_NAMES


def _coerce(value):
    """Convert CSV string back to int or float where possible."""
    try:
        return int(value)
    except (ValueError, TypeError):
        pass
    try:
        return float(value)
    except (ValueError, TypeError):
        pass
    return value


class FeatureGenerator:
    def __init__(self, system, cache_path=None):
        self.system = system
        self._cache_path = cache_path
        self._cache: dict[str, dict] = {}   # key: "pkg@version"

        if cache_path and os.path.exists(cache_path):
            with open(cache_path, newline='') as f:
                for row in csv.DictReader(f):
                    key = f"{row['package']}@{row['version']}"
                    self._cache[key] = {
                        col: _coerce(row[col])
                        for col in PACKAGE_FEATURE_NAMES
                        if col in row
                    }
            print(f'[FeatureGenerator] Loaded {len(self._cache)} cached entries from {cache_path}')

    def _write_cache_row(self, package, version, metadata):
        """Append one row to the cache CSV immediately after a fresh API fetch."""
        if not self._cache_path:
            return
        write_header = not os.path.exists(self._cache_path)
        with open(self._cache_path, 'a', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=_CACHE_COLUMNS)
            if write_header:
                writer.writeheader()
            row = {'package': package, 'version': version}
            row.update({col: metadata.get(col, '') for col in PACKAGE_FEATURE_NAMES})
            writer.writerow(row)

    @staticmethod
    def get_security_advisory(package, version, system):
        get_version_url = f"https://api.deps.dev/v3/systems/{system}/packages/{package}/versions/{version}"
        version_response = requests.get(get_version_url)
        if version_response.status_code != 200:
            raise HTTPError(f"HTTP Error with status code: {version_response.status_code}")

        response_body = version_response.json()
        advisory_keys = response_body['advisoryKeys']

        if len(advisory_keys) == 0:
            return []

        vulnerabilities = []
        for advisory in advisory_keys:
            advisory_id = advisory["id"]
            get_advisory_url = f"https://api.deps.dev/v3/advisories/{advisory_id}"
            vulnerability = requests.get(get_advisory_url).json()
            vulnerabilities.append(vulnerability)

        return vulnerabilities

    def get_full_features(self, package_id, nodes_map):
        package, version = package_id.rsplit('@', 1)
        package_metadata = self.get_package_metadata(package, version)

        package_node = nodes_map.get(package_id)
        structural_metadata = self.get_structural_metadata(package_node, nodes_map)

        package_feature_order = [
            # --- Ownership / identity ---
            "num_authors",
            "num_maintainers",
            "num_roles",
            "has_organization",
            # --- Provenance signals ---
            "has_license",
            "yanked",
            "has_sdist",
            "has_sig",
            # --- Dependency surface ---
            "num_dependencies",
            "has_requires_python",
            # --- Maturity / activity ---
            "num_releases",
            "days_since_first_release",
            "days_since_last_release",
            "dev_status_level",
            # --- Documentation / metadata completeness ---
            "description_length",
            "num_classifiers",
            "num_project_urls",
            "has_homepage",
            # --- Distribution characteristics ---
            "num_wheel_dists",
            "total_dist_size_kb",
        ]
        structural_feature_order = [
            "in_degree",
            "out_degree",
            "depth_from_root",
            "is_leaf",
            "is_shared",
            "graph_node_count",
            "graph_edge_count",
        ]

        col_names = package_feature_order + structural_feature_order
        full_metadata = (
            [package_metadata.get(c, 0) for c in package_feature_order]
            + [structural_metadata.get(c, 0) for c in structural_feature_order]
        )

        return {"full_metadata": full_metadata, "col_names": col_names}

    def get_package_metadata(self, package, version):
        if self.system != 'pypi':
            return {}

        # --- Cache hit ---
        cache_key = f'{package}@{version}'
        if cache_key in self._cache:
            return self._cache[cache_key]

        # --- Version-specific endpoint: info, urls, ownership ---
        ver_url = f"https://pypi.org/pypi/{package}/{version}/json"
        ver_response = requests.get(ver_url)
        if ver_response.status_code != 200:
            return {}
        ver_data = ver_response.json()
        if not ver_data:
            return {}

        info = ver_data.get('info', {})
        urls = ver_data.get('urls', [])
        ownership = ver_data.get('ownership', {})

        # --- Package-level endpoint: full release history ---
        pkg_url = f"https://pypi.org/pypi/{package}/json"
        pkg_response = requests.get(pkg_url)
        releases = {}
        if pkg_response.status_code == 200:
            releases = pkg_response.json().get('releases', {})

        now = datetime.now(timezone.utc)

        # === Ownership / identity ===
        author_email = info.get("author_email") or ""
        maintainer_email = info.get("maintainer_email") or ""
        num_authors = len([e for e in author_email.split(",") if e.strip()])
        num_maintainers = len([e for e in maintainer_email.split(",") if e.strip()])
        num_roles = len(ownership.get('roles', []))
        has_organization = int(bool(ownership.get('organization')))

        # === Provenance signals ===
        has_license = int(bool(info.get("license") or info.get("license_expression") or info.get("license_files")))
        yanked = int(bool(info.get('yanked')))
        # Source distribution present → source is auditable
        has_sdist = int(any(d.get('packagetype') == 'sdist' for d in urls))
        # Any file carries a GPG detached signature
        has_sig = int(any(d.get('has_sig') for d in urls))

        # === Dependency surface ===
        requires_dist = info.get('requires_dist') or []
        num_dependencies = len(requires_dist)
        has_requires_python = int(bool(info.get('requires_python')))

        # === Maturity / activity ===
        # Collect all upload timestamps across all releases
        all_times = []
        for dists in releases.values():
            for dist in dists:
                raw = dist.get('upload_time_iso_8601') or dist.get('upload_time')
                if raw:
                    try:
                        dt = datetime.fromisoformat(raw.replace('Z', '+00:00'))
                        if dt.tzinfo is None:
                            dt = dt.replace(tzinfo=timezone.utc)
                        all_times.append(dt)
                    except ValueError:
                        pass

        num_releases = len(releases)
        if all_times:
            days_since_first_release = (now - min(all_times)).days
            days_since_last_release = (now - max(all_times)).days
        else:
            days_since_first_release = -1
            days_since_last_release = -1

        # Development status: ordinal 0–3
        # 0 = unknown, 1 = pre-production (Planning/Pre-Alpha/Alpha),
        # 2 = Beta, 3 = Production/Stable/Mature
        dev_status_level = 0
        _dev_map = {
            'production/stable': 3, 'mature': 3,
            'beta': 2,
            'alpha': 1, 'pre-alpha': 1, 'planning': 1,
        }
        for c in (info.get('classifiers') or []):
            if 'Development Status' in c:
                c_lower = c.lower()
                for key, lvl in _dev_map.items():
                    if key in c_lower:
                        dev_status_level = lvl
                        break
                break

        # === Documentation / metadata completeness ===
        description_length = len(info.get('description') or "")
        classifiers = info.get('classifiers') or []
        num_classifiers = len(classifiers)
        project_urls = info.get('project_urls') or {}
        num_project_urls = len(project_urls)
        _homepage_keys = {'homepage', 'home page', 'source', 'repository', 'github'}
        has_homepage = int(
            bool(info.get('home_page'))
            or any(k.lower() in _homepage_keys for k in project_urls)
        )

        # === Distribution characteristics ===
        num_wheel_dists = sum(1 for d in urls if d.get('packagetype') == 'bdist_wheel')
        total_dist_size_kb = sum(d.get('size', 0) for d in urls) // 1024

        metadata = {
            # Ownership / identity
            "num_authors": num_authors,
            "num_maintainers": num_maintainers,
            "num_roles": num_roles,
            "has_organization": has_organization,
            # Provenance signals
            "has_license": has_license,
            "yanked": yanked,
            "has_sdist": has_sdist,
            "has_sig": has_sig,
            # Dependency surface
            "num_dependencies": num_dependencies,
            "has_requires_python": has_requires_python,
            # Maturity / activity
            "num_releases": num_releases,
            "days_since_first_release": days_since_first_release,
            "days_since_last_release": days_since_last_release,
            "dev_status_level": dev_status_level,
            # Documentation / metadata completeness
            "description_length": description_length,
            "num_classifiers": num_classifiers,
            "num_project_urls": num_project_urls,
            "has_homepage": has_homepage,
            # Distribution characteristics
            "num_wheel_dists": num_wheel_dists,
            "total_dist_size_kb": total_dist_size_kb,
        }

        # --- Persist to cache ---
        self._cache[cache_key] = metadata
        self._write_cache_row(package, version, metadata)
        return metadata

    def get_structural_metadata(self, node, nodes_map):
        # for independent package
        if len(nodes_map) == 1:
            return {
                "in_degree": 0, "out_degree": 0,
                "depth_from_root": 0, "is_leaf": 1, "is_shared": 0,
                "graph_node_count": 1, "graph_edge_count": 0,
            }

        node_id = node.package_id

        # --- Basic degree ---
        out_degree = len(node.depends_on)
        in_degree = sum(1 for n in nodes_map.values() if node_id in n.depends_on)

        # --- Graph-level stats ---
        graph_node_count = len(nodes_map)
        graph_edge_count = sum(
            sum(1 for dep in n.depends_on if dep in nodes_map)
            for n in nodes_map.values()
        )

        # --- Depth from root (roots = nodes with in_degree 0) ---
        in_degrees = {nid: 0 for nid in nodes_map}
        for n in nodes_map.values():
            for dep_id in n.depends_on:
                if dep_id in in_degrees:
                    in_degrees[dep_id] += 1

        roots = [nid for nid, deg in in_degrees.items() if deg == 0]
        depth_from_root = -1
        if roots:
            depth_map = {r: 0 for r in roots}
            queue = deque(roots)
            while queue:
                cur = queue.popleft()
                for dep_id in nodes_map[cur].depends_on:
                    if dep_id in nodes_map and dep_id not in depth_map:
                        depth_map[dep_id] = depth_map[cur] + 1
                        queue.append(dep_id)
            depth_from_root = depth_map.get(node_id, -1)

        return {
            "in_degree": in_degree,
            "out_degree": out_degree,
            "depth_from_root": depth_from_root,
            "is_leaf": int(out_degree == 0),
            "is_shared": int(in_degree > 1),
            "graph_node_count": graph_node_count,
            "graph_edge_count": graph_edge_count,
        }
