#!/bin/bash

# Script to generate thumbnail versions of game cover images using ImageMagick.
# This script should be run from the project root.

# Color codes for output
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

THUMB_WIDTH=150

# --- Check for ImageMagick (convert command) ---
if ! command -v magick &> /dev/null
then
    echo "Error: ImageMagick (convert command) not found."
    echo "Please install ImageMagick. On macOS: brew install imagemagick. On Alpine: apk add imagemagick."
    exit 1
fi

echo "Starting thumbnail generation..."

# Find all cover images by scanning the games directory structure
# This makes the thumbnail generation independent of gamelist.json
GAMES_DIR="public/games"
IMAGE_PATHS=""

# Find all cover.png files in game directories
if [ -d "$GAMES_DIR" ]; then
    IMAGE_PATHS=$(find "$GAMES_DIR" -name "cover.png" -type f | sort)
fi

# Also include the default placeholder and any other static images
DEFAULT_COVER="public/assets/images/placeholder_thumb.png"
if [ -f "$DEFAULT_COVER" ]; then
    IMAGE_PATHS="$IMAGE_PATHS
$DEFAULT_COVER"
fi



if [ -z "$IMAGE_PATHS" ]; then
    echo "No cover images found to process."
    exit 0
fi

# Count total images for progress bar
TOTAL_IMAGES=$(echo "$IMAGE_PATHS" | wc -l)
PROCESSED_COUNT=0
FAILED_COUNT=0
FAILED_FILES=()

echo "Found $TOTAL_IMAGES images to process..."

# Function to update progress bar
update_progress() {
    local current=$1
    local total=$2
    local width=50
    local percentage=$((current * 100 / total))
    local filled=$((current * width / total))
    local empty=$((width - filled))
    
    # Create progress bar string
    local bar=""
    for ((i=0; i<filled; i++)); do
        bar="${bar}█"
    done
    for ((i=0; i<empty; i++)); do
        bar="${bar}░"
    done
    
    # Print progress bar (carriage return to overwrite same line)
    printf "\r${PURPLE}[%s] %d%% (%d/%d)${NC}" "$bar" "$percentage" "$current" "$total"
}

while IFS= read -r relative_path; do
    # Remove leading slash if it's an absolute path from web root
    if [[ "$relative_path" == /* ]]; then
        relative_path="${relative_path:1}"
    fi
    
    full_image_path="$relative_path"
    
    # Prepend 'public/' if the path does not already start with it
    # This assumes coverArt paths in gamelist.json are relative to the *web root* (public/)
    if [[ ! "$full_image_path" == public/* ]]; then
        full_image_path="public/$full_image_path"
    fi

    if [ ! -f "$full_image_path" ]; then
        FAILED_COUNT=$((FAILED_COUNT+1))
        FAILED_FILES+=("$full_image_path (file not found)")
        PROCESSED_COUNT=$((PROCESSED_COUNT+1))
        update_progress $PROCESSED_COUNT $TOTAL_IMAGES
        continue
    fi

    # Construct thumbnail filename (e.g., cover.png -> cover_thumb.png)
    filename=$(basename "$full_image_path")
    dirname=$(dirname "$full_image_path")
    extension="${filename##*.}"
    base_name="${filename%.*}"
    
    thumbnail_path="${dirname}/${base_name}_thumb.${extension}"

    # Generate thumbnail using ImageMagick's magick command
    # -resize: Resizes the image to the given width, maintaining aspect ratio.
    #          > prevents upsizing if original is smaller.
    if magick "$full_image_path" -resize "${THUMB_WIDTH}x>" "$thumbnail_path" 2>/dev/null; then
        PROCESSED_COUNT=$((PROCESSED_COUNT+1))
    else
        FAILED_COUNT=$((FAILED_COUNT+1))
        FAILED_FILES+=("$full_image_path (ImageMagick processing failed)")
    fi
    
    # Update progress bar
    update_progress $PROCESSED_COUNT $TOTAL_IMAGES

done <<< "$IMAGE_PATHS"

# Complete the progress bar with a newline
echo ""

echo "Thumbnail generation complete. Processed: ${PROCESSED_COUNT}, Failed: ${FAILED_COUNT}"

if [ "$FAILED_COUNT" -gt 0 ]; then
    echo "⚠️  Thumbnail generation completed with ${FAILED_COUNT} failures."
    echo ""
    echo "Failed files:"
    for failed_file in "${FAILED_FILES[@]}"; do
        echo "  ❌ $failed_file"
    done
    exit 1 # Indicate failure if any images failed to process
else
    echo "✅ Thumbnail generation completed successfully!"
    exit 0
fi 
