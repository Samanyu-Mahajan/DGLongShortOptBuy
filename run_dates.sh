#!/bin/bash

# Directory containing date-based folders
DATA_DIR="quantx/data"

# Loop through all folders inside quantx/data
for folder in "$DATA_DIR"/*/; do
    # Extract the folder name (which is the date)
    date=$(basename "$folder")

    # Execute ./run.sh with the date
    echo "Executing ./run.sh $date"
    ./run.sh "$date"
done