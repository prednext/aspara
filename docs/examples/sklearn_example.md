# scikit-learn Example

This page demonstrates how to track machine learning model training with scikit-learn using Aspara.

## Complete Code Example

Below is a complete example using scikit-learn and Aspara.

```python
import numpy as np
from sklearn.datasets import load_iris
from sklearn.model_selection import train_test_split, GridSearchCV
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, confusion_matrix
import aspara

# Load data
iris = load_iris()
X = iris.data
y = iris.target
feature_names = iris.feature_names
target_names = iris.target_names

# Split data
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.3, random_state=42
)

# Grid search parameters
param_grid = {
    'n_estimators': [10, 50, 100],
    'max_depth': [None, 10, 20],
    'min_samples_split': [2, 5, 10]
}

# Initialize run with Aspara
aspara.init(
    project="ml_examples",
    name="iris_classification",
    config={
        "dataset": "Iris",
        "n_samples": X.shape[0],
        "n_features": X.shape[1],
        "feature_names": feature_names,
        "target_names": target_names,
        "test_size": 0.3,
        "random_state": 42,
        "train_samples": X_train.shape[0],
        "test_samples": X_test.shape[0],
        "param_grid": param_grid
    }
)

# Run grid search
rf = RandomForestClassifier(random_state=42)
grid_search = GridSearchCV(
    rf, param_grid, cv=5, scoring='accuracy', return_train_score=True
)
grid_search.fit(X_train, y_train)

# Log each grid search result
for i, (params, mean_test_score, mean_train_score) in enumerate(zip(
        grid_search.cv_results_['params'],
        grid_search.cv_results_['mean_test_score'],
        grid_search.cv_results_['mean_train_score'])):

    aspara.log({
        "mean_test_score": mean_test_score,
        "mean_train_score": mean_train_score,
        **{f"param_{k}": v for k, v in params.items()}
    }, step=i)

# Log best parameters
aspara.log({
    "best_params": str(grid_search.best_params_)
})

# Predict with best model
best_model = grid_search.best_estimator_
y_pred = best_model.predict(X_test)

# Calculate evaluation metrics
accuracy = accuracy_score(y_test, y_pred)
precision = precision_score(y_test, y_pred, average='macro')
recall = recall_score(y_test, y_pred, average='macro')
f1 = f1_score(y_test, y_pred, average='macro')
conf_matrix = confusion_matrix(y_test, y_pred)

# Log final evaluation metrics
aspara.log({
    "test_accuracy": accuracy,
    "test_precision": precision,
    "test_recall": recall,
    "test_f1": f1
})

# Log feature importances
feature_importances = best_model.feature_importances_
importance_dict = {name: importance for name, importance in zip(feature_names, feature_importances)}

aspara.log({
    "feature_importances": importance_dict
})

# Finish the run
aspara.finish()

print(f"Best parameters: {grid_search.best_params_}")
print(f"Test accuracy: {accuracy:.4f}")
print(f"Feature importances:")
for name, importance in importance_dict.items():
    print(f"  {name}: {importance:.4f}")
```

## Code Explanation

This code performs the following:

1. **Data Preparation**:
   - Load Iris dataset
   - Split into training and test sets

2. **Tracking with Aspara**:
   - Initialize run with `aspara.init()`
   - Record dataset information and grid search parameters in `config`

3. **Hyperparameter Optimization with Grid Search**:
   - Define hyperparameter grid for RandomForestClassifier
   - Execute grid search with 5-fold cross-validation
   - Log results for each parameter combination with `aspara.log()`

4. **Evaluating the Best Model**:
   - Predict on test data using the best model found by grid search
   - Calculate evaluation metrics: accuracy, precision, recall, F1 score
   - Log evaluation metrics with `aspara.log()`

5. **Feature Importance Analysis**:
   - Get feature importances from RandomForest
   - Log mapping of feature names and importances with `aspara.log()`
   - Finish the run with `aspara.finish()`

This sample demonstrates how to track the entire model selection process and analyze the best model's performance and feature importances.

In particular, by tracking each step of the grid search, you can later analyze how different hyperparameters affect model performance.

## Alternative: Using Context Manager

You can also use the context manager pattern for automatic cleanup:

```python
with aspara.init(
    project="ml_examples",
    name="iris_classification",
    config={...}
) as run:
    # Grid search and logging code...
    pass
# finish() called automatically
```

The context manager ensures `finish()` is called even if an exception occurs during training.
