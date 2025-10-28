#!/bin/bash

# CloudMouse SDK - Documentation Generation Tool
# Standalone tool for generating clean HTML documentation from CloudMouse SDK source code
# 
# Usage: ./generate_docs.sh --path /path/to/cloudmouse-sdk
# 
# This tool can be placed anywhere and will generate documentation for any CloudMouse SDK codebase

set -e  # Exit on any error

# Default configuration
TOOL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR=""
DOCS_DIR="$TOOL_DIR/docs"
CLEAN_DIR="$DOCS_DIR/clean"
DOXYFILE="$TOOL_DIR/Doxyfile"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to show usage
show_usage() {
    cat << EOF
CloudMouse SDK Documentation Generator

USAGE:
    $0 --path <source_path> [options]

REQUIRED:
    --path <path>      Path to CloudMouse SDK source code directory

OPTIONS:
    --clean-only       Only clean existing Doxygen HTML (skip generation)
    --help, -h         Show this help message

EXAMPLES:
    # Generate docs for SDK in ~/dev/cloudmouse-sdk
    $0 --path ~/dev/cloudmouse-sdk
    
    # Generate docs for current directory
    $0 --path .
    
    # Only clean existing HTML
    $0 --path ~/dev/cloudmouse-sdk --clean-only

DIRECTORY STRUCTURE:
    Tool directory (where this script lives):
    ~/dev/tools/cloudmouse-docs-generator/
    ├── generate_docs.sh       # This script
    ├── clean_doxygen.py       # HTML cleaner
    ├── Doxyfile              # Doxygen configuration
    └── docs/                 # Generated documentation
        ├── html/             # Raw Doxygen output
        └── clean/            # Clean HTML for CMS

DEPENDENCIES:
    - doxygen
    - python3
    - beautifulsoup4 (auto-installed if missing)

OUTPUT:
    Clean HTML files suitable for CMS WYSIWYG integration will be generated in:
    $TOOL_DIR/docs/clean/

EOF
}

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Parse command line arguments
parse_arguments() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --path)
                PROJECT_DIR="$2"
                shift 2
                ;;
            --clean-only)
                CLEAN_ONLY=true
                shift
                ;;
            --help|-h)
                show_usage
                exit 0
                ;;
            *)
                print_error "Unknown option: $1"
                echo "Use --help for usage information"
                exit 1
                ;;
        esac
    done
    
    # Validate required arguments
    if [[ -z "$PROJECT_DIR" ]]; then
        print_error "Missing required --path argument"
        echo
        show_usage
        exit 1
    fi
    
    # Convert to absolute path and validate
    PROJECT_DIR="$(realpath "$PROJECT_DIR" 2>/dev/null)" || {
        print_error "Invalid path: $PROJECT_DIR"
        exit 1
    }
    
    if [[ ! -d "$PROJECT_DIR" ]]; then
        print_error "Directory does not exist: $PROJECT_DIR"
        exit 1
    fi
    
    print_status "Target SDK path: $PROJECT_DIR"
}

# Check dependencies
check_dependencies() {
    print_status "Checking dependencies..."
    
    if ! command_exists doxygen; then
        print_error "Doxygen not found. Please install it:"
        echo "  Ubuntu/Debian: sudo apt install doxygen"
        echo "  macOS: brew install doxygen"
        echo "  Windows: Download from https://doxygen.nl/"
        exit 1
    fi
    
    if ! command_exists python3; then
        print_error "Python 3 not found. Please install Python 3."
        exit 1
    fi
    
    # Check if BeautifulSoup is available
    if ! python3 -c "import bs4" 2>/dev/null; then
        print_warning "BeautifulSoup4 not found. Installing..."
        pip3 install beautifulsoup4 lxml || {
            print_error "Failed to install BeautifulSoup4. Please install manually:"
            echo "  pip3 install beautifulsoup4 lxml"
            exit 1
        }
    fi
    
    print_success "All dependencies are available"
}

# Validate CloudMouse SDK structure
validate_sdk_structure() {
    print_status "Validating CloudMouse SDK structure..."
    
    # Check for key SDK files
    local required_files=(
        "lib/hardware/DisplayManager.h"
        "lib/hardware/EncoderManager.h"
        "lib/hardware/LEDManager.h"
        "lib/hardware/SimpleBuzzer.h"
        "lib/network/WiFiManager.h"
        "lib/network/WebServerManager.h"
        "lib/network/BluetoothManager.h"
        "lib/core/Core.h"
        "lib/core/EventBus.h"
        "lib/core/Events.h"
        "lib/config/DeviceConfig.h"
        "lib/utils/DeviceID.h"
        "lib/utils/JsonHelper.h"
        "lib/utils/NTPManager.h"
        "lib/utils/QRCodeManager.h"
        "lib/prefs/PreferencesManager.h"
    )
    
    local missing_files=()
    for file in "${required_files[@]}"; do
        if [[ ! -f "$PROJECT_DIR/$file" ]]; then
            missing_files+=("$file")
        fi
    done
    
    if [[ ${#missing_files[@]} -gt 0 ]]; then
        print_error "Invalid CloudMouse SDK structure. Missing files:"
        for file in "${missing_files[@]}"; do
            echo "  - $file"
        done
        echo
        echo "Please ensure you're pointing to a valid CloudMouse SDK directory."
        exit 1
    fi
    
    print_success "CloudMouse SDK structure validated"
}

# Update Doxyfile with correct paths
update_doxyfile() {
    print_status "Updating Doxygen configuration..."
    
    # Create a temporary Doxyfile with correct paths
    local temp_doxyfile="$TOOL_DIR/Doxyfile.tmp"
    
    # Copy base Doxyfile and update paths
    cp "$DOXYFILE" "$temp_doxyfile"
    
    # Update INPUT path to point to the SDK directory
    sed -i.bak "s|INPUT[[:space:]]*=.*|INPUT = $PROJECT_DIR|g" "$temp_doxyfile"
    
    # Update OUTPUT_DIRECTORY to point to tool directory
    sed -i.bak "s|OUTPUT_DIRECTORY[[:space:]]*=.*|OUTPUT_DIRECTORY = $DOCS_DIR|g" "$temp_doxyfile"
    
    # Clean up backup file
    rm -f "$temp_doxyfile.bak"
    
    DOXYFILE="$temp_doxyfile"
    print_success "Doxygen configuration updated"
}

# Clean previous documentation
clean_previous() {
    print_status "Cleaning previous documentation..."
    
    if [[ -d "$DOCS_DIR" ]]; then
        rm -rf "$DOCS_DIR"
        print_success "Removed previous documentation directory"
    fi
}

# Generate Doxygen documentation
generate_doxygen() {
    print_status "Generating Doxygen documentation..."
    
    # Change to project directory for relative path resolution
    local original_dir="$(pwd)"
    cd "$PROJECT_DIR"
    
    # Run Doxygen
    doxygen "$DOXYFILE" > /dev/null 2>&1 || {
        print_error "Doxygen generation failed"
        cd "$original_dir"
        exit 1
    }
    
    cd "$original_dir"
    
    if [[ ! -d "$DOCS_DIR/html" ]]; then
        print_error "Doxygen failed to generate HTML documentation"
        exit 1
    fi
    
    print_success "Doxygen documentation generated successfully"
}

# Clean HTML for CMS integration
clean_html() {
    print_status "Cleaning HTML for CMS integration..."
    
    # Create clean directory
    mkdir -p "$CLEAN_DIR"
    
    # Run the cleaning script
    python3 "$TOOL_DIR/clean_doxygen.py" "$DOCS_DIR/html" "$CLEAN_DIR" || {
        print_error "HTML cleaning failed"
        exit 1
    }
    
    if [[ ! -d "$CLEAN_DIR" ]] || [[ ! "$(ls -A $CLEAN_DIR)" ]]; then
        print_error "HTML cleaning produced no output"
        exit 1
    fi
    
    print_success "HTML cleaned successfully for CMS integration"
}

# Create component summary
create_summary() {
    print_status "Creating component summary..."
    
    # Count generated files
    local html_count
    html_count=$(find "$CLEAN_DIR" -name "*.html" | wc -l)
    
    cat > "$CLEAN_DIR/README.md" << EOF
# CloudMouse SDK Documentation

Generated on: $(date)
Source path: $PROJECT_DIR
Tool path: $TOOL_DIR
Total components: $html_count

## Generated Files

### Hardware Management
- **DisplayManager** (\`displaymanager.html\`) - TFT display control and UI rendering
- **EncoderManager** (\`encodermanager.html\`) - Rotary encoder input processing  
- **RotaryEncoderPCNT** (\`rotaryencoderpcnt.html\`) - Cross-platform PCNT abstraction
- **SimpleBuzzer** (\`simplebuzzer.html\`) - Audio feedback system
- **LGFX_ILI9488** (\`lgfx_ili9488.html\`) - Display hardware configuration

### Networking
- **WiFiManager** (\`wifimanager.html\`) - WiFi lifecycle management
- **BluetoothManager** (\`bluetoothmanager.html\`) - Bluetooth lifecycle management
- **WebServerManager** (\`webservermanager.html\`) - Captive portal setup

### Communication System
- **EventBus** (\`eventbus.html\`) - Thread-safe inter-task messaging
- **Event** (\`event.html\`) - Type-safe event definitions

### Configuration
- **DeviceConfig** (\`deviceconfig.html\`) - Central device configuration

## Integration Notes

- All HTML files are cleaned for CMS WYSIWYG integration
- No external CSS, JavaScript, or complex styling
- Ready for copy-paste into your CMS
- Each file contains complete API documentation for one component

## Regeneration

To regenerate documentation after code changes:
\`\`\`bash
$TOOL_DIR/generate_docs.sh --path $PROJECT_DIR
\`\`\`

To clean only (after manual Doxygen run):
\`\`\`bash
$TOOL_DIR/generate_docs.sh --path $PROJECT_DIR --clean-only
\`\`\`
EOF

    print_success "Component summary created"
}

# Display results
show_results() {
    print_success "Documentation generation completed!"
    echo
    echo "📁 Generated files:"
    echo "  - Doxygen HTML: $DOCS_DIR/html/"
    echo "  - Clean HTML for CMS: $CLEAN_DIR/"
    echo
    echo "📋 Available components:"
    find "$CLEAN_DIR" -name "*.html" -exec basename {} \; | sort
    echo
    echo "🚀 Ready for CMS integration!"
    echo "   Copy the HTML content from $CLEAN_DIR/ into your WYSIWYG editor"
    echo
    echo "📝 Documentation summary: $CLEAN_DIR/README.md"
}

# Cleanup function
cleanup() {
    # Remove temporary Doxyfile if it exists
    if [[ -f "$TOOL_DIR/Doxyfile.tmp" ]]; then
        rm -f "$TOOL_DIR/Doxyfile.tmp"
    fi
}

# Set up cleanup trap
trap cleanup EXIT

# Main execution function
main() {
    echo "🚀 CloudMouse SDK Documentation Generator"
    echo "=========================================="
    echo "Tool directory: $TOOL_DIR"
    echo
    
    parse_arguments "$@"
    check_dependencies
    validate_sdk_structure
    
    if [[ "${CLEAN_ONLY:-false}" == "true" ]]; then
        print_status "Running HTML cleaning only..."
        if [[ ! -d "$DOCS_DIR/html" ]]; then
            print_error "No existing Doxygen HTML found. Run without --clean-only first."
            exit 1
        fi
        clean_html
    else
        clean_previous
        update_doxyfile
        generate_doxygen
        clean_html
    fi
    
    create_summary
    show_results
}

# Execute main function with all arguments
main "$@"
