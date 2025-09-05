# Frontend Design Brief

## Design Philosophy

Based on the preferred UI styling examples, this application follows a **sophisticated dark-mode-first design system** with emphasis on clarity, hierarchy, and professional aesthetics.

## Core Design Principles

### 1. Color Palette

- **Background**: Pure black (#000000) to near-black (#0A0A0A)
- **Surface**: Dark gray cards (#111111 to #1A1A1A) with subtle borders
- **Borders**: Very subtle gray (#2A2A2A to #333333)
- **Text Hierarchy**:
  - Primary: Pure white (#FFFFFF)
  - Secondary: Light gray (#A0A0A0 to #888888)
  - Muted: Dark gray (#666666)
- **Accent Colors**:
  - Primary Accent: Mellow red (#DC2626 to #EF4444) - used sparingly for CTAs and highlights
  - Secondary: Subtle warm tones (#FCA5A5 for lighter red hints)
- **Gradients**:
  - Subtle radial gradients from dark center to slightly lighter edges
  - Text gradients: Subtle white-to-gray for headers
  - Background meshes: Very subtle red-to-black gradients for accent sections

### 2. Typography

- **Font Family**: System fonts with fallbacks
  - Sans-serif: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial
  - Monospace: "SF Mono", Monaco, "Cascadia Code", "Roboto Mono", Consolas
- **Font Sizes**:
  - Display: 48-64px (hero headings)
  - H1: 36-40px
  - H2: 28-32px
  - H3: 20-24px
  - Body: 14-16px
  - Small: 12-14px
- **Font Weight**: Light (300) to Medium (500), avoiding heavy weights
- **Line Height**: Generous (1.5-1.7 for body text)

### 3. Layout & Spacing

- **Container**: Centered with max-width (typically 1200px)
- **Grid**: 3-column card layouts for feature sections
- **Spacing Scale**:
  - xs: 4px
  - sm: 8px
  - md: 16px
  - lg: 24px
  - xl: 32px
  - 2xl: 48px
  - 3xl: 64px
- **Card Padding**: Generous internal padding (24-32px)
- **Section Spacing**: Large breathing room between sections (64-96px)

### 4. Component Patterns

#### Cards

```css
.card {
  background: #111111;
  border: 1px solid #2A2A2A;
  border-radius: 8px;
  padding: 24px;
  transition: all 0.2s ease;
}

.card:hover {
  border-color: #444444;
  transform: translateY(-2px);
}
```

#### Buttons

```css
.button-primary {
  background: linear-gradient(135deg, #EF4444 0%, #DC2626 100%);
  color: #FFFFFF;
  padding: 12px 24px;
  border-radius: 6px;
  font-weight: 500;
  transition: all 0.2s ease;
  box-shadow: 0 0 20px rgba(239, 68, 68, 0.3);
}

.button-primary:hover {
  background: linear-gradient(135deg, #F87171 0%, #EF4444 100%);
  box-shadow: 0 0 30px rgba(239, 68, 68, 0.4);
}

.button-secondary {
  background: transparent;
  color: #FFFFFF;
  border: 1px solid #333333;
  padding: 12px 24px;
  border-radius: 6px;
  transition: all 0.2s ease;
}

.button-secondary:hover {
  border-color: #DC2626;
  color: #EF4444;
}
```

#### Form Inputs

```css
.input {
  background: #0A0A0A;
  border: 1px solid #2A2A2A;
  color: #FFFFFF;
  padding: 12px 16px;
  border-radius: 6px;
  font-size: 14px;
}

.input:focus {
  border-color: #666666;
  outline: none;
}
```

### 5. Visual Hierarchy

- **Minimal chrome**: Remove unnecessary UI elements
- **Clear sections**: Distinct content blocks with clear boundaries
- **Progressive disclosure**: Show information as needed
- **Iconography**: Simple, monochrome icons (preferably outline style)

### 6. Gradients & Visual Effects

- **Background gradients**:
  - Radial gradients from lighter center to darker edges for depth
  - Subtle red gradient overlays for accent sections
  - Mesh gradients for hero sections
- **Button gradients**: Red gradient for primary CTAs (135deg angle)
- **Text gradients**: Occasional use for large display text
- **Glow effects**: Subtle red glow on hover for interactive elements
- **Border gradients**: Gradient borders for premium/highlighted content

### 7. Animation & Interactions

- **Subtle transitions**: 0.2s ease for most interactions
- **Hover states**: Slight brightness/border changes, red accent appears
- **Loading states**: Skeleton screens with subtle shimmer
- **Glow animations**: Soft pulsing red glow for active states
- **No aggressive animations**: Maintain professional feel

## Implementation Guidelines

### Tailwind CSS Configuration

```javascript
// tailwind.config.js
module.exports = {
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        background: '#000000',
        surface: {
          DEFAULT: '#111111',
          hover: '#1A1A1A',
        },
        border: {
          DEFAULT: '#2A2A2A',
          hover: '#444444',
        },
        text: {
          primary: '#FFFFFF',
          secondary: '#A0A0A0',
          muted: '#666666',
        },
        accent: {
          red: {
            DEFAULT: '#EF4444',
            dark: '#DC2626',
            light: '#FCA5A5',
            muted: '#991B1B',
          }
        }
      },
      backgroundImage: {
        'gradient-radial': 'radial-gradient(var(--tw-gradient-stops))',
        'gradient-radial-dark': 'radial-gradient(circle at center, #111111 0%, #000000 100%)',
        'gradient-red-subtle': 'linear-gradient(135deg, rgba(239, 68, 68, 0.1) 0%, transparent 100%)',
      },
      fontFamily: {
        sans: ['-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'Helvetica Neue', 'Arial', 'sans-serif'],
        mono: ['SF Mono', 'Monaco', 'Cascadia Code', 'Roboto Mono', 'Consolas', 'monospace'],
      },
    },
  },
}
```

### Component Structure

```tsx
// Example Card Component
export function FeatureCard({ icon, title, description }: FeatureCardProps) {
  return (
    <div className="bg-surface border border-border rounded-lg p-6 hover:border-border-hover transition-all duration-200 hover:-translate-y-0.5">
      <div className="mb-4 text-text-secondary">
        {icon}
      </div>
      <h3 className="text-xl font-medium text-text-primary mb-2">
        {title}
      </h3>
      <p className="text-text-secondary text-sm leading-relaxed">
        {description}
      </p>
    </div>
  );
}
```

## Page-Specific Styling

### Dashboard

- Left sidebar navigation (dark surface)
- Main content area with card-based layout
- Minimal header with user info

### Job Listings

- Card grid layout (2-3 columns)
- Each card with company, title, location, match score
- Subtle hover effects for interactivity

### Resume/Profile

- Clean form layouts with dark inputs
- Section dividers with subtle borders
- Progress indicators for completion

### Landing/Auth Pages

- Centered content with hero messaging
- Minimal form design
- High contrast CTAs

## Accessibility Considerations

- **Contrast ratios**: Ensure WCAG AA compliance
- **Focus indicators**: Visible but subtle focus rings
- **Keyboard navigation**: Full keyboard support
- **Screen readers**: Proper ARIA labels and semantic HTML

## Do's and Don'ts

### Do's ✅

- Use plenty of whitespace
- Maintain consistent spacing
- Keep interactions subtle
- Use system fonts for performance
- Implement smooth transitions
- Follow the established color palette

### Don'ts ❌

- Don't use bright colors unnecessarily
- Avoid heavy drop shadows
- Don't use excessive animations
- Avoid cluttered layouts
- Don't mix light and dark themes inconsistently
- Avoid using pure white on pure black (use slight off-whites/grays)

## Reference Implementation

The design system is inspired by modern SaaS applications with dark themes, emphasizing:

- Professional appearance suitable for career-focused application
- High readability and clear information hierarchy
- Minimal cognitive load through consistent patterns
- Modern, sophisticated aesthetic that appeals to tech-savvy users

---

This design brief should be referenced throughout development to maintain visual consistency across all frontend components.
