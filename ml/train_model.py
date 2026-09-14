import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, accuracy_score
import joblib

df = pd.read_csv("training_dataset.csv")

if len(df) == 0:
    raise SystemExit(
        "[ERROR] training_dataset.csv has 0 rows — can't train a Random Forest on no "
        "examples. This is an upstream problem, not something to fix here: re-run "
        "merge_and_label.py after firms_pipeline.py has actually produced detections "
        "(widen --day-range, try a different --region, or use --mock)."
    )

n_classes = df["classification"].nunique()
if n_classes < 2:
    raise SystemExit(
        f"[ERROR] training_dataset.csv only has {n_classes} distinct classification "
        "label(s) — a classifier needs at least 2 to learn anything. Check that the "
        "underlying FIRMS data actually has varied detections (not just one repeated "
        "mock/sample source), then re-run merge_and_label.py."
    )

numeric_features = [
    "brightness", "confidence", "detections_30d", "persistence_score",
    "n_detections_total", "distance_m", "nearest_forest_km",
]
categorical_features = ["nearest_industry", "land_cover"]

X = pd.get_dummies(df[numeric_features + categorical_features], columns=categorical_features)
y = df["classification"]

joblib.dump(list(X.columns), "feature_columns.pkl")

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

model = RandomForestClassifier(n_estimators=200, max_depth=10, random_state=42, class_weight="balanced")
model.fit(X_train, y_train)

y_pred = model.predict(X_test)
print("Accuracy:", accuracy_score(y_test, y_pred))
print("\n", classification_report(y_test, y_pred, zero_division=0))

joblib.dump(model, "classification_model.pkl")
print("Model saved as classification_model.pkl")