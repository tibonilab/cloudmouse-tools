# CloudMouse Tools 🐭⚡

Toolkit for CloudMouse SDK: device provisioning, automatic documentation generation, and documentation export.

## 📦 Contents

- **cloudmouse-provisioning**: ESP32 firmware flashing and device database registration
- **cloudmouse-docs-generator**: Automatic Doxygen documentation generation with CMS import
- **cloudmouse-docs-exporter**: CMS documentation export to GitHub-flavored Markdown

## 🚀 Quick Setup

### 1. Configure database credentials

Copy example files and fill with your credentials:

```bash
# For provisioning
cd cloudmouse-provisioning
cp config.example.json config.json
# Edit config.json with your credentials

# For docs generator
cd ../cloudmouse-docs-generator
cp config.example.json config.json
# Edit config.json with your credentials

# For docs exporter
cd ../cloudmouse-docs-exporter
cp .env.example .env
# Edit .env with your credentials
```

### 2. Install dependencies

```bash
# Base dependencies
pip install beautifulsoup4 mysql-connector-python

# For docs exporter
pip install html2text python-dotenv
```

## 🔧 Device Provisioning

Flash firmware to ESP32 and automatically register device ID to database.

```bash
cd cloudmouse-provisioning
python flash_and_register.py --port /dev/ttyUSB0 --firmware path/to/firmware.bin
```

**Features:**
- Automatic ESP32 firmware flashing
- Hardware ID extraction
- Automatic database registration
- Integrity and connection verification

## 📚 Documentation Generation

Complete pipeline: Doxygen → Clean HTML → Automatic CMS import.

```bash
cd cloudmouse-docs-generator

# 1. Generate Doxygen docs (edit Doxyfile for your project)
./generate_docs.sh

# 2. Clean HTML for CMS
python clean_doxygen.py ./docs/html ./docs/clean

# 3. Automatic CMS import
python import_to_cms.py --clean-dir ./docs/clean
```

**Features:**
- Doxygen navigation and styling removal
- Documentation structure preservation
- Automatic CMS category organization
- Automatic internal link fixing
- Hierarchical namespace support

## 📤 Documentation Export

Export CMS documentation to GitHub-flavored Markdown for public repository.

```bash
cd cloudmouse-docs-exporter

# Setup environment
cp .env.example .env
# Edit .env with your database credentials and CMS host

# Export to Markdown
python html_to_markdown.py --export-db
# Or specify custom output directory
python html_to_markdown.py --export-db ./output/
```

**Features:**
- HTML to Markdown conversion with code block preservation
- Automatic title and abstract extraction
- Internal link conversion to relative Markdown files
- Zero-padded file ordering (01, 02, 03...)
- GitHub-ready output

**Workflow:**
```
CMS (source of truth)
  ↓
Export to Markdown
  ↓
Commit & Push to GitHub
  ↓
Public documentation repository
```

### Configuration

Create `.env` file in `cloudmouse-docs-exporter/`:

```bash
DB_HOST=localhost
DB_NAME=cloudmouse
DB_USER=root
DB_PASS=yourpassword
CMS_SERVICE_HOST=http://localhost/
```

### Additional Usage

```bash
# Convert single HTML file to Markdown
python html_to_markdown.py input.html output.md

# Convert entire directory
python html_to_markdown.py ./html_files/ ./markdown_files/
```

**Output Format:**

Each exported file contains:
- `# Title` (h1) from `page_contents.title`
- `### Abstract` (h3) from `page_contents.abstract`
- Converted content with preserved code blocks
- Relative links to other documentation files

**File Naming:**
- Format: `{order}_{uri}.md`
- Example: `01_introduction.md`, `02_getting_started.md`
- Order preserved from database for correct sequencing

## 🔐 Security

`config.json` and `.env` files contain sensitive credentials and are in `.gitignore`.

**Never commit:**
- `config.json`
- `.env`
- Files with passwords or API keys
- Sensitive production data

## 📝 Notes

- [Doxygen](https://www.doxygen.nl/) must be installed to generate documentation
- Tools assume MySQL/MariaDB database
- CMS structure must have a root "SDK" category for docs generator
- CMS import tool is for [tibonilab/managee](https://github.com/tibonilab/managee)
- Docs exporter requires Python 3.7+

## 🎯 Complete Quick Start

```bash
# Clone repo
git clone <your-repo>
cd cloudmouse-tools

# Setup configs
cp cloudmouse-provisioning/config.example.json cloudmouse-provisioning/config.json
cp cloudmouse-docs-generator/config.example.json cloudmouse-docs-generator/config.json
cp cloudmouse-docs-exporter/.env.example cloudmouse-docs-exporter/.env
# Edit all config files with your credentials

# Flash a device
cd cloudmouse-provisioning
python flash_and_register.py --port /dev/ttyUSB0 --firmware firmware.bin

# Generate and import API docs
cd ../cloudmouse-docs-generator
./generate_docs.sh
python clean_doxygen.py ./docs/html ./docs/clean
python import_to_cms.py --clean-dir ./docs/clean

# Export docs to GitHub
cd ../cloudmouse-docs-exporter
python html_to_markdown.py --export-db ./markdown_docs/
# Then commit and push to your public docs repository
```

## 🔄 Documentation Pipeline

Complete documentation flow:

```
1. Write code with Doxygen comments
   ↓
2. Generate with cloudmouse-docs-generator
   ↓
3. Import to CMS (private, editable)
   ↓
4. Edit/enhance in CMS if needed
   ↓
5. Export with cloudmouse-docs-exporter
   ↓
6. Push to public GitHub repository
   ↓
7. Community can read and contribute via issues/PRs
```

## 🤝 Contributing

Pull requests welcome! For major changes, please open an issue first.

## 📄 License

MIT

---

Made with ⚡ for CloudMouse SDK