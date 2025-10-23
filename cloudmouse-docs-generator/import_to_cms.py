#!/usr/bin/env python3
"""
CloudMouse SDK - CMS Documentation Importer

Imports clean HTML documentation into CodeIgniter CMS database.
Creates categories, pages, routes, and content automatically.

Usage:
    python import_to_cms.py --clean-dir /path/to/docs/clean [options]
    
Example:
    python import_to_cms.py --clean-dir ~/dev/tools/cloudmouse-docs-generator/docs/clean/
"""

import os
import sys
import re
import argparse
from pathlib import Path
import mysql.connector
from mysql.connector import Error
from bs4 import BeautifulSoup
from urllib.parse import quote
import json

# Load config
config_file = Path(__file__).parent / 'config.json'
with open(config_file) as f:
    config = json.load(f)

# =============================================================================
# DATABASE CONFIGURATION - MODIFY THESE VALUES
# =============================================================================
DB_CONFIG = {
    'host': config['db_host'],
    'database': config['db_name'],
    'user': config['db_user'], 
    'password': config['db_pass'],
    'charset': config['db_charset'],
    'collation': config['db_collation']
}

# =============================================================================
# SDK CONFIGURATION
# =============================================================================
SDK_ROOT_CATEGORY = 'SDK'  # Name of existing root category in CMS

# =============================================================================
# SDK DOCUMENTATION STRUCTURE
# =============================================================================
SDK_STRUCTURE = {
    'subcategories': {
        'Core System': {
            'uri': 'core-system',
            'description': 'Core SDK components and event system',
            'components': ['core', 'eventbus', 'event']
        },
        'Hardware Management': {
            'uri': 'hardware-management', 
            'description': 'Hardware abstraction and device control',
            'components': ['displaymanager', 'encodermanager', 'rotaryencoderpcnt', 
                         'ledmanager', 'ledevent', 'simplebuzzer', 'lgfx_ili9488']
        },
        'Networking': {
            'uri': 'networking',
            'description': 'Networking abstraction for connectivity control',
            'components': ['wifimanager', 'webservermanager']
        },
        'Helpers & Utilities': {
            'uri': 'helpers-utilities',
            'description': 'Utility classes and helper functions', 
            'components': ['deviceid', 'jsonhelper', 'ntpmanager', 
                         'qrcodemanager']
        },
        'Preferences': {
            'uri': 'preferences',
            'description': 'Preferences management',
            'components': ['preferencesmanager']
        },
        'Configuration': {
            'uri': 'configuration',
            'description': 'Device and system configuration',
            'components': ['deviceconfig']
        },
        'Namespace': {
            'uri': 'namespace',
            'description': 'SDK namespace schema',
            'components': ['cloudmouse', 'network', 'hardware', 'utils', 'prefs']
        }
    }
}

class CMSImporter:
    def __init__(self, db_config):
        self.db = None
        self.cursor = None
        self.db_config = db_config
        self.iso = 'en'  # Default language
        self.template = 'sdk'
        self.module = 'pages'
        self.category_path_cache = {}  # Cache for category paths in dry-run mode
        self.slug_map = {}  # Map filename.html -> final slug for link processing
        
    def connect_db(self):
        """Connect to MySQL database"""
        try:
            self.db = mysql.connector.connect(**self.db_config)
            self.cursor = self.db.cursor(dictionary=True)
            print("✅ Connected to database successfully")
            return True
        except Error as e:
            print(f"❌ Database connection failed: {e}")
            return False
    
    def disconnect_db(self):
        """Disconnect from database"""
        if self.cursor:
            self.cursor.close()
        if self.db:
            self.db.close()
        print("📤 Database connection closed")
    
    def create_route(self, slug, route_type, entity_id):
        """Create or update route entry"""
        try:
            # Check if route exists
            self.cursor.execute("SELECT id FROM routes WHERE slug = %s", (slug,))
            existing = self.cursor.fetchone()
            
            if existing:
                route_id = existing['id']
                print(f"📍 Route exists: {slug}")
            else:
                # Create new route
                route_query = "INSERT INTO routes (slug, route) VALUES (%s, %s)"
                route_value = f"front/{route_type}/show/{entity_id}"
                self.cursor.execute(route_query, (slug, route_value))
                route_id = self.cursor.lastrowid
                print(f"🆕 Created route: {slug} -> {route_value}")
            
            return route_id
        except Error as e:
            print(f"❌ Error creating route: {e}")
            return None
    
    def map_doxygen_filename(self, doxygen_filename):
        """Map Doxygen filename to our simplified filename"""
        # Remove .html extension for processing
        base_name = doxygen_filename.replace('.html', '')
        
        # Doxygen to simplified name mappings
        doxygen_mappings = {
            # Core
            'classCloudMouse_1_1Core': 'core',
            'classCloudMouse_1_1EventBus': 'eventbus',
            'structCloudMouse_1_1Event': 'event',
            
            # Hardware
            'classCloudMouse_1_1Hardware_1_1DisplayManager': 'displaymanager',
            'classCloudMouse_1_1Hardware_1_1EncoderManager': 'encodermanager',
            'classCloudMouse_1_1Hardware_1_1LEDManager': 'ledmanager',
            'classCloudMouse_1_1Hardware_1_1SimpleBuzzer': 'simplebuzzer',
            'structCloudMouse_1_1Hardware_1_1LEDEvent': 'ledevent',
            'classRotaryEncoderPCNT': 'rotaryencoderpcnt',
            'classLGFX__ILI9488': 'lgfx_ili9488',
            
            # Network
            'classCloudMouse_1_1Network_1_1WiFiManager': 'wifimanager',
            'classCloudMouse_1_1Network_1_1WebServerManager': 'webservermanager',
            
            # Utils
            'classCloudMouse_1_1Utils_1_1DeviceID': 'deviceid',
            'classCloudMouse_1_1Utils_1_1JsonHelper': 'jsonhelper',
            'classCloudMouse_1_1Utils_1_1NTPManager': 'ntpmanager',
            'classCloudMouse_1_1Utils_1_1QRCodeManager': 'qrcodemanager',
            
            # Prefs
            'classCloudMouse_1_1Prefs_1_1PreferencesManager': 'preferencesmanager',
            
            # Config
            'DeviceConfig_8h': 'deviceconfig',
            'Events_8h': 'event',
            
            # Namespaces
            'namespaceCloudMouse': 'cloudmouse',
            'namespaceCloudMouse_1_1Hardware': 'hardware',
            'namespaceCloudMouse_1_1Network': 'network',
            'namespaceCloudMouse_1_1Utils': 'utils',
            'namespaceCloudMouse_1_1Prefs': 'prefs'
        }
        
        # Try direct mapping first
        if base_name in doxygen_mappings:
            mapped_name = doxygen_mappings[base_name]
            if mapped_name:
                result_filename = f"{mapped_name}.html"
                print(f"🗺️ Direct mapping: {doxygen_filename} → {result_filename}")
                return result_filename
            else:
                print(f"⚠️ Mapping exists but is None: {doxygen_filename}")
                return None  # No mapping available
        
        # Try pattern-based mapping for missed cases
        if base_name.startswith('class'):
            # Extract class name and convert to lowercase
            class_name = base_name.replace('class', '').replace('CloudMouse_1_1', '')
            simplified = class_name.lower()
            candidate = f"{simplified}.html"
            if candidate in self.slug_map:
                return candidate
        
        elif base_name.startswith('struct'):
            # Extract struct name and convert to lowercase  
            struct_name = base_name.replace('struct', '').replace('CloudMouse_1_1', '')
            simplified = struct_name.lower()
            candidate = f"{simplified}.html"
            if candidate in self.slug_map:
                return candidate
        
        elif base_name.endswith('_8h'):
            # Header file - convert to lowercase without _8h
            header_name = base_name.replace('_8h', '').lower()
            candidate = f"{header_name}.html"
            if candidate in self.slug_map:
                return candidate
        
        # No mapping found
        print(f"⚠️ No mapping found for: {doxygen_filename}")
        return None

    def fix_internal_links(self, html_content):
        """Fix internal links in HTML content to point to CMS slugs"""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            links_fixed = 0
            
            for link in soup.find_all('a', href=True):
                href = link['href']
                original_href = href
                
                # Handle anchors (#something in the same page)
                if href.startswith('#'):
                    continue  # Keep same-page anchors as-is
                
                print(f"🔍 Processing link: {href}")
                
                # Handle links to other HTML files
                if '#' in href:
                    # Link with anchor: "classDisplayManager.html#method-name"
                    file_part, anchor = href.split('#', 1)
                    print(f"  📎 Link with anchor - File: {file_part}, Anchor: {anchor}")
                    
                    # Map Doxygen filename to our simplified name
                    mapped_filename = self.map_doxygen_filename(file_part)
                    print(f"  🗺️ Mapped filename: {mapped_filename}")
                    
                    if mapped_filename and mapped_filename in self.slug_map:
                        new_href = f"{self.slug_map[mapped_filename]}#{anchor}"
                        link['href'] = new_href
                        links_fixed += 1
                        print(f"  ✅ Fixed link with anchor: {original_href} → {new_href}")
                    else:
                        print(f"  ❌ Could not map or find in slug_map: {file_part}")
                else:
                    # Simple file link: "classDisplayManager.html"
                    print(f"  📄 Simple file link: {href}")
                    
                    mapped_filename = self.map_doxygen_filename(href)
                    print(f"  🗺️ Mapped filename: {mapped_filename}")
                    
                    if mapped_filename and mapped_filename in self.slug_map:
                        new_href = self.slug_map[mapped_filename]
                        link['href'] = new_href
                        links_fixed += 1
                        print(f"  ✅ Fixed simple link: {original_href} → {new_href}")
                    else:
                        print(f"  ❌ Could not map or find in slug_map: {href}")
            
            if links_fixed > 0:
                print(f"🎉 Fixed {links_fixed} internal links in this page")
            else:
                print("ℹ️ No links were fixed in this page")
            
            return str(soup)
        except Exception as e:
            print(f"❌ Error fixing links: {e}")
            return html_content
        """Parse index.html to extract component titles and abstracts"""
        index_file = Path(clean_dir) / 'index.html'
        component_info = {}
        
        try:
            with open(index_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            soup = BeautifulSoup(content, 'html.parser')
            
            # Find all links to component files
            for link in soup.find_all('a', href=True):
                href = link.get('href')
                if href.endswith('.html') and href != 'index.html':
                    component_name = href.replace('.html', '')
                    
                    # Get the link text as title
                    title = link.get_text().strip()
                    
                    # Get the description after the " - " separator
                    parent_li = link.find_parent('li')
                    if parent_li:
                        full_text = parent_li.get_text().strip()
                        if ' - ' in full_text:
                            abstract = full_text.split(' - ', 1)[1].strip()
                        else:
                            abstract = title  # Fallback to title
                    else:
                        abstract = title
                    
                    component_info[component_name] = {
                        'title': title,
                        'abstract': abstract
                    }
                    print(f"📖 Parsed component: {component_name} - {title}")
            
            return component_info
        except Exception as e:
            print(f"❌ Error parsing index.html: {e}")
            return {}

    def parse_index_html(self, clean_dir):
        """Parse index.html to extract component titles and abstracts"""
        index_file = Path(clean_dir) / 'index.html'
        component_info = {}
        
        try:
            with open(index_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            soup = BeautifulSoup(content, 'html.parser')
            
            # Find all links to component files
            for link in soup.find_all('a', href=True):
                href = link.get('href')
                if href.endswith('.html') and href != 'index.html':
                    component_name = href.replace('.html', '')
                    
                    # Get the link text as title
                    title = link.get_text().strip()
                    
                    # Get the description after the " - " separator
                    parent_li = link.find_parent('li')
                    if parent_li:
                        full_text = parent_li.get_text().strip()
                        if ' - ' in full_text:
                            abstract = full_text.split(' - ', 1)[1].strip()
                        else:
                            abstract = title  # Fallback to title
                    else:
                        abstract = title
                    
                    component_info[component_name] = {
                        'title': title,
                        'abstract': abstract
                    }
                    print(f"📖 Parsed component: {component_name} - {title}")
            
            return component_info
        except Exception as e:
            print(f"❌ Error parsing index.html: {e}")
            return {}

    def get_next_category_ord(self, parent_id):
        """Get the next available ord value for categories under parent"""
        try:
            if parent_id:
                self.cursor.execute(
                    "SELECT COALESCE(MAX(ord), -1) + 1 as next_ord FROM categories WHERE parent_id = %s",
                    (parent_id,)
                )
            else:
                self.cursor.execute(
                    "SELECT COALESCE(MAX(ord), -1) + 1 as next_ord FROM categories WHERE parent_id IS NULL"
                )
            
            result = self.cursor.fetchone()
            next_ord = result['next_ord'] if result else 0
            print(f"📊 Next ord for parent {parent_id}: {next_ord}")
            return next_ord
        except Error as e:
            print(f"❌ Error getting next ord: {e}")
            return 0
    
    def get_root_category_id(self):
        """Get the ID of the existing root SDK category"""
        try:
            self.cursor.execute("SELECT id FROM categories WHERE name = %s", (SDK_ROOT_CATEGORY,))
            result = self.cursor.fetchone()
            
            if result:
                self.root_category_id = result['id']
                # Cache the root category path
                self.category_path_cache[self.root_category_id] = ['sdk']
                print(f"📁 Found existing root category '{SDK_ROOT_CATEGORY}' with ID: {self.root_category_id}")
                return self.root_category_id
            else:
                print(f"❌ Root category '{SDK_ROOT_CATEGORY}' not found in database")
                return None
        except Error as e:
            print(f"❌ Error finding root category: {e}")
            return None

    def create_category(self, name, uri, description, parent_id):
        """Create or update category"""
        try:
            # Check if category exists
            self.cursor.execute(
                "SELECT id FROM categories WHERE name = %s AND parent_id = %s", 
                (name, parent_id)
            )
            existing = self.cursor.fetchone()
            
            if existing:
                category_id = existing['id']
                print(f"📁 Category exists: {name}")
            else:
                # Get next ord value
                ord_value = self.get_next_category_ord(parent_id)
                
                # Create new category
                category_query = """
                INSERT INTO categories (name, module, template, published, parent_id, ord)
                VALUES (%s, %s, %s, %s, %s, %s)
                """
                self.cursor.execute(category_query, (name, self.module, self.template, 1, parent_id, ord_value))
                category_id = self.cursor.lastrowid
                print(f"🆕 Created category: {name} (ord: {ord_value})")
            
            # Create category content
            self.create_category_content(category_id, name, description, uri, parent_id)
            
            return category_id
        except Error as e:
            print(f"❌ Error creating category: {e}")
            return None
    
    def create_category_content(self, category_id, name, description, uri, parent_id):
        """Create or update category content"""
        try:
            # Cache the category path info for dry-run mode
            if hasattr(self, 'root_category_id') and parent_id == self.root_category_id:
                # Direct child of SDK, path is ['sdk', uri]
                self.category_path_cache[category_id] = ['sdk', uri]
                print(f"🧠 Cached path for {name} (ID: {category_id}): ['sdk', '{uri}']")
            elif parent_id in self.category_path_cache:
                # Child of cached category
                parent_path = self.category_path_cache[parent_id].copy()
                parent_path.append(uri)
                self.category_path_cache[category_id] = parent_path
                print(f"🧠 Cached path for {name} (ID: {category_id}): {parent_path}")
            else:
                # Fallback - try to get from DB
                parent_path = self.get_complete_category_path_from_db(parent_id)
                if parent_path:
                    parent_path.append(uri)
                else:
                    parent_path = ['sdk', uri]  # Fallback
                self.category_path_cache[category_id] = parent_path
                print(f"🧠 Cached path for {name} (ID: {category_id}): {parent_path}")
            
            # Build slug path using complete cached path
            slug_parts = [self.iso]
            
            # Get complete category path from cache
            if category_id in self.category_path_cache:
                category_path = self.category_path_cache[category_id]
                slug_parts.extend(category_path)
            else:
                # Fallback - shouldn't happen if cache is working correctly
                slug_parts.extend(['sdk', uri])
            
            slug = '/'.join(slug_parts)
            print(f"🛣️ Category slug: {slug}")

            
            # Create route
            route_id = self.create_route(slug, 'categories', category_id)
            if not route_id:
                return False
            
            # Check if content exists
            self.cursor.execute(
                "SELECT id FROM category_contents WHERE category_id = %s AND iso = %s",
                (category_id, self.iso)
            )
            existing = self.cursor.fetchone()
            
            meta_title = f"{name} - CloudMouse SDK"
            meta_descr = description
            meta_key = f"sdk, {name.lower()}"
            
            if existing:
                # Update existing content
                update_query = """
                UPDATE category_contents 
                SET name = %s, description = %s, uri = %s, meta_title = %s, meta_descr = %s, meta_key = %s, route_id = %s, active = %s
                WHERE category_id = %s AND iso = %s
                """
                self.cursor.execute(update_query, (name, description, uri, meta_title, meta_descr, meta_key, route_id, 1, category_id, self.iso))
                print(f"📝 Updated category content: {name}")
            else:
                # Create new content
                content_query = """
                INSERT INTO category_contents (iso, category_id, name, description, uri, meta_title, meta_descr, meta_key, route_id, active)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                self.cursor.execute(content_query, (self.iso, category_id, name, description, uri, meta_title, meta_descr, meta_key, route_id, 1))
                print(f"🆕 Created category content: {name}")
            
            return True
        except Error as e:
            print(f"❌ Error creating category content: {e}")
            return False
    
    def extract_title_from_html(self, html_content):
        """Extract title from HTML content"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Try to find h1 tag
        h1 = soup.find('h1')
        if h1:
            return h1.get_text().strip()
        
        # Try to find first heading
        for tag in ['h2', 'h3', 'h4']:
            heading = soup.find(tag)
            if heading:
                return heading.get_text().strip()
        
        # Fallback to filename
        return "Documentation"
    
    def create_page(self, name, category_id, uri, html_content, component_info=None):
        """Create or update page"""
        try:
            # Extract title from parsed info or HTML
            if component_info and uri in component_info:
                title = component_info[uri]['title']
            else:
                title = self.extract_title_from_html(html_content)
            
            # Check if page exists
            self.cursor.execute(
                "SELECT id FROM pages WHERE name = %s AND category_id = %s",
                (name, category_id)
            )
            existing = self.cursor.fetchone()
            
            if existing:
                page_id = existing['id']
                print(f"📄 Page exists: {name}")
                # Update content only
                self.update_page_content(page_id, title, html_content, uri, category_id, component_info)
            else:
                # Create new page
                page_query = """
                INSERT INTO pages (name, category_id, published, template)
                VALUES (%s, %s, %s, %s)
                """
                self.cursor.execute(page_query, (name, category_id, 1, self.template))
                page_id = self.cursor.lastrowid
                print(f"🆕 Created page: {name}")
                
                # Create page content
                self.create_page_content(page_id, title, html_content, uri, category_id, component_info)
            
            return page_id
        except Error as e:
            print(f"❌ Error creating page: {e}")
            return None
    
    def update_page_content(self, page_id, title, html_content, uri, category_id, component_info=None):
        """Update existing page content"""
        try:
            # Use parsed component info if available
            if component_info and uri in component_info:
                title = component_info[uri]['title']
                abstract = component_info[uri]['abstract']
                print(f"📖 Using parsed data for update - Title: {title}, Abstract: {abstract}")
            else:
                # Fallback to extracted title from HTML
                abstract = ""  # No abstract available
                print(f"⚠️ No parsed data for {uri}, using fallback title: {title}")
            
            # Build complete slug path for route update if needed
            slug_parts = [self.iso]
            category_path = self.get_complete_category_path(category_id)
            slug_parts.extend(category_path)
            slug_parts.append(uri)
            slug = '/'.join(slug_parts)
            
            # Add to slug map for link processing (without /en/ prefix)
            filename = f"{uri}.html"
            cms_slug = '/' + '/'.join(slug_parts[1:])  # Remove 'en' prefix
            self.slug_map[filename] = cms_slug
            print(f"🗺️ Mapped {filename} → {cms_slug}")
            
            print(f"🛣️ Updated slug: {slug}")
            
            meta_title = f"{title} - CloudMouse SDK"
            meta_key = f"sdk, {uri}"
            
            # Update content
            update_query = """
            UPDATE page_contents 
            SET title = %s, content = %s, abstract = %s, meta_title = %s, meta_key = %s
            WHERE page_id = %s AND iso = %s
            """
            self.cursor.execute(update_query, (title, html_content, abstract, meta_title, meta_key, page_id, self.iso))
            print(f"📝 Updated page content: {title}")
            return True
        except Error as e:
            print(f"❌ Error updating page content: {e}")
            return False
    
    def get_complete_category_path_from_db(self, category_id):
        """Get complete URI path from database only"""
        try:
            path = []
            current_id = category_id
            
            while current_id:
                self.cursor.execute("""
                    SELECT cc.uri, c.parent_id 
                    FROM category_contents cc 
                    JOIN categories c ON cc.category_id = c.id 
                    WHERE c.id = %s AND cc.iso = %s
                """, (current_id, self.iso))
                result = self.cursor.fetchone()
                
                if result:
                    uri = result['uri']
                    if uri:  # Only add if URI is not None/empty
                        path.insert(0, uri)
                    current_id = result['parent_id']
                else:
                    break
            
            return path
        except Error as e:
            print(f"❌ Error getting category path from DB: {e}")
            return []

    def get_complete_category_path(self, category_id):
        """Get complete URI path for category hierarchy - uses cache for dry-run mode"""
        # First try cache (for dry-run mode)
        if category_id in self.category_path_cache:
            cached_path = self.category_path_cache[category_id]
            print(f"🧠 Using cached path for category {category_id}: {cached_path}")
            return cached_path
        
        # Fallback to database
        db_path = self.get_complete_category_path_from_db(category_id)
        print(f"🔍 DB path for category {category_id}: {db_path}")
        return db_path

    def create_page_content(self, page_id, title, html_content, uri, category_id, component_info=None):
        """Create page content"""
        try:
            # Use parsed component info if available
            if component_info and uri in component_info:
                title = component_info[uri]['title']
                abstract = component_info[uri]['abstract']
                print(f"📖 Using parsed data - Title: {title}, Abstract: {abstract}")
            else:
                # Fallback to extracted title from HTML
                abstract = ""  # No abstract available
                print(f"⚠️ No parsed data for {uri}, using fallback title: {title}")
            
            # Build complete slug path: en/sdk/hardware-management/displaymanager
            slug_parts = [self.iso]
            
            # Get complete category hierarchy path
            category_path = self.get_complete_category_path(category_id)
            slug_parts.extend(category_path)
            
            # Add page URI
            slug_parts.append(uri)
            slug = '/'.join(slug_parts)
            
            # Add to slug map for link processing (without /en/ prefix)
            filename = f"{uri}.html"
            cms_slug = '/' + '/'.join(slug_parts[1:])  # Remove 'en' prefix
            self.slug_map[filename] = cms_slug
            print(f"🗺️ Mapped {filename} → {cms_slug}")
            
            print(f"🛣️ Generated slug: {slug}")
            
            # Create route
            route_id = self.create_route(slug, 'pages', page_id)
            if not route_id:
                return False
            
            meta_title = f"{title} - CloudMouse SDK"
            meta_key = f"sdk, {uri}"
            
            # Create page content
            content_query = """
            INSERT INTO page_contents (iso, page_id, route_id, title, content, abstract, uri, meta_title, meta_key, active)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            self.cursor.execute(content_query, (self.iso, page_id, route_id, title, html_content, abstract, uri, meta_title, meta_key, 1))
            print(f"🆕 Created page content: {title}")
            
            return True
        except Error as e:
            print(f"❌ Error creating page content: {e}")
            return False
    
    def post_process_links(self):
        """Post-process all imported pages to fix internal links"""
        try:
            print("🔗 Starting link post-processing...")
            
            if not self.slug_map:
                print("⚠️ No slug map available, skipping link processing")
                return True
            
            print(f"🗺️ Slug map contains {len(self.slug_map)} entries:")
            for filename, slug in self.slug_map.items():
                print(f"   {filename} → {slug}")
            
            # Get all imported page contents
            self.cursor.execute("""
                SELECT pc.id, pc.page_id, pc.content, pc.uri
                FROM page_contents pc
                JOIN pages p ON pc.page_id = p.id
                JOIN categories c ON p.category_id = c.id
                WHERE pc.iso = %s AND c.parent_id = (
                    SELECT id FROM categories WHERE name = %s
                )
            """, (self.iso, SDK_ROOT_CATEGORY))
            
            pages = self.cursor.fetchall()
            
            if not pages:
                print("⚠️ No pages found for link processing")
                return True
            
            print(f"📄 Processing links in {len(pages)} pages...")
            
            pages_updated = 0
            total_links_fixed = 0
            
            for page in pages:
                page_id = page['page_id']
                content = page['content']
                uri = page['uri']
                
                print(f"🔍 Processing links in page: {uri}")
                
                # Fix internal links
                fixed_content = self.fix_internal_links(content)
                
                # Update only if content changed
                if fixed_content != content:
                    update_query = """
                    UPDATE page_contents 
                    SET content = %s 
                    WHERE page_id = %s AND iso = %s
                    """
                    self.cursor.execute(update_query, (fixed_content, page_id, self.iso))
                    pages_updated += 1
                    print(f"📝 Updated page content for: {uri}")
                else:
                    print(f"✅ No links to fix in: {uri}")
            
            print(f"🎉 Link processing completed! Updated {pages_updated} pages")
            return True
            
        except Error as e:
            print(f"❌ Error in post-processing links: {e}")
            return False
        """Process all HTML files in clean directory"""
        clean_path = Path(clean_dir)
        
        if not clean_path.exists():
            print(f"❌ Clean directory not found: {clean_dir}")
            return False
        
        print(f"📁 Processing HTML files from: {clean_dir}")
        
        # Parse index.html for component titles and abstracts
        component_info = self.parse_index_html(clean_dir)
        if component_info:
            print(f"📚 Parsed {len(component_info)} components from index.html")
        else:
            print("⚠️ No component info parsed, using fallback titles")
        
        # Create category structure
        category_map = self.create_category_structure()
        
        # Process each HTML file
        html_files = list(clean_path.glob("*.html"))
        if not html_files:
            print("❌ No HTML files found in clean directory")
            return False
        
        # Exclude index.html from processing
        html_files = [f for f in html_files if f.name != 'index.html']
        
        processed_count = 0
        for html_file in html_files:
            component_name = html_file.stem  # filename without extension
            
            # Skip if this is index file
            if component_name == 'index':
                continue
            
            # Find which category this component belongs to
            category_id = self.find_component_category(component_name, category_map)
            if not category_id:
                print(f"⚠️ No category found for component: {component_name}")
                continue
            
            # Read HTML content
            with open(html_file, 'r', encoding='utf-8') as f:
                html_content = f.read()
            
            # Create/update page with component info
            page_id = self.create_page(component_name, category_id, component_name, html_content, component_info)
            if page_id:
                processed_count += 1
                print(f"✅ Processed: {component_name}")
            else:
                print(f"❌ Failed to process: {component_name}")
        
        print(f"🎉 Successfully processed {processed_count} components!")
        
        # Post-process links after all pages are imported
        if processed_count > 0:
            print("\n🔗 Starting link post-processing phase...")
            link_success = self.post_process_links()
            if not link_success:
                print("⚠️ Link post-processing failed, but pages were imported successfully")
        
        return True
    
    def process_html_files(self, clean_dir):
        """Process all HTML files in clean directory"""
        clean_path = Path(clean_dir)
        
        if not clean_path.exists():
            print(f"❌ Clean directory not found: {clean_dir}")
            return False
        
        print(f"📁 Processing HTML files from: {clean_dir}")
        
        # Parse index.html for component titles and abstracts
        component_info = self.parse_index_html(clean_dir)
        if component_info:
            print(f"📚 Parsed {len(component_info)} components from index.html")
        else:
            print("⚠️ No component info parsed, using fallback titles")
        
        # Create category structure
        category_map = self.create_category_structure()
        
        # Process each HTML file
        html_files = list(clean_path.glob("*.html"))
        if not html_files:
            print("❌ No HTML files found in clean directory")
            return False
        
        # Exclude index.html from processing
        html_files = [f for f in html_files if f.name != 'index.html']
        
        processed_count = 0
        for html_file in html_files:
            component_name = html_file.stem  # filename without extension
            
            # Skip if this is index file
            if component_name == 'index':
                continue
            
            # Find which category this component belongs to
            category_id = self.find_component_category(component_name, category_map)
            if not category_id:
                print(f"⚠️ No category found for component: {component_name}")
                continue
            
            # Read HTML content
            with open(html_file, 'r', encoding='utf-8') as f:
                html_content = f.read()
            
            # Create/update page with component info
            page_id = self.create_page(component_name, category_id, component_name, html_content, component_info)
            if page_id:
                processed_count += 1
                print(f"✅ Processed: {component_name}")
            else:
                print(f"❌ Failed to process: {component_name}")
        
        print(f"🎉 Successfully processed {processed_count} components!")
        
        # Post-process links after all pages are imported
        if processed_count > 0:
            print("\n🔗 Starting link post-processing phase...")
            link_success = self.post_process_links()
            if not link_success:
                print("⚠️ Link post-processing failed, but pages were imported successfully")
        
        return True

    def create_category_structure(self):
        """Create the complete category structure"""
        category_map = {}
        
        # Get existing root category
        root_id = self.get_root_category_id()
        if not root_id:
            print(f"❌ Cannot proceed without root category '{SDK_ROOT_CATEGORY}'")
            return {}
        
        # Create subcategories under existing root
        for sub_name, sub_data in SDK_STRUCTURE['subcategories'].items():
            sub_id = self.create_category(sub_name, sub_data['uri'], sub_data['description'], root_id)
            category_map[sub_name] = sub_id
            
            # Map components to subcategory
            for component in sub_data['components']:
                category_map[component] = sub_id
        
        return category_map
    
    def find_component_category(self, component_name, category_map):
        """Find the category ID for a component"""
        return category_map.get(component_name.lower())
    
    def commit_changes(self):
        """Commit database changes"""
        try:
            self.db.commit()
            print("💾 Database changes committed successfully")
            return True
        except Error as e:
            print(f"❌ Error committing changes: {e}")
            self.db.rollback()
            return False

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='Import CloudMouse SDK documentation to CMS')
    parser.add_argument('--clean-dir', required=True, help='Path to clean HTML directory')
    parser.add_argument('--dry-run', action='store_true', help='Preview changes without committing')
    
    args = parser.parse_args()
    
    print("🚀 CloudMouse SDK CMS Importer")
    print("===============================")
    print(f"📁 Clean HTML directory: {args.clean_dir}")
    print(f"🔧 Database: {DB_CONFIG['database']}@{DB_CONFIG['host']}")
    
    if args.dry_run:
        print("🧪 DRY RUN MODE - No changes will be committed")
    
    print()
    
    # Initialize importer
    importer = CMSImporter(DB_CONFIG)
    
    try:
        # Connect to database
        if not importer.connect_db():
            sys.exit(1)
        
        # Process HTML files
        success = importer.process_html_files(args.clean_dir)
        
        if success and not args.dry_run:
            # Commit changes
            importer.commit_changes()
        elif args.dry_run:
            print("🧪 Dry run completed - no changes committed")
        
    except KeyboardInterrupt:
        print("\n⚠️ Import interrupted by user")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
    finally:
        # Always disconnect
        importer.disconnect_db()
    
    print("\n🏁 Import process completed!")

if __name__ == "__main__":
    main()