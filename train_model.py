import pandas as pd
from sklearn.ensemble import RandomForestRegressor
import joblib

# Load dataset
data = pd.read_csv("sales_data_large.csv")

X = data[['views', 'price', 'discount']]
y = data['sales']

# Train model
sales_model = RandomForestRegressor(n_estimators=100)
sales_model.fit(X, y)

# Save model
joblib.dump(sales_model, "sales_model.pkl")

print("✅ Model trained and saved as sales_model.pkl")