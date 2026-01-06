# Feature Engineering Phase 5: Feature Normalization & Model-Ready Export

**Projektphase:** Feature Engineering (Phase 2)  
**Datum:** 6. Januar 2026  
**Autor:** Silas Pignotti  
**Notebook:** `notebooks/feature_engineering/05_feature_normalization_model_ready_export.ipynb`

---

## 1. Übersicht

Dieses Dokument beschreibt die **fünfte Feature Engineering Phase**: Feature-Normalisierung und Vorbereitung für Machine Learning.

### 1.1 Zweck

Transformiert räumlich disjunkte Splits zu **normalisiertem, ML-ready Format**:

- **Problem:** Features haben unterschiedliche Skalen (CHM in Metern, NDVI in [0-1], Reflektanz in [0-10000])
- **Folge:** ML-Modelle (RFC, CNN, XGBoost) konvergieren schlecht bei nicht-normalisierter Input
- **Lösung:** Z-Score Normalisierung (StandardScaler), Label Encoding (0-6)

**Output:** 6 normalisierte Datasets (train/val für Hamburg/Berlin, zero-shot + finetune für Rostock)

### 1.2 Data Pipeline

```
Split-Daten aus Phase 2.4 (28,866 Bäume, 184 Features)
├── Hamburg Train/Val: 10,500 Bäume
├── Berlin Train/Val: 10,288 Bäume
└── Rostock (Zero-Shot + Fine-Tune): 8,078 Bäume
    ↓
[Preprocessing] Label Encoding
    ├── Map Genus_Latin → Integer Labels (0-6)
    ├── ACER→0, BETULA→1, FRAXINUS→2, PRUNUS→3, QUERCUS→4, SORBUS→5, TILIA→6
    └── Result: y as integer array
    ↓
[Preprocessing] Feature Normalization
    ├── Fit StandardScaler (mean=0, std=1) on TRAINING data only
    ├── Transform all splits (train/val/test) using training scaler
    ├── 3 separate scalers (Exp 0 Hamburg, Exp 1 Berlin, Exp 2 Hamburg+Berlin)
    └── Result: Normalized X as numpy arrays
    ↓
[Experiment 1] Single-City Baseline
    ├── Hamburg: Train/Val split with Hamburg scaler
    ├── Berlin: Train/Val split with Berlin scaler
    └── Purpose: Single-city reference performance
    ↓
[Experiment 2] Cross-City Transfer
    ├── Combined Train: Hamburg + Berlin (16,670 samples)
    ├── Scaler fitted on Combined Train
    ├── Rostock Zero-Shot: Test on unseen city (without training)
    └── Purpose: Transfer learning baseline
    ↓
[Experiment 3] Fine-Tuning Adaptation
    ├── Uses Combined Scaler (from Exp 2)
    ├── Rostock Fine-Tune Eval: Small eval set for fine-tuning
    └── Purpose: Test adaptation with small labeled data
    ↓
[Export] Model-Ready Arrays
    ├── X_train.npy, y_train.npy (features & labels)
    ├── X_val.npy, y_val.npy
    ├── scaler.pkl (fitted StandardScaler)
    └── label_encoder.pkl, feature_names.json
    ↓ READY FOR ML
```

---

## 2. Label Encoding

### 2.1 Genus Label Mapping

```
Label Mapping (Alphabetisch):
  0: ACER          (Ahorn / Maple)
  1: BETULA        (Birke / Birch)
  2: FRAXINUS      (Esche / Ash)
  3: PRUNUS        (Kirsche/Pflaume / Cherry/Plum)
  4: QUERCUS       (Eiche / Oak)
  5: SORBUS        (Eberesche / Rowan)
  6: TILIA         (Linde / Linden)
```

### 2.2 Encoding Procedure

```python
from sklearn.preprocessing import LabelEncoder

# Create mapping
label_encoder = LabelEncoder()
label_encoder.fit(['ACER', 'BETULA', 'FRAXINUS', 'PRUNUS', 'QUERCUS', 'SORBUS', 'TILIA'])

# Transform all datasets
y_hamburg_train = label_encoder.transform(hamburg_train['genus_latin'])
y_hamburg_val = label_encoder.transform(hamburg_val['genus_latin'])
# ... etc for all splits

# Save for later
pickle.dump(label_encoder, 'label_encoder.pkl')
```

**Result:** Alle y-Werte sind integers [0, 6]

---

## 3. Feature Normalization

### 3.1 StandardScaler Strategy

**Goal:** Transform each feature to mean=0, std=1

```
Formula:
  x_normalized = (x - x_train_mean) / x_train_std

Why StandardScaler?
  - Linear algorithms (RFC, SVM) sensitive to scale
  - Neural networks (CNN) need normalized input
  - Regularization (L1/L2) assumes normalized features
```

### 3.2 Data Leakage Prevention

**Critical:** Scaler MUST be fitted on TRAINING data ONLY

```python
# ❌ WRONG (Data Leakage):
scaler = StandardScaler()
scaler.fit(X_all)  # Fit on train+val+test → val/test statistics leak to train!
X_train = scaler.transform(X_train)
X_val = scaler.transform(X_val)

# ✅ CORRECT (No Leakage):
scaler = StandardScaler()
scaler.fit(X_train)  # Fit ONLY on training data
X_train = scaler.transform(X_train)
X_val = scaler.transform(X_val)  # Val mean/std will NOT be 0/1
X_test = scaler.transform(X_test)  # But no information leaked!
```

**Why this matters:**

- If scaler fit on train+val, model will be overoptimistic about val performance
- Real-world: val/test data should be "unknown" to scaler
- Cross-validation: Each fold gets its own scaler (fitted on fold train data)

### 3.3 Scaling Results

**Hamburg Train (after scaling):**

```
Mean: -0.0000 (✅ ~0)
Std:  1.0000 (✅ ~1)
```

**Hamburg Val (after scaling, using Hamburg Train scaler):**

```
Mean:  0.0148 (✅ ≠ 0, expected)
Std:   1.9760 (✅ ≠ 1, expected)
Reason: Val scaler fitted on different data (Train)
```

**Rostock Zero-Shot (after scaling, using Hamburg+Berlin scaler):**

```
Mean: 0.1568 (✅ ≠ 0, expected)
Std:  1.0341 (✅ ~1, but not exact)
Reason: Different city, different spectral characteristics
```

---

## 4. Label Distribution Validation

### 4.1 Hamburg Label Distribution

**Train (8,371 trees):**

```
ACER:     1,192 (14.2%)
BETULA:   1,217 (14.5%)
FRAXINUS: 1,157 (13.8%)
PRUNUS:   1,194 (14.3%)
QUERCUS:  1,200 (14.3%)
SORBUS:   1,205 (14.4%)
TILIA:    1,206 (14.4%)
──────────────────────
Total:    8,371 (100%)
```

**Observation:** Perfect balance (~14.3% each) → No class imbalance ✅

**Val (2,129 trees):**

```
Alle Genera vorhanden (min 283 BETULA, max 343 FRAXINUS)
Range: 13.3% - 16.1% (slight imbalance ok)
```

### 4.2 Berlin Label Distribution

**Train (8,299 trees):**

```
ACER:     1,224 (14.7%)
BETULA:   1,198 (14.4%)
FRAXINUS: 1,239 (14.9%)
PRUNUS:   1,184 (14.3%)
QUERCUS:  1,226 (14.8%)
SORBUS:   1,026 (12.4%)  ← Slightly lower
TILIA:    1,202 (14.5%)
──────────────────────
Total:    8,299 (100%)
```

**Observation:** SORBUS only 12.4% (but still balanced enough) ✅

### 4.3 Rostock Label Distribution

**Zero-Shot (6,675 trees):**

```
ACER:     1,227 (18.4%)  ← Higher
BETULA:   1,286 (19.3%)  ← Higher
FRAXINUS:   730 (10.9%)  ← Lower (min availability)
PRUNUS:     546 (8.2%)   ← Lower (min availability)
QUERCUS:  1,199 (18.0%)  ← Higher
SORBUS:     524 (7.9%)   ← Lower (min availability)
TILIA:    1,163 (17.4%)  ← Higher
──────────────────────
Total:    6,675 (100%)
```

**Observation:** Rostock hat andere Distribution (from Phase 2.3 balancing limits) ✅

**Fine-Tune (1,403 trees):**

```
Sehr unbalanced wegen klein:
TILIA:    337 (24.0%)  ← Dominant
ACER:     273 (19.5%)
QUERCUS:  263 (18.7%)
BETULA:   214 (15.3%)
SORBUS:   121 (8.6%)
FRAXINUS: 116 (8.3%)
PRUNUS:    79 (5.6%)   ← Minimal
──────────────────────
Total:    1,403 (100%)
```

**Note:** Fine-Tune ist klein, daher unbalanced (aber ok für evaluation)

---

## 5. Experiment Definitions

### 5.1 Experiment 0/1: Single-City Baseline

**Ziel:** Baseline-Performance pro Stadt (keine Transfer Learning)

**Hamburg Setup:**

```
Train:
  Data: hamburg_train.gpkg (8,371 trees, 1,352 blocks)
  Scaler: Fitted on hamburg_train features only
  After Scaling: Mean≈0, Std≈1

Validation:
  Data: hamburg_val.gpkg (2,129 trees, 335 blocks)
  Scaler: SAME as hamburg_train (no refitting!)
  After Scaling: Mean≈0.015, Std≈2.0 (natural variation)
```

**Berlin Setup:** (Identical logic)

```
Train: berlin_train (8,299 trees, 1,789 blocks)
Val: berlin_val (1,989 trees, 457 blocks)
Scaler: Fitted on berlin_train only
```

**Expected Model Performance:**

```
Single-City Random Forest (RFC):
  Hamburg: Accuracy ≈ 85-90% (same-city validation)
  Berlin:  Accuracy ≈ 85-90% (same-city validation)

Why high?
  - Trees in Hamburg Val are spatially close to Hamburg Train
  - Model learns Hamburg-specific patterns (urban structure, tree layout)
  - Overfitting likely on city-specific features
```

**Usage:**

```
Experiment 0/1 Output Files:
├── experiment_0_1_single_city/
│   ├── hamburg/
│   │   ├── X_train.npy (8,371 × 184)
│   │   ├── y_train.npy (8,371,)
│   │   ├── X_val.npy (2,129 × 184)
│   │   ├── y_val.npy (2,129,)
│   │   └── scaler.pkl
│   └── berlin/
│       ├── (same structure)
```

---

### 5.2 Experiment 2: Cross-City Transfer Learning

**Ziel:** Train on Hamburg+Berlin, test generalization on Rostock (unseen city)

**Combined Training:**

```
Train:
  Hamburg Train (8,371 trees) +
  Berlin Train (8,299 trees)
  ═════════════════════════════
  Total: 16,670 trees, 1,789+1,352=3,141 blocks

Scaler: Fitted on Combined Train (16,670 samples)
  Mean: -0.0000 (✅ Exactly 0)
  Std:  1.0000 (✅ Exactly 1)
```

**Validation (for hyperparameter tuning):**

```
Hamburg Val (2,129) +
Berlin Val (1,989)
═════════════════════
Total Val: 4,118 trees
```

**Zero-Shot Test (Rostock unseen city):**

```
Test:
  Rostock Zero-Shot (6,675 trees, 308 blocks)
  Model never seen Rostock during training!

Scaler: Same as Combined Train (no refitting)
  Mean: 0.1568 (natural variation from different geography)
  Std:  1.0341 (similar scale due to scaler)
```

**Expected Model Performance:**

```
Cross-City Random Forest (RFC):
  Hamburg+Berlin Val: Accuracy ≈ 80-85%
  Rostock Zero-Shot: Accuracy ≈ 50-70% (major drop)

Why lower?
  - Rostock is coastal city (different tree species distribution)
  - Different urban structure (smaller, more clustered)
  - Geographic differences → Spectral differences
  - Model must generalize to unseen domain
```

**Usage:**

```
Experiment 2 Output Files:
├── experiment_2_cross_city/
│   ├── X_train_hamburg.npy (8,371 × 184)
│   ├── y_train_hamburg.npy (8,371,)
│   ├── X_train_berlin.npy (8,299 × 184)
│   ├── y_train_berlin.npy (8,299,)
│   ├── X_val_hamburg.npy (2,129 × 184)
│   ├── y_val_hamburg.npy (2,129,)
│   ├── X_val_berlin.npy (1,989 × 184)
│   ├── y_val_berlin.npy (1,989,)
│   ├── X_test_rostock_zero_shot.npy (6,675 × 184)
│   ├── y_test_rostock_zero_shot.npy (6,675,)
│   └── scaler.pkl (fitted on Hamburg+Berlin Train)
```

---

### 5.3 Experiment 3: Fine-Tuning Adaptation

**Ziel:** Test model's ability to adapt to Rostock with small fine-tune data

**Setup:**

```
Pre-trained Model:
  Trained on Hamburg+Berlin (Exp 2)
  Performance on Rostock Zero-Shot: ≈50-70%

Fine-Tuning Data:
  Rostock Fine-Tune Eval (1,403 trees, 78 blocks)
  Small subset of Rostock

Fine-Tuning Process:
  1. Take pre-trained model
  2. Unfreeze last N layers
  3. Train on Rostock Fine-Tune (1,403 samples) for M epochs
  4. Evaluate on Rostock Zero-Shot (6,675 samples)

Scaler: SAME as Exp 2 (no refitting!)
  Important: Do NOT fit new scaler on fine-tune data
  Otherwise information leaks from train to test
```

**Expected Model Performance:**

```
Before Fine-Tuning (Zero-Shot):
  Rostock Zero-Shot Accuracy: ≈50-70%

After Fine-Tuning (on 1,403 samples):
  Rostock Zero-Shot Accuracy: ≈70-80%

Improvement: ≈10-20 percentage points
  Shows model CAN learn Rostock-specific patterns
```

**Real-World Use Case:**

```
Deployment Scenario:
  1. Deploy Hamburg+Berlin model to new city Rostock
  2. Collect 1,403 labeled trees in Rostock
  3. Fine-tune model for 1-2 epochs
  4. Accuracy improves to ≈75%
  5. Model ready for production
```

**Usage:**

```
Experiment 3 Output Files:
├── experiment_3_finetuning/
│   ├── X_test_rostock_finetune_eval.npy (1,403 × 184)
│   ├── y_test_rostock_finetune_eval.npy (1,403,)
│   └── scaler.pkl (COPY of Exp 2, no refitting!)
```

---

## 6. Feature Metadata

### 6.1 Feature Structure (184 total)

```
Sentinel-2 Bands (120 features):
  - B02 (Blue): 12 months × 1 = 12 features
  - B03 (Green): 12 months × 1 = 12 features
  - B04 (Red): 12 months × 1 = 12 features
  - B05 (Veg Red Edge): 12 months × 1 = 12 features
  - B06 (Veg Red Edge): 12 months × 1 = 12 features
  - B07 (Veg Red Edge): 12 months × 1 = 12 features
  - B08 (NIR): 12 months × 1 = 12 features
  - B8A (Narrow NIR): 12 months × 1 = 12 features
  - B11 (SWIR-1): 12 months × 1 = 12 features
  - B12 (SWIR-2): 12 months × 1 = 12 features

Vegetation Indices (60 features):
  - NDre (Normalized Difference Red Edge): 12 months
  - NDVIre (NDVI Red Edge): 12 months
  - kNDVI (Kernel NDVI): 12 months
  - VARI (Visible Atmospherically Resistant Index): 12 months
  - RTVIcore (Red-Edge Triangulation VI): 12 months
  Total: 5 indices × 12 months = 60 features

CHM Features (4 features):
  - height_m (Tree height from CHM peak)
  - CHM_mean (Mean height in 30m buffer)
  - CHM_max (Max height in 30m buffer)
  - CHM_std (Std of heights in 30m buffer)

──────────────────────
Total: 120 + 60 + 4 = 184 features
```

### 6.2 Feature Metadata File

**Datei:** `feature_names.json`

```json
{
  "total_features": 184,
  "sentinel2_bands": 120,
  "vegetation_indices": 60,
  "chm_features": 4,
  "feature_list": [
    "B02_01", "B02_02", ..., "B02_12",
    "B03_01", "B03_02", ..., "B03_12",
    ...
    "B12_01", "B12_02", ..., "B12_12",
    "NDre_01", "NDre_02", ..., "NDre_12",
    "NDVIre_01", "NDVIre_02", ..., "NDVIre_12",
    "kNDVI_01", "kNDVI_02", ..., "kNDVI_12",
    "VARI_01", "VARI_02", ..., "VARI_12",
    "RTVIcore_01", "RTVIcore_02", ..., "RTVIcore_12",
    "height_m", "CHM_mean", "CHM_max", "CHM_std"
  ]
}
```

---

## 7. Output-Dateien Structure

### 7.1 Directory Layout

```
data/model_ready/
├── experiment_0_1_single_city/
│   ├── hamburg/
│   │   ├── X_train.npy          (8,371 × 184 float32)
│   │   ├── y_train.npy          (8,371,) int32 [0-6]
│   │   ├── X_val.npy            (2,129 × 184 float32)
│   │   ├── y_val.npy            (2,129,) int32 [0-6]
│   │   └── scaler.pkl           (StandardScaler fitted on Hamburg Train)
│   └── berlin/
│       ├── X_train.npy          (8,299 × 184 float32)
│       ├── y_train.npy          (8,299,) int32 [0-6]
│       ├── X_val.npy            (1,989 × 184 float32)
│       ├── y_val.npy            (1,989,) int32 [0-6]
│       └── scaler.pkl           (StandardScaler fitted on Berlin Train)
│
├── experiment_2_cross_city/
│   ├── X_train_hamburg.npy      (8,371 × 184 float32)
│   ├── y_train_hamburg.npy      (8,371,) int32 [0-6]
│   ├── X_train_berlin.npy       (8,299 × 184 float32)
│   ├── y_train_berlin.npy       (8,299,) int32 [0-6]
│   ├── X_val_hamburg.npy        (2,129 × 184 float32)
│   ├── y_val_hamburg.npy        (2,129,) int32 [0-6]
│   ├── X_val_berlin.npy         (1,989 × 184 float32)
│   ├── y_val_berlin.npy         (1,989,) int32 [0-6]
│   ├── X_test_rostock_zero_shot.npy (6,675 × 184 float32)
│   ├── y_test_rostock_zero_shot.npy (6,675,) int32 [0-6]
│   └── scaler.pkl               (StandardScaler fitted on Hamburg+Berlin Train)
│
├── experiment_3_finetuning/
│   ├── X_test_rostock_finetune_eval.npy (1,403 × 184 float32)
│   ├── y_test_rostock_finetune_eval.npy (1,403,) int32 [0-6]
│   └── scaler.pkl               (COPY from Experiment 2, NO refitting!)
│
├── feature_names.json           (184 feature names)
└── label_encoder.pkl            (LabelEncoder: Genus→[0-6])
```

### 7.2 File Sizes (Approximate)

```
X_train.npy (8,371 × 184):  ~12 MB (float32 = 4 bytes/value)
y_train.npy (8,371,):       ~33 KB (int32)
scaler.pkl:                 ~10 KB

Total per experiment:
  Hamburg:        ~24 MB
  Berlin:         ~24 MB
  Combined:       ~48 MB
  Rostock:        ~40 MB
────────────────
Overall:        ~136 MB
```

---

## 8. Usage in ML Training

### 8.1 Loading Data in Python

```python
import numpy as np
import pickle

# Load Experiment 2 (Cross-City)
X_train_hh = np.load('experiment_2_cross_city/X_train_hamburg.npy')
y_train_hh = np.load('experiment_2_cross_city/y_train_hamburg.npy')
X_train_be = np.load('experiment_2_cross_city/X_train_berlin.npy')
y_train_be = np.load('experiment_2_cross_city/y_train_berlin.npy')

# Combine training data
X_train = np.vstack([X_train_hh, X_train_be])
y_train = np.hstack([y_train_hh, y_train_be])

# Load validation data
X_val_hh = np.load('experiment_2_cross_city/X_val_hamburg.npy')
y_val_hh = np.load('experiment_2_cross_city/y_val_hamburg.npy')
X_val_be = np.load('experiment_2_cross_city/X_val_berlin.npy')
y_val_be = np.load('experiment_2_cross_city/y_val_berlin.npy')

X_val = np.vstack([X_val_hh, X_val_be])
y_val = np.hstack([y_val_hh, y_val_be])

# Load test data
X_test = np.load('experiment_2_cross_city/X_test_rostock_zero_shot.npy')
y_test = np.load('experiment_2_cross_city/y_test_rostock_zero_shot.npy')

# Load scaler (for reference)
with open('experiment_2_cross_city/scaler.pkl', 'rb') as f:
    scaler = pickle.load(f)

print(f"Train: {X_train.shape[0]} samples, {X_train.shape[1]} features")
print(f"Val: {X_val.shape[0]} samples")
print(f"Test (Rostock Zero-Shot): {X_test.shape[0]} samples")
```

### 8.2 Training Random Forest

```python
from sklearn.ensemble import RandomForestClassifier

# Train
model = RandomForestClassifier(
    n_estimators=200,
    max_depth=25,
    min_samples_split=5,
    random_state=42,
    n_jobs=-1
)
model.fit(X_train, y_train)

# Validate
val_accuracy = model.score(X_val, y_val)
print(f"Validation Accuracy: {val_accuracy:.4f}")

# Test (Zero-Shot)
test_accuracy = model.score(X_test, y_test)
print(f"Rostock Zero-Shot Accuracy: {test_accuracy:.4f}")
```

### 8.3 Training CNN (TensorFlow)

```python
from tensorflow import keras

model = keras.Sequential([
    keras.layers.Dense(256, activation='relu', input_shape=(184,)),
    keras.layers.Dropout(0.3),
    keras.layers.Dense(128, activation='relu'),
    keras.layers.Dropout(0.2),
    keras.layers.Dense(64, activation='relu'),
    keras.layers.Dense(7, activation='softmax')
])

model.compile(
    optimizer='adam',
    loss='sparse_categorical_crossentropy',
    metrics=['accuracy']
)

# Train
model.fit(
    X_train, y_train,
    validation_data=(X_val, y_val),
    epochs=50,
    batch_size=32,
    verbose=1
)

# Test (Zero-Shot)
test_loss, test_accuracy = model.evaluate(X_test, y_test)
print(f"Rostock Zero-Shot Accuracy: {test_accuracy:.4f}")
```

---

## 9. Known Limitations & Issues

### 9.1 Scaler Mismatch Between Cities

**Limitation:** Hamburg/Berlin/Rostock haben unterschiedliche Spektralcharakteristiken

**Impact:**

```
Hamburg Train Scaler fitted on Hamburg data
  → Hamburg Val looks normal (Mean≈0, Std≈1)
  → Berlin Val looks slightly odd (Mean≠0, Std≠1)
  → Rostock Zero-Shot looks very odd (Mean=0.156, Std=1.034)
```

**Issue:**

- Model expects Mean≈0 input (from Hamburg scaler)
- Rostock features sind shifted (Mean=0.156)
- Might slightly hurt generalization

**Workaround:**

- Use city-specific scalers (Hamburg scaler for Hamburg, etc.)
- Or: Robust scaling instead (less sensitive to outliers)
- Or: Whitening (full covariance matrix)

### 9.2 Class Imbalance in Fine-Tuning

**Limitation:** Rostock Fine-Tune hat unbalanced classes

**Impact:**

```
TILIA: 24.0% (dominant)
PRUNUS: 5.6% (minimal)
Ratio: 4.3:1 (not extreme but noticeable)
```

**Issue:**

- Fine-tuning model may overfit to TILIA
- Minority classes (PRUNUS, SORBUS) underlearned

**Workaround:**

- Use class weights (weight_dict = {0: 1.0, ..., 3: 4.3, ...})
- Or: Resample fine-tune data to balance
- Or: Use stratified sampling in fine-tuning

### 9.3 Rostock Distribution Shift

**Limitation:** Rostock hat fundamentally andere Genus-Distribution

**Impact:**

```
Hamburg+Berlin (40,118 samples):
  TILIA: 15-16%

Rostock Zero-Shot (6,675 samples):
  TILIA: 17.4% (similar)

But:
  FRAXINUS: 13.8-14.9% (Hamburg/Berlin) vs. 10.9% (Rostock)
  PRUNUS: 14.3-15.9% (Hamburg/Berlin) vs. 8.2% (Rostock)
```

**Issue:**

- Rostock naturally has fewer FRAXINUS/PRUNUS
- Model trained on Hamburg/Berlin balance may underpredict these classes
- Higher error rate for minority genera in Rostock

**Workaround:**

- Train with class weights
- Or: Use stratified evaluation (per-class metrics)
- Or: Fine-tune on Rostock-specific balance

---

## 10. Nächste Schritte

1. ✅ **Feature Loading & Extraction (Phase 2.1)** - DONE
2. ✅ **Feature Validation & QC (Phase 2.2)** - DONE
3. ✅ **Dataset Balancing (Phase 2.3)** - DONE
4. ✅ **Spatial Block Split (Phase 2.4)** - DONE
5. ✅ **Feature Normalization & Model-Ready Export (Phase 2.5)** - DONE
6. 🔄 **Model Training & Evaluation** - TODO (Phase 3)

---

## 11. Referenzen

### Normalisierung & Skalierung

- Sklearn StandardScaler: Normalisierung mit Z-Score
- Robust Scaler: Resistenter gegen Outliers
- Min-Max Scaling: Normalisierung zu [0, 1]

### Label Encoding

- LabelEncoder: Convert categorical labels to integers
- One-Hot Encoding: Alternative für kategorische Features

### Data Leakage

- Leite, D. A., et al. (2018). "Data Leakage in Machine Learning"
- Train/Val/Test splits: Never fit scaler/encoder on combined data!

---

## 12. Changelog

| Datum      | Änderung                                                     |
| ---------- | ------------------------------------------------------------ |
| 2026-01-06 | Initial: Feature Normalization & Model-Ready Export Methodik |

---

**Dokument-Status:** ✅ Aktualisiert - Alle Notebook-Outputs integriert  
**Letzte Aktualisierung:** 6. Januar 2026
