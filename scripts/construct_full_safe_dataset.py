'''
INVALID
'''
# from GraphGenerator import GraphGenerator
# from FeatureGenerator import FeatureGenerator
# import random

# safe_packages_url = "dataset/safe_packages.txt"
# vulnerable_packages_url = "/data/vulnerable_packages.txt"

# print(f"[Data Loader] Start loading packages from {safe_packages_url}...")
# safe_packages = []
# with open(safe_packages_url, "r") as f_safe:
#     for line in f_safe:
#         safe_packages.append(line.strip())

# print(f"[Data Loader] Start loading packages from {vulnerable_packages_url}...")
# vulnerable_packages = []
# with open(vulnerable_packages_url) as f_vulnerable:
#     for line in f_vulnerable:
#         vulnerable_packages.append(line.strip())

# random.seed(42)
# sampled_vulnerable_packages = random.sample(vulnerable_packages, 5000)

# print(f"Start featurizing packages")
# with open("/data/safe_packages_feature.txt") as f_safe_feature:
#     graph_generator = GraphGenerator("scikit-learn", bfs_depth=2)
#     feature_generator = FeatureGenerator('pypi')
#     for package_id in graph_generator.nodes_map:
#         res = feature_generator.get_full_features(package_id, graph_generator.nodes_map)
#         print(f"Package Id: {package_id}")
#         print(res['full_metadata'])
