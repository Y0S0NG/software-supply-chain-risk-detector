# Software Supply Chain Risk Classifier
A graph based risk prediction system for software supply chain.

## 1. Dataset Construction
Related file: `collect_data.py`
### 1. `collect_data.py`
`collect_data.py` is the automated script for collected data, using deps.dev api

#### Overview
Generate a **directed** graph of package dependencies from a "seed package", then expand the graph using BFS.

#### Key APIs:
+ Package api: https://api.deps.dev/v3alpha/systems/{system}/packages/{package_name}
    This api is for collecting information of all available version, with marked available version
+ Version api: https://api.deps.dev/v3alpha/systems/{system}/packages/{package_name}/versions/{default_version}
    This api is for collecting detailed information about a specific package version, which can be used as package feature.
+ Dependencies api: https://api.deps.dev/v3alpha/systems/pypi/packages/{package_name}/versions/{default_version}:dependencies
    This api provide a resolved dependency graph for the given package version, including "nodes" and "edges"

#### Breakdown
+ Set the 'very seed package'
+ Get the default version of the seed package
+ Get the dependencies of the package's default version
+ Construct the "base graph" using the response of the dependencies api
+ Expand the graph using BFS (traverse the dependencies nodes generated and add their dependencies to the graph)
+ Construct feature map using the version api


