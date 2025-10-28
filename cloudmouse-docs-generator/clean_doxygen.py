#!/usr/bin/env python3
"""
CloudMouse SDK - Doxygen HTML Cleaner

Cleans Doxygen-generated HTML files for CMS WYSIWYG integration.
Removes navigation, headers, footers, and complex styling while preserving
the core documentation content.

Usage:
    python clean_doxygen.py [input_dir] [output_dir]
    
Example:
    python clean_doxygen.py ./docs/html ./docs/clean
"""

import os
import re
import sys
import shutil
from pathlib import Path
from bs4 import BeautifulSoup

def clean_html_content(html_content):
    """
    Clean HTML content for CMS integration
    Removes Doxygen navigation, styling, and scripts while preserving documentation structure
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Remove unwanted elements completely
    unwanted_selectors = [
        '#top',           # Top navigation
        '.header',        # Header elements
        '.tabs',          # Tab navigation
        '.navpath',       # Navigation path
        '#nav-tree',      # Navigation tree
        '#splitbar',      # Split bar
        '#side-nav',      # Side navigation
        '.footer',        # Footer
        '#MSearchBox',    # Search box
        '.directory',     # Directory listings
        'script',         # All JavaScript
        'link[rel="stylesheet"]',  # CSS links
        'style'           # Inline styles
    ]
    
    for selector in unwanted_selectors:
        for element in soup.select(selector):
            element.decompose()
    
    # Find the main content area
    main_content = None
    
    # Try different content selectors used by Doxygen
    content_selectors = [
        '.contents',      # Main content area
        '#doc-content',   # Document content
        '.textblock',     # Text blocks
        '.memitem',       # Member items
        '.groupheader'    # Group headers
    ]
    
    for selector in content_selectors:
        content = soup.select_one(selector)
        if content:
            main_content = content
            break
    
    # If no specific content area found, use body
    if not main_content:
        main_content = soup.find('body')
    
    if not main_content:
        return ""
    
    # Clean up attributes selectively
    for tag in main_content.find_all():
        # Remove only problematic attributes, keep useful ones
        attrs_to_remove = ['onclick', 'onload', 'style']
        for attr in attrs_to_remove:
            if attr in tag.attrs:
                del tag.attrs[attr]
        
        # Clean up specific Doxygen IDs but keep useful classes
        if 'id' in tag.attrs:
            tag_id = tag.attrs['id']
            # Remove Doxygen generated IDs but keep meaningful ones
            if tag_id.startswith(('a', 'g', '_')) and len(tag_id) > 10:
                del tag.attrs['id']
        
        # Keep table attributes (colspan, rowspan, etc.)
        if tag.name == 'table':
            # Keep all table attributes as they're needed for layout
            pass
        elif tag.name in ['td', 'th']:
            # Keep cell attributes like colspan, rowspan
            pass
        elif tag.name in ['tr']:
            # Keep row attributes
            pass
    
    # Convert some Doxygen-specific elements to cleaner HTML
    
    # Convert code blocks with better class preservation
    for code_block in main_content.find_all('div', class_=re.compile(r'fragment')):
        pre = soup.new_tag('pre')
        pre['class'] = 'code-block'
        code = soup.new_tag('code')
        code.string = code_block.get_text()
        pre.append(code)
        code_block.replace_with(pre)
    
    # Convert parameter lists but keep structure
    for param_list in main_content.find_all('dl', class_=re.compile(r'params')):
        param_list['class'] = 'parameter-list'
        for dt in param_list.find_all('dt'):
            dt.name = 'strong'
            dt['class'] = 'param-name'
        for dd in param_list.find_all('dd'):
            dd.name = 'div'
            dd['class'] = 'param-description'
    
    # Preserve member item structure with useful classes
    for memitem in main_content.find_all(class_=re.compile(r'memitem')):
        memitem['class'] = 'member-item'
        
        # Find and mark member titles
        for memtitle in memitem.find_all(class_=re.compile(r'memtitle')):
            memtitle['class'] = 'member-title'
        
        # Find and mark member descriptions
        for memdoc in memitem.find_all(class_=re.compile(r'memdoc')):
            memdoc['class'] = 'member-doc'
    
    # Mark section headers
    for header in main_content.find_all(class_=re.compile(r'groupheader')):
        header['class'] = 'section-header'
    
    # Preserve but clean table classes
    for table in main_content.find_all('table'):
        if 'class' in table.attrs:
            # Keep useful table classes, remove Doxygen-specific ones
            classes = table.get('class', [])
            cleaned_classes = []
            for cls in classes:
                if not cls.startswith(('dox', 'Dox')) and cls not in ['memberdecls', 'memname']:
                    cleaned_classes.append(cls)
            if not cleaned_classes:
                cleaned_classes = ['api-table']
            table['class'] = cleaned_classes
        else:
            table['class'] = ['api-table']
    
    # Convert to string for text replacement
    content_str = str(main_content)
    
    # Remove the Doxygen file reference text
    doxygen_text = "The documentation for this class was generated from the following files:"
    if doxygen_text in content_str:
        # Replace the text with empty string
        content_str = content_str.replace(doxygen_text, "")
        
        # Parse back to soup to remove the last <ul> if it contains file references
        temp_soup = BeautifulSoup(content_str, 'html.parser')
        all_uls = temp_soup.find_all('ul')
        if all_uls:
            last_ul = all_uls[-1]
            # Check if it contains file links (typically .h or .cpp files)
            if last_ul.get_text() and ('.h' in last_ul.get_text() or '.cpp' in last_ul.get_text()):
                last_ul.decompose()
        
        content_str = str(temp_soup)

    doxygen_text = "The documentation for this class was generated from the following file:"
    if doxygen_text in content_str:
        # Replace the text with empty string
        content_str = content_str.replace(doxygen_text, "")
        
        # Parse back to soup to remove the last <ul> if it contains file references
        temp_soup = BeautifulSoup(content_str, 'html.parser')
        all_uls = temp_soup.find_all('ul')
        if all_uls:
            last_ul = all_uls[-1]
            # Check if it contains file links (typically .h or .cpp files)
            if last_ul.get_text() and ('.h' in last_ul.get_text() or '.cpp' in last_ul.get_text()):
                last_ul.decompose()
        
        content_str = str(temp_soup)
    
    return content_str

def extract_class_documentation(input_dir, output_dir):
    """
    Extract documentation for each class/component into separate HTML files
    """
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    
    # Create output directory
    output_path.mkdir(parents=True, exist_ok=True)
    
    # CloudMouse SDK component mapping (based on actual Doxygen output)
    components = {
        # Core
        'classCloudMouse_1_1Core.html': 'Core',
        'classCloudMouse_1_1EventBus.html': 'EventBus',
        'structCloudMouse_1_1Event.html': 'Event',
        
        # Hardware
        'classCloudMouse_1_1Hardware_1_1DisplayManager.html': 'DisplayManager',
        'classCloudMouse_1_1Hardware_1_1EncoderManager.html': 'EncoderManager',
        'classCloudMouse_1_1Hardware_1_1LEDManager.html': 'LEDManager',
        'classCloudMouse_1_1Hardware_1_1SimpleBuzzer.html': 'SimpleBuzzer',
        'structCloudMouse_1_1Hardware_1_1LEDEvent.html': 'LEDEvent',
        'classRotaryEncoderPCNT.html': 'RotaryEncoderPCNT',
        'classLGFX__ILI9488.html': 'LGFX_ILI9488',
        
        # Network
        'classCloudMouse_1_1Network_1_1WiFiManager.html': 'WiFiManager',
        'classCloudMouse_1_1Network_1_1WebServerManager.html': 'WebServerManager',
        'classCloudMouse_1_1Network_1_1BluetoothManager.html': 'BluetoothManager',
        
        # Utils
        'classCloudMouse_1_1Utils_1_1DeviceID.html': 'DeviceID',
        'classCloudMouse_1_1Utils_1_1JsonHelper.html': 'JsonHelper',
        'classCloudMouse_1_1Utils_1_1NTPManager.html': 'NTPManager',
        'classCloudMouse_1_1Utils_1_1QRCodeManager.html': 'QRCodeManager',
        
        # Prefs
        'classCloudMouse_1_1Prefs_1_1PreferencesManager.html': 'PreferencesManager',
        
        # Config
        'DeviceConfig_8h.html': 'DeviceConfig',
        
        # Namespaces
        'namespaceCloudMouse.html': 'CloudMouse',
        'namespaceCloudMouse_1_1Hardware.html': 'Hardware',
        'namespaceCloudMouse_1_1Network.html': 'Network',
        'namespaceCloudMouse_1_1Utils.html': 'Utils',
        'namespaceCloudMouse_1_1Prefs.html': 'Prefs'
    }
    
    print("🧹 Cleaning Doxygen HTML files for CMS integration...")
    
    processed_count = 0
    for doxygen_file, component_name in components.items():
        input_file = input_path / doxygen_file
        
        if input_file.exists():
            print(f"📄 Processing {component_name}...")
            
            # Read original HTML
            with open(input_file, 'r', encoding='utf-8') as f:
                original_html = f.read()
            
            # Clean the HTML
            clean_html = clean_html_content(original_html)
            
            if clean_html:
                # Write cleaned HTML
                output_file = output_path / f"{component_name.lower()}.html"
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(clean_html)
                
                print(f"✅ Created {output_file}")
                processed_count += 1
            else:
                print(f"⚠️ No content found in {doxygen_file}")
        else:
            print(f"❌ File not found: {doxygen_file}")
    
    print(f"📊 Processed {processed_count} components successfully")
    
    # Create index file with component listing
    create_index_file(output_path, components)

def create_index_file(output_path, components):
    """
    Create an index HTML file listing all components
    """
    index_html = """
<h1>CloudMouse SDK API Documentation</h1>

<h2>Namespaces</h2>
<ul>
    <li><a href="cloudmouse.html">CloudMouse</a> - Core namespace with global functions and enums</li>
    <li><a href="network.html">Network</a> - Core namespace with global functions and enums</li>
    <li><a href="harware.html">Hardware</a> - Core namespace with global functions and enums</li>
    <li><a href="utils.html">Utils</a> - Core namespace with global functions and enums</li>
    <li><a href="prefs.html">Prefs</a> - Core namespace with global functions and enums</li>
</ul>

<h2>Core System</h2>
<ul>
    <li><a href="core.html">Core</a> - Main SDK initialization and system management</li>
    <li><a href="eventbus.html">EventBus</a> - Thread-safe inter-task messaging</li>
    <li><a href="event.html">Event</a> - Type-safe event definitions and data structures</li>
</ul>

<h2>Hardware Management</h2>
<ul>
    <li><a href="hardware.html">Hardware</a> - Hardware namespace</li>
    <li><a href="displaymanager.html">DisplayManager</a> - TFT display control and UI rendering</li>
    <li><a href="encodermanager.html">EncoderManager</a> - Rotary encoder input processing</li>
    <li><a href="ledmanager.html">LEDManager</a> - LED control and visual feedback</li>
    <li><a href="ledevent.html">LEDEvent</a> - LED event structure</li>
    <li><a href="simplebuzzer.html">SimpleBuzzer</a> - Audio feedback and sound patterns</li>
    <li><a href="rotaryencoderpcnt.html">RotaryEncoderPCNT</a> - Cross-platform PCNT hardware abstraction</li>
    <li><a href="lgfx_ili9488.html">LGFX_ILI9488</a> - ILI9488 display hardware configuration</li>
</ul>

<h2>Network Management</h2>
<ul>
    <li><a href="network.html">Network</a> - Network namespace</li>
    <li><a href="wifimanager.html">WiFiManager</a> - WiFi connection lifecycle management</li>
    <li><a href="bluetoothmanager.html">BluetoothManager</a> - Bluetooth interface for lifecycle management</li>
    <li><a href="webservermanager.html">WebServerManager</a> - Captive portal for device setup</li>
</ul>

<h2>Helpers and Utilities</h2>
<ul>
    <li><a href="utils.html">Utils</a> - Utilities namespace</li>
    <li><a href="deviceid.html">DeviceID</a> - Hardware-based device identification</li>
    <li><a href="jsonhelper.html">JsonHelper</a> - JSON processing utilities</li>
    <li><a href="ntpmanager.html">NTPManager</a> - Network time synchronization</li>
    <li><a href="qrcodemanager.html">QRCodeManager</a> - QR code generation and rendering</li>
</ul>

<h2>Preferences</h2>
<ul>
    <li><a href="prefs.html">Prefs</a> - Preferences namespace</li>
    <li><a href="preferencesmanager.html">PreferencesManager</a> - Non-volatile storage management</li>
</ul>

<h2>Configuration</h2>
<ul>
    <li><a href="deviceconfig.html">DeviceConfig</a> - Central device and hardware configuration</li>
</ul>

<h2>SDK Information</h2>
<p>CloudMouse SDK provides a comprehensive IoT development platform for ESP32-based devices with professional-grade documentation and hardware abstraction.</p>

<h3>Key Features</h3>
<ul>
    <li>Event-driven architecture with thread-safe communication</li>
    <li>Cross-platform ESP-IDF compatibility (4.4 and 5.x)</li>
    <li>Hardware-accelerated display rendering with PSRAM optimization</li>
    <li>Multi-level encoder input processing (click, long press, ultra-long press)</li>
    <li>Comprehensive WiFi management with captive portal setup</li>
    <li>Professional audio and visual feedback systems</li>
    <li>PCB version compatibility and power management</li>
    <li>Time synchronization and preferences management</li>
    <li>QR code generation for device setup and configuration</li>
    <li>JSON processing utilities for data exchange</li>
</ul>
"""
    
    index_file = output_path / "index.html"
    with open(index_file, 'w', encoding='utf-8') as f:
        f.write(index_html)
    
    print(f"📋 Created documentation index: {index_file}")

def main():
    """
    Main function to process command line arguments and run the cleaner
    """
    if len(sys.argv) < 3:
        print("Usage: python clean_doxygen.py <input_dir> <output_dir>")
        print("Example: python clean_doxygen.py ./docs/html ./docs/clean")
        sys.exit(1)
    
    input_dir = sys.argv[1]
    output_dir = sys.argv[2]
    
    if not os.path.exists(input_dir):
        print(f"❌ Input directory does not exist: {input_dir}")
        sys.exit(1)
    
    extract_class_documentation(input_dir, output_dir)
    print("🎉 Documentation cleaning completed!")
    print(f"📁 Clean HTML files available in: {output_dir}")

if __name__ == "__main__":
    main()