from networkx import graph_edit_distance, house_graph

from FeatureGenerator import FeatureGenerator
from GraphGenerator import GraphGenerator

graph_generator = GraphGenerator('scikit-learn')
feature_generator = FeatureGenerator('pypi')

# package_features = feature_generator.get_package_metadata('scikit-learn', '1.8.0')
# print(package_features)

# structural_feature = feature_generator.get_structural_metadata(graph_generator.nodes_map['scikit-learn@1.8.0'])
# print(structural_feature)

full_feature = feature_generator.get_full_features('scikit-learn@1.8.0', graph_generator.nodes_map)
print(full_feature)


