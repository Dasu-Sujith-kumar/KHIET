import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np

# --- 1. SET THE AESTHETIC ---
# Use a dark, sleek theme
plt.style.use('dark_background')
sns.set_context("talk")  # Makes labels bigger/clearer

# Custom Neon Palette
COLOR_TRAIN = "#00F5FF"  # Cyan Neon
COLOR_VAL = "#FF007F"    # Neon Pink
COLOR_ACCENT = "#ADFF2F" # Green-Yellow
BG_DARK = "#121212"      # Deep Charcoal

# Function to clean up the spines for a "floating" look
def clean_plot(ax):
    ax.set_facecolor(BG_DARK)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_color('#444444')
    ax.spines['bottom'].set_color('#444444')
    ax.grid(color='#333333', linestyle='--', alpha=0.5)

# --- DATA ---
epochs = np.arange(1, 11)
train_acc = [0.82, 0.86, 0.89, 0.91, 0.93, 0.94, 0.945, 0.95, 0.952, 0.955]
val_acc = [0.80, 0.84, 0.87, 0.89, 0.91, 0.92, 0.925, 0.93, 0.935, 0.94]

# --- GRAPH 1: NEON LEARNING CURVES ---
fig, ax = plt.subplots(figsize=(12, 7))
fig.patch.set_facecolor(BG_DARK)

# Plotting with a "glow" effect (double plotting with alpha)
ax.plot(epochs, train_acc, color=COLOR_TRAIN, linewidth=3, label='Train Accuracy', marker='o', markersize=8)
ax.plot(epochs, train_acc, color=COLOR_TRAIN, alpha=0.3, linewidth=8) # Glow

ax.plot(epochs, val_acc, color=COLOR_VAL, linewidth=3, label='Validation Accuracy', marker='s', markersize=8)
ax.plot(epochs, val_acc, color=COLOR_VAL, alpha=0.3, linewidth=8) # Glow

ax.set_title('Combined Model Convergence', fontsize=22, fontweight='bold', pad=20, color='white')
ax.set_xlabel('Epoch', fontsize=14, color='#AAAAAA')
ax.set_ylabel('Accuracy Score', fontsize=14, color='#AAAAAA')
ax.legend(frameon=False, fontsize=12)
clean_plot(ax)
plt.show()

# --- GRAPH 2: MODERN BAR CHART (MODEL COMPARISON) ---
plt.figure(figsize=(12, 7), facecolor=BG_DARK)
models = ['Baseline', 'Frozen Weights', 'Fine-Tuned', 'Unseen Data']
accuracies = [87.75, 85, 94, 92]

# Create bar chart with a gradient-like feel
colors = ["#333333", "#444444", COLOR_TRAIN, COLOR_VAL]
bars = plt.bar(models, accuracies, color=colors, edgecolor='white', linewidth=0.5, width=0.6)

# Customizing text on bars
for bar in bars:
    yval = bar.get_height()
    plt.text(bar.get_x() + bar.get_width()/2, yval + 1, f'{yval}%', 
             ha='center', va='bottom', fontsize=14, fontweight='bold', color='white')

plt.title('Benchmark Comparison', fontsize=22, fontweight='bold', pad=25)
plt.ylim(0, 110)
clean_plot(plt.gca())
plt.show()

# --- GRAPH 3: GENERALIZATION GAP (AREA PLOT) ---
plt.figure(figsize=(12, 5), facecolor=BG_DARK)
gap = np.array(train_acc) - np.array(val_acc)

plt.fill_between(epochs, gap, color=COLOR_ACCENT, alpha=0.2)
plt.plot(epochs, gap, color=COLOR_ACCENT, linewidth=3, marker='D', markersize=6)

plt.axhline(y=0.06, color='#FF4444', linestyle=':', label='Overfit Alert')
plt.title('Generalization Stability (Gap Analysis)', fontsize=20, fontweight='bold', pad=20)
plt.xlabel('Epoch', color='#AAAAAA')
plt.ylabel('$\Delta$ Accuracy', color='#AAAAAA')
plt.legend(frameon=False)
clean_plot(plt.gca())
plt.show()

# --- GRAPH 4: PREDICTION CONFIDENCE (ERROR BARS) ---
plt.figure(figsize=(8, 7), facecolor=BG_DARK)
labels = ['Original', 'Tampered']
means = [0.63, 0.72]
stds = [0.105, 0.08]

# Using a "Floating Bar" or Dot Plot style for confidence
plt.errorbar(labels, means, yerr=stds, fmt='o', color=COLOR_TRAIN, 
             ecolor=COLOR_VAL, elinewidth=4, capsize=10, markersize=15, 
             markeredgecolor='white', label='Mean Confidence $\pm \sigma$')

plt.title('Model Confidence Profile', fontsize=22, fontweight='bold', pad=25)
plt.ylabel('Prediction Probability (0-1)', color='#AAAAAA')
plt.grid(axis='y', color='#333333')
clean_plot(plt.gca())
plt.show()   