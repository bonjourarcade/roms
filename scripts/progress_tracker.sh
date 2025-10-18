#!/bin/bash

# Progress tracking script for gamelist and thumbnail generation
# This script monitors log files created by both processes and calculates progress ratios

# Prevent multiple instances from running
LOCK_FILE="/tmp/progress_tracker.lock"
if [ -f "$LOCK_FILE" ]; then
    echo "Progress tracker is already running. Exiting."
    exit 1
fi

# Create lock file
echo $$ > "$LOCK_FILE"

# Function to cleanup on exit
cleanup() {
    echo ""
    echo -e "${YELLOW}⚠️  Progress monitoring stopped.${NC}"
    rm -f "$LOCK_FILE"
    exit 0
}

# Set up signal handlers
trap cleanup SIGINT SIGTERM EXIT

# Color codes for output
BLUE='\033[0;34m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
GAMELIST_LOG="/tmp/gamelist_progress.log"
THUMBNAILS_LOG="/tmp/thumbnails_progress.log"
UPDATE_INTERVAL=1  # seconds (back to reasonable rate)
ROMS_DIR="./roms"

# Function to count total ROM files (excluding bios directory)
count_total_roms() {
    local roms_dir="${ROMS_DIR:-roms}"
    if [ -d "$roms_dir" ] || [ -L "$roms_dir" ]; then
        # Use -L flag to follow symbolic links and only count actual ROM files
        find -L "$roms_dir" -type f -not -path "*/bios/*" \( \
            -name "*.nes" -o -name "*.smc" -o -name "*.sfc" -o \
            -name "*.gb" -o -name "*.gbc" -o -name "*.gba" -o \
            -name "*.md" -o -name "*.smd" -o -name "*.bin" -o \
            -name "*.gg" -o -name "*.sms" -o -name "*.32x" -o \
            -name "*.vb" -o -name "*.wsc" -o -name "*.pce" -o \
            -name "*.a26" -o -name "*.j64" -o -name "*.z64" -o \
            -name "*.n64" -o -name "*.zip" \) | wc -l | tr -d ' '
    else
        # If roms directory doesn't exist, estimate from log files
        local gamelist_count=$(count_processed_files "$GAMELIST_LOG")
        local thumbnails_count=$(count_processed_files "$THUMBNAILS_LOG")
        # Use the maximum of the two counts as estimate
        if [ "$gamelist_count" -gt "$thumbnails_count" ]; then
            echo "$gamelist_count"
        else
            echo "$thumbnails_count"
        fi
    fi
}

# Function to count processed files from log
count_processed_files() {
    local log_file="$1"
    if [ -f "$log_file" ]; then
        wc -l < "$log_file" | tr -d ' '
    else
        echo "0"
    fi
}

# Function to calculate percentage
calculate_percentage() {
    local processed="$1"
    local total="$2"
    if [ "$total" -gt 0 ]; then
        echo $((processed * 100 / total))
    else
        # If total is 0, show 0% unless we have processed files
        if [ "$processed" -gt 0 ]; then
            echo "100"  # Show 100% if we have processed files but no total
        else
            echo "0"
        fi
    fi
}

# Function to create progress bar
create_progress_bar() {
    local percentage="$1"
    local width=30
    local filled=$((percentage * width / 100))
    local empty=$((width - filled))
    
    local bar=""
    for ((i=0; i<filled; i++)); do
        bar="${bar}█"
    done
    for ((i=0; i<empty; i++)); do
        bar="${bar}░"
    done
    
    echo "[$bar]"
}

# Function to get last processed file from log
get_last_processed() {
    local log_file="$1"
    if [ -f "$log_file" ] && [ -s "$log_file" ]; then
        tail -n 1 "$log_file"
    else
        echo "None"
    fi
}

# Function to display progress
display_progress() {
    local gamelist_processed="$1"
    local thumbnails_processed="$2"
    local total_roms="$3"
    
    local gamelist_percentage=$(calculate_percentage "$gamelist_processed" "$total_roms")
    local thumbnails_percentage=$(calculate_percentage "$thumbnails_processed" "$total_roms")
    
    local gamelist_bar=$(create_progress_bar "$gamelist_percentage")
    local thumbnails_bar=$(create_progress_bar "$thumbnails_percentage")
    
    local gamelist_last=$(get_last_processed "$GAMELIST_LOG")
    local thumbnails_last=$(get_last_processed "$THUMBNAILS_LOG")
    
    # Show progress (without clearing screen to avoid issues)
    echo -e "${CYAN}📊 Build Progress Monitor${NC}"
    echo -e "${CYAN}========================${NC}"
    echo ""
    echo -e "${BLUE}🔄 Gamelist Generation:${NC}"
    echo -e "   ${gamelist_bar} ${gamelist_percentage}% (${gamelist_processed}/${total_roms})"
    echo -e "   Last processed: ${YELLOW}${gamelist_last}${NC}"
    echo ""
    echo -e "${PURPLE}🖼️  Thumbnail Generation:${NC}"
    echo -e "   ${thumbnails_bar} ${thumbnails_percentage}% (${thumbnails_processed}/${total_roms})"
    echo -e "   Last processed: ${YELLOW}${thumbnails_last}${NC}"
    echo ""
    echo -e "${GREEN}📈 Overall Progress:${NC}"
    local overall_processed=$((gamelist_processed + thumbnails_processed))
    local overall_total=$((total_roms * 2))
    local overall_percentage=$(calculate_percentage "$overall_processed" "$overall_total")
    local overall_bar=$(create_progress_bar "$overall_percentage")
    echo -e "   ${overall_bar} ${overall_percentage}% (${overall_processed}/${overall_total})"
    echo ""
    echo -e "${CYAN}⏱️  Update interval: ${UPDATE_INTERVAL}s | Press Ctrl+C to stop monitoring${NC}"
}

# Main monitoring loop
main() {
    echo -e "${CYAN}🚀 Starting progress monitor...${NC}"
    
    # Count total ROM files
    TOTAL_ROMS=$(count_total_roms)
    echo -e "${GREEN}📊 Total ROM files to process: ${TOTAL_ROMS}${NC}"
    echo ""
    
    # Initialize log files if they don't exist
    touch "$GAMELIST_LOG" "$THUMBNAILS_LOG"
    
    # Monitor loop
    while true; do
        GAMELIST_PROCESSED=$(count_processed_files "$GAMELIST_LOG")
        THUMBNAILS_PROCESSED=$(count_processed_files "$THUMBNAILS_LOG")
        
        display_progress "$GAMELIST_PROCESSED" "$THUMBNAILS_PROCESSED" "$TOTAL_ROMS"
        
        # Check if both processes are complete
        if [ "$GAMELIST_PROCESSED" -ge "$TOTAL_ROMS" ] && [ "$THUMBNAILS_PROCESSED" -ge "$TOTAL_ROMS" ]; then
            echo ""
            echo -e "${GREEN}✅ Both processes completed!${NC}"
            break
        fi
        
        sleep "$UPDATE_INTERVAL"
    done
}

# Run main function
main
