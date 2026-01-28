# Adaptation Engine Documentation

## Overview

The Adaptation Engine (`adaptation.py`) applies context-aware rules to modify the UI behavior based on user profile and environmental context. This implements Step 4 (Adaptation Rules) and Step 5 (Adaptive Interface) of the Musea system.

## Rules Implemented

### 1. Bandwidth Rule
- **Condition**: `connection_quality == 'poor'`
- **Action**: Sets `show_images = False`
- **Purpose**: Reduces data usage on poor connections

### 2. Time Constraint Rule
- **Condition**: `time_available <= 15` minutes
- **Actions**: 
  - Sets `max_results = 3`
  - Sets `description_length = 'short'`
- **Purpose**: Shows fewer results with shorter descriptions when user has limited time

### 3. Mobile Context Rule
- **Condition**: `device == 'mobile'`
- **Actions**:
  - Sets `layout = 'list'`
- **Purpose**: Optimizes layout for mobile devices (same number of museums as desktop)

## Usage

### Testing Adaptations

You can test different adaptation scenarios by adding query parameters to the museum gallery URL:

```
# Test poor connection
/museum_gallery?connection_quality=poor

# Test limited time
/museum_gallery?time_available=10

# Test mobile device (or use actual mobile device)
/museum_gallery?device=mobile

# Combine multiple conditions
/museum_gallery?connection_quality=poor&time_available=10
```

### Default Behavior

If no context is detected, the system uses:
- `connection_quality`: 'good'
- `time_available`: 60 minutes
- `device`: 'desktop' (or detected from User-Agent)

## Files

- `adaptation.py`: Core adaptation engine with rule logic
- `app.py`: Updated `/museum_gallery` route to use adaptation engine
- `templates/museum_gallery.html`: Updated to respect adaptation settings
- `static/style.css`: Added list layout styling for mobile adaptation

## Adaptation Log

The system displays a transparency log at the bottom of the gallery page showing:
- What adaptations were applied
- Why they were applied (the reasons)

Example: "System adapted: Hiding images and shortening descriptions because connection is poor and you have 10 minutes."
