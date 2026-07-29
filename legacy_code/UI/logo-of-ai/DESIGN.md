---
name: Rail Assist Design System
colors:
  surface: '#f9f9ff'
  surface-dim: '#cfdaf2'
  surface-bright: '#f9f9ff'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f0f3ff'
  surface-container: '#e7eeff'
  surface-container-high: '#dee8ff'
  surface-container-highest: '#d8e3fb'
  on-surface: '#111c2d'
  on-surface-variant: '#45474d'
  inverse-surface: '#263143'
  inverse-on-surface: '#ecf1ff'
  outline: '#75777d'
  outline-variant: '#c5c6cd'
  surface-tint: '#535f75'
  primary: '#000000'
  on-primary: '#ffffff'
  primary-container: '#101c2f'
  on-primary-container: '#79849c'
  inverse-primary: '#bbc7e0'
  secondary: '#855300'
  on-secondary: '#ffffff'
  secondary-container: '#fea619'
  on-secondary-container: '#684000'
  tertiary: '#000000'
  on-tertiary: '#ffffff'
  tertiary-container: '#002113'
  on-tertiary-container: '#009668'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#d7e3fd'
  primary-fixed-dim: '#bbc7e0'
  on-primary-fixed: '#101c2f'
  on-primary-fixed-variant: '#3c475c'
  secondary-fixed: '#ffddb8'
  secondary-fixed-dim: '#ffb95f'
  on-secondary-fixed: '#2a1700'
  on-secondary-fixed-variant: '#653e00'
  tertiary-fixed: '#6ffbbe'
  tertiary-fixed-dim: '#4edea3'
  on-tertiary-fixed: '#002113'
  on-tertiary-fixed-variant: '#005236'
  background: '#f9f9ff'
  on-background: '#111c2d'
  surface-variant: '#d8e3fb'
typography:
  display-lg:
    fontFamily: Manrope
    fontSize: 48px
    fontWeight: '800'
    lineHeight: 56px
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Manrope
    fontSize: 32px
    fontWeight: '700'
    lineHeight: 40px
    letterSpacing: -0.01em
  headline-lg-mobile:
    fontFamily: Manrope
    fontSize: 24px
    fontWeight: '700'
    lineHeight: 32px
  headline-md:
    fontFamily: Manrope
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
  title-lg:
    fontFamily: Inter
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 28px
  body-lg:
    fontFamily: Inter
    fontSize: 18px
    fontWeight: '400'
    lineHeight: 28px
  body-md:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  body-sm:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  label-md:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '600'
    lineHeight: 16px
    letterSpacing: 0.05em
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  base: 8px
  xs: 4px
  sm: 12px
  md: 24px
  lg: 40px
  xl: 64px
  gutter: 24px
  margin-mobile: 16px
  margin-desktop: 48px
---

## Brand & Style
The design system is engineered for **Rail Assist**, an enterprise-grade AI platform supporting the vast infrastructure of Indian Railways. The brand personality is **authoritative, dependable, and technologically advanced**. It avoids the flighty aesthetics of consumer startups in favor of a "Government-Modern" style—an evolution of institutional design that feels reliable and high-performance.

The visual direction follows a **Modern Corporate** movement. It utilizes high-density information layouts balanced by precise whitespace, conveying a sense of organized scale. The emotional response should be one of absolute trust; the user must feel that the AI is grounded in the stability of a physical institution while offering the speed of modern computation.

Key stylistic markers:
- **Institutional Weight:** Large, solid color blocks of deep navy to anchor the interface.
- **Precision Accents:** Use of amber to highlight critical path actions and AI-driven insights.
- **Safety & Clarity:** Clear visual hierarchies that reduce cognitive load during complex travel or logistics coordination.

## Colors
The palette is rooted in a "Deep Sea and Sunlight" contrast. The primary Navy (#0B172A) provides a professional, "Uniform" feel, while the Amber (#F59E0B) acts as a functional signal for attention, echoing the importance of safety and punctuality in rail travel.

- **Primary (Navy):** Used for sidebars, primary buttons, and structural headers. It represents the "Rail" authority.
- **Accent (Amber):** Used for AI notifications, active status indicators, and primary CTAs that require user focus.
- **Background & Surface:** A layered approach using #F8FAFC for the base canvas and pure #FFFFFF for cards and content containers to ensure maximum contrast.
- **Semantic Colors:** Success (Green), Warning (Amber), and Danger (Red) follow standard accessibility patterns to ensure safety-critical information is never missed.

## Typography
This design system employs a dual-font strategy. **Manrope** is used for headlines to provide a modern, slightly technical character with its geometric roots. **Inter** is used for all body, UI, and data-heavy text to ensure maximum legibility at small sizes, particularly for PNR numbers, schedules, and technical logs.

- **Headlines:** Use Bold or ExtraBold weights to establish clear hierarchy against the primary Navy background.
- **Data Display:** For tabular data or AI logs, `body-sm` or `body-md` in Inter is the standard.
- **Labels:** Small caps with slight letter spacing are used for secondary metadata to distinguish it from interactive text.

## Layout & Spacing
The layout follows a **Fluid Grid** system with a focus on "Generous Professionalism." While enterprise tools often cram data, this system uses strategic padding to ensure the AI's suggestions are digestible.

- **Grid:** A 12-column grid on desktop, transitioning to 4 columns on mobile.
- **Rhythm:** An 8px base unit governs all dimensions.
- **Containers:** Content is typically grouped in cards with `md` (24px) internal padding.
- **Safe Areas:** On mobile, a minimum side margin of 16px is enforced. On large desktops, the content is capped at 1440px width to prevent line lengths from becoming unreadable.

## Elevation & Depth
Depth is used sparingly to maintain a clean, official look. We avoid heavy skeuomorphism in favor of **Ambient Shadows** and **Tonal Layers**.

- **Level 0 (Base):** #F8FAFC background.
- **Level 1 (Surface):** White cards with a very soft, diffused shadow (0px 4px 20px rgba(11, 23, 42, 0.05)).
- **Level 2 (Hover/Active):** Slightly more pronounced shadow (0px 8px 30px rgba(11, 23, 42, 0.08)).
- **AI Focus:** Elements generated or highlighted by AI may use a subtle Amber outer glow or a 1px solid Amber border to lift them from the standard UI hierarchy.

## Shapes
The shape language is "Approachable Geometric." We use a standard 12px (`rounded-lg`) corner radius for most UI elements, which balances the seriousness of the brand with modern software expectations.

- **Standard Elements:** 8px radius for buttons and input fields.
- **Main Containers:** 12px to 16px radius for cards and modals.
- **Status Pills:** Fully rounded (capsule) for quick visual scanning of status.

## Components

### Buttons
- **Primary:** Solid Navy (#0B172A) with white text. 8px border radius.
- **Accent:** Solid Amber (#F59E0B) with Navy text for the most important "Action" of the page (e.g., "Book Ticket" or "Emergency Alert").
- **Secondary:** Transparent background with a 1.5px Navy border.

### Cards
- Always white surface. 12px rounded corners. Use a 1px #E2E8F0 border for definition on light backgrounds instead of heavy shadows.

### Input Fields
- Structured with a clear label in `label-md`. 8px rounded corners. Use a 1px border that turns Navy on focus. 

### Chips & Badges
- Used for train types (Shatabdi, Rajdhani) or status. Use a "Soft Tonal" style: a light tint of the status color with high-contrast text (e.g., Light Green background with Dark Green text).

### AI Suggestions
- Components specifically for AI-generated content should feature a subtle gradient border (Navy to Amber) or a unique background tint (#FFFBEB) to clearly distinguish machine-generated assistance from static system data.

### Lists
- High-density but clear. Use 16px vertical padding between list items and a subtle #F1F5F9 divider line.