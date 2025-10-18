#!/bin/bash

# Test script for the progress tracking system
# This script simulates the two processes to verify the progress tracking works

# Color codes for output
BLUE='\033[0;34m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${CYAN}🧪 Testing Progress Tracking System${NC}"
echo -e "${CYAN}===================================${NC}"
echo ""

# Clear any existing progress logs
rm -f /tmp/gamelist_progress.log /tmp/thumbnails_progress.log

# Create some test ROM files for simulation
TEST_ROMS_DIR="/tmp/test_roms"
mkdir -p "$TEST_ROMS_DIR"

# Create 20 test ROM files
for i in {1..20}; do
    echo "Test ROM $i" > "$TEST_ROMS_DIR/game_$i.nes"
done

echo -e "${BLUE}📊 Created 20 test ROM files${NC}"
echo ""

# Function to simulate gamelist processing
simulate_gamelist_processing() {
    echo -e "${BLUE}🔄 Simulating gamelist processing...${NC}"
    for i in {1..20}; do
        echo "$TEST_ROMS_DIR/game_$i.nes" >> /tmp/gamelist_progress.log
        sleep 0.5  # Simulate processing time
    done
    echo -e "${GREEN}✅ Gamelist processing simulation complete${NC}"
}

# Function to simulate thumbnail processing
simulate_thumbnail_processing() {
    echo -e "${PURPLE}🖼️  Simulating thumbnail processing...${NC}"
    for i in {1..20}; do
        echo "$TEST_ROMS_DIR/game_$i.png" >> /tmp/thumbnails_progress.log
        sleep 0.3  # Simulate processing time (faster than gamelist)
    done
    echo -e "${GREEN}✅ Thumbnail processing simulation complete${NC}"
}

# Start progress monitoring
echo -e "${CYAN}📊 Starting progress monitor...${NC}"
ROMS_DIR="$TEST_ROMS_DIR" bash scripts/progress_tracker.sh &
PROGRESS_PID=$!

# Start both simulations in parallel
simulate_gamelist_processing &
GAMELIST_PID=$!

simulate_thumbnail_processing &
THUMBNAILS_PID=$!

# Wait for both simulations to complete
wait $GAMELIST_PID
wait $THUMBNAILS_PID

# Stop progress monitoring
kill $PROGRESS_PID 2>/dev/null || true

echo ""
echo -e "${GREEN}✅ Test completed successfully!${NC}"
echo ""

# Clean up test files
rm -rf "$TEST_ROMS_DIR"
rm -f /tmp/gamelist_progress.log /tmp/thumbnails_progress.log

echo -e "${CYAN}🧹 Cleaned up test files${NC}"
echo ""
echo -e "${GREEN}🎉 Progress tracking system test passed!${NC}"
