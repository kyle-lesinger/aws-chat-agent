# Static Media Directory

This directory contains static assets for the AWS Agent Chat interface.

## Directory Structure

```
static/
├── images/          # Image files (logos, icons, etc.)
│   └── logo.png     # Main logo file (place your logo here)
├── css/            # Custom CSS files (if needed)
└── js/             # Custom JavaScript files (if needed)
```

## Adding Your Logo

1. Place your logo image in the `images/` directory
2. Recommended formats: PNG, SVG, or JPG
3. Recommended size: 60x60px or larger (will be scaled down)
4. Update the HTML in `/src/aws_agent/chat/server.py` to use your logo:

```html
<!-- Replace the logo placeholder content with: -->
<img src="/static/images/logo.png" alt="AWS Agent Logo" style="width: 100%; height: 100%; object-fit: contain;">
```

## Logo Options in server.py

The server.py file includes three logo options:

1. **Text Logo** (default) - Simple text display
2. **Image Logo** - Uncomment and update the path to use your image
3. **SVG Logo** - Uncomment to use the inline SVG design

Edit lines 109-123 in `/src/aws_agent/chat/server.py` to switch between options.