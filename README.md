# CloudMouse Tools 🐭⚡

Toolkit for CloudMouse SDK: device provisioning and automatic documentation generation.

## 📦 Contents

- **cloudmouse-provisioning**: ESP32 firmware flashing and device database registration
- **cloudmouse-docs-generator**: Automatic Doxygen documentation generation with CMS import

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
```

### 2. Install dependencies
```bash
pip install beautifulsoup4 mysql-connector-python
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

## 🔐 Security

`config.json` files contain sensitive credentials and are in `.gitignore`.

**Never commit:**
- `config.json`
- Files with passwords or API keys
- Sensitive production data

## 📝 Notes

- Doxygen must be installed to generate documentation
- Tools assume MySQL/MariaDB database
- CMS structure must have a root "SDK" category

## 🎯 Complete Quick Start
```bash
# Clone repo
git clone <your-repo>
cd cloudmouse-tools

# Setup configs
cp cloudmouse-provisioning/config.example.json cloudmouse-provisioning/config.json
cp cloudmouse-docs-generator/config.example.json cloudmouse-docs-generator/config.json

# Edit both config.json with your credentials

# Flash a device
cd cloudmouse-provisioning
python flash_and_register.py --port /dev/ttyUSB0 --firmware firmware.bin

# Generate docs
cd ../cloudmouse-docs-generator
./generate_docs.sh
python clean_doxygen.py ./docs/html ./docs/clean
python import_to_cms.py --clean-dir ./docs/clean
```

## 🤝 Contributing

Pull requests welcome! For major changes, please open an issue first.

## 📄 License

MIT

---

Made with ⚡ for CloudMouse SDK