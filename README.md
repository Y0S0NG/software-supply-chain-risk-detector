# Software Supply Chain Risk Detector using Graph
A graph based risk prediction system for software supply chain.

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


