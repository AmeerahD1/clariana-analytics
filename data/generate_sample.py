"""
One-off script to generate a realistic, imperfect e-commerce sales dataset
for testing the analytics pipeline. Run once: python data/generate_sample.py
"""
import pandas as pd
import numpy as np
import random
from datetime import datetime, timedelta

random.seed(42)
np.random.seed(42)

N = 500  # number of records

products = {
    "Laptop": ("Electronics", 55000, 42000),
    "Smartphone": ("Electronics", 25000, 18000),
    "Headphones": ("Electronics", 3000, 1800),
    "Office Chair": ("Furniture", 8000, 5000),
    "Desk": ("Furniture", 12000, 8000),
    "Running Shoes": ("Footwear", 3500, 2000),
    "Backpack": ("Accessories", 1800, 900),
    "Watch": ("Accessories", 6000, 3500),
}
regions = ["North", "South", "East", "West"]
payment_methods = ["Credit Card", "UPI", "Debit Card", "Cash on Delivery", "credit card", "COD"]  # inconsistent casing/labels on purpose
segments = ["Premium", "Regular", "Budget", None]  # None -> missing values on purpose

rows = []
start_date = datetime(2024, 1, 1)

for i in range(1, N + 1):
    product = random.choice(list(products.keys()))
    category, base_price, base_cost = products[product]

    unit_price = base_price * random.uniform(0.9, 1.1)
    cost = base_cost * random.uniform(0.9, 1.1)
    quantity = random.randint(1, 5)
    revenue = round(unit_price * quantity, 2)
    total_cost = round(cost * quantity, 2)
    profit = round(revenue - total_cost, 2)

    order_date = start_date + timedelta(days=random.randint(0, 400))
    date_str = order_date.strftime("%Y-%m-%d")

    # Inject some invalid dates (~2%)
    if random.random() < 0.02:
        date_str = "31/02/2024"  # invalid date

    # Inject some missing values (~5%)
    customer_segment = random.choice(segments)

    row = {
        "Order_ID": f"O{10000 + i}",
        "Order_Date": date_str,
        "Customer_ID": f"C{random.randint(1000, 1400)}",
        "Product": product,
        "Category": category,
        "Quantity": quantity if random.random() > 0.01 else -quantity,  # rare negative qty
        "Unit_Price": round(unit_price, 2),
        "Revenue": revenue,
        "Cost": total_cost,
        "Profit": profit,
        "Region": random.choice(regions),
        "Payment_Method": random.choice(payment_methods),
        "Customer_Segment": customer_segment,
    }
    rows.append(row)

df = pd.DataFrame(rows)

# Inject some missing values directly (~3% of Unit_Price and Region)
for col in ["Unit_Price", "Region"]:
    mask = df.sample(frac=0.03).index
    df.loc[mask, col] = np.nan

# Inject duplicate rows (~2%)
dupes = df.sample(frac=0.02)
df = pd.concat([df, dupes], ignore_index=True)

# Inject a few extreme outliers in Revenue
outlier_idx = df.sample(5).index
df.loc[outlier_idx, "Revenue"] = df.loc[outlier_idx, "Revenue"] * 20

df.to_csv("data/sample_sales.csv", index=False)
print(f"Generated data/sample_sales.csv with {len(df)} rows.")