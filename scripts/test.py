from GraphGenerator import GraphGenerator
import networkx as nx
from pyvis.network import Network
from FeatureGenerator import FeatureGenerator

'''
This testing script went through the entire process of constructing the graph and features
'''
graph_generator = GraphGenerator("scikit-learn", bfs_depth=2)

G = nx.DiGraph()

for package_id, node in graph_generator.nodes_map.items():
    G.add_node(package_id)
    for dep_id in node.depends_on:
        G.add_edge(package_id, dep_id)

net = Network(height="900px", width="100%", directed=True, notebook=False)
net.from_nx(G)
net.write_html("dependency_graph.html", notebook=False)

print(f"nodes={G.number_of_nodes()}, edges={G.number_of_edges()}")
print("Open dependency_graph.html in your browser")

feature_generator = FeatureGenerator('pypi')
for package_id in graph_generator.nodes_map:
    res = feature_generator.get_full_features(package_id, graph_generator.nodes_map)
    print(f"Package Id: {package_id}")
    print(res['full_metadata'])
