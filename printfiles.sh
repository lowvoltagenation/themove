#!/bin/bash

# List of Python script files
files=("main.py" "models.py" "extensions.py" "forms.py" "templates/base.html" "static/css/style.css" "templates/home.html") # Add your file names here

# Loop through each file in the list
for file in "${files[@]}"; do
    # Check if the file exists
    if [ -f "$file" ]; then
        echo "----- Contents of $file -----"
        cat "$file" # Display the contents of the file
    else
        echo "File $file does not exist."
    fi
done
