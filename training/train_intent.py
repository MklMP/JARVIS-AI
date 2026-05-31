"""
Entrena el clasificador de intención local (MLP + TF-IDF).
Genera: intent_model.joblib, vectorizer.joblib, intent_labels.json
"""
import sys
import os
import json
import csv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Asegurar que sklearn está instalado
try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.neural_network import MLPClassifier
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import classification_report, accuracy_score
    import joblib
except ImportError:
    print("Instalando scikit-learn...")
    os.system("pip install scikit-learn joblib")
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.neural_network import MLPClassifier
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import classification_report, accuracy_score
    import joblib


def cargar_datos(ruta_csv):
    textos, intents = [], []
    with open(ruta_csv, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            textos.append(row["texto"])
            intents.append(row["intent"])
    return textos, intents


def entrenar(X_textos, y):
    # Vectorizar (n-gramas de 1 a 2 palabras, máx 3000 características)
    from sklearn.preprocessing import LabelEncoder
    vectorizer = TfidfVectorizer(
        ngram_range=(1, 2),
        max_features=3000,
        sublinear_tf=True,
    )
    X = vectorizer.fit_transform(X_textos)

    # Entrenar MLP con etiquetas codificadas
    from sklearn.preprocessing import LabelEncoder
    le = LabelEncoder()
    y_enc = le.fit_transform(y)

    clf = MLPClassifier(
        hidden_layer_sizes=(128, 64),
        activation="relu",
        solver="adam",
        max_iter=700,
        random_state=42,
        verbose=False,
    )
    clf.fit(X, y_enc)
    clf._label_encoder = le  # guardar para decodificar después
    return vectorizer, clf, le


def main():
    ruta_csv = os.path.join(os.path.dirname(__file__), "intents.csv")
    if not os.path.exists(ruta_csv):
        print("Generando dataset...")
        from nlu_dataset import generar_csv
        generar_csv(ruta_csv)

    textos, intents = cargar_datos(ruta_csv)
    print(f"Cargados {len(textos)} ejemplos, {len(set(intents))} intenciones")

    # Dividir train/test
    X_train, X_test, y_train, y_test = train_test_split(
        textos, intents, test_size=0.15, random_state=42, stratify=intents
    )
    print(f"Train: {len(X_train)}, Test: {len(X_test)}")

    # Entrenar
    vectorizer, clf, le = entrenar(X_train, y_train)

    # Evaluar
    X_test_vec = vectorizer.transform(X_test)
    y_pred_enc = clf.predict(X_test_vec)
    y_pred = le.inverse_transform(y_pred_enc)
    acc = accuracy_score(y_test, y_pred)
    print(f"\nPrecisión: {acc:.3f}")
    print("\nReporte por intención:")
    print(classification_report(y_test, y_pred, zero_division=0))

    # Guardar modelos
    out_dir = os.path.dirname(os.path.dirname(__file__))
    joblib.dump(clf, os.path.join(out_dir, "intent_model.joblib"))
    joblib.dump(vectorizer, os.path.join(out_dir, "vectorizer.joblib"))
    joblib.dump(le, os.path.join(out_dir, "intent_encoder.joblib"))

    print(f"\nModelos guardados en {out_dir}")
    print(f"Etiquetas: {len(le.classes_)}")
    return acc


if __name__ == "__main__":
    main()
