#!/bin/bash

# Define the filename and new filename
old_filename="$1"
new_filename="$2"

# Preserve metadata: Access and modification time
access_time=$(stat --format='%X' "$old_filename")
modification_time=$(stat --format='%Y' "$alter_dateiname")

# Rename file
mv "$old_filename" "$new_filename"

# Restore access and modification time
touch -a -d @$access_time "$new_filename"
touch -m -d @$modification_time "$new_filename"

echo "File successfully renamed and access/modification time restored."
