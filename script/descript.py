from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt

dataset_path = Path(__file__).resolve().parent / "../Dataset/used_phone_price_prediction_1M.csv"
df = pd.read_csv(dataset_path)

print(df.head())
print(df.shape)
print(df.info())
print(df.isnull().sum())

print()
print(df["resale_price"].describe())

corr = (
    df.select_dtypes(include="number")
      .corr()["resale_price"]
      .sort_values(ascending=False)
)

print()
print(corr)

for col in df.select_dtypes(include="str"):
    print(f"\n{col}:")
    print(df[col].value_counts())

print()
for col in ["brand", "model", "os_type", "condition", "city_tier", "seller_type"]:
    print(f"\n{col}")
    print(df.groupby(col)["resale_price"].agg(["mean", "median", "count"]).sort_values("mean", ascending=False))

df["resale_price"].hist(bins=50)
plt.xlabel("Resale Price")
plt.ylabel("Frequency")
plt.show()