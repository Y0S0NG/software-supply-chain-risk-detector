# Software Supply Chain Risk Detector using Graph
This project construct a package-version dependency graph using deps.dev resolved dependencies. Nodes are package versions with metadata features. Edges encode dependency relations. Known vulnerable package versions are labeled using OSV advisories. I train a inductive GNN to model how vulnerability risk or exposure correlates with dependency structure and propagates through transitive dependencies.

Key Assumptions:
+ Package dependency only imply vulnerability exposure, not exploitation.
## 1. Dataset Construction
Related file:`PackageNode.py`, `GraphGenerator.py`

### 1. `PackageNode.py`
`PackageNode.py` defines a customized class `PackageNode` which model packages:
+ package_id: unique identifier of a package, in the form `package@version`
+ feaures: feature vector of the package
+ depends_on: a set storing the package_id of the packages that the current package dependes on
### 2. `GraphGenerator.py`
`GraphGenerator` also defines an customized class. It encapsulates the graph data and initialization of the dependency graph.

#### Key attributes
+ `systems` - ecosystem of the package, default value: `pypi`
+ `levels` - nested list of PackageNode instances visited in each bfs iteration
+ `nodes_map` - dictionary storing key-value pair of package_id and PackageNode instance.
+ `bfs_depth` - maximum depth of map expansion

#### Key functions:
+ `__init__` - initialize and build the whole graph
+ `_fetch_dependencies` - helper function on fetching dependencies of a given version of packages
+ `_fetch_default_version` - helper function on fetching default version of a given package
+ `_bfs_graph_construction` - helper function on expanding the dependency graph using BFS

#### Breaking down graph construction
+ Set the 'very seed package'
+ Get the default version of the seed package(if not provided)
+ Get the dependencies of the package's default version
+ Construct the "base graph" using the response of the dependencies api
+ Expand the graph using BFS (traverse the dependencies nodes generated and add their dependencies to the graph)
+ Construct feature map using the version api

#### Key APIs:
+ Package api: https://api.deps.dev/v3alpha/systems/{system}/packages/{package_name}
    This api is for collecting information of all available version, with marked available version
+ Version api: https://api.deps.dev/v3alpha/systems/{system}/packages/{package_name}/versions/{default_version}
    This api is for collecting detailed information about a specific package version, which can be used as package feature.
+ Dependencies api: https://api.deps.dev/v3alpha/systems/pypi/packages/{package_name}/versions/{default_version}:dependencies
    This api provide a resolved dependency graph for the given package version, including "nodes" and "edges"

For more information, check [this link](https://docs.deps.dev/api/)

### 3. `FeatureGenerator.py`
Defines a customized class that featurizes a given package using metadata from the PyPI API and structural properties derived from the dependency graph built by `GraphGenerator`.

#### Key methods:
+ `get_package_metadata(package, version)` - fetches package-level metadata from the PyPI JSON API and returns a feature dict with:
  + `num_authors`, `num_maintainers` - parsed from comma-separated email fields
  + `has_license` - whether any license files are attached
  + `yanked` - whether this version has been yanked from PyPI
  + `has_project_url`, `has_package_url`, `has_release_url` - presence of URL metadata
  + `has_organization` - whether the package is owned by an organization
  + `num_roles` - number of ownership roles
  + `num_distributions` - number of distribution files (wheels, tarballs, etc.)
+ `get_structural_metadata(node, nodes_map)` - computes graph-structural features for a node:
  + `in_degree` - number of packages that depend on this package (reverse dependency count)
  + `out_degree` - number of direct dependencies of this package
+ `get_full_features(package_id, nodes_map)` - combines package metadata and structural metadata into a single ordered feature vector alongside column names
+ `get_security_advisory(package, version, system)` *(static)* - queries the deps.dev advisory API to retrieve known CVE/advisory records for a specific package version

#### Feature vector order (12 dimensions):
`num_authors`, `num_maintainers`, `has_license`, `yanked`, `has_project_url`, `has_package_url`, `has_release_url`, `has_organization`, `num_roles`, `num_distributions`, `in_degree`, `out_degree`

---

## 2. Dataset Construction Scripts
Related files: `scripts/get_all_pypi_packages.py`, `scripts/construct_safe_packages_dataset.py`, `scripts/construct_vulnerable_packages_dataset.py`

### 1. `get_all_pypi_packages.py`
Fetches the full list of package names from the PyPI Simple API and writes them to `scripts/pypi_packages.txt`. Used as the universe of candidate safe packages.

+ Calls `https://pypi.org/simple/` with `Accept: application/vnd.pypi.simple.v1+json`
+ Extracts the `name` field from each project entry

### 2. `construct_safe_packages_dataset.py`
Builds the negative (safe) class of the training dataset.

+ Randomly samples 5,000 package names from `pypi_packages.txt`
+ For each package, queries the deps.dev package API to resolve its default version
+ Writes `package@version` pairs to `data/safe_packages.txt`
+ Includes a rate-limit sleep every 500 requests

### 3. `construct_vulnerable_packages_dataset.py`
Builds the positive (vulnerable) class of the training dataset from OSV advisory YAML files.

+ Walks the `vulns/` directory (OSV-format YAML files, excluded from this documentation)
+ Skips withdrawn advisories
+ Filters to PyPI ecosystem entries only
+ Extracts explicit `versions` lists from each `affected` entry
+ Randomly shuffles and iterates candidates; for each, queries deps.dev to verify availability and ensure it has at least one dependency (non-isolated packages only)
+ Writes up to 5,000 valid `package@version` pairs to `data/vulnerable_packages.txt`

---
