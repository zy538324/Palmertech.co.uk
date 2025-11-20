<!DOCTYPE html>
<html <?php language_attributes(); ?>>
<head>
    <meta charset="<?php bloginfo('charset'); ?>">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">

    <link rel="icon" type="image/svg+xml" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E%3Crect width='64' height='64' rx='12' fill='%23009688'/%3E%3Ctext x='50%25' y='58%25' text-anchor='middle' font-family='Arial' font-weight='700' font-size='28' fill='white'%3EPT%3C/text%3E%3C/svg%3E">

    <!-- SEO Metadata replicated from Flask layout -->
    <meta name="description" content="Hire Palmertech – an experienced UK freelance web developer creating high-performance websites, web apps, and mobile apps. We specialise in Python, Flask, PHP, JavaScript, and secure API development for small businesses and organisations across the UK.">
    <meta name="keywords" content="freelance web developer UK, web developer Somerset, website design UK, custom web app developer, Python Flask developer UK, mobile app developer UK, API integration specialist, website hosting and maintenance, Palmertech web development, hire web developer">
    <meta name="robots" content="index, follow, max-snippet:-1, max-image-preview:large, max-video-preview:-1">
    <link rel="canonical" href="https://palmertech.co.uk/">

    <!-- Open Graph -->
    <meta property="og:locale" content="en_GB">
    <meta property="og:type" content="website">
    <meta property="og:title" content="Palmertech | Expert UK Web Developer &amp; App Creator">
    <meta property="og:description" content="UK freelance web developer offering bespoke websites, web apps, and mobile app solutions. End-to-end support including hosting, security and maintenance.">
    <meta property="og:url" content="https://palmertech.co.uk/">
    <meta property="og:site_name" content="Palmertech">
    <meta property="og:image" content="https://palmertech.co.uk/static/og-image.webp">

    <!-- Twitter Card -->
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="Palmertech | UK Web Developer &amp; Web App Specialist">
    <meta name="twitter:description" content="Professional freelance UK web developer creating websites, web apps and mobile apps. Python, Flask, PHP, JavaScript &amp; API integrations.">
    <meta name="twitter:image" content="https://palmertech.co.uk/static/og-image.webp">

    <!-- Geo Meta Tags for Local SEO -->
    <meta name="geo.region" content="GB-ENG">
    <meta name="geo.placename" content="Somerset, United Kingdom">
    <meta name="geo.position" content="51.0211;-3.0986">
    <meta name="ICBM" content="51.0211, -3.0986">

    <!-- JSON-LD Schema for LocalBusiness + WebDevelopmentCompany -->
    <script type="application/ld+json">
    {
      "@context": "https://schema.org",
      "@type": "WebDevelopmentCompany",
      "name": "Palmertech",
      "url": "https://palmertech.co.uk/",
      "logo": "https://palmertech.co.uk/static/logo.png",
      "image": "https://palmertech.co.uk/static/og-image.webp",
      "description": "Palmertech is a UK-based freelance web development business delivering high-quality websites, scalable web apps, and mobile applications for clients across the UK.",
      "founder": {
        "@type": "Person",
        "name": "Matt Palmer",
        "jobTitle": "Lead Web Developer",
        "sameAs": [
          "https://www.linkedin.com/company/palmertech",
          "https://github.com/palmertech"
        ]
      },
      "address": {
        "@type": "PostalAddress",
        "addressLocality": "Wellington",
        "addressRegion": "Somerset",
        "addressCountry": "GB"
      },
      "areaServed": {"@type": "Country", "name": "United Kingdom"},
      "telephone": "+44 1823 000000",
      "email": "contact@palmertech.co.uk",
      "priceRange": "££",
      "serviceType": [
        "Website Development",
        "Web App Development",
        "Mobile App Development",
        "API Development",
        "Hosting & Domain Management",
        "Maintenance & Support"
      ]
    }
    </script>

    <?php wp_head(); ?>
</head>
<body <?php body_class(); ?>>
<header role="banner">
    <div class="hero">
        <div class="logo-mark" aria-hidden="true"><span>PT</span></div>
        <div class="hero-brand">
            <p class="brand-name">Palmertech</p>
            <p class="site-tagline">Professional Web Developer in Somerset, UK — Websites, Web Apps &amp; Mobile Apps</p>
        </div>
    </div>
    <nav class="navbar" role="navigation" aria-label="Primary">
        <button class="navbar-toggle" type="button" aria-expanded="false" aria-controls="primary-navigation">
            <span class="sr-only">Toggle navigation</span>
            <span class="navbar-toggle-bar"></span>
            <span class="navbar-toggle-bar"></span>
            <span class="navbar-toggle-bar"></span>
        </button>
        <?php
        wp_nav_menu([
            'theme_location' => 'primary',
            'container' => false,
            'menu_class' => 'nav-list',
            'menu_id' => 'primary-navigation',
            'fallback_cb' => function () {
                echo '<ul id="primary-navigation" class="nav-list">';
                wp_list_pages([
                    'title_li' => '',
                    'depth' => 1,
                ]);
                echo '</ul>';
            },
        ]);
        ?>
    </nav>
</header>
<main id="content" role="main">
