# TensorFlow Example

This page demonstrates how to track a Fashion MNIST classification model with TensorFlow/Keras using Aspara.

## Complete Code Example

Below is a complete example using TensorFlow/Keras and Aspara.

```python
import tensorflow as tf
from tensorflow import keras
import aspara

# Define Aspara callback
class AsparaCallback(keras.callbacks.Callback):
    def on_epoch_end(self, epoch, logs=None):
        # Log metrics at the end of each epoch
        if logs:
            aspara.log(logs, step=epoch)

# Hyperparameters
batch_size = 32
epochs = 5

# Load Fashion MNIST dataset
fashion_mnist = keras.datasets.fashion_mnist
(train_images, train_labels), (test_images, test_labels) = fashion_mnist.load_data()

# Data preprocessing
train_images = train_images / 255.0
test_images = test_images / 255.0

# Class names
class_names = ['T-shirt/top', 'Trouser', 'Pullover', 'Dress', 'Coat',
               'Sandal', 'Shirt', 'Sneaker', 'Bag', 'Ankle boot']

# Build the model
model = keras.Sequential([
    keras.layers.Flatten(input_shape=(28, 28)),
    keras.layers.Dense(128, activation='relu'),
    keras.layers.Dropout(0.2),
    keras.layers.Dense(10)
])

# Compile the model
model.compile(
    optimizer=keras.optimizers.Adam(learning_rate=0.001),
    loss=keras.losses.SparseCategoricalCrossentropy(from_logits=True),
    metrics=['accuracy']
)

# Initialize run with Aspara
aspara.init(
    project="deep_learning_examples",
    name="fashion_mnist_tf",
    config={
        "model_type": "Sequential",
        "batch_size": batch_size,
        "epochs": epochs,
        "dataset": "Fashion MNIST",
        "classes": class_names
    }
)

# Instantiate Aspara callback
aspara_callback = AsparaCallback()

# Train the model
history = model.fit(
    train_images, train_labels,
    batch_size=batch_size,
    epochs=epochs,
    validation_split=0.1,
    callbacks=[aspara_callback]
)

# Evaluate on test data
test_loss, test_acc = model.evaluate(test_images, test_labels, verbose=2)

# Log final test results
aspara.log({
    "final_test_loss": test_loss,
    "final_test_accuracy": test_acc
})

# Finish the run
aspara.finish()

print(f'Test accuracy: {test_acc:.4f}')
```

## Code Explanation

This code performs the following:

1. **Creating a Custom Callback**:
   - Extend Keras callback to integrate with Aspara
   - Log metrics with `aspara.log()` at the end of each epoch

2. **Data Preparation**:
   - Load Fashion MNIST dataset
   - Normalize image data (to 0-1 range)

3. **Model Definition**:
   - Define a simple fully-connected neural network
   - Input layer (28x28=784 nodes), hidden layer (128 nodes), dropout layer, output layer (10 nodes)

4. **Tracking with Aspara**:
   - Initialize run with `aspara.init()` and record hyperparameters with `config` parameter
   - Automatically record training metrics through the callback
   - Record final test results with `aspara.log()`

5. **Model Training and Evaluation**:
   - Automatically record metrics during training using the callback
   - Also record final evaluation results on test data
   - Finish the run with `aspara.finish()`

The advantage of this approach is that you can integrate Aspara with minimal code changes by leveraging Keras' callback system.

## Alternative: Using Context Manager

You can also use the context manager pattern for automatic cleanup:

```python
with aspara.init(
    project="deep_learning_examples",
    name="fashion_mnist_tf",
    config={...}
) as run:
    history = model.fit(
        train_images, train_labels,
        callbacks=[aspara_callback]
    )
    test_loss, test_acc = model.evaluate(test_images, test_labels)
    aspara.log({"final_test_loss": test_loss, "final_test_accuracy": test_acc})
# finish() called automatically
```

The context manager ensures `finish()` is called even if an exception occurs during training.
