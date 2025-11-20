<?php
/**
 * Theme bootstrap for Palmertech WP.
 */

declare(strict_types=1);

// Prevent direct access for security.
if (!defined('ABSPATH')) {
    exit;
}

/**
 * Set up theme defaults and register support for various WordPress features.
 */
function palmertech_setup(): void {
    add_theme_support('title-tag');
    add_theme_support('post-thumbnails');

    register_nav_menus([
        'primary' => __('Primary Navigation', 'palmertech-wp'),
    ]);
}
add_action('after_setup_theme', 'palmertech_setup');

/**
 * Enqueue theme styles and scripts with cache busting.
 */
function palmertech_enqueue_assets(): void {
    $theme_version = wp_get_theme()->get('Version');
    $asset_version = $theme_version;

    $theme_css = get_template_directory() . '/assets/css/theme.css';
    if (file_exists($theme_css)) {
        $asset_version = (string) filemtime($theme_css);
    }

    // Primary stylesheet.
    wp_enqueue_style('palmertech-theme', get_template_directory_uri() . '/assets/css/theme.css', [], $asset_version);

    // Font Awesome for icons.
    wp_enqueue_style(
        'palmertech-fontawesome',
        'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css',
        [],
        '6.4.0'
    );

    // Main interaction script.
    $theme_js = get_template_directory() . '/assets/js/theme.js';
    $script_version = file_exists($theme_js) ? (string) filemtime($theme_js) : $asset_version;
    wp_enqueue_script('palmertech-theme', get_template_directory_uri() . '/assets/js/theme.js', [], $script_version, true);
}
add_action('wp_enqueue_scripts', 'palmertech_enqueue_assets');

/**
 * Register custom image sizes for hero and portfolio previews.
 */
function palmertech_image_sizes(): void {
    add_image_size('palmertech-hero', 1440, 600, true);
}
add_action('after_setup_theme', 'palmertech_image_sizes');

/**
 * Add dropdown helper classes to menu items so CSS/JS mirrors the Flask layout.
 */
function palmertech_nav_menu_css_class(array $classes, $item, $args, int $depth): array {
    if (in_array('menu-item-has-children', $classes, true)) {
        $classes[] = 'dropdown';
    }

    return $classes;
}
add_filter('nav_menu_css_class', 'palmertech_nav_menu_css_class', 10, 4);

/**
 * Add dropbtn class to anchors for parent menu items.
 */
function palmertech_nav_menu_link_attributes(array $atts, $item, $args, int $depth): array {
    $item_classes = $item->classes ?? [];
    if (in_array('menu-item-has-children', $item_classes, true)) {
        $existing_class = isset($atts['class']) ? $atts['class'] . ' ' : '';
        $atts['class'] = $existing_class . 'dropbtn';
    }

    return $atts;
}
add_filter('nav_menu_link_attributes', 'palmertech_nav_menu_link_attributes', 10, 4);
