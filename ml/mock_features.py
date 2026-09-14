import os
import pandas as pd
import numpy as np

def generate_mock_features(firms_csv="firms_processed_sample.csv", seed=42):
    firms = pd.read_csv(firms_csv)
    rng = np.random.default_rng(seed)
    n = len(firms)

    industry_types = ["power_plant", "oil_gas", "factory", "refinery",
                       "industrial_zone", "mine", "landfill", "none"]
    land_covers = ["forest", "agricultural", "industrial", "residential",
                   "water", "mining", "unknown"]
    pop_bands = ["high", "medium", "low", "unknown"]

    nearest_industry = rng.choice(industry_types, size=n,
                                   p=[0.12, 0.08, 0.12, 0.08, 0.15, 0.07, 0.03, 0.35])
    land_cover = rng.choice(land_covers, size=n,
                             p=[0.2, 0.2, 0.15, 0.1, 0.05, 0.05, 0.25])
    population_proximity = rng.choice(pop_bands, size=n, p=[0.2, 0.3, 0.3, 0.2])

    distance_m = np.where(
        nearest_industry == "none",
        rng.uniform(5000, 20000, n),
        rng.exponential(1500, n) + 50
    )
    nearest_forest_km = np.round(rng.exponential(5, n), 2)

    out = pd.DataFrame({
        "anomaly_id": firms["anomaly_id"],
        "latitude": firms["latitude"],
        "longitude": firms["longitude"],
        "nearest_industry": nearest_industry,
        "nearest_industry_name": [f"Facility_{i}" for i in range(n)],
        "distance_m": np.round(distance_m, 1),
        "land_cover": land_cover,
        "nearest_forest_km": nearest_forest_km,
        "population_proximity": population_proximity,
    })
    return out

if __name__ == "__main__":
    df = generate_mock_features()
    df.to_csv("anomaly_features.csv", index=False)
    print("Mock anomaly_features.csv created:", len(df), "rows")
    print(df.head())