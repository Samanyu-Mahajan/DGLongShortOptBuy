#!/bin/bash

for t in $(seq 5 5 60); do
    echo "Running with t=$t"
    ./run.sh "$t"
done
