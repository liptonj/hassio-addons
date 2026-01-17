# Frontend Quick Start Guide

## Installation

```bash
cd frontend

# Install dependencies
npm install

# Install testing dependencies
npm install -D vitest @testing-library/react @testing-library/jest-dom @testing-library/user-event jsdom
npm install -D playwright @playwright/test

# Install Playwright browsers
npx playwright install
```

## Development

```bash
# Start development server
npm run dev

# Server will start at http://localhost:5173
```

## Testing

```bash
# Run unit tests
npm run test

# Run tests in watch mode
npm run test:watch

# Generate coverage report
npm run test:coverage

# Run E2E tests
npm run test:e2e

# Run E2E tests with UI
npm run test:e2e:ui
```

## Building

```bash
# Build for production
npm run build

# Preview production build
npm run preview
```

## New Features Overview

### Components
- **AcceptableUseAgreement** - Display AUP with checkbox and modal
- **PSKCustomizer** - Custom WiFi password with strength indicator
- **CustomFieldRenderer** - Dynamic registration fields
- **QRCodeActions** - Enhanced QR with print/download/share
- **DeviceProvisioningPrompt** - Device-specific setup instructions
- **DeviceCard/DeviceList** - Device management
- **ChangePasswordForm** - Account password change
- **ChangePSKForm** - WiFi password change

### Pages
- **UniversalLogin** (`/login`) - Email-first login
- **UserAccount** (`/user-account`) - Account dashboard

### Utilities
- **captivePortal** - Detect captive portal browsers
- **deviceDetection** - Device type and capabilities
- **printQRCode** - Print-friendly QR generation
- **pskValidation** - WPA2 password validation

## Testing New Features

### Registration with AUP
1. Navigate to `/register`
2. Fill in name and email
3. Accept AUP checkbox (if enabled)
4. Choose custom WiFi password (if enabled)
5. Fill custom fields (if configured)
6. Submit and verify success page

### Universal Login
1. Navigate to `/login`
2. Enter email address
3. System determines auth method
4. Follow password or SSO flow
5. Redirect to user account

### User Account Management
1. Sign in to account
2. Navigate to `/user-account`
3. View WiFi tab for credentials and QR
4. View Devices tab to manage devices
5. View Security tab to change passwords

### QR Code Actions
1. On success or account page
2. Click "Print" to open print view
3. Click "Download" to save PNG
4. Click "Share" to generate public URL
5. Copy shared URL to clipboard

## Configuration

Backend must return extended options from `/api/options`:

```typescript
{
  // Existing fields...
  
  // New fields
  aup_enabled: true,
  aup_text: "Your AUP text here",
  aup_url: "https://example.com/aup", // optional
  aup_version: 1,
  
  custom_fields: [
    {
      id: "unit_number",
      label: "Unit Number",
      type: "text",
      required: true
    }
  ],
  
  allow_custom_psk: true,
  psk_requirements: {
    min_length: 8,
    max_length: 63
  },
  
  universal_login_enabled: true,
  show_login_method_selector: false
}
```

## Mobile Testing

### iOS Simulator
```bash
# With iOS simulator running
npm run test:e2e -- --project="Mobile Safari"
```

### Android Emulator
```bash
# With Android emulator running
npm run test:e2e -- --project="Mobile Chrome"
```

### Physical Devices
1. Get local IP: `ipconfig getifaddr en0`
2. Update vite config with host: `0.0.0.0`
3. Access from device: `http://YOUR_IP:5173`

## Troubleshooting

### Tests Failing
```bash
# Clear test cache
npm run test:clear

# Update snapshots
npm run test -- -u
```

### Build Errors
```bash
# Clear node_modules and reinstall
rm -rf node_modules package-lock.json
npm install
```

### Type Errors
```bash
# Check TypeScript
npx tsc --noEmit
```

## Performance Tips

1. **Lazy Loading**: Routes are already code-split
2. **Images**: Use WebP format with fallbacks
3. **Caching**: Service worker ready (add if needed)
4. **Bundle Size**: Run `npm run build -- --analyze`

## Accessibility

All components follow WCAG 2.1 AA standards:
- ✅ Keyboard navigation
- ✅ Screen reader support
- ✅ ARIA labels
- ✅ Color contrast ratios
- ✅ Touch target sizes (44x44px)

## Browser Support

- **Modern**: Chrome 90+, Firefox 88+, Safari 14+, Edge 90+
- **Mobile**: iOS Safari 14+, Chrome Mobile 90+
- **Tested**: iPhone, iPad, Android phones/tablets
- **Captive Portals**: iOS, Android, macOS

## Next Steps

1. ✅ All components implemented
2. ✅ All tests passing
3. ✅ Mobile optimized
4. ⏳ Backend API integration
5. ⏳ Production deployment

## Support

For issues or questions:
1. Check `IMPLEMENTATION_COMPLETE.md` for details
2. Review component prop interfaces
3. Check test files for usage examples
4. Verify backend API endpoints match spec

---

**Status**: ✅ Ready for backend integration and production deployment
