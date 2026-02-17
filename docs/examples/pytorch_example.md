# PyTorch Example

This page demonstrates how to track an image classification model training on the MNIST dataset with PyTorch using Aspara.

## Complete Code Example

Below is a complete example using PyTorch and Aspara.

```python
import torch
from torch import nn, optim
from torch.utils.data import DataLoader
from torchvision import datasets, transforms
import aspara

# Device configuration
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# Hyperparameters
batch_size = 64
learning_rate = 0.01
epochs = 5
hidden_size = 128

# Data loader configuration
transform = transforms.Compose([
    transforms.ToTensor(),
    transforms.Normalize((0.1307,), (0.3081,))
])

train_dataset = datasets.MNIST('./data', train=True, download=True, transform=transform)
test_dataset = datasets.MNIST('./data', train=False, transform=transform)

train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
test_loader = DataLoader(test_dataset, batch_size=batch_size)

# Model definition
class SimpleNN(nn.Module):
    def __init__(self, hidden_size):
        super(SimpleNN, self).__init__()
        self.flatten = nn.Flatten()
        self.fc1 = nn.Linear(28*28, hidden_size)
        self.relu = nn.ReLU()
        self.fc2 = nn.Linear(hidden_size, 10)

    def forward(self, x):
        x = self.flatten(x)
        x = self.fc1(x)
        x = self.relu(x)
        x = self.fc2(x)
        return x

model = SimpleNN(hidden_size).to(device)

# Loss function and optimizer
criterion = nn.CrossEntropyLoss()
optimizer = optim.SGD(model.parameters(), lr=learning_rate)

# Initialize run with Aspara
aspara.init(
    project="deep_learning_examples",
    name="mnist_pytorch",
    config={
        "model_type": "SimpleNN",
        "hidden_size": hidden_size,
        "batch_size": batch_size,
        "learning_rate": learning_rate,
        "epochs": epochs,
        "optimizer": "SGD",
        "dataset": "MNIST"
    }
)

# Training function
def train(epoch):
    model.train()
    running_loss = 0
    correct = 0
    total = 0

    for batch_idx, (data, target) in enumerate(train_loader):
        data, target = data.to(device), target.to(device)

        # Reset gradients
        optimizer.zero_grad()

        # Forward + backward + optimize
        output = model(data)
        loss = criterion(output, target)
        loss.backward()
        optimizer.step()

        # Statistics
        running_loss += loss.item()
        _, predicted = output.max(1)
        total += target.size(0)
        correct += predicted.eq(target).sum().item()

    # Calculate epoch metrics
    train_loss = running_loss / len(train_loader)
    train_acc = 100. * correct / total

    return train_loss, train_acc

# Test function
def test():
    model.eval()
    test_loss = 0
    correct = 0
    total = 0

    with torch.no_grad():
        for data, target in test_loader:
            data, target = data.to(device), target.to(device)

            # Forward pass
            output = model(data)
            loss = criterion(output, target)

            # Statistics
            test_loss += loss.item()
            _, predicted = output.max(1)
            total += target.size(0)
            correct += predicted.eq(target).sum().item()

    # Calculate test metrics
    test_loss = test_loss / len(test_loader)
    test_acc = 100. * correct / total

    return test_loss, test_acc

# Training loop
for epoch in range(epochs):
    # Training
    train_loss, train_acc = train(epoch)

    # Testing
    test_loss, test_acc = test()

    # Log metrics
    aspara.log({
        "train_loss": train_loss,
        "train_accuracy": train_acc,
        "test_loss": test_loss,
        "test_accuracy": test_acc
    }, step=epoch)

    print(f'Epoch {epoch+1}/{epochs}:')
    print(f'Train Loss: {train_loss:.4f}, Train Acc: {train_acc:.2f}%')
    print(f'Test Loss: {test_loss:.4f}, Test Acc: {test_acc:.2f}%')
    print('---')

# Finish the run
aspara.finish()
```

## Code Explanation

This code performs the following:

1. **Data Preparation**:
   - Download and preprocess the MNIST dataset
   - Use DataLoader for batch processing

2. **Model Definition**:
   - Define a simple fully-connected neural network
   - Input layer (28x28=784 nodes), hidden layer (128 nodes), output layer (10 nodes)

3. **Tracking with Aspara**:
   - Initialize run with `aspara.init()`
   - Record hyperparameters with the `config` parameter
   - Log training and test metrics with `aspara.log()` at each epoch

4. **Training Loop**:
   - Execute training and testing at each epoch
   - Calculate metrics and log them with Aspara

Running this sample will track your training progress with Aspara, enabling later analysis.

## Alternative: Using Context Manager

You can also use the context manager pattern for automatic cleanup. This ensures `finish()` is called even if an exception occurs:

```python
with aspara.init(
    project="deep_learning_examples",
    name="mnist_pytorch",
    config={...}
) as run:
    for epoch in range(epochs):
        train_loss, train_acc = train(epoch)
        test_loss, test_acc = test()
        aspara.log({...}, step=epoch)
# finish() called automatically
```

For simple scripts, the context manager pattern is convenient. For integration with frameworks like PyTorch Lightning, the manual `finish()` pattern shown in the main example is often more appropriate.
