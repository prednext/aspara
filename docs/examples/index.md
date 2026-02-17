# Examples

This section provides framework-specific examples showing how to integrate Aspara with popular machine learning libraries.

## Available Examples

### [PyTorch](pytorch_example.md)

Learn how to track PyTorch training with Aspara using the MNIST dataset. This example covers:

- Setting up data loaders and model architecture
- Initializing Aspara with config parameters
- Logging training and test metrics per epoch
- Basic training loop integration

### [TensorFlow / Keras](tensorflow_example.md)

Learn how to integrate Aspara with TensorFlow/Keras using Fashion MNIST. This example covers:

- Creating a custom Keras callback for Aspara
- Automatic metric logging during training
- Recording final test results
- Minimal code changes for integration

### [scikit-learn](sklearn_example.md)

Learn how to track scikit-learn model training and hyperparameter tuning with Aspara using the Iris dataset. This example covers:

- Grid search hyperparameter optimization tracking
- Recording each parameter combination's results
- Logging evaluation metrics (accuracy, precision, recall, F1)
- Feature importance analysis
