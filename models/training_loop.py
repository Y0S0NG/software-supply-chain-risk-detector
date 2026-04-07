import sys
import os
import pandas as pd
import random

# Set path 
sys.path.append(os.path.abspath(".."))

# Import dataset
df_safe = pd.read_csv("../data/safe_packages.txt")
df_safe["isRisky"] = 0
print(df_safe.head(5))
print(f"Imported safe packages into dataframe with shape {df_safe.shape}")


df_vulnerable = pd.read_csv("../data/vulnerable_packages.txt").sample(n=5000)
df_vulnerable["isRisky"] = 1
print(df_vulnerable.head(5))
print(f"Imported vulnerable packages into dataframe with shape {df_vulnerable.shape}")

df = pd.concat([df_safe, df_vulnerable], ignore_index=True)
print(df.head(5))
print(f"Shape of combined dataframe: {df.shape}")

X = df.drop(['isRisky'], axis=1)
y = df['isRisky']