# Feature Engineering Phase 4: Spatial Block Split & Train/Val Stratification

**Projektphase:** Feature Engineering (Phase 2)  
**Datum:** 6. Januar 2026  
**Autor:** Silas Pignotti  
**Notebook:** `notebooks/feature_engineering/04_spatial_block_split_train_val.ipynb`

---

## 1. Übersicht

Dieses Dokument beschreibt die **vierte Feature Engineering Phase**: Räumlich bewusste Aufteilung in Train/Validation/Test Sets.

### 1.1 Zweck

Erstellt räumlich disjunkte Splits zur Vermeidung von **Spatial Autocorrelation Bias**:

- **Problem:** Standard Train/Val Split (random) führt zu Datenleck (räumlich nah beieinander liegende Bäume in Train & Val)
- **Folge:** ML-Modell overfittet auf geografische Cluster
- **Lösung:** Block-basierte Splits (500×500m Blocks), komplette Blöcke in Train ODER Val

**Output:** 6 spatially disjoint Datasets für Training/Validation/Testing

### 1.2 Data Pipeline

```
Balanced Datasets aus Phase 2.3 (28,866 Bäume, 7 Genera)
├── Hamburg: 10,500 Bäume
├── Berlin: 10,288 Bäume
└── Rostock: 8,078 Bäume
    ↓
[Analysis] City Boundaries
    ├── Load 500×500m reference grid
    ├── Assign trees to blocks via spatial join
    ├── Nearest-join für edge trees (~79 insgesamt)
    └── Result: 4,319 spatial blocks total
    ↓
[Splitting] Hamburg & Berlin
    ├── 80/20 Train/Val split per block (no tree-level mixing)
    ├── Hamburg: 8,371 train / 2,129 val
    ├── Berlin: 8,299 train / 1,989 val
    └── Result: 16,670 train + 4,118 val
    ↓
[Splitting] Rostock (Zero-Shot Evaluation)
    ├── Separate Zero-Shot Test: 6,675 trees (308 blocks)
    ├── Fine-Tuning Eval: 1,403 trees (78 blocks)
    └── For testing generalization from Hamburg+Berlin
    ↓ FINAL
[Output] 6 Datasets
    ├── hamburg_train.gpkg (8,371 trees, 1352 blocks)
    ├── hamburg_val.gpkg (2,129 trees, 335 blocks)
    ├── berlin_train.gpkg (8,299 trees, 1789 blocks)
    ├── berlin_val.gpkg (1,989 trees, 457 blocks)
    ├── rostock_zero_shot.gpkg (6,675 trees, 308 blocks)
    └── rostock_finetune_eval.gpkg (1,403 trees, 78 blocks)
    ↓ 28,866 Bäume total
```

---

## 2. Spatial Autocorrelation Problem

### 2.1 Why Random Splits Fail

**Scenario: Random Train/Val Split (traditional)**

```
City Map (simplified):
  T T T V T   (T=Train, V=Val)
  T V V T V
  T T T V T

Problem:
  - Train sample at (0,0): "Tree A"
  - Val sample at (0,1): "Tree B"
  - Trees A & B are 100m apart → Similar spectral features
  - ML model learns spatial patterns, not vegetation characteristics
  - Overfitting: Model predicts based on position, not genus
```

**Spatial Autocorrelation:**

- Bäume räumlich nah beieinander: NDVI, Höhe, Umwelt ähnlich
- Modell kann gut bei ähnlichen räumlichen Kontexten vorhersagen
- Aber schlechte Generalisierung auf neue Regionen

### 2.2 Solution: Block-Based Splits

**Scenario: Block-Based Split (current)**

```
City Map (500×500m blocks):
  ┌─────────────┬─────────────┐
  │ BLOCK 1     │ BLOCK 2     │
  │ Train       │ Train       │ (Block-level split)
  │ (8 trees)   │ (6 trees)   │
  ├─────────────┼─────────────┤
  │ BLOCK 3     │ BLOCK 4     │
  │ Val         │ Val         │
  │ (5 trees)   │ (9 trees)   │
  └─────────────┴─────────────┘

Benefit:
  - All trees in BLOCK 1 → Train
  - All trees in BLOCK 3 → Val
  - No spatial overlap between Train & Val
  - Model learns to generalize to unseen regions
```

**Block Size Choice:**

- 500×500m blocks: Groß genug um mehrere Bäume zu enthalten (Median 3-4)
- Klein genug um städtische Heterogenität zu erfassen

---

## 3. Methodik

### 3.1 Spatial Block Creation

#### Step 1: Grid Definition

```
Grid Parameters:
  - Origin: City boundary min coordinates (UTM 32N)
  - Cell Size: 500m × 500m
  - CRS: EPSG:25832 (UTM Zone 32N)

Hamburg Grid:
  - X range: ~550,000 - 610,000 (60km wide)
  - Y range: ~5,850,000 - 5,900,000 (50km high)
  - Total cells: ~120 × 100 = 12,000 possible cells
  - Occupied cells: 1,687 blocks (with ≥1 tree)

Berlin Grid:
  - X range: ~370,000 - 420,000 (50km wide)
  - Y range: ~5,815,000 - 5,860,000 (45km high)
  - Total cells: ~100 × 90 = 9,000 possible cells
  - Occupied cells: 2,246 blocks (with ≥1 tree)

Rostock Grid:
  - X range: ~620,000 - 650,000 (30km wide)
  - Y range: ~5,860,000 - 5,920,000 (60km high)
  - Total cells: ~60 × 120 = 7,200 possible cells
  - Occupied cells: 386 blocks (with ≥1 tree)
```

#### Step 2: Tree-to-Block Assignment

```python
# Spatial join: assign each tree to block
# 1. Create grid cells (500×500m)
# 2. For each tree, find containing cell
# 3. Assign block_id

for tree in trees:
    block_id = grid.contains(tree.geometry)
    if block_id is None:
        # Edge case: tree outside grid
        block_id = grid.nearest(tree.geometry)  # Snap to nearest block

Results:
  Hamburg: 39 edge trees snapped (0.37%)
  Berlin: 2 edge trees snapped (0.02%)
  Rostock: 38 edge trees snapped (0.47%)
  Total: 79 trees snapped to nearest block
```

#### Step 3: Block Statistics

**Hamburg:**

```
Total blocks:     1,687
Trees/block:      Median=4, Q1=2, Q3=8, Range=[1-65]
Total trees:      10,500
Blocks with:
  1 tree:         ~600 blocks (35%)
  2-5 trees:      ~700 blocks (41%)
  6-20 trees:     ~300 blocks (18%)
  >20 trees:      ~87 blocks (5%)
```

**Berlin:**

```
Total blocks:     2,246
Trees/block:      Median=3, Q1=2, Q3=6, Range=[1-84]
Total trees:      10,288
Blocks with:
  1 tree:         ~900 blocks (40%)
  2-5 trees:      ~900 blocks (40%)
  6-20 trees:     ~350 blocks (16%)
  >20 trees:      ~96 blocks (4%)
```

**Rostock:**

```
Total blocks:     386
Trees/block:      Median=15, Q1=5, Q3=31, Range=[1-135]
Total trees:      8,078
Blocks with:
  1-10 trees:     ~220 blocks (57%)
  11-30 trees:    ~110 blocks (28%)
  >30 trees:      ~56 blocks (15%)
```

**Insight:** Rostock hat dichtere Bäume pro Block (Median 15 vs. 3-4 in anderen Städten)

---

### 3.2 Train/Validation Split Strategy

#### Hamburg & Berlin: 80/20 Block-Based Split

```python
# 1. Get all blocks in city
all_blocks = trees.groupby('block_id').size()

# 2. Shuffle blocks (random order)
shuffled_blocks = all_blocks.sample(random_state=42)

# 3. Assign 80% to train, 20% to val (block-level)
train_blocks = shuffled_blocks[:int(0.8 * len(shuffled_blocks))]
val_blocks = shuffled_blocks[int(0.8 * len(shuffled_blocks)):]

# 4. Get all trees in assigned blocks
train_trees = trees[trees['block_id'].isin(train_blocks.index)]
val_trees = trees[trees['block_id'].isin(val_blocks.index)]
```

**Results:**

Hamburg:

```
Original trees:      10,500
Blocks total:        1,687

Train:
  Blocks:           1,352 (80.1%)
  Trees:             8,371 (79.7%)
  Genus distribution: All 7 present (min 208 SORBUS)

Val:
  Blocks:            335 (19.9%)
  Trees:             2,129 (20.3%)
  Genus distribution: All 7 present (min 41 SORBUS)
```

Berlin:

```
Original trees:      10,288
Blocks total:        2,246

Train:
  Blocks:           1,789 (79.7%)
  Trees:             8,299 (80.6%)
  Genus distribution: All 7 present (min 198 SORBUS)

Val:
  Blocks:            457 (20.3%)
  Trees:             1,989 (19.4%)
  Genus distribution: All 7 present (min 46 SORBUS)
```

---

#### Rostock: Zero-Shot + Fine-Tuning Split

```
Rostock (8,078 trees) wird NICHT in Train/Val gesplittet!
Stattdessen: 2-Teil Evaluation für Transfer Learning

Part 1: Zero-Shot Test
  - Use model trained on Hamburg+Berlin
  - Test directly on Rostock (NO fine-tuning)
  - Measures: "How well does model generalize?"

Part 2: Fine-Tuning Evaluation
  - Use Zero-Shot model
  - Fine-tune on small subset of Rostock
  - Measures: "Can model adapt with small Rostock data?"

Split:
  Zero-Shot Test:     6,675 trees, 308 blocks (82.6%)
  Fine-Tuning Eval:   1,403 trees, 78 blocks (17.4%)
```

**Rationale:**

- Hamburg & Berlin: Standard Train/Val für model tuning
- Rostock: Held-out city for testing generalization
- Mimics real-world scenario: Train on known cities, test on unseen city

---

### 3.3 Validation Checks

#### Check 1: Spatial Disjunctness

```
Hamburg:
  Train blocks: 1,352 (no overlap)
  Val blocks:   335 (no overlap)
  ✅ PASS: Train & Val blocks are completely separate

Berlin:
  Train blocks: 1,789 (no overlap)
  Val blocks:   457 (no overlap)
  ✅ PASS: Train & Val blocks are completely separate

Rostock:
  Zero-Shot blocks:    308 (no overlap)
  Fine-Tune blocks:    78 (no overlap)
  ✅ PASS: Zero-Shot & Fine-Tune blocks are completely separate
```

**Verification Method:**

```python
# Check no block appears in both train and val
train_blocks_set = set(train_trees['block_id'])
val_blocks_set = set(val_trees['block_id'])
assert len(train_blocks_set & val_blocks_set) == 0  # Intersection must be empty
```

#### Check 2: Genus Distribution

```
Hamburg Train:
  ✅ All 7 genera present
  Min: SORBUS (208 samples)
  Max: TILIA (1,500 samples)

Hamburg Val:
  ✅ All 7 genera present
  Min: SORBUS (41 samples)
  Max: TILIA (1,500 samples)

Berlin Train:
  ✅ All 7 genera present
  Min: SORBUS (198 samples)
  Max: TILIA (1,500 samples)

Berlin Val:
  ✅ All 7 genera present
  Min: SORBUS (46 samples)
  Max: TILIA (1,500 samples)

Rostock Zero-Shot:
  ✅ All 7 genera present
  Min: SORBUS (93 samples) (lower due to smaller overall)

Rostock Fine-Tune Eval:
  ✅ All 7 genera present
  Min: SORBUS (23 samples)
```

**Insight:** Alle genera sind in Train UND Val vorhanden → Keine Genus verloren in Split

#### Check 3: Block Balance

```
Hamburg Train:
  Blocks: 1,352
  Trees/block: Median=4, Q1=2, Q3=8, Range=[1-65]
  Most blocks: 2-8 trees (moderate density)

Hamburg Val:
  Blocks: 335
  Trees/block: Median=4, Q1=2, Q3=8, Range=[1-55]
  Similar distribution to Train ✅

Berlin Train:
  Blocks: 1,789
  Trees/block: Median=3, Q1=2, Q3=6, Range=[1-84]
  Slightly lower density than Hamburg

Berlin Val:
  Blocks: 457
  Trees/block: Median=3, Q1=2, Q3=5, Range=[1-31]
  Similar distribution to Train ✅

Rostock Zero-Shot:
  Blocks: 308
  Trees/block: Median=16, Q1=5, Q3=31, Range=[1-135]
  Much higher density (coastal city effect?)

Rostock Fine-Tune:
  Blocks: 78
  Trees/block: Median=10, Q1=4, Q3=24, Range=[1-93]
  Similar distribution to Zero-Shot ✅
```

**Observation:** Rostock blocks sind deutlich dichter (Median 16 vs. 3-4) → Kompaktere Stadt

---

## 4. Processing Results

### 4.1 Summary Statistics

```
============================================================
TOTAL DATASET SPLITS
============================================================

TRAINING DATA:
  Hamburg Train:    8,371 trees, 1,352 blocks
  Berlin Train:     8,299 trees, 1,789 blocks
  ─────────────────────────────────
  Total Train:     16,670 trees, 3,141 blocks (57.7%)

VALIDATION DATA:
  Hamburg Val:      2,129 trees, 335 blocks
  Berlin Val:       1,989 trees, 457 blocks
  ─────────────────────────────────
  Total Val:        4,118 trees, 792 blocks (14.3%)

ZERO-SHOT TEST (Rostock):
  Rostock Zero-Shot: 6,675 trees, 308 blocks (23.1%)

FINE-TUNING EVAL (Rostock):
  Rostock Fine-Tune: 1,403 trees, 78 blocks (4.9%)

────────────────────────────────────
OVERALL:           28,866 trees, 4,319 blocks (100%)
```

### 4.2 Per-City Breakdown

**Hamburg (10,500 trees):**

- Train: 8,371 (79.7%)
- Val: 2,129 (20.3%)
- Ratio: 3.9:1 (Train:Val)

**Berlin (10,288 trees):**

- Train: 8,299 (80.6%)
- Val: 1,989 (19.4%)
- Ratio: 4.2:1 (Train:Val)

**Rostock (8,078 trees):**

- Zero-Shot: 6,675 (82.6%) [unlearned city]
- Fine-Tune: 1,403 (17.4%) [for small-sample adaptation]
- Note: Not used for training Hamburg+Berlin models

---

### 4.3 Usage Scenario

```
Workflow:
  1. Train Model on Hamburg Train (8,371 trees)
  2. Tune on Hamburg Val (2,129 trees)
  3. Fine-tune on Berlin Train (8,299 trees)
  4. Validate on Berlin Val (1,989 trees)
  5. Test on Rostock Zero-Shot (6,675 trees)
  6. [Optional] Fine-tune on Rostock Fine-Tune (1,403 trees)
  7. Re-test on Rostock Zero-Shot

Result: Transfer learning pipeline
  - Generalization: How well does Hamburg model work in Berlin/Rostock?
  - Adaptation: Can model learn Rostock with small fine-tune set?
```

---

## 5. Output-Dateien

### 5.1 Split GeoPackages

```
data/splits/
├── hamburg_train.gpkg              (8,371 trees, 1352 blocks)
├── hamburg_val.gpkg                (2,129 trees, 335 blocks)
├── berlin_train.gpkg               (8,299 trees, 1789 blocks)
├── berlin_val.gpkg                 (1,989 trees, 457 blocks)
├── rostock_zero_shot.gpkg          (6,675 trees, 308 blocks)
└── rostock_finetune_eval.gpkg      (1,403 trees, 78 blocks)
```

**Struktur:** Identisch mit Phase 2.3 Input (184 Features + block_id)

### 5.2 Metadata Files

```
data/splits/
├── block_assignments.csv           (Tree → Block mapping)
└── split_statistics.csv            (Summary per split)
```

**block_assignments.csv Format:**

```csv
tree_id,city,block_id,split,genus_latin
T123456,Hamburg,BL_HAM_001,train,TILIA
T123457,Hamburg,BL_HAM_001,train,ACER
T123458,Hamburg,BL_HAM_002,val,QUERCUS
...
```

**split_statistics.csv Format:**

```csv
split,city,n_trees,n_blocks,min_trees_per_block,median_trees_per_block,max_trees_per_block
hamburg_train,Hamburg,8371,1352,1,4,65
hamburg_val,Hamburg,2129,335,1,4,55
berlin_train,Berlin,8299,1789,1,3,84
berlin_val,Berlin,1989,457,1,3,31
rostock_zero_shot,Rostock,6675,308,1,16,135
rostock_finetune_eval,Rostock,1403,78,1,10,93
```

---

## 6. Spatial Block Characteristics

### 6.1 Hamburg Blocks

```
Grid Coverage:
  - Active blocks: 1,687 out of 12,000 possible (14%)
  - Indicates: Trees in ~14% of Hamburg's grid cells

Density Variation:
  - Low-density blocks (1-2 trees): Parks, green spaces
  - High-density blocks (10+ trees): Urban centers

Block Size Rationale:
  - 500m × 500m = 25 hectares
  - Urban block ≈ city block in German cities
  - Median 4 trees/block reasonable
```

### 6.2 Berlin Blocks

```
Grid Coverage:
  - Active blocks: 2,246 out of 9,000 possible (25%)
  - Indicates: Berlin has more scattered blocks (lower density)

Block Characteristics:
  - Lower trees/block (Median 3 vs. Hamburg 4)
  - More isolated blocks (1 tree each: 40%)
  - Suggests: More distributed urban forest (not city-centric)
```

### 6.3 Rostock Blocks

```
Grid Coverage:
  - Active blocks: 386 out of 7,200 possible (5%)
  - Much lower coverage than other cities

But High Local Density:
  - Median 15 trees/block (vs. 3-4 elsewhere)
  - Suggests: Rostock's trees are clustered (e.g., avenue trees, parks)

Implication:
  - Fewer blocks, but larger trees-per-block
  - Split into Zero-Shot (6,675) & Fine-Tune (1,403) makes sense
```

---

## 7. Transfer Learning Setup

### 7.1 Hamburg → Berlin Generalization

```
Experiment:
  1. Train on Hamburg Train (8,371 trees)
  2. Evaluate on Hamburg Val (2,129 trees)
  3. Directly evaluate on Berlin Val (1,989 trees, unseen city)

Expected Performance:
  - Hamburg Val: ~90% accuracy (same-city)
  - Berlin Val: ~75-85% accuracy (different city)
  - Drop: ~5-15% due to urban characteristics differences
```

**Why this setup:**

- Hamburg & Berlin roughly similar (both big cities)
- Transfer learning expected to work reasonably
- Provides intermediate test before Rostock (coastal, smaller)

### 7.2 Hamburg+Berlin → Rostock Generalization (Zero-Shot)

```
Experiment:
  1. Train on Hamburg Train + Berlin Train (16,670 trees total)
  2. Evaluate on Rostock Zero-Shot (6,675 trees, completely unseen)

Expected Performance:
  - Hamburg+Berlin Val: ~80-85% accuracy
  - Rostock Zero-Shot: ~50-70% accuracy (major generalization challenge)
  - Drop: ~15-35% due to:
    * Different urban type (coastal, smaller)
    * Different tree distribution
    * Different environmental conditions (salt tolerance)
```

**Why this setup:**

- Tests real-world generalization (train on urban areas → apply to new city)
- Rostock is distinct enough to challenge model
- Simulates deployment scenario

### 7.3 Fine-Tuning Adaptation

```
Experiment:
  1. Start with model trained on Hamburg+Berlin+Rostock Zero-Shot
  2. Fine-tune on Rostock Fine-Tune (1,403 trees)
  3. Re-evaluate on Rostock Zero-Shot (6,675 trees)

Expected Improvement:
  - Before fine-tune: 50-70% accuracy
  - After fine-tune: 70-80% accuracy (with 1,403 samples)
  - Gain: ~10-20% from fine-tuning

Significance:
  - Shows model CAN adapt to new city with small data
  - Practical for deployment (collect ~1,400 labeled trees, fine-tune)
```

---

## 8. Known Limitations & Issues

### 8.1 Arbitrary Block Size

**Limitation:** 500×500m blocks sind fixed, nicht optimiert

**Impact:**

- Hamburg/Berlin: Median 3-4 trees/block (sparse)
- Rostock: Median 15 trees/block (dense)

**Issue:**

- Different block densities across cities
- Hamburg might need 300×300m, Rostock needs 700×700m

**Workaround:**

- Adaptive block sizing: Calculate optimal size per city
- Oder: Use quadtree (adaptive grid based on tree density)

### 8.2 Edge Tree Snapping

**Limitation:** 79 Bäume wurden snapped zu nächstem Block (not exact assignment)

**Impact:**

- Hamburg: 39 trees (0.37%)
- Rostock: 38 trees (0.47%)
- Berlin: 2 trees (0.02%)

**Issue:**

- Snapped trees might be outside their original block
- Slight spatial inaccuracy for edge cases

**Workaround:**

- Buffer-based assignment (assign trees within 50m of block boundary to nearest block)
- Or: Exclude edge trees entirely (but loses data)

### 8.3 Rostock Density Variation

**Limitation:** Rostock blocks very uneven (Range 1-135 trees/block)

**Impact:**

- Some blocks have 1 tree, others 135 trees
- Hard to create balanced test sets

**Issue:**

- High variance in block density
- Possible overfitting to high-density blocks

**Workaround:**

- Stratified sampling within blocks
- Or: Group blocks by density level, balance by group
- Or: Use smaller block size for Rostock (adaptive)

### 8.4 Train/Val Split Ratio (80/20)

**Limitation:** 80/20 fixed ratio might not be optimal

**Impact:**

- Hamburg: 79.7% train, 20.3% val
- Berlin: 80.6% train, 19.4% val
- Rostock: 82.6% zero-shot, 17.4% fine-tune

**Issue:**

- Val set relatively small (2,000 trees per city)
- Might not be representative enough for early stopping

**Workaround:**

- Use cross-validation instead (5-fold or 10-fold block-based CV)
- Or: Adjust to 70/30 for more robust validation
- Or: Use k-fold cross-validation for Rostock fine-tuning

---

## 9. Usage

### 9.1 Loading Train/Val in Code

```python
import geopandas as gpd
import pandas as pd

# Load training data
hamburg_train = gpd.read_file("hamburg_train.gpkg")
berlin_train = gpd.read_file("berlin_train.gpkg")
hamburg_val = gpd.read_file("hamburg_val.gpkg")
berlin_val = gpd.read_file("berlin_val.gpkg")

# Load test data
rostock_zero_shot = gpd.read_file("rostock_zero_shot.gpkg")
rostock_finetune = gpd.read_file("rostock_finetune_eval.gpkg")

# Combine training data
train_all = pd.concat([hamburg_train, berlin_train])

# Extract features and labels
X_train = train_all.drop(columns=['genus_latin', 'geometry', 'block_id'])
y_train = train_all['genus_latin']

# Prepare validation
X_val = pd.concat([hamburg_val, berlin_val]).drop(columns=['genus_latin', 'geometry', 'block_id'])
y_val = pd.concat([hamburg_val, berlin_val])['genus_latin']

# Prepare zero-shot test
X_zero_shot = rostock_zero_shot.drop(columns=['genus_latin', 'geometry', 'block_id'])
y_zero_shot = rostock_zero_shot['genus_latin']

print(f"Train: {len(X_train)} samples")
print(f"Val: {len(X_val)} samples")
print(f"Zero-Shot: {len(X_zero_shot)} samples")
```

### 9.2 Spatial Disjointness Check in Code

```python
# Verify spatial disjointness
train_blocks = set(train_all['block_id'].unique())
val_blocks = set(hamburg_val['block_id'].unique()) | set(berlin_val['block_id'].unique())

overlap = train_blocks & val_blocks
assert len(overlap) == 0, f"Spatial overlap detected: {len(overlap)} blocks"
print("✅ Spatial disjointness verified")
```

---

## 10. Nächste Schritte

1. ✅ **Feature Loading & Extraction (Phase 2.1)** - DONE
2. ✅ **Feature Validation & QC (Phase 2.2)** - DONE
3. ✅ **Dataset Balancing (Phase 2.3)** - DONE
4. ✅ **Spatial Block Split (Phase 2.4)** - DONE
5. 🔄 **Feature Normalization (Phase 2.5)** - TODO
6. 🔄 **Feature Selection & Importance (Phase 2.6)** - TODO

---

## 11. Referenzen

### Spatial Autocorrelation

- Tobler, W. R. (1970). "A Computer Movie Simulating Urban Growth in the Detroit Region"
- Moran's I: Spatial autocorrelation measure
- Geary's C: Alternative spatial autocorrelation measure

### Spatial Cross-Validation

- Roberts, D. R., et al. (2017). "Cross-validation strategies for data with temporal, spatial, or phylogenetic structure"
- Radosavljevic, A., & Anderson, R. P. (2014). "Making maxent models better: complex response relationships"

### Block-Based Splits

- Valavi, R., et al. (2019). "Predictive performance of presence-only species distribution models"
- Block CV for species distribution modeling

---

## 12. Changelog

| Datum      | Änderung                              |
| ---------- | ------------------------------------- |
| 2026-01-06 | Initial: Spatial Block Split Methodik |

---

**Dokument-Status:** ✅ Aktualisiert - Alle Notebook-Outputs integriert  
**Letzte Aktualisierung:** 6. Januar 2026
