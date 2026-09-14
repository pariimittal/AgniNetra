import joblib
import pandas as pd

model = joblib.load("classification_model.pkl")
feature_columns = joblib.load("feature_columns.pkl")

numeric_features = [
    "brightness", "confidence", "detections_30d", "persistence_score",
    "n_detections_total", "distance_m", "nearest_forest_km",
]
categorical_features = ["nearest_industry", "land_cover"]

def classify_anomaly(anomaly_dict):
    row = pd.DataFrame([anomaly_dict])
    row_encoded = pd.get_dummies(row[numeric_features + categorical_features],
                                  columns=categorical_features)
    row_encoded = row_encoded.reindex(columns=feature_columns, fill_value=0)

    predicted_class = model.predict(row_encoded)[0]
    confidence = max(model.predict_proba(row_encoded)[0])

    return {"classification": predicted_class, "confidence": round(float(confidence), 2)}

if __name__ == "__main__":
    test = {
        "brightness": 344.1, "confidence": 75.1, "detections_30d": 7,
        "persistence_score": 0.54, "n_detections_total": 14,
        "distance_m": 420, "nearest_forest_km": 8.2,
        "nearest_industry": "refinery", "land_cover": "industrial",
        
    }
    print(classify_anomaly(test))