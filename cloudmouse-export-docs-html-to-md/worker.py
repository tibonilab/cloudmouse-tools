#!/usr/bin/env python3
"""
Convert HTML from CMS to GitHub-flavored Markdown
Handles code blocks with syntax highlighting
"""

import re
import html2text
from pathlib import Path
import mysql.connector
import os
from dotenv import load_dotenv


def convert_html_to_markdown(html_content):
    """
    Convert HTML to Markdown handling code blocks correctly
    """
    
    # Step 1: Convert <pre><code class="language-XXX"> to markdown code blocks
    def replace_code_block(match):
        language = match.group(1) if match.group(1) else ''
        code = match.group(2)
        # Decode HTML entities in code
        code = code.replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&')
        code = code.replace('&quot;', '"').replace('&#39;', "'")
        return f"\n```{language}\n{code.strip()}\n```\n"
    
    # Pattern to capture pre/code with or without language
    pattern = r'<pre>\s*<code\s+class="language-([^"]+)"[^>]*>(.*?)</code>\s*</pre>'
    html_content = re.sub(pattern, replace_code_block, html_content, flags=re.DOTALL)
    
    # Handle code blocks without language specified
    pattern_no_lang = r'<pre>\s*<code[^>]*>(.*?)</code>\s*</pre>'
    html_content = re.sub(pattern_no_lang, replace_code_block, html_content, flags=re.DOTALL)
    
    # Step 2: Use html2text for the rest
    h = html2text.HTML2Text()
    h.body_width = 0  # No word wrap
    h.ignore_links = False
    h.ignore_images = False
    h.ignore_emphasis = False
    
    markdown = h.handle(html_content)
    
    # Step 3: Final cleanup
    # Remove excessive whitespace
    markdown = re.sub(r'\n{3,}', '\n\n', markdown)
    
    return markdown.strip()


def convert_internal_links(html_content, cms_service_host, uri_to_filename):
    """
    Convert internal CMS links to relative markdown file links
    """
    def replace_link(match):
        full_tag = match.group(0)
        href = match.group(1)
        
        # Only process links that start with CMS service host
        if cms_service_host and href.startswith(cms_service_host):
            # Get the last segment of the URL (after last /)
            url_segment = href.rstrip('/').split('/')[-1]
            
            # Check if this segment matches any URI in our exported pages
            if url_segment in uri_to_filename:
                # Replace entire href with just the markdown filename
                md_filename = uri_to_filename[url_segment]
                return full_tag.replace(href, md_filename)
        
        # Leave all other links unchanged
        return full_tag
    
    # Pattern to match href attributes in anchor tags
    pattern = r'<a\s+[^>]*href=["\']([^"\']+)["\'][^>]*>'
    html_content = re.sub(pattern, replace_link, html_content)
    
    return html_content


def clean_abstract(abstract):
    """
    Clean HTML from abstract, keeping only <br> tags converted to newlines
    """
    if not abstract:
        return ""
    
    # Replace <br> and <br/> tags with newlines
    abstract = re.sub(r'<br\s*/?>', '\n', abstract, flags=re.IGNORECASE)
    
    # Remove all other HTML tags
    abstract = re.sub(r'<[^>]+>', '', abstract)
    
    # Decode HTML entities
    abstract = abstract.replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&')
    abstract = abstract.replace('&quot;', '"').replace('&#39;', "'")
    abstract = abstract.replace('&nbsp;', ' ')
    
    return abstract.strip()


def process_file(input_file, output_file):
    """
    Process a single HTML file to Markdown
    """
    print(f"📄 Converting {input_file} → {output_file}")
    
    with open(input_file, 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    markdown = convert_html_to_markdown(html_content)
    
    # Create directory if it doesn't exist
    Path(output_file).parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(markdown)
    
    print(f"✅ Done!")


def process_directory(input_dir, output_dir):
    """
    Process all HTML files in a directory
    """
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    
    html_files = list(input_path.rglob('*.html'))
    
    print(f"🚀 Found {len(html_files)} HTML files to convert\n")
    
    for html_file in html_files:
        # Maintain directory structure
        relative_path = html_file.relative_to(input_path)
        md_file = output_path / relative_path.with_suffix('.md')
        
        process_file(html_file, md_file)
    
    print(f"\n🎉 All done! {len(html_files)} files converted!")


def export_from_database(output_dir, db_config=None):
    """
    Export contents from CMS MySQL database to Markdown
    """
    # Load config from .env if not provided
    if db_config is None:
        load_dotenv()
        db_config = {
            'host': os.getenv('DB_HOST', 'localhost'),
            'user': os.getenv('DB_USER', 'root'),
            'password': os.getenv('DB_PASS', ''),
            'database': os.getenv('DB_NAME', 'cloudmouse')
        }
    
    # Get CMS service host for link conversion
    cms_service_host = os.getenv('CMS_SERVICE_HOST', 'http://localhost/')
    
    print(f"🔌 Connecting to database {db_config['database']}@{db_config['host']}...")
    
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        
        query = """
            SELECT pages.ord, page_contents.uri, page_contents.title, 
                   page_contents.abstract, page_contents.content 
            FROM page_contents 
            JOIN pages ON pages.id = page_contents.page_id 
            WHERE pages.category_id = (SELECT id FROM categories WHERE name LIKE 'Docs')
            ORDER BY pages.ord ASC
        """
        
        cursor.execute(query)
        results = cursor.fetchall()
        
        print(f"📦 Found {len(results)} pages to export\n")
        
        # Build uri to filename mapping for internal links
        uri_to_filename = {}
        for row in results:
            ord_num = str(row['ord']).zfill(2)
            uri = row['uri']
            filename = f"{ord_num}_{uri.replace('-', '_')}.md"
            uri_to_filename[uri] = filename
        
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        for row in results:
            ord_num = str(row['ord']).zfill(2)
            uri = row['uri']
            title = row['title']
            abstract = row['abstract']
            content = row['content']
            
            # Convert uri to filename with zero-padded ord prefix
            filename = f"{ord_num}_{uri.replace('-', '_')}.md"
            output_file = output_path / filename
            
            print(f"📄 Converting [{ord_num}] {uri} → {filename}")
            
            # Convert internal links
            content = convert_internal_links(content, cms_service_host, uri_to_filename)
            
            # Convert HTML to Markdown
            markdown = convert_html_to_markdown(content)
            
            # Clean abstract from HTML
            cleaned_abstract = clean_abstract(abstract)
            
            # Prepend title (h1) and abstract (h3)
            final_markdown = f"# {title}\n\n"
            if cleaned_abstract:
                final_markdown += f"### {cleaned_abstract}\n\n"
            final_markdown += markdown
            
            # Save file
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(final_markdown)
            
            print(f"✅ Done!")
        
        cursor.close()
        conn.close()
        
        print(f"\n🎉 Export completed! {len(results)} files exported to {output_dir}")
        
    except mysql.connector.Error as err:
        print(f"❌ Database error: {err}")
        return False
    
    return True


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 2:
        print("Usage:")
        print("  Export from DB:  python html_to_markdown.py --export-db [output_dir]")
        print("                   (default output: ./markdown_docs/)")
        print("  Single file:     python html_to_markdown.py input.html output.md")
        print("  Directory:       python html_to_markdown.py input_dir/ output_dir/")
        print("\nFor DB export, create a .env file with:")
        print("  DB_HOST=localhost")
        print("  DB_NAME=cloudmouse")
        print("  DB_USER=root")
        print("  DB_PASS=yourpassword")
        print("  CMS_SERVICE_HOST=http://localhost/")
        sys.exit(1)
    
    # Export from database
    if sys.argv[1] == '--export-db':
        output_dir = sys.argv[2] if len(sys.argv) > 2 else './markdown_docs/'
        export_from_database(output_dir)
    # Single file or directory
    else:
        if len(sys.argv) < 3:
            print("❌ Specify both input and output!")
            sys.exit(1)
        
        input_path = sys.argv[1]
        output_path = sys.argv[2]
        
        if Path(input_path).is_dir():
            process_directory(input_path, output_path)
        else:
            process_file(input_path, output_path)